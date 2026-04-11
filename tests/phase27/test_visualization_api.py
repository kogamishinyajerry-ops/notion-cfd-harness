"""
Tests for FastAPI visualization endpoints (api_server/routers/visualization.py).

Tests the session lifecycle API:
- POST /visualization/launch (201 success, 400 validation errors)
- GET /visualization/{session_id} (200 success, 404 not found)
- POST /visualization/{session_id}/activity (200)
- DELETE /visualization/{session_id} (200)
"""

import asyncio
import tempfile
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root in path
import sys
from pathlib import Path
_project_root = str(Path(__file__).parent.parent.parent.resolve())
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


@pytest.fixture
def mock_trame_manager(test_client):
    """
    Mock the TrameSessionManager to avoid real Docker calls.
    Returns a dict with the manager mock and a pre-created session.
    """
    from api_server.models import TrameSession

    mock_session = MagicMock(spec=TrameSession)
    mock_session.session_id = "PVW-12345678"
    mock_session.job_id = "JOB-001"
    mock_session.container_id = "mock-container-id"
    mock_session.port = 8081
    mock_session.case_dir = "/tmp/testcase"
    mock_session.auth_key = "mock-auth-key"
    mock_session.status = "ready"
    mock_session.created_at = datetime(2026, 1, 1, 0, 0, 0)
    mock_session.last_activity = datetime(2026, 1, 1, 0, 5, 0)

    manager = MagicMock()
    manager.launch_session = AsyncMock(return_value=mock_session)
    manager.get_session = MagicMock(return_value=mock_session)
    manager.update_activity = MagicMock()
    manager.shutdown_session = AsyncMock()

    return {"manager": manager, "session": mock_session}


class TestVisualizationAPI:
    """Tests for /visualization/* endpoints."""

    @pytest.fixture
    def mock_manager(self, test_client):
        from api_server.models import TrameSession

        mock_session = MagicMock(spec=TrameSession)
        mock_session.session_id = "PVW-12345678"
        mock_session.job_id = "JOB-001"
        mock_session.container_id = "mock-container-id"
        mock_session.port = 8081
        mock_session.case_dir = "/tmp/testcase"
        mock_session.auth_key = "mock-auth-key"
        mock_session.status = "ready"
        mock_session.created_at = datetime(2026, 1, 1, 0, 0, 0)
        mock_session.last_activity = datetime(2026, 1, 1, 0, 5, 0)

        manager = MagicMock()
        manager.launch_session = AsyncMock(return_value=mock_session)
        manager.get_session = MagicMock(return_value=mock_session)
        manager.update_activity = MagicMock()
        manager.shutdown_session = AsyncMock()

        return manager

    @pytest.fixture
    def temp_case_dir(self):
        """Create a real temporary directory under data/ for case_dir validation."""
        import api_server.config
        data_dir = api_server.config.DATA_DIR
        import os
        tmpdir = tempfile.mkdtemp(dir=str(data_dir))
        yield tmpdir
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_launch_visualization_session_returns_201(self, test_client, mock_manager, temp_case_dir):
        """POST /visualization/launch returns 201 with session info."""
        with patch(
            "api_server.routers.visualization.get_trame_session_manager",
            return_value=mock_manager,
        ):
            response = test_client.post(
                "/api/v1/visualization/launch",
                json={
                    "job_id": "J1",
                    "case_dir": temp_case_dir,
                },
            )

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "session_id" in data
        assert data["session_id"] == "PVW-12345678"
        assert "port" in data
        assert data["port"] == 8081
        assert "auth_key" in data
        assert "session_url" in data
        assert data["session_url"].startswith("http://localhost:")

    def test_launch_validates_case_dir_absolute(self, test_client, mock_manager):
        """POST with relative case_dir returns 400 with 'absolute' detail."""
        with patch(
            "api_server.routers.visualization.get_trame_session_manager",
            return_value=mock_manager,
        ):
            response = test_client.post(
                "/api/v1/visualization/launch",
                json={
                    "job_id": "J1",
                    "case_dir": "relative/path",
                },
            )

        assert response.status_code == 400
        assert "absolute" in response.json()["detail"].lower()

    def test_launch_validates_case_dir_exists(self, test_client, mock_manager):
        """POST with nonexistent case_dir returns 400."""
        with patch(
            "api_server.routers.visualization.get_trame_session_manager",
            return_value=mock_manager,
        ):
            response = test_client.post(
                "/api/v1/visualization/launch",
                json={
                    "job_id": "J1",
                    "case_dir": "/nonexistent/path/that/does/not/exist",
                },
            )

        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert "exist" in detail or "not" in detail

    def test_get_session_returns_200(self, test_client, mock_manager):
        """GET /visualization/PVW-12345678 returns 200 with session data."""
        with patch(
            "api_server.routers.visualization.get_trame_session_manager",
            return_value=mock_manager,
        ):
            response = test_client.get("/api/v1/visualization/PVW-12345678")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "PVW-12345678"
        assert "status" in data
        assert "port" in data

    def test_get_session_returns_404(self, test_client, mock_manager):
        """GET /visualization/NONEXISTENT returns 404."""
        mock_manager.get_session = MagicMock(return_value=None)
        with patch(
            "api_server.routers.visualization.get_trame_session_manager",
            return_value=mock_manager,
        ):
            response = test_client.get("/api/v1/visualization/NONEXISTENT")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_activity_returns_200(self, test_client, mock_manager):
        """POST /visualization/{id}/activity returns 200."""
        with patch(
            "api_server.routers.visualization.get_trame_session_manager",
            return_value=mock_manager,
        ):
            response = test_client.post("/api/v1/visualization/PVW-12345678/activity")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_delete_session_returns_200(self, test_client, mock_manager):
        """DELETE /visualization/{id} returns 200 with stopped status."""
        with patch(
            "api_server.routers.visualization.get_trame_session_manager",
            return_value=mock_manager,
        ):
            response = test_client.delete("/api/v1/visualization/PVW-12345678")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "PVW-12345678"
        assert data["status"] == "stopped"

    def test_session_url_uses_http_not_ws(self, test_client, mock_manager, temp_case_dir):
        """Launch response session_url starts with http:// (not ws://)."""
        with patch(
            "api_server.routers.visualization.get_trame_session_manager",
            return_value=mock_manager,
        ):
            response = test_client.post(
                "/api/v1/visualization/launch",
                json={
                    "job_id": "J1",
                    "case_dir": temp_case_dir,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["session_url"].startswith("http://localhost:")
        assert not data["session_url"].startswith("ws://localhost:")
