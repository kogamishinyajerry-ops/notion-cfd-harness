---
phase: 31-pipeline-rest-api-react-dashboard
reviewed: 2026-04-12T08:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - api_server/routers/pipelines.py
  - api_server/models.py
  - api_server/services/pipeline_executor.py
  - dashboard/src/pages/PipelinesPage.tsx
  - dashboard/src/pages/PipelineDetailPage.tsx
  - dashboard/src/pages/PipelineCreatePage.tsx
  - dashboard/src/services/pipelineWs.ts
  - dashboard/src/services/types.ts
  - dashboard/src/services/api.ts
  - dashboard/src/services/config.ts
  - dashboard/src/router.tsx
  - dashboard/src/layouts/MainLayout.tsx
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-04-12T08:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 31 delivers the Pipeline REST API and React Dashboard with solid architecture. Three logic bugs were found: a field-name mismatch between frontend `id` and backend `step_id` that will cause Pydantic validation errors on pipeline creation, a race condition in executor registration that allows duplicate executors, and a pause/resume race that can cause executor deadlock. Four informational items cover non-blocking cancel, duplicate step-name IDs, missing auth guards, and orphaned dependencies when step names change.

---

## Warnings

### WR-01: Pipeline creation sends `id` instead of `step_id` — Pydantic validation error

**File:** `dashboard/src/services/api.ts:175`
**Line:** ~175 (createPipeline payload)
**Issue:** `createPipeline` builds the steps payload using `step_id: s.id` (the frontend `PipelineStep.id` field), but the backend `PipelineCreate.PipelineStep` model defines the field as `step_id: str`. Frontend `types.ts:165` defines `id: string` on `PipelineStep`, while backend `models.py:333` defines `step_id: str`. These names do not match, so Pydantic validation on the backend will reject incoming requests with a 422 validation error whenever a user tries to create a pipeline.
**Fix:**

The `createPipeline` method should map `s.id` to `step_id` in the payload. Change line 175 in `api.ts`:

```typescript
// api.ts createPipeline — fix field name
steps: steps.map((s, i) => ({
  step_id: s.id,    // s.id is the frontend field; backend expects step_id
  step_type: s.step_type,
  step_order: i,
  depends_on: dag[s.id] || [],
  params: JSON.parse(s.params || '{}'),
})),
```

---

### WR-02: `start_pipeline_executor` has a race allowing duplicate executors

**File:** `api_server/services/pipeline_executor.py:353-361`
**Issue:** The lock is released between the duplicate check and the dictionary write:

```python
def start_pipeline_executor(pipeline_id: str, loop: asyncio.AbstractEventLoop) -> PipelineExecutor:
    with _ACTIVE_EXECUTORS_LOCK:
        if pipeline_id in _ACTIVE_EXECUTORS:       # line 356 — checked under lock
            raise ValueError(...)
        executor = PipelineExecutor(pipeline_id, loop)
        _ACTIVE_EXECUTORS[pipeline_id] = executor   # line 359 — INSIDE lock
    executor.start()                               # line 360 — OUTSIDE lock
    return executor
```

Two concurrent calls with the same `pipeline_id` can both pass the `if pipeline_id in _ACTIVE_EXECUTORS` check before either writes to the dict, resulting in two `PipelineExecutor` threads running simultaneously for the same pipeline. This causes undefined behavior: two threads executing the same DAG steps concurrently.
**Fix:**

Move `executor.start()` inside the lock, or re-check under lock after `executor.start()`:

```python
def start_pipeline_executor(pipeline_id: str, loop: asyncio.AbstractEventLoop) -> PipelineExecutor:
    with _ACTIVE_EXECUTORS_LOCK:
        if pipeline_id in _ACTIVE_EXECUTORS:
            raise ValueError(f"Pipeline {pipeline_id} is already running")
        executor = PipelineExecutor(pipeline_id, loop)
        _ACTIVE_EXECUTORS[pipeline_id] = executor
        executor.start()    # move inside lock to prevent the race
    return executor
```

---

### WR-03: Pause/resume race can deadlock executor on a single step

**File:** `api_server/services/pipeline_executor.py:239-242`
**Issue:** If `resume()` is called while a step body is still executing (between steps), the sequence is:

1. `pause()` sets `pause_event`; step N finishes; `_paused = True`
2. `resume()` is called (from another thread/API call) — clears `pause_event`, sets `_paused = False`
3. `pause_event.wait()` at line 241 blocks forever — the event was already cleared by step 2

The executor thread is deadlocked inside a single step's execution window. The `is_paused` check at line 239 evaluates `pause_event.is_set()` (False, cleared), so execution does not wait at line 239. But `pause_event.wait()` at line 241 blocks indefinitely because `resume()` already cleared the event before this thread reached `wait()`.
**Fix:**

Use a separate `_pause_requested` flag with the wait pattern:

```python
# In pause():
self._pause_requested = True
self.pause_event.set()

# In resume():
self._pause_requested = False
self.pause_event.clear()

# In step loop — replace is_set() check with a loop that re-checks _pause_requested:
while self._pause_requested:
    logger.info(f"PipelineExecutor {self.pipeline_id}: paused, waiting...")
    self.pause_event.wait()
    if self._pause_requested:
        # Spurious wake — still paused
        pass
    logger.info(f"PipelineExecutor {self.pipeline_id}: resumed")
```

---

## Info

### IN-01: `cancel_and_cleanup` does not block — cancel response is sent before cleanup completes

**File:** `api_server/routers/pipelines.py:178-200`
**Issue:** `cancel_pipeline` calls `await cleanup.cancel_and_cleanup(pipeline_id)` and returns `{"status": "cancelling", ...}` immediately. The cleanup (stopping containers, updating DB state) is still in progress when the HTTP response is sent. If the client immediately calls `getPipeline`, they may see the pipeline still in a running state.
**Note:** This is a design choice (non-blocking cancel). The client does `await apiClient.cancelPipeline()` and then `await loadPipeline()`, so the UI waits correctly. However, concurrent API callers could observe stale state.
**Suggestion:** Consider returning `202 Accepted` with a `Location` header pointing to the pipeline status, or add a `cancellation_in_progress` sub-status to the pipeline model.

---

### IN-02: Duplicate step names produce duplicate step IDs — database constraint violation

**File:** `dashboard/src/services/api.ts:175` (createPipeline)
**Issue:** `makeStepId(name, index)` slugifies the step name and appends a zero-padded index. If two steps have the same name (e.g., both named "Mesh"), their IDs will both be `mesh_01` (assuming index 0 and index 1 both produce `mesh_01` with pad-start). The backend `step_id` is the primary key for `PipelineStep` in the DAG; duplicate IDs will cause a database integrity error on `create_pipeline`.
**Suggestion:** Add validation in the frontend `PipelineCreatePage` to disallow duplicate step names before submission. Alternatively, make the ID generation include a UUID suffix to guarantee uniqueness.

---

### IN-03: Missing authentication guards on pipeline endpoints

**File:** `api_server/routers/pipelines.py` (all endpoints)
**Issue:** All pipeline endpoints (create, list, get, update, delete, start, pause, resume, cancel) are defined as bare `@router.post/get/put/delete` with no `Depends` auth dependency. Any client can manage any pipeline. This is acceptable if the project intends to handle auth at a middleware or network level, but if per-endpoint auth is intended, `get_current_user` or a session-validated dependency should be applied.
**Suggestion:** Add an `get_current_user` dependency to all pipeline endpoints if per-user authorization is required. For now, this is informational since the project's auth strategy (middleware vs. route-level) is not known from this phase.

---

### IN-04: Step name change orphans `depends_on` references — no validation on update

**File:** `dashboard/src/pages/PipelineCreatePage.tsx:104-118` (updateStep)
**Issue:** When a step's `name` field is updated, `updateStep` regenerates the step's `id` from the new name via `makeStepId`. Any other step that listed this step in `depends_on` still references the old ID. The resulting payload has a DAG where a `depends_on` entry points to a step ID that does not exist, causing a `ValueError` in `topological_sort` (`Step 'X' depends on unknown step 'Y'`).
**Note:** The UI only creates pipelines (not editing existing ones), so this is a latent bug for the edit scenario. The current `PipelineUpdate` model in `models.py:364` does not include `steps`, so step-level updates are not yet supported — this will become active when step editing is added.
**Suggestion:** When editing step names, automatically update all `depends_on` references that pointed to the old name to now point to the new name. Validate the DAG after every name change and show a user-visible error before submission.

---

*Reviewer: Claude (gsd-code-reviewer)*
*Phase: 31-pipeline-rest-api-react-dashboard*
