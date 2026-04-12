"""
Tests for Phase 30-01: Pipeline State Machine

Covers:
- StepStatus enum (PENDING, RUNNING, COMPLETED, FAILED, SKIPPED)
- PipelineStatus extension (MONITORING, VISUALIZING, REPORTING)
- StepResult and StepResultStatus
- PipelineDBService step-level updates
- Topological sort and DAG cycle detection
- PipelineExecutor state propagation
"""

import json
import sqlite3
import tempfile
import threading
from collections import deque
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_path(tmp_path):
    """Use a temp file for isolated DB per test."""
    db = tmp_path / "pipelines.db"
    # Monkey-patch the path getter before importing
    import api_server.services.pipeline_db as pdb
    orig = pdb.get_pipeline_db_path
    pdb.get_pipeline_db_path = lambda: db
    pdb._INITIALIZED = False
    pdb._pipeline_service = None
    yield db
    pdb.get_pipeline_db_path = orig


@pytest.fixture
def db_service(tmp_db_path):
    from api_server.services.pipeline_db import PipelineDBService, init_pipeline_db
    init_pipeline_db()
    return PipelineDBService()


# ---------------------------------------------------------------------------
# Task 1 — Model extensions
# ---------------------------------------------------------------------------

class TestStepStatus:
    def test_step_status_has_five_values(self):
        from api_server.models import StepStatus
        values = list(StepStatus)
        assert len(values) == 5
        names = {v.name for v in values}
        assert names == {"PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"}

    def test_step_status_enum_string_values(self):
        from api_server.models import StepStatus
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.RUNNING.value == "running"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.SKIPPED.value == "skipped"


class TestPipelineStatusExtension:
    def test_pipeline_status_has_monitoring(self):
        from api_server.models import PipelineStatus
        assert hasattr(PipelineStatus, "MONITORING")
        assert PipelineStatus.MONITORING.value == "monitoring"

    def test_pipeline_status_has_visualizing(self):
        from api_server.models import PipelineStatus
        assert hasattr(PipelineStatus, "VISUALIZING")
        assert PipelineStatus.VISUALIZING.value == "visualizing"

    def test_pipeline_status_has_reporting(self):
        from api_server.models import PipelineStatus
        assert hasattr(PipelineStatus, "REPORTING")
        assert PipelineStatus.REPORTING.value == "reporting"

    def test_pipeline_status_still_has_original_values(self):
        from api_server.models import PipelineStatus
        assert PipelineStatus.PENDING.value == "pending"
        assert PipelineStatus.RUNNING.value == "running"
        assert PipelineStatus.COMPLETED.value == "completed"
        assert PipelineStatus.FAILED.value == "failed"
        assert PipelineStatus.CANCELLED.value == "cancelled"


class TestStepResult:
    def test_step_result_valid_success(self):
        from api_server.models import StepResult, StepResultStatus
        r = StepResult(status=StepResultStatus.SUCCESS, exit_code=0)
        assert r.status == StepResultStatus.SUCCESS
        assert r.exit_code == 0
        assert r.validation_checks == {}
        assert r.diagnostics == {}

    def test_step_result_with_validation_checks(self):
        from api_server.models import StepResult, StepResultStatus
        r = StepResult(
            status=StepResultStatus.SUCCESS,
            exit_code=0,
            validation_checks={"mesh_quality": True, "y_plus": False},
        )
        assert r.validation_checks["mesh_quality"] is True
        assert r.validation_checks["y_plus"] is False

    def test_step_result_diverged_status(self):
        from api_server.models import StepResult, StepResultStatus
        r = StepResult(status=StepResultStatus.DIVERGED, exit_code=0)
        assert r.status == StepResultStatus.DIVERGED

    def test_step_result_validation_failed(self):
        from api_server.models import StepResult, StepResultStatus
        r = StepResult(
            status=StepResultStatus.VALIDATION_FAILED,
            exit_code=1,
            validation_checks={"mass_balance": False},
        )
        assert r.status == StepResultStatus.VALIDATION_FAILED

    def test_step_result_error_status(self):
        from api_server.models import StepResult, StepResultStatus
        r = StepResult(
            status=StepResultStatus.ERROR,
            exit_code=1,
            diagnostics={"exception": "MemoryError"},
        )
        assert r.status == StepResultStatus.ERROR
        assert r.diagnostics["exception"] == "MemoryError"

    def test_step_result_invalid_status_raises(self):
        from api_server.models import StepResult
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            StepResult(status="bad_value", exit_code=0)


class TestPipelineStepStatusType:
    def test_pipeline_step_status_is_step_status(self):
        from api_server.models import PipelineStep, StepStatus
        step = PipelineStep(
            step_id="s1",
            step_type="generate",
            step_order=0,
            depends_on=[],
            params={},
        )
        # status should be StepStatus, default PENDING
        assert isinstance(step.status, StepStatus)
        assert step.status == StepStatus.PENDING


# ---------------------------------------------------------------------------
# Task 1 — DB layer extensions
# ---------------------------------------------------------------------------

class TestPipelineDBServiceUpdateStepStatus:
    def test_update_step_status_writes_result_json(self, db_service):
        """update_step_status writes status + result_json to DB."""
        from api_server.models import PipelineCreate, StepStatus, StepResult, StepResultStatus

        # Create a pipeline first
        spec = PipelineCreate(
            name="Test Pipeline",
            steps=[],
        )
        pipeline = db_service.create_pipeline(spec)

        # Manually insert a step since PipelineCreate with empty steps doesn't add rows
        import api_server.services.pipeline_db as pdb
        conn = pdb.get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pipeline_steps (pipeline_id, step_id, step_type, step_order, depends_on, params, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pipeline.id, "step-1", "generate", 0, "[]", "{}", "pending"))
        conn.commit()
        conn.close()

        # Now update it
        result = StepResult(
            status=StepResultStatus.SUCCESS,
            exit_code=0,
            validation_checks={"ok": True},
        )
        db_service.update_step_status(
            pipeline.id, "step-1", StepStatus.COMPLETED,
            result_json=result.model_dump_json(),
        )

        # Verify in DB
        conn2 = pdb.get_pipeline_db_connection()
        cursor2 = conn2.cursor()
        cursor2.execute(
            "SELECT status, result_json FROM pipeline_steps WHERE pipeline_id=? AND step_id=?",
            (pipeline.id, "step-1")
        )
        row = cursor2.fetchone()
        conn2.close()

        assert row["status"] == "completed"
        assert row["result_json"] is not None
        parsed = json.loads(row["result_json"])
        assert parsed["status"] == "success"

    def test_update_step_status_without_result_json(self, db_service):
        from api_server.models import PipelineCreate, StepStatus
        spec = PipelineCreate(name="Test", steps=[])
        pipeline = db_service.create_pipeline(spec)

        import api_server.services.pipeline_db as pdb
        conn = pdb.get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pipeline_steps (pipeline_id, step_id, step_type, step_order, depends_on, params, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pipeline.id, "step-x", "run", 0, "[]", "{}", "pending"))
        conn.commit()
        conn.close()

        db_service.update_step_status(pipeline.id, "step-x", StepStatus.RUNNING)

        conn2 = pdb.get_pipeline_db_connection()
        cursor2 = conn2.cursor()
        cursor2.execute(
            "SELECT status, result_json FROM pipeline_steps WHERE pipeline_id=? AND step_id=?",
            (pipeline.id, "step-x")
        )
        row = cursor2.fetchone()
        conn2.close()
        assert row["status"] == "running"
        assert row["result_json"] is None


class TestPipelineDBServiceUpdatePipelineStatus:
    def test_update_pipeline_status_changes_status(self, db_service):
        from api_server.models import PipelineCreate, PipelineStatus
        spec = PipelineCreate(name="Status Test", steps=[])
        pipeline = db_service.create_pipeline(spec)

        assert pipeline.status == PipelineStatus.PENDING

        db_service.update_pipeline_status(pipeline.id, PipelineStatus.MONITORING)

        updated = db_service.get_pipeline(pipeline.id)
        assert updated.status == PipelineStatus.MONITORING

    def test_update_pipeline_status_to_reporting(self, db_service):
        from api_server.models import PipelineCreate, PipelineStatus
        spec = PipelineCreate(name="Status Test 2", steps=[])
        pipeline = db_service.create_pipeline(spec)

        db_service.update_pipeline_status(pipeline.id, PipelineStatus.REPORTING)

        updated = db_service.get_pipeline(pipeline.id)
        assert updated.status == PipelineStatus.REPORTING


class TestGetPipelineReturnsStepStatus:
    def test_get_pipeline_step_status_is_step_status(self, db_service):
        from api_server.models import PipelineCreate, StepStatus
        spec = PipelineCreate(name="Step Type Test", steps=[])
        pipeline = db_service.create_pipeline(spec)

        import api_server.services.pipeline_db as pdb
        conn = pdb.get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pipeline_steps (pipeline_id, step_id, step_type, step_order, depends_on, params, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pipeline.id, "step-y", "monitor", 0, "[]", "{}", "completed"))
        conn.commit()
        conn.close()

        updated = db_service.get_pipeline(pipeline.id)
        step = updated.steps[0]
        assert isinstance(step.status, StepStatus)
        assert step.status == StepStatus.COMPLETED


# ---------------------------------------------------------------------------
# Task 2 — Topological Sort
# ---------------------------------------------------------------------------

class TestTopologicalSort:
    def _make_step(self, step_id, depends_on=None, step_order=0):
        from api_server.models import PipelineStep, StepType
        return PipelineStep(
            step_id=step_id,
            step_type=StepType.GENERATE,
            step_order=step_order,
            depends_on=depends_on or [],
            params={},
        )

    def test_linear_chain(self):
        from api_server.services.pipeline_executor import topological_sort
        steps = [
            self._make_step("A"),
            self._make_step("B", depends_on=["A"]),
            self._make_step("C", depends_on=["B"]),
        ]
        ordered = topological_sort(steps)
        ids = [s.step_id for s in ordered]
        assert ids == ["A", "B", "C"]

    def test_diamond_dag(self):
        from api_server.services.pipeline_executor import topological_sort
        steps = [
            self._make_step("A"),
            self._make_step("B", depends_on=["A"]),
            self._make_step("C", depends_on=["A"]),
            self._make_step("D", depends_on=["B", "C"]),
        ]
        ordered = topological_sort(steps)
        ids = [s.step_id for s in ordered]
        assert ids[0] == "A"                     # A is first
        assert ids[-1] == "D"                   # D is last
        assert ids.index("B") < ids.index("D")  # B before D
        assert ids.index("C") < ids.index("D")  # C before D

    def test_parallel_branches(self):
        from api_server.services.pipeline_executor import topological_sort
        steps = [
            self._make_step("A"),
            self._make_step("B", depends_on=["A"]),
            self._make_step("C", depends_on=["A"]),
            self._make_step("D", depends_on=["A"]),
        ]
        ordered = topological_sort(steps)
        assert ordered[0].step_id == "A"
        assert set(s.step_id for s in ordered[1:]) == {"B", "C", "D"}

    def test_cycle_raises_value_error(self):
        from api_server.services.pipeline_executor import topological_sort
        steps = [
            self._make_step("A", depends_on=["B"]),
            self._make_step("B", depends_on=["A"]),
        ]
        with pytest.raises(ValueError, match="Cycle"):
            topological_sort(steps)

    def test_self_loop_raises_value_error(self):
        from api_server.services.pipeline_executor import topological_sort
        steps = [
            self._make_step("A", depends_on=["A"]),
        ]
        with pytest.raises(ValueError, match="Cycle"):
            topological_sort(steps)

    def test_unknown_dependency_raises(self):
        from api_server.services.pipeline_executor import topological_sort
        steps = [
            self._make_step("A"),
            self._make_step("B", depends_on=["UNKNOWN"]),
        ]
        with pytest.raises(ValueError, match="UNKNOWN"):
            topological_sort(steps)


# ---------------------------------------------------------------------------
# Task 2 — PipelineExecutor state transitions
# ---------------------------------------------------------------------------

class TestPipelineExecutorStart:
    def test_executor_start_transitions_to_running(self, tmp_db_path):
        """Test that PipelineExecutor._execute() transitions pipeline to RUNNING then COMPLETED."""
        from api_server.models import PipelineCreate, PipelineStatus
        from api_server.services.pipeline_db import PipelineDBService, init_pipeline_db
        from api_server.services.pipeline_executor import PipelineExecutor
        import asyncio

        init_pipeline_db()
        svc = PipelineDBService()

        # Create pipeline with a step
        from api_server.models import PipelineStep, StepType
        step = PipelineStep(
            step_id="s1", step_type=StepType.GENERATE, step_order=0,
            depends_on=[], params={},
        )
        spec = PipelineCreate(name="Exec Test", steps=[step])
        pipeline = svc.create_pipeline(spec)

        # Verify initial status
        p = svc.get_pipeline(pipeline.id)
        assert p.status == "pending", f"Expected pending, got {p.status}"

        # Run _execute() directly as coroutine (avoids thread timing issues)
        loop = asyncio.new_event_loop()
        executor = PipelineExecutor(pipeline.id, loop)

        # Run execution
        loop.run_until_complete(executor._execute())

        # Pipeline should now be COMPLETED (single step stub succeeds)
        p2 = svc.get_pipeline(pipeline.id)
        assert p2.status == "completed", f"Expected completed, got {p2.status}"

        # Step should be COMPLETED
        step_status = p2.steps[0].status
        assert step_status.value == "completed", f"Expected step completed, got {step_status}"

        loop.close()


class TestPipelineExecutorGetReadySteps:
    def test_get_ready_steps_returns_ready(self, tmp_db_path):
        from api_server.services.pipeline_executor import _get_ready_steps
        from api_server.models import PipelineStep, StepType, StepStatus

        # All dependencies completed
        completed = {"A", "B"}
        steps = [
            PipelineStep(step_id="C", step_type=StepType.RUN, step_order=0, depends_on=["A", "B"], params={}),
            PipelineStep(step_id="D", step_type=StepType.RUN, step_order=1, depends_on=["A"], params={}),
        ]
        ready = _get_ready_steps(steps, completed)
        assert {s.step_id for s in ready} == {"C", "D"}


class TestPipelineExecutorPropagateFailure:
    def test_propagate_failure_marks_transitive_dependents(self, tmp_db_path):
        from api_server.services.pipeline_executor import _propagate_failure
        from api_server.models import PipelineStep, StepType

        steps = [
            PipelineStep(step_id="A", step_type=StepType.GENERATE, step_order=0, depends_on=[], params={}),
            PipelineStep(step_id="B", step_type=StepType.RUN, step_order=1, depends_on=["A"], params={}),
            PipelineStep(step_id="C", step_type=StepType.MONITOR, step_order=2, depends_on=["B"], params={}),
            PipelineStep(step_id="D", step_type=StepType.VISUALIZE, step_order=3, depends_on=["B"], params={}),
        ]

        skipped = _propagate_failure("A", steps)
        assert {s.step_id for s in skipped} == {"B", "C", "D"}


# ---------------------------------------------------------------------------
# Task 2 — WebSocket stub
# ---------------------------------------------------------------------------

class TestPipelineWebSocketStub:
    def test_broadcast_pipeline_event_does_not_raise(self):
        import asyncio
        from api_server.services.pipeline_websocket import broadcast_pipeline_event, PipelineEvent

        async def _test():
            event = PipelineEvent(
                event_type="pipeline_started",
                pipeline_id="PIPE-TEST",
                sequence=1,
                payload={"total_steps": 3},
            )
            # Should not raise — stub logs only
            await broadcast_pipeline_event(event)

        asyncio.run(_test())

    def test_pipeline_event_dataclass(self):
        from api_server.services.pipeline_websocket import PipelineEvent

        event = PipelineEvent(
            event_type="step_completed",
            pipeline_id="PIPE-123",
            sequence=42,
            payload={"step_id": "s1", "status": "success"},
        )
        assert event.event_type == "step_completed"
        assert event.pipeline_id == "PIPE-123"
        assert event.sequence == 42
        assert event.payload["step_id"] == "s1"


# ---------------------------------------------------------------------------
# Import verification (success criteria)
# ---------------------------------------------------------------------------

class TestImportSuccessCriteria:
    def test_step_status_importable(self):
        from api_server.models import StepStatus
        assert hasattr(StepStatus, "PENDING")

    def test_pipeline_status_monitoring_importable(self):
        from api_server.models import PipelineStatus
        assert PipelineStatus.MONITORING.value == "monitoring"

    def test_pipeline_executor_importable(self):
        from api_server.services.pipeline_executor import PipelineExecutor, topological_sort
        assert callable(topological_sort)

    def test_pipeline_websocket_importable(self):
        from api_server.services.pipeline_websocket import PipelineEvent, broadcast_pipeline_event
        assert callable(broadcast_pipeline_event)
