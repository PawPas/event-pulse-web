# Auth Scaffold Implementation Plan

## Overview

Wire the authentication foundation — password-hashing utilities and a FastAPI Bearer-token dependency — so that every downstream change (S-01 register/login, S-02 report management, …) can protect its routes with a single `Depends(get_current_user)`. No register or login endpoints are added here; those are S-01's job. The sole observable behaviour added by this change is: `GET /api/me` returns 401 without a valid JWT and returns the token payload with a valid one.

## Current State Analysis

The project is a clean slate: `main.py` (8 lines) has `FastAPI()` + `GET /health` only. `pyproject.toml` lists `fastapi>=0.139.0` and `uvicorn>=0.51.0` — no auth packages, no ORM, no tests. There is no `auth/` directory and no `tests/` directory.

## Desired End State

After this plan is complete:

- `auth/` package present at repo root with `security.py`, `schemas.py`, and `dependencies.py`
- `main.py` imports `get_current_user` and exposes `GET /api/me`
- `tests/test_auth.py` passes three HTTP-level checks (valid token → 200, no token → 401, tampered token → 401)
- `pyproject.toml` declares `pyjwt`, `bcrypt` as production deps and `pytest`, `httpx` as dev deps; lock file updated
- `SECRET_KEY` env var documented in `.env.example`; Railway env var is a manual gate for production

### Key Discoveries

- `main.py:1` — `from fastapi import FastAPI` and `app = FastAPI()` already present; no restructuring needed
- `pyproject.toml:8-9` — two deps only; safe to add without conflicts
- `.gitignore` already covers `.env` and `.env.local` (per deploy-plan.md, commit 49d1813)
- No existing tests directory — this plan bootstraps pytest from scratch

## What We're NOT Doing

- No register, login, or logout endpoints (those are auth-flows / S-01)
- No User database model or Postgres connection (that is db-schema-baseline / F-02)
- No refresh tokens or token rotation (out of scope for MVP per PRD)
- No OAuth2 flows, social login, or passwordless (PRD §Access Control, explicit decision)
- No frontend auth UI (S-01)
- No role-based access control (PRD: flat user model)

## Implementation Approach

JWT (HS256) for stateless token validation — no session store needed, pairs cleanly with Railway's env-var secrets, and allows F-01 and F-02 to proceed in parallel. Libraries: `PyJWT` (actively maintained on Python 3.13, no `crypt`-module dependency) and `bcrypt` directly (avoids passlib's Python 3.13 deprecation warnings). `SECRET_KEY` is read lazily inside each function — not at module import time — so tests can inject it via `conftest.py` without import-order issues.

## Critical Implementation Details

**Lazy SECRET_KEY read via `lru_cache`.** `auth/security.py` must NOT assign `SECRET_KEY = os.getenv("SECRET_KEY")` at module level. Instead, define a `@lru_cache(maxsize=1)` function `_secret_key() -> str` that reads `os.getenv("SECRET_KEY")` and raises `RuntimeError` if absent. `lru_cache` means one syscall per process lifetime (idiomatic FastAPI settings pattern). It is safe with our `conftest.py` approach because the env var is set before any test imports `auth.security`, so the first cache fill picks up the test value. Future tests that need a different key must call `_secret_key.cache_clear()` first — add a one-line comment to that effect in the source.

**`tokenUrl` is informational only.** `OAuth2PasswordBearer(tokenUrl="/api/auth/login")` in `auth/dependencies.py` points to S-01's not-yet-existing endpoint. This is intentional: `tokenUrl` only affects the OpenAPI UI's "Authorize" button label — it has no effect on validation. The route does not need to exist for the dependency to work.

**`conftest.py` must set env before imports.** `tests/conftest.py` must place `os.environ.setdefault("SECRET_KEY", "test-secret-key")` before any import that transitively loads `auth.security`. Put it at the very top of the file, before all imports.

---

## Phase 1: Auth utilities package

### Overview

Create the `auth/` package with three modules and install the required production packages. No routes are modified in this phase.

### Changes Required

#### 1. Install production dependencies

**File**: `pyproject.toml`

**Intent**: Add JWT and password-hashing libraries so Phase 1 modules can be imported.

**Contract**: Run `uv add pyjwt>=2.9.0 bcrypt>=4.2.0` — this updates `[project.dependencies]` and regenerates `uv.lock`. Verify no version conflicts with the existing fastapi/uvicorn pins.

#### 2. Token payload schema

**File**: `auth/schemas.py` (new file)

**Intent**: Define the Pydantic model that `get_current_user` returns and that product routes receive as their `current_user` argument. Keeping it as a Pydantic model (not a DB model) lets F-01 and F-02 stay independent.

**Contract**: One model: `TokenPayload(BaseModel)` with fields `sub: str` (the user_id, stored as a string now; S-01 can annotate it as a UUID string once F-02 defines the User table) and `email: str`. No optional fields; both are required in the JWT payload.

#### 3. Hashing and JWT utilities

**File**: `auth/security.py` (new file)

**Intent**: Isolate all cryptography from FastAPI machinery. These four functions are the only place in the codebase that touches the `SECRET_KEY`, bcrypt, or JWT encoding/decoding.

**Contract**: Four exported functions:

- `hash_password(plain: str) -> str` — bcrypt-hash the plaintext password; returns a UTF-8 decoded hash string suitable for storing in Postgres.
- `verify_password(plain: str, hashed: str) -> bool` — constant-time comparison via `bcrypt.checkpw`.
- `create_access_token(subject: str, email: str, expires_delta: timedelta | None = None) -> str` — encode a JWT with `sub`, `email`, and `exp` claims. Default expiry: `ACCESS_TOKEN_EXPIRE_MINUTES` env var (default 30). Uses `datetime.now(timezone.utc)` (not `utcnow()`) to avoid deprecation warnings on Python 3.13.
- `decode_access_token(token: str) -> TokenPayload` — decode and validate the JWT; raises `jwt.InvalidTokenError` on any failure (expired, bad signature, missing claims). Does NOT raise `HTTPException` — that is the dependency's job.

`ALGORITHM = "HS256"` as a module-level constant is fine (not secret). `SECRET_KEY` is accessed via `_secret_key()` — a `@lru_cache(maxsize=1)` function (see Critical Implementation Details above); `create_access_token` and `decode_access_token` call `_secret_key()` internally.

#### 4. FastAPI auth dependency

**File**: `auth/dependencies.py` (new file)

**Intent**: Provide the single importable symbol that all product routes use to require authentication: `Depends(get_current_user)`.

**Contract**: Module-level `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")` (tokenUrl is informational — see Critical Implementation Details). One exported function: `get_current_user(token: str = Depends(oauth2_scheme)) -> TokenPayload`. Catches `jwt.InvalidTokenError` and `KeyError`; raises `HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})`.

#### 5. Package init

**File**: `auth/__init__.py` (new file)

**Intent**: Make `auth/` a Python package so relative imports work.

**Contract**: Empty file.

### Success Criteria

#### Automated Verification

- Import check — auth.security: `uv run python -c "from auth.security import create_access_token, hash_password, verify_password, decode_access_token; print('ok')"`
- Import check — auth.dependencies: `uv run python -c "from auth.dependencies import get_current_user; print('ok')"`
- Import check — auth.schemas: `uv run python -c "from auth.schemas import TokenPayload; print('ok')"`
- Lock file regenerated: `uv.lock` contains `pyjwt` and `bcrypt` entries

#### Manual Verification

- `uv run uvicorn main:app --reload` starts without error (main.py unchanged in this phase)
- `curl http://localhost:8000/health` still returns `{"status": "ok"}`
- Review `auth/security.py` — all four functions present with correct signatures; no `SECRET_KEY` at module level

**Implementation Note**: After this phase passes all automated checks and the manual start/health-check, confirm before proceeding to Phase 2.

---

## Phase 2: Wire stub endpoint and tests

### Overview

Connect the auth dependency to a stub `GET /api/me` route in `main.py`, then add the project's first pytest suite with three HTTP-level tests confirming the 401 behaviour.

### Changes Required

#### 1. Install dev dependencies

**File**: `pyproject.toml`

**Intent**: Add pytest and httpx so `uv run pytest` works. httpx is required by Starlette's TestClient (fastapi>=0.139.0 uses Starlette ≥0.41 which depends on httpx).

**Contract**: Run `uv add --dev pytest>=8.0.0 httpx>=0.28.0` — this writes to `[tool.uv.dev-dependencies]` (or `[dependency-groups]` depending on uv version) and regenerates `uv.lock`.

#### 2. Protected stub route

**File**: `main.py`

**Intent**: Expose `GET /api/me` so the 401 and 200 paths can be verified at the HTTP level without a login endpoint. S-01 will extend this endpoint to also query the database and return a full User response; for now it returns the token payload.

**Contract**: Import `get_current_user` from `auth.dependencies` and `TokenPayload` from `auth.schemas`. Add one route: `@app.get("/api/me")` with `current_user: TokenPayload = Depends(get_current_user)` as the only parameter; return `current_user` directly. No other changes to `main.py`.

#### 3. Test env setup

**File**: `tests/conftest.py` (new file)

**Intent**: Inject a test-only `SECRET_KEY` before any auth module is imported, so tests work without a `.env` file.

**Contract**:
```python
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
```
This must be the first two executable lines in the file (before any other imports). The `setdefault` call means it won't override a real `SECRET_KEY` if one is already set in the environment.

#### 4. Auth tests

**File**: `tests/test_auth.py` (new file)

**Intent**: Three HTTP-level tests that confirm the auth dependency enforces 401 correctly and passes the payload through on a valid token. These are the acceptance tests for this entire foundation.

**Contract**: Use `fastapi.testclient.TestClient(app)` imported from `main`. Call `create_access_token` directly to mint test tokens. Three test functions:

- `test_me_valid_token` — mint a token for `sub="user-123"`, `email="test@example.com"`; `GET /api/me` with `Authorization: Bearer <token>` → assert 200, `json()["sub"] == "user-123"`, `json()["email"] == "test@example.com"`
- `test_me_no_token` — `GET /api/me` with no Authorization header → assert 401
- `test_me_tampered_token` — `GET /api/me` with `Authorization: Bearer not.a.valid.jwt` → assert 401

#### 5. Package init for tests

**File**: `tests/__init__.py` (new file)

**Intent**: Make `tests/` a package so pytest can discover modules correctly.

**Contract**: Empty file.

#### 6. Document SECRET_KEY requirement

**File**: `.env.example` (new file)

**Intent**: Give future developers (and Railway setup documentation) a reference for required env vars.

**Contract**: Two entries: `SECRET_KEY=your-secret-key-here` with a comment showing how to generate a secure value (`python -c "import secrets; print(secrets.token_hex(32))"`), and `ACCESS_TOKEN_EXPIRE_MINUTES=30` (optional, showing the default).

### Success Criteria

#### Automated Verification

- All three tests pass: `uv run pytest tests/test_auth.py -v`
- No import errors: `uv run python -m pytest tests/ --collect-only` shows 3 tests collected

#### Manual Verification

- Start dev server: `uv run uvicorn main:app --reload`
- `curl -s http://localhost:8000/api/me` → HTTP 401 with body `{"detail":"Not authenticated"}`
- Mint a token and use it: `curl -s -H "Authorization: Bearer $(SECRET_KEY=dev uv run python -c 'from auth.security import create_access_token; print(create_access_token("u1","a@b.com"))')" http://localhost:8000/api/me` → HTTP 200 with `{"sub":"u1","email":"a@b.com"}`
- Tampered token: `curl -s -H "Authorization: Bearer bad.token.here" http://localhost:8000/api/me` → HTTP 401
- Health check unaffected: `curl http://localhost:8000/health` → `{"status":"ok"}`

**Implementation Note**: After all tests pass and manual curl checks confirm 401/200 behaviour, this foundation is complete. The Railway `SECRET_KEY` env var (manual gate) must be set before S-01 deploys to production.

---

## Testing Strategy

### Unit Tests

- (Not added in this plan — the three HTTP-level tests in `tests/test_auth.py` cover the dependency end-to-end)
- If `verify_password` / `hash_password` correctness needs its own test, add to `tests/test_auth.py` in S-01 when register uses them

### Integration Tests

- None at this stage (no database)

### Manual Testing Steps

1. Start server with `SECRET_KEY` set: `SECRET_KEY=dev-only uv run uvicorn main:app --reload`
2. `curl http://localhost:8000/api/me` → confirm 401
3. Mint token, curl with it → confirm 200 and payload fields match
4. Use tampered token → confirm 401
5. `curl http://localhost:8000/health` → confirm still 200 (regression check)
6. Open `http://localhost:8000/docs` → confirm `GET /api/me` shows the lock icon and "Authorize" button points to `/api/auth/login`

## Migration Notes

No database changes. No data migration. `SECRET_KEY` must be added to Railway's `event-pulse-api` service env vars before S-01 deploys (S-01 introduces the first real user-creating endpoint). Until then, production `/api/me` will always 401 (no login endpoint exists), which is the correct behaviour.

## References

- Roadmap: `context/foundation/roadmap.md` §F-01
- PRD Access Control: `context/foundation/prd.md` §Access Control
- Deploy plan secrets: `context/deployment/deploy-plan.md` §Secrets wired at deploy time

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Auth utilities package

#### Automated

- [x] 1.1 Import check — auth.security: `uv run python -c "from auth.security import create_access_token, hash_password, verify_password, decode_access_token; print('ok')"` — 9080536
- [x] 1.2 Import check — auth.dependencies: `uv run python -c "from auth.dependencies import get_current_user; print('ok')"` — 9080536
- [x] 1.3 Import check — auth.schemas: `uv run python -c "from auth.schemas import TokenPayload; print('ok')"` — 9080536
- [x] 1.4 Lock file regenerated: `uv.lock` contains `pyjwt` and `bcrypt` entries — 9080536

#### Manual

- [x] 1.5 `uv run uvicorn main:app --reload` starts without error — 9080536
- [x] 1.6 `curl http://localhost:8000/health` returns `{"status":"ok"}` — 9080536
- [x] 1.7 Review `auth/security.py` — four functions present, no `SECRET_KEY` at module level — 9080536

### Phase 2: Wire stub endpoint and tests

#### Automated

- [x] 2.1 All three tests pass: `uv run pytest tests/test_auth.py -v`
- [x] 2.2 Test collection: `uv run python -m pytest tests/ --collect-only` shows 3 tests

#### Manual

- [x] 2.3 `curl -s http://localhost:8000/api/me` → HTTP 401
- [x] 2.4 Valid token curl → HTTP 200 with correct payload
- [x] 2.5 Tampered token curl → HTTP 401
- [x] 2.6 `curl http://localhost:8000/health` still → HTTP 200
