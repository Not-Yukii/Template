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
