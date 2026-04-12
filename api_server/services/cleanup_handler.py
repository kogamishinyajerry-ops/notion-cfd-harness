"""
Pipeline Cleanup Handler (PIPE-06).

Stops Docker containers started by pipeline steps on CANCELLED or FAILED.

Docker ownership contract (from step_wrappers.py):
- Solver containers (step_type=run) are labeled --label pipeline_id=<id>
- Trame containers are labeled trame-{session_id} and owned by TrameSessionManager
- THIS handler: stops ONLY containers with label pipeline_id=<pipeline_id>
- THIS handler: NEVER touches containers without that label
- COMPLETED step outputs are preserved; only running containers are stopped
"""
import asyncio
import logging
import re
import subprocess
from typing import List, Optional

from api_server.models import PipelineStatus

logger = logging.getLogger(__name__)

GRACEFUL_TIMEOUT_SECONDS = 10  # PIPE-06: 10s before force-kill

# Valid pipeline_id pattern: alphanumeric, hyphens, underscores only
_PIPELINE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_pipeline_id(pipeline_id: str) -> None:
    """
    Validate that pipeline_id is safe for use in shell commands.

    Raises:
        ValueError: If pipeline_id contains invalid characters
    """
    if not _PIPELINE_ID_PATTERN.match(pipeline_id):
        raise ValueError(f"Invalid pipeline_id: {pipeline_id!r}. Must match {_PIPELINE_ID_PATTERN.pattern}")


class CleanupHandler:
    """Handles cleanup of Docker containers and background processes for aborted pipelines."""

    def _get_pipeline_containers(self, pipeline_id: str) -> List[str]:
        """
        Find Docker containers labeled pipeline_id=<pipeline_id>.
        Returns list of container IDs. Does NOT include trame containers.
        """
        _validate_pipeline_id(pipeline_id)
        try:
            result = subprocess.run(
                ["docker", "ps", "-q", "--filter", f"label=pipeline_id={pipeline_id}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.warning(f"docker ps failed for pipeline {pipeline_id}: {result.stderr}")
                return []
            container_ids = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
            logger.info(f"Found {len(container_ids)} pipeline containers for {pipeline_id}")
            return container_ids
        except FileNotFoundError:
            logger.warning("docker not found; skipping container cleanup")
            return []
        except subprocess.TimeoutExpired:
            logger.warning(f"docker ps timeout for pipeline {pipeline_id}")
            return []

    def _stop_container(self, container_id: str) -> bool:
        """
        Stop container gracefully (10s timeout), then force-kill if needed.
        Returns True if stopped successfully.
        """
        try:
            result = subprocess.run(
                ["docker", "stop", f"--time={GRACEFUL_TIMEOUT_SECONDS}", container_id],
                capture_output=True, text=True, timeout=GRACEFUL_TIMEOUT_SECONDS + 5
            )
            if result.returncode == 0:
                logger.info(f"Stopped container {container_id} gracefully")
                return True
            # Grace period expired — force kill
            logger.warning(f"Graceful stop failed for {container_id}; force killing")
            kill_result = subprocess.run(
                ["docker", "kill", container_id],
                capture_output=True, text=True, timeout=5
            )
            if kill_result.returncode == 0:
                logger.info(f"Force-killed container {container_id}")
                return True
            logger.error(f"Failed to kill container {container_id}: {kill_result.stderr}")
            return False
        except FileNotFoundError:
            logger.warning("docker not found; cannot stop container")
            return False
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout stopping container {container_id}")
            return False

    async def cleanup_pipeline(self, pipeline_id: str) -> None:
        """
        Stop all Docker containers labeled pipeline_id=<pipeline_id>.
        Runs container operations in asyncio.to_thread() to avoid blocking event loop.
        Preserves COMPLETED step outputs — only stops running containers.
        Does NOT touch trame containers (TrameSessionManager owns those).
        """
        def _do_cleanup():
            containers = self._get_pipeline_containers(pipeline_id)
            for container_id in containers:
                self._stop_container(container_id)

        await asyncio.to_thread(_do_cleanup)

    async def cancel_and_cleanup(self, pipeline_id: str) -> None:
        """
        Signal executor to cancel, then clean up Docker containers.
        Called by POST /pipelines/{id}/cancel and DELETE /pipelines/{id}?cancel=true.
        """
        from api_server.services.pipeline_executor import cancel_pipeline_executor
        cancelled = cancel_pipeline_executor(pipeline_id)
        if cancelled:
            logger.info(f"Pipeline {pipeline_id} executor signalled for cancellation")
        # Always attempt Docker cleanup regardless of executor state
        await self.cleanup_pipeline(pipeline_id)

    async def cleanup_on_server_shutdown(self) -> None:
        """
        Stop all containers for pipelines that are still in RUNNING/MONITORING/
        VISUALIZING/REPORTING state at server shutdown.
        Called from main.py lifespan shutdown hook.
        """
        try:
            from api_server.services.pipeline_db import get_pipeline_db_service
            db = get_pipeline_db_service()
            pipelines = db.list_pipelines()
            active_statuses = {
                PipelineStatus.RUNNING.value,
                PipelineStatus.MONITORING.value,
                PipelineStatus.VISUALIZING.value,
                PipelineStatus.REPORTING.value,
            }
            for p in pipelines:
                status_val = p.status.value if hasattr(p.status, 'value') else p.status
                if status_val in active_statuses:
                    logger.warning(f"Server shutdown: cleaning up pipeline {p.id} (status={status_val})")
                    await self.cleanup_pipeline(p.id)
        except Exception as e:
            logger.error(f"cleanup_on_server_shutdown error: {e}")


# Module-level singleton
_cleanup_handler: Optional[CleanupHandler] = None


def get_cleanup_handler() -> CleanupHandler:
    """Get or create global CleanupHandler singleton."""
    global _cleanup_handler
    if _cleanup_handler is None:
        _cleanup_handler = CleanupHandler()
    return _cleanup_handler
