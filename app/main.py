import sys
import asyncio

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# ----------------------------------------------------------------
# IMPORTATIONS
# ----------------------------------------------------------------
from fastapi import FastAPI, Depends, HTTPException, Header, Body, UploadFile, File
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_community.document_loaders.markdown import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema import Document
import tempfile, shutil
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timezone
import os
from passlib.context import CryptContext
from datetime import timedelta
from jose import JWTError, jwt
from pydantic import BaseModel
from fastapi import status
from jose import JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from . import recherche_web as web
from . import recherche_titre as titre
from . import recherche_local as local

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:Admin@localhost:5432/test",
)

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "#Pr0j3tI@2025!"
)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Token(BaseModel):
    access_token: str
    token_type: str

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    # ⚠️ mettez toujours l'ID en str pour suivre la spec JWT
    to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_access_token(token: str) -> int:
    """
    Renvoie l'user_id si le token est valide, sinon lève une exception.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # print(f"Payload décodé: {payload}")
        user_id: int = payload.get("sub")
        if user_id is None:
            raise JWTError("Subject manquant")
        return int(user_id)
    except JWTError:
        raise JWTError("Jeton invalide ou expiré")
    
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String)
    started_at = Column(DateTime, default=datetime.now(timezone.utc))
    last_update = Column(DateTime, default=datetime.now(timezone.utc))

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String)
    content = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await web.get_serper_api_key()
    yield

app = FastAPI(lifespan=lifespan)

class UserCreate(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """
    - HTTPBearer extrait « Authorization: Bearer <token> » et met <token> dans credentials.credentials.
    - On vérifie ensuite le JWT.
    """
    token = credentials.credentials
    # print(f"Token reçu: {token}") 
    try:
        user_id = verify_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )
    return user

@app.post("/register")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = get_password_hash(user.password)
    new_user = User(email=user.email, password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "email": new_user.email}

@app.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

class SendMessage(BaseModel):
    conversation_id: int | None = None
    content: str
    use_web: bool = False

@app.get("/conversations")
def list_conversations(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    convs = db.query(Conversation).filter(Conversation.user_id == user.id).all()
    return [{"id": c.id, "title": c.title, "last_update": c.last_update} for c in convs]


@app.get("/chat/{conversation_id}")
def get_chat(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
        .all()
    )
    
    return [{"role": m.role, "content": m.content} for m in messages]

@app.post("/send")
async def send_message(
    content: str = Body(...),
    use_web: bool = Body(False),
    conversation_id: int | None = Body(None),
    file: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    - content   : le texte du message utilisateur
    - use_web   : bool (est-ce qu’on veut faire une recherche web ?)
    - conversation_id : si existante, on écrit dans cette conv sinon on crée une nouvelle conv.
    - file      : UploadFile facultatif (.pdf, .txt, .md). Si fourni, on extrait le texte
                  et on l’insère dans memories pour cette conversation, avant de traiter content.
    """
    if conversation_id != -1:
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        title = titre.generate_title(content)
        conv = Conversation(user_id=user.id, title=title)
        db.add(conv)
        db.commit()
        db.refresh(conv)

    if file is not None:
        filename = file.filename
        suffix = Path(filename).suffix.lower()
        if suffix not in {".pdf", ".txt", ".md", ".markdown"}:
            raise HTTPException(status_code=400, detail="Extension non autorisée")

        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, filename)
        try:
            with open(tmp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur stockage temporaire: {e}")

        try:
            if suffix == ".pdf":
                loader = PyPDFLoader(tmp_path)
                docs = loader.load()
                file_text = "\n".join([d.page_content for d in docs])
            elif suffix == ".md" or suffix == ".markdown":
                loader = UnstructuredMarkdownLoader(tmp_path)
                docs = loader.load()
                file_text = "\n".join([d.page_content for d in docs])
            elif suffix == ".txt":
                with open(tmp_path, "r", encoding="utf-8") as ftxt:
                    file_text = ftxt.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur extraction contenu: {e}")

        local.insert_message_and_memory(conv.id, "file", file_text)

        try:
            shutil.rmtree(tmp_dir)
        except:
            pass
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=120,
            length_function=len,
            is_separator_regex=False,
        )
        
        virtual_doc = Document(page_content=file_text, metadata={})
        chunks = splitter.split_documents([virtual_doc])

        for ch in chunks:
            ch.page_content = f"<document>\n{ch.page_content}\n</document>"
            local.insert_message_and_memory(conv.id, "file", ch.page_content)

    user_msg_id = local.insert_message_and_memory(conv.id, "user", content)

    if use_web:
        answer = web.recherche_web(content)
        local.insert_message_and_memory(conv.id, "assistant", answer)
    else:
        answer = local.answer_with_memory(content, conv.id)

    conv.last_update = datetime.now(timezone.utc)
    db.commit()

    return {"conversation_id": conv.id, "response": answer}

@app.post("/delete_conversation/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted"}