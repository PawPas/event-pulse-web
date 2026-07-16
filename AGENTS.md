# Repository Guidelines

EventPulse Web is an RFM customer-segmentation tool: a FastAPI + Python 3.13 backend at the repo root paired with a Vite + React 19 TypeScript SPA under `frontend/`.

## Hard Rules

- Never modify anything under `context/`. It is the planning artifact store (PRD, tech-stack, shape-notes); editing it breaks the chain trail.
- `main.py` is a scaffold placeholder (`print("Hello from projekt10devs!")`). Replace it with `app = FastAPI()` and a `/health` stub before adding any routes.
- All FastAPI request/response shapes must use Pydantic v2 models — no plain `dict` at API boundaries.
- Run `cd frontend && npm run lint` before committing any frontend change. oxlint enforces `react/rules-of-hooks: error` — CI will enforce it once wired.

## Project Structure

- `main.py` — FastAPI app entry point (placeholder; replace before adding routes)
- `pyproject.toml` / `uv.lock` — Python deps managed by `uv`; see `@pyproject.toml`
- `frontend/` — Vite + React 19 + TypeScript SPA; see `@frontend/package.json`

## Build, Test, and Dev Commands

Backend (run from repo root):
- `uv run uvicorn main:app --reload` — dev server at `http://localhost:8000`
- `uv add <package>` — add a dependency

Frontend (run from `frontend/`):
- `npm run dev` — Vite dev server at `http://localhost:5173`
- `npm run lint` — run oxlint
- `npm run build` — type-check then bundle

## Coding Style & Naming Conventions

- Python: type-annotate all function signatures.
- TypeScript: strict mode per `@frontend/tsconfig.app.json`; named exports for components and utilities.
- Lint config: `@frontend/.oxlintrc.json` (React + TypeScript plugins, hooks-rules as error).

## Testing Guidelines

No test runner configured on either side yet. When adding tests:
- Backend: `uv add --dev pytest`
- Frontend: `npm install --save-dev vitest @testing-library/react`

## Architecture Overview

- FastAPI backend owns all RFM computation; target API path: `/api/*`.
- React SPA is display-only; wire the Vite dev proxy (`server.proxy` in `@frontend/vite.config.ts`) to forward `/api` requests to `localhost:8000` during development.
- Event schema, RFM scoring rules, and segment boundary conditions are fully specified in `@context/foundation/prd.md` § Business Logic — read before touching ingestion or analysis code.
