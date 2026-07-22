<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Sample Generator Implementation Plan

- **Plan**: `context/changes/sample-generator/plan.md`
- **Mode**: Deep
- **Date**: 2026-07-21
- **Verdict**: REVISE → SOUND (after fixes)
- **Findings**: 0 critical · 3 warnings · 1 observation

## Verdicts

| Dimension | Verdict |
|---|---|
| End-State Alignment | WARNING |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

5/5 paths ✓, 5/5 symbols ✓, brief↔plan ✓

## Findings

### F1 — "POST with no body → 200" will actually return 422

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 1 §3 contract, test_generate_default, manual step 1.3
- **Detail**: FastAPI 0.139.0 (verified in project venv): `payload: SampleRequest` with no body returns 422 {"detail": [{"type": "missing", "loc": ["body"], "msg": "Field required"}]}. All-default Pydantic fields make the body parseable when `{}` is sent, but do not make the body itself optional. test_generate_default ("POST with no body → 200") and manual step 1.3 fail as written. Production frontend (always sends JSON body) unaffected.
- **Fix A ⭐ Applied**: Declare `payload: SampleRequest | None = None`; handler resolves `payload or SampleRequest()`.
- **Decision**: FIXED via Fix A

### F2 — test_generate_appends asserts absolute count; fragile with shared fixture

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 §4, test spec "test_generate_appends"
- **Detail**: The module-scoped `report_id` fixture is shared; test_generate_default (+150) and test_generate_custom_count (+5) run first, leaving 155 events in the report before test_generate_appends starts. Absolute assertion `event_count == 155` would then fail. Codebase pattern (test_events.py:98-114) uses relative before/after delta checks.
- **Fix Applied**: Rewrote test spec to GET event_count before generating, assert `after == before + 150`.
- **Decision**: FIXED

### F3 — Primary product promise (all 6 segments) has no verification gate

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: End-State Alignment
- **Location**: Desired End State, Phase 1 success criteria, Testing Strategy step 4
- **Detail**: Desired End State promises "the 150-event dataset covers all six RFM segments" — the roadmap's primary risk for S-04. No Phase 1 criterion verifies this; Testing Strategy defers it to S-05 (unplanned). If _SAMPLE_TEMPLATES is miscalibrated, the bug is undetectable until S-05 is built.
- **Fix A ⭐ Applied**: Added manual verification step 1.6 to Phase 1: inspect generated events grouped by customer_id and confirm presence of Champion/Loyal/Potential Loyalist/At Risk/Hibernating/Others candidates by checking recency and event count per customer.
- **Decision**: FIXED via Fix A

### F4 — `itertools` not imported in routers/events.py

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 §3, Implementation Approach
- **Detail**: Plan calls for `itertools.islice(itertools.cycle(...))` but routers/events.py imports only csv, io, json, datetime, Decimal. Missing import causes NameError at runtime.
- **Fix Applied**: Added `import itertools` note to the Phase 1 §3 contract.
- **Decision**: FIXED
