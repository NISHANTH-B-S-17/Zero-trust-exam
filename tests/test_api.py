import pytest
from fastapi.testclient import TestClient
from nivasha.api.main import app, get_db
from nivasha.core.database import Base, engine, SessionLocal
from nivasha.models import domain

# Setup test DB
Base.metadata.create_all(bind=engine)

@pytest.fixture(scope="module")
def client():
    # Use real DB for simple tests, rollback normally in complex apps
    with TestClient(app) as c:
        yield c

def test_seed_data(client):
    response = client.post("/seed")
    assert response.status_code == 200
    assert "admin" in response.json()["msg"] or "Already seeded" in response.json()["msg"]

def test_create_question_success(client):
    # User 2 is creator
    response = client.post(
        "/questions/",
        headers={"x-user-id": "2"},
        json={"topic": "Math", "content": "What is 2+2?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "Math"
    assert "content" not in data # Content should not be in standard response

def test_create_question_forbidden(client):
    # User 3 is student
    response = client.post(
        "/questions/",
        headers={"x-user-id": "3"},
        json={"topic": "Math", "content": "What is 2+2?"}
    )
    assert response.status_code == 403

def test_read_question_decrypted(client):
    # User 2 (creator) viewing their own question
    # First, let's create a fresh question to guarantee we have the right key in memory
    post_response = client.post(
        "/questions/",
        headers={"x-user-id": "2"},
        json={"topic": "Math", "content": "What is 2+2?"}
    )
    new_q_id = post_response.json()["id"]

    response = client.get(f"/questions/{new_q_id}", headers={"x-user-id": "2"})
    assert response.status_code == 200
    assert response.json()["content"] == "What is 2+2?"
