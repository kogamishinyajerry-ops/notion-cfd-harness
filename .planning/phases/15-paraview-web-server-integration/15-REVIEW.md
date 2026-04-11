---
phase: 15-paraview-web-server-integration
reviewed: 2026-04-11T12:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - api_server/services/paraview_web_launcher.py
  - api_server/models.py
  - api_server/config.py
  - api_server/routers/visualization.py
  - api_server/main.py
  - api_server/services/job_service.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 15: Code Review Report

**Reviewed:** 2026-04-11T12:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 15 implements a ParaView Web Docker sidecar pattern for interactive 3D CFD visualization. The architecture is sound with proper async Docker operations, session lifecycle management, and idle timeout background monitoring. However, there is one critical bug causing `cancel_job_async` to always fail, and several correctness issues around concurrent access to shared session state.

## Critical Issues

### CR-01: `_ACTIVE_JOBS` is never populated, `cancel_job_async` always fails

**File:** `api_server/services/job_service.py:23-24, 208, 369`

The `_ACTIVE_JOBS` dictionary is defined at line 23 but is **never written to**. The `ActiveJob` dataclass is created at line 208 but is never added to `_ACTIVE_JOBS`. As a result, `cancel_job_async` at line 369 always finds `_ACTIVE_JOBS.get(job_id)` returning `None` and returns `False` — the Docker container is never killed on async cancellation.

```python
# Line 23: Defined but never populated
_ACTIVE_JOBS: Dict[str, "ActiveJob"] = {}

# Line 208: ActiveJob created but NOT stored in _ACTIVE_JOBS
if job_id in _ACTIVE_JOBS:
    _ACTIVE_JOBS[job_id].container_id = streaming_result.container_id

# Line 369-371: Always None, cancel fails silently
active_job = _ACTIVE_JOBS.get(job_id)  # Always None
if not active_job:
    return False
```

**Fix:**
```python
# In _execute_job_async, store the task and container tracking:
active_job = ActiveJob(task=asyncio.current_task(), container_id=None, job_id=job_id)
_ACTIVE_JOBS[job_id] = active_job

# And when container_id is available from streaming_result:
if job_id in _ACTIVE_JOBS:
    _ACTIVE_JOBS[job_id].container_id = streaming_result.container_id
```

---

## Warnings

### WR-01: Race condition in port allocation

**File:** `api_server/services/paraview_web_launcher.py:110-112, 174`

`_next_port()` uses a simple iterator without locking. When multiple `launch_session` coroutines run concurrently, they can receive the same port before either binds it. This is a TOCTOU (time-of-check-time-of-use) race.

```python
self._port_allocator: Iterator[int] = iter(self._cycle_ports())

def _next_port(self) -> int:
    return next(self._port_allocator)  # No lock — concurrent calls get same port
```

While Docker will reject a duplicate port binding, the session object is already created with the conflicting port before container start.

**Fix:** Use `asyncio.Lock` around port allocation:
```python
self._port_lock = asyncio.Lock()

async def _allocate_port(self) -> int:
    async with self._port_lock:
        return next(self._port_allocator)
```

### WR-02: Unhandled exceptions in `_shutdown_idle_sessions` can crash idle monitor

**File:** `api_server/services/paraview_web_launcher.py:408-417`

The `_shutdown_idle_sessions` method has no try/except. If `shutdown_session` raises an exception (e.g., Docker daemon unreachable), the background `_idle_monitor` loop terminates, leaving all sessions without idle protection.

```python
async def _shutdown_idle_sessions(self) -> None:
    """Stop sessions that have been idle longer than IDLE_TIMEOUT_MINUTES."""
    now = datetime.utcnow()
    timeout = timedelta(minutes=PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES)
    for session_id, session in list(self._sessions.items()):  # No try/except
        if session.status == "stopping" or session.status == "stopped":
            continue
        if now - session.last_activity > timeout:
            logger.info(f"Idle timeout for session {session_id}, shutting down")
            await self.shutdown_session(session_id)  # Can raise, crashes loop
```

**Fix:** Wrap `shutdown_session` in try/except and continue iterating:
```python
for session_id, session in list(self._sessions.items()):
    if session.status in ("stopping", "stopped"):
        continue
    if now - session.last_activity > timeout:
        try:
            await self.shutdown_session(session_id)
        except ParaViewWebError as e:
            logger.error(f"Failed to shutdown idle session {session_id}: {e}")
```

### WR-03: Concurrent access to `self._sessions` without synchronization

**File:** `api_server/services/paraview_web_launcher.py:97, 189, 364, 391-400`

`self._sessions` is accessed from multiple async contexts (API handlers, idle monitor, `update_activity`) without a lock. The `update_activity` method reads and writes `last_activity` without synchronization:

```python
def update_activity(self, session_id: str) -> None:
    session = self._sessions.get(session_id)  # Read
    if session:
        session.last_activity = datetime.utcnow()  # Write
        self._sessions[session_id] = session  # Write
```

Under concurrent requests, the update at line 399 could be lost due to read-modify-write race.

**Fix:** Use `asyncio.Lock` for all `self._sessions` mutations:
```python
self._sessions_lock = asyncio.Lock()

async def update_activity(self, session_id: str) -> None:
    async with self._sessions_lock:
        session = self._sessions.get(session_id)
        if session:
            session.last_activity = datetime.utcnow()
```

### WR-04: Missing attribute check for `streaming_result.container_id`

**File:** `api_server/services/job_service.py:207-209`

The code checks `if job_id in _ACTIVE_JOBS` before setting `container_id`, but `streaming_result` is an object (not a dict). If `streaming_result` lacks a `container_id` attribute, this silently fails to store it — making `cancel_job_async` ineffective even if `_ACTIVE_JOBS` were populated.

```python
# Store container_id in _ACTIVE_JOBS for abort support
if job_id in _ACTIVE_JOBS:
    _ACTIVE_JOBS[job_id].container_id = streaming_result.container_id
```

If `streaming_result` is `None` (e.g., `_run_case` returns early with an error dict at line 225), this raises `AttributeError: 'NoneType' object has no attribute 'container_id'`.

**Fix:** Check for None and attribute existence:
```python
if job_id in _ACTIVE_JOBS and streaming_result is not None:
    container_id = getattr(streaming_result, 'container_id', None)
    if container_id:
        _ACTIVE_JOBS[job_id].container_id = container_id
```

---

## Info

### IN-01: Unused `has_mesh`/`has_foam` fallback in path validation

**File:** `api_server/routers/visualization.py:100-116`

The path validation allows directories containing `polyMesh/` or `case.foam` even if not under `DATA_DIR` or `REPORTS_DIR`. This is an intentional flexibility shortcut, but the `os.path.isdir` and `os.path.isfile` checks do not resolve symlinks — a symlink could point outside allowed roots. This is acceptable as a development convenience but should be documented.

### IN-02: Symlink not resolved before `startswith` check in path validation

**File:** `api_server/routers/visualization.py:94-106`

`os.path.realpath(case_dir)` is used to resolve symlinks before the `startswith` check, which is correct. However, the secondary check for `has_mesh`/`has_foam` does not use `realpath`, meaning a symlink in the path could bypass the root restriction.

```python
case_dir_resolved = os.path.realpath(case_dir)  # Resolved for startswith
allowed_roots = [os.path.realpath(DATA_DIR), os.path.realpath(REPORTS_DIR)]
# But then:
has_mesh = os.path.isdir(os.path.join(case_dir, "polyMesh"))  # NOT realpath
```

### IN-03: Auth key URL-safe but returned in plain JSON

**File:** `api_server/services/paraview_web_launcher.py:177`

Auth key uses `secrets.token_urlsafe(16)` which is cryptographically appropriate. The key is returned in the API response (`VisualizationLaunchResponse.auth_key`) and transmitted over WebSocket. This is expected for client-side WebSocket authentication with ParaView Web server, but the key should not be logged.

**Fix:** Ensure `logger.info` calls that might log `session` objects do not inadvertently log `auth_key`.

---

## Positive Findings

- **Auth key generation**: Uses `secrets.token_urlsafe(16)` — cryptographically secure URL-safe random (128 bits entropy). Correct.
- **Docker subprocess calls**: All use `asyncio.create_subprocess_exec` with explicit argument lists, avoiding shell injection. Correct.
- **Path validation**: `os.path.realpath` + `startswith` correctly prevents directory traversal. The `os.path.isabs` and `os.path.isdir` checks are appropriate.
- **Temp file cleanup**: Config file is written to temp location and cleaned up in `finally` block. Correct.
- **Session cleanup on error**: `launch_session` cleans up session record from `self._sessions` on failure (line 233). Correct.
- **Exception handling in auto-launch**: ParaView Web auto-launch in `job_service.py` is wrapped in try/except with non-fatal logging (line 135-137). Correct.

---

_Reviewed: 2026-04-11T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
