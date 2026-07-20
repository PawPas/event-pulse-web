import pytest
from fastapi.testclient import TestClient

EMAIL = "testuser@example.com"
PASSWORD = "supersecret"


def test_register_success(test_client: TestClient):
    response = test_client.post(
        "/api/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["access_token"]
    assert data["user"]["email"] == EMAIL


def test_register_duplicate_email(test_client: TestClient):
    response = test_client.post(
        "/api/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_login_success(test_client: TestClient):
    response = test_client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]


def test_login_wrong_password(test_client: TestClient):
    response = test_client.post(
        "/api/auth/login", json={"email": EMAIL, "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_logout(test_client: TestClient):
    response = test_client.post("/api/auth/logout")
    assert response.status_code == 200
