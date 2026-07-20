# Event File Upload — Plan Brief

> Full plan: `context/changes/event-file-upload/plan.md`

## What & Why

Users currently have no way to add customer events to a report. This change implements FR-008: accept a CSV or JSON file, validate every record, and bulk-insert events — gating S-05 (RFM analysis) which requires events to exist before analysis can run.

## Starting Point

The `Event` table and ORM model already exist with the correct schema. `ReportDetail.tsx` renders a hard-disabled "Run Analysis" button and has no upload UI. `apiFetch` hardcodes `Content-Type: application/json`, blocking multipart uploads. `python-multipart` is not yet installed.

## Desired End State

A user selects a `.csv` or `.json` file on the ReportDetail page and clicks Upload. If the file is valid, a success message confirms how many events were added and the "Run Analysis" button becomes enabled. If the file has errors, a readable message with a row-level sample is shown and nothing is persisted.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
| --- | --- | --- |
| Persistence strategy | Bulk-insert in one transaction | Atomicity: if any record fails validation, nothing is written |
| Error presentation | Count + first 5 sample messages | Enough signal to fix the file without flooding the UI |
| Re-upload behaviour | Append to existing events | Matches the S-05 re-run model where events accumulate before re-scoring |
| Client-side pre-check | CSV line-count via FileReader | Instant rejection for oversized files without a network round-trip |
| apiFetch adaptation | Separate `apiFetchFile` helper | No risk of breaking existing JSON calls; ~10-line addition |
| Post-upload refresh | Re-fetch report from API | Server is the source of truth for event_count |
| Upload UI placement | Inline section, always visible | Zero extra interaction to reach upload; matches single-screen layout |

## Scope

**In scope:**
- `POST /api/reports/{report_id}/events/upload` endpoint
- CSV and JSON parsing + per-record validation
- 200,000-event cap enforcement (backend + CSV client-side)
- `python-multipart` dependency
- `apiFetchFile` helper in `client.ts`
- Inline upload section in `ReportDetail.tsx`
- Fix "Run Analysis" button disabled logic
- 13 backend test cases in `tests/test_events.py`

**Out of scope:**
- Upload UI for reports in `analyzing` / `completed` / `failed` status (S-05)
- Duplicate-event deduplication (MVP)
- Upload progress bar
- Client-side pre-check for JSON files

## Architecture / Approach

Backend: new `routers/events.py` registered in `main.py`. Parse entire file into a list of dicts, validate all records collecting up to 5 error samples, check total count ≤ 200k, then `db.add_all(...)` + `await db.commit()`. All errors returned as plain strings in `HTTPException.detail` — consistent with existing router pattern.

Frontend: `apiFetchFile` omits `Content-Type` so the browser sets the multipart boundary. `ReportDetail.tsx` wraps `FileReader.readAsText()` in a Promise for the CSV line-count check, then calls `apiFetchFile`, then re-fetches the report on success to update `event_count` and unblock "Run Analysis".

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend upload endpoint | Validated, auth-gated upload API + 13 test cases | Timestamp UTC attachment for naive ISO strings |
| 2. Frontend upload UI | File picker, pre-check, success/error states, Run Analysis fix | FileReader Promise wrapping in upload handler |

**Prerequisites:** S-02 (report management) complete — ✓ done  
**Estimated effort:** ~2 sessions across 2 phases

## Open Risks & Assumptions

- CSV with multi-line quoted fields will cause the client-side line-count pre-check to over-count; backend is the authoritative enforcer — the client check is a fast-fail convenience, not a security control.
- No dedup logic: uploading the same file twice silently doubles the event count for that report.

## Success Criteria (Summary)

- `uv run pytest tests/test_events.py -v` — all 13 cases green
- User can upload a valid CSV or JSON file and see event count update on ReportDetail
- Invalid files produce a row-level error message with zero events persisted
