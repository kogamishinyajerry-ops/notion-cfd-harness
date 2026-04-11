# Phase 27 Plan 01: Integration Feature Parity - Test Suite Summary

## Plan Metadata

| Field | Value |
|-------|-------|
| Phase | 27 |
| Plan | 01 |
| Subsystem | integration-feature-parity (TRAME-05) |
| Committed | 2026-04-12 |
| Requirements | TRAME-05.1, TRAME-05.3, TRAME-05.5, TRAME-05.6 |
| Tech Stack | pytest, pytest-asyncio, FastAPI TestClient, unittest.mock, AST |

## One-liner

Integration test suite for ParaView Web to Trame migration: 49 tests covering 14 postMessage handlers, UUID filter registry, FastAPI visualization endpoints, Docker lifecycle, and session isolation.

## Objective

Write integration tests validating the server-side TRAME-05 requirements: postMessage handler coverage in trame_server.py, UUID filter registry operations, FastAPI visualization API endpoints, Docker container lifecycle (run/health/shutdown/idle-timeout), and concurrent session isolation.

## Tasks Executed

### Task 1: Phase27 test infrastructure
**Commit:** `f28e3fa`
**Files:** `tests/phase27/__init__.py`, `tests/phase27/conftest.py`

Created shared test fixtures:
- `mock_docker`: patches `shutil.which`, `asyncio.create_subprocess_exec`, `subprocess.run` to simulate Docker daemon
- `mock_aiohttp`: patches `aiohttp.ClientSession` for HTTP health check mocking
- `mock_detect_gpu`: patches `_detect_gpu` for GPU vendor simulation
- `test_client`: FastAPI `TestClient` bypassing lifespan
- `get_trame_server_module()`: AST-based function extractor that bypasses paraview/trame import failures by pre-populating `sys.modules` with mocks and using `exec()` in an isolated namespace

### Task 2: postMessage handler and filter registry tests
**Commit:** `1c62e1c`
**Files:** `tests/phase27/test_trame_postmessage.py`, `tests/phase27/test_filter_registry.py`

**test_trame_postmessage.py** (9 tests):
- Regex extraction of JS script block: `re.search(r'_server\.add_custom_script\s*\(\s*"""(.*?)"""\s*\)', ..., re.DOTALL)`
- Verifies all 14 case types in the switch statement
- Verifies `postMessage({ type: 'ready' })` broadcast
- Verifies `setInterval` camera polling at 500ms
- Verifies ctrl wiring for volume_toggle, filter_delete, screenshot

**test_filter_registry.py** (15 tests):
- AST approach: parse `trame_server.py` with `ast.parse()`, extract `FunctionDef` nodes for filter functions, wrap in `Module` node, compile, execute in isolated namespace with mocked `simple`, `_state`, `_ctrl`
- UUID key: `uuid.uuid4().hex` returns **32 hex chars** (not 16 as stated in plan description)
- Tests: clip/contour/streamtracer create with UUID keys, filter delete removes entry, filter list builds correct structure, Mesa GPU detection sets `gpu_available=False`, 3M cell count triggers warning

### Task 3: API endpoint and Docker lifecycle tests
**Commit:** `7bc2df4`
**Files:** `tests/phase27/test_visualization_api.py`, `tests/phase27/test_docker_lifecycle.py`

**test_visualization_api.py** (8 tests):
- Patches `api_server.routers.visualization.get_trame_session_manager` with `MagicMock`
- `temp_case_dir` fixture creates real temp dir under `api_server.config.DATA_DIR` for absolute-path validation
- Tests: 201 launch, 400 validation (relative path, nonexistent path), 200/404 get, 200 activity heartbeat, 200 delete, session_url uses `http://` not `ws://`

**test_docker_lifecycle.py** (11 tests):
- Key mocking patterns: `patch.object(manager, "validate_docker_available", return_value=True)` to bypass real Docker; `patch.object(manager, "_wait_for_ready", mock_noop)` for aiohttp mocking
- `mock_docker` fixture patches `subprocess.run` (used by `validate_docker_available`) in addition to `asyncio.create_subprocess_exec`
- Tests: docker run args, readonly mount `:ro`, HTTP 200 wait, container-exit error raises `TrameSessionError`, docker unavailable raises error, docker kill on shutdown, 31-minute idle timeout kill, port allocation, session retrieval, activity targeting, shutdown isolation

### Task 4: Session isolation tests
**Commit:** `2213abc`
**Files:** `tests/phase27/test_session_isolation.py`

**test_session_isolation.py** (6 tests):
- `@pytest.mark.asyncio` async tests use `await` directly (not `run_until_complete`) to avoid "event loop already running" error
- Tests: separate container IDs for concurrent sessions, separate ports (8081-8090 range), separate auth_keys (`secrets.token_urlsafe(16)` = 22-char base64, not 16), correct session retrieval by ID, targeted activity update, shutdown isolation

## Test Results

```
======================== 49 passed, 3 warnings in 0.88s ========================
```

| File | Tests |
|------|-------|
| test_trame_postmessage.py | 9 |
| test_filter_registry.py | 15 |
| test_visualization_api.py | 8 |
| test_docker_lifecycle.py | 11 |
| test_session_isolation.py | 6 |
| **Total** | **49** |

## Key Decisions

### 1. AST extraction for trame_server.py functions
The module-level `_state = None` and decorator `@_state.change` evaluate at import time, preventing normal import. Solution: parse source with `ast.parse()`, extract `FunctionDef` nodes, wrap in `Module` node, `compile()`, `exec()` in namespace with mocked globals.

### 2. UUID length correction
Plan description said "16-char hex string" for filter UUID keys. Actual implementation uses `uuid.uuid4().hex` which returns **32 hex chars** (128-bit UUID). Tests corrected to match actual implementation.

### 3. auth_key length correction
Plan referenced 16-char auth_key. Actual implementation uses `secrets.token_urlsafe(16)` which returns **22-char base64** string. Tests corrected to `assert len(...) == 22`.

### 4. aiohttp mocking strategy
`_wait_for_ready` uses local `import aiohttp` inside the function, so `patch("...module.aiohttp.ClientSession")` fails. Solution: patch `manager._wait_for_ready` directly as an async no-op.

### 5. subprocess.run mocking for Docker validation
`validate_docker_available()` uses `import subprocess` inside the function (local binding), so `patch("subprocess.run")` only patches the test module's reference. Fixed by also patching `subprocess.run` in the `mock_docker` fixture.

### 6. Event loop pattern for async tests
`@pytest.mark.asyncio` tests run in an already-running event loop. Using `asyncio.get_event_loop().run_until_complete()` raises `RuntimeError: This event loop is already running`. Fixed by using `await` directly inside async test methods.

## Deviation from Plan

### UUID key length (Rule 2 - Auto-add missing critical functionality)
Plan stated filter UUID keys are "16-char hex string". Actual implementation uses `uuid.uuid4().hex` (32 chars). This is a plan description error, not an implementation error. Tests were corrected to assert 32-char keys.

### auth_key length
Plan referenced 16-char auth_key. Implementation uses `secrets.token_urlsafe(16)` producing 22-char base64. Tests corrected to assert 22 chars.

## Commits

| Commit | Description |
|--------|-------------|
| `f28e3fa` | test(phase27-01): add phase27 test infrastructure with mock fixtures |
| `1c62e1c` | test(phase27-01): add postMessage handler and filter registry tests |
| `7bc2df4` | test(phase27-01): add API endpoint and Docker lifecycle tests |
| `2213abc` | test(phase27-01): add session isolation tests |

## Files Created/Modified

| File | Status | Tests |
|------|--------|-------|
| `tests/phase27/__init__.py` | Created | - |
| `tests/phase27/conftest.py` | Created | - |
| `tests/phase27/test_trame_postmessage.py` | Created | 9 |
| `tests/phase27/test_filter_registry.py` | Created | 15 |
| `tests/phase27/test_visualization_api.py` | Created | 8 |
| `tests/phase27/test_docker_lifecycle.py` | Created | 11 |
| `tests/phase27/test_session_isolation.py` | Created | 6 |
