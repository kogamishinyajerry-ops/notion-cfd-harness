"""
Tests for Pipeline Control Endpoints (PIPE-02, PIPE-06):
- POST /api/v1/pipelines/{id}/start
- POST /api/v1/pipelines/{id}/cancel
- DELETE /api/v1/pipelines/{id}?cancel=true
"""
import asyncio
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, "/Users/Zhuanz/Desktop/notion-cfd-harness")

from fastapi.testclient import TestClient


class TestStartPipelineEndpoint(unittest.TestCase):
    """Tests for POST /api/v1/pipelines/{id}/start."""

    def setUp(self):
        from api_server.main import app
        self.client = TestClient(app)

    def tearDown(self):
        import api_server.routers.pipelines as pm
        pm._pipeline_service = None

    @patch("api_server.services.pipeline_executor.start_pipeline_executor")
    def test_start_pending_pipeline_returns_200(self, mock_start):
        """POST /api/v1/pipelines/{id}/start on PENDING pipeline returns 200 with started status."""
        from api_server.models import PipelineStatus, PipelineResponse
        from datetime import datetime

        from api_server.models import PipelineStep, StepType

        mock_step = PipelineStep(
            step_id="step1",
            step_type=StepType.GENERATE,
            step_order=0,
            depends_on=[],
            params={},
        )
        mock_pipeline = PipelineResponse(
            id="P1",
            name="Test",
            description=None,
            status=PipelineStatus.PENDING,
            steps=[mock_step],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = mock_pipeline

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps:
            mock_gps.return_value = mock_svc
            response = self.client.post("/api/v1/pipelines/P1/start", json={})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "started")
        self.assertEqual(data["pipeline_id"], "P1")

    def test_start_nonexistent_pipeline_returns_404(self):
        """POST /api/v1/pipelines/{id}/start on non-existent pipeline returns 404."""
        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = None

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps:
            mock_gps.return_value = mock_svc
            response = self.client.post("/api/v1/pipelines/NOTFOUND/start", json={})

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"])

    @patch("api_server.services.pipeline_executor.start_pipeline_executor")
    def test_start_already_running_pipeline_returns_409(self, mock_start):
        """POST /api/v1/pipelines/{id}/start on already-RUNNING pipeline returns 409."""
        from api_server.models import PipelineStatus, PipelineResponse
        from datetime import datetime

        mock_pipeline = PipelineResponse(
            id="P1",
            name="Test",
            description=None,
            status=PipelineStatus.RUNNING,
            steps=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = mock_pipeline

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps:
            mock_gps.return_value = mock_svc
            response = self.client.post("/api/v1/pipelines/P1/start", json={})

        self.assertEqual(response.status_code, 409)
        self.assertIn("already", response.json()["detail"].lower())

    def test_start_pipeline_with_no_steps_returns_400(self):
        """POST /api/v1/pipelines/{id}/start on pipeline with no steps returns 400."""
        from api_server.models import PipelineStatus, PipelineResponse
        from datetime import datetime

        mock_pipeline = PipelineResponse(
            id="P1",
            name="Empty",
            description=None,
            status=PipelineStatus.PENDING,
            steps=[],  # No steps
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = mock_pipeline

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps:
            mock_gps.return_value = mock_svc
            response = self.client.post("/api/v1/pipelines/P1/start", json={})

        self.assertEqual(response.status_code, 400)
        self.assertIn("no steps", response.json()["detail"])


class TestCancelPipelineEndpoint(unittest.TestCase):
    """Tests for POST /api/v1/pipelines/{id}/cancel."""

    def setUp(self):
        from api_server.main import app
        self.client = TestClient(app)

    def tearDown(self):
        import api_server.routers.pipelines as pm
        pm._pipeline_service = None

    def test_cancel_running_pipeline_returns_200(self):
        """POST /api/v1/pipelines/{id}/cancel on RUNNING pipeline returns 200 with cancelling status."""
        from api_server.models import PipelineStatus, PipelineResponse
        from datetime import datetime

        mock_pipeline = PipelineResponse(
            id="P1",
            name="Test",
            description=None,
            status=PipelineStatus.RUNNING,
            steps=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = mock_pipeline

        mock_handler = MagicMock()
        mock_handler.cancel_and_cleanup = AsyncMock(return_value=None)

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps, \
             patch("api_server.services.cleanup_handler.get_cleanup_handler") as mock_gch:
            mock_gps.return_value = mock_svc
            mock_gch.return_value = mock_handler

            response = self.client.post("/api/v1/pipelines/P1/cancel", json={})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "cancelling")
        self.assertEqual(data["pipeline_id"], "P1")

    def test_cancel_nonexistent_pipeline_returns_404(self):
        """POST /api/v1/pipelines/{id}/cancel on non-existent pipeline returns 404."""
        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = None

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps:
            mock_gps.return_value = mock_svc
            response = self.client.post("/api/v1/pipelines/NOTFOUND/cancel", json={})

        self.assertEqual(response.status_code, 404)

    def test_cancel_completed_pipeline_returns_200(self):
        """POST /api/v1/pipelines/{id}/cancel on COMPLETED pipeline returns 200 (no-op cancel)."""
        from api_server.models import PipelineStatus, PipelineResponse
        from datetime import datetime

        mock_pipeline = PipelineResponse(
            id="P1",
            name="Done",
            description=None,
            status=PipelineStatus.COMPLETED,
            steps=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = mock_pipeline

        mock_handler = MagicMock()
        mock_handler.cancel_and_cleanup = AsyncMock(return_value=None)

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps, \
             patch("api_server.services.cleanup_handler.get_cleanup_handler") as mock_gch:
            mock_gps.return_value = mock_svc
            mock_gch.return_value = mock_handler

            response = self.client.post("/api/v1/pipelines/P1/cancel", json={})

        # Cancel always returns 200; cleanup is attempted regardless of state
        self.assertEqual(response.status_code, 200)


class TestDeletePipelineWithCancel(unittest.TestCase):
    """Tests for DELETE /api/v1/pipelines/{id}?cancel=true."""

    def setUp(self):
        from api_server.main import app
        self.client = TestClient(app)

    def tearDown(self):
        import api_server.routers.pipelines as pm
        pm._pipeline_service = None

    def test_delete_running_pipeline_with_cancel_calls_cleanup_and_deletes(self):
        """DELETE /api/v1/pipelines/{id}?cancel=true on RUNNING pipeline calls cancel_and_cleanup then deletes."""
        from api_server.models import PipelineStatus, PipelineResponse
        from datetime import datetime

        mock_pipeline = PipelineResponse(
            id="P1",
            name="Running",
            description=None,
            status=PipelineStatus.RUNNING,
            steps=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = mock_pipeline
        mock_svc.delete_pipeline.return_value = True

        mock_handler = MagicMock()
        mock_handler.cancel_and_cleanup = AsyncMock(return_value=None)

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps, \
             patch("api_server.services.cleanup_handler.get_cleanup_handler") as mock_gch:
            mock_gps.return_value = mock_svc
            mock_gch.return_value = mock_handler

            response = self.client.delete("/api/v1/pipelines/P1?cancel=true")

        self.assertEqual(response.status_code, 204)
        mock_handler.cancel_and_cleanup.assert_called_once_with("P1")
        mock_svc.delete_pipeline.assert_called_once_with("P1")

    def test_delete_pending_pipeline_with_cancel_skips_cleanup(self):
        """DELETE /api/v1/pipelines/{id}?cancel=true on PENDING pipeline just deletes (no cleanup needed)."""
        from api_server.models import PipelineStatus, PipelineResponse
        from datetime import datetime

        mock_pipeline = PipelineResponse(
            id="P1",
            name="Pending",
            description=None,
            status=PipelineStatus.PENDING,
            steps=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = mock_pipeline
        mock_svc.delete_pipeline.return_value = True

        mock_handler = MagicMock()
        mock_handler.cancel_and_cleanup = AsyncMock(return_value=None)

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps, \
             patch("api_server.services.cleanup_handler.get_cleanup_handler") as mock_gch:
            mock_gps.return_value = mock_svc
            mock_gch.return_value = mock_handler

            response = self.client.delete("/api/v1/pipelines/P1?cancel=true")

        self.assertEqual(response.status_code, 204)
        # PENDING pipeline — cleanup not called (no running containers)
        mock_handler.cancel_and_cleanup.assert_not_called()
        mock_svc.delete_pipeline.assert_called_once_with("P1")

    def test_delete_pipeline_not_found_returns_404(self):
        """DELETE /api/v1/pipelines/{id}?cancel=true on non-existent pipeline returns 404."""
        mock_svc = MagicMock()
        mock_svc.get_pipeline.return_value = None

        with patch("api_server.routers.pipelines.get_pipeline_service") as mock_gps:
            mock_gps.return_value = mock_svc
            response = self.client.delete("/api/v1/pipelines/NOTFOUND?cancel=true")

        self.assertEqual(response.status_code, 404)


class TestMainLifespanCleanup(unittest.TestCase):
    """Tests that main.py lifespan calls cleanup_on_server_shutdown."""

    def test_lifespan_calls_cleanup_on_server_shutdown(self):
        """Verify lifespan shutdown section calls cleanup_handler.cleanup_on_server_shutdown()."""
        import inspect
        from api_server.main import lifespan

        source = inspect.getsource(lifespan)
        self.assertIn("cleanup_on_server_shutdown", source)
        self.assertIn("get_cleanup_handler", source)


if __name__ == "__main__":
    unittest.main()
