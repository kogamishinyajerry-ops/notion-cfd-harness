---
phase: 32-po-02-parametric-sweep
reviewed: 2026-04-12T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - api_server/models.py
  - api_server/services/pipeline_db.py
  - api_server/services/sweep_runner.py
  - api_server/main.py
  - api_server/routers/sweeps.py
  - api_server/routers/__init__.py
  - dashboard/src/services/types.ts
  - dashboard/src/services/api.ts
  - dashboard/src/pages/SweepsPage.tsx
  - dashboard/src/pages/SweepsPage.css
  - dashboard/src/pages/SweepCreatePage.tsx
  - dashboard/src/pages/SweepCreatePage.css
  - dashboard/src/pages/SweepDetailPage.tsx
  - dashboard/src/pages/SweepDetailPage.css
  - dashboard/src/router.tsx
  - dashboard/src/layouts/MainLayout.tsx
  - dashboard/src/theme.css
  - dashboard/src/pages/index.ts
findings:
  critical: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 32: Code Review Report

**Reviewed:** 2026-04-12T00:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 32 adds the full parametric sweep feature: `SweepRunner` (asyncio + semaphore concurrency), a REST router with 6 endpoints, `SweepDBService` (SQLite CRUD with schema v3 migration), and three React pages (SweepsPage, SweepCreatePage, SweepDetailPage). The overall architecture is clean and consistent with the existing pipeline pattern.

One critical defect was found: a systematic casing mismatch between the Python enum serialization (lowercase strings) and the TypeScript type definitions and UI comparisons (uppercase strings). This breaks all status-dependent behaviour in the sweep UI — filter buttons, start/cancel button visibility, progress polling termination, and CSS class assignments. Four warnings cover a parameter parsing bug that silently injects zero values, a premature object-URL revoke that can fail CSV downloads, a deprecated asyncio API call, and an incomplete `completed_combinations` counter on cancellation. Four informational items cover dead code and minor semantic inconsistencies.

---

## Critical Issues

### CR-01: Enum casing mismatch — backend serializes lowercase, frontend expects uppercase

**Files:**
- `api_server/models.py:398-414` (enum definitions)
- `dashboard/src/services/types.ts:216-217` (type definitions)
- `dashboard/src/pages/SweepDetailPage.tsx:93,189,194,251`
- `dashboard/src/pages/SweepsPage.tsx:7-13,71,130`

**Issue:** The Python `SweepStatus` and `SweepCaseStatus` enums use lowercase string values (`"pending"`, `"running"`, `"completed"`, `"failed"`, `"cancelled"`, `"queued"`). With `use_enum_values = True` on `SweepResponse` and `SweepCaseResponse`, the JSON API response serializes these as lowercase. The TypeScript types and all UI comparisons use uppercase (`'PENDING'`, `'RUNNING'`, `'COMPLETED'`, `'FAILED'`, `'CANCELLED'`, `'QUEUED'`). This breaks:

1. **Polling never terminates** (`SweepDetailPage.tsx:93`): `terminal.includes(sweep.status)` compares `'COMPLETED'` against `"completed"` — never matches, so the 10-second interval never stops even after the sweep finishes.
2. **Start/cancel buttons never show** (`SweepDetailPage.tsx:189,194`): `sweep.status === 'PENDING'` and `sweep.status === 'RUNNING'` both fail against lowercase values.
3. **Summary tab condition wrong** (`SweepDetailPage.tsx:251`): `sweep.status !== 'COMPLETED'` never matches `"completed"`, so the summary table is permanently hidden.
4. **Status filter broken** (`SweepsPage.tsx:71`): `s.status === filter` where filter is `'RUNNING'` vs actual `"running"` — filters return no results.
5. **CSS border classes wrong** (`SweepsPage.tsx:116`): `border-left-${sweep.status.toLowerCase()}` calls `.toLowerCase()` on an already-lowercase string — the CSS classes like `.border-left-pending` are in the stylesheet, so this one accidentally works. But `SweepDetailPage.tsx:224` has the same pattern for combination cards.

**Fix:** Align the enum values to match the TypeScript types (change Python enum values to UPPERCASE), or change all TypeScript types and comparisons to lowercase. The simpler, lower-risk fix is to update the Python enum values to uppercase to match the existing TS contract:

```python
# api_server/models.py
class SweepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class SweepCaseStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
```

Also update the SQLite `DEFAULT` values in `pipeline_db.py` schema v3 (lines 146, 163) and all `status.value` comparisons in `sweeps.py` (e.g. line 146) and `sweep_runner.py` to match.

---

## Warnings

### WR-01: `parseParamGrid` silently injects `0` for empty comma-separated slots

**File:** `dashboard/src/pages/SweepCreatePage.tsx:16-22`

**Issue:** The filter `.filter((v) => v !== '')` runs after the number-coercion map. For an empty token (e.g., `"1,,3"` splits to `['1', '', '3']`), the empty string `''` is coerced via `Number('') → 0` (not NaN), so the filter `0 !== ''` passes and `0` is silently included in the parameter list. A user typing `"1,,3"` gets `[1, 0, 3]` instead of `[1, 3]`, adding an unintended zero-valued combination.

**Fix:** Move the empty-string check before coercion:

```typescript
const vals = row.values.split(',').map((v) => v.trim()).filter((v) => v !== '').map((v) => {
  const num = Number(v);
  return isNaN(num) ? v : num;
});
```

### WR-02: Premature `URL.revokeObjectURL` can abort CSV download in some browsers

**File:** `dashboard/src/pages/SweepDetailPage.tsx:44-50`

**Issue:** `URL.revokeObjectURL(url)` is called synchronously on the line immediately after `a.click()`. The `click()` call triggers the download asynchronously; revoking the object URL before the browser has finished reading it can silently fail the download in Firefox and Safari. Chrome buffers the blob before the revoke takes effect, so it works there, masking the bug.

**Fix:** Revoke inside a short timeout so the browser has time to initiate the download:

```typescript
a.click();
setTimeout(() => URL.revokeObjectURL(url), 100);
```

### WR-03: `asyncio.get_event_loop()` deprecated in Python 3.10+

**File:** `api_server/services/sweep_runner.py:154`

**Issue:** `asyncio.get_event_loop()` is deprecated since Python 3.10 and emits a `DeprecationWarning` when called from a running async context (which `_run_case` is). The call is inside `asyncio.run()` → `_execute()` → `_run_case()`, so the running loop is always available via `asyncio.get_running_loop()`.

**Fix:**
```python
loop = asyncio.get_running_loop()
start_pipeline_executor(new_pipeline.id, loop)
```

### WR-04: `completed_combinations` under-counted when sweep is cancelled during polling

**File:** `api_server/services/sweep_runner.py:163-196`

**Issue:** Inside `_run_case`, when `is_cancelled()` becomes true during the polling loop (line 164), the loop breaks and execution falls to the cancellation check at line 198. `increment_completed` is not called for this case. Each case that is in-flight at the moment of cancellation leaves `completed_combinations` one short per case. On the sweep list page and detail progress bar, the counter would display an incorrect low number even after the sweep reaches `CANCELLED`.

**Fix:** Call `increment_completed` when a case exits due to cancellation:

```python
if self.is_cancelled():
    cancel_pipeline_executor(new_pipeline.id)
    self._db.increment_completed(self.sweep_id)  # account for cancelled case
```

---

## Info

### IN-01: `init_pipeline_db()` called twice in lifespan — second call is dead code

**File:** `api_server/main.py:46,50`

**Issue:** `init_pipeline_db()` is called at line 46 and again at line 50 with a comment "idempotent". The `_INITIALIZED` guard in `init_pipeline_db()` makes the second call a no-op. The second call and its log message are dead code and add confusion.

**Fix:** Remove the duplicate call (lines 50-51) and update the single log message to mention that schema v3 (sweeps) is included.

### IN-02: Step insert uses `PipelineStatus.PENDING` instead of `StepStatus.PENDING`

**File:** `api_server/services/pipeline_db.py:220`

**Issue:** When inserting pipeline steps, the status is set with `PipelineStatus.PENDING.value` instead of `StepStatus.PENDING.value`. Both evaluate to `"pending"`, so there is no runtime error, but the semantic intent is wrong and will cause confusion if enum values ever diverge.

**Fix:**
```python
StepStatus.PENDING.value,  # was: PipelineStatus.PENDING.value
```

### IN-03: `routers/__init__.py` `__all__` is incomplete

**File:** `api_server/routers/__init__.py:7-9`

**Issue:** `__all__` lists only `["cases", "jobs", "knowledge", "status", "sweeps"]`. The `auth`, `websocket`, `visualization`, and `pipelines` routers are imported in `main.py` directly from `api_server.routers` but are not exported in `__all__`. This does not affect runtime behaviour but makes the public API of the package misleading.

**Fix:** Add the missing routers to `__all__`:
```python
__all__ = ["cases", "jobs", "knowledge", "status", "sweeps", "auth", "websocket", "visualization", "pipelines"]
```

### IN-04: `SweepsPage` status filter omits `CANCELLED` status

**File:** `dashboard/src/pages/SweepsPage.tsx:7-13`

**Issue:** `STATUS_FILTERS` includes `PENDING`, `RUNNING`, `COMPLETED`, and `FAILED` but omits `CANCELLED`. Users cannot filter for cancelled sweeps, even though `CANCELLED` is a valid terminal state reachable via the cancel endpoint and the `SweepStatus` type includes it.

**Fix:** Add the missing filter entry:
```typescript
{ label: 'CANCELLED', value: 'CANCELLED' },
```

---

_Reviewed: 2026-04-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
