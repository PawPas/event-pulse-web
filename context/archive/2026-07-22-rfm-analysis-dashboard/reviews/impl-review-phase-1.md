<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: RFM Analysis Dashboard

- **Plan**: context/changes/rfm-analysis-dashboard/plan.md
- **Scope**: Phase 1 of 3
- **Date**: 2026-07-24
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical  3 warnings  3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — ORM model uses JSON instead of JSONB

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence
- **Location**: models/report.py:38
- **Detail**: Plan specified `mapped_column(JSONB, nullable=True)` with JSONB from `sqlalchemy.dialects.postgresql`. The migration correctly uses JSONB at the DB level. The ORM model uses generic `JSON` — the change was deliberate to fix the SQLite in-memory test backend incompatibility. Consequences: (1) autogenerate may emit a spurious ALTER COLUMN; (2) JSONB-specific operators not signalled to SQLAlchemy.
- **Fix A ⭐ Recommended**: Use `JSONB().with_variant(JSON(), "sqlite")` as the column type — JSONB is base type for PostgreSQL; variant swaps to JSON for SQLite only.
  - Strength: Fixes ORM/migration inconsistency without breaking tests; one-line change; documented SQLAlchemy idiom.
  - Tradeoff: Two import lines (JSON from sqlalchemy + JSONB from dialects.postgresql).
  - Confidence: HIGH — `with_variant` is the documented idiom for this scenario.
  - Blind spot: None significant.
- **Fix B**: Keep JSON in ORM, add a comment explaining the deliberate choice.
  - Strength: Zero code change; honest documentation.
  - Tradeoff: Autogenerate risk stays; model doesn't express the actual PostgreSQL type.
  - Confidence: MEDIUM — acceptable at MVP but will cause friction later.
  - Blind spot: Autogenerate false-positives not yet observed.
- **Decision**: FIXED via Fix A — `mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)`

### F2 — bare `assert` eliminated under Python -O flag

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: database.py:34 (also database.py:40 — same pattern in get_db)
- **Detail**: `get_session_factory()` uses `assert _session_factory_instance is not None` after calling `_get_engine()`. Under `python -O` or `PYTHONOPTIMIZE=1`, all assert statements are stripped — the guard vanishes and becomes a silent AttributeError. The new function introduced this; `get_db()` had it already.
- **Fix**: Replace both asserts with explicit RuntimeError guards: `if _session_factory_instance is None: raise RuntimeError("Session factory was not initialised")` — consistent with how `_get_engine()` itself raises RuntimeError for missing DATABASE_URL.
- **Decision**: FIXED — replaced assert with explicit RuntimeError guard in both get_session_factory() and get_db()

### F3 — float(amount) loses Decimal precision in monetary accumulator

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: services/rfm.py:54 (init), services/rfm.py:61 (cast)
- **Detail**: Monetary accumulator is initialised as `0.0` (float) and amounts added via `float(amount)`. The event model stores amount as NUMERIC (Decimal); test fixture passes `Decimal("50.00")`. Converting Decimal→float before accumulating introduces IEEE 754 rounding errors that compound across events. Could cause different quintile assignments at boundary values. Final JSON payload must be float (JSON has no Decimal type) so conversion is needed — but at serialisation, not accumulation.
- **Fix**: Accumulate as Decimal; convert at return time. `"monetary": Decimal(0)` at line 54; remove `float()` on line 61; convert in result dict: `"monetary": float(data["monetary"])`. Import `Decimal` from `decimal`.
  - Strength: Monetary accumulation stays precise; conversion happens once at the JSON boundary.
  - Tradeoff: Adds one import line; otherwise identical logic.
  - Confidence: HIGH — Decimal accumulation for monetary data is the Python standard.
  - Blind spot: Float precision at quintile cut-point boundary not measured — may be moot in practice.
- **Decision**: FIXED — monetary accumulator changed to Decimal(0); float() conversion moved to return dict

### F4 — Segment rule list typed as Any instead of Callable

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: services/rfm.py:6
- **Detail**: `_SEGMENT_RULES: list[tuple[str, Any]]` — `Any` disables type checking on the callable. The lambda signature `(r, f, m) -> bool` is well-defined.
- **Fix**: Type as `list[tuple[str, Callable[[int, int, int], bool]]]` and import `Callable` from `collections.abc`.
- **Decision**: FIXED — replaced Any with Callable[[int, int, int], bool]; import Callable from collections.abc

### F5 — statistics.quantiles called without method='exclusive'

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: services/rfm.py:26
- **Detail**: The test file fixture comment explicitly documents cut-points as `method='exclusive'` output. The call relies on the Python default (exclusive since 3.8) but doesn't state it.
- **Fix**: `quantiles(values, n=5, method='exclusive')` — one argument added.
- **Decision**: SKIPPED

### F6 — Unit tests have no pytest marker for future test split

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: tests/test_rfm_algorithm.py
- **Detail**: Integration tests use module-scoped fixtures; pure unit tests here have no marker. If the project adopts a unit/integration split strategy, these tests will have no marker.
- **Fix**: Defer — add `pytestmark = pytest.mark.unit` when the project adopts a unit/integration split strategy.
- **Decision**: SKIPPED — defer until project adopts test split strategy
