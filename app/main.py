# ----------------------------------------------------------------
# IMPORTATIONS
# ----------------------------------------------------------------
from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timezone
import os
from passlib.context import CryptContext
import ollama
from . import recherche_web as web
from . import recherche_titre as titre

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:Admin@localhost:5432/test",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

app = FastAPI()

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

def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split()[1]
    user = db.query(User).filter(User.id == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
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

@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Email ou mot de passe incorrect")
    token = str(db_user.id)
    
    return {"message": "Logged in", "user_id": db_user.id, "token": token}

class SendMessage(BaseModel):
    conversation_id: int | None = None
    content: str
    use_web: bool

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
    
    return {[{"role": m.role, "content": m.content} for m in messages]}

@app.post("/send")
def send_message(
    payload: SendMessage,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.conversation_id:
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == user.id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        print(payload.content)
        conv = Conversation(user_id=user.id, title=titre.generate_title(payload.content))
        db.add(conv)
        db.commit()
        db.refresh(conv)
        
    user_msg = Message(conversation_id=conv.id, role="user", content=payload.content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    if payload.use_web:
        answer = web.recherche_web(payload.content)
    else:
        answer = ""

    assistant_msg = Message(conversation_id=conv.id, role="assistant", content=answer)
    db.add(assistant_msg)
    conv.last_update = datetime.now(timezone.utc)
    db.commit()
    return {"conversation_id": conv.id, "response": answer}