<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Event File Upload Implementation Plan

- **Plan**: `context/changes/event-file-upload/plan.md`
- **Mode**: Deep
- **Date**: 2026-07-20
- **Verdict**: SOUND (after fixes)
- **Findings**: 0 critical · 2 warnings · 2 observations — all FIXED

## Verdicts

| Dimension | Verdict |
|---|---|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING → FIXED |
| Plan Completeness | WARNING → FIXED |

## Grounding

5/5 paths ✓ (2 new files correctly absent), 4/4 symbols ✓, brief↔plan ✓ (13 tests match)

## Findings

### F1 — UploadFile.filename is Optional[str]; None causes AttributeError

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 1 — routers/events.py contract
- **Detail**: `UploadFile.filename: str | None` (confirmed starlette/datastructures.py:420). Calling `.endswith('.csv')` on None raises AttributeError → 500 instead of 400.
- **Fix**: Add `file.filename is None` guard as first check before reading the file body.
- **Decision**: FIXED — added to error responses as first 400 condition

### F2 — Count-check vs. validation order not specified

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 — endpoint contract (processing order)
- **Detail**: Plan didn't specify whether count-check or per-record validation runs first. An implementer validating before counting would waste CPU on oversized files and return 422 instead of 400.
- **Fix**: Added explicit ordering to Intent: parse → count (return 400 if > 200k) → validate → insert.
- **Decision**: FIXED

### F3 — JSON array items not type-checked as dicts

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 1 — JSON specifics in endpoint contract
- **Detail**: Non-dict items in a JSON array (strings, numbers, null) cause TypeError during field-presence checks → 500.
- **Fix**: Added per-item type check to JSON contract: if item is not a dict, emit validation error "Row N: expected an object, got {type}".
- **Decision**: FIXED

### F4 — Non-UTF-8 file encoding not addressed

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 1 — endpoint contract
- **Detail**: `bytes.decode('utf-8')` on a Windows-1252 / Latin-1 CSV (common from Excel) raises UnicodeDecodeError → 500.
- **Fix**: Added file decoding step with try/except UnicodeDecodeError → 400 "File must be UTF-8 encoded". Also added lesson to `context/foundation/lessons.md`.
- **Decision**: FIXED
