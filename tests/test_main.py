import os
import sys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the application module can be imported
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
os.environ["DATABASE_URL"] = SQLALCHEMY_DATABASE_URL

# Import the app and models
import app.main as main

# Create a new SQLite engine and session for testing
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Recreate the tables on the test database
main.Base.metadata.drop_all(bind=engine)
main.Base.metadata.create_all(bind=engine)

# Dependency override for testing

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

main.app.dependency_overrides[main.get_db] = override_get_db

client = TestClient(main.app)

def test_register_and_login():
    response = client.post("/register", json={"email": "test@example.com", "password": "secret"})
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

    response = client.post("/login", json={"email": "test@example.com", "password": "secret"})
    assert response.status_code == 200
    assert response.json()["message"] == "Logged in"
    assert "token" in response.json()


def test_duplicate_register():
    client.post("/register", json={"email": "dup@example.com", "password": "pass"})
    response = client.post("/register", json={"email": "dup@example.com", "password": "pass"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_invalid_login():
    client.post("/register", json={"email": "login@example.com", "password": "good"})
    response = client.post("/login", json={"email": "login@example.com", "password": "bad"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid credentials"
    
def test_list_conversations(monkeypatch):
    client.post("/register", json={"email": "list@example.com", "password": "pw"})
    login_resp = client.post("/login", json={"email": "list@example.com", "password": "pw"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/conversations", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_send_and_chat(monkeypatch):
    client.post("/register", json={"email": "conv@example.com", "password": "pw"})
    login_resp = client.post("/login", json={"email": "conv@example.com", "password": "pw"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(main, "generate_answer", lambda q: "answer")

    resp = client.post("/send", json={"content": "hello"}, headers=headers)
    assert resp.status_code == 200
    conv_id = resp.json()["conversation_id"]
    assert resp.json()["response"] == "answer"

    resp = client.get("/conversations", headers=headers)
    assert resp.status_code == 200
    assert any(c["id"] == conv_id for c in resp.json())

    resp = client.get(f"/chat/{conv_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "answer"},
    ]


def test_send_nonexistent_conversation(monkeypatch):
    client.post("/register", json={"email": "noc@example.com", "password": "pw"})
    login_resp = client.post("/login", json={"email": "noc@example.com", "password": "pw"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(main, "generate_answer", lambda q: "ans")

    resp = client.post(
        "/send",
        json={"conversation_id": 9999, "content": "hi"},
        headers=headers,
    )
    assert resp.status_code == 404