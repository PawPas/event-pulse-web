<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Report Management Implementation Plan

- **Plan**: `context/changes/report-management/plan.md`
- **Mode**: Deep
- **Date**: 2026-07-20
- **Verdict**: SOUND (after fixes)
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | PASS |
| Plan Completeness | WARNING |

## Grounding

9/9 paths ✓, 8/8 symbols ✓, brief↔plan ✓. `docs/reference/contract-surfaces.md` not present (skip). Sub-agent verified: `Event.report_id` FK usable in correlated subquery, `row.Report`/`row.event_count` access valid in SQLAlchemy 2.x, `conftest.py` auto-picks up new router, no route-ordering concerns.

## Findings

### F1 — DELETE 204: contract used Response(status_code=204) without the import

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 — routers/reports.py DELETE endpoint contract
- **Detail**: The contract originally said "Return `Response(status_code=204)`". `Response` is not imported anywhere in the codebase (routers/auth.py imports only APIRouter, Depends, HTTPException, status). Following the contract literally produced a NameError at runtime. The codebase convention is typed return annotations (routers/auth.py:14 — `-> TokenResponse` with `status_code=HTTP_201_CREATED`). Sub-agent verified: `-> None` + `status_code=HTTP_204_NO_CONTENT` on the decorator is idiomatic FastAPI and sends an empty 204 body with no import needed.
- **Fix A ⭐ Recommended**: Changed contract to `-> None` annotation + `status_code=status.HTTP_204_NO_CONTENT`. No import needed, matches codebase style.
  - Confidence: HIGH — verified against installed FastAPI 0.139.0.
- **Decision**: FIXED via Fix A

### F2 — ApiError import not stated in ReportList/ReportDetail contracts

- **Severity**: 🔵 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 — ReportDetail.tsx and ReportList.tsx contracts
- **Detail**: Both contracts referenced `ApiError` by name but didn't mention the import. Login.tsx:5 establishes `import { apiFetch, ApiError } from '../api/client'` as the pattern; an implementer reading only the plan contracts could miss this and produce a TypeScript compile error.
- **Fix**: Added `import { apiFetch, ApiError } from '../api/client'` to each component's contract note.
- **Decision**: FIXED
