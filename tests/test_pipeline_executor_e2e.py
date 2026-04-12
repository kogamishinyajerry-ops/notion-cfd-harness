"""
End-to-end integration tests for PipelineExecutor.

Tests verify:
1. PipelineExecutor runs in a threading.Thread (not BackgroundTasks)
2. Linear DAG (A→B→C): all steps COMPLETED, pipeline COMPLETED
3. Failure propagation: A→B→C, B fails → A COMPLETED, B FAILED, C SKIPPED, pipeline FAILED
4. Cancellation: A→B→C, cancel before A completes → pipeline CANCELLED
5. DIVERGED monitor result does NOT halt pipeline (PIPE-03)

Each test creates an isolated temporary DB and monkeypatches execute_step
to avoid needing real OpenFOAM/Docker. Tests complete in <5 seconds.
"""
import asyncio
import threading
from unittest.mock import AsyncMock, patch

import pytest

from api_server.models import (
    PipelineCreate,
    PipelineResponse,
    PipelineStatus,
    StepResult,
    StepResultStatus,
    StepStatus,
    StepType,
)
from api_server.services import pipeline_db as db_mod
from api_server.services.pipeline_executor import (
    _ACTIVE_EXECUTORS,
    cancel_pipeline_executor,
    start_pipeline_executor,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def make_service(tmp_path, monkeypatch):
    """Create a PipelineDBService with isolated temporary DB."""
    test_db_path = tmp_path / "pipelines.db"
    monkeypatch.setattr(db_mod, "_DB_PATH", test_db_path)
    monkeypatch.setattr(db_mod, "_INITIALIZED", False)
    monkeypatch.setattr(db_mod, "_pipeline_service", None)
    db_mod.init_pipeline_db()
    return db_mod.get_pipeline_db_service()


def make_linear_pipeline(service: db_mod.PipelineDBService, name="Test Linear"):
    """Create a 3-step linear pipeline (A→B→C)."""
    steps = [
        StepType.to_model(step_id="step-A", step_type=StepType.GENERATE, step_order=0, depends_on=[]),
        StepType.to_model(step_id="step-B", step_type=StepType.RUN, step_order=1, depends_on=["step-A"]),
        StepType.to_model(step_id="step-C", step_type=StepType.REPORT, step_order=2, depends_on=["step-B"]),
    ]


# --------------------------------------------------------------------------
# Test 1: Linear pipeline completes successfully
# --------------------------------------------------------------------------

def test_linear_pipeline_completes_all_steps_success(tmp_path, monkeypatch):
    """
    Scenario: A→B→C linear pipeline, all steps succeed.
    Expected: step-A COMPLETED, step-B COMPLETED, step-C COMPLETED, pipeline COMPLETED.
    """
    # Import StepType here to avoid import errors
    from api_server.models import PipelineStep

    service = make_service(tmp_path, monkeypatch)
    loop = asyncio.get_event_loop()

    # Create pipeline directly in temp DB
    steps = [
        PipelineStep(step_id="step-A", step_type=StepType.GENERATE, step_order=0, depends_on=[]),
        PipelineStep(step_id="step-B", step_type=StepType.RUN, step_order=1, depends_on=["step-A"]),
        PipelineStep(step_id="step-C", step_type=StepType.REPORT, step_order=2, depends_on=["step-B"]),
    ]
    pipeline_resp: PipelineResponse = service.create_pipeline(
        PipelineCreate(name="Linear Test", steps=steps)
    )

    # Mock execute_step to always return SUCCESS
    async def fake_execute_step(step, cancel_event):
        return StepResult(status=StepResultStatus.SUCCESS, exit_code=0)

    with patch("api_server.services.step_wrappers.execute_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = fake_execute_step
        with patch("api_server.services.step_wrappers.asyncio.sleep", new_callable=AsyncMock):
            start_pipeline_executor(pipeline_resp.id, loop)
            executor = _ACTIVE_EXECUTORS.get(pipeline_resp.id)
            assert executor is not None
            executor._thread.join(timeout=10)
            assert not executor._thread.is_alive()

    # Verify
    updated = service.get_pipeline(pipeline_resp.id)
    assert updated.status == PipelineStatus.COMPLETED, f"Expected COMPLETED, got {updated.status}"
    step_statuses = {s.step_id: s.status for s in updated.steps}
    assert step_statuses["step-A"] == StepStatus.COMPLETED
    assert step_statuses["step-B"] == StepStatus.COMPLETED
    assert step_statuses["step-C"] == StepStatus.COMPLETED
    assert all(s.status == StepStatus.COMPLETED for s in updated.steps)


# --------------------------------------------------------------------------
# Test 2: Failure propagation
# --------------------------------------------------------------------------

def test_failure_propagates_to_dependents_and_marks_pipeline_failed(tmp_path, monkeypatch):
    """
    Scenario: A→B→C, step-B fails.
    Expected: step-A COMPLETED, step-B FAILED, step-C SKIPPED, pipeline FAILED.
    """
    from api_server.models import PipelineStep

    service = make_service(tmp_path, monkeypatch)
    loop = asyncio.get_event_loop()

    steps = [
        PipelineStep(step_id="step-A", step_type=StepType.GENERATE, step_order=0, depends_on=[]),
        PipelineStep(step_id="step-B", step_type=StepType.RUN, step_order=1, depends_on=["step-A"]),
        PipelineStep(step_id="step-C", step_type=StepType.REPORT, step_order=2, depends_on=["step-B"]),
    ]
    pipeline_resp = service.create_pipeline(
        PipelineCreate(name="Failure Test", steps=steps)
    )

    async def fake_execute_step(step, cancel_event):
        if step.step_id == "step-B":
            return StepResult(status=StepResultStatus.ERROR, exit_code=1,
                              diagnostics={"error": "Simulated solver failure"})
        return StepResult(status=StepResultStatus.SUCCESS, exit_code=0)

    with patch("api_server.services.step_wrappers.execute_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = fake_execute_step
        with patch("api_server.services.step_wrappers.asyncio.sleep", new_callable=AsyncMock):
            start_pipeline_executor(pipeline_resp.id, loop)
            executor = _ACTIVE_EXECUTORS.get(pipeline_resp.id)
            assert executor is not None
            executor._thread.join(timeout=10)

    updated = service.get_pipeline(pipeline_resp.id)
    assert updated.status == PipelineStatus.FAILED
    step_map = {s.step_id: s.status for s in updated.steps}
    assert step_map["step-A"] == StepStatus.COMPLETED
    assert step_map["step-B"] == StepStatus.FAILED
    assert step_map["step-C"] == StepStatus.SKIPPED


# --------------------------------------------------------------------------
# Test 3: Cancellation
# --------------------------------------------------------------------------

def test_cancel_immediately_marks_pipeline_cancelled(tmp_path, monkeypatch):
    """
    Scenario: Start pipeline, call cancel_pipeline_executor() immediately.
    Expected: pipeline CANCELLED.
    """
    from api_server.models import PipelineStep

    service = make_service(tmp_path, monkeypatch)
    loop = asyncio.get_event_loop()

    steps = [
        PipelineStep(step_id="step-A", step_type=StepType.GENERATE, step_order=0, depends_on=[]),
        PipelineStep(step_id="step-B", step_type=StepType.RUN, step_order=1, depends_on=["step-A"]),
        PipelineStep(step_id="step-C", step_type=StepType.REPORT, step_order=2, depends_on=["step-B"]),
    ]
    pipeline_resp = service.create_pipeline(
        PipelineCreate(name="Cancel Test", steps=steps)
    )

    async def fake_slow_step(step, cancel_event):
        """Step that would run forever without cancel."""
        for _ in range(100):
            if cancel_event.is_set():
                return StepResult(status=StepResultStatus.ERROR, exit_code=1,
                                  diagnostics={"cancelled": True})
            await asyncio.sleep(0.05)
        return StepResult(status=StepResultStatus.SUCCESS, exit_code=0)

    with patch("api_server.services.step_wrappers.execute_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = fake_slow_step
        with patch("api_server.services.step_wrappers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Make asyncio.sleep very fast so the loop advances quickly
            async def fast_sleep(*args, **kwargs):
                pass
            mock_sleep.side_effect = fast_sleep

            start_pipeline_executor(pipeline_resp.id, loop)
            cancelled = cancel_pipeline_executor(pipeline_resp.id)
            assert cancelled is True

            executor = _ACTIVE_EXECUTORS.get(pipeline_resp.id)
            assert executor is not None
            executor._thread.join(timeout=5)

    updated = service.get_pipeline(pipeline_resp.id)
    assert updated.status == PipelineStatus.CANCELLED, \
        f"Expected CANCELLED, got {updated.status}"


# --------------------------------------------------------------------------
# Test 4: PipelineExecutor runs in threading.Thread
# --------------------------------------------------------------------------

def test_executor_runs_in_background_thread(tmp_path, monkeypatch):
    """
    Verify PipelineExecutor uses threading.Thread, not FastAPI BackgroundTasks.
    """
    from api_server.models import PipelineStep

    service = make_service(tmp_path, monkeypatch)
    loop = asyncio.get_event_loop()

    steps = [
        PipelineStep(step_id="step-A", step_type=StepType.GENERATE, step_order=0, depends_on=[]),
    ]
    pipeline_resp = service.create_pipeline(
        PipelineCreate(name="Threading Test", steps=steps)
    )

    async def fake_execute_step(step, cancel_event):
        return StepResult(status=StepResultStatus.SUCCESS, exit_code=0)

    with patch("api_server.services.step_wrappers.execute_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = fake_execute_step
        with patch("api_server.services.step_wrappers.asyncio.sleep", new_callable=AsyncMock):
            start_pipeline_executor(pipeline_resp.id, loop)
            executor = _ACTIVE_EXECUTORS.get(pipeline_resp.id)

            assert executor is not None
            assert isinstance(executor._thread, threading.Thread)
            assert executor._thread.daemon is True
            assert executor._thread.name.startswith("pipeline-")

            executor._thread.join(timeout=5)


# --------------------------------------------------------------------------
# Test 5: DIVERGED monitor result does NOT halt pipeline (PIPE-03)
# --------------------------------------------------------------------------

def test_diverged_monitor_result_does_not_halt_pipeline(tmp_path, monkeypatch):
    """
    Scenario: A→B→C where B is MONITOR step that returns DIVERGED.
    Expected: pipeline COMPLETED, B.status = COMPLETED (DIVERGED is non-fatal).

    Per PIPE-03: DIVERGED does NOT halt the pipeline.
    PipelineExecutor treats DIVERGED as success (does not add to failed set).
    """
    from api_server.models import PipelineStep

    service = make_service(tmp_path, monkeypatch)
    loop = asyncio.get_event_loop()

    steps = [
        PipelineStep(step_id="gen", step_type=StepType.GENERATE, step_order=0, depends_on=[]),
        PipelineStep(step_id="mon", step_type=StepType.MONITOR, step_order=1, depends_on=["gen"]),
        PipelineStep(step_id="rep", step_type=StepType.REPORT, step_order=2, depends_on=["mon"]),
    ]
    pipeline_resp = service.create_pipeline(
        PipelineCreate(name="DIVERGED Test", steps=steps)
    )

    async def fake_execute_step(step, cancel_event):
        if step.step_id == "mon":
            # DIVERGED — should NOT halt pipeline per PIPE-03
            return StepResult(status=StepResultStatus.DIVERGED, exit_code=0)
        return StepResult(status=StepResultStatus.SUCCESS, exit_code=0)

    with patch("api_server.services.step_wrappers.execute_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = fake_execute_step
        with patch("api_server.services.step_wrappers.asyncio.sleep", new_callable=AsyncMock):
            start_pipeline_executor(pipeline_resp.id, loop)
            executor = _ACTIVE_EXECUTORS.get(pipeline_resp.id)
            assert executor is not None
            executor._thread.join(timeout=10)

    updated = service.get_pipeline(pipeline_resp.id)
    step_map = {s.step_id: s.status for s in updated.steps}

    assert updated.status == PipelineStatus.COMPLETED, \
        f"DIVERGED should NOT halt pipeline. Got {updated.status}"
    assert step_map["gen"] == StepStatus.COMPLETED
    assert step_map["mon"] == StepStatus.COMPLETED, \
        "DIVERGED monitor should be marked COMPLETED (non-fatal)"
    assert step_map["rep"] == StepStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
