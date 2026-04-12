---
phase: "29-foundation-data-models-sqlite-persistence"
plan: "02"
subsystem: database
tags: [sqlite, pipeline, crud, fastapi, rest]

# Dependency graph
requires:
  - phase: ["29-01"]
    provides: ["Pipeline Pydantic models, init_pipeline_db(), get_pipeline_db_connection()"]
provides:
  - PipelineDBService CRUD operations (create/get/update/delete/list)
  - pipelines REST router at /api/v1/pipelines
  - SQLite persistence for pipelines and pipeline_steps
affects: [30-01, 31-01]

# Tech tracking
tech-stack:
  added: [sqlite3 stdlib (already used for connection factory)]
  patterns: [singleton service getter (matches CaseService), parameterized SQL queries (T-29-01 mitigation)]

key-files:
  created: [api_server/routers/pipelines.py]
  modified: [api_server/services/pipeline_db.py, api_server/services/__init__.py, api_server/main.py]

key-decisions:
  - "Module-level _pipeline_service singleton getter matches CaseService pattern — consistent with codebase"
  - "update_pipeline raises ValueError for non-PENDING pipelines — enforces immutability of running pipelines"
  - "DELETE pipeline relies on ON DELETE CASCADE — pipeline_steps cleaned up automatically"
  - "get_pipeline reconstitutes StepType/JobStatus enums from DB strings — Pydantic validation requires enum not raw string"

requirements-completed: ["PIPE-01"]

# Metrics
duration: "~3 minutes (4 tasks, all committed individually)"
completed: 2026-04-12
---

# Phase 29 Plan 02: Pipeline CRUD + REST Endpoints Summary

**PipelineDBService CRUD operations wired to REST API at /api/v1/pipelines**

## Performance

- **Tasks completed:** 4 (Tasks 3, 4, 5, 6)
- **Files modified:** 4
- **Commits:** 4 (one per task)

## Task Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 3 | `2db5951` | PipelineDBService CRUD (create_pipeline, get_pipeline, list_pipelines, update_pipeline, delete_pipeline) + get_pipeline_db_service singleton |
| Task 4 | `723f7ee` | PipelineDBService and get_pipeline_db_service exported from api_server.services |
| Task 5 | `210c197` | pipelines.py router with 5 REST endpoints (POST/GET/GET{id}/PUT/DELETE /pipelines) |
| Task 6 | `6952b6b` | pipelines router registered in main.py + init_pipeline_db() called at startup |

## Files Created/Modified

- `api_server/services/pipeline_db.py` — +194 lines: PipelineDBService class and singleton getter appended to existing init-only file
- `api_server/services/__init__.py` — +2 lines: PipelineDBService and get_pipeline_db_service added to imports and __all__
- `api_server/routers/pipelines.py` — New file (117 lines): full CRUD router following cases.py pattern
- `api_server/main.py` — +7 lines: pipelines import, router registration, init_pipeline_db() in lifespan

## End-to-End Verification (curl)

| Test | Result |
|------|--------|
| `POST /api/v1/pipelines` creates pipeline with steps | 201, pipeline_id=PIPELINE-2DA36A2D |
| `GET /api/v1/pipelines/{id}` returns full pipeline with branching steps | 200, steps include depends_on=["s1"] |
| `PUT /api/v1/pipelines/{id}` on PENDING pipeline updates name | 200, name="updated-name-wave2" |
| `PUT /api/v1/pipelines/{id}` with status!=PENDING returns | 400 "Can only update status to PENDING via this endpoint" |
| `DELETE /api/v1/pipelines/{id}` returns | 204, subsequent GET returns 404 |

## Decisions Made

- Used `StepType(sr["step_type"])` and `JobStatus(sr["status"])` to convert DB strings back to enums in `get_pipeline` — required because Pydantic rejects raw strings even with `use_enum_values=True`
- `update_pipeline` checks current status before allowing updates — only PENDING pipelines can be modified
- Router uses `from __future__ import annotations` to allow `Optional` without forward-ref issues on `_pipeline_service`
- Pipeline router uses `get_pipeline_db_service()` imported from `api_server.services` (not direct module import) — consistent with how `cases.py` imports `CaseService`

## Deviations from Plan

None — all 4 tasks executed exactly as specified.

## Threat Model Compliance

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-29-01 (Injection) | All SQL uses `cursor.execute("... WHERE id = ?", (pipeline_id,))` — 4 parameterized queries confirmed | Compliant |
| T-29-02 (Config tampering) | config stored as JSON blob — no eval/compile | Accept (per plan) |
| T-29-03 (Info Disclosure) | 404 for missing pipeline IDs (no enumeration) | Compliant |

## Dependencies

- Phase 30 (PO-01 Orchestration Engine) depends on PipelineDBService and the /api/v1/pipelines endpoints created here
- Phase 31 (Pipeline REST API + React Dashboard) depends on these same endpoints

## Self-Check: PASSED

All 5 files found on disk. All 4 task commits (2db5951, 723f7ee, 210c197, 6952b6b) found in git history. Python import checks pass for all modified modules.
