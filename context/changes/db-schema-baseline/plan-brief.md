# Database Schema Baseline — Plan Brief

> Full plan: `context/changes/db-schema-baseline/plan.md`

## What & Why

Wire SQLAlchemy async engine to Railway Postgres and define the three ORM models that every product slice depends on. This is the pure-data-layer foundation — no CRUD routes, no seed data. Without it, S-01 (User table), S-02 (Report table), and S-03/S-04/S-05 (Event table) cannot be planned.

## Starting Point

The project has FastAPI + bcrypt/JWT auth (F-01 complete) but zero database code. `pyproject.toml` has no ORM or migration packages. `DATABASE_URL` is already verified on Railway and injected as an environment variable.

## Desired End State

Three tables (`users`, `reports`, `events`) exist in Railway Postgres after `alembic upgrade head`. The app exposes `GET /api/health/db` that returns `{"db":"ok"}`. All downstream slices can import `models.User`, `models.Report`, and `models.Event` to define their routes.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| ORM library | SQLAlchemy declarative + Alembic | Full control, standard docs, no abstraction leakage vs SQLModel | Plan |
| Engine mode | Async (asyncpg) | Non-blocking DB calls required for S-05's 30s analysis NFR | Plan |
| Engine init timing | Lazy (module-level sentinel) | Mirrors `_secret_key()` pattern — prevents import-time failures in tests | Plan |
| Report table scope | Include `status` enum + `analyzed_at` now | S-02 and S-05 both depend on this state machine; avoids an additive migration on first day | Plan |
| Event indexes | `(report_id)` + `(report_id, customer_id)` composite | Covers S-05's `GROUP BY customer_id WHERE report_id = ?` without full table scan | Plan |
| Session DI | `get_db()` async generator + lifespan engine | FastAPI-idiomatic; trivially overridable in tests via `dependency_overrides` | Plan |
| Health check | `GET /api/health/db` → 200 / 503 | Roadmap requires "engine health verified in Railway logs"; curl-able endpoint makes that trivial | Plan |
| Testing | pytest + aiosqlite override for health route; Alembic round-trip is manual | No Postgres in CI yet; aiosqlite covers routing correctness; round-trip needs real DB | Plan |

## Scope

**In scope:**
- `database.py`: engine, `get_db()`, `engine_health_check()`, `close_engine()`
- `models/`: `Base`, `User`, `Report` + `ReportStatus`, `Event` (with indexes)
- `alembic/`: init + async `env.py` + initial migration
- `main.py`: lifespan event + `GET /api/health/db`
- `tests/test_db_health.py`: 2 tests (ok + failure case)

**Out of scope:**
- Any CRUD routes or repository layer (those are S-01 through S-05)
- Seed or fixture data (S-04 sample generator)
- CI/CD Alembic wiring (Railway pre-start command is a manual gate)
- Password reset, email verification columns (PRD flat model)

## Architecture / Approach

```
main.py (lifespan) ──▶ database.py (engine, get_db)
                              │
                              ▼
                       models/ (User, Report, Event)
                              │
                              ▼
                       alembic/ (env.py → migrations)
                              │
                              ▼
                       Railway Postgres (DATABASE_URL)
```

FastAPI routes call `Depends(get_db)` to get an `AsyncSession`. `alembic upgrade head` is run before starting the server. Test routes override `get_db` with an in-memory aiosqlite session.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Async engine + health check | `database.py`, lifespan, `GET /api/health/db` working | `DATABASE_URL` parsing error on Railway — caught by health endpoint |
| 2. ORM model definitions | `models/` package importable; autogenerate-ready | `ReportStatus` enum leaking into migration incorrectly |
| 3. Alembic + migration + smoke test | Tables in Postgres; pytest green; Railway confirmed | Alembic async env.py async/sync mismatch (see Critical Details in plan) |

**Prerequisites:** `DATABASE_URL` env var set (Railway, already verified). Python 3.13, uv.
**Estimated effort:** ~1 session (3 phases, mostly tooling setup + schema definition)

## Open Risks & Assumptions

- aiosqlite doesn't support all Postgres-specific types (`Numeric`, `DateTime(timezone=True)`) identically — the smoke test verifies routing behavior only; full schema correctness is validated by the manual Alembic round-trip against real Postgres
- `ReportStatus` Alembic autogenerate behavior: Alembic should emit `CREATE TYPE` for the Python enum; review the generated migration before applying

## Success Criteria (Summary)

- `uv run pytest tests/` passes (test_auth.py + test_db_health.py)
- `alembic upgrade head` + round-trip (`downgrade base` → `upgrade head`) succeed against real Postgres
- `curl https://<railway-api>/api/health/db` returns `{"db":"ok"}`
