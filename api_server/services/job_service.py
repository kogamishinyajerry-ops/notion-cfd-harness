"""
Job Service

Business logic for job submission and management.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from api_server.models import JobResponse, JobStatus, JobSubmission
from api_server.services.websocket_manager import get_websocket_manager

logger = logging.getLogger(__name__)

# In-memory job storage
_JOBS: Dict[str, JobResponse] = {}

# Active job tracking
_ACTIVE_JOBS: Dict[str, "ActiveJob"] = {}


@dataclass
class ActiveJob:
    task: asyncio.Task
    container_id: Optional[str] = None
    job_id: str = ""


class JobService:
    """
    Service for managing job execution.

    Handles job submission, status tracking, and result retrieval.
    Supports both synchronous and asynchronous job execution.
    """

    def __init__(self):
        """Initialize the job service."""
        pass

    def submit_job(self, submission: JobSubmission) -> JobResponse:
        """
        Submit a new job for execution.

        Args:
            submission: Job submission specification

        Returns:
            Job response with initial status
        """
        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()

        job = JobResponse(
            job_id=job_id,
            case_id=submission.case_id,
            job_type=submission.job_type,
            status=JobStatus.PENDING,
            submitted_at=now,
            started_at=None,
            completed_at=None,
            progress=0.0,
            result=None,
            error=None,
        )

        _JOBS[job_id] = job

        if submission.async_mode:
            # Schedule async execution
            asyncio.create_task(self._execute_job_async(job_id, submission))
        else:
            # Run synchronously
            asyncio.create_task(self._execute_job_async(job_id, submission))

        logger.info(f"Submitted job: {job_id} (async={submission.async_mode})")
        return job

    async def _execute_job_async(self, job_id: str, submission: JobSubmission) -> None:
        """
        Execute job asynchronously.

        Args:
            job_id: Job identifier
            submission: Job submission specification
        """
        job = _JOBS.get(job_id)
        if not job:
            return

        ws_manager = get_websocket_manager()

        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            _JOBS[job_id] = job

            # Broadcast running status
            await ws_manager.broadcast(job_id, {
                "type": "status",
                "job": self._job_to_dict(job),
            })

            # Execute the actual job — residual streaming via WebSocket is handled in _run_case
            result = await self._run_job(submission, job_id)

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress = 100.0
            job.result = result

            # Broadcast completion
            await ws_manager.broadcast(job_id, {
                "type": "completion",
                "status": job.status.value,
                "result": result,
                "job": self._job_to_dict(job),
            })

        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            logger.error(f"Job {job_id} failed: {e}")

            # Broadcast failure
            await ws_manager.broadcast(job_id, {
                "type": "error",
                "error": str(e),
                "job": self._job_to_dict(job),
            })

        _JOBS[job_id] = job

    async def _run_job(self, submission: JobSubmission, job_id: str) -> Dict:
        """
        Run the actual job logic.

        Args:
            submission: Job submission specification
            job_id: Job identifier (for container tracking)

        Returns:
            Job result data
        """
        # Delegate to runtime based on job type
        if submission.job_type == "run":
            return await self._run_case(submission, job_id)
        elif submission.job_type == "verify":
            return await self._verify_case(submission)
        elif submission.job_type == "report":
            return await self._generate_report(submission)
        else:
            return {"status": "unknown_job_type", "job_type": submission.job_type}

    async def _run_case(self, submission: JobSubmission, job_id: str) -> Dict:
        """Execute a case using the streaming executor with real-time residual broadcasting."""
        from knowledge_compiler.phase2.execution_layer.openfoam_docker import OpenFOAMDockerExecutor

        ws_manager = get_websocket_manager()

        async def residual_callback(residual_data: Dict) -> None:
            """Broadcast residual data to WebSocket subscribers."""
            await ws_manager.broadcast(job_id, {
                "type": "residual",
                **residual_data,
            })

        # Wrap with DivergenceDetector for MON-06 divergence detection
        from api_server.services.divergence_detector import DivergenceDetector
        detector = DivergenceDetector(residual_callback)

        try:
            # Build config from submission parameters
            config = {
                "case_id": submission.case_id,
                "case_dir": submission.parameters.get("case_dir"),
                "solver": submission.parameters.get("solver", "simpleFoam"),
                "docker": submission.parameters.get("docker", {}),
            }

            executor = OpenFOAMDockerExecutor()
            streaming_result = await executor.execute_streaming(
                config=config,
                residual_callback=detector,
            )

            # Store container_id in _ACTIVE_JOBS for abort support
            if job_id in _ACTIVE_JOBS:
                _ACTIVE_JOBS[job_id].container_id = streaming_result.container_id

            result = streaming_result.solver_result
            return {
                "status": "completed" if result.success else "failed",
                "case_id": submission.case_id,
                "job_type": submission.job_type,
                "message": "Case executed via streaming executor",
                "result": {
                    "output_dir": result.output_dir,
                    "metrics": result.metrics,
                    "execution_time_s": result.execution_time_s,
                },
            }
        except Exception as e:
            logger.error(f"Case execution failed: {e}")
            return {
                "status": "failed",
                "case_id": submission.case_id,
                "job_type": submission.job_type,
                "error": str(e),
            }

    async def _verify_case(self, submission: JobSubmission) -> Dict:
        """Verify case results using the verify console."""
        try:
            from knowledge_compiler.orchestrator.verify_console import VerifyConsole

            console = VerifyConsole()
            results_data = submission.parameters.get("results_data", {}) if submission.parameters else {}

            report = console.run_full_verification(
                submission.case_id or "CASE-001",
                results_data
            )

            return {
                "status": "completed",
                "case_id": submission.case_id,
                "job_type": submission.job_type,
                "message": "Verification completed",
                "result": report.to_dict() if hasattr(report, 'to_dict') else str(report),
                "passed": report.overall_pass if hasattr(report, 'overall_pass') else True,
            }
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return {
                "status": "failed",
                "case_id": submission.case_id,
                "job_type": submission.job_type,
                "error": str(e),
            }

    async def _generate_report(self, submission: JobSubmission) -> Dict:
        """Generate case report using the report generator."""
        try:
            from knowledge_compiler.phase9_report import ReportGenerator

            case_id = submission.case_id or "CASE-001"
            parameters = submission.parameters or {}

            # Generate report (standalone, without case context)
            report_gen = ReportGenerator()
            report_result = report_gen.generate(
                case_id=case_id,
                solver_result=parameters.get("solver_result"),
                derived_quantities=parameters.get("derived_quantities"),
            )

            return {
                "status": "completed",
                "case_id": case_id,
                "job_type": submission.job_type,
                "message": "Report generated",
                "result": report_result,
                "formats": list(report_result.keys()) if isinstance(report_result, dict) else ["html"],
            }
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return {
                "status": "failed",
                "case_id": submission.case_id,
                "job_type": submission.job_type,
                "error": str(e),
            }

    def get_job(self, job_id: str) -> Optional[JobResponse]:
        """
        Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job response or None if not found
        """
        return _JOBS.get(job_id)

    def list_jobs(
        self,
        case_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50,
    ) -> list[JobResponse]:
        """
        List jobs with optional filtering.

        Args:
            case_id: Filter by case ID
            status: Filter by job status
            limit: Maximum results

        Returns:
            List of matching jobs
        """
        results = list(_JOBS.values())

        if case_id:
            results = [j for j in results if j.case_id == case_id]
        if status:
            results = [j for j in results if j.status == status]

        # Sort by submission date (newest first)
        results.sort(key=lambda j: j.submitted_at, reverse=True)

        return results[:limit]

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending or running job.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled, False if not found or not cancellable
        """
        job = _JOBS.get(job_id)
        if not job:
            return False

        if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            _JOBS[job_id] = job
            logger.info(f"Cancelled job: {job_id}")
            return True

        return False

    async def cancel_job_async(self, job_id: str) -> bool:
        """
        Asynchronously cancel a running job by killing its Docker container.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled, False if job not found or no container
        """
        active_job = _ACTIVE_JOBS.get(job_id)
        if not active_job:
            return False

        if active_job.container_id:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "kill", active_job.container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                logger.info(f"Docker container {active_job.container_id} killed for job {job_id}")
            except Exception as e:
                logger.warning(f"Failed to kill container {active_job.container_id}: {e}")

        if active_job.task and not active_job.task.done():
            active_job.task.cancel()
            try:
                await active_job.task
            except asyncio.CancelledError:
                pass

        return True

    def get_active_job_count(self) -> int:
        """Get count of active (pending/running) jobs."""
        return sum(
            1 for j in _JOBS.values()
            if j.status in (JobStatus.PENDING, JobStatus.RUNNING)
        )

    def _job_to_dict(self, job: JobResponse) -> dict:
        """
        Convert a JobResponse to a dictionary for JSON serialization.

        Args:
            job: Job response object

        Returns:
            Dictionary representation
        """
        return {
            "job_id": job.job_id,
            "case_id": job.case_id,
            "job_type": job.job_type,
            "status": job.status.value,
            "progress": job.progress,
            "submitted_at": job.submitted_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result": job.result,
            "error": job.error,
        }


# Service singleton
_job_service: Optional[JobService] = None


def get_job_service() -> JobService:
    """Get or create job service instance."""
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service
