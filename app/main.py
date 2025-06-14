import sys
import asyncio
import os
import re
import argparse
import smtplib
import tempfile, shutil

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
from pathlib import Path
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import Boolean, create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timezone
from langchain.prompts.chat import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_community.llms.ollama import Ollama
from passlib.context import CryptContext
from datetime import timedelta
from jose import JWTError, jwt
from fastapi import status
from jose import JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import Form, File, UploadFile
from email.mime.text import MIMEText
from . import recherche_web as web
from . import recherche_titre as titre
from . import recherche_local as local

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
base_url = "http://ollamaProjet4A:11434"

FRONTEND_URL = "http://192.168.100.1:8000"

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise EnvironmentError("SECRET_KEY environment variable not set")

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

# --- création et vérif de jeton ---
def create_email_verification_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(hours=1)
    payload = {"sub": str(user_id), "exp": expire, "type": "verify"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_email_token(token: str) -> int:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "verify":
        raise JWTError("Wrong token type")
    return int(payload["sub"])

# --- envoi via Gmail SMTP ---
def send_verification_email(to_email: str, token: str):
    verify_link = f"{FRONTEND_URL}/verify-email?token={token}"
    body = (
        f"Bonjour,\n\n"
        f"Merci de vous être inscrit.\n"
        f"Cliquez sur ce lien pour vérifier votre adresse : {verify_link}\n\n"
        f"Ce lien est valable 1 h."
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "Vérification de votre email"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    is_verified = Column(Boolean, default=False) 

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
    email: EmailStr
    password: str

    @field_validator("password")
    def password_must_be_strong(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Le mot de passe doit contenir au moins 12 caractères")
        if not re.search(r"[a-z]", v):
            raise ValueError("Il faut au moins une minuscule")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Il faut au moins une majuscule")
        if not re.search(r"\d", v):
            raise ValueError("Il faut au moins un chiffre")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Il faut au moins un caractère spécial")
        return v

class UserLogin(BaseModel):
    email: EmailStr
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
    if len(user.password) and not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{12,}$", user.password):
        raise HTTPException(
            status_code=400,
            detail="Le mot de passe doit contenir au moins 12 caractères, "
                   "une minuscule, une majuscule, un chiffre et un caractère spécial.",
        )
    hashed = get_password_hash(user.password)
    new_user = User(email=user.email, password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    token = create_email_verification_token(new_user.id)
    try:
        send_verification_email(new_user.email, token)
    except Exception as e:
        db.delete(new_user)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'envoi de l'email de vérification. "
                   "Veuillez réessayer plus tard.",
        )
    
    return {"message": "Compte créé. Vérifiez votre boîte mail pour activer le compte."}

@app.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        user_id = verify_email_token(token)
    except JWTError:
        db_user = db.query(User).filter(User.id == user_id).first()
        db.delete(db_user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de vérification invalide ou expiré",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur non trouvé")
    
    if user.is_verified:
        return {"message": "Email déjà vérifié"}
    
    user.is_verified = True
    db.commit()
    
    return {"message": "Email vérifié avec succès"}

@app.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not db_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email non vérifié. Veuillez vérifier votre boîte mail.",
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
async def get_chat(
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

def _process_upload(up_file: UploadFile, conv_id: int):
    """
    Lit un UploadFile, extrait le texte, le découpe puis stocke chaque chunk
    dans la mémoire vectorielle. 100 % synchrone → à exécuter dans un thread.
    """
    suffix = Path(up_file.filename).suffix.lower()
    if suffix not in {".pdf", ".txt", ".md", ".markdown"}:
        raise ValueError("Extension non autorisée")

    filename =  os.path.basename(up_file.filename)
    if not filename or filename != up_file.filename:
        raise ValueError("Invalid filename")

    up_file.file.seek(0, os.SEEK_END)
    size = up_file.file.tell()
    up_file.file.seek(0)
    if size > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 25 MB.",
        )

    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, filename)
    with open(tmp_path, "wb") as buffer:
        shutil.copyfileobj(up_file.file, buffer)

    # Extraction -------------------------------------------------------------
    if suffix == ".pdf":
        loader = PyPDFLoader(tmp_path)
        docs = loader.load()
        file_text = "\n".join(d.page_content for d in docs)
    elif suffix in {".md", ".markdown"}:
        loader = UnstructuredMarkdownLoader(tmp_path)
        docs = loader.load()
        file_text = "\n".join(d.page_content for d in docs)
    else:                       # .txt
        with open(tmp_path, "r", encoding="utf-8") as f:
            file_text = f.read()

    # Mémoire courte ---------------------------------------------------------
    local.insert_message_and_memory(conv_id, "file", file_text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=250000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )
    virtual_doc = Document(page_content=file_text, metadata={})
    chunks = splitter.split_documents([virtual_doc])

    for ch in chunks:
        ch.page_content = (
            f"<file> Fichier {up_file.filename} :\n{ch.page_content}\n</file>"
        )
        local.insert_message_and_memory(conv_id, "file", ch.page_content)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    
    return file_text

def _get_conv(cid: int, uid: int):
    with SessionLocal() as s:
        return (
            s.query(Conversation)
             .filter(Conversation.id == cid, Conversation.user_id == uid)
             .first()
        )
        
def _create_conv(u_id: int, title: str, ts: str):
    with SessionLocal() as s:
        conv = Conversation(user_id=u_id, title=title, last_update=ts)
        s.add(conv)
        s.commit()
        s.refresh(conv)
        return conv

def _touch_conv(cid: int):
    with SessionLocal() as s:
        s.query(Conversation).filter(Conversation.id == cid)\
          .update({"last_update": datetime.now(timezone.utc)})
        s.commit()
        
def find_emotions(text: str) -> List[str]:
    """
    Trouve les émotions dans le texte.
    """
    EMOTIONS = [
    "#colère#", "#détective#", "#fatigué#", "#heureux#", "#inquiet#",
    "#intelligent#", "#naturel#", "#pensif#", "#professeur#", "#effrayant#",
    "#triste#", "#soulagé#", "#amoureux#", "#endormi#", "#surpris#"
    ]
    EMOTIONS_SET = set(EMOTIONS)
    EMOTIONS_STR = ", ".join(EMOTIONS)

    SYSTEM_PROMPT = (
        "You are an *emotion tagger*. "
        "You MUST answer with **exactly one tag** from the list below, "
        "including the surrounding # symbols. "
        "If none applies, answer with #naturel#.\n\n"
        f"Allowed tags: [{EMOTIONS_STR}]"
    )

    HUMAN_PROMPT = "Text: {text}"
    
    prompt_template = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
        HumanMessagePromptTemplate.from_template(HUMAN_PROMPT),
    ])

    llm = Ollama(model="granite3.1-dense:latest", temperature=0, base_url=base_url)
    
    raw = llm.invoke(prompt_template.format(text=text)).strip()

    match = re.search(r"#\w+#", raw)
    if match:
        tag = match.group(0)
        if tag in EMOTIONS_SET:
            return tag

    for tag in EMOTIONS:
        plain = tag.strip("#").lower()
        if plain in raw.lower():
            return tag

    return "#naturel#"
        
@app.post("/send")
async def send_message(
    content: str = Form(...),
    use_web: bool = Form(False),
    conversation_id: Optional[int] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
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
        conv = await asyncio.to_thread(_get_conv, conversation_id, user.id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        title = await asyncio.to_thread(titre.generate_title, content)
        conv = await asyncio.to_thread(_create_conv, user.id, title, datetime.now(timezone.utc))
    filenames = []
    
    texts_from_files: List[str] = [] 
    if files:
        filenames = [f.filename for f in files]
        # print(f"Fichiers reçus : {[f.filename for f in files]}")
        # print(f"Taille des fichiers : {[f.file.size for f in files]} octets")
        tasks = [asyncio.to_thread(_process_upload, f, conv.id) for f in files]
        texts_from_files = await asyncio.gather(*tasks)

    user_msg_id = await asyncio.to_thread(local.insert_message_and_memory, conv.id, "user", content)
    
    emotion = find_emotions(content)

    if use_web:
        answer = await asyncio.to_thread(web.recherche_web, content)
        await asyncio.to_thread(local.insert_message_and_memory, conv.id, "assistant", answer)
    else:
        answer = await asyncio.to_thread(local.answer_with_memory, content, conv.id, file_names=filenames, texts_from_files=texts_from_files)
    conv.last_update = datetime.now(timezone.utc)
    await asyncio.to_thread(_touch_conv, conv.id)

    return {"conversation_id": conv.id, "response": answer, "title": conv.title, "emotion": emotion}

@app.post("/delete_conversation/{conversation_id}")
async def delete_conversation(
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

    db.query(Message).filter(Message.conversation_id == conv.id).delete()
    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted"}

@app.post("/logout")
def logout():
    return {"message": "Logged out successfully"}