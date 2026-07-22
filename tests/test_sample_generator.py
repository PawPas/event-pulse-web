import io

import pytest

from tests.test_events import make_csv_bytes, VALID_ROW


@pytest.fixture(scope="module")
def auth_token(test_client):
    resp = test_client.post(
        "/api/auth/register",
        json={"email": "sample_user_a@test.com", "password": "secret"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_token_b(test_client):
    resp = test_client.post(
        "/api/auth/register",
        json={"email": "sample_user_b@test.com", "password": "secret"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def report_id(test_client, auth_token):
    resp = test_client.post(
        "/api/reports/",
        json={"name": "Sample Generator Test Report"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _generate(test_client, auth_token, report_id, body=None):
    kwargs = {"headers": {"Authorization": f"Bearer {auth_token}"}}
    if body is not None:
        kwargs["json"] = body
    return test_client.post(f"/api/reports/{report_id}/events/sample", **kwargs)


def _event_count(test_client, auth_token, report_id) -> int:
    resp = test_client.get(
        f"/api/reports/{report_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    return resp.json()["event_count"]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_generate_unauthenticated(test_client, report_id):
    resp = test_client.post(f"/api/reports/{report_id}/events/sample")
    assert resp.status_code == 401


def test_generate_wrong_user(test_client, auth_token_b, report_id):
    resp = _generate(test_client, auth_token_b, report_id)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_generate_default(test_client, auth_token, report_id):
    before = _event_count(test_client, auth_token, report_id)
    resp = _generate(test_client, auth_token, report_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["events_added"] == 150
    after = _event_count(test_client, auth_token, report_id)
    assert after == before + 150


def test_generate_custom_count(test_client, auth_token, report_id):
    before = _event_count(test_client, auth_token, report_id)
    resp = _generate(test_client, auth_token, report_id, body={"count": 5})
    assert resp.status_code == 200
    assert resp.json()["events_added"] == 5
    after = _event_count(test_client, auth_token, report_id)
    assert after == before + 5


def test_generate_appends(test_client, auth_token, report_id):
    before = _event_count(test_client, auth_token, report_id)
    resp = _generate(test_client, auth_token, report_id)
    assert resp.status_code == 200
    assert resp.json()["events_added"] == 150
    after = _event_count(test_client, auth_token, report_id)
    assert after == before + 150


# ---------------------------------------------------------------------------
# Cap enforcement
# ---------------------------------------------------------------------------


def test_generate_exceeds_cap_standalone(test_client, auth_token, report_id):
    resp = _generate(test_client, auth_token, report_id, body={"count": 200_001})
    assert resp.status_code == 400
    assert "200,000" in resp.json()["detail"]


def test_generate_cap_combined(test_client, auth_token):
    # Create a fresh report so we control the baseline event count precisely
    resp = test_client.post(
        "/api/reports/",
        json={"name": "Cap Combined Test"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 201
    cap_report_id = resp.json()["id"]

    # Upload a small CSV to establish a baseline
    rows = [VALID_ROW, {**VALID_ROW, "customer_id": "c2"}]
    upload_resp = test_client.post(
        f"/api/reports/{cap_report_id}/events/upload",
        files={"file": ("data.csv", io.BytesIO(make_csv_bytes(rows)), "text/csv")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["events_added"] == 2

    # Request enough to push combined total over 200k
    resp = _generate(test_client, auth_token, cap_report_id, body={"count": 200_000})
    assert resp.status_code == 400
    assert "200,000" in resp.json()["detail"]
