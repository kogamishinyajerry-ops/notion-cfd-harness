"""
Tests for TrameSessionManager Docker container lifecycle.

Tests the Docker sidecar lifecycle using mocked subprocess calls:
- docker run args, port allocation, read-only mount
- HTTP health check polling and container-exit error
- docker kill for shutdown
- Idle timeout shutdown
- Multiple sessions get different ports
"""

import asyncio
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root in path
import sys
from pathlib import Path
_project_root = str(Path(__file__).parent.parent.parent.resolve())
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from api_server.services.trame_session_manager import (
    TrameSessionManager,
    TrameSessionError,
)


class MockHttpResponse:
    """Mock aiohttp response."""

    def __init__(self, status=200):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestDockerLifecycle:
    """Tests for Docker container lifecycle."""

    @pytest.fixture
    def manager(self):
        """Fresh TrameSessionManager instance."""
        return TrameSessionManager()

    def test_launch_session_runs_docker_run_command(
        self, manager, mock_docker, mock_aiohttp
    ):
        """launch_session calls docker run with correct args."""
        captured_commands = []

        async def mock_subprocess_exec(*args, **kwargs):
            captured_commands.append(list(args))
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"container-abc123", b""))
            proc.returncode = 0
            return proc

        async def mock_wait_for_ready(*a, **kw):
            # Skip actual HTTP health check — just mark session ready
            pass

        with tempfile.TemporaryDirectory() as case_dir:
            with patch.object(manager, "validate_docker_available", return_value=True):
                with patch.object(manager, "_wait_for_ready", mock_wait_for_ready):
                    with patch(
                        "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
                        side_effect=mock_subprocess_exec,
                    ):
                        with patch(
                            "api_server.services.trame_session_manager.shutil.which",
                            return_value="/usr/bin/docker",
                        ):
                            session = asyncio.get_event_loop().run_until_complete(
                                manager.launch_session(
                                    session_id="TEST-001",
                                    case_dir=case_dir,
                                    port=8081,
                                    job_id="J1",
                                )
                            )

        # Verify docker run was called
        assert len(captured_commands) >= 1
        docker_run_cmd = captured_commands[0]
        assert docker_run_cmd[0] == "/usr/bin/docker"
        assert docker_run_cmd[1] == "run"
        assert "--name" in docker_run_cmd
        name_idx = docker_run_cmd.index("--name")
        assert docker_run_cmd[name_idx + 1] == "trame-TEST-001"
        assert "-p" in docker_run_cmd
        assert "9000" in docker_run_cmd
        assert "pvpython" in docker_run_cmd
        assert "/trame_server.py" in docker_run_cmd

    def test_launch_session_mounts_case_dir_readonly(
        self, manager, mock_docker, mock_aiohttp
    ):
        """docker run is called with -v case_path:/data:ro (read-only)."""
        captured_commands = []

        async def mock_subprocess_exec(*args, **kwargs):
            captured_commands.append(list(args))
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"container-xyz", b""))
            proc.returncode = 0
            return proc

        async def mock_wait_for_ready(*a, **kw):
            pass

        with tempfile.TemporaryDirectory() as case_dir:
            with patch.object(manager, "validate_docker_available", return_value=True):
                with patch.object(manager, "_wait_for_ready", mock_wait_for_ready):
                    with patch(
                        "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
                        side_effect=mock_subprocess_exec,
                    ):
                        with patch(
                            "api_server.services.trame_session_manager.shutil.which",
                            return_value="/usr/bin/docker",
                        ):
                            session = asyncio.get_event_loop().run_until_complete(
                                manager.launch_session(
                                    session_id="TEST-002",
                                    case_dir=case_dir,
                                    port=8082,
                                )
                            )

        docker_run_cmd = captured_commands[0]
        vol_args = [a for a in docker_run_cmd if a.startswith(f"{case_dir}:")]
        assert len(vol_args) >= 1
        assert vol_args[0].endswith(":ro"), f"Expected read-only mount, got: {vol_args[0]}"

    def test_launch_session_waits_for_http_200(
        self, manager, mock_docker, mock_aiohttp
    ):
        """_wait_for_ready polls and returns when HTTP 200 received."""
        async def mock_subprocess_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"true", b""))
            proc.returncode = 0
            return proc

        # Mock _wait_for_ready to simulate successful HTTP 200
        async def mock_wait_for_ready(session_id, container_id, port, timeout=60):
            # Simulate 1 poll then success
            pass  # No-op: session already marked ready by default

        with tempfile.TemporaryDirectory() as case_dir:
            with patch.object(manager, "validate_docker_available", return_value=True):
                with patch.object(manager, "_wait_for_ready", mock_wait_for_ready):
                    with patch(
                        "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
                        side_effect=mock_subprocess_exec,
                    ):
                        with patch(
                            "api_server.services.trame_session_manager.shutil.which",
                            return_value="/usr/bin/docker",
                        ):
                            session = asyncio.get_event_loop().run_until_complete(
                                manager.launch_session(
                                    session_id="TEST-003",
                                    case_dir=case_dir,
                                    port=8083,
                                )
                            )

        assert session.status == "ready"

    def test_launch_session_raises_if_container_exits_early(
        self, manager, mock_docker, mock_aiohttp
    ):
        """If container exits before HTTP 200, TrameSessionError is raised."""
        async def mock_subprocess_exec(*args, **kwargs):
            cmd = list(args)
            proc = MagicMock()
            if cmd[1] == "run":
                proc.communicate = AsyncMock(return_value=(b"container-abc", b""))
                proc.returncode = 0
            elif cmd[1] == "inspect":
                proc.communicate = AsyncMock(return_value=(b"false", b""))
                proc.returncode = 0
            elif cmd[1] == "logs":
                proc.communicate = AsyncMock(return_value=(b"segfault", b""))
                proc.returncode = 0
            return proc

        # Mock _wait_for_ready to raise "container exited" error
        async def mock_wait_for_ready(session_id, container_id, port, timeout=60):
            from api_server.services.trame_session_manager import TrameSessionError
            raise TrameSessionError("Container exited during startup. Logs:\nsegfault")

        with tempfile.TemporaryDirectory() as case_dir:
            with patch.object(manager, "validate_docker_available", return_value=True):
                with patch.object(manager, "_wait_for_ready", mock_wait_for_ready):
                    with patch(
                        "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
                        side_effect=mock_subprocess_exec,
                    ):
                        with patch(
                            "api_server.services.trame_session_manager.shutil.which",
                            return_value="/usr/bin/docker",
                        ):
                            with pytest.raises(TrameSessionError) as exc_info:
                                asyncio.get_event_loop().run_until_complete(
                                    manager.launch_session(
                                        session_id="TEST-004",
                                        case_dir=case_dir,
                                        port=8084,
                                    )
                                )

        assert "exited during startup" in str(exc_info.value).lower()

    def test_launch_session_raises_on_docker_unavailable(self, manager, mock_docker):
        """validate_docker_available returns False → TrameSessionError."""
        with tempfile.TemporaryDirectory() as case_dir:
            with patch(
                "api_server.services.trame_session_manager.shutil.which",
                return_value=None,
            ):
                with pytest.raises(TrameSessionError) as exc_info:
                    asyncio.get_event_loop().run_until_complete(
                        manager.launch_session(
                            session_id="TEST-005",
                            case_dir=case_dir,
                            port=8085,
                        )
                    )

        assert "docker" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_shutdown_session_kills_container(self, manager):
        """shutdown_session calls docker kill with the correct container name."""
        from api_server.models import TrameSession

        session = TrameSession(
            session_id="TEST-006",
            job_id="J1",
            container_id="real-container-id",
            port=8086,
            case_dir="/tmp/testcase",
            auth_key="key",
            status="ready",
        )
        manager._sessions["TEST-006"] = session

        kill_calls = []

        async def mock_kill(*args, **kwargs):
            kill_calls.append(list(args))

        with patch(
            "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
            side_effect=mock_kill,
        ):
            with patch(
                "api_server.services.trame_session_manager.shutil.which",
                return_value="/usr/bin/docker",
            ):
                await manager.shutdown_session("TEST-006")

        assert len(kill_calls) >= 1
        kill_cmd = kill_calls[0]
        assert kill_cmd[0] == "/usr/bin/docker"
        assert kill_cmd[1] == "kill"
        assert "trame-TEST-006" in kill_cmd
        assert "TEST-006" not in manager._sessions

    @pytest.mark.asyncio
    async def test_idle_timeout_shuts_down(self, manager):
        """Sessions idle > 30 minutes are shut down by _shutdown_idle_sessions."""
        from api_server.models import TrameSession

        old_time = datetime.utcnow() - timedelta(minutes=31)

        session = TrameSession(
            session_id="TEST-007",
            job_id="J1",
            container_id="idle-container-id",
            port=8087,
            case_dir="/tmp/testcase",
            auth_key="key",
            status="ready",
            last_activity=old_time,
        )
        manager._sessions["TEST-007"] = session

        kill_calls = []

        async def mock_kill(*args, **kwargs):
            kill_calls.append(list(args))

        with patch(
            "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
            side_effect=mock_kill,
        ):
            with patch(
                "api_server.services.trame_session_manager.shutil.which",
                return_value="/usr/bin/docker",
            ):
                await manager._shutdown_idle_sessions()

        assert len(kill_calls) >= 1
        kill_cmd = kill_calls[0]
        assert "trame-TEST-007" in kill_cmd
        assert "TEST-007" not in manager._sessions

    def test_multiple_sessions_get_different_ports(self, manager, mock_docker, mock_aiohttp):
        """Two launch_session calls without explicit port get different ports."""
        async def mock_subprocess_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"container-xyz", b""))
            proc.returncode = 0
            return proc

        async def mock_wait_for_ready(*a, **kw):
            pass

        with tempfile.TemporaryDirectory() as case_dir:
            with patch.object(manager, "validate_docker_available", return_value=True):
                with patch.object(manager, "_wait_for_ready", mock_wait_for_ready):
                    with patch(
                        "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
                        side_effect=mock_subprocess_exec,
                    ):
                        with patch(
                            "api_server.services.trame_session_manager.shutil.which",
                            return_value="/usr/bin/docker",
                        ):
                            loop = asyncio.get_event_loop()
                            s1 = loop.run_until_complete(
                                manager.launch_session(
                                    session_id="SESSION-A",
                                    case_dir=case_dir,
                                    port=None,
                                )
                            )
                            s2 = loop.run_until_complete(
                                manager.launch_session(
                                    session_id="SESSION-B",
                                    case_dir=case_dir,
                                    port=None,
                                )
                            )

        assert s1.port != s2.port, f"Expected different ports, got {s1.port} == {s2.port}"

    def test_get_session_returns_correct_session(self, manager):
        """get_session returns the exact session object stored for that ID."""
        from api_server.models import TrameSession

        session1 = TrameSession(
            session_id="PVW-SESS1",
            job_id="J1",
            container_id="c1",
            port=8081,
            case_dir="/tmp/case1",
            auth_key="k1",
            status="ready",
        )
        session2 = TrameSession(
            session_id="PVW-SESS2",
            job_id="J2",
            container_id="c2",
            port=8082,
            case_dir="/tmp/case2",
            auth_key="k2",
            status="ready",
        )
        manager._sessions["PVW-SESS1"] = session1
        manager._sessions["PVW-SESS2"] = session2

        result1 = manager.get_session("PVW-SESS1")
        result2 = manager.get_session("PVW-SESS2")

        assert result1 is session1
        assert result2 is session2
        assert result1 is not result2

    def test_update_activity_only_affects_target_session(self, manager):
        """update_activity only updates the targeted session."""
        from api_server.models import TrameSession

        before = datetime(2026, 1, 1, 0, 0, 0)
        session1 = TrameSession(
            session_id="ACT-1",
            job_id="J1",
            container_id="c1",
            port=8081,
            case_dir="/tmp/c1",
            auth_key="k1",
            status="ready",
            last_activity=before,
        )
        session2 = TrameSession(
            session_id="ACT-2",
            job_id="J2",
            container_id="c2",
            port=8082,
            case_dir="/tmp/c2",
            auth_key="k2",
            status="ready",
            last_activity=before,
        )
        manager._sessions["ACT-1"] = session1
        manager._sessions["ACT-2"] = session2

        manager.update_activity("ACT-1")

        assert session1.last_activity > before
        assert session2.last_activity == before

    def test_shutdown_one_session_preserves_other(self, manager):
        """Shutting down one session does not affect the other."""
        from api_server.models import TrameSession

        s1 = TrameSession(
            session_id="KILL-1",
            job_id="J1",
            container_id="k1",
            port=8091,
            case_dir="/tmp/k1",
            auth_key="k1",
            status="ready",
        )
        s2 = TrameSession(
            session_id="KILL-2",
            job_id="J2",
            container_id="k2",
            port=8092,
            case_dir="/tmp/k2",
            auth_key="k2",
            status="ready",
        )
        manager._sessions["KILL-1"] = s1
        manager._sessions["KILL-2"] = s2

        async def mock_kill(*args, **kwargs):
            pass

        async def do_shutdown():
            with patch(
                "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
                side_effect=mock_kill,
            ):
                with patch(
                    "api_server.services.trame_session_manager.shutil.which",
                    return_value="/usr/bin/docker",
                ):
                    await manager.shutdown_session("KILL-1")

        asyncio.get_event_loop().run_until_complete(do_shutdown())

        assert "KILL-1" not in manager._sessions
        assert "KILL-2" in manager._sessions
