<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: RFM Analysis Dashboard

- **Plan**: context/changes/rfm-analysis-dashboard/plan.md
- **Scope**: Phase 3 of 3 (Frontend dashboard) — uncommitted working tree
- **Date**: 2026-07-27
- **Verdict**: NEEDS ATTENTION
- **Findings**: 1 critical, 3 warnings, 3 observations

> Note: the working tree also contains backend edits (`database.py`, `models/report.py`, `routers/analysis.py`, `services/rfm.py`, `tests/*`). All were verified as 1:1 matches to FIXED/ACCEPTED triage decisions from `impl-review-phase-1.md` and `impl-review-phase-2.md` — not Phase 3 scope creep. Phase 3 scope is `frontend/src/pages/ReportDetail.tsx` and `frontend/src/types/report.ts`.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | FAIL |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — Re-run can permanently wedge UI on "Loading results…"

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/pages/ReportDetail.tsx:76-83 (effect) + :354 (Re-run button)
- **Detail**: The results-fetch effect depends on `[report?.status, id]`. "Re-run Analysis" sets `analysisResult = null` then POSTs `/run` and re-fetches the report. FastAPI runs the background task after the 202 response, so for small datasets the analysis can finish before the follow-up GET — the GET then returns `status: 'completed'`, identical to the pre-re-run value. The dep never changes, the effect never re-fires, `analysisResult` stays `null`, and the completed branch renders "Loading results…" forever (only a page reload recovers). First run is unaffected (status transitions `created` → `completed`). This directly breaks planned manual criterion 3.7. The `eslint-disable react-hooks/exhaustive-deps` at line 82 suppresses exactly this dependency class — and is inert anyway (`.oxlintrc.json` enables only `rules-of-hooks`).
- **Fix**: Add `report?.analyzed_at` to the effect deps (`[report?.status, report?.analyzed_at, id]`) — the backend sets `analyzed_at` fresh on every completed run, so the effect re-fires on re-run while the existing `analysisResult === null` guard prevents redundant fetches. Do NOT instead add `analysisResult` to deps — that would refetch stale results between the click and the new run committing.
  - Strength: One-line change; `analyzed_at` already exists on the frontend `Report` type (types/report.ts:7).
  - Tradeoff: None significant.
  - Confidence: HIGH — race confirmed by direct code reading; dep-key fix covers first-run and re-run paths.
  - Blind spot: Not exercised in a browser yet (manual 3.7 pending).
- **Decision**: FIXED — added `report?.analyzed_at` to the results-fetch effect deps (ReportDetail.tsx:76-85)

### F2 — Results-fetch failure is silent with no recovery path

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/pages/ReportDetail.tsx:80
- **Detail**: `apiFetch(.../analysis/results).catch(() => {})` — a 500 (e.g. the "corrupted result" case the backend now returns) or transient failure leaves the completed view stuck on "Loading results…" with no message and no retry. Every other call site in this file (initial load :53-59, upload :116-123, sample :140-147, run :171-178) catches, checks `instanceof ApiError`, and surfaces `err.detail` in state — this is the one exception. The plan specified no error handling here, so this is a plan gap, not drift.
- **Fix**: Add a results-error state following the file's ApiError pattern; render the error in the completed branch with a "Retry" button that re-triggers the fetch.
- **Decision**: FIXED — added `resultsError` state, extracted `loadResults()` with ApiError handling, error message + Retry button in the completed branch

### F3 — Polling is unbounded and swallows all errors

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/src/pages/ReportDetail.tsx:63-73
- **Detail**: Interval cleanup is correct, but there is no attempt cap and `.catch(() => {})` swallows everything. The plan itself notes BackgroundTasks are fire-and-forget: a server restart mid-analysis leaves DB status `'analyzing'` forever, and this page will poll every 2s indefinitely showing "Analyzing… up to 30 seconds". A 401/404/network outage likewise polls silently forever. The plan accepted the stuck-`analyzing` backend risk at MVP; the unbounded frontend loop is a consequence it didn't address.
- **Fix A ⭐ Recommended**: Cap polling (e.g. 60 attempts ≈ 2 min), then stop and show an error with a Retry affordance; surface `ApiError.detail` after a few consecutive failures.
  - Strength: Bounds the failure mode the plan explicitly documented; consistent with the 30-second UX promise in the UI copy.
  - Tradeoff: Slightly more state/logic in an already large component.
  - Confidence: HIGH — straightforward counter in the existing interval.
  - Blind spot: Cap value is a guess; very large datasets could legitimately exceed it.
- **Fix B**: Accept as MVP risk, consistent with the plan's stance on lost background jobs, and defer to the planned startup-recovery-sweep change.
  - Strength: Zero work now; aligned with an already-accepted risk.
  - Tradeoff: A user can watch a spinner forever with no feedback.
  - Confidence: MED — depends how soon the recovery-sweep change lands.
  - Blind spot: Recovery sweep fixes the backend state but not the swallowed 401/404 polling.
- **Decision**: FIXED via Fix A — MAX_POLL_ATTEMPTS=60 cap (~2 min), stop after 3 consecutive failures surfacing ApiError.detail, "Keep waiting" button restarts polling via pollGeneration

### F4 — In-flight responses can land after cleanup or navigation

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/pages/ReportDetail.tsx:64-73 (also latent in :49-61)
- **Detail**: `clearInterval` stops future ticks but not in-flight promises. Out-of-order poll responses can briefly overwrite `'completed'` with a stale `'analyzing'` (self-healing flicker). More substantively, if the route param changes, a late response for the old `id` calls `setReport` with the wrong report's data. The initial-load effect (:49-61, pre-existing) has the same latent issue.
- **Fix**: Set a `cancelled` flag in each effect's cleanup and skip `setReport` when set.
- **Decision**: FIXED — cancelled flags added to initial-load and polling effects; additionally reset analysisResult/resultsError/pollError on id change (adjacent bug found during triage: stale results from report A rendered under report B)

### F5 — Sort re-runs on every render without memoization

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/pages/ReportDetail.tsx:190-207
- **Detail**: `sortedCustomers` clones and re-sorts on every render, including unrelated state changes. Fine at the plan's stated scale ("hundreds, not millions"), but the sample generator allows 250k events, so thousands of customers are plausible. Pagination/virtualization is explicitly out of scope per the plan's "NOT Doing" list — not flagged.
- **Fix**: Wrap in `useMemo` keyed on `[analysisResult, sortKey, sortDir]`.
- **Decision**: FIXED — sortedCustomers wrapped in useMemo (still before the early returns, hooks order preserved)

### F6 — 'Analyzing' view lacks the planned spinner/animated ellipsis

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/src/pages/ReportDetail.tsx:318-322
- **Detail**: Plan specified the analyzing message "with a spinner or animated ellipsis"; implementation renders static text with a literal `…` character. Only intent deviation found — everything else in Phase 3 matches the plan, including default segment-priority sort, immutable sorting, and monetary formatting.
- **Fix**: Add a small CSS animation (or consciously accept static text).
- **Decision**: FIXED — `.analyzing-pulse` keyframe animation added to index.css, applied to the analyzing message

### F7 — Table header is data-driven but body cells are hardcoded

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/pages/ReportDetail.tsx:366-380 vs :386-393
- **Detail**: `<th>` cells map over the `COLUMNS` const, but `<td>` cells are hardcoded in fixed order — reordering or extending `COLUMNS` silently desyncs header from body.
- **Fix**: Render body cells from the same `COLUMNS` array with a per-key formatter for `monetary`.
- **Decision**: FIXED — tbody cells now map over COLUMNS with an inline monetary formatter

## Success criteria

- **Automated 3.1** — `cd frontend && npm run lint`: ✅ PASS (zero errors, verified during this review).
- **Manual 3.2–3.9** — all honestly unchecked in `## Progress` (pending, no rubber-stamping). Note: 3.7 (re-run refreshes results) will fail until F1 is fixed — fix F1 before running the manual pass.

## Triage outcome (2026-07-27)

All 7 findings FIXED (F3 via Fix A). Post-triage verification: `npm run lint` zero errors, `npm run build` (type-check + bundle) passes. One adjacent bug found and fixed during F4 triage: per-report analysis state (`analysisResult`, `resultsError`, `pollError`) is now reset on route-param change so report B never renders report A's results. Manual criteria 3.2–3.9 remain pending — F1's fix means 3.7 is now expected to pass.

## Clean areas

- No XSS exposure; all API strings render as escaped JSX text.
- Rules-of-hooks correct: all hooks unconditional, before early returns; interval cleanup returned; `handleSort` uses functional updater.
- New types match existing file style exactly; scope discipline respected (extras are benign: sorted segment breakdown, hardened Retry button, `COLUMNS`/`SEGMENT_ORDER` constants).
- Backend working-tree edits fully accounted for by phase-1/2 triage decisions.
