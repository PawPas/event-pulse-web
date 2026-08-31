# RFM Analysis Dashboard Implementation Plan

## Overview

Build the full RFM analysis pipeline: Alembic migration adding a JSONB result column, a pure-Python computation service, two API endpoints (trigger + retrieve), and a frontend dashboard that auto-polls while analyzing and renders a sortable results table. This is roadmap slice S-05 — the north-star validation milestone.

## Current State Analysis

- `Report` model (`models/report.py`) already defines `ReportStatus` enum with `created / analyzing / completed / failed` and an `analyzed_at` nullable datetime column. No `analysis_result` column exists yet — results storage is the only schema gap.
- `Event` model has a composite index on `(report_id, customer_id)` — exactly what per-customer aggregation needs.
- No analysis service, no analysis router, no analysis tests exist anywhere.
- `ReportDetail.tsx` "Run Analysis" button is a dead placeholder at line 209 — no `onClick`, no API call.
- TypeScript `Report` type already declares all four status values; none beyond `'created'` produce any UI.
- `apiFetch` always injects `Content-Type: application/json` and `Authorization` headers.
- No reusable table component exists — sortable results table is built inline.
- No pandas/numpy in `pyproject.toml` — quintile computation uses Python stdlib `statistics.quantiles`.

## Desired End State

A user with events in a report can click "Run Analysis," watch the button change to "Analyzing…" while the page polls every 2 seconds, and then see a dashboard appear automatically showing: (1) a summary bar with total events, unique customer count, and per-segment counts; (2) a sortable 7-column table (customer_id, Segment, R, F, M, Recency days, Frequency, Monetary) sorted by segment (Champions first) then customer_id by default. Clicking any column header re-sorts ascending/descending. Re-running on a completed report is always allowed and re-scores all current events. A failed analysis shows an error message and a Retry button.

### Key Discoveries

- `database.py` exports `get_db()` as a FastAPI dependency; the background task needs its own session — expose `AsyncSessionLocal` from `database.py` for use outside the request lifecycle (`routers/analysis.py:_run_analysis`)
- `models/report.py:16-20` — `ReportStatus` enum already covers all needed states; no enum alteration in the migration
- `idx_events_report_customer` index at `models/event.py` — covers the `WHERE report_id = ? GROUP BY customer_id` query pattern
- Quintile edge case: `statistics.quantiles(data, n=5)` raises `StatisticsError` for fewer than 2 data points; if all values are identical, all 4 cut-points equal that value so every customer scores 1 (undesirable). Both cases need explicit handling in `services/rfm.py`.
- `BackgroundTasks` are fire-and-forget: if the server restarts mid-analysis the job is lost and `status` stays `'analyzing'` forever. Acceptable at MVP; a future `/10x-new` change can add a startup recovery sweep.

## What We're NOT Doing

- No separate worker service or task queue (defer to post-MVP if concurrency demands it)
- No segment distribution chart (FR-012b — parked as nice-to-have)
- No file export of analysis results (PRD §Non-Goals)
- No per-customer drill-down pages
- No server-side pagination of results (all rows loaded client-side; realistic customer counts are hundreds, not millions)
- No streaming or real-time updates — polling only
- No automatic re-run on event upload — user triggers manually

## Implementation Approach

**Phase 1** adds the JSONB column via Alembic and builds the pure-Python RFM engine as a testable service module, decoupled from HTTP.

**Phase 2** wires two endpoints: `POST /{report_id}/analysis/run` (202, queues BackgroundTask) and `GET /{report_id}/analysis/results` (returns stored JSONB). The background task opens its own DB session, runs the engine, writes results and status.

**Phase 3** connects the frontend: wires the button, starts the polling loop on `analyzing`, renders the three non-`created` states, and builds the sortable table.

## Critical Implementation Details

**Quintile scoring correctness.** The standard score for F and M is `1 + count(cutpoints that value strictly exceeds)` — giving scores 1–5 where higher is better. For Recency (lower days = more recent = better), invert: `R = 6 − standard_score(recency_days)`. Edge cases: population of 1 customer → assign score 3 for all dimensions. All-same-value distribution (min == max) → assign score 3 uniformly rather than letting all customers fall into score 1.

**Background task session.** FastAPI's `Depends(get_db)` session is closed once the request response is sent. The background task function `_run_analysis` must open its own session using `get_session_factory()` from `database.py`: `async with get_session_factory()() as db:`. Fetch the Report row inside `_run_analysis` (don't close over the ORM object from the request handler — it won't be usable after the session closes).

**Re-fetch inside background task.** The handler commits `status=analyzing` before returning 202. The background task opens a new session and loads the Report fresh — do not share the handler's `report` object across sessions.

---

## Phase 1: DB migration + RFM computation service

### Overview

Add `analysis_result JSONB` to the `reports` table via Alembic. Build `services/rfm.py` — a pure-Python module that takes a list of raw event dicts and returns the full result payload. Write unit tests that verify correctness for normal cases and edge cases without any HTTP or DB involvement.

### Changes Required

#### 1. Alembic migration

**File**: `alembic/versions/<rev>_add_analysis_result.py` (generate with `uv run alembic revision -m "add analysis result column"`, then fill body)

**Intent**: Add the nullable JSONB column that will hold the full RFM result payload after analysis completes.

**Contract**: `op.add_column('reports', sa.Column('analysis_result', JSONB(), nullable=True))` using `from sqlalchemy.dialects.postgresql import JSONB`. Downgrade removes the column.

#### 2. Report ORM model update

**File**: `models/report.py`

**Intent**: Reflect the new column so SQLAlchemy can read and write it via the ORM.

**Contract**: Add `analysis_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` to the `Report` class. Import `JSONB` from `sqlalchemy.dialects.postgresql`; `mapped_column` is already imported. No default needed — column starts NULL. (Use `mapped_column`, not `Column` — the entire model uses SQLAlchemy 2.0 `Mapped[T] = mapped_column(...)` style.)

#### 3. Expose AsyncSessionLocal from database.py

**File**: `database.py`

**Intent**: The background task in Phase 2 needs a session factory it can call outside the FastAPI request lifecycle.

**Contract**: Add a `get_session_factory()` getter function (do NOT export the raw `_session_factory_instance` — it starts as `None` and is only initialized after the first `_get_engine()` call):

```python
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    _get_engine()
    assert _session_factory_instance is not None
    return _session_factory_instance
```

This mirrors the existing lazy-init pattern and is safe whether or not a prior request has warmed up the engine.

#### 4. RFM computation service

**File**: `services/__init__.py` (empty — make `services/` a package)

**File**: `services/rfm.py`

**Intent**: Encapsulate the full RFM pipeline — event aggregation, quintile scoring, segment assignment, result serialisation — as a single callable that takes plain Python data and returns a dict. No SQLAlchemy, no HTTP dependencies; must be unit-testable in isolation.

**Contract**:

```
def compute_rfm(
    events: list[dict],   # keys: customer_id (str), timestamp (datetime), event_type (str), amount (Decimal)
    analysis_ts: datetime,  # UTC; recency = (analysis_ts.date() - event.timestamp.date()).days
) -> dict:
    ...
```

Return shape (stored verbatim in `analysis_result` JSONB):

```json
{
  "unique_customers": <int>,
  "segment_counts": {
    "Champions": <int>,
    "Loyal Customers": <int>,
    "Potential Loyalists": <int>,
    "At Risk": <int>,
    "Hibernating": <int>,
    "Others": <int>
  },
  "customers": [
    {
      "customer_id": <str>,
      "segment": <str>,
      "r_score": <int 1-5>,
      "f_score": <int 1-5>,
      "m_score": <int 1-5>,
      "recency_days": <int>,
      "frequency": <int>,
      "monetary": <float>
    }
  ]
}
```

Internal algorithm:
1. **Aggregate** events by `customer_id`: recency_days = (analysis_ts.date() − latest event timestamp date); frequency = total event count; monetary = sum of `float(amount)` where `event_type == "purchase"`.
2. **Quintile cut-points** for each dimension: if population == 1 → all scores 3. If min == max for a dimension → all scores 3. Otherwise `statistics.quantiles(values, n=5)` returns `[p20, p40, p60, p80]`.
3. **Score** F and M: `1 + sum(1 for cp in cutpoints if value > cp)`. Score R: `6 − (1 + sum(1 for cp in cutpoints if recency_days > cp))`.
4. **Segment** per priority order (first match): Champions (R≥4 AND F≥4), Loyal Customers (F≥4 AND M≥4), Potential Loyalists (R≥4 AND F<4), At Risk (R≤2 AND F≥3), Hibernating (R≤2 AND F≤2), Others (catch-all).
5. **Return** dict with `unique_customers`, `segment_counts`, `customers` list.

#### 5. Algorithm unit tests

**File**: `tests/test_rfm_algorithm.py`

**Intent**: Verify the computation module produces correct output for known inputs, including edge cases. These run without a DB or server.

**Contract**: Import `compute_rfm` from `services.rfm`. Test cases:

- **Normal 5-customer fixture**: a hand-crafted set of 5 customers whose expected R/F/M scores and segments are pre-calculated. Assert `segment_counts` totals to 5. Assert at least one customer per segment type present in the result.
- **Single-customer edge case**: one customer → all scores 3, segment "Others".
- **All-same-recency edge case**: all customers have identical recency_days → all R scores 3.
- **Purchase-only monetary**: customers with non-purchase events should have those events excluded from Monetary but included in Frequency.
- **Tie handling**: two customers with identical recency_days at a quintile boundary → same R score.
- **Determinism**: calling `compute_rfm` twice on the same input returns identical output.

### Success Criteria

#### Automated Verification

- `uv run alembic upgrade head` — migration applies cleanly with no errors
- `uv run pytest tests/test_rfm_algorithm.py -v` — all algorithm unit tests pass
- `uv run pytest tests/ -v` — no regressions in existing suite

#### Manual Verification

- Inspect `reports` table in pgAdmin: `analysis_result` column exists, type is `jsonb`, nullable

**Implementation Note**: Pause after automated verification passes; confirm manual DB inspection before Phase 2.

---

## Phase 2: Analysis API endpoints

### Overview

Add `POST /{report_id}/analysis/run` and `GET /{report_id}/analysis/results` to a new `routers/analysis.py` router. Wire `POST /run` to a BackgroundTask that opens its own session, calls `compute_rfm`, and writes results. Cover the full async flow with integration tests.

### Changes Required

#### 1. Analysis router

**File**: `routers/analysis.py`

**Intent**: Two ownership-checked endpoints on the `/api/reports` prefix. `POST /run` transitions the report to `analyzing` and enqueues the background job. `GET /results` returns the stored JSON payload.

**Contract**:

```
POST /{report_id}/analysis/run
  Auth: Depends(get_current_user)
  Returns: 202  { "status": "analyzing" }
  409 if report.status == "analyzing" (detail: "Analysis already in progress")
  400 if event count == 0 (detail: "Report has no events to analyse")
  404 if not found / wrong owner
  Side-effect: sets report.status = ReportStatus.analyzing, commits, enqueues _run_analysis
  Note: `event_count` is NOT a column on the Report ORM model — load the report using a
  correlated scalar subquery (same pattern as routers/reports.py:34-50):
    event_count_sq = select(func.count(Event.id)).where(Event.report_id == report_id).scalar_subquery()
    row = await db.execute(select(Report, event_count_sq.label("event_count")).where(
        Report.id == report_id, Report.user_id == current_user.user_id))
    row = result.first()
    if row is None: raise 404
    report, event_count = row.Report, row.event_count
    if event_count == 0: raise 400

GET /{report_id}/analysis/results
  Auth: Depends(get_current_user)
  Returns: 200  AnalysisResult (see Pydantic model below)
  404 if not found / wrong owner
  404 if report.analysis_result is None (detail: "No analysis results — run analysis first")
```

Pydantic response models (defined in `routers/analysis.py`):

```
class CustomerResult(BaseModel):
    customer_id: str
    segment: str
    r_score: int
    f_score: int
    m_score: int
    recency_days: int
    frequency: int
    monetary: float

class AnalysisResult(BaseModel):
    unique_customers: int
    segment_counts: dict[str, int]
    customers: list[CustomerResult]
```

`RunAnalysisResponse`:
```
class RunAnalysisResponse(BaseModel):
    status: str  # always "analyzing"
```

#### 2. Background task function

**File**: `routers/analysis.py` (private function `_run_analysis`)

**Intent**: Asynchronous function that opens its own DB session, loads events for the report, calls `compute_rfm`, persists results, and updates status to `completed` or `failed`.

**Contract**:

```
async def _run_analysis(report_id: UUID) -> None:
    async with get_session_factory()() as db:
        # 1. Load report (fresh session — do not reuse handler's session)
        # 2. Load all events ordered by timestamp
        # 3. analysis_ts = datetime.now(timezone.utc)
        # 4. result = compute_rfm([event.__dict__...], analysis_ts)
        # 5. report.analysis_result = result; report.analyzed_at = analysis_ts
        # 6. report.status = ReportStatus.completed; await db.commit()
        # On ANY exception: report.status = ReportStatus.failed; await db.commit()
```

Events are fetched as ORM objects and converted to plain dicts before passing to `compute_rfm`.

#### 3. Register router in main.py

**File**: `main.py`

**Intent**: Include the analysis router so its routes are reachable under `/api/reports`.

**Contract**: `app.include_router(analysis_router, prefix="/api/reports", tags=["analysis"])` — same prefix and pattern as `events_router`.

#### 4. Integration tests

**File**: `tests/test_analysis.py`

**Intent**: Cover the full async flow end-to-end with the test database. Use a known fixture dataset (≥5 customers, known expected segment distribution) to verify not just shape but correctness.

**Contract**: Module-scoped `auth_token` + `report_id` fixtures following `tests/test_sample_generator.py`. Upload a small fixture CSV (or use the sample generator endpoint) to seed events. Test cases:

- `test_run_unauthenticated` → 401
- `test_run_wrong_user` → 404
- `test_run_no_events` → 400 ("no events")
- `test_run_triggers_analysis` — POST /run → 202, `{"status": "analyzing"}`; poll GET /reports/{id} until `status != "analyzing"` (max 30 retries × 1s); assert final status is `"completed"`
- `test_results_shape` — GET /results → 200; assert `unique_customers > 0`, `customers` list non-empty, all 6 segment keys present in `segment_counts`, sum of segment_counts equals `unique_customers`
- `test_results_correctness` — using the fixture dataset with pre-known expected scores, assert at least one customer lands in the correct segment
- `test_run_already_analyzing` — Setup: directly UPDATE `report.status = 'analyzing'` in the test DB (do not rely on timing); then POST /run → 409
- `test_results_before_run` — GET /results on a fresh report → 404
- `test_rerun_completes` — POST /run on a completed report → 202; poll until completed again; assert results updated

### Success Criteria

#### Automated Verification

- `uv run pytest tests/test_analysis.py -v` — all 9 integration tests pass
- `uv run pytest tests/ -v` — no regressions

#### Manual Verification

- `POST /api/reports/{id}/analysis/run` with valid auth → 202, `{"status": "analyzing"}`
- Polling `GET /api/reports/{id}` → status transitions to `completed` within 30 seconds
- `GET /api/reports/{id}/analysis/results` → JSON with `unique_customers`, `segment_counts`, `customers` list with correct R/F/M scores

**Implementation Note**: Pause after automated verification; confirm manual endpoint flow before Phase 3.

---

## Phase 3: Frontend dashboard

### Overview

Wire the "Run Analysis" button to the API, start a 2-second polling loop while `status === 'analyzing'`, and render three new status-gated sections in `ReportDetail.tsx`: an analyzing spinner, a failed error+retry state, and the full completed dashboard (summary bar + sortable 7-column table). Add TypeScript result types. Run lint.

### Changes Required

#### 1. TypeScript result types

**File**: `frontend/src/types/report.ts`

**Intent**: Add the shapes for the results response so all call sites are typed.

**Contract**: Add alongside `Report` and `UploadResult`:

```ts
export interface CustomerResult {
  customer_id: string
  segment: string
  r_score: number
  f_score: number
  m_score: number
  recency_days: number
  frequency: number
  monetary: number
}

export interface AnalysisResult {
  unique_customers: number
  segment_counts: Record<string, number>
  customers: CustomerResult[]
}
```

#### 2. State, handler, and polling in ReportDetail.tsx

**File**: `frontend/src/pages/ReportDetail.tsx`

**Intent**: Add analysis state variables, a `handleRunAnalysis` function, a polling interval that activates while `status === 'analyzing'`, and a result-fetching effect that fires when status transitions to `'completed'`.

**Contract**:

New state variables (alongside existing upload state):
```
analysisStatus: 'idle' | 'triggering' | 'error'  useState('idle')
analysisError: string | null                       useState(null)
analysisResult: AnalysisResult | null              useState(null)
sortKey: keyof CustomerResult | 'segment'          useState('segment')
sortDir: 'asc' | 'desc'                            useState('asc')
```

`handleRunAnalysis`: calls `apiFetch(\`/api/reports/${id}/analysis/run\`, { method: 'POST' })`. On success (202): sets `analysisStatus='idle'`; re-fetches `GET /api/reports/${id}` to get the updated `status: 'analyzing'`; the polling effect takes over from there. On `ApiError`: sets `analysisStatus='error'`, stores `err.detail` in `analysisError`.

**Polling effect** (`useEffect` with `[report?.status]` dependency):
- If `report?.status === 'analyzing'`: start a `setInterval` every 2000ms that calls `apiFetch(\`/api/reports/${id}\`)` and calls `setReport(updated)`.
- Clear interval when status changes away from `'analyzing'` or on unmount.

**Results-fetch effect** (`useEffect` with `[report?.status]` dependency, alongside polling effect):
- If `report?.status === 'completed'` and `analysisResult === null`: call `apiFetch(\`/api/reports/${id}/analysis/results\`)` and set `analysisResult`.

#### 3. UI sections in ReportDetail.tsx

**File**: `frontend/src/pages/ReportDetail.tsx`

**Intent**: Replace the single `report.status === 'created'` block with four status-gated sections that cover the full report lifecycle.

**Contract**:

**`status === 'created'` section** (existing — no change to Add Events area):
- Keep existing upload + sample generator controls.
- "Run Analysis" button: remove the `disabled={report.event_count === 0}` placeholder; add `onClick={handleRunAnalysis}`, `disabled={analysisStatus === 'triggering' || report.event_count === 0}`, label toggles `'Run Analysis'` / `'Starting…'`.
- Show red error `<p>` when `analysisStatus === 'error'`.

**`status === 'analyzing'` section** (new):
- `<p>Analyzing… this may take up to 30 seconds.</p>` with a spinner or animated ellipsis.
- No Run Analysis button (analysis in flight).

**`status === 'failed'` section** (new):
- `<p style={{ color: 'red' }}>Analysis failed. Please try again.</p>`
- "Retry" button that calls `handleRunAnalysis`.

**`status === 'completed'` section** (new):
- Summary bar: three `<strong>` values for total events (`report.event_count`), unique customers (`analysisResult.unique_customers`), and segment breakdown (`Object.entries(analysisResult.segment_counts)`).
- "Re-run Analysis" button (calls `handleRunAnalysis`; resets `analysisResult` to null before the call so the completed section disappears and the analyzing section takes over).
- Sortable table: `<table>` with 7 columns — Customer ID, Segment, R, F, M, Recency (days), Frequency, Monetary ($).
- Column header `<th>` elements: `onClick` sets `sortKey` to that column; if `sortKey` already equals that column, toggles `sortDir`; otherwise resets `sortDir` to `'asc'`. Display a `▲` / `▼` arrow on the active sort column.
- Default sort: segment-first using the PRD priority order (Champions=1, Loyal Customers=2, Potential Loyalists=3, At Risk=4, Hibernating=5, Others=6), secondary sort by `customer_id` ascending.
- Client-side sorted rows: `[...analysisResult.customers].sort(compareFn)` — do not mutate state.
- `monetary` rendered as `$${row.monetary.toFixed(2)}`.
- Show a `<p>Loading results…</p>` while `analysisResult === null` (during the results-fetch after completion).

#### 4. Lint check

**File**: `frontend/src/pages/ReportDetail.tsx`, `frontend/src/types/report.ts`

**Intent**: Verify no hook rule violations or other oxlint errors were introduced.

**Contract**: `cd frontend && npm run lint` exits with zero errors.

### Success Criteria

#### Automated Verification

- `cd frontend && npm run lint` — zero errors

#### Manual Verification

- "Run Analysis" button appears for a `created`-status report with events; clicking it triggers analysis and shows the Analyzing… state
- Dashboard appears automatically (no page refresh) within 30 seconds showing summary bar and sortable table
- All 7 table columns render with correct data for the sample dataset
- Clicking column headers sorts ascending/descending; active column shows arrow
- Default sort groups by segment in PRD priority order
- "Re-run Analysis" button is visible in the completed state; clicking it re-runs and refreshes results
- Failed analysis (can simulate by temporarily breaking the endpoint) shows red error + Retry button
- `monetary` values display with `$` prefix and 2 decimal places

**Implementation Note**: Pause after lint passes for manual UI verification.

---

## Testing Strategy

### Unit Tests

- `tests/test_rfm_algorithm.py` — isolated tests of `compute_rfm` covering: normal 5-customer fixture, single customer, all-same-value dimension, purchase-only monetary, tie handling, determinism

### Integration Tests

- `tests/test_analysis.py` — 9 tests covering auth, trigger flow, polling, results shape, results correctness, re-run, edge cases (no events, already analyzing, results before run)

### Manual Testing Steps

1. Generate 150 sample events, click Run Analysis, verify all 6 segments appear
2. Upload additional events to a completed report, re-run, verify results update
3. Set event_count to 0 (fresh report), click Run Analysis — verify button disabled
4. Verify analysis completes within 30 seconds for 150 events

## References

- PRD Business Logic (RFM algorithm spec): `context/foundation/prd.md:107-126`
- Roadmap S-05: `context/foundation/roadmap.md:141-152`
- Existing report model: `models/report.py`
- Existing event model: `models/event.py`
- DB session factory: `database.py`
- Existing router pattern: `routers/events.py:316-375`
- Frontend API client: `frontend/src/api/client.ts`
- Existing report types: `frontend/src/types/report.ts`
- Test fixture pattern: `tests/test_sample_generator.py`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: DB migration + RFM computation service

#### Automated

- [x] 1.1 `uv run alembic upgrade head` — migration applies cleanly — 559dccf
- [x] 1.2 `uv run pytest tests/test_rfm_algorithm.py -v` — all algorithm unit tests pass — 559dccf
- [x] 1.3 `uv run pytest tests/ -v` — no regressions in existing suite — 559dccf

#### Manual

- [x] 1.4 pgAdmin: `analysis_result` column exists on `reports` table, type jsonb, nullable — 559dccf

### Phase 2: Analysis API endpoints

#### Automated

- [x] 2.1 `uv run pytest tests/test_analysis.py -v` — all 9 integration tests pass — 81849b6
- [x] 2.2 `uv run pytest tests/ -v` — no regressions — 81849b6

#### Manual

- [x] 2.3 `POST /api/reports/{id}/analysis/run` → 202, `{"status": "analyzing"}` — 81849b6
- [x] 2.4 Polling `GET /api/reports/{id}` → status transitions to `completed` within 30 seconds — 81849b6
- [x] 2.5 `GET /api/reports/{id}/analysis/results` → valid JSON with `unique_customers`, `segment_counts`, `customers` — 81849b6

### Phase 3: Frontend dashboard

#### Automated

- [x] 3.1 `cd frontend && npm run lint` — zero errors

#### Manual

- [x] 3.2 "Run Analysis" button triggers analysis and shows Analyzing… state
- [x] 3.3 Dashboard appears automatically within 30 seconds without page refresh
- [x] 3.4 All 7 table columns render with correct data
- [x] 3.5 Column header clicks sort ascending/descending with arrow indicator
- [x] 3.6 Default sort groups rows by segment in PRD priority order
- [x] 3.7 "Re-run Analysis" button visible in completed state; clicking re-runs and refreshes results
- [x] 3.8 Failed state shows red error message and Retry button
- [x] 3.9 monetary values display with $ prefix and 2 decimal places
