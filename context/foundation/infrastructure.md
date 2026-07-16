---
project: EventPulse Web
researched_at: 2026-07-15
recommended_platform: Railway
runner_up: Render
context_type: mvp
tech_stack:
  language: Python 3.13
  framework: FastAPI
  runtime: uvicorn
  database: PostgreSQL (managed)
  background_jobs: true
  frontend: Vite + React 19 (static SPA)
---

## Recommendation

**Deploy on Railway.**

Railway was initially scored as runner-up behind Render on the five agent-friendly criteria (one gap: no `llms.txt`). After a structured predictability comparison across six common operational scenarios, Railway outperformed Render on five of six — rollback behaviour, second-worker disk access, env var propagation, worker sleep transparency, and platform mental model. The single criteria gap (docs not in markdown) is a real limitation for autonomous agent doc-fetching, but it is outweighed by Railway's more predictable runtime behaviour for a solo developer iterating fast on a 3-week MVP.

Railway runs FastAPI on Python 3.13.2 by default via Railpack (no Dockerfile required), treats multi-service projects as first-class citizens (API + worker + Postgres + Redis in one project), and exposes a GA local MCP server via `railway mcp install` plus a dedicated `railway agent` CLI command. The Hobby plan at $5/month covers the full MVP stack within the included credit.

Note: Cassandra + Spark were considered and rejected during this research session. The PRD's scale (≤200k events, low QPS, 3-week MVP) is well within what Pandas + Postgres handles in-process. Dropping JVM workloads eliminates the memory contention and operational complexity that would have pushed the platform choice toward a raw VPS.

## Platform Comparison

| Platform | CLI-first | Managed/Serverless | Agent docs | Stable deploy API | MCP/Integration | Notes |
|---|---|---|---|---|---|---|
| **Railway** | Pass | Pass | Fail | Pass | Pass | No llms.txt; GA local MCP + `railway agent`; most predictable runtime |
| Render | Pass | Pass | Pass | Pass | Pass | GA hosted MCP; llms.txt GA; rollback/autodeploy race is a known trap |
| Fly.io | Pass | Pass | Pass | Partial | Partial | No `fly rollback`; free tier gone; Postgres $38/month |
| DigitalOcean | Pass | Partial | Pass | Pass | Partial | App Platform partial; MCP is labs/beta |
| Hetzner | Partial | Fail | Partial | Partial | Fail | Raw VMs; SSH-only deploys; no deploy API |

Hard filters applied: Netlify and Vercel (serverless-only) dropped before scoring — the app requires persistent background workers. All five researched platforms passed the persistent-process filter.

Interview weights applied: DX prioritised (Q2) → penalises Hetzner's operational overhead. Single region (Q4) → no edge advantage weighting. External providers acceptable (Q5) → co-location score neutral.

### Shortlisted Platforms

#### 1. Railway (Recommended)

4/5 on agent-friendly criteria (docs gap: no `llms.txt`). Python 3.13.2 is the default runtime via Railpack — no Dockerfile required. Multi-service projects with API, worker, Postgres, and Redis are first-class citizens; services share private networking via `.railway.internal` hostnames and reference each other's env vars directly. Hobby plan at $5/month includes $5 credit, covering ~3 small services within budget. GA local MCP installed via `railway mcp install` (no separate auth step beyond CLI login); `railway agent` CLI command for AI-driven terminal workflows. Chosen over Render because of superior predictability across rollback, second-worker scaling, env var propagation, and platform mental model — see predictability comparison below.

#### 2. Render

5/5 on agent-friendly criteria. Python 3.13.4 native, `llms.txt` GA, hosted GA MCP server (`mcp.render.com`) plus three Claude Code skills. The fuller agent-friendly score is real — Render's hosted MCP requires no local CLI install, and its docs are fetchable by agents directly. Runner-up because of three predictability traps that surface at MVP velocity: rollback is immediately overwritten by a queued CI deploy unless autodeploy is manually paused first; a second worker instance cannot access Render Disks (files must go to external storage from day 1); and env var changes sometimes require a manual restart. These are manageable with documented SOPs, but they add operational overhead a solo developer on a 3-week timeline does not want.

#### 3. Hetzner + Docker Compose

Lowest agent-friendly score but cheapest option at ~€6.49/month (CX33, 8GB RAM). Matches the user's original stated preference (cheap VPS + docker-compose). Dropped to third after anti-bias cross-check surfaced: no application deployment API (SSH-only), Docker+UFW iptables bypass exposes ports, no zero-downtime deploy mechanism, and no managed Postgres (requires self-hosted or third-party). The cross-check also clarified that Cassandra + Spark (the original data layer preference) does not make sense at MVP scale — and without that JVM requirement, a managed PaaS is objectively lower-friction.

## Predictability Comparison: Railway vs Render

Predictability was the deciding factor in swapping the recommendation. The five agent-friendly criteria score platform capability; this table scores platform behaviour under routine operational events a solo developer will encounter in weeks 1–6.

| Scenario | Railway | Render | More predictable |
|---|---|---|---|
| Run a second worker instance | Works normally — second worker is a separate service with its own filesystem | Second worker cannot access the Render Disk attached to the first instance; files are invisible | Railway |
| Rollback a bad deploy | `railway redeploy` reverts cleanly; no race with autodeploy | `render deploys create --rollback` can be overwritten by a queued CI deploy within seconds | Railway |
| Change Python patch version | Railpack build may fail (no precompiled binary); error is explicit and fixable | Usually works on native runtime; switching runtime type (native→Docker) requires a new service | Railway (slightly) |
| Add or update an env var | Takes effect on all services immediately; no restart required | Sometimes requires a manual service restart to propagate | Railway |
| Worker stops receiving tasks | Visible in logs; sleep mode is opt-in and clearly labelled | Sleep mode can be accidentally enabled per-service; tasks are silently dropped without a clear error | Railway |
| Understand how the platform works | Behaves like containers + internal network — maps to what developers already know | Has platform-specific rules (disk attachment, service types, runtime variants) that require Render-specific knowledge | Railway |

## Anti-Bias Cross-Check: Railway (Recommended)

### Devil's Advocate — Weaknesses

1. **No `llms.txt` and docs are HTML-only.** Railway's primary docs at `docs.railway.com` are not GitHub-hosted markdown and publish no `llms.txt`. An agent cannot fetch docs directly — it falls back to training-data knowledge of Railway's CLI, which drifts as Railway evolves (the Nixpacks → Railpack transition is a recent example where outdated training data produces wrong build commands).

2. **Railpack precompiled Python binary constraint.** If a precompiled binary is unavailable for the exact Python patch version in `.python-version`, the build fails with a cryptic error. The workaround (`MISE_PYTHON_COMPILE=1`) makes builds 5–8 minutes long instead of ~2 minutes. Silently bumping the patch version (e.g., `.python-version: 3.13.3`) can break CI without an obvious explanation.

3. **No atomic multi-service deploy.** Railway deploys each service independently in sequence. If the API and worker both ship a breaking schema change in the same commit, there is a 60–90 second window where the new API enqueues tasks the old worker doesn't understand — or vice versa. Silent data loss, not a recoverable error.

4. **Remote MCP (`mcp.railway.com`) is explicitly "work in progress."** The hosted MCP endpoint is marked WIP in Railway's own docs. The GA path is the local MCP installed via `railway mcp install`, which requires the CLI to be authenticated on the agent's machine — tighter coupling than Render's hosted, token-based MCP endpoint.

5. **Sleep mode is opt-in but easy to trigger accidentally per-service.** Serverless (sleep) mode activates after 10 minutes of no outbound packets and returns 502 on cold start. While off by default on paid plans, it can be enabled per-service in the dashboard. A sleeping background worker silently drops in-flight queue tasks with no error visible to the user.

### Pre-mortem — How This Could Fail

The team deployed EventPulse Web to Railway in July 2026 on the Hobby plan. Six months later, three compounding issues had become recurring incidents.

The first: week 3, the developer bumped `.python-version` from 3.13.2 to 3.13.3 after a security patch announcement. The Railpack build failed — no precompiled binary available for 3.13.3. The error message was not obvious; the fix (`MISE_PYTHON_COMPILE=1`) tripled build times. The developer added the env var and never revisited it. Every subsequent deploy took 8 minutes, making the "fast iteration" promise hollow.

The second: in October, the team shipped a schema change to the RFM analysis job payload simultaneously to the API and the worker. Railway deployed the API first, then the worker 90 seconds later. During that window, the new API was enqueuing tasks with a new `analysis_version` field; the old worker did not recognise the field and silently discarded 47 jobs. There was no deploy hook to hold the API until the worker was ready.

The third: the developer attempted to use the Railway remote MCP to let the agent query deployment status and stream logs. The `mcp.railway.com` endpoint — marked "work in progress" in the docs — returned malformed JSON on roughly 30% of calls. The team fell back to CLI-based monitoring, which was reliable but required a terminal session to stay open. The MCP story that had been a selling point delivered nothing in practice.

The assumption that aged worst: "best MCP story" meant production-ready MCP. The local MCP is solid; the remote MCP is an experiment. For an agent operating autonomously, there is a meaningful gap between the two.

### Unknown Unknowns

1. **Hobby plan credit covers ~3 small services, but any RAM spike overruns it.** Usage is billed at $10/GB-RAM/month and $20/vCPU/month against the $5 included monthly credit. A 200k-event RFM analysis that spikes the worker to 512MB RAM is cheap per-run — but a memory leak or repeated analysis load can push the total over the included credit for that billing cycle with no proactive warning.

2. **Railway Postgres is a container, not a managed database service.** It runs as a Docker container on Railway's infrastructure. Automatic backups are not enabled by default — they must be configured explicitly in the service settings. Point-in-time recovery is available only on Pro plans. An unexamined Postgres service on Hobby has no automated backup and no PITR.

3. **Services communicate via `.railway.internal` hostnames, not `localhost`.** If `DATABASE_URL` or `REDIS_URL` is hardcoded to `localhost`, the worker cannot reach Postgres or Redis in production — they are separate Railway services. The correct pattern is Railway's auto-injected `$DATABASE_URL` / `$REDIS_URL` env vars. This works locally but breaks silently after deploy if hardcoded.

4. **`railway up` deploys the local working directory, including uncommitted changes.** The default deploy command packages whatever is on disk — not the last git commit. Uncommitted debug flags, local `.env` overrides, or work-in-progress files ship to production if the developer runs `railway up` with a dirty working tree. The production-safe path is connecting Railway to a GitHub repo and triggering deploys via git push.

## Anti-Bias Cross-Check: Render (Runner-Up)

### Devil's Advocate — Weaknesses

1. **Rollback is not atomic with autodeploy.** `render deploys create --rollback` reverts the running version but does NOT pause autodeploys. If CI has a queued deploy, the rollback lasts seconds before the broken version re-deploys. The CLI reports success; the state is immediately overwritten. Fixing this requires an additional step: disable autodeploy before rolling back, then re-enable — a two-step operation with no atomic CLI path.

2. **Free Postgres self-destructs after 30 days.** No warning, no recovery path. Prototyping on the free database tier ends in silent data loss at day 31. An agent that provisions the free DB during early development will lose all schema and analysis results without notice.

3. **Every persistent service is billed separately.** FastAPI web ($7) + background worker ($7) + Redis ($10) + Postgres ($6) = $30/month minimum on Starter tiers. Adding a second worker replica doubles worker cost. There is no flat "app" rate — each long-running process is an independent line item.

4. **Persistent disks are single-instance only.** A Render Disk attaches to exactly one service instance. If the web service is ever scaled to 2+ instances, the second instance has no disk access. File uploads (CSV/JSON event files) must target external object storage (R2, S3) from day one — the Disk path breaks at scale.

5. **Env var changes sometimes require a manual service restart.** Unlike Railway where env var updates propagate immediately, Render services may need a manual redeploy to pick up new environment variable values. This breaks the expected "set and it applies" mental model.

### Pre-mortem — How This Could Fail

The team deployed EventPulse Web to Render in July 2026. Six months later, three compounding mistakes had turned the infrastructure into a recurring operational headache.

The first incident: demo day, week 5. The free Postgres database silently expired 31 days after creation. The connection string returned errors with no explanation in the dashboard; all analysis results were gone. The team had not read the free-tier fine print. Rebuilding on paid tiers added $37/month — tolerable, but the incident created distrust of platform defaults.

The second: a bad background worker deploy in November caused analysis jobs to silently eat tasks and return no results. The team rolled back via `render deploys create --rollback`. The CLI confirmed success. CI re-deployed the broken version 40 seconds later. Two hours of debugging before someone noticed the autodeploy timestamp. The fix — temporarily disabling autodeploy from the dashboard — was a manual step with no atomic CLI equivalent.

The third, and most structural: by month 6, the worker service had been scaled to 2 instances to handle a usage spike. The Render Disk (used for staging uploaded CSV files before processing) became inaccessible to the second worker instance. Files uploaded to the web service appeared to process correctly but produced empty analysis results. The fix required migrating file uploads to Cloudflare R2 — a correct long-term decision, but one that consumed a full day not budgeted in the 3-week MVP timeline.

The assumption that aged worst: "Render handles the operational complexity." It handles the platform; the application-level wiring (storage, rollback discipline, tier lifecycle) remained the developer's job.

### Unknown Unknowns

1. **Private networking is region-scoped and silently fails cross-region.** If the background worker and web service land in different Render regions (possible when services are created at different times with different dashboard defaults), they cannot communicate via internal hostnames. The failure mode is a timeout, not a useful connection-refused error.

2. **Native runtime vs Docker runtime are not interchangeable mid-project.** Render's native Python runtime (easy on-boarding) and a Docker-based deploy have different build environments, file paths, and env var injection semantics. Switching from native to Docker requires creating a new service — not an in-place migration — and recreating all environment variable bindings.

3. **`render.yaml` absence causes configuration drift.** Without a declarative spec, all service configuration lives only in Render's dashboard state. After 6 weeks of tweaks to env vars, health check paths, and scaling settings, the production configuration becomes impossible to reproduce from scratch. The `render.yaml` spec is optional but its absence is a quiet risk.

4. **Render Workflows (the successor service type for multi-step jobs) is still beta as of July 2026.** If the RFM analysis job evolves into a DAG-style pipeline, Render's recommended path is Workflows — but it should not be relied on for production pipelines yet.

## Operational Story

How Railway actually operates day to day. One concrete answer per line.

- **Preview deploys**: Railway creates an isolated preview environment for every pull request when connected to GitHub. Each preview has its own URL and inherits the project's env vars unless overridden. Preview environments are not publicly gated by default — add environment protection via Railway's dashboard if analysis data must not be accessible via preview links.

- **Secrets**: `railway variables set KEY=VALUE` sets env vars immediately and propagates to all services in the project on next deploy. Unlike Render, no manual restart is needed. Secret values are readable via `railway variables` (CLI) by authenticated project members — scope access via Railway's team permissions. Rotation flow: `railway variables set KEY=<new-value>`, then trigger a redeploy.

- **Rollback**: `railway redeploy` redeploys the previous image from Railway's deploy history. Custom env vars from the current environment are preserved across the rollback. Railway does not have the autodeploy race condition that Render has — the rollback is not overwritten by CI unless a new git push triggers one explicitly. Database migrations do not roll back automatically — run Alembic downgrade manually if a migration was part of the bad deploy.

- **Approval**: The following actions require human sign-off and should not be performed by the agent unattended: deleting a project or service, destroying the Railway Postgres service, rotating the Railway API token, changing the billing plan. Deploy, redeploy (rollback), variable set, log streaming, and service restart are safe for unattended agent operation.

- **Logs**: `railway logs` streams real-time logs from all services in the project. `railway logs --service <name>` filters to a specific service. `--lines N` and `--since <duration>` control output volume. The GA local MCP server (`railway mcp install`) exposes structured log access without CLI output parsing — use it for agent-driven debugging sessions.

## Risk Register

| Risk | Source | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Railpack build fails on Python patch version bump | Devil's advocate | M | M | Pin `.python-version` to `3.13.2`; set `RAILPACK_PYTHON_VERSION=3.13.2` explicitly; test any version bump in a branch before merging |
| Schema change drops tasks during 60–90s multi-service deploy window | Devil's advocate | M | H | Deploy worker first, then API; use a task queue with dead-letter queue; avoid breaking payload schema changes without a migration period |
| Remote MCP unreliable for autonomous agent ops | Devil's advocate | M | M | Use local MCP (`railway mcp install`) as the only agent-facing MCP path; treat `mcp.railway.com` as experimental |
| Sleep mode accidentally enabled on worker, tasks silently dropped | Devil's advocate | L | H | Explicitly verify sleep mode is OFF on all services; document in team runbook |
| Hobby plan RAM spike overruns $5 monthly credit | Unknown unknowns | M | L | Monitor usage in Railway dashboard; set a billing alert at $4; upgrade to Pro ($20) if RFM analysis jobs regularly spike above 256MB RAM |
| Railway Postgres has no automatic backups by default | Unknown unknowns | H | H | Enable automated backups in Railway Postgres service settings on day 1; Pro plan required for PITR |
| Hardcoded `localhost` breaks inter-service communication | Unknown unknowns | M | H | Always use `$DATABASE_URL` / `$REDIS_URL` from Railway's injected env vars; never hardcode `localhost` for dependent services |
| `railway up` ships uncommitted local changes to production | Unknown unknowns | M | M | Connect Railway to GitHub repo; use git push as the only deploy trigger; ban `railway up` from CI scripts |
| RFM analysis stack over-engineered with distributed tech | Research finding | H (resolved) | H | Cassandra + Spark dropped in favour of Pandas + Postgres; decision recorded here as resolved |

## Getting Started

1. **Install the Railway CLI and authenticate**
   ```bash
   npm install -g @railway/cli
   railway login
   ```

2. **Initialise the project and link to Railway**
   ```bash
   railway init          # creates a new Railway project
   railway link          # links the current directory to the project
   ```

3. **Add services via the dashboard or CLI** — create an API service, a worker service, a Postgres add-on, and (optionally) a Redis add-on from the Railway project view. Pin the Python version for both services:
   ```bash
   railway variables set RAILPACK_PYTHON_VERSION=3.13.2
   ```
   Set start commands per service:
   - API: `uv run uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Worker: `uv run python worker.py`

4. **Connect the Railway MCP server to Claude Code**
   ```bash
   railway mcp install
   ```
   This registers Railway's MCP tools directly in Claude Code using your existing CLI auth — no separate API key or `.mcp.json` edit required.

5. **Connect Railway to GitHub for git-push deploys** — in the Railway dashboard, link the service to the repository. From this point, every push to `main` triggers a deploy. Never use `railway up` in CI; always deploy via git push.

6. **Wire the Vite dev proxy** — in `frontend/vite.config.ts`, add:
   ```ts
   server: {
     proxy: {
       '/api': 'http://localhost:8000'
     }
   }
   ```
   This forwards `/api` requests to the FastAPI dev server during local development, matching the production routing.

## Out of Scope

The following were not evaluated in this research:
- Docker image configuration or multi-stage Dockerfile authoring
- CI/CD pipeline setup beyond git-push autodeploy
- Production-scale architecture (multi-region, HA, DR)
- Cassandra or Spark deployment (evaluated and rejected in favour of Postgres + Pandas at MVP scale)
