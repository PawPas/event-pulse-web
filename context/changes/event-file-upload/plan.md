# Event File Upload Implementation Plan

## Overview

Add CSV and JSON file upload to EventPulse so users can attach customer events to a report. The backend validates every record before persisting anything; the frontend adds an inline upload section to ReportDetail with client-side pre-check and clear error display.

## Current State Analysis

- `Event` table and ORM model already exist (`models/event.py`) with the correct four-column schema and indexes on `report_id` and `(report_id, customer_id)`.
- `ReportDetail.tsx` renders the report but currently hard-disables the "Run Analysis" button whenever `status === 'created'`, regardless of event count — this must be fixed.
- `apiFetch` in `client.ts` unconditionally sets `Content-Type: application/json`, which prevents multipart uploads. A separate helper is needed.
- `python-multipart` is absent from `pyproject.toml`; FastAPI requires it to receive `UploadFile` bodies.
- No events router exists yet.

## Desired End State

A user on the ReportDetail page can select a `.csv` or `.json` file, click Upload, and see either a success message ("Successfully uploaded N events") or a clear validation error summary. After a successful upload, the event count on the page updates and the "Run Analysis" button becomes enabled. Files that exceed 200,000 events are rejected — on the client for CSV (fast-fail) and on the server for both formats. No events are written to the database unless the entire file passes validation.

### Key Discoveries

- `Event.amount` is stored as `Numeric(15, 4)` — the parser must convert string values to `Decimal` and reject non-numeric inputs.
- `Event.timestamp` is `DateTime(timezone=True)` — ISO 8601 strings without timezone offset are treated as UTC (per PRD) and must be stored with UTC tzinfo attached.
- `routers/reports.py` is the pattern to follow: `APIRouter(prefix="/api/reports")`, `get_current_user` dependency, Pydantic v2 response models.
- Test harness uses `TestClient` + SQLite in-memory; `tests/conftest.py` is module-scoped. New event upload tests follow the same fixture pattern as `test_reports.py`.

## What We're NOT Doing

- No deduplication of events — appending the same file twice inserts duplicate rows (MVP acceptable).
- No streaming or chunked insert for large files — full in-memory parse then single bulk insert.
- No upload progress indicator — a button loading state (`Uploading…`) is sufficient.
- No upload UI for reports in `analyzing`, `completed`, or `failed` status — that is S-05 scope.
- No client-side line-count pre-check for JSON files — only CSV is pre-checked; backend enforces the 200k cap for both.

## Implementation Approach

Two phases: backend first (new router + tests), frontend second (helper + ReportDetail update). The backend is the authoritative validator; the client-side CSV check is a UX convenience, not a security control. Validation is a full single-pass over all records — errors are collected (up to 5 sample messages with row numbers) before any insert is attempted. If any record fails, the whole upload is rejected with a formatted error string.

## Critical Implementation Details

**FileReader is callback-based.** The CSV line-count pre-check in the upload handler must wrap `FileReader.readAsText()` in a `Promise<string>` so the async count can gate the upload call before `apiFetchFile` is invoked.

**UTC attachment for naive timestamps.** Python's `datetime.fromisoformat()` on a string like `"2024-03-15T10:30:00"` returns a naive datetime. Per PRD, naive timestamps are treated as UTC — the parser must attach `timezone.utc` before inserting, or the `DateTime(timezone=True)` column will raise.

---

## Phase 1: Backend upload endpoint

### Overview

New `routers/events.py` with a single `POST /api/reports/{report_id}/events/upload` endpoint. Adds `python-multipart` to deps, registers the new router in `main.py`, and adds a full test file.

### Changes Required

#### 1. Add python-multipart dependency

**File**: `pyproject.toml`

**Intent**: FastAPI cannot parse `UploadFile` bodies without `python-multipart`.

**Contract**: Add `python-multipart>=0.0.9` to the `dependencies` list.

---

#### 2. New events router

**File**: `routers/events.py` (new)

**Intent**: Expose `POST /api/reports/{report_id}/events/upload`. Detect file format from extension, then parse all records into a list. Check the total count first — if it exceeds 200,000, return 400 immediately without per-record validation (PRD: "rejected at the upload boundary"). If count is within limit, validate every record, collect up to 5 error samples; reject with 422 if any fail. If all pass, bulk-insert in a single transaction.

**Contract**:

Route: `POST /api/reports/{report_id}/events/upload`  
Auth: `get_current_user` dependency (401 if missing)  
Input: `file: UploadFile = File(...)` (multipart)  
Response on success: `HTTP 200`, `UploadResult { events_added: int }`

Error responses (all use `HTTPException`, `detail` is a plain string):
- `400` — `file.filename` is `None` or has an unrecognized extension (not `.csv` or `.json`); check this before reading the file body to return a clean error rather than an AttributeError
- `400` — empty file, or JSON not an array
- `400` — total record count exceeds 200,000: `"File contains {N} events which exceeds the 200,000-event limit"`
- `404` — report not found or belongs to another user
- `422` — validation failures: `"Validation failed: {total_invalid} invalid record(s). Sample errors: {e1}; {e2}; …"` (up to 5 samples)

Validation rules per record (rows are 1-indexed for error messages):
- All four fields (`customer_id`, `timestamp`, `event_type`, `amount`) must be present and non-empty
- `timestamp` must parse via `datetime.fromisoformat()`; naive results get `timezone.utc` attached
- `amount` must convert to `Decimal` without error

File decoding: after `await file.read()`, decode bytes as UTF-8; wrap in `try/except UnicodeDecodeError` and return 400 `"File must be UTF-8 encoded"` on failure. Windows-1252 / Latin-1 exports from Excel are a common trigger.

CSV specifics: `csv.DictReader` with the decoded string content (via `io.StringIO`); required header columns are `customer_id`, `timestamp`, `event_type`, `amount` (missing header = 400 before row-level validation).

JSON specifics: `json.loads` of full file content; top-level must be a list (not a list = 400). During per-record validation, if an item is not a dict (e.g. a string, number, or null), treat it as a validation error: `"Row N: expected an object, got {type(item).__name__}"` — do not attempt field-presence checks on non-dict items, as that would raise a TypeError rather than a clean validation message.

Bulk insert: `db.add_all([Event(...) for r in records])` then `await db.commit()`.

---

#### 3. Register events router in main.py

**File**: `main.py`

**Intent**: Make the new upload endpoint reachable.

**Contract**: Import `router as events_router` from `routers.events` and call `app.include_router(events_router)` alongside the existing router registrations.

---

#### 4. Upload endpoint tests

**File**: `tests/test_events.py` (new)

**Intent**: Cover the upload contract end-to-end using the existing test harness (SQLite in-memory, `TestClient`, module-scoped `test_client` fixture).

**Contract**: The following cases must be present, each as a named test function:

- `test_upload_unauthenticated` — 401 with no auth header
- `test_upload_valid_csv` — well-formed CSV with all 4 columns, 200 OK, `events_added == row count`
- `test_upload_valid_json` — well-formed JSON array, 200 OK
- `test_upload_appends_to_existing` — second upload on the same report adds to (not replaces) existing events
- `test_upload_wrong_user_report` — user B cannot upload to user A's report (404)
- `test_upload_exceeds_limit` — file with > 200,000 records → 400
- `test_upload_missing_required_field` — record missing `amount` → 422 with error detail string
- `test_upload_invalid_timestamp` — unparseable timestamp value → 422
- `test_upload_invalid_amount` — non-numeric amount value → 422
- `test_upload_unsupported_extension` — `.txt` file → 400
- `test_upload_json_not_array` — JSON object instead of array → 400
- `test_upload_csv_missing_header` — CSV without required column → 400
- `test_upload_empty_file` — zero-byte file → 400

Helper in the test file: a factory function `make_csv_bytes(rows)` and `make_json_bytes(rows)` that produce minimal valid file bytes for parameterized test cases.

### Success Criteria

#### Automated Verification

- All event upload tests pass: `uv run pytest tests/test_events.py -v`
- Existing tests still pass: `uv run pytest tests/ -v`
- Application starts without import errors: `uv run uvicorn main:app --reload` (observe startup log, no traceback)

#### Manual Verification

- Upload a valid CSV file via curl or Postman to `POST /api/reports/{id}/events/upload`; response is `{"events_added": N}`
- Upload a file with a missing field; response contains a readable error string with row number
- Upload a file with > 200,000 records; response body mentions the limit

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to Phase 2.

---

## Phase 2: Frontend upload UI

### Overview

Add `apiFetchFile` to `client.ts`, add `UploadResult` type, and update `ReportDetail.tsx` with an inline upload section and a fixed "Run Analysis" button.

### Changes Required

#### 1. apiFetchFile helper

**File**: `frontend/src/api/client.ts`

**Intent**: Provide a multipart-capable fetch wrapper that shares the same auth and error-handling pattern as `apiFetch` but omits `Content-Type` (letting the browser set the multipart boundary).

**Contract**:

```typescript
export async function apiFetchFile(path: string, formData: FormData): Promise<unknown>
```

- No `Content-Type` header set (browser sets `multipart/form-data; boundary=...` automatically)
- `Authorization: Bearer <token>` added from `localStorage.getItem("token")` if present
- Method is always `POST`
- Error handling identical to `apiFetch`: throw `ApiError(status, body.detail)` on non-2xx

---

#### 2. UploadResult type

**File**: `frontend/src/types/report.ts`

**Intent**: Typed shape for the upload endpoint's success response.

**Contract**: Add `export interface UploadResult { events_added: number }` alongside the existing `Report` interface.

---

#### 3. ReportDetail upload UI and Run Analysis fix

**File**: `frontend/src/pages/ReportDetail.tsx`

**Intent**: Add three capabilities — an inline upload section, client-side CSV row pre-check, and a corrected "Run Analysis" button enable condition.

**Contract**:

New state variables:
- `uploadFile: File | null` — the selected file
- `uploadStatus: 'idle' | 'uploading' | 'success' | 'error'`
- `uploadError: string | null`
- `uploadEventsAdded: number | null`

Upload handler (`handleUpload`):
1. If `uploadFile.name` ends with `.csv`: wrap `FileReader.readAsText()` in a Promise, count newlines in the result; if estimated row count > 200,000 (subtract 1 for header), set `uploadError` and return early without a network call.
2. Append file to `new FormData()` under the key `"file"`.
3. Call `apiFetchFile('/api/reports/${id}/events/upload', formData)`.
4. On success: set `uploadStatus = 'success'`, store `events_added`, then re-fetch the report (`apiFetch('/api/reports/${id}')`) and call `setReport(data)`.
5. On `ApiError`: set `uploadStatus = 'error'`, `uploadError = err.detail`.

Upload UI section (rendered only when `report.status === 'created'`):
- `<input type="file" accept=".csv,.json">` — `onChange` sets `uploadFile` and resets prior status/error
- `<button>` labeled "Upload" / "Uploading…" — disabled when `uploadStatus === 'uploading'` or `uploadFile === null`
- Success message: `"Successfully uploaded {uploadEventsAdded} events."` (green or neutral color)
- Error message: `uploadError` string in red

Run Analysis button fix — change the existing `disabled` prop from unconditional `true` to `report.event_count === 0`. Update `title` accordingly:
- `event_count === 0` → `title="Add events first to run analysis"`, `disabled`
- `event_count > 0` → no title, not disabled (click handler is S-05 scope; no `onClick` needed here)

### Success Criteria

#### Automated Verification

- Frontend builds without type errors: `cd frontend && npm run build`
- Lint passes: `cd frontend && npm run lint`

#### Manual Verification

- Select a valid CSV file on the ReportDetail page, click Upload; see "Successfully uploaded N events" and updated event count
- Select a valid JSON file; same success flow
- Select a CSV with > 200,000 lines; see the client-side rejection message before any network call
- Upload a CSV with a missing required field; see the backend error message displayed in red
- Confirm "Run Analysis" button is disabled before upload and enabled after a successful upload
- Confirm existing delete-report modal still works after upload UI changes

**Implementation Note**: After completing this phase and all verification passes, confirm no regressions before considering the phase done.

---

## Testing Strategy

### Unit Tests (backend)

Covered in `tests/test_events.py` — 13 named cases spanning auth, isolation, format detection, record validation, limit enforcement, and append behaviour.

### Integration Tests (manual)

1. Register a new user, create a report, upload a CSV, confirm event count in the report detail response.
2. Upload a second file to the same report; confirm total event count is cumulative.
3. Upload a file with a bad row; confirm zero events are stored after the rejection.

### Manual Testing Steps

1. Run backend: `uv run uvicorn main:app --reload`
2. Run frontend: `cd frontend && npm run dev`
3. Log in, open any report, verify the upload section is visible
4. Upload `samples/valid.csv` (create a 5-row test file); expect success message
5. Refresh the page; event count should persist
6. Upload a file with a missing `amount` column; expect red error with row reference
7. Select a 200,001-row CSV; expect instant client-side rejection (no spinner, no network tab request)
8. Verify "Run Analysis" button is enabled after upload

## References

- PRD §Event Ingestion: `context/foundation/prd.md` (FR-008, NFR event cap, Business Logic §Event schema)
- Roadmap S-03: `context/foundation/roadmap.md`
- Existing router pattern: `routers/reports.py`
- Existing test pattern: `tests/test_reports.py`, `tests/conftest.py`
- Frontend API pattern: `frontend/src/api/client.ts`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Backend upload endpoint

#### Automated

- [x] 1.1 All event upload tests pass: `uv run pytest tests/test_events.py -v` — ad486a0
- [x] 1.2 Existing tests still pass: `uv run pytest tests/ -v` — ad486a0
- [x] 1.3 Application starts without import errors: `uv run uvicorn main:app --reload` — ad486a0

#### Manual

- [x] 1.4 Upload a valid CSV via curl/Postman; response is `{"events_added": N}` — ad486a0
- [x] 1.5 Upload a file with a missing field; response contains readable error with row number — ad486a0
- [x] 1.6 Upload > 200,000 records; response mentions the limit — ad486a0

### Phase 2: Frontend upload UI

#### Automated

- [x] 2.1 Frontend builds without type errors: `cd frontend && npm run build`
- [x] 2.2 Lint passes: `cd frontend && npm run lint`

#### Manual

- [x] 2.3 Upload valid CSV on ReportDetail; see success message and updated event count
- [x] 2.4 Upload valid JSON; same success flow
- [x] 2.5 Select CSV > 200k lines; client-side rejection before network call
- [x] 2.6 Upload CSV with missing field; backend error displayed in red
- [x] 2.7 "Run Analysis" button disabled before upload, enabled after
- [x] 2.8 Delete modal still works after upload UI changes
