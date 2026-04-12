---
phase: 30-po-01-orchestration-engine
reviewed: 2026-04-12T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - api_server/main.py
  - api_server/models.py
  - api_server/routers/pipelines.py
  - api_server/routers/websocket.py
  - api_server/services/cleanup_handler.py
  - api_server/services/pipeline_db.py
  - api_server/services/pipeline_executor.py
  - api_server/services/pipeline_websocket.py
  - api_server/services/step_wrappers.py
  - tests/test_cleanup_handler.py
  - tests/test_pipeline_control.py
  - tests/test_pipeline_executor_e2e.py
  - tests/test_pipeline_state_machine.py
  - tests/test_pipeline_websocket.py
  - tests/test_step_wrappers.py
findings:
  critical: 2
  warning: 5
  info: 6
  total: 13
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-04-12
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Reviewed the orchestration engine (pipeline executor, WebSocket event bus, step wrappers, cleanup handler, REST endpoints) and associated tests. Found 2 critical security issues, 5 warnings, and 6 informational items. The architecture is well-designed with clear separation of concerns (DAG execution, Docker ownership, event streaming). Tests are comprehensive. The critical issues should be addressed before production use.

## Critical Issues

### CR-01: Pipeline WebSocket endpoint has no authentication

**File:** `api_server/routers/websocket.py:136-209`
**Issue:** The `/ws/pipelines/{pipeline_id}` endpoint accepts any WebSocket connection without verifying client identity. After checking the pipeline exists in the DB (line 168-171), it immediately calls `await websocket.accept()`. There is no JWT validation, no session check, and no ownership check (any user can subscribe to any pipeline's events).

**Fix:**
```python
# After line 171 (websocket.accept()), add auth check:
from api_server.auth.rbac_middleware import get_current_user_from_ws_token
token = websocket.query_params.get("token")
if token:
    try:
        user = await get_current_user_from_ws_token(token)
        # Optionally verify pipeline ownership:
        # if pipeline.owner_id != user.user_id:
        #     await websocket.close(code=4003, reason="Forbidden")
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
else:
    # Decide policy: reject anonymous or allow
    await websocket.close(code=4001, reason="Authentication required")
```

---

### CR-02: `pipeline_id` not validated before use in shell commands

**File:** `api_server/services/cleanup_handler.py:33-36`
**Issue:** `pipeline_id` is passed directly into a subprocess command list without validation. A malicious or malformed `pipeline_id` could cause unexpected behavior in the `docker ps --filter label=pipeline_id=<id>` command.

```python
result = subprocess.run(
    ["docker", "ps", "-q", "--filter", f"label=pipeline_id={pipeline_id}"],
    # pipeline_id is not validated — could contain spaces, quotes, etc.
```

While the docker CLI itself sanitizes this, the pattern of passing unsanitized user input into shell commands is risky.

**Fix:**
```python
# Validate pipeline_id format before use
import re
PIPELINE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")

def _get_pipeline_containers(self, pipeline_id: str) -> List[str]:
    if not PIPELINE_ID_PATTERN.match(pipeline_id):
        logger.warning(f"Invalid pipeline_id format: {pipeline_id}")
        return []
    # ... proceed with docker command
```

---

## Warnings

### WR-01: `StepType.REPORT` not mapped in pipeline status tracking

**File:** `api_server/services/pipeline_executor.py:125-131`
**Issue:** `_STEP_TYPE_TO_PIPELINE_STATUS` does not include `StepType.REPORT`. When a REPORT step runs, `pipeline_state` defaults to `PipelineStatus.RUNNING` instead of `PipelineStatus.REPORTING`, so the pipeline's reported status during the report generation phase is misleading.

```python
_STEP_TYPE_TO_PIPELINE_STATUS: Dict[StepType, PipelineStatus] = {
    StepType.GENERATE: PipelineStatus.RUNNING,
    StepType.RUN: PipelineStatus.RUNNING,
    StepType.MONITOR: PipelineStatus.MONITORING,
    StepType.VISUALIZE: PipelineStatus.VISUALIZING,
    StepType.REPORT: PipelineStatus.REPORTING,  # <-- MISSING
}
```

**Fix:** Add the missing entry to the dictionary.

---

### WR-02: `list_pipelines()` makes N+1 database queries

**File:** `api_server/services/pipeline_db.py:226-239`
**Issue:** `list_pipelines()` first fetches all pipeline IDs (1 query), then calls `get_pipeline(pid)` for each ID in a loop (N additional queries). For a server with many pipelines, this is inefficient.

```python
def list_pipelines(self) -> List[PipelineResponse]:
    cursor.execute("SELECT id FROM pipelines ORDER BY created_at DESC")
    ids = [r["id"] for r in cursor.fetchall()]  # Query 1
    results = []
    for pid in ids:
        p = self.get_pipeline(pid)  # N additional queries
```

**Fix:** Refactor to fetch all pipeline rows with steps in 2 queries total using JOINs, or batch the step fetching.

---

### WR-03: `JobService` instantiated directly instead of using singleton getter

**File:** `api_server/services/step_wrappers.py:214`
**Issue:** `run_wrapper` creates a new `JobService()` instance on every step execution instead of using the existing singleton pattern (`get_job_service()`). This bypasses any state that might exist on the singleton instance and creates inconsistent behavior compared to other call sites that use the singleton.

```python
job_service = JobService()  # Should use get_job_service()
```

**Fix:**
```python
from api_server.services.job_service import get_job_service
job_service = get_job_service()
```

---

### WR-04: `_STEP_CACHE` grows unbounded within server session

**File:** `api_server/services/step_wrappers.py:56`
**Issue:** The idempotency cache (`_STEP_CACHE`) uses an unbounded `Dict` with no TTL, size limit, or eviction policy. During a long server session with many unique (step_id, params) combinations, memory usage grows indefinitely. The cache is noted as surviving "within server session" but has no cleanup.

**Fix:** Add a maximum cache size with LRU eviction, or document that the cache is intentionally unbounded and the server must be restarted periodically to clear it.

---

### WR-05: `run_wrapper` hardcoded timeout (7200s) overrides user-provided timeout_seconds

**File:** `api_server/services/step_wrappers.py:231-232`
**Issue:** The comment states "2 hours — acceptable for CFD solver duration" and uses a hardcoded `max_wait = 7200`, ignoring any `timeout_seconds` the user might pass in `params`. The `params.get("timeout_seconds", 7200)` pattern is not implemented; instead it uses a fixed constant.

```python
poll_interval = 5.0   # seconds
max_wait = 7200       # hardcoded; user-provided timeout_seconds is ignored
```

**Fix:**
```python
max_wait = params.get("timeout_seconds", 7200)
```

---

## Info

### IN-01: Dead code — `make_linear_pipeline` references non-existent `StepType.to_model()`

**File:** `tests/test_pipeline_executor_e2e.py:51-58`
**Issue:** The `make_linear_pipeline` helper function calls `StepType.to_model(...)`, but `StepType` is an Enum in `models.py` and has no `to_model` method. However, this function is never called by any test (tests construct `PipelineStep` directly), so it is dead code that does not cause a runtime failure.

**Fix:** Either remove `make_linear_pipeline` or change it to construct `PipelineStep` directly.

---

### IN-02: `asyncio.get_event_loop()` used instead of `get_running_loop()`

**File:** `api_server/routers/pipelines.py:170`
**Issue:** `asyncio.get_event_loop()` is used in an async context. This works in FastAPI request handlers (which always have a running loop) but is semantically incorrect. `asyncio.get_running_loop()` is the proper API when an event loop is expected to exist.

**Fix:**
```python
loop = asyncio.get_running_loop()
```

---

### IN-03: `cancel` endpoint does not check pipeline state before cleanup

**File:** `api_server/routers/pipelines.py:178-200`
**Issue:** `cancel_pipeline` fetches the pipeline and then always calls `cleanup.cancel_and_cleanup()`, even if the pipeline is COMPLETED or CANCELLED. While the handler handles this gracefully (no-op), it is inefficient and misleading about what the endpoint actually does.

**Fix:** Add an early return or 200 with a note if the pipeline is not in a cancellable state:
```python
cancellable = ("running", "monitoring", "visualizing", "reporting")
if pipeline_status not in cancellable:
    return {"status": "already_stopped", "pipeline_id": pipeline_id}
```

---

### IN-04: `step_wrappers.py` `params.pop()` mutates caller's dict

**File:** `api_server/services/step_wrappers.py:216-218`
**Issue:** In `run_wrapper`, `params.pop("case_id", ...)` and `params.pop("pipeline_id", ...)` mutate the step's `params` dict in place. If the same step object were reused or if the params were referenced elsewhere, this could cause unexpected behavior.

**Fix:** Copy params first:
```python
params = step.params.copy()
```

---

### IN-05: `pipeline_db.py` uses `check_same_thread=False` without explicit locking

**File:** `api_server/services/pipeline_db.py:49`
**Issue:** `sqlite3.connect(..., check_same_thread=False)` allows SQLite connections to be accessed from multiple threads. The code uses module-level singletons for the service and connection factory, but there is no locking around connection usage. SQLite connections are not thread-safe for writes.

**Fix:** Either remove `check_same_thread=False` and ensure all DB access happens from a single thread (the current design appears to assume this), or wrap all connection usage with a lock.

---

### IN-06: Schema migration idempotency relies on silent catch of `OperationalError`

**File:** `api_server/services/pipeline_db.py:119-125`
**Issue:** Schema v2 migration uses `ALTER TABLE ... ADD COLUMN` inside a try/except that silently catches `OperationalError` when the column already exists. This works, but it would also silently catch other column-related errors (e.g., disk full, locked DB), masking real failures.

**Fix:** Check if the column exists before adding it:
```python
cursor.execute("PRAGMA table_info(pipeline_steps)")
columns = {row[1] for row in cursor.fetchall()}
if "result_json" not in columns:
    cursor.execute("ALTER TABLE pipeline_steps ADD COLUMN result_json TEXT")
```

---

_Reviewed: 2026-04-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
