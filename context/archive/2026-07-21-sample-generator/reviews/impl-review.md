<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Sample Generator

- **Plan**: `context/changes/sample-generator/plan.md`
- **Scope**: All phases (1 + 2)
- **Date**: 2026-07-22
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical · 3 warnings · 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Automated Verification

- `uv run pytest tests/test_sample_generator.py -v` — 7/7 passed
- `uv run pytest tests/ -v` — 39/39 passed (no regressions)

## Findings

### F1 — events_added returns resolved.count, not len(events)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: `routers/events.py:375`
- **Detail**: `return UploadResult(events_added=resolved.count)` trusts the requested count, not the actual rows built by itertools.islice. If `_SAMPLE_TEMPLATES` were accidentally emptied, islice would yield zero events while the response claims `resolved.count` were inserted. The sibling `upload_events` returns `len(events_inserted)` — this endpoint should match for consistency and correctness. Currently a theoretical gap since `_SAMPLE_TEMPLATES` is a static constant.
- **Fix**: Change `resolved.count` to `len(events)` at line 375.
- **Decision**: FIXED — changed `resolved.count` to `len(events)` at line 375

### F2 — Frontend sampleCount input has no NaN or upper-bound guard

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: `frontend/src/pages/ReportDetail.tsx:183-185`
- **Detail**: `onChange` calls `setSampleCount(Number(e.target.value))`. `Number("")` → 0, `Number("abc")` → NaN — both produce an invalid body (`{"count": 0}` or `{"count": null}`) that the backend rejects with a 422, surfaced as a raw ApiError detail. The input also lacks a `max` attribute, so values above 250,000 reach the backend. Backend catches all of these — it's a UX gap, not a data loss risk.
- **Fix**: Add `max={250_000}` to the input; guard onChange: `const parsed = Number(e.target.value); if (!Number.isNaN(parsed) && parsed >= 1) setSampleCount(parsed)`
- **Decision**: FIXED — added `max={250_000}` attribute and NaN guard to onChange

### F3 — Cap check is TOCTOU-vulnerable under concurrent requests

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: `routers/events.py:338-349`
- **Detail**: The COUNT query and the INSERT run in separate round-trips. Two concurrent POSTs for the same report can both read the same `existing` count, both pass the cap guard, and both insert — taking the total above 200,000. The same gap exists in `upload_events` (this pattern predates the change). The window is wider for generate_sample since the request has no file I/O overhead.
- **Fix A ⭐ Recommended**: Accept as known risk — add an inline comment at lines 337-341 noting the race and defer to a future sprint with `SELECT ... FOR UPDATE` or a DB check constraint.
  - Strength: Zero churn; blast radius is bounded (soft ceiling, not a security issue); consistent with upload endpoint's accepted approach.
  - Tradeoff: The 200k limit becomes a soft ceiling under concurrent workloads.
  - Confidence: HIGH — consistent with project maturity; upload already lives with this gap.
  - Blind spot: If the product adds multi-device concurrent use, this needs revisiting.
- **Fix B**: Enforce atomically with `SELECT COUNT ... FOR UPDATE` inside the same transaction.
  - Strength: Hard ceiling guaranteed.
  - Tradeoff: Serialises all generate requests per report; needs careful query design.
  - Confidence: MEDIUM — Postgres row-lock semantics on aggregates need verification.
  - Blind spot: Potential impact on upload endpoint consistency.
- **Decision**: FIXED via Fix A — added inline comment at lines 337-341 noting the race; deferred to future sprint

### F4 — sampleError not cleared when count input changes

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: `frontend/src/pages/ReportDetail.tsx:183-185`
- **Detail**: `onChange` resets `sampleStatus` to `'idle'` but does not call `setSampleError(null)`. A stale red error message stays visible after the user edits the count. The plan spec says "onChange resets sampleStatus to 'idle'" — that is met. The error persistence is a UX polish gap not mandated by the plan.
- **Fix**: Add `setSampleError(null)` to the `onChange` handler alongside `setSampleStatus('idle')`.
- **Decision**: FIXED — added `setSampleError(null)` to onChange alongside `setSampleStatus('idle')`

### F5 — test_generate_exceeds_cap_standalone label implies clean state

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: `tests/test_sample_generator.py:108-111`
- **Detail**: Test sends `count=200_001`. Since `0 + 200_001 > 200_000`, the cap triggers even on an empty report — the test is correct regardless of state. But the name "standalone" implies a clean baseline while the report has ~305 accumulated events from prior tests. The test works by accident of the math, not design intent. `test_generate_cap_combined` is the better-designed pattern.
- **Fix**: Add a comment `# 200_001 exceeds cap regardless of existing events (0 + 200_001 > 200_000)`, or rename to `test_generate_count_exceeds_limit`.
- **Decision**: SKIPPED

### F6 — delete_report ownership check in reports.py uses an inferior pattern

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: `routers/reports.py:121-124`
- **Detail**: `delete_report` fetches the report without the `user_id` predicate, then checks ownership in Python. Both `upload_events` and `generate_sample` use the combined-predicate form (`.where(Report.id == ..., Report.user_id == ...)`), which is a single DB round-trip with no Python-side ownership check. This inconsistency predates this change — the new endpoint chose the better pattern. Out of scope to fix here.
- **Fix**: Align `delete_report` in `routers/reports.py` to use the combined predicate in a future cleanup PR.
- **Decision**: SKIPPED — predates this change; track for future cleanup PR
