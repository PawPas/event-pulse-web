---
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
---

## Why this stack

Solo Python developer shipping a 3-week RFM analysis MVP with auth and file upload.
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
