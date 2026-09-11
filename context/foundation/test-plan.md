# Test Plan

> Phased test rollout for this project. Strategy is frozen at the top
> (§1–§5); cookbook patterns at the bottom (§6) fill in as phases ship.
> Read before writing any new test.
>
> Refresh: re-run `/10x-test-plan --refresh` when stale (see §8).
>
> Last updated: 2026-09-11

## 1. Strategy

Tests follow three non-negotiable principles for this project:

1. **Cost × signal.** The cheapest test that gives a real signal for the
   risk wins. Do not promote to e2e because e2e "feels safer." Do not put a
   vision model on top of a deterministic visual diff that already catches
   the regression.
2. **User concerns are first-class evidence.** Risks anchored in "the
   team is worried about X, and the failure would surface somewhere in
   that area" carry the same weight as PRD lines or hot-spot data.
3. **Risks are scenarios, not code locations.** This plan documents *what
   could fail* and *why we believe it's likely* — drawn from documents,
   interview, and codebase *signal* (churn, structure, test base). It does
   NOT claim to know which line owns the failure. That knowledge is
   produced by `/10x-research` during each rollout phase. If the plan and
   research disagree about where the failure lives, research is the
   ground truth.

Hot-spot scope used for likelihood weighting: scan skipped — only 2 commits
touched product code in the last 30 days (MVP closed 2026-08-31). Likelihood
ratings rely on the roadmap and the Phase 2 interview.

## 2. Risk Map

The top failure scenarios this project must protect against, ordered by
risk = impact × likelihood. Risks are failure scenarios in user / business
terms, not test names. The Source column cites the *evidence that surfaced
this risk* — never a specific file as "where the failure lives" (that is
research's job, see §1 principle #3).

| # | Risk (failure scenario) | Impact | Likelihood | Source (evidence — not anchor) |
|---|--------------------------|--------|------------|--------------------------------|
| 1 | A user gains access to another account's report or event data — an endpoint checks authentication but not resource ownership (IDOR) | High | Medium | PRD §Success Criteria Guardrails + NFR "no user's data accessible to another account"; interview Q1; abuse/security lens (auth product) |
| 2 | RFM analysis returns wrong scores or segments (quintile boundaries, ties, segment-rule priority, purchase-only Monetary) and nobody notices — customers act on bad data | High | Medium | PRD §Business Logic; roadmap S-05 risk note ("the PRD §Business Logic is the acceptance test oracle"); interview Q1 |
| 3 | Import silently drops or mangles records — analysis runs on incomplete data with no error shown | High | Medium | PRD NFR "no silent failure or partial analysis" + 200k cap "rejected before processing"; interview Q1, Q3 |
| 4 | A frontend change breaks app startup or the auth flow — white screen on corrupted localStorage, or users bounced to login in a loop | High | Medium | lessons.md (localStorage startup crash); interview Q2, Q3, Q4; test-base profile: frontend nearly untested (2 files) |
| 5 | Unexpected-but-plausible input (malformed file, odd encoding, missing field) surfaces as a 500 instead of a clear 4xx | Medium | High | lessons.md ("Convert avoidable 500s to 4xx" — team was burned here); interview Q2 |
| 6 | Async analysis failure is invisible — the user is stuck on "Analyzing…" with no error state ever surfacing | Medium | Medium | interview Q4; tech-stack.md (has_background_jobs: true); roadmap S-05 unknown (BackgroundTasks execution strategy) |

### Risk Response Guidance

| Risk | What would prove protection | Must challenge | Context `/10x-research` must ground | Likely cheapest layer | Anti-pattern to avoid |
|------|-----------------------------|----------------|--------------------------------------|-----------------------|-----------------------|
| #1 | A two-user matrix over *every* resource endpoint: requests against another user's resource return 404/403, never data | "Reports have isolation tests, so the other endpoints are probably covered too" | Full inventory of resource endpoints and where the ownership filter lives on each | integration (pytest) | happy-path-only (testing only one's own resources) |
| #2 | Results match fixtures computed independently from PRD §Business Logic rules (not from the code); deterministic re-runs; re-run appends new events and rescores, never replaces | "Algorithm tests exist, therefore the PRD rule boundaries are covered" | Which PRD edge cases (quintile ties, segment-rule priority order, purchase-only Monetary, single-customer) have a test and which do not | unit | the oracle problem — expected values copied from the implementation under test |
| #3 | Records-in equals records-persisted, or an explicit error before any write; the 200k cap rejects before processing starts | "Format validation passing means no silent loss is possible" | The parse-to-persist boundary and its transactional behavior (all-or-nothing vs partial write) | integration | asserting only on the HTTP status without checking persisted DB state |
| #4 | The app mounts and login-to-dashboard works despite corrupted localStorage or an expired token | "The safe-parse helper exists, so the startup-crash class is solved forever" | Which state reads happen at frontend startup; how the app reacts to a 401 mid-session | component/integration (Vitest + Testing Library) | meaningless snapshots (explicitly excluded by §7) |
| #5 | A matrix of hostile/odd inputs always yields a 4xx with a clear message, never a 500, and never a partial write | "That class of bug was fixed after lessons.md, so it's done" | Inventory of inbound boundaries (upload, request bodies, params) and which built-ins can raise there | integration | testing only the well-formed examples from the PRD |
| #6 | A forced analysis failure lands the report in a visible `failed` state in both API and UI; no eternal "analyzing" | "The happy path sets `completed`, so the failure path surely sets `failed`" | How the background task reports errors and which component persists the failure status | integration (backend) + component (frontend) | mocking the task internals instead of forcing a real failure |

## 3. Phased Rollout

Each row is a discrete rollout phase that will open its own change folder
via `/10x-new`. Status moves left-to-right through the values below; the
orchestrator updates Status as artifacts appear on disk.

| # | Phase name | Goal (one line) | Risks covered | Test types | Status | Change folder |
|---|------------|------------------|----------------|-------------|--------|----------------|
| 1 | Isolation matrix completion | Prove every resource endpoint rejects another user's resources, not just reports | #1 | integration | not started | — |
| 2 | Import integrity and input boundaries | Prove no silent record loss and no 500s at inbound boundaries | #3, #5 | integration | not started | — |
| 3 | RFM oracle and analysis failure paths | Prove results match PRD-derived fixtures and failures surface as a visible `failed` state | #2, #6 | unit + integration | not started | — |
| 4 | Frontend confidence layer | Prove app startup and the auth/analysis UI flows survive bad state without a browser | #4, #6 | component/integration | not started | — |
| 5 | Quality-gates wiring | Lock the floor: lint + typecheck + scoped tests at commit, full suites before push/CI | cross-cutting | gates | not started | — |

## 4. Stack

The classic test base for this project. Recommendations below are grounded
in local manifests plus the MCP/tools actually exposed in the current
session.

| Layer | Tool | Version | Notes |
|-------|------|---------|-------|
| backend unit + integration | pytest + FastAPI TestClient | >=8.0.0 | 8 test files: API, auth flows, RFM algorithm, upload, DB health; in-memory SQLite via conftest |
| frontend unit + component | Vitest (jsdom) + Testing Library | ^3.2.7 / ^16.3.3 | 2 test files today (store slice, util); Testing Library installed but unused — Phase 4 adopts it |
| mutation testing | Stryker (vitest runner) | ^10.0.0 | configured for frontend (`stryker.config.json`); optional signal, not a gate |
| e2e | none yet | — | deliberately absent for now; revisit only if Phases 1–4 leave a browser-shaped gap |
| accessibility | none | — | out of MVP scope (PRD: desktop-only, no a11y requirement stated) |

**Stack grounding tools (current session):**
- Docs: Context7 MCP available — not queried; local configs were sufficient for stack facts; checked: 2026-09-11
- Search: built-in WebSearch available; Exa.ai not available in current session — not used; checked: 2026-09-11
- Runtime/browser: Playwright MCP not available in current session — e2e layer deferred anyway; checked: 2026-09-11
- Provider/platform: Railway MCP available — relevant for future deploy smoke checks, not used by this plan; checked: 2026-09-11

## 5. Quality Gates

The full set of gates that must pass before a change reaches production.
"Required for §3 Phase N" means the gate is enforced once that rollout
phase lands; before that, the gate is `planned`.

| Gate | Where | Required? | Catches |
|------|-------|-----------|---------|
| lint (oxlint) + typecheck (tsc) | local, frontend | required (AGENTS.md rule today); wired at commit by §3 Phase 5 | syntactic / type drift |
| backend pytest suite | local | required after §3 Phase 2 | logic and boundary regressions |
| frontend vitest suite | local | required after §3 Phase 4 | startup/auth/state regressions |
| scoped tests at commit (staged files) | local pre-commit | wired by §3 Phase 5 | regressions before they leave the machine |
| full suites at push | local pre-push | wired by §3 Phase 5 | cross-module regressions |

## 6. Cookbook Patterns

How to add new tests in this project. Each sub-section is filled in once
the relevant rollout phase ships; before that, the sub-section reads
"TBD — see §3 Phase N."

### 6.1 Adding a backend integration test (API endpoint)

- **Location**: `tests/test_<router>.py` at repo root.
- **Pattern**: register user(s) via `/api/auth/register` fixtures, call the
  endpoint through `test_client`, assert response AND persisted state.
- **Isolation**: every resource endpoint test must include a second-user
  case (see `tests/test_reports.py` `test_isolation_*`).
- **Run locally**: `uv run pytest`.

### 6.2 Adding a backend unit test (business logic)

- **Location**: `tests/test_rfm_algorithm.py` (or a sibling for new logic).
- **Oracle rule**: expected values must derive from PRD §Business Logic,
  never from running the implementation — see §2 Risk #2 guidance.
- **Run locally**: `uv run pytest tests/test_rfm_algorithm.py`.

### 6.3 Adding a silent-loss / input-boundary test

- TBD — see §3 Phase 2 for the records-in-equals-records-persisted and
  hostile-input-to-4xx patterns.

### 6.4 Adding a frontend component/flow test

- TBD — see §3 Phase 4 for the startup-with-corrupted-storage and
  auth-flow patterns (Vitest + Testing Library, no snapshots).

### 6.5 Adding an analysis failure-path test

- TBD — see §3 Phase 3 for the forced-failure-to-visible-`failed`-state
  pattern (backend and frontend halves).

### 6.6 Per-rollout-phase notes

(Appended by /10x-implement as phases land.)

## 7. What We Deliberately Don't Test

Exclusions agreed during the rollout (Phase 2 interview, Q5). Future
contributors should respect these unless the underlying assumption changes.

- **UI snapshots / visual regression** — brittle, high maintenance, low
  signal for this product. Re-evaluate if the dashboard gains complex
  visual output (charts). (Source: Phase 2 interview Q5.)
- **Sample data generator internals** — demo path, low blast radius; its
  one meaningful property (segment coverage) is asserted where it matters.
  Re-evaluate if the generator becomes a primary data source. (Source:
  Phase 2 interview Q5.)
- **200k-event performance envelope** — real volumes are far below the cap;
  the cap-rejection behavior IS tested (Risk #3), the 30-second NFR is not
  benchmarked. Re-evaluate when real uploads approach the limit.

## 8. Freshness Ledger

- Strategy (§1–§5) last reviewed: 2026-09-11
- Stack versions last verified: 2026-09-11
- AI-native tool references last verified: 2026-09-11

Refresh (`/10x-test-plan --refresh`) when:

- a new top-3 risk surfaces from the roadmap or archive,
- a recommended tool's `checked:` date is older than three months,
- the project's tech stack changes (new framework, new test runner),
- §7 negative-space no longer matches what the team believes.
