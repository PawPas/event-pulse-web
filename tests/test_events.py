import io
import json

import pytest

_state: dict[str, str] = {}

VALID_ROW = {
    "customer_id": "c1",
    "timestamp": "2024-03-15T10:30:00Z",
    "event_type": "purchase",
    "amount": "49.99",
}


def make_csv_bytes(rows: list[dict]) -> bytes:
    cols = ["customer_id", "timestamp", "event_type", "amount"]
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join(str(r.get(c, "")) for c in cols))
    return "\n".join(lines).encode("utf-8")


def make_json_bytes(rows: list) -> bytes:
    return json.dumps(rows).encode("utf-8")


@pytest.fixture(scope="module")
def auth_token(test_client):
    resp = test_client.post(
        "/api/auth/register",
        json={"email": "events_user_a@test.com", "password": "secret"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_token_b(test_client):
    resp = test_client.post(
        "/api/auth/register",
        json={"email": "events_user_b@test.com", "password": "secret"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def report_id(test_client, auth_token):
    resp = test_client.post(
        "/api/reports/",
        json={"name": "Upload Test Report"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 201
    rid = resp.json()["id"]
    _state["report_id"] = rid
    return rid


def _upload(test_client, auth_token, report_id, filename, content_bytes, content_type="text/csv"):
    return test_client.post(
        f"/api/reports/{report_id}/events/upload",
        files={"file": (filename, io.BytesIO(content_bytes), content_type)},
        headers={"Authorization": f"Bearer {auth_token}"},
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_upload_unauthenticated(test_client, report_id):
    resp = test_client.post(
        f"/api/reports/{report_id}/events/upload",
        files={"file": ("data.csv", io.BytesIO(make_csv_bytes([VALID_ROW])), "text/csv")},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_upload_valid_csv(test_client, auth_token, report_id):
    rows = [VALID_ROW, {**VALID_ROW, "customer_id": "c2"}, {**VALID_ROW, "customer_id": "c3"}]
    resp = _upload(test_client, auth_token, report_id, "data.csv", make_csv_bytes(rows))
    assert resp.status_code == 200
    data = resp.json()
    assert data["events_added"] == 3


def test_upload_valid_json(test_client, auth_token, report_id):
    rows = [VALID_ROW, {**VALID_ROW, "customer_id": "c4"}]
    resp = _upload(test_client, auth_token, report_id, "data.json", make_json_bytes(rows), "application/json")
    assert resp.status_code == 200
    assert resp.json()["events_added"] == 2


def test_upload_appends_to_existing(test_client, auth_token, report_id):
    # First get current event count via report endpoint
    before = test_client.get(
        f"/api/reports/{report_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    ).json()["event_count"]

    rows = [{**VALID_ROW, "customer_id": "c_new"}]
    resp = _upload(test_client, auth_token, report_id, "more.csv", make_csv_bytes(rows))
    assert resp.status_code == 200
    assert resp.json()["events_added"] == 1

    after = test_client.get(
        f"/api/reports/{report_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    ).json()["event_count"]
    assert after == before + 1


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


def test_upload_wrong_user_report(test_client, auth_token_b, report_id):
    rows = [VALID_ROW]
    resp = _upload(test_client, auth_token_b, report_id, "data.csv", make_csv_bytes(rows))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Limit enforcement
# ---------------------------------------------------------------------------


def test_upload_exceeds_limit(test_client, auth_token, report_id):
    # Build 200001 minimal rows without holding them all in RAM as a big string
    header = "customer_id,timestamp,event_type,amount\n"
    row = "c1,2024-01-01T00:00:00Z,purchase,1.00\n"
    content = (header + row * 200_001).encode("utf-8")
    resp = _upload(test_client, auth_token, report_id, "big.csv", content)
    assert resp.status_code == 400
    assert "200,000" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_upload_missing_required_field(test_client, auth_token, report_id):
    bad = [{"customer_id": "c1", "timestamp": "2024-01-01T00:00:00Z", "event_type": "purchase"}]
    resp = _upload(test_client, auth_token, report_id, "bad.csv", make_csv_bytes(bad))
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "amount" in detail
    assert "Row 1" in detail


def test_upload_invalid_timestamp(test_client, auth_token, report_id):
    bad = [{**VALID_ROW, "timestamp": "not-a-date"}]
    resp = _upload(test_client, auth_token, report_id, "bad.csv", make_csv_bytes(bad))
    assert resp.status_code == 422
    assert "timestamp" in resp.json()["detail"]


def test_upload_invalid_amount(test_client, auth_token, report_id):
    bad = [{**VALID_ROW, "amount": "not-a-number"}]
    resp = _upload(test_client, auth_token, report_id, "bad.csv", make_csv_bytes(bad))
    assert resp.status_code == 422
    assert "amount" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Format / structure errors
# ---------------------------------------------------------------------------


def test_upload_unsupported_extension(test_client, auth_token, report_id):
    resp = _upload(test_client, auth_token, report_id, "data.txt", b"hello", "text/plain")
    assert resp.status_code == 400


def test_upload_json_not_array(test_client, auth_token, report_id):
    content = json.dumps({"key": "value"}).encode("utf-8")
    resp = _upload(test_client, auth_token, report_id, "data.json", content, "application/json")
    assert resp.status_code == 400
    assert "array" in resp.json()["detail"].lower()


def test_upload_csv_missing_header(test_client, auth_token, report_id):
    # CSV with a missing required column (no 'amount')
    content = b"customer_id,timestamp,event_type\nc1,2024-01-01T00:00:00Z,purchase"
    resp = _upload(test_client, auth_token, report_id, "noamt.csv", content)
    assert resp.status_code == 400
    assert "amount" in resp.json()["detail"]


def test_upload_empty_file(test_client, auth_token, report_id):
    resp = _upload(test_client, auth_token, report_id, "empty.csv", b"")
    assert resp.status_code == 400
