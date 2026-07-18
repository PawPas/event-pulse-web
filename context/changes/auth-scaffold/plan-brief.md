# Auth Scaffold — Plan Brief

> Full plan: `context/changes/auth-scaffold/plan.md`

## What & Why

Wire the authentication foundation so every downstream route can become protected with `Depends(get_current_user)`. This is roadmap item F-01 — the narrowest enabler for S-01 (register/login) and all subsequent slices. Without this foundation, no product route can enforce the PRD's guardrail ("no user's data visible to any other account").

## Starting Point

`main.py` is 8 lines: `FastAPI()` + `GET /health`. `pyproject.toml` has two packages (fastapi + uvicorn). No auth code, no tests, no directory structure beyond repo root.

## Desired End State

An `auth/` package at repo root provides `get_current_user` — a FastAPI dependency that validates a Bearer JWT and returns a `TokenPayload`. `GET /api/me` uses it as a stub. Three pytest tests confirm: valid token → 200, no token → 401, tampered token → 401. `SECRET_KEY` env var is documented and required.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Token type | JWT (HS256) | Stateless — no session store needed; F-01 and F-02 can proceed in parallel | Plan |
| JWT library | PyJWT ≥ 2.9.0 | More actively maintained than python-jose; no Python 3.13 `crypt`-module issues | Plan |
| Password hashing | bcrypt directly (not passlib) | Avoids passlib's deprecation warnings on Python 3.13 | Plan |
| Project structure | `auth/` package at repo root | Isolated, easy for S-01 to extend; no app/ restructure needed | Plan |
| Verification | `GET /api/me` stub | Makes 401/200 verifiable at HTTP level before S-01 ships | Plan |
| Testing | pytest + httpx + 3 HTTP tests | Bootstraps test baseline for all future slices | Plan |
| SECRET_KEY | `@lru_cache` lazy read, fail-fast if missing | One syscall per process (idiomatic settings pattern); conftest.py sets env before first import so cache fills correctly | Plan |

## Scope

**In scope:**
- `auth/schemas.py` — `TokenPayload` Pydantic model
- `auth/security.py` — `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`
- `auth/dependencies.py` — `get_current_user` FastAPI dependency
- `main.py` — add `GET /api/me` stub route
- `tests/` — conftest.py + test_auth.py (3 tests)
- `.env.example` — document SECRET_KEY requirement
- `pyproject.toml` — add pyjwt, bcrypt, pytest, httpx

**Out of scope:**
- Register, login, logout endpoints (auth-flows / S-01)
- User database model (db-schema-baseline / F-02)
- Refresh tokens or token rotation
- Frontend auth UI
- Railway SECRET_KEY env var (manual gate — must be set before S-01 deploys)

## Architecture / Approach

```
main.py
  └── GET /api/me  ──→  Depends(get_current_user)
                              │
                        auth/dependencies.py
                              │  extracts Bearer token
                              │  calls decode_access_token()
                              ▼
                        auth/security.py
                              │  PyJWT decode + bcrypt utilities
                              ▼
                        auth/schemas.py
                              TokenPayload(sub, email)
```

`SECRET_KEY` flows in from `os.getenv("SECRET_KEY")` at call time (lazy). Tests inject it via `tests/conftest.py` before imports.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Auth utilities package | `auth/` package importable; pyjwt + bcrypt installed | Import fails if SECRET_KEY read at module level (use lazy read) |
| 2. Wire stub + tests | `GET /api/me` live; 3 pytest tests green | conftest.py must set SECRET_KEY before auth.security import |

**Prerequisites:** `DATABASE_URL` verified (for F-02 parallelism, not needed here); Railway CLI authenticated (to set SECRET_KEY env var before S-01 deploys)

**Estimated effort:** ~1 session, 2 phases (utilities first, then wire + test)

## Open Risks & Assumptions

- Railway's `SECRET_KEY` env var must be set manually before S-01 can deploy to production. This plan only adds it to `.env.example`.
- S-01 will extend `GET /api/me` to also query the database (verify user still exists). The current stub returns token payload only — acceptable for F-01.
- `bcrypt` package version ≥ 4.2.0 required for Python 3.13 compatibility (earlier versions have ABI issues on some platforms).

## Success Criteria (Summary)

- `uv run pytest tests/test_auth.py -v` exits 0 with all 3 tests passing
- `curl http://localhost:8000/api/me` → 401 (no token)
- `curl -H "Authorization: Bearer <valid_token>" http://localhost:8000/api/me` → 200 with `{sub, email}`
