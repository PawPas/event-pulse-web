# Auth Flows — Plan Brief

> Full plan: `context/changes/auth-flows/plan.md`

## What & Why

S-01 completes the user auth loop: register with email/password, log in, log out. All downstream slices (S-02 reports, S-03 upload, S-05 analysis) depend on a logged-in user existing. Both F-01 (auth utilities) and F-02 (User table) are done — this slice connects them into real endpoints and adds the frontend auth UI.

## Starting Point

FastAPI has `hash_password`, `verify_password`, `create_access_token`, and `get_current_user` ready in `auth/`. The `User` ORM model (email unique, hashed_password, UUID pk) exists and is applied to Railway Postgres. The React frontend is the Vite default template with no router, no state management, and no product pages.

## Desired End State

A visitor can open `/register`, create an account, and land in an authenticated `AppShell` showing their email and a logout button — all in one flow. The token persists in `localStorage` so a page refresh doesn't log them out. `POST /api/auth/login` and a duplicate-email / wrong-password error path are also exercised and tested.

## Key Decisions Made

| Decision | Choice | Why | Source |
|---|---|---|---|
| Token storage | localStorage | Pairs with existing Bearer header scheme; session persists across tabs | Plan |
| Post-register flow | Auto-login (return JWT immediately) | One-step onboarding; no redundant login after register | Plan |
| Frontend scope | Auth pages + shell + protected route guard | Complete auth UX so S-02 can drop in without touching auth | Plan |
| Frontend router | React Router v7 | Most widely adopted; first-class React 19 support | Plan |
| Frontend state | Redux Toolkit | Scales cleanly to S-02–S-05 state; DevTools from day one | Plan |
| Backend test DB | Real SQLite in-memory with `Base.metadata.create_all()` | Exercises ORM queries and uniqueness constraints mocks can't catch | Plan |
| Frontend errors | Inline form error message | Contextual, accessible, no extra library | Plan |
| Logout strategy | Client-side token clear; `POST /logout` returns 200 | JWT is stateless; server-side blacklist excluded from MVP | Plan |

## Scope

**In scope:** `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`; Pydantic request/response schemas; React Router v7; Redux Toolkit auth slice with localStorage hydration; typed API client; Login page, Register page, ProtectedRoute, AppShell, Dashboard placeholder; 5 backend tests with SQLite fixture.

**Out of scope:** Refresh tokens, email verification, password reset, password strength rules, OAuth, server-side token blacklist, `/api/me` DB upgrade, frontend unit tests.

## Architecture / Approach

Backend: a new `routers/auth.py` (`APIRouter(prefix="/api/auth")`) wired into `main.py` via `include_router`. Routes use `get_db()` + SQLAlchemy `select(User)` — no new abstractions. Frontend: Redux `authSlice` holds `{ token, user }`, hydrated from `localStorage` on slice init. An `apiFetch` utility reads the token from `localStorage` directly (not the Redux store) to avoid circular imports. Pages dispatch `loginSuccess` / `logout` actions which update both Redux state and `localStorage` in tandem.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Backend endpoints + tests | Register, login, logout routes; 5 tests pass against SQLite | `asyncio.run()` + module-scoped fixture pattern must not conflict with other test files |
| 2. Redux store + API client | Store wired, auth slice with localStorage hydration, typed hooks, apiFetch utility | Initial state hydration from `localStorage` must handle `null` gracefully |
| 3. Frontend pages + routing + shell | Login + Register forms, ProtectedRoute, AppShell, Dashboard placeholder | oxlint rules-of-hooks must pass; `npm run build` catches TS type errors |

**Prerequisites:** F-01 (`auth-scaffold`) and F-02 (`db-schema-baseline`) both implemented.
**Estimated effort:** ~2 sessions across 3 phases.

## Open Risks & Assumptions

- `asyncio.run()` inside a synchronous `pytest.fixture(scope="module")` should work with the existing test setup (no `pytest-anyio` detected) — if it conflicts, the fallback is `pytest-anyio` + async fixtures.
- oxlint version `1.71.0` — confirm `react/rules-of-hooks` plugin covers the hook usage patterns in the new pages before committing frontend code.

## Success Criteria (Summary)

- `uv run pytest tests/ -v` passes 10/10 (5 prior + 5 new)
- `cd frontend && npm run build && npm run lint` both exit 0
- Manual end-to-end: register → session persists on refresh → logout → login → inline errors work
