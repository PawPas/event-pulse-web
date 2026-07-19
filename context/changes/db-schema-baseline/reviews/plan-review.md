<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Database Schema Baseline

- **Plan**: `context/changes/db-schema-baseline/plan.md`
- **Mode**: Deep
- **Date**: 2026-07-19
- **Verdict**: REVISE → SOUND (after triage)
- **Findings**: 1 critical | 3 warnings | 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | WARNING |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

4/4 paths ✓, brief↔plan ✓

## Findings

### F1 — Lifespan startup breaks existing test_auth.py

- **Severity**: ❌ CRITICAL
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: End-State Alignment
- **Location**: Phase 1 Change 3 + success criterion 1.6
- **Detail**: Phase 1 adds a lifespan calling _get_engine() eagerly. TestClient(app) in test_auth.py:6 runs the lifespan synchronously at construction. With no DATABASE_URL set, it raises RuntimeError before any test runs. conftest.py fix was scoped to Phase 3 — too late.
- **Fix Applied**: Fix A — moved DATABASE_URL setdefault into Phase 1 as new Change 4 (conftest.py). Phase 3 Change 5 updated to note this is already done.
- **Decision**: FIXED (Fix A)

### F2 — "alembic revision --autogenerate --sql" is invalid syntax

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 § Automated Verification
- **Detail**: `--sql` is only valid with `upgrade`/`downgrade`, not `revision`. Command would error. Also, this criterion had no matching Progress row — Progress↔Phase consistency failure.
- **Fix Applied**: Removed the 'autogenerate dry run' bullet entirely from Phase 2 Automated Verification. Phase 3 criterion 3.2 already covers this.
- **Decision**: FIXED

### F3 — test_db_health_ok overrides the wrong dependency

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 3 Change 5
- **Detail**: Plan said test_db_health_ok "overrides get_db with an aiosqlite session." But GET /api/health/db calls engine_health_check() directly — get_db is never invoked. test_db_health_fails correctly overrides engine_health_check; the ok test should match.
- **Fix Applied**: Updated test_db_health_ok contract to override engine_health_check with an async function returning True. Removed aiosqlite session override description. Added clarifying note that both tests override engine_health_check, not get_db.
- **Decision**: FIXED

### F4 — close_engine() leaves sentinel pointing at disposed engine

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 1 Change 2 (database.py contract)
- **Detail**: close_engine() disposes the pool but plan didn't specify resetting _engine_instance = None. Subsequent _get_engine() calls would return the disposed engine.
- **Fix Applied**: Added to close_engine() contract: after disposal, reset _engine_instance and _session_factory_instance to None.
- **Decision**: FIXED

### F5 — Railway pre-start command instruction is underspecified

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Migration Notes
- **Detail**: "Add alembic upgrade head as start command prefix" didn't specify which Railway surface (UI vs railway.toml vs Procfile).
- **Fix Applied**: Replaced with specific Railway UI path and full start command: `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Decision**: FIXED
