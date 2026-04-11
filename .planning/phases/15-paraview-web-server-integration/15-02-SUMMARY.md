---
phase: "15"
plan: "02"
subsystem: infra
tags: [paraview-web, docker, openfoam, asyncio, fastapi, rest-api]

# Dependency graph
requires:
  - phase: "15-01"
    provides: ParaviewWebManager, ParaViewWebSession model, PARAVIEW_WEB_* config
provides:
  - Visualization REST API router (4 endpoints)
  - Idle timeout background monitor
  - Auto-launch ParaView Web session on job completion
affects: [phase 16, phase 17, phase 18]

# Tech tracking
tech-stack:
  added:
    - FastAPI REST endpoints (visualization router)
    - asyncio background task (idle monitor)
    - Docker sidecar auto-launch on job completion
  patterns:
    - Idle timeout via background coroutine (60s polling interval)
    - Session lifecycle tied to job result directory
    - Path validation for case_dir (absolute, exists, allowed root)

key-files:
  created:
    - api_server/routers/visualization.py (253 lines)
  modified:
    - api_server/services/paraview_web_launcher.py (added idle monitor + singleton)
    - api_server/main.py (registered visualization router + lifespan integration)
    - api_server/services/job_service.py (auto-launch on job completion)

key-decisions:
  - "Used singleton get_paraview_web_manager() to share manager across router and lifespan"
  - "Idle monitor skips sessions with status stopping/stopped to prevent race conditions"
  - "Non-fatal ParaView Web auto-launch: job completes even if visualization fails to start"
  - "case_dir validation: must be absolute path + exist + under DATA_DIR/REPORTS_DIR or contain polyMesh/case.foam"

patterns-established:
  - "Background asyncio task managed by start/stop_idle_monitor() with graceful cancellation"
  - "Visualization session auto-launched with session_id=PVW-{job_id} for traceability"

requirements-completed: [PV-01.2, PV-01.4]

# Metrics
duration: 5min
completed: 2026-04-11
---

# Phase 15 Plan 02: ParaView Web REST API + Idle Monitor Summary

**Visualization REST API router (4 endpoints) + idle timeout background task that auto-shuts down sessions after 30 min inactivity + job completion auto-launch**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-11T04:14:19Z
- **Completed:** 2026-04-11T04:19:00Z
- **Tasks:** 3 (each committed individually)
- **Files modified:** 4 (1 created, 3 modified)

## Task Commits

1. **Task 1: visualization router** - `543d0ca` (feat)
2. **Task 2: idle monitor + singleton** - `8651ab5` (feat)
3. **Task 3: router registration + job lifecycle** - `4d13875` (feat)

## Accomplishments

- 4 REST endpoints for ParaView Web session lifecycle: launch, status, activity heartbeat, shutdown
- Idle timeout background task: checks every 60s, shuts down sessions idle > 30 min
- Singleton `get_paraview_web_manager()` for shared manager across router and lifespan
- Visualization router registered in FastAPI lifespan: idle monitor starts/stops with app
- Job completion auto-launches ParaView Web session tied to job result directory
- Path validation for case_dir (absolute, exists, under allowed root or contains mesh files)

## Files Created/Modified

### Created
- `api_server/routers/visualization.py` (253 lines)
  - `POST /visualization/launch` — validate case_dir, launch session, return session_url + auth_key
  - `GET /visualization/{session_id}` — return session status
  - `POST /visualization/{session_id}/activity` — heartbeat to update last_activity
  - `DELETE /visualization/{session_id}` — shutdown session
  - `_validate_case_dir()` — path validation helper (absolute, exists, allowed root)

### Modified
- `api_server/services/paraview_web_launcher.py` (58 lines added)
  - Added `timedelta`, `logging` imports
  - Added `_idle_check_interval`, `_idle_task` to `__init__`
  - Added `_idle_monitor()`, `_shutdown_idle_sessions()`, `start_idle_monitor()`, `stop_idle_monitor()`
  - Added `get_paraview_web_manager()` singleton function

- `api_server/main.py` (lifespan integration)
  - Added `visualization` router import and registration
  - Added idle monitor start in lifespan startup section
  - Added idle monitor stop in lifespan shutdown section

- `api_server/services/job_service.py` (auto-launch)
  - After job completion with output_dir: auto-launch ParaView Web session
  - Store `paraview_session_id` and `paraview_session_url` in job result
  - Non-fatal: log warning if session creation fails

## Decisions Made

- Used singleton `get_paraview_web_manager()` pattern to share manager instance between router and lifespan without circular imports
- Idle monitor sets `status="stopping"` immediately in `shutdown_session()` to prevent race with concurrent idle checks
- Auto-launch is non-fatal: job completes successfully even if ParaView Web session fails to start
- Path validation uses both allowed root check (DATA_DIR/REPORTS_DIR) and mesh file presence check for flexibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: path_traversal | api_server/routers/visualization.py | case_dir validated as absolute, existing, under allowed root — mitigates T-15-05 |
| threat_flag: race_condition | api_server/services/paraview_web_launcher.py | status="stopping" set before async shutdown + idle check skips stopping/stopped — mitigates T-15-06 |

## Next Phase Readiness

- Phase 16 (Dashboard 3D viewer) can import visualization router and call endpoints
- Idle monitor runs automatically when API server starts
- Docker daemon must be running for ParaView Web sessions to launch

---
*Phase: 15-02*
*Completed: 2026-04-11*
