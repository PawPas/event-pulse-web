<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: RFM Analysis Dashboard

- **Plan**: context/changes/rfm-analysis-dashboard/plan.md
- **Scope**: Phase 2 of 3
- **Date**: 2026-07-24
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 4 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — No logging in _run_analysis error handler

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: routers/analysis.py:73-82
- **Detail**: The outer `except Exception` block swallows the original exception entirely. The inner `except Exception: pass` (line 82) swallows failures in the error-handling path itself. If `_run_analysis` fails in production, the report stays in `analyzing` or transitions to `failed` with no log trace of why. Diagnosing failures requires DB inspection rather than log tailing.
- **Fix**: Add `logging.exception("_run_analysis failed for report %s", report_id)` before the rollback in the outer except block, and `logging.exception("Failed to set report %s to failed", report_id)` in the inner except before `pass`.
  - Strength: Standard Python `logging.exception` captures the full traceback; one import at the top of the file.
  - Tradeoff: Minimal — adds 2 lines.
  - Confidence: HIGH — every other background-task pattern in production FastAPI apps logs at ERROR on exception.
  - Blind spot: None significant.
- **Decision**: FIXED

### F2 — Missing try/finally in test_run_already_analyzing

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: tests/test_analysis.py:162-175
- **Detail**: `_set_report_status(report_id, ReportStatus.analyzing)` sets shared module-scoped fixture state. If the `assert resp.status_code == 409` on line 170 fails, `_set_report_status(report_id, ReportStatus.created)` on line 175 is never reached. The shared `report_id` fixture is left in `analyzing` state, causing every subsequent test in the module (test_run_triggers_analysis, test_results_shape, test_results_correctness, test_rerun_completes) to return 409 instead of 202 — a cascade of misleading failures.
- **Fix**: Wrap lines 167-173 in `try/finally` with the restore call in `finally`.
- **Decision**: FIXED

### F3 — Unguarded Pydantic deserialization of stored JSONB on GET /results

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: routers/analysis.py:156
- **Detail**: `return AnalysisResult(**report.analysis_result)` deserializes a JSONB blob directly with no try/except. If the stored JSON has schema drift (e.g., a field renamed between deployments without a migration), Pydantic raises `ValidationError`, which FastAPI converts to 422. The 422 body may expose internal field names. The lesson "Convert avoidable 500s/4xx surprises at the boundary" applies here — the fix is one try/except. Data is written by our own `_run_analysis`, so the risk is low, but it exists under schema evolution.
- **Fix**: Wrap in `try/except pydantic.ValidationError` and raise `HTTPException(500, "Stored analysis result is corrupted")`.
- **Decision**: FIXED

### F4 — Test fixture injects private module globals without guard assertion

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: tests/conftest.py:37-38
- **Detail**: `_db_module._engine_instance = engine` and `_db_module._session_factory_instance = session_factory` directly write module-private variables. If `database.py` renames these during a refactor, the test fixture silently sets stale attributes and tests fail with cryptic DB errors rather than an `AttributeError`. The comment at line 34 explains the rationale but there is no guard.
- **Fix**: Add `assert _db_module.get_session_factory() is session_factory` immediately after injection to make breakage explicit.
- **Decision**: SKIPPED

### F5 — conftest.py modified without being in the Phase 2 plan

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: tests/conftest.py (entire file substantially changed)
- **Detail**: Phase 2 plan does not list `tests/conftest.py` under "Changes Required". The file was modified to pre-inject the test engine into `database._engine_instance` and `database._session_factory_instance` so background tasks share the same StaticPool SQLite engine as request-scoped sessions. This was a necessary undiscovered implementation detail — without it, `_run_analysis` opens a new empty in-memory DB in tests and all events are invisible to it. The plan's stated approach ("background task opens its own session via `get_session_factory()`") silently implied this test infrastructure need.
- **Fix**: No code change needed. Document this as a lesson: "integration tests for background tasks that bypass FastAPI DI (calling `get_session_factory()` directly) must pre-inject the test engine into the database module before the lifespan runs."
- **Decision**: ACCEPTED-AS-RULE: Pre-inject test engine when background tasks bypass FastAPI DI (+ comment added to conftest.py)

### F6 — tags=["analysis"] breaks Swagger UI grouping for /api/reports/* endpoints

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: routers/analysis.py:16
- **Detail**: `router = APIRouter(prefix="/api/reports", tags=["analysis"])` uses a different tag than `routers/reports.py` which uses `tags=["reports"]` for the same URL prefix. In Swagger UI, analysis endpoints appear under a separate "analysis" group from all other `/api/reports/*` endpoints, fragmenting the documentation.
- **Fix**: Change `tags=["analysis"]` to `tags=["reports"]` in `router = APIRouter(...)`.
- **Decision**: FIXED

### F7 — Strict exact-match segment set assertion will break on segment additions

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: tests/test_analysis.py:207-208
- **Detail**: `assert set(data["segment_counts"].keys()) == _KNOWN_SEGMENTS` requires the response to contain exactly the 6 known segments — no more, no less. If `compute_rfm` adds a new segment (even in a future phase), this test fails without any code defect. The assertion is correct if segments are meant to be a closed set per the PRD, but it couples the test tightly to the segment list.
- **Fix**: If segments are a closed PRD-specified set, keep the assertion and add a comment: `# PRD §RFM-algorithm: segment list is fixed`. If they may grow, change to `assert set(data["segment_counts"].keys()).issubset(_KNOWN_SEGMENTS)`.
- **Decision**: FIXED via Fix A
