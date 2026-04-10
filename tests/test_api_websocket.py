"""
WebSocket Tests

Tests for WebSocket job progress streaming functionality.
"""

import asyncio
import pytest
from fastapi.testclient import TestClient
from fastapi import WebSocket

from api_server.main import app
from api_server.services.websocket_manager import WebSocketManager, get_websocket_manager
from api_server.services.job_service import JobService, get_job_service, _JOBS
from api_server.models import JobResponse, JobSubmission, JobStatus


@pytest.fixture
def client():
    """FastAPI test client fixture."""
    with TestClient(app) as test_client:
        yield test_client


class TestWebSocketManager:
    """Tests for the WebSocket connection manager."""

    @pytest.fixture
    def manager(self):
        """Create a fresh WebSocket manager for each test."""
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_connect_registers_connection(self, manager):
        """Test that connect adds the WebSocket to the job's subscriber set."""
        # Create a mock WebSocket
        mock_ws = MockWebSocket()

        await manager.connect(mock_ws, "JOB-123")

        assert manager.get_subscriber_count("JOB-123") == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager):
        """Test that disconnect removes the WebSocket from the job's subscriber set."""
        mock_ws = MockWebSocket()

        await manager.connect(mock_ws, "JOB-123")
        await manager.disconnect(mock_ws, "JOB-123")

        assert manager.get_subscriber_count("JOB-123") == 0

    @pytest.mark.asyncio
    async def test_multiple_subscribers_per_job(self, manager):
        """Test that multiple WebSockets can subscribe to the same job."""
        mock_ws1 = MockWebSocket()
        mock_ws2 = MockWebSocket()
        mock_ws3 = MockWebSocket()

        await manager.connect(mock_ws1, "JOB-123")
        await manager.connect(mock_ws2, "JOB-123")
        await manager.connect(mock_ws3, "JOB-123")

        assert manager.get_subscriber_count("JOB-123") == 3

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_subscribers(self, manager):
        """Test that broadcast sends messages to all subscribers of a job."""
        mock_ws1 = MockWebSocket()
        mock_ws2 = MockWebSocket()

        await manager.connect(mock_ws1, "JOB-123")
        await manager.connect(mock_ws2, "JOB-123")

        await manager.broadcast("JOB-123", {"type": "progress", "progress": 50})

        assert len(mock_ws1.sent_messages) == 1
        assert len(mock_ws2.sent_messages) == 1
        assert mock_ws1.sent_messages[0]["type"] == "progress"
        assert mock_ws1.sent_messages[0]["progress"] == 50

    @pytest.mark.asyncio
    async def test_broadcast_only_affects_target_job(self, manager):
        """Test that broadcast to one job doesn't affect subscribers of other jobs."""
        mock_ws1 = MockWebSocket()
        mock_ws2 = MockWebSocket()

        await manager.connect(mock_ws1, "JOB-123")
        await manager.connect(mock_ws2, "JOB-456")

        await manager.broadcast("JOB-123", {"type": "test", "job_id": "JOB-123"})

        assert len(mock_ws1.sent_messages) == 1
        assert len(mock_ws2.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_get_total_connections(self, manager):
        """Test total connection count across all jobs."""
        mock_ws1 = MockWebSocket()
        mock_ws2 = MockWebSocket()
        mock_ws3 = MockWebSocket()

        await manager.connect(mock_ws1, "JOB-123")
        await manager.connect(mock_ws2, "JOB-123")
        await manager.connect(mock_ws3, "JOB-456")

        assert manager.get_total_connections() == 3

    @pytest.mark.asyncio
    async def test_cleanup_empty_job_subscriptions(self, manager):
        """Test that job is removed from registry when last subscriber disconnects."""
        mock_ws = MockWebSocket()

        await manager.connect(mock_ws, "JOB-123")
        assert manager.get_subscriber_count("JOB-123") == 1

        await manager.disconnect(mock_ws, "JOB-123")
        assert manager.get_subscriber_count("JOB-123") == 0

    def test_get_subscriber_count_nonexistent_job(self, manager):
        """Test subscriber count for a job that has no subscribers."""
        assert manager.get_subscriber_count("JOB-NONE") == 0


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.accepted = False
        self.sent_messages = []
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, message: dict):
        self.sent_messages.append(message)

    async def send_text(self, message: str):
        self.sent_messages.append(message)

    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    async def receive_text(self):
        # Default to ping - test can override
        return "ping"


class TestWebSocketEndpoint:
    """Integration tests for the WebSocket endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        return TestClient(app)

    @pytest.fixture
    def job_service(self):
        """Get the job service instance."""
        return get_job_service()

    def test_websocket_endpoint_exists(self, client):
        """Test that the WebSocket endpoint path is valid."""
        # We can't actually test WebSocket without a real connection,
        # but we can verify the route is registered
        routes = [route.path for route in app.routes]
        assert "/ws/jobs/{job_id}" in routes

    def test_websocket_status_endpoint(self, client):
        """Test that WebSocket status endpoint works (returns 200)."""
        response = client.get("/ws/status")
        assert response.status_code == 200
        data = response.json()
        assert "total_connections" in data

    def test_websocket_subscriber_count_endpoint(self, client):
        """Test that subscriber count endpoint works (returns 200)."""
        response = client.get("/ws/jobs/JOB-123/subscribers")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "JOB-123"
        assert "subscriber_count" in data


class TestJobProgressBroadcasting:
    """Tests for job progress broadcasting via WebSocket."""

    @pytest.fixture(autouse=True)
    def reset_jobs(self):
        """Reset job storage before each test."""
        _JOBS.clear()
        yield
        _JOBS.clear()

    def test_job_service_has_broadcast_capability(self):
        """Test that job service can broadcast to WebSocket manager."""
        service = get_job_service()
        manager = get_websocket_manager()

        # Verify we can access both
        assert service is not None
        assert manager is not None

    def test_job_submission_via_api_returns_job_response(self, client):
        """Test that job submission via API returns a proper JobResponse."""
        submission = {
            "case_id": "CASE-001",
            "job_type": "run",
            "parameters": {},
            "async_mode": True,
        }

        response = client.post("/api/v1/jobs", json=submission)

        assert response.status_code == 201
        data = response.json()
        assert data["case_id"] == "CASE-001"
        assert data["job_type"] == "run"
        assert data["status"] == "pending"

    def test_job_to_dict_conversion(self):
        """Test that _job_to_dict produces a valid dictionary."""
        service = get_job_service()

        # Create a mock job to test _job_to_dict without async issues
        from datetime import datetime
        mock_job = JobResponse(
            job_id="JOB-TEST001",
            case_id="CASE-001",
            job_type="run",
            status=JobStatus.PENDING,
            submitted_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            progress=50.0,
            result=None,
            error=None,
        )

        job_dict = service._job_to_dict(mock_job)

        assert job_dict["job_id"] == "JOB-TEST001"
        assert job_dict["case_id"] == "CASE-001"
        assert job_dict["job_type"] == "run"
        assert job_dict["status"] == "pending"
        assert job_dict["progress"] == 50.0
