# Report Management Implementation Plan

## Overview

Build the CRUD report management slice (S-02): users can create a named report, view their report list, open a report to see its pre-analysis detail, and delete a report with a confirmation modal. This lands four PRD functional requirements (FR-004–FR-007) in two phases: backend API first, then frontend pages and routing.

## Current State Analysis

- `models/report.py` — `Report` ORM model is fully defined: `id (UUID)`, `user_id (FK→users)`, `name (String 255)`, `description (Text nullable)`, `status (ReportStatus enum: created/analyzing/completed/failed)`, `analyzed_at`, `created_at`, `updated_at`. Relationships to `User` and `Event` are wired. No migration needed.
- `auth/dependencies.py:12` — `get_current_user` returns `TokenPayload(sub: str, email: str)`; `sub` is the string user UUID used for all user-scoped queries via `UUID(current_user.sub)`.
- `routers/auth.py` — canonical router pattern: `APIRouter(prefix="/api/auth", tags=["auth"])`, async handlers, `get_db` + dependency injection. Report router follows this exactly.
- `database.py:32` — `get_db()` async session generator, ready to inject.
- `tests/conftest.py:18` — `test_client` fixture with `scope="module"`: fresh in-memory SQLite DB per test file, `app.dependency_overrides[get_db]` for isolation.
- `frontend/src/api/client.ts` — `apiFetch(path, options)` handles auth headers and throws `ApiError(status, detail)` on non-2xx; used by all pages.
- `frontend/src/App.tsx` — ProtectedRoute wraps AppShell with one nested index route (`<Dashboard />`); new report routes nest here.
- `frontend/src/pages/Dashboard.tsx` — placeholder "Welcome, {email}" component; will be deleted and replaced by `ReportList`.
- 10 tests currently passing.

## Desired End State

After this plan is complete:

- `POST /api/reports/` — authenticated, creates report, returns `ReportResponse` with `event_count: 0`
- `GET /api/reports/` — authenticated, returns list of caller's reports newest-first with `event_count` per report
- `GET /api/reports/{report_id}` — authenticated, returns single report; 404 if not found or owned by another user
- `DELETE /api/reports/{report_id}` — authenticated, deletes caller's report; 204; 404 if not found or wrong owner
- `uv run pytest tests/test_reports.py -v` — 9 new tests pass
- `uv run pytest tests/ -v` — all 19 tests pass (10 prior + 9 new)
- Frontend: authenticated users see report list at `/`; create inline via form; navigate to `/reports/:id` for detail; delete via confirmation modal; "Run Analysis" button visible but disabled on detail page
- `cd frontend && npm run build` and `npm run lint` both pass

### Key Discoveries

- `models/report.py:46` — `Report.events` relationship uses `cascade="all, delete-orphan"`, so deleting a Report also purges its Event rows — no manual cascade in the endpoint needed.
- `auth/schemas.py:5` — `TokenPayload.sub` is the string user UUID written by `create_access_token(subject=str(user.id), ...)`. Convert back with `UUID(current_user.sub)` in report endpoints.
- `tests/conftest.py:18` — `scope="module"` means each test file gets its own isolated in-memory DB; module-level `_state` dict carries report IDs across ordered tests within the file.
- `frontend/src/store/index.ts` — Redux store currently holds only `auth`; report data is NOT stored in Redux — local `useState`/`useEffect` per page is the chosen approach.
- `frontend/vite.config.ts:8` — `/api` is proxied to `http://localhost:8000` in dev; `apiFetch('/api/reports/')` works without a base URL.

## What We're NOT Doing

- No Redux slice for reports — local component state per page; no cache invalidation complexity
- No pagination on the report list — PRD does not specify it; at MVP scale a flat list suffices
- No "Run Analysis" functionality — button renders disabled; wired in S-05
- No event upload or sample data — those are S-03/S-04
- No report editing (rename/re-describe) — not in FR-004–FR-007
- No per-field validation beyond "name is required" — PRD does not specify constraints beyond name + optional description
- No server-side delete confirmation — confirmation is a frontend modal only; the backend simply executes the DELETE

## Implementation Approach

Backend first (Phase 1): all four endpoints + inline Pydantic schemas + report router + wire into `main.py` + 9 pytest tests. The `event_count` field uses a correlated scalar subquery so every response includes it without N+1 queries.

Frontend second (Phase 2): TypeScript type, ReportList page (inline create form + modal delete), ReportDetail page (two-state: pre-analysis view with disabled "Run Analysis"), routing changes in App.tsx, AppShell app-name link, Dashboard.tsx removed.

## Critical Implementation Details

**`event_count` via correlated scalar subquery.** In both list and detail endpoints, `event_count` is computed with `select(func.count(Event.id)).where(Event.report_id == Report.id).correlate(Report).scalar_subquery()`. The query returns `Row(Report, int)` tuples, not plain `Report` objects — construct `ReportResponse` explicitly from each row rather than using `model_validate`.

**User-scoping is the only access control.** There is no 403 — a report that exists but belongs to another user returns 404 (`"Report not found"`). This matches the user-enumeration-prevention principle established in auth-flows (same error for wrong email vs missing user).

**safeJsonParse lesson does not apply here.** Report data is fetched from the API on mount, never from `localStorage`. The `safeJsonParse` lesson applies only to `localStorage` reads at initialisation.

---

## Phase 1: Backend report API + tests

### Overview

Add four report endpoints in `routers/reports.py`, wire the router into `main.py`, and write `tests/test_reports.py` with 9 tests covering the happy path, unauthenticated access, not-found, and cross-user isolation.

### Changes Required

#### 1. Create routers/reports.py

**File**: `routers/reports.py` (new)

**Intent**: Isolate all report route handlers in an `APIRouter` following the exact pattern of `routers/auth.py`. All four endpoints are user-scoped via `get_current_user`.

**Contract**: `router = APIRouter(prefix="/api/reports", tags=["reports"])`.

Four inline Pydantic v2 models at the top of the file:
- `CreateReportRequest(BaseModel)` — `name: str`, `description: str | None = None`
- `ReportResponse(BaseModel)` — `id: str`, `name: str`, `description: str | None`, `status: str`, `event_count: int`, `analyzed_at: datetime | None`, `created_at: datetime`, `updated_at: datetime`

Four route handlers:

- `POST /` → 201, `response_model=ReportResponse`
  - Construct `Report(user_id=UUID(current_user.sub), name=payload.name, description=payload.description)`, `db.add`, `commit`, `refresh`. Return `ReportResponse(..., event_count=0)`.

- `GET /` → 200, `response_model=list[ReportResponse]`
  - Correlated subquery: `event_count_sq = select(func.count(Event.id)).where(Event.report_id == Report.id).correlate(Report).scalar_subquery()`.
  - `select(Report, event_count_sq.label("event_count")).where(Report.user_id == UUID(current_user.sub)).order_by(Report.created_at.desc())`.
  - Build and return `list[ReportResponse]` from the resulting rows.

- `GET /{report_id}` → 200, `response_model=ReportResponse`
  - Same subquery, additionally `.where(Report.id == report_id)`. If row is `None` or `row.Report.user_id != UUID(current_user.sub)`, raise `HTTPException(404, "Report not found")`.

- `DELETE /{report_id}` → 204 (no response body), handler annotated `-> None`
  - `select(Report).where(Report.id == report_id)`. If not found or `report.user_id != UUID(current_user.sub)` → 404. `await db.delete(report)`, `await db.commit()`. Return nothing (`None`). Decorator: `@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)`. FastAPI strips the body automatically — no `Response` import needed.

#### 2. Wire router into main.py

**File**: `main.py`

**Intent**: Register the reports router so its endpoints are served under `/api/reports/`.

**Contract**: Import `router as reports_router` from `routers.reports`; call `app.include_router(reports_router)` after the existing `app.include_router(auth_router)` line.

#### 3. Write tests/test_reports.py

**File**: `tests/test_reports.py` (new)

**Intent**: Cover the four endpoints with 9 HTTP-level tests against the in-memory SQLite DB. All tests use the `test_client` fixture from `conftest.py`.

**Contract**: Two module-scoped fixtures added at the top of this file:
- `auth_token(test_client)` — registers `reports_user_a@test.com` via `POST /api/auth/register`, returns `access_token`. `scope="module"`.
- `auth_token_b(test_client)` — registers `reports_user_b@test.com`, returns `access_token`. `scope="module"`.

Module-level `_state: dict[str, str] = {}` carries `report_id` across ordered tests.

Nine test functions (order-dependent within module):
1. `test_create_report_unauthenticated` — POST `/api/reports/` with no token → 401
2. `test_create_report_success(test_client, auth_token)` — POST with token + `{name: "Q4 Report"}` → 201; stores `response.json()["id"]` in `_state["report_id"]`
3. `test_create_report_missing_name(test_client, auth_token)` — POST with `{}` (name omitted) → 422
4. `test_list_reports(test_client, auth_token)` — GET `/api/reports/` → 200, list has 1 item, `event_count == 0`
5. `test_get_report_success(test_client, auth_token)` — GET `/api/reports/{_state["report_id"]}` → 200, `name == "Q4 Report"`
6. `test_get_report_not_found(test_client, auth_token)` — GET `/api/reports/00000000-0000-0000-0000-000000000000` → 404
7. `test_isolation_get(test_client, auth_token_b)` — GET user A's report ID as user B → 404
8. `test_isolation_delete(test_client, auth_token_b)` — DELETE user A's report ID as user B → 404
9. `test_delete_report_success(test_client, auth_token)` — DELETE user A's own report → 204; follow-up GET → 404

### Success Criteria

#### Automated Verification

- All new tests pass: `uv run pytest tests/test_reports.py -v` (9/9)
- Full suite passes: `uv run pytest tests/ -v` (19/19)
- Import check: `uv run python -c "from routers.reports import router; print('ok')"`

#### Manual Verification

- Start server: `uv run uvicorn main:app --reload`
- Register + login via `POST /api/auth/register`, capture token
- `curl -s -X POST http://localhost:8000/api/reports/ -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"name":"My Report"}' | python3 -m json.tool` → 201 with `id`, `event_count: 0`
- `curl -s http://localhost:8000/api/reports/ -H "Authorization: Bearer <token>"` → list with 1 report
- `curl -s -X DELETE http://localhost:8000/api/reports/<id> -H "Authorization: Bearer <token>"` → 204
- Request without token → 401

**Implementation Note**: After all automated verification passes, pause for manual curl verification before proceeding to Phase 2.

---

## Phase 2: Frontend report pages + routing

### Overview

Add TypeScript types, replace the Dashboard placeholder with a `ReportList` page (inline create form + delete modal), add a `ReportDetail` page with the two-state layout, update App.tsx routing, and remove Dashboard.tsx. All data fetching uses local component state with `apiFetch`.

### Changes Required

#### 1. Create frontend/src/types/report.ts

**File**: `frontend/src/types/report.ts` (new)

**Intent**: Single source of truth for the Report shape on the frontend. Imported by both `ReportList` and `ReportDetail`.

**Contract**:
```typescript
export interface Report {
  id: string
  name: string
  description: string | null
  status: 'created' | 'analyzing' | 'completed' | 'failed'
  event_count: number
  analyzed_at: string | null
  created_at: string
  updated_at: string
}
```

#### 2. Create frontend/src/pages/ReportList.tsx

**File**: `frontend/src/pages/ReportList.tsx` (new)

**Intent**: Main authenticated home screen. Shows the user's reports (newest first), an inline create form, and handles deletion via a confirmation modal. Replaces the Dashboard placeholder as the index route.

**Contract**: Key imports: `import { apiFetch, ApiError } from '../api/client'` and `import type { Report } from '../types/report'`. Component state:
- `reports: Report[]` — fetched on mount via `GET /api/reports/`
- `loading: boolean` — true during initial fetch
- `error: string | null` — error message if fetch fails
- `showForm: boolean` — toggles create form visibility
- `name: string`, `description: string` — controlled inputs for the create form
- `creating: boolean` — true while POST is in flight (disables submit button)
- `formError: string | null` — inline validation error on the create form
- `deletingId: string | null` — non-null means the delete confirmation modal is open for that report ID
- `deleteInFlight: boolean` — true while DELETE is in flight

Fetch on mount: `useEffect(() => { apiFetch('/api/reports/').then(...) }, [])`.

Create: POST `/api/reports/` with `{ name, description: description || null }`. On success: prepend new report to `reports` (not a full refetch), hide form, clear inputs. On error: set `formError`.

Delete: when user confirms in modal, `DELETE /api/reports/{deletingId}`. On success: filter report from `reports` state, set `deletingId = null`.

UI elements (no CSS framework — inline styles following AppShell's pattern):
- "Create New Report" button → toggles `showForm`
- Form (when `showForm`): name input (required), description textarea (optional), Submit + Cancel buttons
- Empty state (when `reports.length === 0` and not loading): "No reports yet. Create your first one above."
- Report list: each row shows name (as `<Link to={/reports/${id}}>`) + created date + event count badge + Delete button
- Delete confirmation modal (when `deletingId !== null`): overlay div with "Delete '{name}'? This cannot be undone." + Cancel + Delete buttons

#### 3. Create frontend/src/pages/ReportDetail.tsx

**File**: `frontend/src/pages/ReportDetail.tsx` (new)

**Intent**: Two-state report page. Pre-analysis state (status: `created`) shows report metadata and a disabled "Run Analysis" button. Post-analysis state (status: `completed`) shows the same metadata with a note that analysis is complete. S-05 wires the button and adds the results panel.

**Contract**: Key imports: `import { apiFetch, ApiError } from '../api/client'` and `import type { Report } from '../types/report'`. Uses `useParams<{ id: string }>()` to get the report ID from the URL.

Component state: `report: Report | null`, `loading: boolean`, `notFound: boolean`, `showDeleteModal: boolean`, `deleteInFlight: boolean`.

Fetch on mount: `GET /api/reports/{id}`. On `ApiError` with `status === 404`: set `notFound = true`. Other errors: set generic error message.

UI elements:
- `← Back to reports` link (`<Link to="/">`)
- Report name as `<h1>`
- Description (if non-null)
- Status badge (text only)
- Event count: "{event_count} events"
- "Run Analysis" button: always rendered, `disabled`, `title="Add events first to run analysis"` — status `created` only; hidden when status is `completed` or `analyzing`
- Delete button → `setShowDeleteModal(true)`
- Delete confirmation modal (same pattern as ReportList modal)
- On successful delete: `navigate("/")`
- Not-found state: "Report not found." + back link

#### 4. Update frontend/src/App.tsx

**File**: `frontend/src/App.tsx`

**Intent**: Replace the `<Dashboard />` index route with `<ReportList />` and add the `reports/:id` nested route under the existing ProtectedRoute/AppShell wrapper.

**Contract**: Import `ReportList` from `./pages/ReportList` and `ReportDetail` from `./pages/ReportDetail`; remove the `Dashboard` import. The route tree becomes:
- `/login` → `<Login />`
- `/register` → `<Register />`
- `/` (ProtectedRoute → AppShell):
  - index → `<ReportList />`
  - `reports/:id` → `<ReportDetail />`

#### 5. Update frontend/src/pages/AppShell.tsx

**File**: `frontend/src/pages/AppShell.tsx`

**Intent**: Add a clickable app name that navigates to `/` (the report list) so users can return home from any nested route.

**Contract**: Import `Link` from `react-router-dom`. In the `<nav>`, wrap the app name `"EventPulse"` in `<Link to="/">EventPulse</Link>` as the leftmost nav element, before the email display. No other changes.

#### 6. Delete frontend/src/pages/Dashboard.tsx

**File**: `frontend/src/pages/Dashboard.tsx` (delete)

**Intent**: The Dashboard placeholder is fully replaced by ReportList as the authenticated index route.

**Contract**: File is removed. No other file imports it after App.tsx is updated.

### Success Criteria

#### Automated Verification

- Type check + build: `cd frontend && npm run build` (exits 0)
- Lint: `cd frontend && npm run lint` (exits 0)

#### Manual Verification

- Navigate to `http://localhost:5173/` → shows report list (empty state: "No reports yet…")
- Click "Create New Report" → inline form appears
- Submit with name "Q4 Retention" → report appears in list with "0 events" badge
- Click the report name → navigates to `/reports/{id}`, shows name, description (empty), "0 events", disabled "Run Analysis" button with tooltip visible on hover
- Click Delete on detail page → modal appears with report name in message
- Confirm delete → navigates to `/`, list is empty
- Create two reports → both appear, newest at top
- Click Delete on list row → modal appears, cancel → report stays; confirm → report removed
- Navigate directly to `/reports/00000000-0000-0000-0000-000000000000` → "Report not found." shown with back link
- `uv run pytest tests/ -v` — all 19 tests pass (regression)
- AppShell "EventPulse" link navigates to `/` from detail page

**Implementation Note**: After all automated verification passes, pause for manual browser testing before considering this phase complete.

---

## Testing Strategy

### Backend Tests

- `tests/test_reports.py` — 9 HTTP-level endpoint tests against in-memory SQLite, covering: unauthenticated access, CRUD happy paths, missing-name validation, not-found, and cross-user isolation.
- `tests/test_auth_flows.py` — 5 tests continue to pass as regression (auth routes unchanged).

### Frontend Tests

No frontend test runner configured. Verified via manual browser testing per phase success criteria.

### Manual Testing Steps

1. `uv run uvicorn main:app --reload` (backend)
2. `cd frontend && npm run dev` (frontend at `http://localhost:5173`)
3. Register a new user → confirm redirect to `/`, empty report list
4. Create a report via inline form → appears in list
5. Click report → detail page, disabled button, 0 events
6. Delete via detail page → returns to empty list
7. Create two reports → newest appears first
8. Delete via list modal → removed immediately
9. Navigate to unknown report URL → "Report not found."
10. `uv run pytest tests/ -v` → 19/19 pass
11. `cd frontend && npm run lint` → exits 0

## Performance Considerations

At MVP data volumes (single user, handful of reports), the correlated `event_count` scalar subquery adds negligible overhead. No caching or index hints required.

## Migration Notes

No Alembic migration needed. The `reports` and `events` tables were created by the F-02 migration (`26aaf8bb5019_initial_schema.py`), which is already applied to Railway Postgres.

## References

- Roadmap: `context/foundation/roadmap.md` §S-02
- PRD: `context/foundation/prd.md` §Reports (FR-004–FR-007)
- Auth-flows plan: `context/archive/2026-07-20-auth-flows/plan.md` (router + test + Redux patterns)
- Report model: `models/report.py`
- Auth dependency: `auth/dependencies.py`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend report API + tests

#### Automated

- [x] 1.1 New tests pass: `uv run pytest tests/test_reports.py -v` (9/9) — 5c2d6c2
- [x] 1.2 Full suite passes: `uv run pytest tests/ -v` (19/19) — 5c2d6c2
- [x] 1.3 Import check: `uv run python -c "from routers.reports import router; print('ok')"` — 5c2d6c2

#### Manual

- [x] 1.4 `curl POST /api/reports/` with token → 201 with `id` and `event_count: 0` — 5c2d6c2
- [x] 1.5 `curl GET /api/reports/` → list with 1 report — 5c2d6c2
- [x] 1.6 `curl DELETE /api/reports/<id>` → 204 — 5c2d6c2
- [x] 1.7 Request without token → 401 — 5c2d6c2

### Phase 2: Frontend report pages + routing

#### Automated

- [x] 2.1 Build passes: `cd frontend && npm run build` — b946029
- [x] 2.2 Lint passes: `cd frontend && npm run lint` — b946029

#### Manual

- [x] 2.3 Unauthenticated `/` redirects to `/login` — b946029
- [x] 2.4 Empty list → "No reports yet…" empty state shown — b946029
- [x] 2.5 Inline create form → report appears in list — b946029
- [x] 2.6 Click report → detail page with disabled "Run Analysis" button — b946029
- [x] 2.7 Delete modal on detail page → confirm → navigates to `/`, report gone — b946029
- [x] 2.8 Delete modal on list → cancel keeps report, confirm removes it — b946029
- [x] 2.9 Unknown report URL → "Report not found." with back link — b946029
- [x] 2.10 `uv run pytest tests/ -v` — all 19 pass (regression) — b946029
- [x] 2.11 AppShell "EventPulse" link navigates to `/` — b946029
