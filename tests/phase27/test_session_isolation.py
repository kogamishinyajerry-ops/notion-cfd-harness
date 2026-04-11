"""
Tests for TrameSessionManager session isolation.

Verifies that two concurrent trame sessions are fully isolated:
- Separate container IDs
- Separate ports
- Separate auth_keys
- Correct session retrieval by ID
- Targeted activity update (only one session affected)
- Shutdown isolation (shutting down one does not affect the other)
"""

import asyncio
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path
_project_root = str(Path(__file__).parent.parent.parent.resolve())
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from api_server.models import TrameSession
from api_server.services.trame_session_manager import TrameSessionManager


class TestSessionIsolation:
    """Tests that concurrent sessions are fully isolated from each other."""

    @pytest.fixture
    def manager(self):
        """Fresh TrameSessionManager instance."""
        return TrameSessionManager()

    @pytest.mark.asyncio
    async def test_two_sessions_have_separate_containers(self, manager):
        """Two sessions launched get distinct container IDs."""
        captured_containers = []

        async def mock_wait_for_ready(*a, **kw):
            pass

        async def capture_docker_run(*args, **kwargs):
            cmd = list(args)
            proc = MagicMock()
            if cmd[1] == "run":
                name_idx = cmd.index("--name")
                container_id = f"container-{cmd[name_idx + 1]}"
                captured_containers.append(container_id)
                proc.communicate = AsyncMock(return_value=(container_id.encode(), b""))
                proc.returncode = 0
            return proc

        with tempfile.TemporaryDirectory() as case_dir:
            with patch.object(manager, "validate_docker_available", return_value=True):
                with patch.object(manager, "_wait_for_ready", mock_wait_for_ready):
                    with patch(
                        "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
                        side_effect=capture_docker_run,
                    ):
                        with patch(
                            "api_server.services.trame_session_manager.shutil.which",
                            return_value="/usr/bin/docker",
                        ):
                            s1 = await manager.launch_session(
                                session_id="ISO-001",
                                case_dir=case_dir,
                                port=None,
                            )
                            s2 = await manager.launch_session(
                                session_id="ISO-002",
                                case_dir=case_dir,
                                port=None,
                            )

        assert len(captured_containers) == 2
        assert captured_containers[0] != captured_containers[1]
        assert s1.container_id != s2.container_id

    @pytest.mark.asyncio
    async def test_two_sessions_have_separate_ports(self, manager):
        """Two sessions launched without explicit port get different assigned ports."""
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
                            s1 = await manager.launch_session(
                                session_id="PORT-001",
                                case_dir=case_dir,
                                port=None,
                            )
                            s2 = await manager.launch_session(
                                session_id="PORT-002",
                                case_dir=case_dir,
                                port=None,
                            )

        assert s1.port != s2.port
        assert 8081 <= s1.port <= 8090
        assert 8081 <= s2.port <= 8090

    @pytest.mark.asyncio
    async def test_two_sessions_have_separate_auth_keys(self, manager):
        """Two sessions get distinct auth_key values."""
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
                            s1 = await manager.launch_session(
                                session_id="AUTH-001",
                                case_dir=case_dir,
                                port=None,
                            )
                            s2 = await manager.launch_session(
                                session_id="AUTH-002",
                                case_dir=case_dir,
                                port=None,
                            )

        assert s1.auth_key != s2.auth_key
        assert len(s1.auth_key) == 22  # secrets.token_urlsafe(16) → 22-char base64
        assert len(s2.auth_key) == 22

    def test_get_session_returns_correct_session(self, manager):
        """get_session returns the exact session object stored for that ID."""
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
        """update_activity only updates the targeted session's last_activity."""
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

    @pytest.mark.asyncio
    async def test_shutdown_one_session_preserves_other(self, manager):
        """Shutting down one session does not remove or affect the other."""
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

        with patch(
            "api_server.services.trame_session_manager.asyncio.create_subprocess_exec",
            side_effect=mock_kill,
        ):
            with patch(
                "api_server.services.trame_session_manager.shutil.which",
                return_value="/usr/bin/docker",
            ):
                await manager.shutdown_session("KILL-1")

        assert "KILL-1" not in manager._sessions
        assert "KILL-2" in manager._sessions
