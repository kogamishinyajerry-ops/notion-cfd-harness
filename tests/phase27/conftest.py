"""
Pytest Configuration for Phase 27 Integration Tests

Provides shared fixtures for:
- Mock Docker (shutil.which + subprocess)
- Mock TrameSession model
- Mock aiohttp.ClientSession
- Mock _detect_gpu
- FastAPI TestClient
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Python path — ensure api_server imports work
# ---------------------------------------------------------------------------
_project_root = str(Path(__file__).parent.parent.parent.resolve())
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# anyio backend (required for pytest-asyncio)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio to use the asyncio backend."""
    return "asyncio"


# ---------------------------------------------------------------------------
# TrameSession model fixture
# ---------------------------------------------------------------------------

def make_trame_session(
    session_id: str = "PVW-TEST1234",
    job_id: Optional[str] = "JOB-001",
    container_id: str = "abc123def456",
    port: int = 8081,
    case_dir: str = "/data/testcase",
    auth_key: str = "test-auth-key-16ch",
    status: str = "ready",
) -> MagicMock:
    """
    Factory fixture that returns a mock TrameSession with realistic field values.
    """
    session = MagicMock()
    session.session_id = session_id
    session.job_id = job_id
    session.container_id = container_id
    session.port = port
    session.case_dir = case_dir
    session.auth_key = auth_key
    session.status = status
    session.created_at = datetime(2026, 1, 1, 0, 0, 0)
    session.last_activity = datetime(2026, 1, 1, 0, 5, 0)
    return session


# ---------------------------------------------------------------------------
# Mock docker fixture — patches shutil.which and subprocess exec calls
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_docker(monkeypatch) -> Dict[str, Any]:
    """
    Patch shutil.which("docker") and asyncio.create_subprocess_exec to simulate
    a working Docker environment without requiring the Docker daemon.
    """
    mock_docker_path = "/usr/bin/docker"

    def mock_which(name: str):
        if name == "docker":
            return mock_docker_path
        return None

    async def mock_subprocess_exec(*args, stdout=None, stderr=None, **kwargs):
        """Mock asyncio.create_subprocess_exec for docker run/inspect/kill."""
        cmd = list(args)
        proc = MagicMock()

        if cmd[1] == "run":
            # docker run → return container ID
            proc.communicate = AsyncMock(return_value=(b"mock-container-id-12345", b""))
            proc.returncode = 0

        elif cmd[1] == "inspect":
            # docker inspect → container is running
            proc.communicate = AsyncMock(return_value=(b"true", b""))
            proc.returncode = 0

        elif cmd[1] == "kill":
            # docker kill → success
            proc.communicate = AsyncMock(return_value=(b"", b""))
            proc.returncode = 0

        elif cmd[1] == "logs":
            proc.communicate = AsyncMock(return_value=(b"trame server started", b""))
            proc.returncode = 0

        elif cmd[1] == "info":
            proc.returncode = 0

        else:
            proc.communicate = AsyncMock(return_value=(b"", b""))
            proc.returncode = 0

        # Make proc awaitable
        async def awaitable_communicate():
            return proc.communicate.return_value

        proc.communicate = AsyncMock(side_effect=lambda: asyncio.sleep(0) and proc.communicate.return_value)
        return proc

    # Apply patches
    import shutil
    monkeypatch.setattr(shutil, "which", mock_which)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_subprocess_exec)

    return {
        "docker_path": mock_docker_path,
        "mock_subprocess_exec": mock_subprocess_exec,
    }


# ---------------------------------------------------------------------------
# Mock aiohttp.ClientSession fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_aiohttp(monkeypatch) -> MagicMock:
    """
    Patch aiohttp.ClientSession.get to return a mocked 200 response,
    simulating a healthy trame server.
    """
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__aenter__ = MagicMock(return_value=mock_response)
    mock_response.__aexit__ = MagicMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    async def mock_get(*args, **kwargs):
        return mock_response

    mock_session.get = MagicMock(side_effect=mock_get)

    class MockClientSession:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return mock_session.get(*args, **kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    import aiohttp
    monkeypatch.setattr(aiohttp, "ClientSession", MockClientSession)
    return mock_session


# ---------------------------------------------------------------------------
# Mock _detect_gpu fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_detect_gpu(monkeypatch) -> MagicMock:
    """
    Patch trame_server._detect_gpu to return configurable GPU info.
    """
    def make_detector(available: bool, vendor: str):
        def _detect_gpu():
            return available, vendor
        return _detect_gpu

    # Default: NVIDIA GPU available
    monkeypatch.setattr(
        "trame_server._detect_gpu",
        make_detector(True, "NVIDIA"),
    )
    return make_detector


# ---------------------------------------------------------------------------
# FastAPI TestClient fixture (reuses api_tests/conftest pattern)
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client():
    """FastAPI test client, bypassing lifespan (no actual Docker/integration)."""
    from fastapi.testclient import TestClient
    from api_server.main import app

    # Bypass lifespan context manager (which starts idle monitor)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
