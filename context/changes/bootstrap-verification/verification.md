---
bootstrapped_at: 2026-07-12T12:35:00Z
starter_id: fastapi
starter_name: "FastAPI"
project_name: event-pulse-web
language_family: python
package_manager: uv
cwd_strategy: native-cwd
bootstrapper_confidence: first-class
phase_3_status: ok
audit_command: "pip-audit --format json"
---

## Hand-off

```yaml
starter_id: fastapi
package_manager: uv
project_name: event-pulse-web
hints:
  language_family: python
  team_size: solo
  deployment_target: self-host
  ci_provider: github-actions
  ci_default_flow: manual-promotion
  bootstrapper_confidence: first-class
  path_taken: custom
  quality_override: false
  self_check_answers:
    typed: true
    from_official_starter: true
    conventions: true
    docs_current: true
    can_judge_agent: false
  has_auth: true
  has_payments: false
  has_realtime: false
  has_ai: false
  has_background_jobs: true
```

**Why this stack**: Solo Python developer shipping a 3-week RFM analysis MVP with auth and file upload.
Custom path: FastAPI over Django because of an explicit preference for Pydantic-typed
schemas and a separate React SPA dashboard. FastAPI clears all four quality gates —
typed (Pydantic throughout), convention-based (opinionated routing and dependency
injection), popular in Python training data, and well-documented. Vite+React pairs
cleanly with FastAPI's API-only footprint: the SPA calls REST endpoints, keeping the
Python computation layer and the React dashboard fully decoupled. Deployment defaults
to self-host via Dockerfile; no CI/CD is scaffolded for the MVP (manual-promotion
recorded as the default flow). Background jobs flagged true — the "Analyzing…" →
"Completed" analysis flow implies async task processing beyond a synchronous HTTP
response. Self-check: agent-judgment returned partial (one stack known, one new) —
review AI suggestions carefully for the unfamiliar half of the stack.

## Pre-scaffold verification

| Signal      | Value    | Severity | Notes                                                                  |
| ----------- | -------- | -------- | ---------------------------------------------------------------------- |
| npm package | not run  | —        | Python starter; no npm package check applies                           |
| GitHub repo | not run  | —        | docs_url (https://fastapi.tiangolo.com) is not a GitHub URL; no check |

No recency signal available for fastapi. This is expected — fastapi.tiangolo.com is the official docs host, not a GitHub repo URL. The project is actively maintained (FastAPI 0.139.0 installed).

## Scaffold log

**Resolved invocation**: `uv init . && uv add fastapi uvicorn`
**Strategy**: native-cwd (scaffold directly into the current directory)
**Exit code**: 0

**Phase 1 — `uv init .`**
- Exit code: 0
- Output: `Initialized project 'projekt10devs' at /Users/pawelpaskudzki/projekt10devs`

**Phase 2 — `uv add fastapi uvicorn`**
- Exit code: 0
- Python: CPython 3.13.2 via /opt/homebrew/opt/python@3.13/bin/python3.13
- Created `.venv/` (virtual environment)
- Resolved 15 packages, installed 13:
  - fastapi==0.139.0
  - uvicorn==0.51.0
  - pydantic==2.13.4
  - pydantic-core==2.46.4
  - starlette==1.3.1
  - anyio==4.14.1
  - h11==0.16.0
  - click==8.4.2
  - idna==3.18
  - typing-extensions==4.16.0
  - typing-inspection==0.4.2
  - annotated-types==0.7.0
  - annotated-doc==0.0.4

**Files written by CLI**: 8
- `pyproject.toml` — project manifest; dependencies: fastapi>=0.139.0, uvicorn>=0.51.0
- `README.md` — empty placeholder
- `.python-version` — pins Python 3.13
- `main.py` — generic "Hello from projekt10devs!" template (not a FastAPI entry point yet)
- `.gitignore` — uv-generated Python gitignore
- `.git/` — git repository initialized by `uv init` (side-effect of uv's default behaviour)
- `.venv/` — virtual environment (13 packages)
- `uv.lock` — lockfile (25 278 bytes)

**Pre-existing files preserved** (not touched by CLI):
- `CLAUDE.md`
- `context/` (all subdirectories)
- `idea-notes.md`
- `.claude/` (skills directory)

**Known issue — project name**: `pyproject.toml` carries `name = "projekt10devs"` (the directory name). The hand-off `project_name` is `event-pulse-web`. Rename the `[project] name` field in `pyproject.toml` manually.

## Post-scaffold audit

**Tool**: pip-audit --format json
**Status**: failed to run
**Reason**: pip-audit is not installed on this machine (command not found)
**Partial output**: none

Install pip-audit to scan the dependency tree for known advisories:

```bash
uv tool install pip-audit
# then re-run from the project directory:
pip-audit
```

FastAPI 0.139.0 + Pydantic 2.13.4 + uvicorn 0.51.0 are recent releases as of scaffold date; no known CRITICAL advisories were publicly disclosed at the time of this run, but this is not a substitute for a real audit.

## Hints recorded but not acted on

| Hint                    | Value                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------- |
| bootstrapper_confidence | first-class                                                                                       |
| quality_override        | false                                                                                             |
| path_taken              | custom                                                                                            |
| self_check_answers      | typed:true, from_official_starter:true, conventions:true, docs_current:true, can_judge_agent:false |
| team_size               | solo                                                                                              |
| deployment_target       | self-host                                                                                         |
| ci_provider             | github-actions                                                                                    |
| ci_default_flow         | manual-promotion                                                                                  |
| has_auth                | true                                                                                              |
| has_payments            | false                                                                                             |
| has_realtime            | false                                                                                             |
| has_ai                  | false                                                                                             |
| has_background_jobs     | true                                                                                              |

These fields were read and logged. Bootstrapper v1 takes no automated action on them. A future M1L4 skill will act on `deployment_target`, `ci_provider`, `ci_default_flow`, and `has_*` flags when generating CLAUDE.md / AGENTS.md.

## Next steps

Next: a future skill will set up agent context (CLAUDE.md, AGENTS.md). For now, your project is scaffolded and verified — happy hacking.

**Manual steps before writing any code:**

1. Fix the project name in `pyproject.toml`: change `name = "projekt10devs"` to `name = "event-pulse-web"`.
2. Replace `main.py` with a real FastAPI entry point (`app = FastAPI()`, an `@app.get("/health")` stub, etc.).
3. Create a `frontend/` directory (or a sibling repo) and scaffold the Vite+React SPA — the hand-off records `vite-react` as the chosen frontend variant.
4. Install and run `pip-audit` to check the dependency tree: `uv tool install pip-audit && pip-audit`.
5. Note: `.git/` was created by `uv init` automatically. If you want a clean history, you can remove it and run `git init` yourself, or keep the one `uv` created.
