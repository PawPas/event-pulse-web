# Report Management — Plan Brief

> Full plan: `context/changes/report-management/plan.md`

## What & Why

Build the report CRUD slice (S-02): users can create a named report, view their list, open a detail page, and delete with a confirmation modal. This is the prerequisite for S-03 (file upload), S-04 (sample generator), and ultimately S-05 (RFM analysis). Without it, there's no container to attach events to.

## Starting Point

The `Report` ORM model is fully defined and migrated to Railway Postgres (status enum, event cascade-delete, timestamps all present). The auth layer (S-01) is complete and merged: `get_current_user` dependency, `apiFetch` utility, Redux auth store, and AppShell shell are all in place. The authenticated index route (`/`) currently shows a "Welcome, {email}" placeholder.

## Desired End State

Logged-in users see a report list at `/`, can create a report inline, click into a detail page at `/reports/:id` that shows metadata and a disabled "Run Analysis" button, and delete reports via a confirmation modal. The backend exposes four protected endpoints under `/api/reports/` returning `event_count` per report. 19 backend tests pass.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
| --- | --- | --- |
| Create report UX | Inline form on list page | Zero navigation overhead; new report appears immediately in the list. |
| "Run Analysis" in S-02 | Show disabled, tooltip | Establishes the two-state page layout now (FR-006) so S-05 only needs to enable the button. |
| Delete confirmation | Modal overlay | Satisfies FR-007's "mandatory confirmation step" without per-row inline state churn. |
| Frontend state management | Local useState/useEffect per page | No Redux slice for server data; avoids cache-invalidation complexity at MVP scale. |
| event_count in responses | Yes, correlated subquery | Pre-analysis page can show "0 events" immediately; avoids a schema change mid-S-03. |
| List sort order | created_at DESC (newest first) | New reports are immediately visible at top after creation. |
| Access control on detail/delete | 404 for other user's reports | Consistent with auth-flows user-enumeration-prevention principle. |

## Scope

**In scope:** `POST /api/reports/` (create), `GET /api/reports/` (list), `GET /api/reports/{id}` (detail), `DELETE /api/reports/{id}` (delete); frontend ReportList, ReportDetail, routing, AppShell app-name link.

**Out of scope:** Report editing, list pagination, "Run Analysis" action, event upload (S-03), sample generator (S-04), RFM results panel (S-05).

## Architecture / Approach

Backend: `routers/reports.py` follows the `routers/auth.py` pattern exactly — `APIRouter(prefix="/api/reports")`, inline Pydantic v2 schemas, async handlers. `event_count` computed via correlated scalar subquery (no N+1). `DELETE` returns 204; all user-scoping applied via `UUID(current_user.sub)`.

Frontend: No new Redux slice — each page manages its own data with `useState`/`useEffect` + `apiFetch`. `ReportList` replaces `Dashboard` as the AppShell index route. `ReportDetail` is a new nested route at `reports/:id`. The delete modal is an inline overlay component in each page.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend report API + tests | 4 endpoints, 9 tests, reports router wired | Correlated subquery syntax with SQLAlchemy 2.x typed API |
| 2. Frontend report pages + routing | ReportList, ReportDetail, routing, delete modal | TypeScript types must align with backend response shape |

**Prerequisites:** S-01 (auth-flows) is merged — `get_current_user`, `apiFetch`, AppShell, and Redux auth all in place.
**Estimated effort:** ~1-2 sessions across 2 phases.

## Open Risks & Assumptions

- The `apiFetch` return type is `Promise<unknown>` — type assertions (`as Report[]`) are needed in components. This is acceptable for MVP but could be improved with a typed wrapper in a later slice.
- The "Run Analysis" button being visible-but-disabled in S-02 assumes the page layout will not need restructuring when S-05 enables it — the two-state design must be stable.

## Success Criteria (Summary)

- `uv run pytest tests/ -v` — 19/19 tests pass (10 existing + 9 new)
- Authenticated user can create, view, and delete reports via the browser UI with no console errors
- "Run Analysis" is visible but non-functional; detail page handles the 404 case gracefully
