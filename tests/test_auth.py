from fastapi.testclient import TestClient

from auth.security import create_access_token
from main import app

client = TestClient(app)


def test_me_valid_token():
    token = create_access_token(subject="user-123", email="test@example.com")
    response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["sub"] == "user-123"
    assert data["email"] == "test@example.com"


def test_me_no_token():
    response = client.get("/api/me")
    assert response.status_code == 401


def test_me_tampered_token():
    response = client.get("/api/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert response.status_code == 401
