# EventPulse Web

EventPulse Web turns raw customer event exports (CSV/JSON) into an actionable RFM
segmentation report in minutes. It targets small e-commerce and SaaS teams that
have event data — product views, purchases, logins — but no data team or budget
for enterprise analytics platforms. Upload a file (or generate sample data),
run the analysis, and see which customers are Champions, Loyal, At Risk, or
Hibernating.

Full product context lives in [`context/foundation/`](context/foundation/) —
start with [`prd.md`](context/foundation/prd.md) (problem, scope, business
rules) and [`roadmap.md`](context/foundation/roadmap.md).

## Tech stack

- **Backend**: FastAPI + Python 3.13, SQLAlchemy (async) + Alembic, PostgreSQL, JWT auth. Deps managed by [`uv`](https://docs.astral.sh/uv/).
- **Frontend**: Vite + React 19 + TypeScript SPA under [`frontend/`](frontend/), Redux Toolkit state.

## Getting started

Backend (repo root):

```bash
uv sync                                 # install dependencies
uv run alembic upgrade head             # apply DB migrations
uv run uvicorn main:app --reload        # dev server at http://localhost:8000
```

Frontend (from `frontend/`):

```bash
npm install
npm run dev                             # Vite dev server at http://localhost:5173
```

The Vite dev server proxies `/api` requests to the backend on port 8000.

## Key endpoints

| Area | Endpoints |
| --- | --- |
| Auth | `POST /api/auth/register`, `/login`, `/logout` |
| Reports | `POST/GET/PATCH/DELETE /api/reports` — CRUD, scoped to the logged-in user |
| Events | `POST /api/reports/{id}/events/upload` (CSV/JSON), `POST .../events/sample` generator |
| Analysis | `POST /api/reports/{id}/analysis/run` — runs RFM scoring, `GET .../analysis/results` |

RFM scoring and segment assignment live in [`services/rfm.py`](services/rfm.py).

## Testing

```bash
uv run pytest                           # backend suite (API, auth, RFM algorithm)
cd frontend && npm test                 # frontend Vitest suite
```

## Repository layout

- `main.py`, `routers/`, `services/`, `models/`, `auth/` — FastAPI backend
- `alembic/` — database migrations
- `tests/` — backend pytest suite
- `frontend/` — React SPA
- `context/` — planning artifacts (PRD, roadmap, tech stack, change history); do not edit
