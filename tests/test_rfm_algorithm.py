"""
Unit tests for services.rfm.compute_rfm.

No database or HTTP server involved — pure Python.

Fixture design (5-customer dataset):
  analysis_ts = 2024-01-10 UTC

  Customer | Last event   | Recency | Frequency | Monetary ($)
  ---------|--------------|---------|-----------|-------------
  cA       | 2024-01-09   |  1 day  |    10     |   500.00
  cB       | 2023-12-31   | 10 days |     7     |   200.00
  cC       | 2023-12-21   | 20 days |     5     |   100.00
  cD       | 2023-12-01   | 40 days |     3     |    50.00
  cE       | 2023-10-22   | 80 days |     1     |    10.00

Pre-calculated quintile cut-points (statistics.quantiles, n=5, method='exclusive'):
  Recency : [2.8, 14.0, 32.0, 72.0]
  Frequency: [1.4, 3.8, 6.2, 9.4]
  Monetary : [18.0, 70.0, 160.0, 440.0]

Expected R/F/M scores and segments:
  cA: R=5, F=5, M=5 → Champions
  cB: R=4, F=4, M=4 → Champions
  cC: R=3, F=3, M=3 → Others
  cD: R=2, F=2, M=2 → Hibernating
  cE: R=1, F=1, M=1 → Hibernating
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.rfm import compute_rfm

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ANALYSIS_TS = datetime(2024, 1, 10, tzinfo=timezone.utc)


def _event(customer_id: str, date: tuple, event_type: str = "purchase", amount: str = "0") -> dict:
    y, m, d = date
    return {
        "customer_id": customer_id,
        "timestamp": datetime(y, m, d, 12, 0, 0, tzinfo=timezone.utc),
        "event_type": event_type,
        "amount": Decimal(amount),
    }


def _make_fixture_events() -> list[dict]:
    events = []
    # cA: 10 purchase events, last on Jan 9
    for _ in range(10):
        events.append(_event("cA", (2024, 1, 9), "purchase", "50.00"))
    # cB: 7 purchase events, last on Dec 31
    for _ in range(7):
        events.append(_event("cB", (2023, 12, 31), "purchase", "28.57"))
    # cC: 5 purchase events, last on Dec 21
    for _ in range(5):
        events.append(_event("cC", (2023, 12, 21), "purchase", "20.00"))
    # cD: 3 purchase events, last on Dec 1
    for _ in range(3):
        events.append(_event("cD", (2023, 12, 1), "purchase", "16.67"))
    # cE: 1 purchase event, last on Oct 22
    events.append(_event("cE", (2023, 10, 22), "purchase", "10.00"))
    return events


# ---------------------------------------------------------------------------
# Normal 5-customer fixture
# ---------------------------------------------------------------------------


def test_normal_fixture_segment_counts_total():
    result = compute_rfm(_make_fixture_events(), ANALYSIS_TS)
    assert result["unique_customers"] == 5
    assert sum(result["segment_counts"].values()) == 5


def test_normal_fixture_all_six_segments_present_as_keys():
    result = compute_rfm(_make_fixture_events(), ANALYSIS_TS)
    expected_keys = {"Champions", "Loyal Customers", "Potential Loyalists", "At Risk", "Hibernating", "Others"}
    assert set(result["segment_counts"].keys()) == expected_keys


def test_normal_fixture_expected_scores():
    result = compute_rfm(_make_fixture_events(), ANALYSIS_TS)
    by_id = {c["customer_id"]: c for c in result["customers"]}

    assert by_id["cA"]["r_score"] == 5
    assert by_id["cA"]["f_score"] == 5
    assert by_id["cA"]["m_score"] == 5
    assert by_id["cA"]["segment"] == "Champions"

    assert by_id["cB"]["r_score"] == 4
    assert by_id["cB"]["f_score"] == 4
    assert by_id["cB"]["segment"] == "Champions"

    assert by_id["cC"]["r_score"] == 3
    assert by_id["cC"]["f_score"] == 3
    assert by_id["cC"]["segment"] == "Others"

    assert by_id["cD"]["r_score"] == 2
    assert by_id["cD"]["f_score"] == 2
    assert by_id["cD"]["segment"] == "Hibernating"

    assert by_id["cE"]["r_score"] == 1
    assert by_id["cE"]["f_score"] == 1
    assert by_id["cE"]["segment"] == "Hibernating"


def test_normal_fixture_recency_days():
    result = compute_rfm(_make_fixture_events(), ANALYSIS_TS)
    by_id = {c["customer_id"]: c for c in result["customers"]}
    assert by_id["cA"]["recency_days"] == 1
    assert by_id["cB"]["recency_days"] == 10
    assert by_id["cC"]["recency_days"] == 20
    assert by_id["cD"]["recency_days"] == 40
    assert by_id["cE"]["recency_days"] == 80


# ---------------------------------------------------------------------------
# Single-customer edge case
# ---------------------------------------------------------------------------


def test_single_customer_all_scores_3():
    events = [_event("solo", (2024, 1, 9), "purchase", "100.00")]
    result = compute_rfm(events, ANALYSIS_TS)
    assert result["unique_customers"] == 1
    c = result["customers"][0]
    assert c["r_score"] == 3
    assert c["f_score"] == 3
    assert c["m_score"] == 3
    assert c["segment"] == "Others"


def test_single_customer_segment_counts():
    events = [_event("solo", (2024, 1, 9), "purchase", "100.00")]
    result = compute_rfm(events, ANALYSIS_TS)
    assert result["segment_counts"]["Others"] == 1
    assert sum(result["segment_counts"].values()) == 1


# ---------------------------------------------------------------------------
# All-same-recency edge case → all R scores = 3
# ---------------------------------------------------------------------------


def test_all_same_recency_r_scores_are_3():
    same_date = (2024, 1, 5)  # 5 days before analysis_ts
    events = [
        _event("x1", same_date, "purchase", "100.00"),
        _event("x1", same_date, "purchase", "100.00"),  # 2 events for x1
        _event("x2", same_date, "purchase", "50.00"),
        _event("x3", same_date, "purchase", "10.00"),
    ]
    result = compute_rfm(events, ANALYSIS_TS)
    for c in result["customers"]:
        assert c["r_score"] == 3, f"{c['customer_id']} had r_score={c['r_score']}, expected 3"
    assert all(c["recency_days"] == 5 for c in result["customers"])


# ---------------------------------------------------------------------------
# Purchase-only monetary
# ---------------------------------------------------------------------------


def test_purchase_only_monetary():
    events = [
        # c_buyer: 2 purchases + 1 page_view
        _event("c_buyer", (2024, 1, 5), "purchase", "100.00"),
        _event("c_buyer", (2024, 1, 5), "purchase", "50.00"),
        _event("c_buyer", (2024, 1, 5), "page_view", "0.00"),
        # c_viewer: 3 page_views, no purchases
        _event("c_viewer", (2024, 1, 5), "page_view", "0.00"),
        _event("c_viewer", (2024, 1, 5), "page_view", "0.00"),
        _event("c_viewer", (2024, 1, 5), "page_view", "0.00"),
    ]
    result = compute_rfm(events, ANALYSIS_TS)
    by_id = {c["customer_id"]: c for c in result["customers"]}

    # monetary counts only purchases
    assert by_id["c_buyer"]["monetary"] == pytest.approx(150.0)
    assert by_id["c_viewer"]["monetary"] == 0.0

    # frequency counts all events
    assert by_id["c_buyer"]["frequency"] == 3
    assert by_id["c_viewer"]["frequency"] == 3


# ---------------------------------------------------------------------------
# Tie handling: identical recency_days → same R score
# ---------------------------------------------------------------------------


def test_tie_recency_same_r_score():
    # Four customers: c1 (1 day), c2 (10 days), c3 (40 days), c4 (40 days)
    # c3 and c4 share recency_days=40; both should get the same R score
    events = [
        _event("c1", (2024, 1, 9)),   # 1 day
        _event("c2", (2023, 12, 31)), # 10 days
        _event("c3", (2023, 12, 1)),  # 40 days
        _event("c4", (2023, 12, 1)),  # 40 days
    ]
    result = compute_rfm(events, ANALYSIS_TS)
    by_id = {c["customer_id"]: c for c in result["customers"]}
    assert by_id["c3"]["recency_days"] == by_id["c4"]["recency_days"] == 40
    assert by_id["c3"]["r_score"] == by_id["c4"]["r_score"]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_determinism():
    events = _make_fixture_events()
    result1 = compute_rfm(events, ANALYSIS_TS)
    result2 = compute_rfm(events, ANALYSIS_TS)
    assert result1 == result2


# ---------------------------------------------------------------------------
# Empty events list
# ---------------------------------------------------------------------------


def test_empty_events():
    result = compute_rfm([], ANALYSIS_TS)
    assert result["unique_customers"] == 0
    assert result["customers"] == []
    assert sum(result["segment_counts"].values()) == 0
