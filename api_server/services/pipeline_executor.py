"""
PipelineExecutor — Core orchestration engine.

Architecture (PIPE-07):
  - PipelineExecutor runs in a dedicated background threading.Thread
  - FastAPI is the API facade only; it does NOT own pipeline lifecycle
  - Blocking I/O inside step wrappers uses asyncio.to_thread() in Plan 02

Docker ownership decision (PIPE-04 / PITFALL 2.2):
  - DECISION: Option B — TrameSessionManager retains ownership of trame viewer containers
  - PipelineExecutor owns solver (run-step) containers ONLY
  - Solver containers are started with label pipeline_id=<id> for cleanup tracking
  - Trame containers are started via TrameSessionManager.launch_session() and are NOT
    stopped during pipeline cancel/abort — TrameSessionManager manages their lifecycle
  - This avoids lifecycle conflicts between pipeline abort and interactive viewer sessions
"""
import asyncio
import json
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from api_server.models import (
    PipelineStatus,
    StepStatus,
    StepType,
    StepResult,
    StepResultStatus,
)
from api_server.services.pipeline_db import get_pipeline_db_service
from api_server.services.pipeline_websocket import PipelineEvent, broadcast_pipeline_event

logger = logging.getLogger(__name__)

# Registry of active PipelineExecutor runs: pipeline_id -> executor thread
_ACTIVE_EXECUTORS: Dict[str, "PipelineExecutor"] = {}
_ACTIVE_EXECUTORS_LOCK = threading.Lock()


def topological_sort(steps) -> list:
    """
    Topological sort of PipelineStep list using Kahn's algorithm.

    steps: list of PipelineStep (each has step_id: str, depends_on: List[str])
    Returns ordered list. Raises ValueError if cycle detected.
    """
    id_to_step = {s.step_id: s for s in steps}
    in_degree = {s.step_id: 0 for s in steps}
    adj: Dict[str, List[str]] = {s.step_id: [] for s in steps}

    for step in steps:
        for dep in step.depends_on:
            if dep not in id_to_step:
                raise ValueError(f"Step '{step.step_id}' depends on unknown step '{dep}'")
            adj[dep].append(step.step_id)
            in_degree[step.step_id] += 1

    queue = deque(sid for sid, deg in in_degree.items() if deg == 0)
    ordered = []

    while queue:
        sid = queue.popleft()
        ordered.append(id_to_step[sid])
        for neighbour in adj[sid]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(ordered) != len(steps):
        raise ValueError("Cycle detected in pipeline DAG")
    return ordered


def _get_ready_steps(steps, completed: Set[str]) -> list:
    """
    Return steps whose all depends_on predecessors are in `completed`.

    Args:
        steps: full list of PipelineStep
        completed: set of step_ids that have COMPLETED

    Returns:
        List of steps ready to execute (all deps satisfied, not yet completed)
    """
    ready = []
    for step in steps:
        if step.step_id in completed:
            continue
        if all(dep in completed for dep in step.depends_on):
            ready.append(step)
    return ready


def _find_dependents(failed_step_id: str, all_steps: list) -> list:
    """
    Return all steps that transitively depend on failed_step_id.

    Used by _propagate_failure to mark all downstream steps as SKIPPED.
    """
    dependent = set()
    changed = True
    while changed:
        changed = False
        for s in all_steps:
            if s.step_id in dependent:
                continue
            if failed_step_id in s.depends_on or any(dep in dependent for dep in s.depends_on):
                dependent.add(s.step_id)
                changed = True
    return [s for s in all_steps if s.step_id in dependent]


def _propagate_failure(failed_step_id: str, all_steps: list) -> list:
    """
    Return all steps transitively dependent on failed_step_id.

    Caller is responsible for marking these as SKIPPED in the DB.
    """
    return _find_dependents(failed_step_id, all_steps)


# Pipeline-status mapping for step-type-aware pipeline-level status
_STEP_TYPE_TO_PIPELINE_STATUS: Dict[StepType, PipelineStatus] = {
    StepType.GENERATE: PipelineStatus.RUNNING,
    StepType.RUN: PipelineStatus.RUNNING,
    StepType.MONITOR: PipelineStatus.MONITORING,
    StepType.VISUALIZE: PipelineStatus.VISUALIZING,
    StepType.REPORT: PipelineStatus.REPORTING,
}


class PipelineExecutor:
    """
    Executes a pipeline in a dedicated background thread.

    Communicates with FastAPI via SQLite (state) and PipelineEventBus (WebSocket events).

    Key design decisions:
    - Runs in a dedicated threading.Thread, NOT FastAPI BackgroundTasks (PIPE-07)
    - Cancellation: uses threading.Event so blocking step wrappers can also check it
    - Step result: uses `status` (StepResultStatus) not exit_code as success signal (PIPE-03)
    - Diverged monitor result: does NOT halt pipeline by default (PIPE-03)
    """

    def __init__(self, pipeline_id: str, loop: asyncio.AbstractEventLoop):
        self.pipeline_id = pipeline_id
        self._loop = loop        # main event loop for scheduling coroutines
        self._cancel_event = threading.Event()
        self.pause_event = threading.Event()  # set() = paused, clear() = running
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._db = get_pipeline_db_service()

    # -- Public control interface --

    def start(self) -> None:
        """Launch execution in background thread. Non-blocking."""
        self._thread = threading.Thread(
            target=self._run_sync_entrypoint,
            name=f"pipeline-{self.pipeline_id}",
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Signal cancellation. Running step wrappers check this event."""
        self._cancel_event.set()
        logger.info(f"Cancel requested for pipeline {self.pipeline_id}")

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def pause(self) -> None:
        """Signal the executor to pause after the current step completes."""
        logger.info(f"PipelineExecutor {self.pipeline_id}: pause requested")
        self._paused = True
        self.pause_event.set()

    def resume(self) -> None:
        """Resume a paused executor."""
        logger.info(f"PipelineExecutor {self.pipeline_id}: resume requested")
        self._paused = False
        self.pause_event.clear()

    @property
    def is_paused(self) -> bool:
        return self._paused

    # -- Execution logic --

    def _run_sync_entrypoint(self) -> None:
        """Entry point for background thread — runs its own event loop."""
        asyncio.run(self._execute())

    async def _execute(self) -> None:
        """Main async coroutine that drives pipeline execution."""
        db = self._db
        pipeline = db.get_pipeline(self.pipeline_id)
        if pipeline is None:
            logger.error(f"Pipeline {self.pipeline_id} not found at execution start")
            return

        # Validate DAG and get sorted steps
        try:
            ordered_steps = topological_sort(pipeline.steps)
        except ValueError as e:
            logger.error(f"Pipeline {self.pipeline_id} DAG error: {e}")
            db.update_pipeline_status(self.pipeline_id, PipelineStatus.FAILED)
            await self._emit(PipelineEvent(
                event_type="pipeline_failed",
                pipeline_id=self.pipeline_id,
                payload={"error": str(e)},
            ))
            return

        # Transition to RUNNING
        db.update_pipeline_status(self.pipeline_id, PipelineStatus.RUNNING)
        await self._emit(PipelineEvent(
            event_type="pipeline_started",
            pipeline_id=self.pipeline_id,
            payload={"total_steps": len(ordered_steps)},
        ))

        completed: Set[str] = set()
        failed: Set[str] = set()
        skipped: Set[str] = set()

        for step in ordered_steps:
            if self.is_cancelled():
                # Mark remaining PENDING steps as SKIPPED
                if step.step_id not in completed and step.step_id not in failed:
                    db.update_step_status(self.pipeline_id, step.step_id, StepStatus.SKIPPED)
                    skipped.add(step.step_id)
                continue

            # Wait if paused — loop handles spurious wakeups and resume-between-check-and-wait race
            while self._paused:
                logger.info(f"PipelineExecutor {self.pipeline_id}: paused, waiting to resume...")
                self.pause_event.wait()
                # Spurious wakeup or resume() cleared the event — loop will re-check _paused
            if not self.is_cancelled():
                logger.info(f"PipelineExecutor {self.pipeline_id}: resumed")

            # Check if all dependencies are completed
            deps_ok = all(dep in completed for dep in step.depends_on)
            if not deps_ok:
                # Some dependency failed/skipped — skip this step
                db.update_step_status(self.pipeline_id, step.step_id, StepStatus.SKIPPED)
                skipped.add(step.step_id)
                continue

            # Update pipeline-level status to reflect current step type
            pipeline_state = _STEP_TYPE_TO_PIPELINE_STATUS.get(step.step_type, PipelineStatus.RUNNING)
            db.update_pipeline_status(self.pipeline_id, pipeline_state)

            # Mark step RUNNING
            db.update_step_status(self.pipeline_id, step.step_id, StepStatus.RUNNING)
            await self._emit(PipelineEvent(
                event_type="step_started",
                pipeline_id=self.pipeline_id,
                payload={"step_id": step.step_id, "step_type": step.step_type},
            ))

            # Execute step (step_wrappers.py installed by Plan 02)
            result = await self._execute_step(step)

            # Store result in DB
            result_json = result.model_dump_json() if result else None
            step_ok = result is not None and result.status in (
                StepResultStatus.SUCCESS, StepResultStatus.DIVERGED  # diverged does not halt
            )

            if step_ok:
                db.update_step_status(self.pipeline_id, step.step_id, StepStatus.COMPLETED, result_json)
                completed.add(step.step_id)
                await self._emit(PipelineEvent(
                    event_type="step_completed",
                    pipeline_id=self.pipeline_id,
                    payload={"step_id": step.step_id, "status": result.status if result else "unknown"},
                ))
            else:
                db.update_step_status(self.pipeline_id, step.step_id, StepStatus.FAILED, result_json)
                failed.add(step.step_id)
                await self._emit(PipelineEvent(
                    event_type="step_failed",
                    pipeline_id=self.pipeline_id,
                    payload={"step_id": step.step_id, "error": result.diagnostics if result else {}},
                ))
                # Mark all transitive dependents as SKIPPED
                dependents = _find_dependents(step.step_id, ordered_steps)
                for dep_step in dependents:
                    db.update_step_status(self.pipeline_id, dep_step.step_id, StepStatus.SKIPPED)
                    skipped.add(dep_step.step_id)

        # Final pipeline state
        if self.is_cancelled():
            db.update_pipeline_status(self.pipeline_id, PipelineStatus.CANCELLED)
            await self._emit(PipelineEvent(
                event_type="pipeline_cancelled",
                pipeline_id=self.pipeline_id,
                payload={},
            ))
        elif failed:
            db.update_pipeline_status(self.pipeline_id, PipelineStatus.FAILED)
            await self._emit(PipelineEvent(
                event_type="pipeline_failed",
                pipeline_id=self.pipeline_id,
                payload={"failed_steps": list(failed)},
            ))
        else:
            db.update_pipeline_status(self.pipeline_id, PipelineStatus.COMPLETED)
            await self._emit(PipelineEvent(
                event_type="pipeline_completed",
                pipeline_id=self.pipeline_id,
                payload={},
            ))

        # Deregister self
        with _ACTIVE_EXECUTORS_LOCK:
            _ACTIVE_EXECUTORS.pop(self.pipeline_id, None)

    async def _execute_step(self, step) -> Optional[StepResult]:
        """
        Dispatch to step wrapper. Installed by Plan 02 (step_wrappers.py).

        Returns StepResult or None on unexpected exception.
        """
        # Plan 02 will replace this import with real wrappers
        try:
            from api_server.services.step_wrappers import execute_step
            return await execute_step(step, self._cancel_event)
        except ImportError:
            # step_wrappers not yet installed (Plan 02); return stub success
            logger.warning(f"step_wrappers not installed; returning stub success for {step.step_id}")
            return StepResult(status=StepResultStatus.SUCCESS, exit_code=0)
        except Exception as e:
            logger.exception(f"Step {step.step_id} raised unexpected exception")
            return StepResult(
                status=StepResultStatus.ERROR,
                exit_code=1,
                diagnostics={"exception": str(e)},
            )

    async def _emit(self, event: PipelineEvent) -> None:
        try:
            await broadcast_pipeline_event(event)
        except Exception as e:
            logger.warning(f"Failed to emit event {event.event_type}: {e}")


# -- Public API --

def start_pipeline_executor(pipeline_id: str, loop: asyncio.AbstractEventLoop) -> PipelineExecutor:
    """Create and start a PipelineExecutor in background thread. Idempotent per pipeline_id."""
    with _ACTIVE_EXECUTORS_LOCK:
        if pipeline_id in _ACTIVE_EXECUTORS:
            raise ValueError(f"Pipeline {pipeline_id} is already running")
        executor = PipelineExecutor(pipeline_id, loop)
        _ACTIVE_EXECUTORS[pipeline_id] = executor
        executor.start()  # start inside lock to prevent duplicate executor race
    return executor


def cancel_pipeline_executor(pipeline_id: str) -> bool:
    """Signal cancel on active executor. Returns True if found."""
    with _ACTIVE_EXECUTORS_LOCK:
        executor = _ACTIVE_EXECUTORS.get(pipeline_id)
    if executor:
        executor.cancel()
        return True
    return False


def get_active_executor(pipeline_id: str) -> Optional[PipelineExecutor]:
    with _ACTIVE_EXECUTORS_LOCK:
        return _ACTIVE_EXECUTORS.get(pipeline_id)


def get_pipeline_executor(pipeline_id: str) -> Optional["PipelineExecutor"]:
    """Get the active PipelineExecutor for a pipeline, or None."""
    return _ACTIVE_EXECUTORS.get(pipeline_id)
