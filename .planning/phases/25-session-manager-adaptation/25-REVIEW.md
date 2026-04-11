---
phase: "25"
status: "issues_found"
severity: "high"
reviewer: "Claude Sonnet 4.6"
started: "2026-04-12T00:55:00.000Z"
---

## Phase 25 Code Review — Findings

### CRITICAL (1)

| ID | Issue | File | Severity |
|----|-------|------|----------|
| C-01 | `start_idle_monitor()` never called — sessions never cleaned up | `main.py` | Critical |

### MEDIUM (2)

| ID | Issue | File | Severity |
|----|-------|------|----------|
| M-01 | Port allocation race condition — no collision detection | `trame_session_manager.py` | Medium |
| M-02 | No cleanup of failed containers before retry | `trame_session_manager.py` | Medium |

### LOW (7)

| ID | Issue | File |
|----|-------|------|
| L-01 | `docker kill` failure silently swallowed | `trame_session_manager.py` |
| L-02 | `aiohttp.ClientSession` recreated every health-check iteration | `trame_session_manager.py` |
| L-03 | `result["trame_session_id"]` can race with completion broadcast | `job_service.py` |
| L-04 | `_validate_case_dir` uses `realpath`, `launch_session` uses `abspath` | `visualization.py` / `trame_session_manager.py` |
| L-05 | `session_id` passed unsanitized to `docker --name` | `trame_session_manager.py` |
| L-06 | `TrameSession` and `ParaViewWebSession` are nearly identical | `models.py` |

### Verified Correct
- Import errors / circular dependencies: None found
- Async/await correctness: All callers correctly `await` async `launch_session`
- Docker command injection: Protected by `_validate_case_dir` + read-only mount + UUID-constrained session_id
- Session lifecycle status transitions: Correct

---

## Critical Fix Required

**C-01: `start_idle_monitor()` never called**

`main.py:35-42` only starts the old `ParaViewWebManager` idle monitor:
```python
from api_server.services.paraview_web_launcher import get_paraview_web_manager
pv_manager = get_paraview_web_manager()
pv_manager.start_idle_monitor()
```

`TrameSessionManager.start_idle_monitor()` — which drives 30-minute idle cleanup — is never invoked. Sessions will never be auto-cleaned.

**Fix:** Add equivalent `get_trame_session_manager().start_idle_monitor()` to the FastAPI lifespan in `main.py`, alongside the `stop_idle_monitor()` cleanup on shutdown.
