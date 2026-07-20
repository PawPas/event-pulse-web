from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_db_health_ok():
    with patch("main.engine_health_check", new=AsyncMock(return_value=True)):
        response = client.get("/api/health/db")
    assert response.status_code == 200
    assert response.json() == {"db": "ok"}


def test_db_health_fails():
    with patch("main.engine_health_check", new=AsyncMock(return_value=False)):
        response = client.get("/api/health/db")
    assert response.status_code == 503
