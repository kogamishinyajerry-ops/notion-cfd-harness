---
phase: 29-foundation-data-models-sqlite-persistence
reviewed: 2026-04-12T12:55:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - api_server/main.py
  - api_server/models.py
  - api_server/routers/pipelines.py
  - api_server/services/__init__.py
  - api_server/services/pipeline_db.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-04-12T12:55:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the SQLite persistence layer for pipeline data models. Found one critical type mismatch issue where `PipelineStep.status` incorrectly uses `JobStatus` instead of `PipelineStatus`, which could cause runtime validation errors or semantic confusion. Several architectural concerns around async/sync boundaries and N+1 query patterns were also identified.

## Critical Issues

### CR-01: PipelineStep uses wrong status enum type

**File:** `api_server/models.py:301`
**Issue:** The `PipelineStep` model defines `status: JobStatus = Field(default=JobStatus.PENDING, ...)` but should use `PipelineStatus`. Pipeline steps are part of a pipeline, not jobs. Using `JobStatus` here conflates two distinct concepts and could cause runtime errors when the step status is set to a pipeline status value (e.g., `PipelineStatus.RUNNING`) that does not exist in `JobStatus`.

**Fix:**
```python
# models.py line 301 - change:
status: JobStatus = Field(default=JobStatus.PENDING, description="Step execution status")

# to:
status: PipelineStatus = Field(default=PipelineStatus.PENDING, description="Step execution status")
```

## Warnings

### WR-01: N+1 query pattern in list_pipelines

**File:** `api_server/services/pipeline_db.py:214-227`
**Issue:** `list_pipelines()` first queries all pipeline IDs, then calls `get_pipeline()` individually for each ID. This results in N+1 database round trips (1 for IDs + N for each pipeline + N for steps), which will degrade performance as pipeline count grows.

**Fix:**
```python
def list_pipelines(self) -> List[PipelineResponse]:
    """List all pipelines."""
    conn = get_pipeline_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, ps.* FROM pipelines p
        LEFT JOIN pipeline_steps ps ON p.id = ps.pipeline_id
        ORDER BY p.created_at DESC
    """)
    # Process rows into PipelineResponse objects, grouping steps by pipeline_id
    ...
```

### WR-02: Synchronous database operations in async endpoints

**File:** `api_server/routers/pipelines.py:36-117`
**Issue:** `PipelineDBService` methods (`create_pipeline`, `get_pipeline`, `list_pipelines`, etc.) are synchronous but are called from `async def` FastAPI endpoints. FastAPI runs these in a threadpool by default, which works, but blocks a thread during I/O. For high-concurrency scenarios, consider making the service methods async (using `aiosqlite`) or offloading to a worker.

**Fix:** Either make `PipelineDBService` use async I/O (`aiosqlite`), or use `run_in_executor` to explicitly control threading behavior.

### WR-03: Global mutable state with thread-safety concern

**File:** `api_server/services/pipeline_db.py:14-15, 289`
**Issue:** Two global variables (`_DB_PATH`, `_INITIALIZED`, and `_pipeline_service`) are mutated without locks. Combined with `check_same_thread=False` on the SQLite connection (line 34), concurrent async requests could theoretically race on initialization. In practice, FastAPI's single-threaded startup makes this low-risk, but it is fragile.

**Fix:** Use `fastapi.Depends` for dependency injection instead of module-level singletons, or add proper locking around global initialization.

### WR-04: Late `json` import violates module organization

**File:** `api_server/services/pipeline_db.py:106`
**Issue:** `import json` appears after the `init_pipeline_db()` function definition (line 39), violating PEP 8 / PEP 20 "Flat is better than nested" principle. All imports should be at module level at the top.

**Fix:**
```python
# Move line 106 to top of file, after line 10
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
```

## Info

### IN-01: Missing type parameter on Optional

**File:** `api_server/routers/pipelines.py:24`
**Issue:** `_pipeline_service: Optional = None` should be `Optional[PipelineDBService]` for proper type checking and IDE support.

**Fix:**
```python
from api_server.services.pipeline_db import PipelineDBService
_pipeline_service: Optional[PipelineDBService] = None
```

### IN-02: Singleton via global instead of dependency injection

**File:** `api_server/routers/pipelines.py:27-32`
**Issue:** Uses a manual singleton pattern with `global` instead of FastAPI's `Depends()` dependency injection. This works but reduces testability and mixes concerns.

**Fix:** Use FastAPI's dependency injection:
```python
def get_pipeline_service() -> PipelineDBService:
    return get_pipeline_db_service()

@router.post("/pipelines", ...)
async def create_pipeline(spec: PipelineCreate, service: PipelineDBService = Depends(get_pipeline_service)):
    pipeline = service.create_pipeline(spec)
    return pipeline
```

---

_Reviewed: 2026-04-12T12:55:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
