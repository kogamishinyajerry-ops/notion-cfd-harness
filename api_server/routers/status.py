"""
Status Endpoints

System status, health check, and uptime monitoring endpoints.
"""

import time
from datetime import datetime

from fastapi import APIRouter

from api_server.config import DEBUG
from api_server.models import HealthResponse, SystemStatus

router = APIRouter()

# Application start time (imported from main for uptime calculation)
APP_START_TIME = time.time()


def get_uptime_seconds() -> float:
    """Calculate uptime since application start."""
    return time.time() - APP_START_TIME


@router.get("/health", response_model=HealthResponse, tags=["status"])
async def health_check():
    """
    Health check endpoint.

    Returns basic health status of the API server.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.2.0",
    )


@router.get("/status", response_model=SystemStatus, tags=["status"])
async def system_status():
    """
    Get detailed system status.

    Returns comprehensive system status including uptime,
    job counts, and knowledge registry statistics.
    """
    from api_server.services.case_service import CaseService
    from api_server.services.job_service import JobService
    from api_server.services.knowledge_service import KnowledgeService

    try:
        case_service = CaseService()
        case_count = len(case_service.list_cases())
    except Exception:
        case_count = 0

    try:
        job_service = JobService()
        active_jobs = job_service.get_active_job_count()
    except Exception:
        active_jobs = 0

    try:
        knowledge_service = KnowledgeService()
        unit_count = knowledge_service.get_unit_count()
    except Exception:
        unit_count = 0

    return SystemStatus(
        version="1.2.0",
        status="operational" if not DEBUG else "debug",
        uptime_seconds=get_uptime_seconds(),
        active_jobs=active_jobs,
        total_cases=case_count,
        knowledge_units=unit_count,
    )
