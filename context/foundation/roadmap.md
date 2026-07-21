---
project: "EventPulse Web"
version: 1
status: draft
created: 2026-07-17
updated: 2026-07-21
prd_version: 1
main_goal: market-feedback
top_blocker: capacity
---

# Roadmap: EventPulse Web

> Derived from `context/foundation/prd.md` (v1) + auto-researched codebase baseline.
> Edit-in-place; archive when superseded.
> Slices below are listed in dependency order. The "At a glance" table is the index.

## Vision recap

Small and medium e-commerce and SaaS product managers have customer event data in CSV or JSON files but no affordable, fast path from those files to actionable RFM customer segments. EventPulse Web fills that gap: a user uploads a file (or generates sample data with one click), runs analysis, and sees a sortable dashboard showing Champions, At Risk, Hibernating, and other segments within minutes. Enterprise analytics platforms are priced out of reach for these teams; spreadsheet RFM is slow and error-prone. The product's distinguishing trait is simplicity at the right price point — no data warehouse, no data engineering team, no per-seat enterprise contract required.

## North star

**S-05: run analysis + see RFM dashboard** — this is the validation milestone: the smallest end-to-end slice whose successful delivery proves the core product hypothesis (the specific bet EventPulse makes: a PM with event data can reach segment insights within 5 minutes of first visit, self-serve). US-01 and the primary Success Criterion both converge on this slice; every upstream slice is scaffolding that makes this moment reachable.

> "North star" as used here: the one slice that, if it works end-to-end, proves the product's central claim. Placed as early as Prerequisites allow because everything else only matters if this works.

## At a glance

| ID   | Change ID              | Outcome (user can …)                                            | Prerequisites | PRD refs                       | Status   |
| ---- | ---------------------- | --------------------------------------------------------------- | ------------- | ------------------------------ | -------- |
| F-01 | auth-scaffold          | (foundation) auth middleware wired; protected routes return 401 | —             | FR-001, FR-002, Access Control | ready    |
| F-02 | db-schema-baseline     | (foundation) ORM + Alembic migrations for User, Report, Event tables applied | — | Business Logic §Event schema, Access Control | ready |
| S-01 | auth-flows             | register with email/password, log in, and log out              | F-01, F-02    | FR-001, FR-002, FR-003         | done     |
| S-02 | report-management      | create a report, view the list, open it, and delete it         | S-01          | FR-004, FR-005, FR-006, FR-007 | done     |
| S-03 | event-file-upload      | add customer events to a report by uploading CSV or JSON       | S-02          | FR-008                         | done     |
| S-04 | sample-generator       | add sample customer events to a report in one click            | S-02          | FR-009                         | proposed |
| S-05 | rfm-analysis-dashboard | run RFM analysis and view a sortable results dashboard         | S-03          | FR-010, FR-011, FR-012, US-01  | proposed |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme                    | Chain                                                 | Note                                                                              |
| ------ | ------------------------ | ----------------------------------------------------- | --------------------------------------------------------------------------------- |
| A      | Auth → analysis pipeline | `F-01` / `F-02` → `S-01` → `S-02` → `S-03` → `S-05` | F-01 and F-02 run in parallel; chain leads to the north star                      |
| B      | Sample generator         | `S-02` → `S-04`                                       | Parallel with S-03 after S-02 lands; S-04 provides an alternative event source for S-05 |

## Baseline

What's already in place in the codebase as of 2026-07-17 (auto-researched + user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** partial — Vite + React 19 scaffold, no product screens (`frontend/src/App.tsx` is the Vite default template)
- **Backend / API:** partial — FastAPI app with `/health` stub only (`main.py:1-8`), no product routes
- **Data:** absent — no ORM, no models, no migrations (`pyproject.toml`: fastapi + uvicorn only)
- **Auth:** absent — no auth code anywhere
- **Deploy / infra:** present — Railway deployed (API + Frontend + Postgres), git-push autodeploy confirmed working, `DATABASE_URL` verified (2026-07-17, per deploy-plan.md)
- **Observability:** absent — no logging library or error tracking configured

## Foundations

### F-01: Auth scaffold

- **Outcome:** (foundation) password-hashing config wired (bcrypt), FastAPI auth dependency that validates a Bearer token and returns the current user, 401 response on all protected routes for unauthenticated requests — no register/login endpoints yet.
- **Change ID:** auth-scaffold
- **PRD refs:** Access Control section ("all product routes require an authenticated session"), FR-001, FR-002
- **Unlocks:** S-01 (register/login endpoints consume the auth dependency and token-issuance utility)
- **Prerequisites:** —
- **Parallel with:** F-02
- **Blockers:** —
- **Unknowns:** —
- **Risk:** narrow scope (middleware + hashing config only) keeps this fast; if token strategy (JWT vs opaque session) is undecided at planning time, it needs a decision before S-01 can be planned
- **Status:** ready

### F-02: Database schema and ORM baseline

- **Outcome:** (foundation) SQLAlchemy async engine connected to Railway Postgres via the verified `DATABASE_URL`; Alembic migration with User, Report, and Event table definitions applied; engine health verified in Railway API service logs.
- **Change ID:** db-schema-baseline
- **PRD refs:** Business Logic §Event schema (customer_id, timestamp, event_type, amount), Access Control section (per-user data isolation)
- **Unlocks:** S-01 (User table), S-02 (Report table), S-03 and S-04 (Event table)
- **Prerequisites:** —
- **Parallel with:** F-01
- **Blockers:** —
- **Unknowns:** —
- **Risk:** all product slices block on this; the event schema is fully specified in PRD §Business Logic so schema definition is low-uncertainty; ORM + migration tooling choice (plain SQLAlchemy + Alembic vs SQLModel) to be decided in `/10x-plan`
- **Status:** ready

## Slices

### S-01: User can register, log in, and log out

- **Outcome:** user can create an account with email and password, receive a session token on login, access protected product routes, and log out to invalidate the session.
- **Change ID:** auth-flows
- **PRD refs:** FR-001, FR-002, FR-003
- **Prerequisites:** F-01, F-02
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** email + password auth is well-understood; PRD explicitly locked this model (no OAuth, no passwordless) so no decision drift expected; main risk is token storage and expiry edge cases on the frontend
- **Status:** done

### S-02: User can manage reports

- **Outcome:** user can create a named report with an optional description, view their list of reports, open a report to see its detail in the pre-analysis state, and delete a report with a mandatory confirmation step.
- **Change ID:** report-management
- **PRD refs:** FR-004, FR-005, FR-006, FR-007
- **Prerequisites:** S-01
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** four FRs in one slice; all are CRUD operations on the same Report entity — splitting would produce artificially thin slices with no independent user-visible value; FR-006's two-state report page (pre-analysis and post-analysis) must be designed in this slice even though the post-analysis state is exercised in S-05
- **Status:** done

### S-03: User can add events via file upload

- **Outcome:** user can upload a CSV or JSON file to a report; the application validates the file format and every event record's required fields before persisting events; invalid files or records produce a clear error message before any events are stored; files exceeding 200,000 events are rejected at the upload boundary.
- **Change ID:** event-file-upload
- **PRD refs:** FR-008
- **Prerequisites:** S-02
- **Parallel with:** S-04
- **Blockers:** —
- **Unknowns:**
  - Persistence strategy: parse file and insert events row-by-row vs bulk-insert in a single transaction. Owner: team. Block: no (both approaches work within PRD constraints; detail for `/10x-plan`).
- **Risk:** file validation must be strict per PRD NFR ("no silent failure or partial analysis"); the 200,000-event cap and required-field check must both be enforced before any events are written — not after
- **Status:** done

### S-04: User can add events via sample generator

- **Outcome:** user can click a single button to generate a set of representative sample customer events and add them to a report, without uploading a file.
- **Change ID:** sample-generator
- **PRD refs:** FR-009
- **Prerequisites:** S-02
- **Parallel with:** S-03
- **Blockers:** —
- **Unknowns:**
  - Sample size and distribution: how many customers, events, and what purchase rate should the generator produce? Owner: team. Block: no (sensible defaults suffice for MVP; can be tuned after seeing the dashboard results).
- **Risk:** the generated sample must produce representatives from all six segment types when analysed, or the zero-friction demo path loses its value; verify segment coverage as an acceptance criterion for this slice
- **Status:** proposed

### S-05: User can run RFM analysis and view the results dashboard

- **Outcome:** user can click "Run Analysis" on a report that has events, see a status transition from "Analyzing…" to "Completed", and view a results dashboard showing total event count, unique customer count, and a sortable RFM results table with each customer's R/F/M scores and segment assignment (Champions, Loyal Customers, Potential Loyalists, At Risk, Hibernating, Others).
- **Change ID:** rfm-analysis-dashboard
- **PRD refs:** FR-010, FR-011, FR-012, US-01
- **Prerequisites:** S-03
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:**
  - Async execution strategy: FastAPI BackgroundTasks + DB status polling vs a dedicated Railway worker service + queue. Owner: team. Block: no (BackgroundTasks is sufficient for MVP given the 30-second NFR at ≤200k events; a separate worker can be promoted later if load justifies it).
- **Risk:** RFM computation must match PRD §Business Logic exactly — quintile-based scoring, priority-ordered segment assignment rules, purchase-only Monetary dimension, deterministic output; the PRD §Business Logic is the acceptance test oracle; re-run (FR-011) must append new events to the existing set before re-scoring, not replace the prior events
- **Status:** proposed

## Backlog Handoff

| Roadmap ID | Change ID              | Suggested issue title                              | Ready for `/10x-plan` | Notes                                                   |
| ---------- | ---------------------- | -------------------------------------------------- | --------------------- | ------------------------------------------------------- |
| F-01       | auth-scaffold          | Auth scaffold: Bearer middleware + bcrypt config   | yes                   | Run `/10x-plan auth-scaffold`; parallel with F-02       |
| F-02       | db-schema-baseline     | DB schema baseline: ORM + Alembic migrations       | yes                   | Run `/10x-plan db-schema-baseline`; parallel with F-01  |
| S-01       | auth-flows             | Auth flows: register, login, logout                | no                    | Plan after F-01 and F-02 are implemented                |
| S-02       | report-management      | Report management: create, list, open, delete      | no                    | Plan after S-01 is implemented                          |
| S-03       | event-file-upload      | Event ingestion: CSV/JSON file upload + validation | no                    | Plan after S-02; run parallel with S-04                 |
| S-04       | sample-generator       | Event ingestion: sample data generator             | no                    | Plan after S-02; run parallel with S-03                 |
| S-05       | rfm-analysis-dashboard | RFM analysis: async execution + results dashboard  | no                    | Plan after S-03 is implemented; this is the north star  |

## Open Roadmap Questions

No cross-cutting open questions — all PRD open questions were resolved before this roadmap was generated. Per-slice unknowns are recorded in each slice's Unknowns field and are all non-blocking.

## Parked

Items from PRD §Non-Goals — deferred from MVP scope.

- **Real-time / streaming analysis** — Why parked: PRD §Non-Goals ("batch only; no live event feeds or continuous ingestion").
- **Analytics beyond RFM segmentation** — Why parked: PRD §Non-Goals (no funnel analysis, cohort retention, predictive ML, or other analysis types for v1).
- **File export of analysis results** — Why parked: PRD §Non-Goals ("results are viewed in-app only; no PDF, Excel, or CSV download of analysis output").
- **Report sharing / team workspaces** — Why parked: PRD §Non-Goals ("each account is strictly private; no collaboration, invite flows, or shared access").
- **External data source integrations** — Why parked: PRD §Non-Goals ("no connectors to third-party event platforms").
- **Scheduled / automated analysis** — Why parked: PRD §Non-Goals ("triggered manually by the user every time; no cron or auto-refresh").
- **AI-generated explanations or next-best-action features** — Why parked: PRD §Non-Goals ("rule-based RFM classification only; no language model involvement").
- **Notification / alert system** — Why parked: PRD §Non-Goals ("users check the dashboard manually").
- **Mobile browser support** — Why parked: PRD §Non-Goals ("desktop web only for MVP").
- **Segment distribution chart (FR-012b)** — Why parked: PRD nice-to-have; sortable RFM table (FR-012) carries the same information for MVP; add after core analysis is stable.

## Done

- **S-01: register with email/password, log in, and log out** — Archived 2026-07-20 → `context/archive/2026-07-20-auth-flows/`. Lesson: —.
- **S-02: user can create a named report with an optional description, view their list of reports, open a report to see its detail in the pre-analysis state, and delete a report with a mandatory confirmation step.** — Archived 2026-07-20 → `context/archive/2026-07-20-report-management/`. Lesson: —.
- **S-03: add customer events to a report by uploading CSV or JSON** — Archived 2026-07-21 → `context/archive/2026-07-20-event-file-upload/`. Lesson: —.
