<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Auth Flows Implementation Plan

- **Plan**: `context/changes/auth-flows/plan.md`
- **Mode**: Deep
- **Date**: 2026-07-20
- **Verdict**: SOUND (after fixes)
- **Findings**: 1 critical  1 warning  1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | FAIL |
| Plan Completeness | WARNING |

## Grounding

9/9 paths ✓ (8 existing + routers/ new, correctly marked), 5/5 symbols ✓ (hash_password, verify_password, create_access_token, get_db, OAuth2PasswordBearer), brief↔plan ✓, contract-surfaces.md absent (skipped)

## Findings

### F1 — SQLite in-memory connection isolation breaks test fixture

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 1, Change 4 — tests/conftest.py test_client fixture
- **Detail**: SQLite :memory: creates a new, empty database per connection. The fixture's asyncio.run(Base.metadata.create_all) creates tables on connection A; TestClient requests open connection B (empty DB). All 5 tests fail with "no such table: users".
- **Fix**: Add `poolclass=StaticPool, connect_args={"check_same_thread": False}` to `create_async_engine` in the fixture; import `StaticPool` from `sqlalchemy.pool`.
- **Decision**: FIXED — StaticPool + check_same_thread added to Phase 1 Change 4 contract.

### F2 — Phase 3 lint check duplicated in Automated and Manual sections

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 3 Success Criteria + Progress rows 3.2 and 3.11
- **Detail**: `cd frontend && npm run lint` appeared in both Automated Verification (→ Progress 3.2) and Manual Verification (→ Progress 3.11). Two checkboxes for the same command.
- **Fix**: Remove lint from Phase 3 Manual Verification; replace with pytest regression check. Drop Progress row 3.11.
- **Decision**: FIXED — Manual Verification now ends with `uv run pytest tests/ -v`; Progress 3.11 removed.

### F3 — Logout dispatch order silently swallows network errors

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3, AppShell contract
- **Detail**: AppShell dispatches `logout()` (clears token) before calling `apiFetch('/api/auth/logout')`. If the network call throws, error is silently swallowed. Correct behavior (stateless JWT) but undocumented.
- **Fix**: Added note to AppShell contract that network errors are intentionally caught and ignored.
- **Decision**: FIXED — contract updated with try/catch intent note.
