# Sample Generator — Plan Brief

> Full plan: `context/changes/sample-generator/plan.md`

## What & Why

Add a "Generate Sample" button to the report detail page so users can populate a report with representative customer events in one click, without uploading a file. This is FR-009 and roadmap slice S-04 — the zero-friction path to a first demo of the RFM analysis (S-05), and the acceptance criterion is that the generated data produces all six segments when analysed.

## Starting Point

The event ingestion surface (`routers/events.py`) already exists with the file upload endpoint. The `UploadResult` Pydantic model and TypeScript interface, the 200k cap constant, the report ownership check pattern, and the "Add Events" section in `ReportDetail.tsx` are all in place — the new feature slots in without touching any existing code paths.

## Desired End State

A count input (defaulting to 150) and "Generate Sample" button appear in the "Add Events" section of any `created`-status report. Clicking calls `POST /api/reports/{report_id}/events/sample`, which generates events from 30 hardcoded customer archetypes and inserts them. The default 150-event dataset covers all six RFM segments. Users can set count to 200,001 to immediately see and test the 200k cap error — no large file upload required.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
|---|---|---|
| Sample size | 30 customers (5 per segment) | Minimum headcount for clean quintile boundaries across all 6 segments |
| Event mix | Purchase + non-purchase (`view`, `add_to_cart`) | Makes Frequency and Monetary independently meaningful in the demo |
| Repeat generation | Always append | Consistent with upload semantics; count message tells user what was added |
| Cap guard | Count existing + requested > 200k → 400 | PRD NFR requires no report to exceed 200k events; inconsistent enforcement would corrupt analysis |
| Count parameter | Optional JSON body `{ "count": N }`, default 150, max 250,000 | Lets testers hit the 200k cap without uploading a large file |
| Timestamp strategy | Resolved at call time via `datetime.now(UTC) - timedelta(days=days_ago)` | Static dates would cause recency scores to drift and break segment coverage |

## Scope

**In scope:** Backend endpoint + tests; frontend button + count input + feedback; 200k cap check.

**Out of scope:** New model or migration; changes to the upload endpoint; per-segment count controls; randomised output; analysis of the sample (that's S-05).

## Architecture / Approach

New `POST /api/reports/{report_id}/events/sample` route added to `routers/events.py` (same router, no `main.py` change). A module-level `_SAMPLE_TEMPLATES` constant encodes 30 customer archetypes; the handler materialises them at call time and cycles through the list to reach any requested `count`. Frontend adds four state variables and a handler to `ReportDetail.tsx`, mirroring the existing upload flow.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Backend endpoint | `POST .../events/sample` with count param, ownership check, cap guard, tests | Template data must produce all 6 segments — verify segment coverage in S-05 |
| 2. Frontend button | Count input + "Generate Sample" button in "Add Events" section | None — mirrors upload pattern exactly |

**Prerequisites:** S-02 (report management) — done.  
**Estimated effort:** ~1 session across 2 phases.

## Open Risks & Assumptions

- Segment coverage depends on the exact `days_ago` / event count values in `_SAMPLE_TEMPLATES` — this must be verified when S-05 (RFM analysis) is implemented and run against the default 150-event sample.
- Cycling events for large counts (count > 150) means customers accumulate proportionally equal extra events — quintile positions are preserved but the absolute counts scale up. This is sufficient for cap-testing purposes.

## Success Criteria (Summary)

- Default 150-event sample inserts without error and the report `event_count` updates correctly.
- Setting count to 200,001 returns a 400 error containing "200,000".
- The 150-event sample produces all six RFM segments when S-05 analysis is run (forward-looking verification).
