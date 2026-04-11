"""
Trame Session Manager

Manages Trame Docker container lifecycle for interactive 3D CFD visualization.
Each session runs as a sidecar container with the case directory mounted read-only.

Replaces: api_server/services/paraview_web_launcher.py (ParaViewWebManager)
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator, Optional

logger = logging.getLogger(__name__)

try:
    from api_server.config import (
        PARAVIEW_WEB_IMAGE,
        PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES,
        PARAVIEW_WEB_PORT_RANGE_END,
        PARAVIEW_WEB_PORT_RANGE_START,
    )
except ImportError:
    # Defaults if config not yet updated
    PARAVIEW_WEB_IMAGE = "cfd-workbench:openfoam-v10"
    PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES = 30
    PARAVIEW_WEB_PORT_RANGE_START = 8081
    PARAVIEW_WEB_PORT_RANGE_END = 8090

try:
    from api_server.models import TrameSession
except ImportError:
    # Forward reference until models.py is updated
    TrameSession = None  # type: ignore


class TrameSessionError(Exception):
    """Raised when Trame session operations fail."""
    pass


class TrameSessionManager:
    """
    Manages Trame Docker container lifecycle.

    Each session is a sidecar container that persists until shutdown or idle timeout.
    Containers are named `trame-{session_id}` for clean docker kill later.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, TrameSession] = {}
        self._port_allocator: Iterator[int] = iter(self._cycle_ports())
        self._idle_check_interval = 60  # seconds between idle checks
        self._idle_task: Optional[asyncio.Task] = None

    def _cycle_ports(self) -> Iterator[int]:
        """Cycle through the configured port range indefinitely."""
        while True:
            for port in range(PARAVIEW_WEB_PORT_RANGE_START, PARAVIEW_WEB_PORT_RANGE_END + 1):
                yield port

    def _next_port(self) -> int:
        """Get the next available port from the range."""
        return next(self._port_allocator)

    def validate_docker_available(self) -> bool:
        """Check Docker daemon is responsive."""
        docker = shutil.which("docker")
        if not docker:
            return False
        try:
            import subprocess
            result = subprocess.run(
                [docker, "info"], capture_output=True, timeout=10, check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    async def launch_session(
        self,
        session_id: str,
        case_dir: str,
        port: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> TrameSession:
        """
        Launch a Trame session as a Docker sidecar container.

        Args:
            session_id: Unique session identifier
            case_dir: Absolute path to the OpenFOAM case directory (mounted read-only)
            port: Host port to expose (auto-allocated if None)
            job_id: Optional associated job ID

        Returns:
            TrameSession with container_id, port, auth_key

        Raises:
            TrameSessionError: If Docker is unavailable or container fails to start.
        """
        # Validate Docker availability
        if not self.validate_docker_available():
            raise TrameSessionError("Docker daemon is not running or not accessible")

        # Validate case_dir is absolute
        case_path = os.path.abspath(case_dir)
        if not os.path.isdir(case_path):
            raise TrameSessionError(f"case_dir does not exist or is not a directory: {case_path}")

        # Allocate port
        allocated_port = port if port is not None else self._next_port()

        # Generate auth key
        auth_key = secrets.token_urlsafe(16)

        # Create session record early (status=launching)
        session = TrameSession(
            session_id=session_id,
            job_id=job_id,
            container_id="",  # filled after container starts
            port=allocated_port,
            case_dir=case_path,
            auth_key=auth_key,
            status="launching",
        )
        self._sessions[session_id] = session

        try:
            # Start container in detached mode
            container_id = await self._start_container(
                session_id=session_id,
                port=allocated_port,
                case_path=case_path,
            )

            # Update session with container_id
            session.container_id = container_id

            # Poll for ready state
            await self._wait_for_ready(session_id, container_id, allocated_port)

            # Mark as ready
            session.status = "ready"
            self._sessions[session_id] = session
            return session

        except TrameSessionError:
            # Clean up session on failure
            self._sessions.pop(session_id, None)
            raise

    async def _start_container(
        self,
        session_id: str,
        port: int,
        case_path: str,
    ) -> str:
        """
        Start the Trame Docker container in detached mode.

        Command: docker run -d --platform linux/amd64 --name trame-{session_id}
                 -v {case_path}:/data:ro -p {port}:9000
                 {PARAVIEW_WEB_IMAGE}
                 pvpython /trame_server.py --port 9000

        No --entrypoint override, no config JSON, no adv_protocols.py mount.
        Container internal port is always 9000 (mapped to host port {port}).
        """
        docker = shutil.which("docker")
        if not docker:
            raise TrameSessionError("docker executable not found")

        container_name = f"trame-{session_id}"

        proc = await asyncio.create_subprocess_exec(
            docker,
            "run",
            "-d",  # detached
            "--platform", "linux/amd64",
            "--name", container_name,
            "-v", f"{case_path}:/data:ro",
            "-p", f"{port}:9000",
            PARAVIEW_WEB_IMAGE,
            "pvpython", "/trame_server.py", "--port", "9000",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode().strip()
            raise TrameSessionError(f"Failed to start Trame container: {err[:300]}")

        container_id = stdout.decode().strip()
        if not container_id:
            raise TrameSessionError("Container started but no container ID returned")

        return container_id

    async def _wait_for_ready(
        self,
        session_id: str,
        container_id: str,
        port: int,
        timeout: int = 60,
    ) -> None:
        """
        Poll HTTP at http://localhost:{port} until 200 response or timeout.

        Trame serves HTTP directly (not WebSocket at /ws).
        """
        docker = shutil.which("docker")
        if not docker:
            raise TrameSessionError("docker executable not found")

        elapsed = 0
        interval = 1.0

        while elapsed < timeout:
            await asyncio.sleep(interval)

            # Check if container is still running
            inspect_proc = await asyncio.create_subprocess_exec(
                docker, "inspect", "-f", "{{.State.Running}}", container_id,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            inspect_out, _ = await inspect_proc.communicate()
            if inspect_proc.returncode != 0 or inspect_out.decode().strip() != "true":
                # Container stopped — get logs for error info
                logs_proc = await asyncio.create_subprocess_exec(
                    docker, "logs", container_id,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                )
                logs_out, _ = await logs_proc.communicate()
                raise TrameSessionError(
                    f"Container exited during startup. Logs:\n{logs_out.decode()[:500]}"
                )

            # Try HTTP health check
            try:
                import aiohttp
                async with aiohttp.ClientSession() as http_session:
                    try:
                        async with http_session.get(
                            f"http://localhost:{port}",
                            timeout=aiohttp.ClientTimeout(total=2),
                        ) as resp:
                            if resp.status == 200:
                                return  # Ready
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        pass
            except ImportError:
                # aiohttp not available — try urllib
                try:
                    import urllib.request
                    urllib.request.urlopen(f"http://localhost:{port}", timeout=2)
                    return
                except Exception:
                    pass

            elapsed += interval

        raise TrameSessionError(
            f"Trame container did not become ready within {timeout}s "
            f"(session_id={session_id})"
        )

    async def shutdown_session(self, session_id: str) -> None:
        """
        Stop a Trame session gracefully via docker kill.

        Args:
            session_id: The session to stop

        Raises:
            TrameSessionError: If the session cannot be stopped
        """
        session = self._sessions.get(session_id)
        if not session:
            return  # Already gone

        session.status = "stopping"
        self._sessions[session_id] = session

        docker = shutil.which("docker")
        if not docker:
            raise TrameSessionError("docker executable not found")

        container_name = f"trame-{session_id}"

        try:
            proc = await asyncio.create_subprocess_exec(
                docker, "kill", container_name,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            # Ignore return code — container may already be stopped
        except Exception:
            pass

        # Remove the session
        self._sessions.pop(session_id, None)

    def get_session(self, session_id: str) -> Optional[TrameSession]:
        """Get session info by ID."""
        return self._sessions.get(session_id)

    def update_activity(self, session_id: str) -> None:
        """Update the last_activity timestamp for a session."""
        session = self._sessions.get(session_id)
        if session:
            session.last_activity = datetime.now(timezone.utc)
            self._sessions[session_id] = session

    async def _idle_monitor(self) -> None:
        """Background task: check idle sessions every 60 seconds and shut down expired ones."""
        while True:
            await asyncio.sleep(self._idle_check_interval)
            await self._shutdown_idle_sessions()

    async def _shutdown_idle_sessions(self) -> None:
        """Stop sessions that have been idle longer than IDLE_TIMEOUT_MINUTES."""
        now = datetime.now(timezone.utc)
        timeout = timedelta(minutes=PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES)
        for session_id, session in list(self._sessions.items()):
            if session.status == "stopping" or session.status == "stopped":
                continue
            if now - session.last_activity > timeout:
                logger.info(f"Idle timeout for session {session_id}, shutting down")
                await self.shutdown_session(session_id)

    def start_idle_monitor(self) -> None:
        """Start the background idle monitoring task. Call once at app startup."""
        if self._idle_task is None:
            self._idle_task = asyncio.create_task(self._idle_monitor())
            logger.info("Trame idle monitor started")

    async def stop_idle_monitor(self) -> None:
        """Stop the background idle monitoring task."""
        if self._idle_task is not None:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass
            self._idle_task = None
            logger.info("Trame idle monitor stopped")


# =============================================================================
# Singleton
# =============================================================================


_trame_session_manager: Optional[TrameSessionManager] = None


def get_trame_session_manager() -> TrameSessionManager:
    """Get or create the singleton TrameSessionManager instance."""
    global _trame_session_manager
    if _trame_session_manager is None:
        _trame_session_manager = TrameSessionManager()
    return _trame_session_manager
