---
phase: 27-integration-feature-parity
reviewed: 2026-04-12T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - tests/phase27/__init__.py
  - tests/phase27/conftest.py
  - tests/phase27/test_cfd_viewer_bridge.js
  - tests/phase27/test_docker_lifecycle.py
  - tests/phase27/test_feature_parity_checklist.md
  - tests/phase27/test_filter_registry.py
  - tests/phase27/test_screenshot_pipeline.py
  - tests/phase27/test_session_isolation.py
  - tests/phase27/test_trame_postmessage.py
  - tests/phase27/test_trame_viewer_component.py
  - tests/phase27/test_visualization_api.py
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
status: issues_found
---

# Phase 27: Code Review Report

**Reviewed:** 2026-04-12
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 27 integration tests are well-structured with good coverage of Docker lifecycle, session isolation, postMessage bridge, filter registry, visualization API, and feature parity checklists. Two warnings and five informational items were found. No critical security vulnerabilities or logic bugs that would cause test suite failures were identified.

The most significant issue is a test that does not verify its stated behavioral claim (max_steps capping), and several hardcoded absolute paths that will break portability.

---

## Warnings

### WR-01: test_filter_streamtracer_caps_max_steps does not assert the capped value

**File:** `tests/phase27/test_filter_registry.py:301-308`
**Issue:** The test `test_filter_streamtracer_caps_max_steps` calls `on_filter_streamtracer_create(integration_direction="FORWARD", max_steps=99999)` and only asserts `result["success"] is True`. The docstring explicitly states "caps max_steps at 10000", but the actual capped value is never checked. If the capping logic is broken and 99999 is passed through unmodified, the test still passes.

**Fix (applied commit `5fe2efb`):**
```python
def test_filter_streamtracer_caps_max_steps(self, ns):
    """on_filter_streamtracer_create caps max_steps at 10000."""
    result = ns["on_filter_streamtracer_create"](
        integration_direction="FORWARD", max_steps=99999
    )
    assert result["success"] is True
    filter_uuid = result["filterId"]
    registered = ns["_state"].filters[filter_uuid]
    assert registered["params"]["maxSteps"] <= 10000
```

**Status:** Fixed ✅

---

### WR-02: datetime.utcnow() is deprecated in Python 3.12+

**File:** `tests/phase27/test_docker_lifecycle.py:285`
**Issue:** `datetime.utcnow()` is used at line 285 in `test_idle_timeout_shuts_down`. This method is deprecated in Python 3.12 because it returns a naive datetime without timezone info. It should be replaced with `datetime.now(timezone.utc)`.

**Fix (applied commit `5fe2efb`):**
```python
from datetime import datetime, timedelta, timezone
# ...
old_time = datetime.now(timezone.utc) - timedelta(minutes=31)
```
Also updated: `api_server/models.py` (all `default_factory=datetime.utcnow` → `lambda: datetime.now(timezone.utc)`) and `api_server/services/trame_session_manager.py` (both `datetime.utcnow()` calls → `datetime.now(timezone.utc)`) to maintain consistency. Fixed naive datetime in `test_session_isolation.py:191` as well.

**Status:** Fixed ✅

---

## Info

### IN-01: Hardcoded absolute PROJECT_ROOT paths reduce portability

**Files:**
- `tests/phase27/conftest.py:17` — `PROJECT_ROOT = Path("/Users/Zhuanz/Desktop/notion-cfd-harness")`
- `tests/phase27/test_filter_registry.py:17` — same hardcoded path
- `tests/phase27/test_trame_postmessage.py:13` — same hardcoded path

**Issue:** All three files use a hardcoded absolute path. If the project is cloned to a different location or run in CI, these will break. The pattern used in `test_docker_lifecycle.py` and `test_session_isolation.py` (`Path(__file__).parent.parent.parent.resolve()`) is the correct approach.

**Fix:** Replace the hardcoded path with a relative computation:
```python
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
```

---

### IN-02: Dead code in conftest.py — get_trame_server_module() is never called

**File:** `tests/phase27/conftest.py:367-416`
**Issue:** The `get_trame_server_module()` function is defined but never imported or called by any test. It appears to be a leftover from an earlier approach. Test `test_filter_registry.py` uses its own AST-based approach (`_parse_filter_functions`, `_compile_function`, `_fn_to_module`) rather than this conftest helper.

**Fix:** Either remove the dead function or wire it up to `test_filter_registry.py` to eliminate the duplicated AST logic in the test file.

---

### IN-03: Dead code in conftest.py — MockHttpResponse class is never instantiated

**File:** `tests/phase27/conftest.py:32-42`
**Issue:** `MockHttpResponse` is defined but never used. The `mock_aiohttp` fixture creates its own inline mock response instead.

**Fix:** Remove `MockHttpResponse` or wire it into `mock_aiohttp` to use it.

---

### IN-04: mock_aiohttp fixture return value is the mock_session MagicMock, not the response

**File:** `tests/phase27/conftest.py:324`
**Issue:** The `mock_aiohttp` fixture returns `mock_session` (a MagicMock), but no test actually uses the return value of this fixture. The fixture only patches `aiohttp.ClientSession` via monkeypatch. The return type annotation `-> MagicMock` is technically misleading since callers don't use the return value. This is not a bug — the fixture works correctly as a side-effect (monkeypatch) fixture — but the return value is dead code.

**Fix:** Either delete the return statement and change the fixture to return `None`, or add `scope="function"` to make the intent clearer. Alternatively, if a return value is desired for future use, document what callers should expect.

---

### IN-05: Test execution assumptions not validated

**Files:** `tests/phase27/test_trame_viewer_component.py`, `tests/phase27/test_screenshot_pipeline.py`, `tests/phase27/test_trame_postmessage.py`
**Issue:** All three files read `TRAME_VIEWER_PATH = "dashboard/src/components/TrameViewer.tsx"` as a relative path. Tests will only pass if executed from the project root (`/Users/Zhuanz/Desktop/notion-cfd-harness/`). If pytest is invoked from a different cwd, `open()` will fail with `FileNotFoundError`. The same applies to `test_trame_postmessage.py` reading `trame_server.py` via `PROJECT_ROOT / "trame_server.py"`.

**Fix:** Derive the path relative to the test file's location:
```python
# In test_trame_viewer_component.py and test_screenshot_pipeline.py:
TRAME_VIEWER_PATH = Path(__file__).parent.parent.parent.parent / "dashboard/src/components/TrameViewer.tsx"

# In test_trame_postmessage.py:
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
```

---

## Fix Summary

| Finding | File | Fix | Commit |
|---------|------|-----|--------|
| WR-01: missing assertion for max_steps cap | test_filter_registry.py:301 | Assert `registered["params"]["maxSteps"] <= 10000` | `5fe2efb` |
| WR-02: deprecated datetime.utcnow() | test_docker_lifecycle.py:285, models.py, trame_session_manager.py | Replaced with `datetime.now(timezone.utc)` | `5fe2efb` |

**Status:** All warnings resolved ✅

_Reviewed: 2026-04-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
