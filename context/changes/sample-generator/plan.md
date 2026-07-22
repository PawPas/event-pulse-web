# Sample Generator Implementation Plan

## Overview

Add a one-click sample data generator that populates a report with representative customer events covering all six RFM segments. The backend exposes `POST /api/reports/{report_id}/events/sample` accepting an optional `count` parameter; the frontend adds a "Generate Sample" button with a count input to the existing "Add Events" section.

## Current State Analysis

The Event ingestion surface already exists in `routers/events.py` with the upload endpoint. The key reusable pieces are all in place:

- `UploadResult` Pydantic model (`events_added: int`) is defined in `routers/events.py`
- `UploadResult` TypeScript interface is in `frontend/src/types/report.ts` — no new type needed
- `ReportDetail.tsx` has an "Add Events" block that renders when `report.status === 'created'`; the new button goes inside it
- `apiFetch` in `api/client.ts` handles JSON POST with auth headers
- The 200k cap (`_MAX_EVENTS = 200_000`) is already a named constant — the new endpoint references it directly

## Desired End State

- A "Generate Sample" button with a count input (default 150) appears in the "Add Events" section of any `created`-status report.
- Clicking it calls `POST /api/reports/{report_id}/events/sample` with `{ "count": N }`.
- The endpoint verifies ownership, checks that existing events + N ≤ 200,000, generates N events across 30 customer archetypes (5 per RFM segment), bulk-inserts, and returns `{ events_added: N }`.
- Success and error feedback mirrors the upload flow.
- Setting count to a value that would push the report over 200k returns a clear 400 error.

### Key Discoveries

- `routers/events.py:19` — `router = APIRouter(prefix="/api/reports", tags=["events"])` — new endpoint joins this router, no registration changes needed in `main.py`
- `routers/events.py:22` — `_MAX_EVENTS = 200_000` — reuse this constant for the cap check
- `routers/reports.py:34-40` — `_event_count_sq()` scalar subquery pattern for counting events — the new endpoint can use an inline `COUNT` select instead (simpler, no subquery needed for a single report)
- `models/event.py` — `Event` model already accepts `Decimal` for `amount`; non-purchase events must use `Decimal("0.00")`
- `tests/conftest.py` + `tests/test_events.py` — module-scoped `auth_token` + `report_id` fixture pattern to follow

## What We're NOT Doing

- No new model or Alembic migration
- No changes to the upload endpoint
- No per-segment count controls — total `count` is distributed internally across the 30 templates
- No randomisation — the distribution is deterministic; only timestamps are computed relative to `now()`

## Implementation Approach

New endpoint in `routers/events.py` (same file, same router — no `main.py` changes). Sample data is encoded as a list of 30 customer templates (5 per segment), each carrying a list of `(days_ago, event_type, amount_str)` event tuples. At request time, events are materialised by resolving `datetime.now(timezone.utc) - timedelta(days=days_ago)`. To reach an arbitrary `count`, the flat event list is cycled using `itertools.islice(itertools.cycle(base_events), count)`. Frontend mirrors the upload state pattern exactly.

## Critical Implementation Details

- **Timestamp generation at call time**: all `days_ago` values are resolved to `datetime.now(timezone.utc) - timedelta(days=days_ago)` inside the request handler — not at module import time. Static absolute dates would cause recency scores to drift over time and break segment coverage.

- **Amount 0 for non-purchase events**: `view` and `add_to_cart` events must use `Decimal("0.00")`. Any nonzero amount on a non-purchase event corrupts the Monetary dimension for those customers.

---

## Phase 1: Backend endpoint

### Overview

Add `POST /api/reports/{report_id}/events/sample` to `routers/events.py`. The endpoint checks ownership, enforces the cap, materialises events from 30 customer templates (cycling to reach `count`), and bulk-inserts.

### Changes Required

#### 1. Sample request schema

**File**: `routers/events.py`

**Intent**: Define the Pydantic request model for the endpoint body.

**Contract**: `class SampleRequest(BaseModel): count: int = Field(default=150, ge=1, le=250_000)` — `ge=1` rejects zero; `le=250_000` blocks runaway requests while still allowing cap-violation testing at 200,001.

#### 2. Customer template constant

**File**: `routers/events.py`

**Intent**: Encode the base sample dataset as a module-level constant that the endpoint materialises at call time.

**Contract**: `_SAMPLE_TEMPLATES` is a list of 30 dicts, each with `customer_id` (e.g. `"SAMPLE_C001"`) and `events: list[tuple[int, str, str]]` where each tuple is `(days_ago, event_type, amount_str)`. Distribution across segments:

| Segment | Customer IDs | Base event count per customer | Recency (days_ago of latest event) |
|---|---|---|---|
| Champions | SAMPLE_C001–C005 | 10–15 events | 1–5 days |
| Loyal Customers | SAMPLE_C006–C010 | 8–12 events | 30–60 days |
| Potential Loyalists | SAMPLE_C011–C015 | 2–3 events | 3–14 days |
| At Risk | SAMPLE_C016–C020 | 5–8 events | 90–150 days |
| Hibernating | SAMPLE_C021–C025 | 1–2 events | 180–300 days |
| Others | SAMPLE_C026–C030 | 3–5 events | 20–45 days |

Champions and Loyal Customers include purchase events with varying `amount_str` (e.g. `"49.99"`, `"149.00"`) to achieve M quintile 4–5. Non-purchase events (`view`, `add_to_cart`) carry `amount_str = "0.00"`.

#### 3. Sample generator endpoint

**File**: `routers/events.py`

**Intent**: New route that validates ownership and cap, generates `count` events from templates (cycling if necessary), bulk-inserts, and returns `UploadResult`.

**Contract**:

```
POST /api/reports/{report_id}/events/sample
Body: SampleRequest | None = None  ← declare as optional so missing body uses defaults
      (FastAPI 0.139: `payload: SampleRequest` without a default returns 422 for no-body
       requests even when all Pydantic fields have defaults — verified against project venv)
Auth: Bearer token via Depends(get_current_user)

200 UploadResult  → { events_added: count }
400              → if existing_event_count + count > 200_000
                   detail must contain "200,000" (consistent with upload error wording)
404              → report not found or wrong owner
```

Also add `import itertools` to the imports at the top of `routers/events.py` (not currently present).

Implementation sequence inside the handler:
1. Resolve payload: `resolved = payload or SampleRequest()`.
2. Verify report ownership (same `select(Report).where(Report.id == ..., Report.user_id == ...)` pattern as upload).
3. Count existing events: `select(func.count(Event.id)).where(Event.report_id == report_id)`.
4. If `existing + resolved.count > _MAX_EVENTS` → 400 with a detail string containing "200,000".
5. Flatten `_SAMPLE_TEMPLATES` into a base event list; use `itertools.islice(itertools.cycle(base), resolved.count)` to produce exactly `resolved.count` entries.
6. Materialise each entry as an `Event` with `timestamp = now - timedelta(days=days_ago)` where `now = datetime.now(timezone.utc)`.
7. `db.add_all(events)` + `await db.commit()`.
8. Return `UploadResult(events_added=resolved.count)`.

#### 4. Backend tests

**File**: `tests/test_sample_generator.py`

**Intent**: Cover happy path (default and custom count), authentication, ownership isolation, and cap enforcement (standalone and combined with existing events).

**Contract**: Module-scoped `auth_token` + `report_id` fixtures following `tests/test_events.py`. Test cases:

- `test_generate_unauthenticated` → 401
- `test_generate_wrong_user` → 404
- `test_generate_default` — POST with no body (no Content-Type, no body bytes) → 200, `events_added == 150`; verify report `event_count` increases by 150 via `GET /api/reports/{id}`
- `test_generate_custom_count` — POST `{"count": 5}` → 200, `events_added == 5`
- `test_generate_appends` — GET event_count before; POST with no body; GET event_count after; assert `after == before + 150` (relative delta, not absolute count — follows `test_upload_appends_to_existing` pattern at `tests/test_events.py:98-114`)
- `test_generate_exceeds_cap_standalone` — POST `{"count": 200_001}` → 400, `"200,000"` in detail
- `test_generate_cap_combined` — upload a small CSV first, then generate enough to exceed 200,000 total → 400

### Success Criteria

#### Automated Verification

- `uv run pytest tests/test_sample_generator.py -v` — all 7 tests pass (test_generate_appends uses before/after delta, not absolute count)
- `uv run pytest tests/ -v` — no regressions in existing test suite

#### Manual Verification

- `POST /api/reports/{id}/events/sample` (no body) with valid auth → 200, `events_added: 150`
- `POST` with `{"count": 200001}` → 400, detail contains "200,000"
- Report `event_count` increases by `events_added` (confirmed via `GET /api/reports/{id}`)
- Inspect generated events grouped by customer_id; confirm the distribution matches the intended segment profile:
  - ≥ 1 customer with latest event ≤ 5 days ago AND ≥ 10 events (Champion candidate)
  - ≥ 1 customer with latest event ≥ 30 days ago AND ≥ 8 events AND high purchase total (Loyal Customer candidate)
  - ≥ 1 customer with latest event ≤ 14 days ago AND ≤ 3 events (Potential Loyalist candidate)
  - ≥ 1 customer with latest event ≥ 90 days ago AND ≥ 5 events (At Risk candidate)
  - ≥ 1 customer with latest event ≥ 180 days ago AND ≤ 2 events (Hibernating candidate)
  - ≥ 1 customer with middling recency AND low-medium event count (Others candidate)

**Implementation Note**: After automated verification passes, pause for manual confirmation before proceeding to Phase 2.

---

## Phase 2: Frontend button

### Overview

Add a count input (default 150) and "Generate Sample" button to the "Add Events" section in `ReportDetail.tsx`. State and feedback mirror the upload flow.

### Changes Required

#### 1. State and handler

**File**: `frontend/src/pages/ReportDetail.tsx`

**Intent**: Add state for the sample generation flow and a handler that calls the new endpoint.

**Contract**: Four new state variables alongside the existing upload state:

```
sampleCount: number  (useState(150))
sampleStatus: 'idle' | 'loading' | 'success' | 'error'  (useState('idle'))
sampleError: string | null  (useState(null))
sampleEventsAdded: number | null  (useState(null))
```

`handleGenerateSample` calls `apiFetch(\`/api/reports/${id}/events/sample\`, { method: 'POST', body: JSON.stringify({ count: sampleCount }) })`. On success: set status to `'success'`, store `result.events_added`, then re-fetch the report (same `apiFetch(\`/api/reports/${id}\`)` pattern as `handleUpload` does after upload). On `ApiError`: set status to `'error'`, store `err.detail`.

#### 2. UI elements

**File**: `frontend/src/pages/ReportDetail.tsx`

**Intent**: Render the count input and button below the file upload controls, inside the existing `report.status === 'created'` block.

**Contract**: 
- A labelled number input (`min={1}`) bound to `sampleCount` with an `onChange` that resets `sampleStatus` to `'idle'`.
- A button disabled while `sampleStatus === 'loading'`, text toggling between `"Generate Sample"` and `"Generating…"`.
- Success `<p style={{ color: 'green' }}>` showing `sampleEventsAdded.toLocaleString()` events added.
- Error `<p style={{ color: 'red' }}>` showing `sampleError`.

### Success Criteria

#### Automated Verification

- `cd frontend && npm run lint` — zero lint errors

#### Manual Verification

- "Generate Sample" button and count input appear in the "Add Events" section on a `created`-status report
- Default count input shows `150`; changing it resets any prior feedback
- Clicking with default count shows green success message with event count; report `event_count` refreshes
- Setting count to `200001` (no prior events) triggers a red error message containing "200,000"
- Setting count to `5` generates exactly 5 events (visible in the green message and report count)
- Button shows "Generating…" and is disabled during the in-flight request

**Implementation Note**: After lint passes, pause for manual UI verification before considering this phase done.

---

## Testing Strategy

### Integration Tests

- `tests/test_sample_generator.py` — 7 cases covering auth, happy paths (default, custom count, append), cap (standalone and combined)
- Run full `tests/` suite after Phase 1 to verify no regressions

### Manual Testing Steps

1. Create a report, click "Generate Sample" (default 150) → check event count and green message
2. Set count to 5, click again → verify count becomes 155 (append semantics)
3. Set count to 200,001 → verify red 400 error
4. Verify all 6 RFM segments appear when the S-05 analysis endpoint is eventually run on the 150-event sample

## References

- Upload endpoint: `routers/events.py`
- Frontend upload flow: `frontend/src/pages/ReportDetail.tsx:34-73`
- Test fixture pattern: `tests/test_events.py:26-55`
- Cap constant: `routers/events.py:22`
- Roadmap slice S-04: `context/foundation/roadmap.md:128-139`
- PRD FR-009: `context/foundation/prd.md:82-84`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend endpoint

#### Automated

- [x] 1.1 `uv run pytest tests/test_sample_generator.py -v` — all 7 tests pass — 27a30cb
- [x] 1.2 `uv run pytest tests/ -v` — no regressions in existing test suite — 27a30cb

#### Manual

- [x] 1.3 POST with no body → 200, `events_added: 150` — 27a30cb
- [x] 1.4 POST with `{"count": 200001}` → 400, detail contains "200,000" — 27a30cb
- [x] 1.5 Report `event_count` increases by `events_added` after the call — 27a30cb
- [x] 1.6 Event distribution per customer matches intended segment profile (Champion/Loyal/Potential Loyalist/At Risk/Hibernating/Others candidates all present) — 27a30cb

### Phase 2: Frontend button

#### Automated

- [x] 2.1 `cd frontend && npm run lint` — zero lint errors

#### Manual

- [x] 2.2 "Generate Sample" button and count input appear on a `created`-status report
- [x] 2.3 Default count shows 150; changing it resets prior feedback
- [x] 2.4 Default count click shows green success message and refreshed event count
- [x] 2.5 Count set to 200001 shows red 400 error
- [x] 2.6 Count set to 5 generates exactly 5 events
- [x] 2.7 Button shows "Generating…" and is disabled during in-flight request
