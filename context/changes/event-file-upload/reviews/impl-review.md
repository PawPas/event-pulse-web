<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Event File Upload

- **Plan**: context/changes/event-file-upload/plan.md
- **Scope**: Full plan (Phase 1 + Phase 2 of 2)
- **Date**: 2026-07-21
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Automated Checks

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_events.py -v` | 13 passed |
| `uv run pytest tests/ -v` | 32 passed, 0 warnings |
| `cd frontend && npm run build` | Clean build, no type errors |
| `cd frontend && npm run lint` | 0 findings |

## Unplanned files

- `tests/resources/valid_events.csv` — user-requested mid-implementation; test fixture only, no functional scope
- `tests/resources/invalid_events.csv` — same
- `uv.lock` — automatic side effect of `uv add python-multipart`

## Plan Adherence Notes

All 7 changed files matched plan intent:
- `pyproject.toml`: `python-multipart>=0.0.9` added ✓
- `routers/events.py`: route, auth, all error codes, count-before-validate order, UTC attachment, Decimal coercion, bulk insert — all per contract ✓
- `main.py`: `events_router` registered alongside existing routers ✓
- `tests/test_events.py`: all 13 named test cases present; `make_csv_bytes`/`make_json_bytes` helpers present ✓
- `frontend/src/api/client.ts`: `apiFetchFile` — no Content-Type, Bearer token, POST, same ApiError path ✓
- `frontend/src/types/report.ts`: `UploadResult { events_added: number }` ✓
- `frontend/src/pages/ReportDetail.tsx`: upload state vars, CSV pre-check Promise, re-fetch on success, Run Analysis button fix ✓

## Findings

### F1 — `assert` used as type-narrowing in production upload path

- **Severity**: 👀 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: routers/events.py:159
- **Detail**: `assert event is not None` is used to narrow the type after the `if error:` branch. The assertion is logically sound — `_parse_record` never returns `(None, None)` — but `assert` statements are stripped by the Python optimizer (`-O` flag). If uvicorn were ever started with `-O`, the stripped assertion would pass `None` into `event.report_id = report_id`, raising an `AttributeError` at the DB layer (500) rather than the expected path. A type-narrowing guard (`if event is None: continue`) or `cast(Event, event)` is the conventional alternative.
- **Fix**: Replace `assert event is not None` with `if event is None: continue` to narrow the type without relying on a runtime-strippable check.
- **Decision**: FIXED — replaced assert with if-guard

### F2 — Private helper docstrings explain WHAT, not WHY

- **Severity**: 👀 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: routers/events.py:31, 63, 74
- **Detail**: Three one-line docstrings on private helpers (`_parse_record`, `_parse_csv`, `_parse_json`) describe what each function does — information already conveyed by the function name and type signature. Project rule: "Default to writing no comments. Only add one when the WHY is non-obvious."
- **Fix**: Remove the three docstrings. The names and type signatures are self-explanatory.
- **Decision**: FIXED — removed docstrings from _parse_record, _parse_csv, _parse_json

### F3 — `_state` dict populated but never consumed outside its own fixture

- **Severity**: 👀 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: tests/test_events.py:6, 57
- **Detail**: `_state: dict[str, str] = {}` is assigned `_state["report_id"] = rid` inside the `report_id` fixture, but no test function reads `_state` — they all receive `report_id` directly via pytest injection. The dict is vestigial; the fixture pattern itself carries the value correctly without it.
- **Fix**: Remove `_state` declaration and the `_state["report_id"] = rid` assignment line.
- **Decision**: FIXED — removed _state dict and assignment from report_id fixture
