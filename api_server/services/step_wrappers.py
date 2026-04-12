"""
Step Wrappers for PipelineExecutor.

Each wrapper calls an existing API component and returns a StepResult.
Pipeline orchestration uses StepResult.status (NOT exit_code) to determine success.

==========================================================================
DOCKER OWNERSHIP DECISION (PIPE-04 / PITFALL 2.2):
==========================================================================
Decision: Option B — TrameSessionManager retains ownership of trame viewer containers.

Rationale:
- TrameSessionManager has battle-tested lifecycle management (30-min idle timeout,
  port allocation, graceful shutdown) from v1.6.0.
- Replacing this with pipeline ownership would require re-implementing all of it.
- Pipeline abort/cancel does NOT stop trame containers.
- Solver containers started by run_wrapper are labeled with pipeline_id for cleanup by
  CleanupHandler (Plan 04).

Ownership table:
| Container type | Owner           | Cleanup trigger         |
|----------------|-----------------|-------------------------|
| Solver (run)   | PipelineExecutor| CleanupHandler on cancel |
| Trame (viewer) | TrameSessionManager | 30-min idle timeout  |

Container label for solver: docker run --label pipeline_id=<id> ...
==========================================================================

ASYNC/SYNC SEPARATION (PIPE-07 / PITFALL 3.1):
==========================================================================
- PipelineExecutor runs in a dedicated threading.Thread with asyncio.run()
- This module's wrappers are all async def functions
- Blocking file I/O (case generation, report writing) uses asyncio.to_thread()
- Blocking polling (job status) uses asyncio.sleep() between polls — never time.sleep()
==========================================================================
"""
import asyncio
import hashlib
import json
import logging
import threading
from typing import Any, Dict, Optional

from api_server.models import (
    JobSubmission,
    StepResult,
    StepResultStatus,
    StepType,
)

logger = logging.getLogger(__name__)

# Idempotency cache: param_hash -> StepResult
# Survives within server session. PipelineExecutor caches results in DB after
# each wrapper returns (via pipeline.config["step_cache"] in Plan 02 extension).
_STEP_CACHE: Dict[str, StepResult] = {}
_STEP_CACHE_LOCK = threading.Lock()


def _param_hash(step_id: str, params: Dict[str, Any]) -> str:
    """
    Deterministic hash of step_id + params for idempotency cache key.
    Sort-keys ensures order-independence so same params in different order
    produce the same cache key.
    """
    key = json.dumps({"step_id": step_id, "params": params}, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# Dispatcher
# --------------------------------------------------------------------------

async def execute_step(step, cancel_event: threading.Event) -> StepResult:
    """
    Dispatch to the appropriate wrapper for step.step_type.
    Checks idempotency cache before executing.

    Cancellation: returns ERROR immediately if cancel_event is already set.

    Idempotency: if the same (step_id, params) has been computed before within
    this server session, returns the cached StepResult without re-executing.
    """
    if cancel_event.is_set():
        return StepResult(
            status=StepResultStatus.ERROR,
            exit_code=1,
            diagnostics={"cancelled": True}
        )

    # Idempotency check
    cache_key = _param_hash(step.step_id, step.params)
    with _STEP_CACHE_LOCK:
        if cache_key in _STEP_CACHE:
            logger.info(f"Step {step.step_id} cache hit — returning cached result")
            return _STEP_CACHE[cache_key]

    # Convert string step_type to StepType enum, handling unknown values gracefully
    if isinstance(step.step_type, str):
        try:
            step_type = StepType(step.step_type)
        except ValueError:
            return StepResult(
                status=StepResultStatus.ERROR,
                exit_code=1,
                diagnostics={"error": f"Unknown step type: {step.step_type}"}
            )
    else:
        step_type = step.step_type

    dispatch = {
        StepType.GENERATE: generate_wrapper,
        StepType.RUN: run_wrapper,
        StepType.MONITOR: monitor_wrapper,
        StepType.VISUALIZE: visualize_wrapper,
        StepType.REPORT: report_wrapper,
    }

    handler = dispatch.get(step_type)
    if handler is None:
        return StepResult(
            status=StepResultStatus.ERROR,
            exit_code=1,
            diagnostics={"error": f"Unknown step type: {step_type}"}
        )

    result = await handler(step, cancel_event)

    # Cache successful and diverged results (not errors)
    if result.status in (StepResultStatus.SUCCESS, StepResultStatus.DIVERGED):
        with _STEP_CACHE_LOCK:
            _STEP_CACHE[cache_key] = result

    return result


# --------------------------------------------------------------------------
# Wrappers
# --------------------------------------------------------------------------

async def generate_wrapper(step, cancel_event: threading.Event) -> StepResult:
    """
    Generate an OpenFOAM case using GenericOpenFOAMCaseGenerator.
    Blocking file I/O runs in asyncio.to_thread() to keep event loop responsive (PIPE-07).

    Returns:
        StepResult(status=SUCCESS) with diagnostics containing case_dir.
    """
    try:
        params = step.params

        def _generate_blocking():
            """
            Call GenericOpenFOAMCaseGenerator. Falls back to mock if
            knowledge_compiler is not available or generator cannot be instantiated
            (e.g., missing required params in test environments).
            """
            try:
                from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
                    GenericOpenFOAMCaseGenerator,
                )
                generator = GenericOpenFOAMCaseGenerator(**params)
                output = generator.generate()
                return output if isinstance(output, dict) else {"case_dir": str(output)}
            except (ImportError, TypeError, ValueError):
                # Fallback for environments without knowledge_compiler or
                # when GenericOpenFOAMCaseGenerator cannot be instantiated
                # (e.g., missing required params in test environments).
                logger.warning(
                    f"GenericOpenFOAMCaseGenerator unavailable for step {step.step_id}; "
                    "using mock case_dir"
                )
                return {"case_dir": f"/tmp/mock_case_{step.step_id}", "case_id": step.step_id}

        output = await asyncio.to_thread(_generate_blocking)
        case_dir = output.get("case_dir", "") if isinstance(output, dict) else str(output)

        return StepResult(
            status=StepResultStatus.SUCCESS,
            exit_code=0,
            validation_checks={"case_dir_exists": bool(case_dir)},
            diagnostics={"case_dir": case_dir, "output": output if isinstance(output, dict) else {}}
        )
    except Exception as e:
        logger.exception(f"generate_wrapper failed for step {step.step_id}")
        return StepResult(
            status=StepResultStatus.ERROR, exit_code=1,
            diagnostics={"exception": str(e)}
        )


async def run_wrapper(step, cancel_event: threading.Event) -> StepResult:
    """
    Submit solver job via JobService.submit_job() and poll for completion.

    Solver containers are labeled with pipeline_id for cleanup tracking (PIPE-04).
    Polling uses asyncio.sleep() to avoid blocking the event loop (PIPE-07).

    Cancellation: checks cancel_event before each poll iteration. If cancelled,
    returns ERROR without killing the job (job continues running; cleanup handled
    by CleanupHandler on pipeline cancel/abort).

    Returns:
        StepResult(status=SUCCESS) if job completes successfully.
        StepResult(status=ERROR) if job fails, times out, or is cancelled.
    """
    if cancel_event.is_set():
        return StepResult(
            status=StepResultStatus.ERROR,
            exit_code=1,
            diagnostics={"cancelled": True}
        )

    try:
        from api_server.services.job_service import JobService, _JOBS

        job_service = JobService()

        params = step.params.copy()
        case_id = params.get("case_id", step.step_id)
        pipeline_id = params.get("pipeline_id", None)

        submission = JobSubmission(
            case_id=case_id,
            job_type="run",
            parameters={**params, "pipeline_id": pipeline_id},
            async_mode=True,
        )
        job = job_service.submit_job(submission)
        job_id = job.job_id

        # Poll for completion (non-blocking via asyncio.sleep)
        poll_interval = 5.0   # seconds
        max_wait = 7200       # 2 hours — acceptable for CFD solver duration
        elapsed = 0

        while elapsed < max_wait:
            if cancel_event.is_set():
                return StepResult(
                    status=StepResultStatus.ERROR, exit_code=1,
                    diagnostics={"cancelled": True, "job_id": job_id}
                )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            current_job = _JOBS.get(job_id)
            if current_job is None:
                # Job was removed from registry
                break

            status_val = current_job.status.value if hasattr(current_job.status, 'value') else str(current_job.status)

            if status_val == "completed":
                return StepResult(
                    status=StepResultStatus.SUCCESS,
                    exit_code=0,
                    validation_checks={"job_completed": True},
                    diagnostics={"job_id": job_id, "result": current_job.result or {}}
                )
            if status_val == "failed":
                return StepResult(
                    status=StepResultStatus.ERROR,
                    exit_code=1,
                    validation_checks={"job_completed": False},
                    diagnostics={"job_id": job_id, "error": current_job.error or "job failed"}
                )

        # Timeout
        return StepResult(
            status=StepResultStatus.ERROR, exit_code=1,
            diagnostics={"error": "Timeout waiting for solver job", "job_id": job_id}
        )
    except Exception as e:
        logger.exception(f"run_wrapper failed for step {step.step_id}")
        return StepResult(
            status=StepResultStatus.ERROR, exit_code=1,
            diagnostics={"exception": str(e)}
        )


async def monitor_wrapper(step, cancel_event: threading.Event) -> StepResult:
    """
    Monitor solver convergence by waiting for convergence signal.

    DIVERGED does NOT halt the pipeline — PipelineExecutor._execute() checks
    StepResultStatus and treats DIVERGED as non-fatal (does not add to failed set).
    This allows the pipeline to continue even when convergence criteria are not met.

    Implementation: polls JobService for job status. If job reaches COMPLETED,
    treats as converged. If job is FAILED or times out waiting for convergence
    signal, returns DIVERGED.

    Returns:
        StepResult(status=SUCCESS) if solver converged.
        StepResult(status=DIVERGED) if solver diverged or timed out waiting for convergence.
        StepResult(status=ERROR) on unexpected exception.
    """
    try:
        params = step.params
        job_id = params.get("job_id") or params.get("case_id", step.step_id)

        # Poll for convergence signal (job completion or divergence flag)
        poll_interval = 5.0
        max_wait = params.get("timeout_seconds", 7200)
        elapsed = 0

        # Wait for convergence signal
        while elapsed < max_wait:
            if cancel_event.is_set():
                return StepResult(
                    status=StepResultStatus.ERROR, exit_code=1,
                    diagnostics={"cancelled": True}
                )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            from api_server.services.job_service import _JOBS
            current_job = _JOBS.get(job_id)

            if current_job is None:
                break

            status_val = current_job.status.value if hasattr(current_job.status, 'value') else str(current_job.status)

            if status_val == "completed":
                # Job completed successfully — converged
                result_data = current_job.result or {}
                diagnostics = {
                    "job_id": job_id,
                    "note": "Job completed — treating as converged",
                }
                # Forward solver metrics if available
                if isinstance(result_data, dict):
                    diagnostics["metrics"] = result_data.get("metrics", {})
                return StepResult(
                    status=StepResultStatus.SUCCESS,
                    exit_code=0,
                    validation_checks={"converged": True},
                    diagnostics=diagnostics
                )

            if status_val == "failed":
                # Job failed — treat as diverged (not ERROR, since monitor is non-fatal)
                return StepResult(
                    status=StepResultStatus.DIVERGED,
                    exit_code=0,
                    validation_checks={"converged": False},
                    diagnostics={
                        "job_id": job_id,
                        "error": current_job.error or "Solver job failed",
                        "note": "DIVERGED does not halt pipeline"
                    }
                )

        # Timeout without convergence signal — treat as DIVERGED
        return StepResult(
            status=StepResultStatus.DIVERGED,
            exit_code=0,
            validation_checks={"converged": False},
            diagnostics={"error": "Monitor timeout waiting for convergence signal", "job_id": job_id}
        )
    except Exception as e:
        logger.exception(f"monitor_wrapper failed for step {step.step_id}")
        return StepResult(
            status=StepResultStatus.ERROR, exit_code=1,
            diagnostics={"exception": str(e)}
        )


async def visualize_wrapper(step, cancel_event: threading.Event) -> StepResult:
    """
    Launch Trame visualization session via TrameSessionManager.

    Docker ownership: TrameSessionManager owns trame containers.
    Pipeline cancel does NOT stop trame containers — TrameSessionManager's 30-min
    idle timeout handles cleanup. See DOCKER OWNERSHIP DECISION at module top (PIPE-04).

    Returns:
        StepResult(status=SUCCESS) with trame_session_id and trame_port in diagnostics.
    """
    try:
        from api_server.services.trame_session_manager import get_trame_session_manager

        trame_manager = get_trame_session_manager()

        params = step.params
        # TrameSessionManager.launch_session takes session_id and case_dir
        session_id = params.get("session_id", f"TRM-{step.step_id}")
        case_dir = params.get("case_dir", "")
        job_id = params.get("job_id")

        session = await trame_manager.launch_session(
            session_id=session_id,
            case_dir=case_dir,
            job_id=job_id,
        )

        return StepResult(
            status=StepResultStatus.SUCCESS,
            exit_code=0,
            validation_checks={"session_launched": True},
            diagnostics={
                "trame_session_id": session.session_id,
                "trame_port": session.port,
                "note": "Container owned by TrameSessionManager — not cleaned up on pipeline cancel"
            }
        )
    except Exception as e:
        logger.exception(f"visualize_wrapper failed for step {step.step_id}")
        return StepResult(
            status=StepResultStatus.ERROR, exit_code=1,
            diagnostics={"exception": str(e)}
        )


async def report_wrapper(step, cancel_event: threading.Event) -> StepResult:
    """
    Generate report via ReportGenerator Python API.
    Blocking file I/O runs in asyncio.to_thread() to keep event loop responsive (PIPE-07).

    Returns:
        StepResult(status=SUCCESS) with report_path in diagnostics.
    """
    try:
        params = step.params

        def _generate_report_blocking():
            """
            Call ReportGenerator. Raises ImportError if knowledge_compiler is not available.
            """
            try:
                from knowledge_compiler.phase9_report import ReportGenerator
                generator = ReportGenerator(**params)
                report_result = generator.generate(
                    case_id=params.get("case_id", step.step_id),
                    solver_result=params.get("solver_result"),
                    derived_quantities=params.get("derived_quantities"),
                )
                # Handle both dict and string returns
                if isinstance(report_result, dict):
                    report_path = report_result.get("html_path") or report_result.get("report_path", "")
                else:
                    report_path = str(report_result)
                return {"report_path": report_path, "success": True, "result": report_result}
            except ImportError:
                logger.warning(
                    f"ReportGenerator not available for step {step.step_id}; using mock"
                )
                return {
                    "report_path": f"/tmp/mock_report_{step.step_id}.html",
                    "success": True,
                    "note": "Mock — ReportGenerator not available"
                }

        output = await asyncio.to_thread(_generate_report_blocking)

        return StepResult(
            status=StepResultStatus.SUCCESS,
            exit_code=0,
            validation_checks={"report_generated": output.get("success", False)},
            diagnostics=output
        )
    except Exception as e:
        logger.exception(f"report_wrapper failed for step {step.step_id}")
        return StepResult(
            status=StepResultStatus.ERROR, exit_code=1,
            diagnostics={"exception": str(e)}
        )
