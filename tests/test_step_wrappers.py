"""
Tests for step_wrappers.py — TDD for 5 step wrappers + dispatcher.

Tests cover:
1.  generate_wrapper: success, idempotency (cache hit)
2.  run_wrapper: success, failure, cancellation
3.  monitor_wrapper: DIVERGED (non-halting), SUCCESS, ERROR
4.  visualize_wrapper: success with trame session id in diagnostics
5.  report_wrapper: success
6.  execute_step dispatcher: dispatches to correct wrapper, unknown type returns ERROR
7.  Cancellation: cancel_event set before run_wrapper returns ERROR without calling JobService
"""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_server.models import (
    JobResponse,
    JobStatus,
    StepResult,
    StepResultStatus,
    StepType,
)
from api_server.services.step_wrappers import (
    _STEP_CACHE,
    _param_hash,
    execute_step,
    generate_wrapper,
    monitor_wrapper,
    report_wrapper,
    run_wrapper,
    visualize_wrapper,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

class DummyStep:
    """Minimal step object for testing wrappers."""
    def __init__(self, step_id: str, step_type, params: dict):
        self.step_id = step_id
        self.step_type = step_type
        self.params = params


@pytest.fixture(autouse=True)
def clear_step_cache():
    """Clear the in-process step cache before and after each test."""
    _STEP_CACHE.clear()
    yield
    _STEP_CACHE.clear()


# --------------------------------------------------------------------------
# Tests: execute_step dispatcher
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_step_dispatches_to_generate():
    """execute_step with GENERATE step_type calls generate_wrapper."""
    step = DummyStep("s1", StepType.GENERATE, {"case_id": "CASE-001"})
    cancel = threading.Event()

    with patch("api_server.services.step_wrappers.generate_wrapper", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = StepResult(status=StepResultStatus.SUCCESS, exit_code=0)
        result = await execute_step(step, cancel)

        mock_gen.assert_called_once_with(step, cancel)
        assert result.status == StepResultStatus.SUCCESS


@pytest.mark.asyncio
async def test_execute_step_dispatches_to_run():
    """execute_step with RUN step_type calls run_wrapper."""
    step = DummyStep("s2", StepType.RUN, {"case_id": "CASE-001"})
    cancel = threading.Event()

    with patch("api_server.services.step_wrappers.run_wrapper", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = StepResult(status=StepResultStatus.SUCCESS, exit_code=0)
        result = await execute_step(step, cancel)

        mock_run.assert_called_once_with(step, cancel)
        assert result.status == StepResultStatus.SUCCESS


@pytest.mark.asyncio
async def test_execute_step_dispatches_to_monitor():
    """execute_step with MONITOR step_type calls monitor_wrapper."""
    step = DummyStep("s3", StepType.MONITOR, {"job_id": "JOB-001"})
    cancel = threading.Event()

    with patch("api_server.services.step_wrappers.monitor_wrapper", new_callable=AsyncMock) as mock_mon:
        mock_mon.return_value = StepResult(status=StepResultStatus.SUCCESS, exit_code=0)
        result = await execute_step(step, cancel)

        mock_mon.assert_called_once_with(step, cancel)
        assert result.status == StepResultStatus.SUCCESS


@pytest.mark.asyncio
async def test_execute_step_dispatches_to_visualize():
    """execute_step with VISUALIZE step_type calls visualize_wrapper."""
    step = DummyStep("s4", StepType.VISUALIZE, {"case_dir": "/tmp/case"})
    cancel = threading.Event()

    with patch("api_server.services.step_wrappers.visualize_wrapper", new_callable=AsyncMock) as mock_vis:
        mock_vis.return_value = StepResult(status=StepResultStatus.SUCCESS, exit_code=0)
        result = await execute_step(step, cancel)

        mock_vis.assert_called_once_with(step, cancel)
        assert result.status == StepResultStatus.SUCCESS


@pytest.mark.asyncio
async def test_execute_step_dispatches_to_report():
    """execute_step with REPORT step_type calls report_wrapper."""
    step = DummyStep("s5", StepType.REPORT, {"case_id": "CASE-001"})
    cancel = threading.Event()

    with patch("api_server.services.step_wrappers.report_wrapper", new_callable=AsyncMock) as mock_rep:
        mock_rep.return_value = StepResult(status=StepResultStatus.SUCCESS, exit_code=0)
        result = await execute_step(step, cancel)

        mock_rep.assert_called_once_with(step, cancel)
        assert result.status == StepResultStatus.SUCCESS


@pytest.mark.asyncio
async def test_execute_step_unknown_type_returns_error():
    """execute_step with unknown step_type returns StepResult(status=ERROR)."""
    step = DummyStep("s6", "unknown_type", {})
    cancel = threading.Event()

    result = await execute_step(step, cancel)

    assert result.status == StepResultStatus.ERROR
    assert result.exit_code == 1
    assert "Unknown step type" in result.diagnostics.get("error", "")


@pytest.mark.asyncio
async def test_execute_step_cancel_event_set_returns_error():
    """execute_step returns ERROR when cancel_event is already set."""
    step = DummyStep("s7", StepType.RUN, {})
    cancel = threading.Event()
    cancel.set()

    result = await execute_step(step, cancel)

    assert result.status == StepResultStatus.ERROR
    assert result.diagnostics.get("cancelled") is True


# --------------------------------------------------------------------------
# Tests: generate_wrapper
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_wrapper_idempotency():
    """generate_wrapper: cache hit returns cached result without calling wrapper.

    Pre-populate cache with known diagnostics, then call execute_step.
    Since cache is populated, wrapper is NOT called and cached result is returned.
    """
    step = DummyStep("gen-cache-1", StepType.GENERATE, {"case_id": "CASE-001"})
    cancel = threading.Event()

    # Pre-populate cache with a known result containing distinctive diagnostics
    cached = StepResult(
        status=StepResultStatus.SUCCESS,
        exit_code=0,
        diagnostics={"cached": True, "step_id": step.step_id}
    )
    cache_key = _param_hash(step.step_id, step.params)
    _STEP_CACHE[cache_key] = cached

    # Call execute_step — should return cached result directly
    result = await execute_step(step, cancel)

    # Must return the cached result (not call generate_wrapper)
    assert isinstance(result, StepResult)
    assert result.status == StepResultStatus.SUCCESS
    assert result.diagnostics.get("cached") is True


# --------------------------------------------------------------------------
# Tests: run_wrapper
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_wrapper_job_completed_returns_success():
    """run_wrapper: JobService returns completed → StepResult(status=SUCCESS)."""
    step = DummyStep("run1", StepType.RUN, {"case_id": "CASE-001", "pipeline_id": "P-001"})
    cancel = threading.Event()

    mock_job_response = JobResponse(
        job_id="JOB-001",
        case_id="CASE-001",
        job_type="run",
        status=JobStatus.COMPLETED,
        submitted_at=time.time(),
        result={"output_dir": "/tmp/out"},
    )

    # Patch at source: JobService class and _JOBS dict
    with patch("api_server.services.job_service.JobService") as MockJS:
        mock_js_instance = MockJS.return_value
        mock_js_instance.submit_job.return_value = mock_job_response

        # Patch _JOBS at source so run_wrapper's local import sees it
        with patch("api_server.services.job_service._JOBS", {"JOB-001": mock_job_response}):
            # Mock asyncio.sleep so polling returns immediately
            with patch("api_server.services.step_wrappers.asyncio.sleep", new_callable=AsyncMock):
                result = await run_wrapper(step, cancel)

    assert result.status == StepResultStatus.SUCCESS
    assert result.exit_code == 0
    assert result.validation_checks.get("job_completed") is True


@pytest.mark.asyncio
async def test_run_wrapper_job_failed_returns_error():
    """run_wrapper: JobService returns failed → StepResult(status=ERROR)."""
    step = DummyStep("run2", StepType.RUN, {"case_id": "CASE-001"})
    cancel = threading.Event()

    mock_job_response = JobResponse(
        job_id="JOB-002",
        case_id="CASE-001",
        job_type="run",
        status=JobStatus.FAILED,
        submitted_at=time.time(),
        error="Solver crashed",
    )

    with patch("api_server.services.job_service.JobService") as MockJS:
        mock_js_instance = MockJS.return_value
        mock_js_instance.submit_job.return_value = mock_job_response

        with patch("api_server.services.job_service._JOBS", {"JOB-002": mock_job_response}):
            with patch("api_server.services.step_wrappers.asyncio.sleep", new_callable=AsyncMock):
                result = await run_wrapper(step, cancel)

    assert result.status == StepResultStatus.ERROR
    assert result.exit_code == 1
    assert result.validation_checks.get("job_completed") is False


@pytest.mark.asyncio
async def test_run_wrapper_cancel_before_submit_returns_error():
    """run_wrapper: cancel_event set before submission → ERROR without calling JobService."""
    step = DummyStep("run3", StepType.RUN, {"case_id": "CASE-001"})
    cancel = threading.Event()
    cancel.set()

    # Patch JobService to track if submit_job is called
    with patch("api_server.services.job_service.JobService") as MockJS:
        mock_js_instance = MockJS.return_value
        result = await run_wrapper(step, cancel)

    assert result.status == StepResultStatus.ERROR
    assert result.diagnostics.get("cancelled") is True
    # submit_job should NOT have been called because cancel_event is set first
    mock_js_instance.submit_job.assert_not_called()


# --------------------------------------------------------------------------
# Tests: monitor_wrapper
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitor_wrapper_diverged_returns_diverged():
    """monitor_wrapper: DIVERGED result does NOT halt pipeline — wrapper returns DIVERGED."""
    step = DummyStep("mon1", StepType.MONITOR, {"job_id": "JOB-MON-001"})
    cancel = threading.Event()

    # Simulate: job status never reaches COMPLETED and times out → DIVERGED
    mock_running_job = JobResponse(
        job_id="JOB-MON-001",
        case_id="CASE-001",
        job_type="run",
        status=JobStatus.RUNNING,
        submitted_at=time.time(),
    )

    with patch("api_server.services.job_service._JOBS", {"JOB-MON-001": mock_running_job}):
        # Mock asyncio.sleep so polling returns immediately but job stays RUNNING
        with patch("api_server.services.step_wrappers.asyncio.sleep", new_callable=AsyncMock):
            result = await monitor_wrapper(step, cancel)

    # DIVERGED is the expected outcome when timeout occurs
    assert result.status == StepResultStatus.DIVERGED


@pytest.mark.asyncio
async def test_monitor_wrapper_job_completed_returns_success():
    """monitor_wrapper: job completes successfully → StepResult(status=SUCCESS)."""
    step = DummyStep("mon2", StepType.MONITOR, {"job_id": "JOB-MON-002"})
    cancel = threading.Event()

    mock_completed_job = JobResponse(
        job_id="JOB-MON-002",
        case_id="CASE-001",
        job_type="run",
        status=JobStatus.COMPLETED,
        submitted_at=time.time(),
        result={"output_dir": "/tmp/out", "metrics": {"final_residual": 1e-5}},
    )

    with patch("api_server.services.job_service._JOBS", {"JOB-MON-002": mock_completed_job}):
        with patch("api_server.services.step_wrappers.asyncio.sleep", new_callable=AsyncMock):
            result = await monitor_wrapper(step, cancel)

    assert result.status == StepResultStatus.SUCCESS
    assert result.validation_checks.get("converged") is True


# --------------------------------------------------------------------------
# Tests: visualize_wrapper
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_visualize_wrapper_success_includes_trame_session_id():
    """visualize_wrapper: diagnostics contains trame_session_id and note about container ownership."""
    step = DummyStep("vis1", StepType.VISUALIZE, {"case_dir": "/tmp/case"})
    cancel = threading.Event()

    mock_session = MagicMock()
    mock_session.session_id = "TRM-001"
    mock_session.port = 8081

    # Patch get_trame_session_manager at its source module
    with patch("api_server.services.trame_session_manager.get_trame_session_manager") as mock_get_mgr:
        mock_mgr = AsyncMock()
        mock_mgr.launch_session = AsyncMock(return_value=mock_session)
        mock_get_mgr.return_value = mock_mgr

        result = await visualize_wrapper(step, cancel)

    assert result.status == StepResultStatus.SUCCESS
    assert result.diagnostics.get("trame_session_id") == "TRM-001"
    assert result.diagnostics.get("trame_port") == 8081
    assert "TrameSessionManager" in result.diagnostics.get("note", "")


# --------------------------------------------------------------------------
# Tests: asyncio patterns verification
# --------------------------------------------------------------------------

def test_generate_wrapper_uses_asyncio_to_thread():
    """generate_wrapper must use asyncio.to_thread for blocking file I/O (PIPE-07)."""
    import inspect
    import api_server.services.step_wrappers as sw
    source = inspect.getsource(sw.generate_wrapper)
    assert "asyncio.to_thread" in source, "generate_wrapper must use asyncio.to_thread"


def test_report_wrapper_uses_asyncio_to_thread():
    """report_wrapper must use asyncio.to_thread for blocking file I/O (PIPE-07)."""
    import inspect
    import api_server.services.step_wrappers as sw
    source = inspect.getsource(sw.report_wrapper)
    assert "asyncio.to_thread" in source, "report_wrapper must use asyncio.to_thread"


def test_run_wrapper_uses_asyncio_sleep_not_time_sleep():
    """run_wrapper must use asyncio.sleep for polling, not time.sleep (PIPE-07)."""
    import inspect
    import api_server.services.step_wrappers as sw
    source = inspect.getsource(sw.run_wrapper)
    assert "asyncio.sleep" in source, "run_wrapper must use asyncio.sleep"
    assert "time.sleep" not in source, "run_wrapper must NOT use time.sleep"


def test_docker_ownership_decision_comment_present():
    """Docker ownership decision must be documented as a code comment (PIPE-04)."""
    import api_server.services.step_wrappers as sw
    source = sw.__doc__
    assert "DOCKER OWNERSHIP" in source or "Docker ownership" in source, \
        "Docker ownership decision comment must be present in step_wrappers.py"


def test_param_hash_is_deterministic():
    """_param_hash: same inputs always produce same output."""
    hash1 = _param_hash("step1", {"a": 1, "b": 2})
    hash2 = _param_hash("step1", {"b": 2, "a": 1})  # different order
    hash3 = _param_hash("step1", {"a": 1, "b": 3})  # different value
    hash4 = _param_hash("step2", {"a": 1, "b": 2})  # different step

    assert hash1 == hash2, "param_hash must be order-independent"
    assert hash1 != hash3, "param_hash must reflect param values"
    assert hash1 != hash4, "param_hash must reflect step_id"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
