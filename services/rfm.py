from datetime import datetime
from statistics import quantiles
from typing import Any


_SEGMENT_RULES: list[tuple[str, Any]] = [
    ("Champions",           lambda r, f, m: r >= 4 and f >= 4),
    ("Loyal Customers",     lambda r, f, m: f >= 4 and m >= 4),
    ("Potential Loyalists", lambda r, f, m: r >= 4 and f < 4),
    ("At Risk",             lambda r, f, m: r <= 2 and f >= 3),
    ("Hibernating",         lambda r, f, m: r <= 2 and f <= 2),
    ("Others",              lambda r, f, m: True),
]

_SEGMENT_NAMES = [name for name, _ in _SEGMENT_RULES]


def _standard_score(value: float, cutpoints: list[float]) -> int:
    return 1 + sum(1 for cp in cutpoints if value > cp)


def _cutpoints(values: list[float]) -> list[float] | None:
    """Return 4 quintile cut-points, or None when all values are identical."""
    if min(values) == max(values):
        return None
    return quantiles(values, n=5)


def compute_rfm(events: list[dict], analysis_ts: datetime) -> dict:
    """
    Compute RFM scores and segment assignments for a set of customer events.

    events: list of dicts with keys customer_id, timestamp (datetime), event_type, amount (Decimal)
    analysis_ts: the UTC datetime used as the "now" reference for recency
    """
    if not events:
        return {
            "unique_customers": 0,
            "segment_counts": {name: 0 for name in _SEGMENT_NAMES},
            "customers": [],
        }

    analysis_date = analysis_ts.date()

    # --- aggregate per customer ---
    agg: dict[str, dict] = {}
    for event in events:
        cid = event["customer_id"]
        ts: datetime = event["timestamp"]
        amount = event["amount"]
        etype: str = event["event_type"]

        if cid not in agg:
            agg[cid] = {"latest_date": ts.date(), "frequency": 0, "monetary": 0.0}

        if ts.date() > agg[cid]["latest_date"]:
            agg[cid]["latest_date"] = ts.date()

        agg[cid]["frequency"] += 1
        if etype == "purchase":
            agg[cid]["monetary"] += float(amount)

    customer_ids = list(agg.keys())
    n = len(customer_ids)

    # --- single-customer edge case: all scores = 3 ---
    if n == 1:
        cid = customer_ids[0]
        data = agg[cid]
        recency_days = (analysis_date - data["latest_date"]).days
        return {
            "unique_customers": 1,
            "segment_counts": {name: (1 if name == "Others" else 0) for name in _SEGMENT_NAMES},
            "customers": [{
                "customer_id": cid,
                "segment": "Others",
                "r_score": 3,
                "f_score": 3,
                "m_score": 3,
                "recency_days": recency_days,
                "frequency": data["frequency"],
                "monetary": data["monetary"],
            }],
        }

    # --- collect raw dimension values ---
    recency_vals = [(analysis_date - agg[cid]["latest_date"]).days for cid in customer_ids]
    freq_vals = [float(agg[cid]["frequency"]) for cid in customer_ids]
    mon_vals = [agg[cid]["monetary"] for cid in customer_ids]

    r_cuts = _cutpoints(recency_vals)
    f_cuts = _cutpoints(freq_vals)
    m_cuts = _cutpoints(mon_vals)

    # --- score and segment each customer ---
    segment_counts = {name: 0 for name in _SEGMENT_NAMES}
    result_customers = []

    for i, cid in enumerate(customer_ids):
        data = agg[cid]
        recency_days = recency_vals[i]

        r_score = 3 if r_cuts is None else (6 - _standard_score(recency_days, r_cuts))
        f_score = 3 if f_cuts is None else _standard_score(freq_vals[i], f_cuts)
        m_score = 3 if m_cuts is None else _standard_score(mon_vals[i], m_cuts)

        segment = next(
            name for name, rule in _SEGMENT_RULES if rule(r_score, f_score, m_score)
        )
        segment_counts[segment] += 1

        result_customers.append({
            "customer_id": cid,
            "segment": segment,
            "r_score": r_score,
            "f_score": f_score,
            "m_score": m_score,
            "recency_days": recency_days,
            "frequency": data["frequency"],
            "monetary": data["monetary"],
        })

    return {
        "unique_customers": n,
        "segment_counts": segment_counts,
        "customers": result_customers,
    }
