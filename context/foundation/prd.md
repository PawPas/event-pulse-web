---
project: "EventPulse Web"
version: 1
status: draft
created: 2026-07-11
context_type: greenfield
product_type: web-app
target_scale:
  users: small
  qps: low
  data_volume: small
timeline_budget:
  mvp_weeks: 3
  hard_deadline: null
  after_hours_only: true
---

## Vision & Problem Statement

Small and medium e-commerce and SaaS teams collect customer event data — product views, add-to-cart actions, purchases, logins — but have no fast, affordable path from those raw events to actionable customer segments. Manual RFM analysis in spreadsheets is slow and error-prone. Enterprise analytics platforms (Amplitude, Mixpanel, Snowflake + dbt) are priced and scaled for larger teams and data pipelines. No simple, affordable shared-platform tool bridges the gap between a raw event file and a business-ready RFM segmentation report.

The insight: existing tools are built for high-volume pipelines and large data teams. A product targeting small teams that just want to know who is loyal, at risk, or hibernating — and surfaces that answer in minutes from a file upload — has a clear UX gap to fill at a price point those teams can afford.

## User & Persona

**Primary persona**: A product manager at a small e-commerce or SaaS company. They have customer event data — typically as CSV or JSON exports from their platform — but no data engineering team to process it. When they need to understand customer retention (who is at risk, who is loyal, who needs reactivation), they either do it manually in a spreadsheet or skip it entirely. They know RFM segmentation would be valuable; the barrier is the absence of a simple tool that doesn't require a data warehouse or a per-seat enterprise contract.

## Success Criteria

### Primary
- A new user can register, add customer events (via file upload or the sample data generator), create a report, run RFM analysis, and see the results dashboard — all within 5 minutes of first visit.
- The dashboard correctly shows key metrics (total events, unique customers, segment distribution) and a sortable RFM results table.

### Secondary
- Re-running analysis on an existing report after adding new events works reliably and completes within a reasonable time.

### Guardrails
- No user's event data or reports are visible to any other user's account at any point in the product lifecycle.

## User Stories

### US-01: User analyses customer events and sees RFM segments

- **Given** a logged-in user who has added customer events to a report (via file upload or sample generator)
- **When** they click "Run Analysis"
- **Then** they see a dashboard with: total events count, unique customer count, and a sortable RFM results table showing each customer's Recency, Frequency, Monetary values and their assigned segment (Champions / Loyal Customers / At Risk / Hibernating / others)

#### Acceptance Criteria
- Dashboard renders after analysis completes (status changes from "Analyzing…" to "Completed")
- Every customer in the imported event data appears in the results table
- Re-running analysis after adding events updates the dashboard results

## Functional Requirements

### Authentication
- FR-001: User can register with email and password. Priority: must-have
  > Socrates: Counter-argument considered: "no-auth trial reduces friction before first value." Resolution: kept; private event data requires accounts from day one — cannot be deferred.

- FR-002: User can log in with email and password. Priority: must-have
  > Socrates: Counter-argument considered: "passwordless or OAuth is lower friction and safer." Resolution: kept; email + password is the most universally understood auth model for MVP with no third-party dependency.

- FR-003: User can log out. Priority: must-have
  > Socrates: Counter-argument considered: "solo devs on personal machines rarely log out — overhead with no gain." Resolution: kept; basic session security requires it. Implementation is trivial.

### Reports
- FR-004: User can create a report (with name, optional description). Priority: must-have
  > Socrates: Counter-argument considered: "auto-create a default report on sign-up to remove a step." Resolution: kept as explicit creation; users need to name reports to manage multiple later — naming gives ownership and the form takes seconds.

- FR-005: User can view a list of their reports. Priority: must-have
  > Socrates: Counter-argument considered: "if most users only have 1 report, a list view is wasted dev time." Resolution: kept; the list is the navigation shell — without it there is no way to return to an existing report.

- FR-006: User can open a report to view its detail and results. Priority: must-have
  > Socrates: Clarified: the report view has two states — pre-analysis (shows metadata + "Run Analysis" button) and post-analysis (results replace the button). Same page, two states.

- FR-007: User can delete a report (with a mandatory confirmation step). Priority: must-have
  > Socrates: Counter-argument considered: "delete without confirmation could wipe event data silently." Resolution: modified — deletion must require an explicit confirmation step before any data is removed.

### Event Ingestion
- FR-008: User can add customer events to a report by uploading a CSV or JSON file. Priority: must-have
  > Socrates: Counter-argument considered: "unvalidated file upload produces silent garbage analysis." Resolution: kept; format validation before processing is implied by any correct implementation — no FR change needed, but it must be enforced.

- FR-009: User can add customer events to a report using the built-in sample data generator. Priority: must-have
  > Socrates: Counter-argument considered: "generator adds scope; a downloadable sample CSV achieves the same outcome." Resolution: kept; the generator is a single button click — it's the zero-friction path to first impression and justifies the implementation cost.

### Analysis & Dashboard
- FR-010: User can run RFM analysis on a report. Priority: must-have
  > Socrates: Counter-argument considered: "auto-run on upload removes the manual trigger step." Resolution: kept as manual trigger; users may add events in batches before deciding to run, and the re-run story (FR-011) makes the trigger logical.

- FR-011: User can re-run RFM analysis on a report after adding new events. Priority: must-have
  > Socrates: Combined challenge with FR-010. Resolution: kept; manual trigger supports batching and makes re-run a first-class action rather than an accidental side-effect.

- FR-012: User can view a results dashboard showing key metrics and a sortable RFM results table. Priority: must-have
  > Socrates: Counter-argument considered: "charts add a charting library dependency and 1–2 days of frontend work; a table alone is sufficient to understand segment distribution." Resolution: modified — segment distribution chart demoted to nice-to-have; sortable RFM table is the must-have for MVP.

- FR-012b: User can view a segment distribution chart on the results dashboard. Priority: nice-to-have
  > Socrates: Demoted from FR-012 must-have. Chart is the "aha moment" visually, but the table carries the same information. Add after core analysis is stable.

## Non-Functional Requirements

- Analysis completes within 30 seconds from the moment the user clicks "Run Analysis", for a report containing up to 200,000 events.
- A report cannot contain more than 200,000 events; input that exceeds this cap is rejected before processing begins, with a clear error message stating the limit.
- An uploaded file that is not a valid CSV or JSON structure is rejected before processing begins, with a clear message describing why — no silent failure or partial analysis.
- No user's event data or reports are accessible to any other user's account at any point.
- The product is fully usable on the latest two major versions of Chrome, Firefox, Safari, and Edge (desktop only; no mobile browser requirement for MVP).
- RFM classification and segment assignment are deterministic — the same input always produces the same output.

## Business Logic

**Event schema.** Each uploaded event record must contain four fields: `customer_id` (string), `timestamp` (ISO 8601, e.g. `2024-03-15T10:30:00Z`; UTC assumed when no timezone offset is present), `event_type` (string), and `amount` (decimal; must be 0 for non-purchase events). For CSV uploads the delimiter is a comma and the first row is a header. For JSON uploads the file must be an array of objects, one object per event. Any record missing a required field is rejected before processing begins.

**Purchase events.** Only events where `event_type == "purchase"` contribute to the Monetary dimension. All events regardless of type contribute to the Frequency dimension.

**RFM scoring.** After grouping events by `customer_id`, the application computes three raw values per customer: Recency (days since the customer's most recent event, calculated from the analysis run date), Frequency (total event count), and Monetary (sum of `amount` across purchase events only). Each dimension is then ranked into quintiles across the full customer population in the report, producing an R score, F score, and M score in the range 1–5. Quintile 5 = most favourable (most recent, most frequent, highest spend). Ties within a quintile boundary are assigned the same score. Quintile boundaries are derived from the population being analysed, not from fixed thresholds.

**Segment assignment.** Each customer is assigned to exactly one segment using the following priority-ordered rules (first match wins):

| Segment | Condition |
| --- | --- |
| Champions | R ≥ 4 and F ≥ 4 |
| Loyal Customers | F ≥ 4 and M ≥ 4 |
| Potential Loyalists | R ≥ 4 and F < 4 |
| At Risk | R ≤ 2 and F ≥ 3 |
| Hibernating | R ≤ 2 and F ≤ 2 |
| Others | all remaining customers |

The classification is deterministic: the same input events always produce the same R/F/M scores, the same quintile boundaries, and the same segment assignments. No randomness is introduced.

## Access Control

Users authenticate with email and password. Registration and login are the only entry points — no social login or passwordless auth for MVP. The user model is flat: every registered account has the same capabilities. Each user's reports and event data are private to their account — no cross-account sharing or team workspaces. Unauthenticated routes are limited to the landing page, login, and registration. All product routes require an authenticated session.

## Non-Goals

- No real-time or streaming analysis — batch only; the user submits a file or uses sample data; no live event feeds or continuous ingestion.
- No analytics beyond RFM segmentation — no funnel analysis, cohort retention, predictive ML, or any other analysis type for v1.
- No file export of analysis results — results are viewed in-app only; no PDF, Excel, or CSV download of analysis output.
- No report sharing or team workspaces — each account is strictly private; no collaboration, invite flows, or shared access to reports.
- No integrations with external data sources — no connectors to third-party event platforms; the user brings their own CSV or JSON file.
- No scheduled or automated analysis — analysis is triggered manually by the user every time; no cron or auto-refresh.
- No AI-generated explanations, recommended actions, or next-best-action features — rule-based RFM classification only; no language model involvement.
- No notification or alert system — no email, push, or in-app alerts on segment changes; users check the dashboard manually.
- No mobile browser support — desktop web only for MVP.

## Open Questions

All blocking open questions resolved. No open items remain.
