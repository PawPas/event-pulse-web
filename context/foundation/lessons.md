# Lessons Learned

> Append-only register of recurring rules and patterns. Re-read at start by /10x-frame, /10x-research, /10x-plan, /10x-plan-review, /10x-implement, /10x-impl-review.

## Wrap localStorage JSON.parse in a safe helper to prevent startup crashes

**Context**: Any code that calls `JSON.parse` at module load time or app initialisation — especially Redux slice `initialState`, framework bootstrapping, or any singleton that runs before an error boundary is mounted.

**Problem**: `JSON.parse(localStorage.getItem("key") ?? "null")` throws synchronously if the stored value is corrupted (browser extension write, quota truncation, manual edit, stale format after a schema change). When called during Redux store creation, this crashes the entire app before React can mount — the user sees a blank white screen with no recovery path.

**Rule**: Never call `JSON.parse` directly on `localStorage` values at app initialisation. Always use a safe wrapper that catches parse errors and returns a typed fallback. Use `safeJsonParse<T>(value, fallback)` from `frontend/src/utils/safeJsonParse.ts`. Any new slice that reads structured data from `localStorage` as its initial state must go through this helper.

**Applies to**: `implement`, `impl-review`

## Convert avoidable 500s to 4xx at the plan stage

**Context**: Any code path that handles untrusted external input — file uploads, API request bodies, external API responses, database reads of user-supplied data — where a decoding, parsing, or type-checking step can throw an unhandled exception.

**Problem**: Without an explicit plan contract, implementers focus on the happy path. Edge inputs (None filename, non-UTF-8 encoding, non-dict JSON items) cause unhandled exceptions that FastAPI surfaces as 500. These are always fixable with a try/except or a None guard, but they're easy to miss when the contract doesn't call them out.

**Rule**: During plan review (`plan-review`) and implementation review (`impl-review`), scan every inbound data boundary for cases where a Python built-in (`str.endswith`, `bytes.decode`, dict key access) can raise on unexpected but plausible input. Add the 4xx response to the plan contract before implementation begins. Costs one line to specify; costs an incident to discover in production.

**Applies to**: `plan`, `plan-review`, `impl-review`
