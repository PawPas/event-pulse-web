# Auth Flows Implementation Plan

## Overview

Build the register / login / logout user flows end-to-end: three backend API endpoints backed by real DB writes, a Redux Toolkit auth store on the frontend, and the React pages (Login, Register) and authenticated shell (AppShell) that consume them. After this slice, a new visitor can create an account, log in, and reach a protected dashboard placeholder — every downstream slice (S-02+) drops into the shell without touching auth again.

## Current State Analysis

**Backend foundation is complete (F-01 + F-02):**
- `auth/security.py` — `hash_password`, `verify_password`, `create_access_token`, `decode_access_token` all present and tested
- `auth/dependencies.py` — `get_current_user` with `OAuth2PasswordBearer` (Authorization: Bearer header extraction)
- `auth/schemas.py` — `TokenPayload(sub, email)` only; no request/response schemas for register or login
- `models/user.py` — `User` ORM model with `id (UUID)`, `email (unique)`, `hashed_password`, timestamps — applied to Railway Postgres via Alembic
- `database.py` — `get_db()` async session dependency, ready to inject
- `main.py` — `/health`, `/api/me`, `/api/health/db`; **no** `/api/auth/*` routes
- `tests/conftest.py` — sets `SECRET_KEY` and `DATABASE_URL=sqlite+aiosqlite:///:memory:` sentinels; no table-creation fixture

**Frontend is a blank slate:**
- `react@19.2.7` + `react-dom` only — no router, no state management, no UI pages
- `App.tsx` is the Vite default template

## Desired End State

After this plan is complete:

- `POST /api/auth/register` accepts `{email, password}`, creates a User row, returns a JWT + user info (auto-login)
- `POST /api/auth/login` accepts `{email, password}`, verifies credentials, returns a JWT + user info
- `POST /api/auth/logout` returns 200 (client responsibility to clear token)
- `uv run pytest tests/test_auth_flows.py -v` — 5 tests pass against an in-memory SQLite DB
- `uv run pytest tests/ -v` — all prior tests still pass (regression)
- Frontend: React Router v7 + Redux Toolkit wired; `/login` and `/register` pages work end-to-end with the API; authenticated users see `AppShell` with their email and a logout button; unauthenticated access to `/` redirects to `/login`
- `npm run build` and `npm run lint` both pass

### Key Discoveries

- `auth/dependencies.py:7` — `OAuth2PasswordBearer(tokenUrl="/api/auth/login")` already points at the login endpoint we're adding; no change needed to `get_current_user`
- `auth/security.py:39-45` — `create_access_token(subject: str, email: str)` is the exact signature our register and login routes will call
- `models/user.py:12` — `User.id` is a `uuid.UUID` with `default=uuid.uuid4`; routes must call `str(user.id)` when passing to `create_access_token(subject=...)`
- `tests/conftest.py:4` — `DATABASE_URL` sentinel is already `sqlite+aiosqlite:///:memory:`; the new test fixture creates a second in-memory engine with tables applied via `Base.metadata.create_all()`, then overrides `get_db` — the lifespan's engine is a separate singleton and is not affected
- `frontend/package.json` — only `react` and `react-dom`; all three new packages (`react-router-dom`, `@reduxjs/toolkit`, `react-redux`) must be installed before any frontend code is written

## What We're NOT Doing

- No refresh tokens or token rotation — PRD and auth-scaffold plan both explicitly exclude this for MVP
- No email verification or password reset — flat user model per PRD §Access Control
- No server-side token blacklist — logout is client-side token deletion; stateless JWT
- No password strength rules — PRD does not specify them; a non-empty string passes
- No OAuth, social login, or passwordless auth — PRD §Access Control, locked decision
- No `/api/me` DB upgrade — `/api/me` continues to return the token payload as-is; a full user DB lookup can be added in S-02 when routes need the User object
- No frontend unit tests — backend test coverage is the verification gate; frontend is verified via manual browser testing

## Implementation Approach

**Backend first (Phase 1)**: all three endpoints + their Pydantic schemas + the SQLite test fixture land together. The test fixture pattern (async engine + `Base.metadata.create_all()` + `app.dependency_overrides[get_db]`) avoids any new test runner dep — it uses `asyncio.run()` for setup inside a synchronous pytest fixture, the same pattern the rest of the test suite follows.

**Redux store second (Phase 2)**: install dependencies and wire the store before writing any UI. The auth slice hydrates its initial state from `localStorage` so the session survives page refresh. The API client (`frontend/src/api/client.ts`) reads the token from `localStorage` directly — not from the Redux store — to avoid circular imports.

**UI last (Phase 3)**: React Router routes, ProtectedRoute guard, Login + Register form pages, AppShell. Each page dispatches `loginSuccess` / `logout` actions to the Redux store AND writes to / clears `localStorage` — the store is the source of truth for React re-renders; localStorage is the persistence layer.

## Critical Implementation Details

**Two separate SQLite engines in tests.** The app lifespan calls `database._get_engine()` which creates a module-level singleton engine from `DATABASE_URL`. The test fixture creates a *second* in-memory engine, runs `Base.metadata.create_all()` on it, and overrides `get_db` to yield sessions from that second engine. The lifespan engine is unused for auth routes in these tests. Both engines share the same `sqlite+aiosqlite:///:memory:` URL but are independent connections — SQLite in-memory engines are isolated per connection. The fixture must therefore import all model modules before calling `create_all()` so `Base.metadata` is fully populated.

**Redux ↔ localStorage dual-write.** The `authSlice` initial state reads `localStorage` on slice creation (`token: localStorage.getItem("token")`) so a page refresh restores the session without a re-login. The `loginSuccess` action must write both to Redux state AND to `localStorage`; the `logout` action must clear both. The `ProtectedRoute` component reads from the Redux store (not `localStorage`) so React re-renders instantly on logout without a page refresh.

**`str(user.id)` in JWT sub.** `User.id` is a `uuid.UUID` Python object. `create_access_token` expects `subject: str`. Always call `str(user.id)` — not `user.id` directly — or the JWT encode will fail with a serialization error.

---

## Phase 1: Backend auth endpoints + tests

### Overview

Add `UserRegister`, `LoginRequest`, `UserResponse`, `TokenResponse` Pydantic schemas; create `routers/auth.py` with the three endpoints; wire the router into `main.py`; extend `tests/conftest.py` with a SQLite table-creation fixture; and write `tests/test_auth_flows.py` with five endpoint tests.

### Changes Required

#### 1. Extend auth/schemas.py

**File**: `auth/schemas.py`

**Intent**: Add four Pydantic v2 models covering the request and response shapes for register and login. These live alongside the existing `TokenPayload` in the same file — no new module needed.

**Contract**: Four new models:
- `UserRegister(BaseModel)` — `email: str`, `password: str`
- `LoginRequest(BaseModel)` — `email: str`, `password: str`
- `UserResponse(BaseModel)` — `id: str`, `email: str` (never exposes `hashed_password`)
- `TokenResponse(BaseModel)` — `access_token: str`, `token_type: str = "bearer"`, `user: UserResponse`

#### 2. Create routers/auth.py

**File**: `routers/auth.py` (new), `routers/__init__.py` (new, empty)

**Intent**: Isolate all auth route handlers in an `APIRouter` so `main.py` stays small and each downstream slice can add its own router the same way.

**Contract**: `router = APIRouter(prefix="/api/auth", tags=["auth"])` with three routes:

- `POST /register` → status `201`, `response_model=TokenResponse`
  - `select(User).where(User.email == payload.email)` — raise `HTTPException(409, "Email already registered")` if found
  - `hash_password(payload.password)` → insert `User` row → `db.commit()` → `db.refresh(user)`
  - `create_access_token(subject=str(user.id), email=user.email)` → return `TokenResponse`

- `POST /login` → status `200`, `response_model=TokenResponse`
  - `select(User).where(User.email == payload.email)` — if not found or `not verify_password(...)`: raise `HTTPException(401, "Invalid email or password")` (same message for both cases — avoids user enumeration)
  - `create_access_token(...)` → return `TokenResponse`

- `POST /logout` → status `200`
  - No DB access needed; returns `{"message": "Logged out"}`. Client clears its token.

#### 3. Wire router into main.py

**File**: `main.py`

**Intent**: Register the auth router so its routes appear under `/api/auth/`.

**Contract**: Import `router as auth_router` from `routers.auth`; call `app.include_router(auth_router)` after the `app = FastAPI(lifespan=lifespan)` line. No other changes to existing routes.

#### 4. Extend tests/conftest.py with table-creation fixture

**File**: `tests/conftest.py`

**Intent**: Provide a `test_client` fixture that creates a fresh in-memory SQLite engine with all tables applied and overrides `get_db` so the three new endpoint tests hit a real schema without requiring a Postgres connection.

**Contract**: Add below the existing sentinel lines:
- Import `asyncio`, `create_async_engine`, `async_sessionmaker` from sqlalchemy, `StaticPool` from `sqlalchemy.pool`, `Base` from `models.base`, all model modules (`models.user`, `models.report`, `models.event`) for metadata registration, `get_db` from `database`, `app` from `main`, and `TestClient` from `fastapi.testclient`
- `pytest.fixture(scope="module")` named `test_client`:
  1. `engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)` — `StaticPool` forces all connections to reuse the same underlying `sqlite3.Connection` so tables created during setup are visible to every TestClient request. Without it, each async session opens a fresh empty in-memory database.
  2. `asyncio.run(...)` — `async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)`
  3. Define `async def override_get_db()` that yields sessions from an `async_sessionmaker` on that engine
  4. `app.dependency_overrides[get_db] = override_get_db`
  5. `with TestClient(app) as client: yield client`
  6. Teardown: `app.dependency_overrides.clear()` + `asyncio.run(engine.dispose())`

`scope="module"` means one engine + schema per test file — tests within `test_auth_flows.py` share the same in-memory DB and can depend on each other's state (e.g., `test_register_duplicate_email` re-uses the email inserted by `test_register_success`).

#### 5. Write tests/test_auth_flows.py

**File**: `tests/test_auth_flows.py` (new)

**Intent**: Five HTTP-level tests covering the happy path and the two primary error cases.

**Contract**: All tests accept `test_client` as a fixture parameter. Five test functions:
- `test_register_success` — POST `/api/auth/register` with `{email, password}` → assert 201, `response["access_token"]` is non-empty, `response["user"]["email"]` matches
- `test_register_duplicate_email` — POST same email again → assert 409, `response["detail"] == "Email already registered"`
- `test_login_success` — POST `/api/auth/login` with same credentials → assert 200, non-empty `access_token`
- `test_login_wrong_password` — POST with correct email + wrong password → assert 401
- `test_logout` — POST `/api/auth/logout` → assert 200

### Success Criteria

#### Automated Verification

- All new tests pass: `uv run pytest tests/test_auth_flows.py -v`
- Full suite still passes: `uv run pytest tests/ -v` (5 prior tests + 5 new = 10 total)
- Import check: `uv run python -c "from routers.auth import router; print('ok')"`

#### Manual Verification

- Start server with real `DATABASE_URL`: `uv run uvicorn main:app --reload`
- `curl -s -X POST http://localhost:8000/api/auth/register -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"secret"}' | python3 -m json.tool` → 201 with `access_token`
- `curl -s -X POST http://localhost:8000/api/auth/login` with same credentials → 200 with `access_token`
- Duplicate register → 409 `"Email already registered"`
- Wrong password → 401 `"Invalid email or password"`
- `uv run pytest tests/test_auth.py -v` — existing 3 tests still pass

---

## Phase 2: Frontend Redux store + API client

### Overview

Install the three frontend dependencies, configure the Redux store with an auth slice that hydrates from `localStorage`, and create a typed API client utility that attaches the Authorization header from `localStorage`.

### Changes Required

#### 1. Install frontend dependencies

**File**: `frontend/package.json` (updated by npm)

**Intent**: Add routing and state management libraries before any TypeScript source references them (avoids type errors during the write-then-install sequence).

**Contract**: From `frontend/`: `npm install react-router-dom @reduxjs/toolkit react-redux`. Verify `package.json` shows all three under `"dependencies"`.

#### 2. Redux store

**File**: `frontend/src/store/index.ts` (new)

**Intent**: Central Redux store configuration. Every slice added by future slices (S-02 reports, S-03 events) imports this file.

**Contract**: `configureStore` from `@reduxjs/toolkit`; combine `authReducer` from `authSlice`. Export `RootState` and `AppDispatch` types.

#### 3. Auth slice

**File**: `frontend/src/store/authSlice.ts` (new)

**Intent**: Own the single source of truth for whether the user is authenticated, who they are, and their token. Hydrates from `localStorage` on slice creation so page refresh restores the session.

**Contract**: `createSlice` with:
- Initial state: `{ token: localStorage.getItem("token"), user: JSON.parse(localStorage.getItem("user") ?? "null") }` — type `{ token: string | null, user: { id: string; email: string } | null }`
- `loginSuccess(state, action: PayloadAction<{ token: string; user: { id: string; email: string } }>)` — sets `state.token` + `state.user` AND calls `localStorage.setItem` for both
- `logout(state)` — clears `state.token` + `state.user` AND calls `localStorage.removeItem` for both

#### 4. Typed hooks

**Files**: `frontend/src/hooks/useAppDispatch.ts` (new), `frontend/src/hooks/useAppSelector.ts` (new)

**Intent**: Typed wrappers over `useDispatch` and `useSelector` so components never import the raw Redux hooks.

**Contract**: Standard RTK pattern — `useAppDispatch` returns `() => AppDispatch`; `useAppSelector` wraps `TypedUseSelectorHook<RootState>`.

#### 5. API client utility

**File**: `frontend/src/api/client.ts` (new)

**Intent**: Central fetch wrapper that automatically attaches `Authorization: Bearer <token>` from `localStorage` on every authenticated request, and parses the JSON response (or throws on non-2xx).

**Contract**: One exported function `apiFetch(path: string, options?: RequestInit): Promise<unknown>`. Reads `localStorage.getItem("token")` internally — no Redux import. Merges the Authorization header into `options.headers` when the token is present. Throws an object `{ status: number, detail: string }` on non-2xx to make error handling uniform across pages.

### Success Criteria

#### Automated Verification

- Type check + build: `cd frontend && npm run build` (exits 0)
- Lint: `cd frontend && npm run lint` (exits 0)

#### Manual Verification

- Redux DevTools browser extension shows the `auth` slice after app loads
- Refreshing the browser with a token in `localStorage` restores `auth.token` + `auth.user` in the DevTools store

---

## Phase 3: Frontend pages + routing + shell

### Overview

Replace the Vite default template with React Router routes, a `ProtectedRoute` guard, Login and Register form pages that call the API and dispatch to Redux, and an `AppShell` with nav and logout.

### Changes Required

#### 1. Update frontend/src/main.tsx

**File**: `frontend/src/main.tsx`

**Intent**: Wrap the React tree with `BrowserRouter` (React Router) and `Provider` (Redux) so every component can use routing and the store.

**Contract**: Import `BrowserRouter` from `react-router-dom` and `Provider` from `react-redux`; import `store` from `./store`; wrap `<App />` with `<Provider store={store}><BrowserRouter>…</BrowserRouter></Provider>`. Order matters: Provider outside BrowserRouter so router components can also dispatch to the store.

#### 2. Rewrite frontend/src/App.tsx

**File**: `frontend/src/App.tsx`

**Intent**: Replace the default Vite template with a `<Routes>` tree: public routes for `/login` and `/register`, and a protected root route that renders `AppShell`.

**Contract**: Three `<Route>` entries:
- `/login` → `<Login />`
- `/register` → `<Register />`
- `/` → `<ProtectedRoute><AppShell /></ProtectedRoute>` with a nested index route rendering `<Dashboard />`

No CSS import from the old template needed — keep or remove `App.css` as preferred; the new layout is minimal.

#### 3. ProtectedRoute component

**File**: `frontend/src/components/ProtectedRoute.tsx` (new)

**Intent**: Gate all product routes behind auth; redirect unauthenticated users to `/login` with the original destination preserved so login can redirect back.

**Contract**: Reads `token` from the Redux store via `useAppSelector`. If `token` is null, renders `<Navigate to="/login" replace />`. Otherwise renders `{children}`. Accepts `children: React.ReactNode`.

#### 4. Login page

**File**: `frontend/src/pages/Login.tsx` (new)

**Intent**: Email + password form that calls `POST /api/auth/login`, dispatches `loginSuccess`, and navigates to `/`.

**Contract**:
- Controlled form with `email` and `password` fields
- On submit: calls `apiFetch("/api/auth/login", { method: "POST", body: JSON.stringify({email, password}) })`
- On success: dispatches `loginSuccess({ token, user })` then `navigate("/")`
- On API error (caught `{ detail }`): sets an inline error string rendered below the form submit button
- Link to `/register` for new users

#### 5. Register page

**File**: `frontend/src/pages/Register.tsx` (new)

**Intent**: Email + password form that calls `POST /api/auth/register`, dispatches `loginSuccess` (auto-login), and navigates to `/`.

**Contract**: Same structure as Login page. On success dispatches `loginSuccess` and navigates to `/`. On 409 error: inline message `"This email is already registered"`. Link to `/login` for returning users.

#### 6. AppShell

**File**: `frontend/src/pages/AppShell.tsx` (new)

**Intent**: Authenticated layout wrapper: top navigation bar showing the logged-in user's email and a logout button, with an `<Outlet />` for child routes. Every downstream slice (S-02, S-03, …) renders inside this shell.

**Contract**:
- Reads `user.email` from Redux store via `useAppSelector`
- Logout button: dispatches `logout()` action (clears token from Redux + localStorage immediately) then calls `apiFetch("/api/auth/logout", { method: "POST" })` in a try/catch that ignores network errors (the client token is always cleared regardless of server reachability) then `navigate("/login")`
- Renders `<Outlet />` below the nav bar

#### 7. Dashboard placeholder

**File**: `frontend/src/pages/Dashboard.tsx` (new)

**Intent**: Placeholder home screen for the authenticated area. S-02 will replace this with the report list.

**Contract**: Minimal component: reads `user.email` from Redux store, renders `<h1>Welcome, {email}</h1>` and a short placeholder message.

### Success Criteria

#### Automated Verification

- Build: `cd frontend && npm run build` (exits 0)
- Lint: `cd frontend && npm run lint` (exits 0)

#### Manual Verification

- Navigate to `http://localhost:5173/` → redirects to `/login`
- Register with a new email → lands on `/` showing `Welcome, {email}` in `AppShell`
- Refresh the page → session persists (token in `localStorage`, Redux store hydrated)
- Logout button → token cleared, redirects to `/login`, Redux DevTools shows `token: null`
- Navigate to `/login` → log in with registered credentials → lands on `/`
- Try duplicate email on `/register` → inline error `"This email is already registered"`
- Try wrong password on `/login` → inline error `"Invalid email or password"`
- `uv run pytest tests/ -v` — all 10 tests pass (regression: frontend changes must not break backend)

---

## Testing Strategy

### Unit Tests

None added — the backend endpoint tests in `test_auth_flows.py` cover the auth contract at the HTTP level with a real schema. Frontend is verified via manual browser testing.

### Integration Tests

- `tests/test_auth_flows.py` — five endpoint tests against in-memory SQLite; exercises real ORM inserts, uniqueness constraints, and password verification
- `tests/test_auth.py` — existing three tests continue to pass as regression coverage for `GET /api/me`

### Manual Testing Steps

1. Start backend: `uv run uvicorn main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Register at `http://localhost:5173/register` → confirm redirect to `/`
4. Refresh browser → confirm session persists (no re-login prompt)
5. Logout → confirm redirect to `/login`, DevTools `auth.token` is null
6. Login at `/login` → confirm redirect to `/`
7. Try registering the same email → confirm 409 inline error on the form
8. Try wrong password at `/login` → confirm 401 inline error
9. `uv run pytest tests/ -v` → all 10 tests pass
10. `cd frontend && npm run lint` → exits 0

## Migration Notes

No Alembic migration needed — `users` table already exists (F-02). The three new endpoints operate on the existing schema.

Railway pre-start command update (manual gate): the `alembic upgrade head && uvicorn ...` command set during F-02 is still correct — no change needed. Verify `SECRET_KEY` is set in Railway's `event-pulse-api` service environment before deploying (it was a manual gate in F-01).

## References

- Roadmap: `context/foundation/roadmap.md` §S-01
- PRD Access Control: `context/foundation/prd.md` §Access Control (email + password only, flat model)
- Auth scaffold plan: `context/changes/auth-scaffold/plan.md` (utilities contract)
- DB schema plan: `context/changes/db-schema-baseline/plan.md` (User model contract)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Backend auth endpoints + tests

#### Automated

- [x] 1.1 New tests pass: `uv run pytest tests/test_auth_flows.py -v` (5/5) — 4c16ac4
- [x] 1.2 Full suite passes: `uv run pytest tests/ -v` (10/10) — 4c16ac4
- [x] 1.3 Router import check: `uv run python -c "from routers.auth import router; print('ok')"` — 4c16ac4

#### Manual

- [x] 1.4 `curl POST /api/auth/register` with new email → 201 with `access_token` — 4c16ac4
- [x] 1.5 `curl POST /api/auth/login` with same credentials → 200 with `access_token` — 4c16ac4
- [x] 1.6 Duplicate register → 409; wrong password → 401 — 4c16ac4
- [x] 1.7 Existing `uv run pytest tests/test_auth.py -v` still passes (regression) — 4c16ac4

### Phase 2: Frontend Redux store + API client

#### Automated

- [x] 2.1 Build passes: `cd frontend && npm run build` — 33e19bf
- [x] 2.2 Lint passes: `cd frontend && npm run lint` — 33e19bf

#### Manual

- [x] 2.3 Redux DevTools shows `auth` slice after app loads — 6a6f917
- [x] 2.4 Page refresh with token in localStorage restores `auth.token` + `auth.user` in DevTools — 6a6f917

### Phase 3: Frontend pages + routing + shell

#### Automated

- [x] 3.1 Build passes: `cd frontend && npm run build` — 6a6f917
- [x] 3.2 Lint passes: `cd frontend && npm run lint` — 6a6f917

#### Manual

- [x] 3.3 Unauthenticated `/` redirects to `/login` — 6a6f917
- [x] 3.4 Register → lands on `/` with `Welcome, {email}` in AppShell — 6a6f917
- [x] 3.5 Page refresh → session persists, no re-login — 6a6f917
- [x] 3.6 Logout → clears token, redirects to `/login` — 6a6f917
- [x] 3.7 Login with valid credentials → lands on `/` — 6a6f917
- [x] 3.8 Duplicate email on `/register` → inline error shown — 6a6f917
- [x] 3.9 Wrong password on `/login` → inline error shown — 6a6f917
- [x] 3.10 `uv run pytest tests/ -v` — all 10 tests pass — 6a6f917
