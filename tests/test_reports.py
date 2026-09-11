import pytest

_state: dict[str, str] = {}


@pytest.fixture(scope="module")
def auth_token(test_client):
    response = test_client.post(
        "/api/auth/register",
        json={"email": "reports_user_a@test.com", "password": "secret"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_token_b(test_client):
    response = test_client.post(
        "/api/auth/register",
        json={"email": "reports_user_b@test.com", "password": "secret"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_create_report_unauthenticated(test_client):
    response = test_client.post("/api/reports/", json={"name": "Test"})
    assert response.status_code == 401


def test_create_report_success(test_client, auth_token):
    response = test_client.post(
        "/api/reports/",
        json={"name": "Q4 Report"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Q4 Report"
    assert data["event_count"] == 0
    assert data["status"] == "created"
    _state["report_id"] = data["id"]


def test_create_report_missing_name(test_client, auth_token):
    response = test_client.post(
        "/api/reports/",
        json={},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422


def test_list_reports(test_client, auth_token):
    response = test_client.get(
        "/api/reports/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_count"] == 0


def test_get_report_success(test_client, auth_token):
    response = test_client.get(
        f"/api/reports/{_state['report_id']}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Q4 Report"


def test_get_report_not_found(test_client, auth_token):
    response = test_client.get(
        "/api/reports/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


def test_update_report_success(test_client, auth_token):
    response = test_client.patch(
        f"/api/reports/{_state['report_id']}",
        json={"name": "Q4 Report (renamed)", "description": "After review"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Q4 Report (renamed)"
    assert data["description"] == "After review"

    get_response = test_client.get(
        f"/api/reports/{_state['report_id']}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Q4 Report (renamed)"


def test_update_report_partial(test_client, auth_token):
    response = test_client.patch(
        f"/api/reports/{_state['report_id']}",
        json={"description": None},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Q4 Report (renamed)"
    assert data["description"] is None


def test_update_report_empty_payload(test_client, auth_token):
    response = test_client.patch(
        f"/api/reports/{_state['report_id']}",
        json={},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422


def test_update_report_null_name(test_client, auth_token):
    response = test_client.patch(
        f"/api/reports/{_state['report_id']}",
        json={"name": None},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422


def test_update_report_not_found(test_client, auth_token):
    response = test_client.patch(
        "/api/reports/00000000-0000-0000-0000-000000000000",
        json={"name": "X"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


def test_update_report_unauthenticated(test_client):
    response = test_client.patch(
        f"/api/reports/{_state['report_id']}",
        json={"name": "X"},
    )
    assert response.status_code == 401


def test_isolation_get(test_client, auth_token_b):
    response = test_client.get(
        f"/api/reports/{_state['report_id']}",
        headers={"Authorization": f"Bearer {auth_token_b}"},
    )
    assert response.status_code == 404


def test_isolation_update(test_client, auth_token_b):
    response = test_client.patch(
        f"/api/reports/{_state['report_id']}",
        json={"name": "Hijacked"},
        headers={"Authorization": f"Bearer {auth_token_b}"},
    )
    assert response.status_code == 404


def test_isolation_delete(test_client, auth_token_b):
    response = test_client.delete(
        f"/api/reports/{_state['report_id']}",
        headers={"Authorization": f"Bearer {auth_token_b}"},
    )
    assert response.status_code == 404


def test_delete_report_success(test_client, auth_token):
    response = test_client.delete(
        f"/api/reports/{_state['report_id']}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 204
    get_response = test_client.get(
        f"/api/reports/{_state['report_id']}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert get_response.status_code == 404
