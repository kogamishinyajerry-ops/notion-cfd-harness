"""
SweepRunner — Parametric Sweep execution engine (PIPE-10).

Manages full-factorial sweep execution with concurrency control.
Each combination runs as an independent pipeline. Concurrency is controlled
by an asyncio.Semaphore (max_concurrent Docker containers at a time).
"""

import asyncio
import copy
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from api_server.models import (
    SweepCaseStatus,
    SweepStatus,
)
from api_server.services.pipeline_db import get_sweep_db_service, get_pipeline_db_service
from api_server.services.pipeline_executor import start_pipeline_executor, cancel_pipeline_executor

logger = logging.getLogger(__name__)

_ACTIVE_SWEEP_RUNNERS: Dict[str, "SweepRunner"] = {}
_ACTIVE_SWEEP_RUNNERS_LOCK = threading.Lock()


class SweepRunner:
    """Manages full-factorial sweep execution with concurrency control.

    Each combination runs as an independent pipeline. Concurrency is controlled
    by an asyncio.Semaphore (max_concurrent Docker containers at a time).
    """

    def __init__(self, sweep_id: str):
        self.sweep_id = sweep_id
        self._cancel_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._db = get_sweep_db_service()
        self._pipeline_db = get_pipeline_db_service()

    def start(self) -> None:
        """Launch sweep execution in background thread. Non-blocking."""
        self._thread = threading.Thread(
            target=self._run_sync_entrypoint,
            name=f"sweep-{self.sweep_id}",
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Signal cancellation of the sweep."""
        self._cancel_event.set()
        logger.info(f"Cancel requested for sweep {self.sweep_id}")

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _run_sync_entrypoint(self) -> None:
        asyncio.run(self._execute())

    async def _execute(self) -> None:
        """Main async coroutine."""
        sweep = self._db.get_sweep(self.sweep_id)
        if not sweep:
            logger.error(f"Sweep {self.sweep_id} not found")
            return

        base_pipeline = self._pipeline_db.get_pipeline(sweep.base_pipeline_id)
        if not base_pipeline:
            logger.error(f"Base pipeline {sweep.base_pipeline_id} not found for sweep {self.sweep_id}")
            self._db.update_sweep_status(self.sweep_id, SweepStatus.FAILED)
            return

        # Transition sweep to RUNNING
        self._db.update_sweep_status(self.sweep_id, SweepStatus.RUNNING)

        cases = self._db.get_sweep_cases(self.sweep_id)
        running_case_poll_tasks: List[asyncio.Task] = []
        semaphore = asyncio.Semaphore(sweep.max_concurrent)

        # Launch cases with concurrency control
        for case in cases:
            if self.is_cancelled():
                break
            # Wait for a concurrency slot before launching
            await semaphore.acquire()
            if self.is_cancelled():
                semaphore.release()
                break
            task = asyncio.create_task(self._run_case(case, base_pipeline, semaphore))
            running_case_poll_tasks.append(task)

        # Wait for all case tasks to complete
        if running_case_poll_tasks:
            await asyncio.gather(*running_case_poll_tasks, return_exceptions=True)

        # Final sweep status
        if self.is_cancelled():
            self._db.update_sweep_status(self.sweep_id, SweepStatus.CANCELLED)
        else:
            # Check if any case failed
            remaining_cases = self._db.get_sweep_cases(self.sweep_id)
            all_completed = all(
                c.status in (SweepCaseStatus.COMPLETED, SweepCaseStatus.FAILED, SweepCaseStatus.CANCELLED)
                for c in remaining_cases
            )
            any_failed = any(c.status == SweepCaseStatus.FAILED for c in remaining_cases)
            if all_completed:
                self._db.update_sweep_status(
                    self.sweep_id,
                    SweepStatus.COMPLETED if not any_failed else SweepStatus.FAILED,
                )

        # Deregister self
        with _ACTIVE_SWEEP_RUNNERS_LOCK:
            _ACTIVE_SWEEP_RUNNERS.pop(self.sweep_id, None)

    async def _run_case(self, case, base_pipeline, semaphore: asyncio.Semaphore) -> None:
        """Run a single combination case: create pipeline, start it, poll to completion."""
        try:
            # Deep-copy base pipeline and inject params
            new_pipeline_steps = copy.deepcopy(base_pipeline.steps)

            # Inject param_combination into each step's params
            for step in new_pipeline_steps:
                step.params["_sweep_override"] = case.param_combination

            # Create output dir path in config
            output_dir = f"sweep_{self.sweep_id}/{case.combination_hash}/"
            pipeline_config = copy.deepcopy(base_pipeline.config)
            pipeline_config["sweep_case_id"] = case.id
            pipeline_config["output_dir"] = output_dir

            # Create the pipeline via PipelineDBService
            from api_server.models import PipelineCreate

            create_spec = PipelineCreate(
                name=f"{base_pipeline.name} [{case.combination_hash}]",
                description=f"Sweep {self.sweep_id} case {case.combination_hash}",
                steps=new_pipeline_steps,
                config=pipeline_config,
            )
            new_pipeline = get_pipeline_db_service().create_pipeline(create_spec)

            # Update case with pipeline_id and mark RUNNING
            self._db.update_case_pipeline_id(case.id, new_pipeline.id)

            # Start the pipeline
            try:
                loop = asyncio.get_event_loop()
                start_pipeline_executor(new_pipeline.id, loop)
            except Exception as e:
                logger.error(f"Failed to start pipeline {new_pipeline.id} for case {case.id}: {e}")
                self._db.update_case_result(case.id, SweepCaseStatus.FAILED, {"error": str(e)})
                semaphore.release()
                self._db.increment_completed(self.sweep_id)
                return

            # Poll until pipeline completes
            while not self.is_cancelled():
                await asyncio.sleep(5)
                pipeline = get_pipeline_db_service().get_pipeline(new_pipeline.id)
                if not pipeline:
                    break
                from api_server.models import PipelineStatus

                if pipeline.status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.CANCELLED):
                    # Extract result summary
                    result_summary: Dict[str, Any] = {}
                    execution_time = None
                    final_residual = None
                    for step in pipeline.steps:
                        if step.result and step.result.diagnostics:
                            if "final_residual" in step.result.diagnostics:
                                final_residual = step.result.diagnostics["final_residual"]
                            if "execution_time" in step.result.diagnostics:
                                execution_time = step.result.diagnostics["execution_time"]
                    result_summary["final_residual"] = final_residual
                    result_summary["execution_time"] = execution_time
                    result_summary["pipeline_status"] = (
                        pipeline.status.value if hasattr(pipeline.status, "value") else pipeline.status
                    )

                    case_status = SweepCaseStatus.COMPLETED
                    if pipeline.status == PipelineStatus.FAILED:
                        case_status = SweepCaseStatus.FAILED
                    elif pipeline.status == PipelineStatus.CANCELLED:
                        case_status = SweepCaseStatus.CANCELLED

                    self._db.update_case_result(case.id, case_status, result_summary)
                    self._db.increment_completed(self.sweep_id)
                    break

            if self.is_cancelled() and new_pipeline:
                # Cancel the child pipeline
                cancel_pipeline_executor(new_pipeline.id)

        except Exception as e:
            logger.exception(f"Error running case {case.id}")
            self._db.update_case_result(case.id, SweepCaseStatus.FAILED, {"error": str(e)})
            self._db.increment_completed(self.sweep_id)
        finally:
            semaphore.release()


def start_sweep_runner(sweep_id: str) -> SweepRunner:
    """Create and start a SweepRunner in background thread."""
    with _ACTIVE_SWEEP_RUNNERS_LOCK:
        if sweep_id in _ACTIVE_SWEEP_RUNNERS:
            raise ValueError(f"Sweep {sweep_id} is already running")
        runner = SweepRunner(sweep_id)
        _ACTIVE_SWEEP_RUNNERS[sweep_id] = runner
        runner.start()
    return runner


def cancel_sweep_runner(sweep_id: str) -> bool:
    """Signal cancel on active sweep runner."""
    with _ACTIVE_SWEEP_RUNNERS_LOCK:
        runner = _ACTIVE_SWEEP_RUNNERS.get(sweep_id)
    if runner:
        runner.cancel()
        return True
    return False


def get_sweep_runner(sweep_id: str) -> Optional[SweepRunner]:
    return _ACTIVE_SWEEP_RUNNERS.get(sweep_id)
