<!-- PLAN-REVIEW-REPORT -->
# Plan Review: RFM Analysis Dashboard

- **Plan**: context/changes/rfm-analysis-dashboard/plan.md
- **Mode**: Deep
- **Date**: 2026-07-22
- **Verdict**: REVISE
- **Findings**: 1 critical  3 warnings  1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | FAIL |

## Grounding

5/5 existing paths ✓, 3/3 symbols ✓, brief↔plan ✓ — 3 grounding failures: `event_count` not on ORM object (F2); `AsyncSessionLocal` not exported / starts as None (F3); `Column(JSONB)` style inconsistent with codebase (F4).

## Findings

### F1 — Phase 3 Progress missing manual check 3.9

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: ## Progress / Phase 3 / Manual subsection
- **Detail**: Phase 3 "Manual Verification" in the plan body has 8 bullets. The Progress section has only 7 manual rows (3.2–3.8). The 8th bullet — "`monetary` values display with `$` prefix and 2 decimal places" — has no matching `- [ ] 3.9 …` row. `/10x-implement` uses Progress as the single source of truth; this check will never be executed or tracked.
- **Fix**: Add `- [ ] 3.9 monetary values display with $ prefix and 2 decimal places` under `#### Manual` in `### Phase 3:` in Progress.
- **Decision**: FIXED — added `- [ ] 3.9 monetary values display with $ prefix and 2 decimal places` to Progress Phase 3 Manual section

### F2 — `report.event_count` raises AttributeError on bare ORM object

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Completeness
- **Location**: Phase 2 — Analysis router / POST /run contract
- **Detail**: The plan's `POST /run` handler contract says "400 if report.event_count == 0". But `event_count` is NOT a column on the `Report` ORM model (`models/report.py:26-48`). It is a query-time correlated subquery label (`routers/reports.py:34-40`): only `row.event_count` works on row tuples, not `row.Report.event_count`. Accessing `.event_count` on a bare `Report` ORM object raises `AttributeError` → 500.
- **Fix A ⭐ Recommended**: Reuse the `_event_count_sq()` helper from reports.py
  - Strength: One line in the handler; reuses the established pattern at `routers/reports.py:34-50`.
  - Tradeoff: Cross-router import of `_event_count_sq` (private function) — or move it to a shared helper.
  - Confidence: HIGH — confirmed in existing codebase; pattern works and is tested.
  - Blind spot: `_event_count_sq` is underscore-prefixed (private by convention); may warrant moving to a shared module.
- **Fix B**: Inline a separate SELECT COUNT query in the run handler
  - Strength: No cross-router import; self-contained in analysis.py.
  - Tradeoff: Two DB round-trips (COUNT then SELECT Report).
  - Confidence: HIGH — standard SQLAlchemy pattern.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A — plan contract updated to use correlated scalar subquery pattern (same as routers/reports.py:34-50) with `row.event_count` check instead of `report.event_count`

### F3 — `AsyncSessionLocal` export plan is inaccurate (lazy-init gap)

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Completeness
- **Location**: Phase 1 — "Expose AsyncSessionLocal from database.py"
- **Detail**: The plan says "Export `AsyncSessionLocal` as a module-level name — the same async_sessionmaker instance already used by get_db(). If it already exists as a module-level variable, just verify it's accessible; no change needed." Both assertions are wrong. `_session_factory_instance` (`database.py:13`) starts as `None` and is private. Importing it at module-top-level would capture `None`, crashing background tasks with `TypeError: 'NoneType' is not callable`.
- **Fix**: Update Phase 1 to specify adding a `get_session_factory()` getter to `database.py`: `def get_session_factory() -> async_sessionmaker[AsyncSession]: _get_engine(); assert _session_factory_instance is not None; return _session_factory_instance`. Update Phase 2 background task to call `async with get_session_factory()() as db:`.
  - Strength: Mirrors the existing `_get_engine()` lazy-init pattern; safe whether or not a prior request has warmed things up.
  - Tradeoff: One function added instead of a bare module-level name.
  - Confidence: HIGH — only safe pattern given the lazy-init design.
  - Blind spot: None significant.
- **Decision**: FIXED — plan updated to specify `get_session_factory()` getter in database.py; Phase 2 background task contract updated to `async with get_session_factory()() as db:`; Critical Implementation Details updated accordingly

### F4 — `Column(JSONB)` style inconsistent with ORM model

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 — "Report ORM model update"
- **Detail**: The plan specifies `analysis_result = Column(JSONB, nullable=True)`. Every existing column in `models/report.py` (lines 26-43) uses the SQLAlchemy 2.0 `Mapped[T] = mapped_column(...)` form. `Column(...)` is the legacy 1.x style — would work at runtime but is inconsistent.
- **Fix**: Change the plan contract to `analysis_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` (`mapped_column` accepts dialect types like `JSONB` directly).
- **Decision**: FIXED — plan contract updated to `analysis_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` with note to use `mapped_column` not `Column`

### F5 — `test_run_already_analyzing` has no reliable setup path

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 2 — "Integration tests"
- **Detail**: The test matrix includes "POST /run when status is `analyzing` → 409" but gives no setup path. If the test POSTs /run once and re-POSTs immediately, it races the background task — on fast hardware the task may complete before the second POST arrives, yielding 202 instead of 409.
- **Fix**: Add a note specifying direct DB UPDATE to set `report.status = 'analyzing'` rather than relying on timing.
- **Decision**: FIXED — test contract updated to specify direct DB UPDATE to set status = 'analyzing' before the POST call
