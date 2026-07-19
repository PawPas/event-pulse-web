# Database Schema Baseline Implementation Plan

## Overview

Wire SQLAlchemy async engine to Railway Postgres via `DATABASE_URL`, define three ORM models (User, Report, Event) that reflect the PRD's entity requirements, and apply an Alembic initial migration — establishing the data layer that every downstream slice (S-01 through S-05) depends on.

## Current State Analysis

The project has FastAPI + bcrypt/JWT auth utilities but zero database code: no ORM, no models, no migrations, no DB packages in `pyproject.toml` (only fastapi, uvicorn, pyjwt, bcrypt). `DATABASE_URL` is already verified on Railway and injected as an environment variable. The `auth-scaffold` (F-01) stores `sub` (user_id as string) in JWT tokens — the `User.id` UUID this plan defines is what `sub` will reference once S-01 creates user rows.

## Desired End State

After this plan is complete:

- `database.py` at repo root provides `get_db()` FastAPI dependency (async SQLAlchemy session) and `engine_health_check()` utility
- `models/` package defines `User`, `Report` (with `ReportStatus` enum), and `Event` with proper FK relationships and indexes
- `alembic/` directory is configured for async engine; `alembic upgrade head` applies all three tables cleanly
- `GET /api/health/db` returns `{"db": "ok"}` / HTTP 503 on connectivity failure
- `uv run pytest tests/test_db_health.py` passes (health endpoint smoke test via SQLite override)
- Railway deployment: `alembic upgrade head` runs as pre-start command; tables are visible in the Postgres DB

### Key Discoveries

- `pyproject.toml` targets Python 3.13; all chosen packages are compatible (SQLAlchemy 2.x, asyncpg, Alembic 1.14+)
- `auth/security.py` uses `@lru_cache(maxsize=1)` for lazy env-var reads — the same lazy-init pattern is adopted for `database.py`'s engine to avoid import-time connection failures in tests
- PRD §Business Logic fully specifies Event's four required fields: `customer_id` (str), `timestamp` (ISO 8601), `event_type` (str), `amount` (decimal ≥ 0)
- Per-user data isolation (PRD §Access Control NFR) is enforced at the schema level via `reports.user_id FK → users.id` and `events.report_id FK → reports.id` with `ondelete="CASCADE"`
- Alembic async env.py requires a `run_async_migrations()` pattern that is non-obvious but well-documented (see Critical Implementation Details)

## What We're NOT Doing

- No CRUD routes or repository functions — those belong to individual slices (S-01, S-02, etc.)
- No seed data or fixture data — sample data is S-04's responsibility
- No `User` password reset, email verification, or token refresh columns — flat model per PRD §Access Control
- No Alembic branch management — single linear migration history for MVP
- No production CI/CD wiring for Alembic — Railway pre-start command is a manual step in this plan

## Implementation Approach

Three-phase sequencing: (1) install packages and wire the async engine with a health check route — the engine is the only dependency for everything else; (2) define all three ORM models using SQLAlchemy 2.x typed `Mapped[]` syntax so models import cleanly before Alembic autogenerate runs; (3) init Alembic, autogenerate the migration from the model definitions, apply it, and add a pytest smoke test. This order lets each phase be verified independently.

SQLAlchemy declarative base + Alembic (not SQLModel): full control, no abstraction leakage, standard docs alignment. Async engine + asyncpg: non-blocking DB calls required by S-05's 30-second analysis NFR. Engine initialized lazily via module-level sentinel — same pattern as `_secret_key()` in `auth/security.py` — so tests can override `DATABASE_URL` before first access.

## Critical Implementation Details

**Alembic async env.py pattern.** Alembic's `env.py` runs synchronously by default. For an async engine, the `run_migrations_online()` function must use `asyncio.run()` to call an async helper that creates a fresh engine, runs migrations via `conn.run_sync(do_run_migrations)`, then disposes the engine. The key contract:

```python
async def run_async_migrations() -> None:
    url = os.getenv("DATABASE_URL")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())
```

This is the non-obvious part; everything else in env.py is standard Alembic boilerplate.

**ReportStatus as a Postgres native ENUM.** Mapping `ReportStatus` to `SQLAlchemyEnum(ReportStatus)` will cause Alembic autogenerate to emit `CREATE TYPE reportstatus AS ENUM (...)` in the upgrade and `DROP TYPE reportstatus` in the downgrade. This is correct and expected — do not convert to `String` to avoid it.

**UUID primary keys use Python-level default, not `gen_random_uuid()`.** Using `default=uuid.uuid4` (Python-side) instead of `server_default=text("gen_random_uuid()")` keeps models portable across Postgres and the SQLite test engine. Alembic will not emit a `server_default` for these columns.

---

## Phase 1: Async engine + health check route

### Overview

Install DB packages, create `database.py` with lazy engine initialization and a `get_db()` async generator dependency, wire a FastAPI lifespan for startup/shutdown, and add `GET /api/health/db`.

### Changes Required

#### 1. Install production and dev dependencies

**File**: `pyproject.toml`

**Intent**: Add SQLAlchemy async extras, asyncpg driver, and Alembic to production deps; add aiosqlite for async SQLite in tests.

**Contract**: Run:
```
uv add "sqlalchemy[asyncio]>=2.0.0" "asyncpg>=0.30.0" "alembic>=1.14.0"
uv add --dev "aiosqlite>=0.21.0"
```
Confirm `uv.lock` updates. No version conflicts expected with existing packages.

#### 2. Async engine module

**File**: `database.py` (new)

**Intent**: Centralize all engine and session concerns so every route (and test) obtains an `AsyncSession` through a single, overridable `get_db()` dependency.

**Contract**: Three exported symbols:
- `get_db() -> AsyncGenerator[AsyncSession, None]` — async generator yielding one `AsyncSession` per request; suitable for `Depends(get_db)`.
- `engine_health_check() -> bool` — runs `SELECT 1` through the engine; returns `True` on success, `False` on any exception. Used by the health route.
- `close_engine() -> None` (async) — disposes the engine connection pool and resets `_engine_instance` and `_session_factory_instance` to `None`; called on app shutdown. The sentinel reset ensures any post-shutdown call to `_get_engine()` raises a clean `RuntimeError` rather than silently using the disposed engine.

Engine is initialized on first call (lazy sentinel `_engine_instance`). Reading `DATABASE_URL` at call time (not import time) mirrors the `_secret_key()` pattern in `auth/security.py`, preventing import-time failures when tests haven't set the env var yet.

#### 3. Wire lifespan and health route in main.py

**File**: `main.py`

**Intent**: Boot the engine eagerly on startup (so Railway logs show a connection error immediately if `DATABASE_URL` is wrong), dispose it on shutdown, and expose a curl-able health endpoint for Railway post-deploy checks.

**Contract**:
- Import `asynccontextmanager` from `contextlib`; define `lifespan(app: FastAPI)` that calls `_get_engine()` on enter and `await close_engine()` on exit; pass `lifespan=lifespan` to `FastAPI()`.
- Add `GET /api/health/db` route: calls `engine_health_check()`; returns `{"db": "ok"}` with HTTP 200 on success; raises `HTTPException(status_code=503, detail="db unavailable")` on failure.
- Existing `/health` and `/api/me` routes are unchanged.

#### 4. Extend tests/conftest.py with DATABASE_URL sentinel

**File**: `tests/conftest.py`

**Intent**: `TestClient(app)` in `test_auth.py` runs the lifespan context manager synchronously on construction. Without `DATABASE_URL` set, the lifespan's `_get_engine()` call raises `RuntimeError` before any test function executes. Setting a SQLite sentinel here — in the same phase as the lifespan addition — keeps the existing auth tests green.

**Contract**: Add one line immediately after the existing `SECRET_KEY` setdefault:
```python
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
```
The `setdefault` means a real `DATABASE_URL` (e.g., on Railway CI) is never overwritten.

### Success Criteria

#### Automated Verification

- Import check: `uv run python -c "from database import get_db, engine_health_check; print('ok')"`
- Lock file updated: `uv.lock` contains `sqlalchemy`, `asyncpg`, `alembic`, `aiosqlite` entries
- App starts: `uv run python -c "from main import app; print('ok')"` (lifespan import check only — no actual DB call)

#### Manual Verification

- Start server with `DATABASE_URL` set: `DATABASE_URL=<railway-url> uv run uvicorn main:app --reload`
- `curl http://localhost:8000/api/health/db` → `{"db":"ok"}` HTTP 200
- `curl http://localhost:8000/health` → still `{"status":"ok"}` (regression check)
- Existing `uv run pytest tests/test_auth.py` still passes (no regressions)

**Implementation Note**: After automated checks pass and manual verification confirms `/api/health/db` works with a real DATABASE_URL, pause for confirmation before Phase 2.

---

## Phase 2: ORM model definitions

### Overview

Create the `models/` package with four files: a `Base` and common mixin, `User`, `Report` (including `ReportStatus` enum), and `Event` (including the two indexes). No migration is run in this phase — just model import verification.

### Changes Required

#### 1. Package init

**File**: `models/__init__.py` (new)

**Intent**: Make `models/` a Python package; re-export all model classes for convenient imports by Alembic's `env.py`.

**Contract**: Import and re-export `User`, `Report`, `ReportStatus`, and `Event` from their respective submodules.

#### 2. Declarative base

**File**: `models/base.py` (new)

**Intent**: Single `Base = DeclarativeBase()` instance shared by all models; avoid cross-import cycles.

**Contract**: One symbol: `Base`. No other logic.

#### 3. User model

**File**: `models/user.py` (new)

**Intent**: Define the `users` table — the anchor for per-user data isolation. S-01 will insert rows here during register; F-01's JWT `sub` field will carry the string representation of `User.id`.

**Contract**: `User(Base)` mapped to `"users"` with columns:
- `id: Mapped[uuid.UUID]` — primary key, `default=uuid.uuid4` (Python-level)
- `email: Mapped[str]` — `String(255)`, unique, not null
- `hashed_password: Mapped[str]` — `String(255)`, not null (bcrypt output is always 60 chars; 255 gives headroom)
- `created_at: Mapped[datetime]` — `DateTime(timezone=True)`, `server_default=func.now()`
- `updated_at: Mapped[datetime]` — `DateTime(timezone=True)`, `server_default=func.now()`, `onupdate=func.now()`
- `reports: Mapped[list["Report"]]` — relationship with `cascade="all, delete-orphan"`

#### 4. Report model + status enum

**File**: `models/report.py` (new)

**Intent**: Define the `reports` table — the container for a user's analysis run. The `status` column drives the pre-analysis / analyzing / completed / failed state machine that FR-006, FR-010, FR-011, and S-05 all depend on.

**Contract**: `ReportStatus(str, enum.Enum)` with values `created`, `analyzing`, `completed`, `failed`. `Report(Base)` mapped to `"reports"` with columns:
- `id: Mapped[uuid.UUID]` — primary key, `default=uuid.uuid4`
- `user_id: Mapped[uuid.UUID]` — `ForeignKey("users.id", ondelete="CASCADE")`, not null
- `name: Mapped[str]` — `String(255)`, not null
- `description: Mapped[str | None]` — `Text`, nullable
- `status: Mapped[ReportStatus]` — `SQLAlchemyEnum(ReportStatus)`, `default=ReportStatus.created`, not null
- `analyzed_at: Mapped[datetime | None]` — `DateTime(timezone=True)`, nullable
- `created_at / updated_at` — same pattern as User
- `user: Mapped["User"]` — back-reference relationship
- `events: Mapped[list["Event"]]` — relationship with `cascade="all, delete-orphan"`

#### 5. Event model + indexes

**File**: `models/event.py` (new)

**Intent**: Define the `events` table — the raw input to RFM analysis. The composite index `(report_id, customer_id)` covers S-05's `GROUP BY customer_id WHERE report_id = ?` query directly.

**Contract**: `Event(Base)` mapped to `"events"` with `__table_args__` declaring two indexes:
- `Index("idx_events_report_id", "report_id")`
- `Index("idx_events_report_customer", "report_id", "customer_id")`

Columns:
- `id: Mapped[uuid.UUID]` — primary key, `default=uuid.uuid4`
- `report_id: Mapped[uuid.UUID]` — `ForeignKey("reports.id", ondelete="CASCADE")`, not null
- `customer_id: Mapped[str]` — `String(255)`, not null
- `timestamp: Mapped[datetime]` — `DateTime(timezone=True)`, not null (UTC assumed per PRD §Business Logic)
- `event_type: Mapped[str]` — `String(100)`, not null
- `amount: Mapped[Decimal]` — `Numeric(15, 4)`, not null (0.0000 for non-purchase events per PRD)
- `report: Mapped["Report"]` — back-reference relationship

### Success Criteria

#### Automated Verification

- Model import check: `uv run python -c "from models import User, Report, ReportStatus, Event; print('ok')"`

#### Manual Verification

- Review each model file: column types, FK references, cascade rules, index names match the plan
- `ReportStatus` enum has exactly four values: `created`, `analyzing`, `completed`, `failed`
- `Event.amount` uses `Numeric(15, 4)`, not `Float` (exact decimal arithmetic for monetary values)

**Implementation Note**: Phase 2 is purely definitional — no DB write occurs. Confirm model imports are clean before proceeding to Phase 3.

---

## Phase 3: Alembic setup + initial migration + smoke test

### Overview

Initialize Alembic, configure `env.py` for async engine, autogenerate the initial migration from the Phase 2 models, apply it, write a pytest smoke test for `/api/health/db` using aiosqlite, and verify the round-trip (upgrade → downgrade → upgrade).

### Changes Required

#### 1. Initialize Alembic

**File**: `alembic.ini`, `alembic/` directory (new)

**Intent**: Create the Alembic project structure. `alembic.ini`'s `sqlalchemy.url` will be overridden in `env.py` from the `DATABASE_URL` env var — the ini file value is a placeholder.

**Contract**: Run `uv run alembic init alembic`. This creates:
- `alembic.ini` — set `sqlalchemy.url = ` (empty; env.py will supply it)
- `alembic/env.py` — will be replaced in the next step
- `alembic/script.py.mako` — migration template, leave as-is
- `alembic/versions/` — empty directory

#### 2. Configure env.py for async

**File**: `alembic/env.py`

**Intent**: Replace the autogenerated `env.py` with an async-compatible version that (a) imports all models so autogenerate sees their metadata, and (b) uses `asyncio.run()` + `conn.run_sync()` to run migrations through the async engine.

**Contract**: The non-obvious piece is the online migration path (see Critical Implementation Details above). The offline path is standard Alembic. `target_metadata = Base.metadata` must be set so `--autogenerate` can diff against the DB. All four model modules must be imported before `target_metadata` is referenced (not just `Base`) to ensure their table definitions are registered.

```python
# alembic/env.py — async online migration pattern
import asyncio, os
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from models.base import Base
from models import user, report, event  # noqa: F401 — registers tables on Base.metadata

target_metadata = Base.metadata

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

# offline path (standard Alembic, unchanged from template)
def run_migrations_offline() -> None:
    url = os.environ.get("DATABASE_URL")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

#### 3. Generate the initial migration

**File**: `alembic/versions/<hash>_initial_schema.py` (autogenerated)

**Intent**: Produce a migration file that creates `users`, `reports` (with `reportstatus` enum), and `events` tables with all FK constraints and indexes.

**Contract**: Run `DATABASE_URL=<url> uv run alembic revision --autogenerate -m "initial_schema"`. Review the generated file and verify:
- Three `op.create_table()` calls in dependency order: `users` → `reports` → `events`
- `reportstatus` enum is created via `sa.Enum(...)` before the `reports` table
- Both indexes on `events` appear as `op.create_index()` calls
- `downgrade()` drops tables and enum in reverse order

#### 4. Apply the migration

**Intent**: Confirm the migration runs cleanly against Railway Postgres.

**Contract**: `DATABASE_URL=<url> uv run alembic upgrade head` — should complete with no errors. Verify with `uv run alembic current` showing the migration as head.

#### 5. Smoke test for health endpoint

**File**: `tests/test_db_health.py` (new)

**Intent**: Automated coverage that `GET /api/health/db` routes correctly and returns the right shape, using an in-memory SQLite engine (aiosqlite) via `app.dependency_overrides` — no Railway connection required in CI.

**Contract**: Two test functions:
- `test_db_health_ok` — overrides `engine_health_check` with an async function returning `True` via `app.dependency_overrides` or monkeypatching `database.engine_health_check`; hits `GET /api/health/db`; asserts HTTP 200 and `{"db": "ok"}`.
- `test_db_health_fails` — overrides `engine_health_check` with an async function returning `False`; hits `GET /api/health/db`; asserts HTTP 503.

Both tests override `engine_health_check` — the function the health route calls directly. `get_db` is not used by this endpoint and should not be overridden here.

Note: `tests/conftest.py` already sets both `SECRET_KEY` and `DATABASE_URL` sentinels (added in Phase 1 Change 4). No conftest change is needed here.

### Success Criteria

#### Automated Verification

- All tests pass: `uv run pytest tests/ -v` (includes existing test_auth.py + new test_db_health.py)
- Alembic current: `DATABASE_URL=<url> uv run alembic current` shows the initial_schema revision as `(head)`

#### Manual Verification

- Round-trip clean: `DATABASE_URL=<url> uv run alembic downgrade base` succeeds; then `uv run alembic upgrade head` re-applies cleanly
- Tables visible: connect to Railway Postgres (or local) and confirm `users`, `reports`, `events` tables exist with expected columns
- Health endpoint on Railway: `curl https://<railway-api-url>/api/health/db` → `{"db":"ok"}`
- Existing auth tests unaffected: `uv run pytest tests/test_auth.py` still passes

**Implementation Note**: After the round-trip passes and Railway tables are confirmed, this foundation is complete. S-01 (auth-flows) is unblocked and can start immediately.

---

## Testing Strategy

### Unit Tests

- None at this stage — models have no business logic; testing column definitions via import-check + migration autogenerate is sufficient

### Integration Tests

- `test_db_health_ok` / `test_db_health_fails` cover the health route behavior without a real Postgres (aiosqlite override)
- Full Postgres migration round-trip is a manual verification gate

### Manual Testing Steps

1. Apply migration: `DATABASE_URL=<url> uv run alembic upgrade head`
2. Verify tables: inspect DB schema — `users`, `reports`, `events` present with correct column types
3. Health endpoint: `curl http://localhost:8000/api/health/db` → 200 with `{"db":"ok"}`
4. Round-trip: `alembic downgrade base` then `alembic upgrade head` — both clean
5. Auth regression: `uv run pytest tests/test_auth.py` — still 3/3

## Migration Notes

No existing data. The first migration is additive-only. Downgrade is safe as long as no S-01 data exists yet. Once S-01 ships user rows, `downgrade base` would delete them — coordinate any schema changes after S-01 lands carefully.

Railway pre-start command (manual gate): before S-01 deploys to production, update the start command in Railway dashboard → `event-pulse-api` service → Settings → Deploy → Start Command:
```
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```
This ensures migrations run before the server starts on every deploy.

## References

- Roadmap: `context/foundation/roadmap.md` §F-02
- PRD Business Logic (Event schema): `context/foundation/prd.md` §Business Logic
- PRD Access Control (per-user isolation): `context/foundation/prd.md` §Access Control
- Auth scaffold (F-01, for JWT sub → User.id linkage): `context/changes/auth-scaffold/plan.md`
- SQLAlchemy async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Alembic async tutorial: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Async engine + health check route

#### Automated

- [x] 1.1 Import check: `uv run python -c "from database import get_db, engine_health_check; print('ok')"`
- [x] 1.2 Lock file updated: uv.lock contains sqlalchemy, asyncpg, alembic, aiosqlite
- [x] 1.3 App import check: `uv run python -c "from main import app; print('ok')"`

#### Manual

- [x] 1.4 `curl http://localhost:8000/api/health/db` → `{"db":"ok"}` HTTP 200 with DATABASE_URL set
- [x] 1.5 `curl http://localhost:8000/health` → `{"status":"ok"}` (regression)
- [x] 1.6 `uv run pytest tests/test_auth.py` still passes (no regressions from lifespan change)

### Phase 2: ORM model definitions

#### Automated

- [ ] 2.1 Model import check: `uv run python -c "from models import User, Report, ReportStatus, Event; print('ok')"`

#### Manual

- [ ] 2.2 Review User model: id (UUID), email (unique), hashed_password, created_at, updated_at, reports relationship
- [ ] 2.3 Review Report model: id, user_id FK, name, description, status (ReportStatus enum), analyzed_at, timestamps, relationships
- [ ] 2.4 Review Event model: id, report_id FK, customer_id, timestamp, event_type, amount (Numeric 15,4), two indexes

### Phase 3: Alembic setup + initial migration + smoke test

#### Automated

- [ ] 3.1 All tests pass: `uv run pytest tests/ -v` (test_auth.py + test_db_health.py)
- [ ] 3.2 Alembic current: `DATABASE_URL=<url> uv run alembic current` shows initial_schema as (head)

#### Manual

- [ ] 3.3 Round-trip: `alembic downgrade base` then `alembic upgrade head` both succeed
- [ ] 3.4 Tables visible in Postgres: `users`, `reports`, `events` with expected columns
- [ ] 3.5 Health endpoint on Railway: `curl https://<api-url>/api/health/db` → `{"db":"ok"}`
