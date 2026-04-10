"""
Case Management Endpoints

REST API endpoints for case CRUD operations.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api_server.models import (
    CaseListResponse,
    CaseResponse,
    CaseSpec,
    CaseUpdate,
    ProblemType,
)
from api_server.services import CaseService

router = APIRouter()

# Service instance
_case_service: Optional[CaseService] = None


def get_case_service() -> CaseService:
    """Get or create case service instance."""
    global _case_service
    if _case_service is None:
        _case_service = CaseService()
    return _case_service


@router.post("/cases", response_model=CaseResponse, status_code=201, tags=["cases"])
async def create_case(spec: CaseSpec):
    """
    Create a new case.

    Creates a new CFD case with the given specification.
    Returns the created case with assigned ID and timestamps.
    """
    service = get_case_service()
    case = service.create_case(spec)
    return case


@router.get("/cases", response_model=CaseListResponse, tags=["cases"])
async def list_cases(
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
    problem_type: Optional[ProblemType] = Query(default=None, description="Filter by problem type"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
):
    """
    List all cases.

    Returns a paginated list of cases with optional filtering.
    """
    service = get_case_service()
    cases = service.list_cases(
        offset=offset,
        limit=limit,
        problem_type=problem_type,
        status=status,
    )
    total = service.get_total_count()

    return CaseListResponse(
        cases=cases,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/cases/{case_id}", response_model=CaseResponse, tags=["cases"])
async def get_case(case_id: str):
    """
    Get a case by ID.

    Returns the case with the specified ID.
    Raises 404 if case is not found.
    """
    service = get_case_service()
    case = service.get_case(case_id)

    if not case:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    return case


@router.patch("/cases/{case_id}", response_model=CaseResponse, tags=["cases"])
async def update_case(
    case_id: str,
    update: CaseUpdate,
):
    """
    Update an existing case.

    Updates only the provided fields. All fields are optional.
    Raises 404 if case is not found.
    """
    service = get_case_service()

    # Validate status if provided
    valid_statuses = ["created", "running", "completed", "failed"]
    if update.status and update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    case = service.update_case(
        case_id=case_id,
        name=update.name,
        description=update.description,
        status=update.status,
    )

    if not case:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    return case


@router.delete("/cases/{case_id}", status_code=204, tags=["cases"])
async def delete_case(case_id: str):
    """
    Delete a case.

    Removes the case from the system.
    Raises 404 if case is not found.
    """
    service = get_case_service()

    if not service.delete_case(case_id):
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    return None
