---
phase: "25"
plan: "01"
status: "completed"
completed_tasks: "3/3"
wave: 1
completed: "2026-04-12T00:50:00.000Z"
---

## Plan 25-01 Summary

### Objective
Create `TrameSessionManager` replacing `ParaViewWebManager`, wire the visualization router and job completion handler to use it, add the `TrameSession` model, and switch session URLs from WebSocket (`ws://`) to HTTP (`http://`).

### Tasks Completed

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Create TrameSessionManager service | ✅ Done | 406 lines, Docker launch, idle monitor, HTTP health check |
| 2 | Add TrameSession model | ✅ Done | Added to models.py alongside ParaViewWebSession |
| 3 | Wire router and job service | ✅ Done | visualization.py + job_service.py updated |

### Key Changes

**New file: `api_server/services/trame_session_manager.py`**
- `TrameSessionManager` class: `_sessions`, `_port_allocator`, `_idle_task`
- `_start_container`: `docker run -d --name trame-{session_id} -v {case}:/data:ro -p {port}:9000 IMAGE pvpython /trame_server.py --port 9000`
- `_wait_for_ready`: HTTP poll at `http://localhost:{port}` (not "Starting factory" log)
- `_shutdown_idle_sessions`: Uses `PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES` (30 min default)
- Singleton: `get_trame_session_manager()`
- `TrameSessionError` exception class

**`api_server/models.py`**
- Added `class TrameSession` with fields: session_id, job_id, container_id, port, case_dir, auth_key, created_at, last_activity, status
- `ParaViewWebSession` preserved (removed in Phase 28)

**`api_server/routers/visualization.py`**
- Import: `TrameSessionError`, `get_trame_session_manager` (from trame_session_manager)
- All 4 endpoints: `get_trame_session_manager()` replacing `get_paraview_web_manager()`
- `session_url`: `http://localhost:{port}` (not `ws://localhost:{port}/ws`)
- Exception: `TrameSessionError` (not `ParaViewWebError`)
- Detail text: "Failed to launch trame session"

**`api_server/services/job_service.py`**
- Import: `get_trame_session_manager` (from trame_session_manager)
- `session_id` prefix: `TRM-{job_id}` (not `PVW-{job_id}`)
- Result keys: `trame_session_id`, `trame_session_url` (not `paraview_session_*`)

### Docker Command Comparison

| Aspect | Old | New |
|--------|-----|-----|
| Entrypoint | `--entrypoint /entrypoint_wrapper.sh` | Default CMD |
| Command | `pvpython .../launcher.py /tmp/config.json` | `pvpython /trame_server.py --port 9000` |
| Config file | `/tmp/launcher_config.json` | None |
| Volume mounts | case + adv_protocols.py + config JSON | case only |
| Image verify | `vtk.web.launcher` module check | None |
| Ready check | "Starting factory" in logs | HTTP 200 at `http://localhost:{port}` |
| Container name | `pvweb-{session_id}` | `trame-{session_id}` |

### Verification Results

```
grep -c "class TrameSessionManager" trame_server.py                → 0  (correct file)
grep -c "class TrameSessionManager" trame_session_manager.py       → 1  ✓
grep "pvpython /trame_server.py --port 9000" trame_session_manager.py → 1  ✓
grep -c "get_paraview_web_manager" visualization.py                → 0  ✓
grep "get_trame_session_manager" visualization.py                → 5  ✓
grep "http://localhost" visualization.py                          → 1  ✓
grep "get_trame_session_manager" job_service.py                  → 1  ✓
grep "trame_session_url" job_service.py                          → 1  ✓
grep -c "get_paraview_web_manager" job_service.py                → 0  ✓
```

### Requirements Addressed

| Requirement | Task | Status |
|-------------|------|--------|
| TRAME-03.1 (Docker launch via pvpython /trame_server.py) | Task 1 | ✅ _start_container uses correct cmd |
| TRAME-03.2 (30-min idle timeout) | Task 1 | ✅ _shutdown_idle_sessions with PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES |
| TRAME-03.3 (Job completion auto-launch) | Task 3 | ✅ job_service.py completion block updated |
| TRAME-04.4 (Auth key routing) | Task 1 | ✅ secrets.token_urlsafe(16), session dict keyed by session_id |

### Git Commit
`4046395` — feat(25-01): create TrameSessionManager replacing ParaViewWebManager

### Next
Phase 25 complete. Phase 26 (Vue Frontend + Iframe Bridge) is next: Vue.js viewer, CFDViewerBridge.ts, postMessage wiring.
