---
phase: 10-rest-api-server
reviewed: 2026-04-10T19:30:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - api_server/main.py
  - api_server/models.py
  - api_server/config.py
  - api_server/routers/cases.py
  - api_server/routers/jobs.py
  - api_server/routers/knowledge.py
  - api_server/routers/status.py
  - api_server/routers/websocket.py
  - api_server/services/case_service.py
  - api_server/services/job_service.py
  - api_server/services/knowledge_service.py
  - api_server/services/websocket_manager.py
  - api_server/auth/__init__.py
  - api_server/auth/jwt_handler.py
  - api_server/auth/rbac_middleware.py
  - tests/api_tests/test_api_cases.py
  - tests/api_tests/test_api_jobs.py
  - tests/api_tests/test_api_knowledge.py
  - tests/api_tests/test_api_status.py
  - tests/test_api_websocket.py
findings:
  critical: 2
  warning: 5
  info: 5
  total: 12
status: issues_found
---

# Phase 10: REST API Server Code Review Report

**Reviewed:** 2026-04-10T19:30:00Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

The REST API Server phase implements a FastAPI application for the AI-CFD Knowledge Harness with case management, job submission, knowledge registry queries, and WebSocket support. The codebase has proper structure with separation of routers, services, and auth modules. However, several critical security and correctness bugs were identified that require immediate attention before production deployment.

## Critical Issues

### CR-01: `async_mode` parameter is completely ignored

**File:** `api_server/services/job_service.py:65-70`
**Issue:** The `submit_job` method has identical code for both async and sync modes:

```python
if submission.async_mode:
    # Schedule async execution
    asyncio.create_task(self._execute_job_async(job_id, submission))
else:
    # Run synchronously
    asyncio.create_task(self._execute_job_async(job_id, submission))
```

Both branches execute `asyncio.create_task()` - there is no synchronous execution path. The docstring claims "Supports both synchronous and asynchronous job execution" but sync mode is not implemented.

**Fix:**
```python
if submission.async_mode:
    asyncio.create_task(self._execute_job_async(job_id, submission))
else:
    # Run synchronously (blocking)
    await self._execute_job_async(job_id, submission)
```

---

### CR-02: JWT_SECRET_KEY generated at import time, not runtime

**File:** `api_server/auth/jwt_handler.py:18`
**Issue:** The default JWT secret is generated when the module is first imported:

```python
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
```

Problems:
1. If the server runs with multiple uvicorn workers (common in production), each worker generates a different secret at import, causing token validation to fail randomly across workers.
2. If the server restarts and `JWT_SECRET_KEY` env var was not set, all existing tokens are invalidated because a new key is generated.

**Fix:** Either require `JWT_SECRET_KEY` to be set in environment (fail fast if missing), or generate the key once at first access and cache it:

```python
_import_secret = os.getenv("JWT_SECRET_KEY")
if _import_secret is None:
    raise RuntimeError("JWT_SECRET_KEY environment variable must be set")
JWT_SECRET_KEY = _import_secret
```

---

## Warnings

### WR-01: CORS allows all origins by default

**File:** `api_server/config.py:16`
**Issue:** Default CORS origin is `"*"` (allow all):

```python
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
```

This is a security risk. FastAPI's CORSMiddleware with `allow_origins=["*"]` will not actually allow credentials with wildcard, but it still broadcasts the permissive configuration.

**Fix:** Default should be more restrictive, e.g., empty list or specific allowed origins:

```python
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
```

---

### WR-02: CaseService uses global mutable state without proper synchronization

**File:** `api_server/services/case_service.py:20, 39-40`
**Issue:** `_CASES` is a module-level dict that is shared across all `CaseService` instances:

```python
_CASES: Dict[str, CaseResponse] = {}

def __init__(self, storage_path: Optional[Path] = None):
    self.storage_path = storage_path or DATA_DIR / "cases"
    self.storage_path.mkdir(parents=True, exist_ok=True)
    self._load_cases()
```

If `CaseService()` is called with different `storage_path` values, they all read/write to the same global `_CASES`. The singleton pattern in routers mitigates this, but the design is fragile.

**Fix:** Make `_CASES` an instance variable, not a module global:

```python
def __init__(self, storage_path: Optional[Path] = None):
    self._cases: Dict[str, CaseResponse] = {}
    self.storage_path = storage_path or DATA_DIR / "cases"
    ...
```

---

### WR-03: `_ACTIVE_JOBS` is populated but never cleaned

**File:** `api_server/services/job_service.py:22`
**Issue:** `_ACTIVE_JOBS` tracks running asyncio tasks but is never decremented:

```python
_ACTIVE_JOBS: Dict[str, asyncio.Task] = {}
```

Tasks are added at line 67 but never removed after completion. This causes memory growth over time.

**Fix:** Add cleanup after job completes in `_execute_job_async`:

```python
finally:
    _JOBS[job_id] = job
    if job_id in _ACTIVE_JOBS:
        del _ACTIVE_JOBS[job_id]
```

---

### WR-04: WebSocket endpoint has optional authentication but is effectively unauthenticated

**File:** `api_server/routers/websocket.py:22-55`
**Issue:** The `websocket_job_updates` endpoint receives a token but explicitly allows anonymous access:

```python
# Note: In production, you'd want to validate the token
# For now, we allow anonymous access to job updates
```

Any client who knows a job ID can subscribe to its progress updates without authentication. This leaks job status information to unauthorized users.

**Fix:** Enforce authentication on the WebSocket endpoint, or at minimum validate that the job belongs to the requesting user.

---

### WR-05: Status endpoint creates new service instances per request

**File:** `api_server/routers/status.py:48-66`
**Issue:** Each `/status` call instantiates fresh services:

```python
case_service = CaseService()
job_service = JobService()
knowledge_service = KnowledgeService()
```

While the routers use singletons, the status endpoint creates its own instances, missing any data that was loaded by router-level singletons.

**Fix:** Use the same singleton pattern as other routers:

```python
from api_server.services.case_service import get_case_service
case_service = get_case_service()
```

---

## Info

### IN-01: Mixing timezone-aware and naive datetime

**File:** Multiple locations
**Issue:** The codebase mixes `datetime.utcnow()` (naive, deprecated) with `datetime.now(timezone.utc)` (timezone-aware):

- `status.py:35`: `datetime.utcnow()`
- `job_service.py:77,91`: `datetime.utcnow()`
- `jwt_handler.py:38-40`: `datetime.now(timezone.utc)`

**Fix:** Use timezone-aware datetimes consistently. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`.

---

### IN-02: `unit_type` parameter not validated against allowed values

**File:** `api_server/routers/knowledge.py:31,70-73`
**Issue:** The `unit_type` query parameter is passed through without validation:

```python
unit_type: Optional[str] = Query(default=None, description="Filter by unit type")
```

Valid types are: "chapter", "formula", "data_point", "chart_rule", "evidence". Invalid values will just return empty results rather than a 400 error.

**Fix:** Add validation or use an Enum:

```python
class KnowledgeUnitType(str, Enum):
    CHAPTER = "chapter"
    FORMULA = "formula"
    DATA_POINT = "data_point"
    CHART_RULE = "chart_rule"
    EVIDENCE = "evidence"
```

---

### IN-03: WebSocket subscriber count returns 0 for nonexistent jobs

**File:** `api_server/routers/websocket.py:90-110`
**Issue:** `get_job_subscriber_count` returns `{"job_id": "...", "subscriber_count": 0}` for jobs that don't exist, rather than a 404.

**Fix:** Check job existence first and raise 404 if not found.

---

### IN-04: `_job_to_dict` duplicates JobResponse serialization

**File:** `api_server/services/job_service.py:342-363`
**Issue:** `_job_to_dict` manually converts JobResponse to dict, but Pydantic models have built-in `.model_dump()` method.

**Fix:** Use the built-in serialization:

```python
def _job_to_dict(self, job: JobResponse) -> dict:
    return job.model_dump(mode="json")
```

---

### IN-05: Auth imports in routers are unused

**File:** `api_server/routers/cases.py`, `api_server/routers/jobs.py`, `api_server/routers/knowledge.py`
**Issue:** These files import `get_current_user` and `AuthenticatedUser` but do not use them - none of the endpoints have authentication dependencies.

**Fix:** Either add `Depends(get_current_user)` to endpoints that need auth, or remove the unused imports.

---

_Reviewed: 2026-04-10T19:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
