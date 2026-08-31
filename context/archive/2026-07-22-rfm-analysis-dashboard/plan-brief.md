# Plan Brief: RFM Analysis Dashboard

**Change**: `rfm-analysis-dashboard` | **Roadmap**: S-05 (north-star slice) | **Status**: planned

---

## What We're Building

Full RFM analysis pipeline — Alembic migration, pure-Python computation service, two API endpoints, and a frontend dashboard that auto-polls while analyzing and renders a sortable results table with segment summary.

---

## 3-Phase Summary

| Phase | Scope | Key files | Blocker |
|-------|-------|-----------|---------|
| 1 | DB migration + RFM service + unit tests | `alembic/versions/<rev>_add_analysis_result.py`, `models/report.py`, `database.py`, `services/__init__.py`, `services/rfm.py`, `tests/test_rfm_algorithm.py` | Manual: pgAdmin column verification |
| 2 | Analysis API endpoints + integration tests | `routers/analysis.py`, `main.py`, `tests/test_analysis.py` | Manual: endpoint smoke test |
| 3 | Frontend dashboard | `frontend/src/types/report.ts`, `frontend/src/pages/ReportDetail.tsx` | Manual: full UI walkthrough + lint |

---

## Critical Decisions (Already Made)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Async model | BackgroundTasks + client polling | Sufficient at MVP scale; no separate worker needed |
| Result storage | JSONB on `reports.analysis_result` | Zero schema joins; single read at results-fetch |
| Quintile math | `statistics.quantiles(n=5)` stdlib | No numpy/pandas in pyproject.toml |
| Re-run | Always allowed — re-score all current events | Simplest mental model |
| Polling interval | 2 seconds | Responsive UX; low server load |
| Table sort default | Segment (PRD priority order) then customer_id | Highest-value segment (Champions) first |
| Failed state | Error message + Retry button | Minimal recovery path |

---

## Key Contracts

**POST `/api/reports/{report_id}/analysis/run`** → 202 `{"status": "analyzing"}`
- 409 if already analyzing; 400 if no events; 404 if wrong owner

**GET `/api/reports/{report_id}/analysis/results`** → 200 `AnalysisResult`
- 404 if no results yet

**`analysis_result` JSONB shape**:
```json
{
  "unique_customers": int,
  "segment_counts": {"Champions": int, "Loyal Customers": int, ...},
  "customers": [{"customer_id": str, "segment": str, "r_score": int, "f_score": int, "m_score": int, "recency_days": int, "frequency": int, "monetary": float}]
}
```

**`compute_rfm(events, analysis_ts)`** — pure function, no DB/HTTP deps
- Monetary = sum of `amount` where `event_type == "purchase"` only
- R score inverted: low recency_days → high R score
- Edge cases: 1 customer → all scores 3; all-same-value dimension → all scores 3

**Segment rules** (first match wins — PRD priority order):
1. Champions: R≥4 AND F≥4
2. Loyal Customers: F≥4 AND M≥4
3. Potential Loyalists: R≥4 AND F<4
4. At Risk: R≤2 AND F≥3
5. Hibernating: R≤2 AND F≤2
6. Others: catch-all

---

## Implementation Risks

- **BackgroundTask session**: background function needs own `AsyncSessionLocal()` — cannot reuse the request-lifecycle session after response is sent. Export `AsyncSessionLocal` from `database.py`.
- **Server restart during analysis**: job lost, `status` stays `'analyzing'` forever. Acceptable at MVP.
- **`statistics.quantiles` with < 2 data points**: raises `StatisticsError` — handle explicitly in `services/rfm.py`.
- **Polling cleanup**: `setInterval` started in a React effect must be cleared on unmount and when status transitions away from `'analyzing'` to prevent memory leaks and stale updates.

---

## What We're NOT Doing

- No task queue / separate worker service
- No segment distribution chart (FR-012b parked)
- No file export of results
- No per-customer drill-down pages
- No server-side pagination (client-side sort only)
- No auto re-run on event upload
