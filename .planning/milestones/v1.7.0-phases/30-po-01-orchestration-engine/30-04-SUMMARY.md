---
phase: 30-po-01-orchestration-engine
plan: 04
subsystem: orchestration
tags: [pipeline, docker, cleanup, REST-api, graceful-shutdown]

# Dependency graph
requires:
  - phase: 30-po-01-orchestration-engine
    provides: PipelineExecutor, cancel_pipeline_executor, start_pipeline_executor, CleanupHandler stub
provides:
  - CleanupHandler with docker stop --time=10 + force-kill fallback
  - POST /api/v1/pipelines/{id}/start (transitions PENDING → RUNNING, launches executor)
  - POST /api/v1/pipelines/{id}/cancel (calls cancel_and_cleanup, returns 200)
  - DELETE /api/v1/pipelines/{id}?cancel=true (cancels RUNNING pipelines before delete)
  - main.py lifespan shutdown calls cleanup_on_server_shutdown()
affects:
  - 31-pipeline-rest-api-react-dashboard — uses start/cancel endpoints
  - 32-po-02-parametric-sweep — uses start/cancel for each combination pipeline

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.to_thread() for blocking subprocess (docker) in async context
    - Docker ownership separation: CleanupHandler owns solver containers only
    - FastAPI dependency override pattern for testing with module-level singletons

key-files:
  created:
    - api_server/services/cleanup_handler.py — CleanupHandler with Docker cleanup + 10s timeout
    - tests/test_cleanup_handler.py — 14 tests for Docker cleanup, cancel, server shutdown
    - tests/test_pipeline_control.py — 11 tests for start/cancel/delete endpoints
  modified:
    - api_server/routers/pipelines.py — added start, cancel endpoints + cancel=true DELETE param
    - api_server/main.py — cleanup_on_server_shutdown() wired into lifespan shutdown

key-decisions:
  - "cancel_and_cleanup always attempts Docker cleanup regardless of cancel_pipeline_executor result — cancel returns bool but cleanup always runs per plan must_have"
  - "DELETE ?cancel=true only calls cleanup for RUNNING/MONITORING/VISUALIZING/REPORTING pipelines — PENDING/COMPLETED/FAILED pipelines skip cleanup"
  - "cancel_pipeline_executor imported locally inside cancel_and_cleanup — patch target is api_server.services.pipeline_executor.cancel_pipeline_executor (not cleanup_handler module)"

patterns-established:
  - "Docker containers identified by pipeline_id label filter — trame containers never touched (different label scheme)"
  - "asyncio.to_thread(_do_cleanup) for blocking docker subprocess — keeps event loop responsive"

requirements-completed: [PIPE-06, PIPE-02]

# Metrics
duration: 15min
completed: 2026-04-12
---

# Phase 30 Plan 04: Cleanup Handler + Pipeline Control Endpoints Summary

**CleanupHandler with Docker docker-stop + force-kill, REST start/cancel/delete endpoints wired into FastAPI router and main.py lifespan shutdown.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-12T06:08:00Z
- **Completed:** 2026-04-12T06:22:35Z
- **Tasks:** 2 (Task 1 TDD: 14 tests, Task 2: 11 tests)
- **Files modified:** 5 files, +822 insertions

## Accomplishments

- Created `CleanupHandler` with `cleanup_pipeline()` (stops containers labeled `pipeline_id=<id>`), `cancel_and_cleanup()` (signals executor + Docker cleanup), `cleanup_on_server_shutdown()` (cleans all active pipelines on server exit)
- Graceful shutdown: `docker stop --time=10` with `docker kill` fallback if graceful stop fails
- `POST /api/v1/pipelines/{id}/start`: validates pipeline is PENDING, launches `PipelineExecutor` via `start_pipeline_executor()`, returns 200 on success, 409 on already-running, 404 on not found
- `POST /api/v1/pipelines/{id}/cancel`: calls `cleanup.cancel_and_cleanup()` regardless of pipeline state, always returns 200 (404 if not found)
- `DELETE /api/v1/pipelines/{id}?cancel=true`: cancels RUNNING/MONITORING/VISUALIZING/REPORTING pipelines before deletion (skips cleanup for PENDING/COMPLETED)
- `main.py` lifespan shutdown now calls `cleanup_handler.cleanup_on_server_shutdown()` before server exit
- 25 total tests across both test files, all passing

## Task Commits

1. **Task 1 (TDD RED/GREEN): cleanup_handler.py + test_cleanup_handler.py** — `7d43ced` (feat)
2. **Task 2: control endpoints + main.py + test_pipeline_control.py** — `501d22f` (feat)

**Plan metadata:** `7d43ced` and `501d22f`

## Files Created/Modified

- `api_server/services/cleanup_handler.py` (new) — `CleanupHandler` with `_get_pipeline_containers`, `_stop_container`, `cleanup_pipeline`, `cancel_and_cleanup`, `cleanup_on_server_shutdown`; `get_cleanup_handler()` singleton; `GRACEFUL_TIMEOUT_SECONDS = 10`
- `api_server/routers/pipelines.py` (modified) — added `start_pipeline()` and `cancel_pipeline()` endpoints; updated `delete_pipeline()` to accept `cancel: bool = Query(default=False)`; added `from fastapi import Request` import
- `api_server/main.py` (modified) — lifespan shutdown now calls `cleanup_handler.cleanup_on_server_shutdown()` before stopping Trame manager
- `tests/test_cleanup_handler.py` (new) — 14 tests: docker container listing, graceful/force stop, asyncio cleanup pipeline, cancel+cleanup, server shutdown cleanup
- `tests/test_pipeline_control.py` (new) — 11 tests: start endpoint (200/400/404/409), cancel endpoint (200/404), delete with cancel param (204/cleanup-skip), lifespan source inspection

## Decisions Made

- `cancel_and_cleanup` always attempts Docker cleanup even when `cancel_pipeline_executor()` returns False (no running executor found) — matches plan must_have: "always attempt Docker cleanup regardless of executor state"
- `DELETE ?cancel=true` checks pipeline status before calling cleanup: only RUNNING/MONITORING/VISUALIZING/REPORTING trigger cleanup; PENDING/COMPLETED/FAILED skip it (no running containers to clean)
- Patched at source module (`api_server.services.pipeline_executor.cancel_pipeline_executor`, `api_server.services.pipeline_db.get_pipeline_db_service`) rather than at consumer for locally-imported dependencies — avoids `AttributeError: does not have attribute`

## Deviations from Plan

None — plan executed exactly as written.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] patch target wrong for locally-imported cancel_pipeline_executor**
- **Found during:** Task 2 (test_cancel_and_cleanup_calls_cancel_then_cleanup)
- **Issue:** Original test patched `api_server.services.cleanup_handler.cancel_pipeline_executor` but the function is imported locally inside `cancel_and_cleanup()` method, not at module level — `AttributeError: does not have the attribute`
- **Fix:** Changed all patches for locally-imported functions to target the source module: `api_server.services.pipeline_executor.cancel_pipeline_executor` and `api_server.services.pipeline_db.get_pipeline_db_service`
- **Files modified:** `tests/test_cleanup_handler.py`, `tests/test_pipeline_control.py`
- **Verification:** All 25 tests pass
- **Committed in:** `7d43ced` and `501d22f`

**2. [Rule 1 - Bug] AsyncMock defined at bottom of test file causing NameError**
- **Found during:** Task 1 (TestCleanupOnServerShutdown tests)
- **Issue:** `AsyncMock` class was defined after the class using it in `test_cleanup_handler.py` — Python raised `NameError` when TestClient loaded the module
- **Fix:** Moved `AsyncMock` class definition to the top of the file (after imports), before any test classes that use it
- **Files modified:** `tests/test_cleanup_handler.py`
- **Verification:** All 14 cleanup tests pass
- **Committed in:** `7d43ced`

**3. [Rule 3 - Blocking] pipeline with empty steps triggered 400 on start endpoint**
- **Found during:** Task 2 (test_start_pending_pipeline_returns_200)
- **Issue:** Mock `PipelineResponse` was created with `steps=[]`, triggering the endpoint's "no steps" validation and returning 400 instead of 200
- **Fix:** Provided a non-empty step list in the mock pipeline (`steps=[mock_step]`) with `PipelineStep(step_id="step1", step_type=GENERATE, ...)`
- **Files modified:** `tests/test_pipeline_control.py`
- **Verification:** Test passes, returns 200
- **Committed in:** `501d22f`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** All fixes essential for correctness. No scope creep.

## Issues Encountered

- `TestClient` POST requests required `json={}` body even when endpoint takes no body — without it, FastAPI returned default 404 before calling the endpoint handler; resolved by always providing empty JSON body in tests
- Patching module-level functions that are locally imported inside methods requires patching at the SOURCE module, not the consumer module; documented this pattern for future tests

## Verification Results

| Check | Result |
|-------|--------|
| `python3 -m pytest tests/test_cleanup_handler.py tests/test_pipeline_control.py -x -q` | 25 passed |
| `python3 -c "from api_server.main import app; print('app ok')"` | app ok |
| `python3 -c "from api_server.services.cleanup_handler import get_cleanup_handler; print('cleanup ok')"` | cleanup ok |
| `grep "cleanup_on_server_shutdown" api_server/main.py` | Found |
| `grep "cancel=true" api_server/routers/pipelines.py` | Found |
| `grep "GRACEFUL_TIMEOUT_SECONDS = 10" api_server/services/cleanup_handler.py` | Found |
| `grep "docker stop.*time=10" api_server/services/cleanup_handler.py` | Found |

## Success Criteria Met

- [x] POST /api/v1/pipelines/{id}/start endpoint starts PipelineExecutor in background thread
- [x] POST /api/v1/pipelines/{id}/cancel endpoint signals cancel and triggers Docker cleanup
- [x] DELETE /api/v1/pipelines/{id}?cancel=true cancels then deletes
- [x] CleanupHandler uses `docker ps --filter label=pipeline_id=<id>` (solver only, not trame)
- [x] Graceful 10-second timeout before force-kill (`docker stop --time=10`)
- [x] COMPLETED step outputs are preserved (CleanupHandler does NOT delete case directories)
- [x] main.py lifespan shutdown calls cleanup_on_server_shutdown()
- [x] All 11 control endpoint tests pass
- [x] All existing Phase 29 CRUD endpoints remain functional

## Next Phase Readiness

- Phase 31 (Pipeline REST API + React Dashboard) is ready — start/cancel endpoints are installed; cleanup handler is wired
- Phase 32 (Parametric Sweep) is ready — SweepRunner can use `start_pipeline_executor()` and `cancel_pipeline_executor()` for each combination pipeline

---
*Phase: 30-po-01-orchestration-engine plan 04*
*Completed: 2026-04-12*
