"""
Tests for CleanupHandler (PIPE-06): Docker container cleanup for aborted pipelines.
"""
import asyncio
import sys
import unittest
from unittest.mock import MagicMock, patch, call

# Ensure api_server is on path
sys.path.insert(0, "/Users/Zhuanz/Desktop/notion-cfd-harness")

from api_server.services.cleanup_handler import (
    CleanupHandler,
    get_cleanup_handler,
    GRACEFUL_TIMEOUT_SECONDS,
)


class AsyncMock(MagicMock):
    """Async mock that can be awaited."""
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


class TestCleanupHandlerDockerStop(unittest.TestCase):
    """Tests for _stop_container and _get_pipeline_containers."""

    def setUp(self):
        self.handler = CleanupHandler()

    @patch("subprocess.run")
    def test_get_pipeline_containers_returns_container_ids(self, mock_run):
        """docker ps returns 2 container IDs for pipeline P1."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc123\ndef456\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        containers = self.handler._get_pipeline_containers("P1")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        self.assertEqual(call_args[0][0], ["docker", "ps", "-q", "--filter", "label=pipeline_id=P1"])
        self.assertEqual(containers, ["abc123", "def456"])

    @patch("subprocess.run")
    def test_get_pipeline_containers_empty_returns_empty_list(self, mock_run):
        """docker ps with no containers returns empty list."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        containers = self.handler._get_pipeline_containers("P2")

        self.assertEqual(containers, [])

    @patch("subprocess.run")
    def test_get_pipeline_containers_docker_ps_failed_returns_empty(self, mock_run):
        """docker ps returning non-zero exit code logs warning and returns empty."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "docker daemon not running"
        mock_run.return_value = mock_result

        containers = self.handler._get_pipeline_containers("P3")

        self.assertEqual(containers, [])

    @patch("subprocess.run")
    def test_stop_container_graceful_stop_succeeds(self, mock_run):
        """docker stop with --time=10 succeeds, returns True without kill."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = self.handler._stop_container("container123")

        self.assertTrue(result)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "docker")
        self.assertEqual(call_args[1], "stop")
        self.assertIn("--time=10", call_args[1:])

    @patch("subprocess.run")
    def test_stop_container_graceful_fails_then_force_kill_succeeds(self, mock_run):
        """docker stop fails (non-zero), docker kill is called and succeeds."""
        # First call: docker stop fails
        mock_stop = MagicMock()
        mock_stop.returncode = 1
        mock_stop.stderr = "timeout"
        # Second call: docker kill succeeds
        mock_kill = MagicMock()
        mock_kill.returncode = 0
        mock_run.side_effect = [mock_stop, mock_kill]

        result = self.handler._stop_container("container123")

        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)
        kill_call = mock_run.call_args_list[1][0][0]
        self.assertEqual(kill_call[0], "docker")
        self.assertEqual(kill_call[1], "kill")

    @patch("subprocess.run")
    def test_stop_container_both_fail_returns_false(self, mock_run):
        """docker stop fails and docker kill fails, returns False."""
        mock_fail = MagicMock()
        mock_fail.returncode = 1
        mock_fail.stderr = "container not found"
        mock_run.return_value = mock_fail

        result = self.handler._stop_container("ghost-container")

        self.assertFalse(result)

    @patch("subprocess.run")
    def test_stop_container_uses_graceful_timeout_seconds(self, mock_run):
        """_stop_container uses GRACEFUL_TIMEOUT_SECONDS=10 in docker stop call."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        self.handler._stop_container("abc")

        stop_call_args = mock_run.call_args[0][0]
        self.assertIn(f"--time={GRACEFUL_TIMEOUT_SECONDS}", stop_call_args)
        self.assertEqual(GRACEFUL_TIMEOUT_SECONDS, 10)


class TestCleanupHandlerAsyncMethods(unittest.TestCase):
    """Tests for async cleanup methods."""

    def setUp(self):
        self.handler = CleanupHandler()

    @patch("subprocess.run")
    def test_cleanup_pipeline_calls_stop_for_each_container(self, mock_run):
        """cleanup_pipeline calls docker stop for each container found."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "c1\nc2\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        asyncio.run(self.handler.cleanup_pipeline("P1"))

        # docker ps called once + docker stop for each of 2 containers = 3 calls
        self.assertEqual(mock_run.call_count, 3)
        # Verify stop calls
        self.assertEqual(mock_run.call_args_list[1][0][0], ["docker", "stop", "--time=10", "c1"])
        self.assertEqual(mock_run.call_args_list[2][0][0], ["docker", "stop", "--time=10", "c2"])

    @patch("subprocess.run")
    def test_cleanup_pipeline_no_containers_does_not_raise(self, mock_run):
        """cleanup_pipeline with no containers found is a no-op."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Should not raise
        asyncio.run(self.handler.cleanup_pipeline("P-noexist"))

        # Only docker ps was called
        self.assertEqual(mock_run.call_count, 1)

    @patch("api_server.services.pipeline_executor.cancel_pipeline_executor")
    @patch("subprocess.run")
    def test_cancel_and_cleanup_calls_cancel_then_cleanup(self, mock_run, mock_cancel):
        """cancel_and_cleanup calls cancel_pipeline_executor then cleanup_pipeline."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "c1\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        mock_cancel.return_value = True

        asyncio.run(self.handler.cancel_and_cleanup("P1"))

        mock_cancel.assert_called_once_with("P1")
        # cleanup_pipeline was also called (docker ps returns c1)
        self.assertGreater(mock_run.call_count, 0)

    @patch("api_server.services.pipeline_executor.cancel_pipeline_executor")
    @patch("subprocess.run")
    def test_cancel_and_cleanup_always_attempts_cleanup_even_if_cancel_returns_false(self, mock_run, mock_cancel):
        """cancel_and_cleanup always calls cleanup_pipeline regardless of cancel result."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        mock_cancel.return_value = False  # No running executor found

        asyncio.run(self.handler.cancel_and_cleanup("P-noexist"))

        mock_cancel.assert_called_once_with("P-noexist")
        # cleanup_pipeline was still attempted (docker ps called)
        docker_ps_calls = [c for c in mock_run.call_args_list if c[0][0][0] == "docker" and c[0][0][1] == "ps"]
        self.assertEqual(len(docker_ps_calls), 1)


class TestCleanupOnServerShutdown(unittest.TestCase):
    """Tests for cleanup_on_server_shutdown."""

    @patch("api_server.services.pipeline_db.get_pipeline_db_service")
    def test_cleanup_on_server_shutdown_cleans_running_pipelines(self, mock_get_db):
        """cleanup_on_server_shutdown cleans pipelines with RUNNING/MONITORING/VISUALIZING/REPORTING status."""
        from api_server.models import PipelineStatus, PipelineResponse
        from datetime import datetime

        mock_pipeline_running = PipelineResponse(
            id="RUN-01", name="Running", description=None,
            status=PipelineStatus.RUNNING, steps=[], config={},
            created_at=datetime.now(), updated_at=datetime.now()
        )
        mock_pipeline_monitoring = PipelineResponse(
            id="MON-01", name="Monitoring", description=None,
            status=PipelineStatus.MONITORING, steps=[], config={},
            created_at=datetime.now(), updated_at=datetime.now()
        )
        mock_pipeline_completed = PipelineResponse(
            id="DONE-01", name="Done", description=None,
            status=PipelineStatus.COMPLETED, steps=[], config={},
            created_at=datetime.now(), updated_at=datetime.now()
        )

        mock_db = MagicMock()
        mock_db.list_pipelines.return_value = [
            mock_pipeline_running, mock_pipeline_monitoring, mock_pipeline_completed
        ]
        mock_get_db.return_value = mock_db

        handler = CleanupHandler()
        with patch.object(handler, "cleanup_pipeline", new_callable=AsyncMock) as mock_cleanup:
            asyncio.run(handler.cleanup_on_server_shutdown())

            # Only RUNNING and MONITORING pipelines should be cleaned
            self.assertEqual(mock_cleanup.call_count, 2)
            called_ids = {c.args[0] for c in mock_cleanup.call_args_list}
            self.assertIn("RUN-01", called_ids)
            self.assertIn("MON-01", called_ids)
            self.assertNotIn("DONE-01", called_ids)

    @patch("api_server.services.pipeline_db.get_pipeline_db_service")
    def test_cleanup_on_server_shutdown_handles_db_error(self, mock_get_db):
        """cleanup_on_server_shutdown logs error but does not raise on DB failure."""
        mock_get_db.side_effect = RuntimeError("DB connection failed")

        handler = CleanupHandler()
        # Should not raise
        asyncio.run(handler.cleanup_on_server_shutdown())


if __name__ == "__main__":
    unittest.main()
