"""
Job Management Endpoints

REST API endpoints for job submission and status monitoring.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api_server.models import JobListResponse, JobResponse, JobStatus, JobSubmission
from api_server.services import JobService

router = APIRouter()

# Service instance
_job_service: Optional[JobService] = None


def get_job_service() -> JobService:
    """Get or create job service instance."""
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service


@router.post("/jobs", response_model=JobResponse, status_code=201, tags=["jobs"])
async def submit_job(submission: JobSubmission):
    """
    Submit a new job.

    Submits a job for execution. The job can run synchronously (blocking)
    or asynchronously (background). Use async_mode=true for long-running jobs.
    """
    service = get_job_service()
    job = service.submit_job(submission)
    return job


@router.get("/jobs", response_model=JobListResponse, tags=["jobs"])
async def list_jobs(
    case_id: Optional[str] = Query(default=None, description="Filter by case ID"),
    status: Optional[JobStatus] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
):
    """
    List all jobs.

    Returns a list of jobs with optional filtering by case ID or status.
    """
    service = get_job_service()
    jobs = service.list_jobs(
        case_id=case_id,
        status=status,
        limit=limit,
    )

    return JobListResponse(
        jobs=jobs,
        total=len(jobs),
    )


@router.get("/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
async def get_job(job_id: str):
    """
    Get a job by ID.

    Returns the job with the specified ID including current status and result.
    Raises 404 if job is not found.
    """
    service = get_job_service()
    job = service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse, tags=["jobs"])
async def cancel_job(job_id: str):
    """
    Cancel a pending or running job.

    Attempts to cancel the specified job.
    Only works for jobs in PENDING or RUNNING status.
    Raises 400 if job cannot be cancelled.
    Raises 404 if job is not found.
    """
    service = get_job_service()
    job = service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if not service.cancel_job(job_id):
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot be cancelled in status: {job.status.value}"
        )

    return service.get_job(job_id)


@router.delete("/jobs/{job_id}/abort", tags=["jobs"])
async def abort_job(job_id: str) -> dict:
    """
    Abort a running job by killing its Docker container.

    Args:
        job_id: Job identifier

    Returns:
        {"job_id": str, "aborted": bool, "message": str}
    """
    service = get_job_service()

    # Check job exists
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Only pending/running jobs can be aborted
    if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
        return {"job_id": job_id, "aborted": False, "message": f"Job is {job.status.value}, cannot abort"}

    # Sync cancel (mark as cancelled)
    service.cancel_job(job_id)

    # Async cancel (kill container if running)
    await service.cancel_job_async(job_id)

    return {"job_id": job_id, "aborted": True, "message": "Job aborted"}
