"""
Integration tests for the analysis endpoints:
  POST /api/reports/{id}/analysis/run
  GET  /api/reports/{id}/analysis/results

Uses the module-scoped test_client fixture (SQLite in-memory with StaticPool).
Background tasks run synchronously in TestClient, so polling completes in the
first iteration. The `_set_report_status` helper directly updates the DB via
get_session_factory() — which the conftest patches to use the test engine.
"""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select

from database import get_session_factory
from models.report import Report, ReportStatus

_KNOWN_SEGMENTS = {
    "Champions", "Loyal Customers", "Potential Loyalists",
    "At Risk", "Hibernating", "Others",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _set_report_status_async(report_id: str, new_status: ReportStatus) -> None:
    async with get_session_factory()() as db:
        result = await db.execute(select(Report).where(Report.id == UUID(report_id)))
        r = result.scalar_one()
        r.status = new_status
        await db.commit()


def _set_report_status(report_id: str, new_status: ReportStatus) -> None:
    asyncio.run(_set_report_status_async(report_id, new_status))


def _poll_until_done(test_client, auth_token: str, report_id: str, max_retries: int = 30) -> dict:
    """Poll GET /reports/{id} until status leaves 'analyzing'. Return final report dict."""
    import time
    for _ in range(max_retries):
        resp = test_client.get(f"/api/reports/{report_id}", headers=_headers(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] != "analyzing":
            return data
        time.sleep(1)  # only reached when running against a real server
    return resp.json()


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def auth_token(test_client):
    resp = test_client.post(
        "/api/auth/register",
        json={"email": "analysis_user_a@test.com", "password": "secret"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_token_b(test_client):
    resp = test_client.post(
        "/api/auth/register",
        json={"email": "analysis_user_b@test.com", "password": "secret"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def report_id(test_client, auth_token):
    """Create a report and seed 150 sample events."""
    resp = test_client.post(
        "/api/reports/",
        json={"name": "Analysis Integration Test Report"},
        headers=_headers(auth_token),
    )
    assert resp.status_code == 201
    rid = resp.json()["id"]

    resp = test_client.post(
        f"/api/reports/{rid}/events/sample",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 200
    return rid


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_run_unauthenticated(test_client, report_id):
    resp = test_client.post(f"/api/reports/{report_id}/analysis/run")
    assert resp.status_code == 401


def test_run_wrong_user(test_client, auth_token_b, report_id):
    resp = test_client.post(
        f"/api/reports/{report_id}/analysis/run",
        headers=_headers(auth_token_b),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_run_no_events(test_client, auth_token):
    resp = test_client.post(
        "/api/reports/",
        json={"name": "Empty Report"},
        headers=_headers(auth_token),
    )
    assert resp.status_code == 201
    empty_id = resp.json()["id"]

    resp = test_client.post(
        f"/api/reports/{empty_id}/analysis/run",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 400
    assert "no events" in resp.json()["detail"].lower()


def test_results_before_run(test_client, auth_token):
    resp = test_client.post(
        "/api/reports/",
        json={"name": "Fresh Report No Analysis"},
        headers=_headers(auth_token),
    )
    assert resp.status_code == 201
    fresh_id = resp.json()["id"]

    resp = test_client.get(
        f"/api/reports/{fresh_id}/analysis/results",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 404
    assert "run analysis" in resp.json()["detail"].lower()


def test_run_already_analyzing(test_client, auth_token, report_id):
    # Directly set the report into 'analyzing' state without triggering the
    # background task — using the test engine via get_session_factory().
    _set_report_status(report_id, ReportStatus.analyzing)

    try:
        resp = test_client.post(
            f"/api/reports/{report_id}/analysis/run",
            headers=_headers(auth_token),
        )
        assert resp.status_code == 409
        assert "in progress" in resp.json()["detail"].lower()
    finally:
        # Restore to created so subsequent tests can trigger analysis
        _set_report_status(report_id, ReportStatus.created)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_run_triggers_analysis(test_client, auth_token, report_id):
    resp = test_client.post(
        f"/api/reports/{report_id}/analysis/run",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "analyzing"

    # TestClient executes background tasks synchronously after the response, so
    # the report should already be in 'completed' state on the first poll.
    final = _poll_until_done(test_client, auth_token, report_id)
    assert final["status"] == "completed"


def test_results_shape(test_client, auth_token, report_id):
    resp = test_client.get(
        f"/api/reports/{report_id}/analysis/results",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["unique_customers"] > 0
    assert len(data["customers"]) == data["unique_customers"]
    assert set(data["segment_counts"].keys()) == _KNOWN_SEGMENTS  # PRD §RFM-algorithm: segment list is a fixed 6-element closed set
    assert sum(data["segment_counts"].values()) == data["unique_customers"]


def test_results_correctness(test_client, auth_token, report_id):
    resp = test_client.get(
        f"/api/reports/{report_id}/analysis/results",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify per-customer structure and score ranges
    for c in data["customers"]:
        assert c["segment"] in _KNOWN_SEGMENTS
        assert 1 <= c["r_score"] <= 5
        assert 1 <= c["f_score"] <= 5
        assert 1 <= c["m_score"] <= 5
        assert c["recency_days"] >= 0
        assert c["frequency"] >= 1
        assert c["monetary"] >= 0.0

    # Champions should have R≥4 AND F≥4
    champions = [c for c in data["customers"] if c["segment"] == "Champions"]
    for c in champions:
        assert c["r_score"] >= 4 and c["f_score"] >= 4


def test_rerun_completes(test_client, auth_token, report_id):
    # Report is already completed from test_run_triggers_analysis.
    # Re-running should succeed and update results.
    resp = test_client.post(
        f"/api/reports/{report_id}/analysis/run",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "analyzing"

    final = _poll_until_done(test_client, auth_token, report_id)
    assert final["status"] == "completed"

    # Results should still be accessible and valid
    resp = test_client.get(
        f"/api/reports/{report_id}/analysis/results",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["unique_customers"] > 0


# ---------------------------------------------------------------------------
# Failure path (O1 — visible `failed` state)
# ---------------------------------------------------------------------------


def _fresh_report_with_events(test_client, auth_token: str) -> str:
    resp = test_client.post(
        "/api/reports/",
        json={"name": "Failure Path Report"},
        headers=_headers(auth_token),
    )
    assert resp.status_code == 201
    rid = resp.json()["id"]
    resp = test_client.post(
        f"/api/reports/{rid}/events/sample",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 200
    return rid


def test_analysis_failure_sets_failed_status(test_client, auth_token, monkeypatch):
    """When compute_rfm raises, the background task must persist status=failed —
    not leave the report stuck in 'analyzing' (test-plan Risk #6)."""
    rid = _fresh_report_with_events(test_client, auth_token)

    def _boom(*args, **kwargs):
        raise ValueError("forced failure for test")

    # Patch the symbol as imported into routers.analysis (analysis.py:15),
    # which is what _run_analysis actually calls.
    monkeypatch.setattr("routers.analysis.compute_rfm", _boom)

    resp = test_client.post(
        f"/api/reports/{rid}/analysis/run",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 202

    final = _poll_until_done(test_client, auth_token, rid)
    assert final["status"] == "failed"


def test_results_on_failed_returns_409(test_client, auth_token, monkeypatch):
    """A failed analysis must be distinguishable from 'never run' — 409, not the
    same 404 that a fresh report returns."""
    rid = _fresh_report_with_events(test_client, auth_token)

    def _boom(*args, **kwargs):
        raise ValueError("forced failure for test")

    monkeypatch.setattr("routers.analysis.compute_rfm", _boom)
    test_client.post(
        f"/api/reports/{rid}/analysis/run",
        headers=_headers(auth_token),
    )
    _poll_until_done(test_client, auth_token, rid)

    resp = test_client.get(
        f"/api/reports/{rid}/analysis/results",
        headers=_headers(auth_token),
    )
    assert resp.status_code == 409
    assert "failed" in resp.json()["detail"].lower()
