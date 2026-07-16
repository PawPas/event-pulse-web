# First Deploy: EventPulse Web → Railway

## Context

The project has a FastAPI skeleton (`main.py` with `/health` endpoint, no business logic yet) and a bare Vite + React 19 frontend. The goal is to get both deployed to Railway and verify the live `/health` URL responds — establishing that the git-push → deploy loop works before any feature code is added. Postgres is provisioned now so the `DATABASE_URL` is available when auth and data routes land next sprint.

Chosen platform: **Railway** (see `context/foundation/infrastructure.md`). No Dockerfile needed — Railpack auto-detects Python 3.13 and Node.

## Current state at plan time

| File | Status |
|---|---|
| `main.py` | ✓ FastAPI app with `/health` already in place |
| `.python-version` | ✓ `3.13` pinned |
| `pyproject.toml` | ✓ FastAPI + Uvicorn, uv lockfile present |
| `frontend/vite.config.ts` | ✓ `/api` proxy wired (commit 49d1813) |
| `.gitignore` | ✓ node_modules, .env, frontend/dist covered (commit 49d1813) |
| `railway.toml` | ✗ Does not exist (deferred; dashboard is source of truth for first deploy) |
| Railway project | ✗ Not created yet |

## Service architecture

```
Railway Project: event-pulse-web
├── event-pulse-api       Python web service — repo root
│   start: uv run uvicorn main:app --host 0.0.0.0 --port $PORT
├── event-pulse-frontend  Static site — frontend/ subdir
│   build: npm run build  output: dist/
└── event-pulse-db        Railway Postgres add-on
```

In production the frontend calls the API via `VITE_API_URL` (set to the Railway API service URL). In local dev, the Vite proxy forwards `/api` to `localhost:8000`.

Worker service is **not** included in this deploy — no worker code exists yet. It will be added when the RFM analysis background job is implemented.

## Steps

### Manual Gate 1 — Railway account (human)
- [v] Sign up at railway.app; verify email.

### Manual Gate 2 — CLI setup (human)
- [v] Run:
  ```bash
  npm install -g @railway/cli
  railway login
  railway mcp install   # registers Railway MCP tools in Claude Code
  ```

### Step 1 — Fix `.gitignore` ✅ done (commit 49d1813)
Added: `frontend/node_modules/`, `frontend/dist/`, `frontend/.env*`, `.env`, `.env.local`, `.DS_Store`

### Step 2 — Wire Vite dev proxy ✅ done (commit 49d1813)
`frontend/vite.config.ts` now proxies `/api` → `http://localhost:8000` in dev mode.

### Step 3 — Create Railway project (agent + CLI)
- [ ] Run:
  ```bash
  railway init
  # At the prompt: Create new project → name: event-pulse-web
  ```

### Step 4 — Create services and Postgres (human, Railway dashboard)
In the Railway dashboard for the `event-pulse-web` project:

- [ ] **API service** — Add service → Empty service → name: `event-pulse-api`
  - Source: connect GitHub repo, root directory: `/` (repo root)
  - Build command: *(leave blank — Railpack detects uv)*
  - Start command: `uv run uvicorn main:app --host 0.0.0.0 --port $PORT`
  - Env var: `RAILPACK_PYTHON_VERSION = 3.13.2`

- [ ] **Frontend service** — Add service → Empty service → name: `event-pulse-frontend`
  - Source: same GitHub repo, root directory: `frontend/`
  - Build command: `npm run build`
  - Output directory: `dist`
  - Type: Static Site

- [ ] **Postgres** — Add service → Database → PostgreSQL → name: `event-pulse-db`
  - Railway auto-injects `$DATABASE_URL` into the API service

- [ ] **Wire DATABASE_URL** — in `event-pulse-api` service → Variables → add reference variable:
  `DATABASE_URL = ${{event-pulse-db.DATABASE_URL}}`

- [ ] **Set VITE_API_URL** — in `event-pulse-frontend` service → Variables:
  `VITE_API_URL = https://<event-pulse-api-url>.railway.app`
  *(copy the generated domain from event-pulse-api after first deploy)*

### Step 5 — Enable automatic backups on Postgres (human, Railway dashboard)
- [ ] In `event-pulse-db` → Settings → Backups → enable automated backups.
  (Not on by default — see risk register in `context/foundation/infrastructure.md`.)

### Step 6 — Trigger first deploy (agent + git push)
- [ ] Run:
  ```bash
  git push origin main   # triggers Railway autodeploy on both services
  ```

### Step 7 — Verify (agent)
- [ ] Run:
  ```bash
  # Check API health endpoint
  curl https://<event-pulse-api-url>.railway.app/health
  # Expected: {"status":"ok"}

  # Check frontend loads (open in browser)
  open https://<event-pulse-frontend-url>.railway.app

  # Tail API logs
  railway logs --service event-pulse-api
  ```

## Secrets wired at deploy time

| Secret | Service | Source |
|---|---|---|
| `DATABASE_URL` | event-pulse-api | Auto-injected by Railway from event-pulse-db |
| `RAILPACK_PYTHON_VERSION` | event-pulse-api | Set manually: `3.13.2` |
| `VITE_API_URL` | event-pulse-frontend | Set manually: Railway API service URL |

## Verification checklist

- [ ] `curl /health` returns `{"status":"ok"}` with HTTP 200
- [ ] Frontend URL renders the Vite + React default page in browser
- [ ] `railway logs --service event-pulse-api` shows clean uvicorn startup, no errors
- [ ] Railway dashboard shows `event-pulse-db` Postgres service as healthy
- [ ] Postgres backups enabled

## What's next after this deploy

- Implement auth routes (`/api/auth/register`, `/api/auth/login`) — needs `DATABASE_URL` (wired above)
- Add worker service when RFM analysis background job is implemented
- Export Railway service config to `railway.toml` and commit for IaC drift prevention
