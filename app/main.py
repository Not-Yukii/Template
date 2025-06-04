from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime
import os
from passlib.context import CryptContext
import requests
from bs4 import BeautifulSoup
try:
    import ollama
except Exception:  # pragma: no cover - optional dependency
    ollama = None

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


SERPER_API_KEY = "3ac3421edc9038fe814fcf282616bd4c93e5999d"
MODEL_NAME = "llama3.1:8b"
NB_SITES_MAX = 3


def generer_requete_web(question_utilisateur: str) -> str:
    if ollama is None:
        return ""
    today = datetime.now().date()
    date_str = today.strftime("%d/%m/%Y")
    system_prompt = (
        "Tu es spécialisé dans la recherche d'informations sur Internet et travail "
        "pour des étudiants en cybersécurité."
    )
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question_utilisateur.strip()},
            ],
        )
        return response["message"]["content"].strip()
    except Exception:
        return ""


def recherche_serper(query: str, max_results: int) -> list[str]:
    url_api = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query}
    try:
        resp = requests.post(url_api, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return []
    data = resp.json()
    liens = []
    if "organic" in data and isinstance(data["organic"], list):
        for item in data["organic"][:max_results]:
            if "link" in item:
                liens.append(item["link"])
    return liens


def recuperer_contenu_site(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup([
        "script",
        "style",
        "noscript",
        "header",
        "footer",
        "nav",
        "aside",
    ]):
        tag.decompose()
    textes = soup.stripped_strings
    return "\n".join(textes)[:50000]


def synthese_contenu(question_initiale: str, url: str, contenu_site: str) -> str:
    if ollama is None:
        return ""
    system_prompt = "Tu es un expert très compétent chargé de répondre en utilisant les fragments d'informations donnés."
    user_prompt = f"Question: {question_initiale}\nURL: {url}\nContenu:\n{contenu_site}"
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        )
        return response["message"]["content"].strip()
    except Exception:
        return ""


def generate_answer(question: str) -> str:
    if ollama is None:
        return ""
    requete = generer_requete_web(question)
    if not requete or "#impossible#" in requete:
        return ""
    liens = recherche_serper(requete, NB_SITES_MAX)
    for url in liens:
        contenu = recuperer_contenu_site(url)
        if contenu:
            rep = synthese_contenu(question, url, contenu)
            if rep:
                return rep
    return ""

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
    started_at = Column(DateTime, default=datetime.utcnow)
    last_update = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String)
    content = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

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
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = str(db_user.id)
    return {"message": "Logged in", "user_id": db_user.id, "token": token}


class SendMessage(BaseModel):
    conversation_id: int | None = None
    content: str


@app.get("/conversations")
def list_conversations(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    convs = db.query(Conversation).filter(Conversation.user_id == user.id).all()
    return [{"id": c.id, "title": c.title} for c in convs]


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
def send_message(
    payload: SendMessage,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
        conv = Conversation(user_id=user.id, title=payload.content[:30])
        db.add(conv)
        db.commit()
        db.refresh(conv)
    user_msg = Message(conversation_id=conv.id, role="user", content=payload.content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    answer = generate_answer(payload.content)
    assistant_msg = Message(conversation_id=conv.id, role="assistant", content=answer)
    db.add(assistant_msg)
    conv.last_update = datetime.utcnow()
    db.commit()
    return {"conversation_id": conv.id, "response": answer}
