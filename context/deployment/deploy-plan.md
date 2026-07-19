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

### Step 3 — Create Railway project (agent + CLI) ✅ done
- [x] Run:
  ```bash
  railway init
  # At the prompt: Create new project → name: event-pulse-web
  ```

### Step 4 — Create services and Postgres ✅ done
All three services deployed successfully on 2026-07-16.

- [x] **API service** — `event-pulse-api`
  - Source: PawPas/event-pulse-web, root directory: `/`
  - Start command: `uv run uvicorn main:app --host 0.0.0.0 --port $PORT`
  - Env var: `RAILPACK_PYTHON_VERSION = 3.13.2`
  - Public URL: `https://event-pulse-api-production.up.railway.app`

- [x] **Frontend service** — `event-pulse-frontend`
  - Source: PawPas/event-pulse-web, root directory: `/frontend`
  - Build command: `npm run build` (Railpack auto-detected)
  - Public URL: `https://event-pulse-frontend-production.up.railway.app`

- [x] **Postgres** — `event-pulse-db` (Railway managed PostgreSQL)

- [x] **Wire DATABASE_URL** — reference variable set on `event-pulse-api`:
  `DATABASE_URL = ${{event-pulse-db.DATABASE_URL}}`
  ⚠️ MCP list_variables shows `DATABASE_URL=` as empty — verify in dashboard that the reference expands correctly before adding DB routes.

- [x] **Set VITE_API_URL** — set on `event-pulse-frontend`:
  `VITE_API_URL = https://event-pulse-api-production.up.railway.app`
  *(Fixed 2026-07-17: was missing `https://` prefix — frontend redeployed with corrected value)*

### Step 5 — Postgres backups ⚠️ not available on Hobby plan
Automatic backups require the Pro plan ($20/month). On Hobby, Postgres has no managed backup.

Workaround for MVP: schedule a manual `pg_dump` via a cron job or Railway's one-off jobs once the schema stabilises. Until then, the database holds no production data so the risk is low.

Upgrade path: Railway dashboard → Settings → Plan → Pro, then `event-pulse-db` → Backups.

### Step 6 — Trigger first deploy (agent + git push) ✅ done
- [x] Run:
  ```bash
  git push origin main   # triggers Railway autodeploy on both services
  ```

### Step 7 — Verify ✅ done (2026-07-17)
- [x] Run:
  ```bash
  # Check API health endpoint
  curl https://event-pulse-api-production.up.railway.app/health
  # Result: {"status":"ok"} — HTTP 200 ✅

  # Check frontend loads (open in browser)
  open https://event-pulse-frontend-production.up.railway.app

  # Tail API logs
  railway logs --service event-pulse-api
  ```

## Secrets wired at deploy time

| Secret | Service | Source | Status |
|---|---|---|---|
| `DATABASE_URL` | event-pulse-api | Reference var → event-pulse-db | ⚠️ Verify in dashboard |
| `RAILPACK_PYTHON_VERSION` | event-pulse-api | Set manually: `3.13.2` | ✅ |
| `VITE_API_URL` | event-pulse-frontend | `https://event-pulse-api-production.up.railway.app` | ✅ Fixed 2026-07-17 |

## Live URLs

| Service | URL |
|---|---|
| API | `https://event-pulse-api-production.up.railway.app` |
| Frontend | `https://event-pulse-frontend-production.up.railway.app` |
| API Docs | `https://event-pulse-api-production.up.railway.app/docs` |

## Verification checklist

- [x] `curl /health` returns `{"status":"ok"}` with HTTP 200 — confirmed 2026-07-17
- [x] Frontend URL renders the Vite + React default page in browser — confirmed 2026-07-17 (redeployed with corrected VITE_API_URL)
- [ ] `railway logs --service event-pulse-api` shows clean uvicorn startup, no errors
- [x] Railway dashboard shows all 3 services (API, frontend, Postgres) as SUCCESS
- [ ] Postgres backups enabled — not available on Hobby plan (see Step 5)
- [ ] `DATABASE_URL` reference variable verified in dashboard to expand correctly

## What's next after this deploy

- Verify `DATABASE_URL` expands correctly in Railway dashboard before adding any DB routes
- Implement auth routes (`/api/auth/register`, `/api/auth/login`) — needs `DATABASE_URL` (wired above)
- Add worker service when RFM analysis background job is implemented
- Export Railway service config to `railway.toml` and commit for IaC drift prevention
