<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Auth Flows — Phase 3

- **Plan**: `context/changes/auth-flows/plan.md`
- **Scope**: Phase 3 of 3
- **Date**: 2026-07-20
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical  4 warnings  3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — JSON.parse on localStorage crashes app at startup

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: `frontend/src/store/authSlice.ts:16`
- **Detail**: `JSON.parse(localStorage.getItem("user") ?? "null")` runs synchronously at Redux store initialisation. If the stored value is corrupted (manually edited, written by a browser extension, or truncated by a quota error), `JSON.parse` throws and the entire app fails to mount — before React can display anything.
- **Fix**: Wrap in a safe-parse helper:
  ```ts
  function safeParseUser(): AuthUser | null {
    try { return JSON.parse(localStorage.getItem("user") ?? "null") }
    catch { return null }
  }
  // initialState: user: safeParseUser()
  ```
- **Decision**: FIXED via safeJsonParse<T> generic helper in frontend/src/utils/safeJsonParse.ts; authSlice.ts updated. Lesson recorded in context/foundation/lessons.md.

### F2 — `as` cast on `unknown` error in Login and Register

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: `frontend/src/pages/Login.tsx:23`, `frontend/src/pages/Register.tsx:25`
- **Detail**: Both catch blocks cast `err as { status?: number; detail?: string }` without a runtime check. When `apiFetch` throws our custom object this is fine; but a native `Error` (DNS failure, CORS block before server responds) is also `unknown` — the cast silences TypeScript and `e.status` will always be `undefined` for native errors. The null-coalescing fallbacks (`?? 'Login failed'`) happen to produce acceptable UX, but the cast hides the type mismatch.
- **Fix**: Replace cast with a narrow type-guard:
  ```ts
  function isApiError(e: unknown): e is { status?: number; detail?: string } {
    return typeof e === 'object' && e !== null
  }
  // then: if (isApiError(err)) { ... }
  ```
- **Decision**: FIXED — replaced `as` cast with `instanceof ApiError` check in Login.tsx and Register.tsx.

### F3 — `apiFetch` throws a plain object, not an Error subclass

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: `frontend/src/api/client.ts:17`
- **Detail**: `throw { status, detail }` produces a value with no stack trace and no `instanceof Error` identity. Generic error boundaries and future `catch` clauses that check `err instanceof Error` will silently miss it. `console.error` shows `[object Object]` with no source location in some browsers.
- **Fix**: Introduce a minimal `ApiError` class:
  ```ts
  export class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail); this.name = 'ApiError'
    }
  }
  // throw new ApiError(response.status, body.detail ?? response.statusText)
  ```
  Then Login/Register catch clauses can use `instanceof ApiError` cleanly.
- **Decision**: FIXED — introduced ApiError class (explicit fields, no parameter properties due to erasableSyntaxOnly) in client.ts; apiFetch now throws new ApiError(...).

### F4 — No double-submit guard on Login and Register forms

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: `frontend/src/pages/Login.tsx:14`, `frontend/src/pages/Register.tsx:14`
- **Detail**: `handleSubmit` is async with no in-flight flag. Double-click or rapid Enter fires two concurrent requests. On login this wastes a round trip; on register there is a small race window where two requests both pass the uniqueness check before either commits, potentially creating a duplicate account (database unique constraint will catch the second, but it produces a confusing 409 mid-session).
- **Fix**: Add `const [loading, setLoading] = useState(false)`, guard the handler with early return if loading, set `true` before `apiFetch`, clear in a `finally` block, and bind `<button disabled={loading}>`.
- **Decision**: FIXED — added loading state + if (loading) return guard + disabled={loading} button in Login.tsx and Register.tsx.

### F5 — `database.py` modified outside Phase 3 scope

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: `database.py` (unstaged)
- **Detail**: Phase 3 is frontend-only, but `database.py` was modified during manual testing (added `pool_pre_ping=True` to fix intermittent 500 errors from stale asyncpg connections to Railway). The change is valid and necessary — it should simply be committed with a clear message rather than left floating in the working tree or silently bundled into the Phase 3 frontend commit.
- **Fix**: Commit `database.py` separately with a `fix:` prefix before or after the Phase 3 commit.
- **Decision**: FIXED — committed separately as fix: 1ff78dc.

### F6 — Inline error renders above submit button, plan said below

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: `frontend/src/pages/Login.tsx:54`, `frontend/src/pages/Register.tsx:54`
- **Detail**: Plan specified error rendered "below the form submit button." Both Login and Register render the error `<p>` one JSX line above `<button type="submit">`. Functionally equivalent and consistently applied across both pages, but it is cosmetically opposite to the spec.
- **Fix**: Move the `{error && <p>}` block to after the `<button>` in both files — two-line JSX reorder.
- **Decision**: FIXED — error <p> moved to after the button in both Login.tsx and Register.tsx.

### F7 — ProtectedRoute has no guard for future async auth rehydration

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architecture
- **Location**: `frontend/src/components/ProtectedRoute.tsx:11`
- **Detail**: `authSlice` initialises `token` synchronously from `localStorage.getItem`, so there is genuinely no async gap right now — the current implementation is correct. However, if auth ever acquires an async step (token refresh, remote session validation), the component will redirect to `/login` before the token resolves, logging users out on every refresh. The pattern is safe today but brittle for any future change.
- **Fix**: Document the sync-only assumption with a comment in `authSlice.ts` initial state — no code change needed now. If async auth is added later, add an `isInitialising: true` flag to `AuthState` and guard `ProtectedRoute` with `if (isInitialising) return null`.
- **Decision**: FIXED — sync-only assumption documented with comment in authSlice.ts initialState block.
