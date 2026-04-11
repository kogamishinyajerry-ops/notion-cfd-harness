"""
ParaView Web Launcher Service

Manages ParaView Web Docker container lifecycle for interactive 3D CFD visualization.
Each session runs as a sidecar container with the case directory mounted read-only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Iterator, Literal, Optional

logger = logging.getLogger(__name__)

try:
    from api_server.config import (
        PARAVIEW_WEB_IMAGE,
        PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES,
        PARAVIEW_WEB_LAUNCHER_TIMEOUT,
        PARAVIEW_WEB_PORT_RANGE_END,
        PARAVIEW_WEB_PORT_RANGE_START,
    )
except ImportError:
    # Defaults if config not yet updated (Task 3)
    PARAVIEW_WEB_IMAGE = "openfoam/openfoam10-paraview510"
    PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES = 30
    PARAVIEW_WEB_LAUNCHER_TIMEOUT = 60
    PARAVIEW_WEB_PORT_RANGE_START = 8081
    PARAVIEW_WEB_PORT_RANGE_END = 8090

try:
    from api_server.models import ParaViewWebSession
except ImportError:
    # Forward reference until Task 3
    ParaViewWebSession = None  # type: ignore


class ParaViewWebError(Exception):
    """Raised when ParaView Web operations fail."""

    pass


async def verify_paraview_web_image(image: str = PARAVIEW_WEB_IMAGE) -> tuple[bool, str]:
    """
    Verify the ParaView Web Docker image has vtk.web.launcher module.

    Returns:
        (success, message) — success=True if launcher module found
    """
    docker = shutil.which("docker")
    if not docker:
        return False, "Docker executable not found"

    # Quick docker info check
    proc = await asyncio.create_subprocess_exec(
        docker, "info", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if proc.returncode != 0:
        return False, "Docker daemon not running"

    # Run a lightweight check: try to find the launcher module path
    # Use pvpython -c "import vtk.web.launcher" inside the container
    proc = await asyncio.create_subprocess_exec(
        docker, "run", "--rm", image,
        "pvpython", "-c",
        "import vtk.web.launcher; import os; print(os.path.dirname(vtk.web.launcher.__file__))",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode == 0:
        launcher_path = stdout.decode().strip()
        return True, launcher_path
    else:
        err = stderr.decode().strip()
        return False, f"vtk.web.launcher not found: {err[:200]}"


class ParaviewWebManager:
    """
    Manages ParaView Web Docker container lifecycle.

    Each session is a sidecar container that persists until shutdown or idle timeout.
    Containers are named `pvweb-{session_id}` for clean docker kill later.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, ParaViewWebSession] = {}
        self._port_allocator: Iterator[int] = iter(self._cycle_ports())
        self._launcher_path: Optional[str] = None
        self._verified: bool = False
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

    async def _verify_image(self) -> None:
        """Fail fast if the Docker image doesn't have the required launcher module."""
        if self._verified:
            return
        ok, msg = await verify_paraview_web_image()
        if not ok:
            raise ParaViewWebError(f"ParaView Web image verification failed: {msg}")
        self._launcher_path = msg
        self._verified = True

    async def launch_session(
        self,
        session_id: str,
        case_dir: str,
        port: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> ParaViewWebSession:
        """
        Launch a ParaView Web session as a Docker sidecar container.

        Args:
            session_id: Unique session identifier
            case_dir: Absolute path to the OpenFOAM case directory (mounted read-only)
            port: Host port to expose (auto-allocated if None)
            job_id: Optional associated job ID

        Returns:
            ParaViewWebSession with container_id, port, auth_key

        Raises:
            ParaViewWebError: If Docker is unavailable, image verification fails,
                              or container fails to start within the timeout.
        """
        # Validate Docker availability
        if not self.validate_docker_available():
            raise ParaViewWebError("Docker daemon is not running or not accessible")

        # Verify the image has the required launcher module
        await self._verify_image()

        # Validate case_dir is absolute
        case_path = os.path.abspath(case_dir)
        if not os.path.isdir(case_path):
            raise ParaViewWebError(f"case_dir does not exist or is not a directory: {case_path}")

        # Allocate port
        allocated_port = port if port is not None else self._next_port()

        # Generate auth key
        auth_key = secrets.token_urlsafe(16)

        # Create session record early (status=launching)
        session = ParaViewWebSession(
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
            # Build launcher config JSON
            config = self._build_launcher_config(
                session_id=session_id,
                port=allocated_port,
                auth_key=auth_key,
                case_dir=case_path,
            )

            # Write config to a temp file to be mounted into container
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(config, f)
                config_path = f.name

            try:
                # Start container in detached mode (no --rm so container persists)
                container_id = await self._start_container(
                    session_id=session_id,
                    config_path=config_path,
                    port=allocated_port,
                    case_path=case_path,
                )
            finally:
                # Clean up temp config file
                try:
                    os.unlink(config_path)
                except OSError:
                    pass

            # Update session with container_id
            session.container_id = container_id

            # Poll for ready state
            await self._wait_for_ready(session_id, container_id)

            # Mark as ready
            session.status = "ready"
            self._sessions[session_id] = session
            return session

        except ParaViewWebError:
            # Clean up session on failure
            self._sessions.pop(session_id, None)
            raise

    def _build_launcher_config(
        self,
        session_id: str,
        port: int,
        auth_key: str,
        case_dir: str,
    ) -> dict:
        """Build the ParaView Web launcher configuration JSON."""
        return {
            "host": "0.0.0.0",
            "port": 9000,
            "sessionURL": f"ws://${{host}}:{port}/ws",
            "timeout": 10,
            "fields": ["sessionURL", "secret", "id"],
            "resources": [{"host": "localhost", "port_range": [PARAVIEW_WEB_PORT_RANGE_START, PARAVIEW_WEB_PORT_RANGE_END]}],
            "apps": {
                "openfoam_viewer": {
                    "cmd": [
                        "pvpython", "-dr",
                        "lib/site-packages/vtk/web/launcher.py",
                        "--port", "${port}",
                        "--data", "/data",
                        "--authKey", "${secret}",
                        "-f",
                    ],
                    "ready_line": "Starting factory",
                }
            },
        }

    async def _start_container(
        self,
        session_id: str,
        config_path: str,
        port: int,
        case_path: str,
    ) -> str:
        """Start the ParaView Web Docker container in detached mode."""
        docker = shutil.which("docker")
        if not docker:
            raise ParaViewWebError("docker executable not found")

        container_name = f"pvweb-{session_id}"

        proc = await asyncio.create_subprocess_exec(
            docker,
            "run",
            "-d",  # detached
            "--name", container_name,
            "-v", f"{config_path}:/tmp/launcher_config.json:ro",
            "-v", f"{case_path}:/data:ro",
            "-p", f"{port}:9000",
            "--entrypoint", "pvpython",
            PARAVIEW_WEB_IMAGE,
            "lib/site-packages/vtk/web/launcher.py",
            "/tmp/launcher_config.json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode().strip()
            raise ParaViewWebError(f"Failed to start ParaView Web container: {err[:300]}")

        container_id = stdout.decode().strip()
        if not container_id:
            raise ParaViewWebError("Container started but no container ID returned")

        return container_id

    async def _wait_for_ready(self, session_id: str, container_id: str) -> None:
        """Poll container logs until 'Starting factory' appears or timeout."""
        docker = shutil.which("docker")
        if not docker:
            raise ParaViewWebError("docker executable not found")

        timeout = PARAVIEW_WEB_LAUNCHER_TIMEOUT
        elapsed = 0
        interval = 1.0

        while elapsed < timeout:
            await asyncio.sleep(interval)

            proc = await asyncio.create_subprocess_exec(
                docker, "logs", "--tail", "20", container_id,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            logs = stdout.decode()

            if "Starting factory" in logs or "Starting Factory" in logs:
                return  # Ready

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
                raise ParaViewWebError(
                    f"Container exited during startup. Logs:\n{logs_out.decode()[:500]}"
                )

            elapsed += interval

        raise ParaViewWebError(
            f"ParaView Web container did not become ready within {timeout}s "
            f"(session_id={session_id})"
        )

    async def shutdown_session(self, session_id: str) -> None:
        """
        Stop a ParaView Web session gracefully via docker kill.

        Args:
            session_id: The session to stop

        Raises:
            ParaViewWebError: If the session cannot be stopped
        """
        session = self._sessions.get(session_id)
        if not session:
            return  # Already gone

        session.status = "stopping"
        self._sessions[session_id] = session

        docker = shutil.which("docker")
        if not docker:
            raise ParaViewWebError("docker executable not found")

        container_name = f"pvweb-{session_id}"

        try:
            # First try docker kill (SIGKILL, immediate)
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

    def get_session(self, session_id: str) -> Optional[ParaViewWebSession]:
        """Get session info by ID."""
        return self._sessions.get(session_id)

    def update_activity(self, session_id: str) -> None:
        """Update the last_activity timestamp for a session."""
        session = self._sessions.get(session_id)
        if session:
            session.last_activity = datetime.utcnow()
            self._sessions[session_id] = session

    async def _idle_monitor(self) -> None:
        """Background task: check idle sessions every 60 seconds and shut down expired ones."""
        while True:
            await asyncio.sleep(self._idle_check_interval)
            await self._shutdown_idle_sessions()

    async def _shutdown_idle_sessions(self) -> None:
        """Stop sessions that have been idle longer than IDLE_TIMEOUT_MINUTES."""
        now = datetime.utcnow()
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
            logger.info("ParaView Web idle monitor started")

    async def stop_idle_monitor(self) -> None:
        """Stop the background idle monitoring task."""
        if self._idle_task is not None:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass
            self._idle_task = None
            logger.info("ParaView Web idle monitor stopped")


# =============================================================================
# Singleton
# =============================================================================


_paraview_web_manager: Optional[ParaviewWebManager] = None


def get_paraview_web_manager() -> ParaviewWebManager:
    """Get or create the singleton ParaviewWebManager instance."""
    global _paraview_web_manager
    if _paraview_web_manager is None:
        _paraview_web_manager = ParaviewWebManager()
    return _paraview_web_manager
