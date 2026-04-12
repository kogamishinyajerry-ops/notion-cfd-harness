# Phase 32 Plan 01 Summary: PO-02 Parametric Sweep Backend Foundation

**Plan:** 32-01
**Phase:** 32 (po-02-parametric-sweep)
**Milestone:** v1.7.0 — Pipeline Orchestration & Automation
**Executed:** 2026-04-12
**Duration:** ~224 seconds (4 tasks)
**Status:** COMPLETE

---

## One-liner

Pydantic models, SQLite schema v3, and SweepRunner engine for full-factorial parametric sweep execution with concurrency control.

---

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Add Sweep Pydantic models to api_server/models.py | 4d105b8 | api_server/models.py |
| 2 | Add SQLite schema v3 and SweepDBService to pipeline_db.py | aa8352e | api_server/services/pipeline_db.py |
| 3 | Create SweepRunner service | c068165 | api_server/services/sweep_runner.py |
| 4 | Wire sweeps router into FastAPI app + lifespan | 7d95d9c | api_server/main.py, api_server/routers/sweeps.py, api_server/routers/__init__.py |

---

## What Was Built

### 1. Pydantic Models (api_server/models.py)
- `SweepStatus` enum: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
- `SweepCaseStatus` enum: QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
- `SweepCreate`: name, description, base_pipeline_id, param_grid, max_concurrent
- `SweepResponse`: full sweep response with total_combinations, completed_combinations
- `SweepCaseResponse`: per-combination case with param_combination, combination_hash, pipeline_id, result_summary
- `SweepListResponse`: paginated sweep list response

### 2. SQLite Schema v3 + SweepDBService (api_server/services/pipeline_db.py)
- Schema v3 migration: `sweeps` table + `sweep_cases` table with ON DELETE CASCADE FK
- `SweepDBService` class with methods: create_sweep, get_sweep, list_sweeps, update_sweep_status, increment_completed, delete_sweep, get_sweep_cases, get_case, update_case_pipeline_id, update_case_result
- `get_sweep_db_service()` singleton getter
- Shared `pipelines.db` via `init_pipeline_db()` (schema v3 applied on top of v2)

### 3. SweepRunner (api_server/services/sweep_runner.py)
- `SweepRunner` class running in dedicated `threading.Thread` (same pattern as PipelineExecutor)
- `asyncio.Semaphore(max_concurrent)` for concurrency control across Docker containers
- Param injection: `_sweep_override` dict injected into each step's params
- Per-case `output_dir = sweep_{sweep_id}/{combination_hash}/` stored in pipeline config
- 5-second polling loop per child pipeline until completion
- Result summary extraction: final_residual, execution_time, pipeline_status
- Public API: `start_sweep_runner()`, `cancel_sweep_runner()`, `get_sweep_runner()`

### 4. FastAPI App Wiring (api_server/main.py)
- `sweeps.router` registered with `API_PREFIX` and `tags=["sweeps"]`
- Sweep DB init logged in lifespan (idempotent call to `init_pipeline_db()`)
- Stub `api_server/routers/sweeps.py` created as placeholder (full endpoints in Plan 02)

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Shared pipelines.db (not separate sweeps.db) | SweepRunner creates child pipelines that must share the same DB as PipelineDBService |
| Cases pre-generated at sweep creation | `itertools.product` expansion happens in `create_sweep`; cases stored in sweep_cases table — SweepRunner just iterates |
| `combination_hash` via `uuid.uuid5(NAMESPACE_DNS, combo_str)` | Deterministic hash from param combination string, consistent across restarts |
| `_sweep_override` key for param injection | Non-destructive: base pipeline step params remain unmodified; override is additive |

---

## Deviations from Plan

### Auto-fixed Issue (Rule 3 — Blocking Issue)

**sweeps router missing blocked Task 4 wiring**
- **Issue:** Plan's Task 4 instructs `app.include_router(sweeps.router, ...)` but `api_server/routers/sweeps.py` did not exist, causing `ImportError` at startup
- **Fix:** Created minimal stub `api_server/routers/sweeps.py` with `APIRouter()` placeholder; full endpoint implementation deferred to Plan 02
- **Files modified:** `api_server/routers/sweeps.py`, `api_server/routers/__init__.py`
- **Commit:** 7d95d9c

---

## Threat Surface

No new security surface introduced. All mitigations from the plan's threat model are respected:
- T-32-01 (param_grid injection): `_sweep_override` is additive; base pipeline unmodified
- T-32-02 (max_concurrent unbounded): enforced at model level (ge=1, le=10)
- T-32-03 (output_dir path traversal): constructed server-side from sweep_id + combination_hash
- T-32-04 (cascade delete): ON DELETE CASCADE intentional and acceptable

---

## Known Stubs

| Stub | File | Reason | Resolved In |
|------|------|--------|-------------|
| `sweeps.py` stub router with no endpoints | api_server/routers/sweeps.py | Full REST API endpoints belong to Plan 02 | Plan 32-02 |

---

## Verification

```bash
python3 -c "from api_server.models import SweepStatus, SweepCaseStatus, SweepCreate, SweepResponse, SweepCaseResponse, SweepListResponse; print('models OK')"
python3 -c "from api_server.services.pipeline_db import SweepDBService, get_sweep_db_service, init_pipeline_db; init_pipeline_db(); print('schema OK')"
python3 -c "from api_server.services.sweep_runner import SweepRunner, start_sweep_runner; print('sweep_runner OK')"
python3 -c "from api_server.main import app; print('app OK')"
```

All checks pass.

---

## Self-Check: PASSED

- [x] All 4 tasks executed and committed individually
- [x] All new Pydantic models importable from api_server.models
- [x] SweepDBService functional with schema v3 migrations
- [x] SweepRunner module loads without ImportError
- [x] sweeps router registered in FastAPI app
- [x] Deviations documented (stub sweeps router)
- [x] No new security surface introduced
