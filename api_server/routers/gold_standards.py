"""
GoldStandard Case Management Endpoints

GS-02 REST API: Exposes GoldStandardRegistry via FastAPI.
GET  /gold-standard-cases                        — list all cases
GET  /gold-standard-cases/{case_id}            — case detail + ReportSpec
GET  /gold-standard-cases/{case_id}/reference-data — literature values
POST /gold-standard-cases/{case_id}/validate    — validate ReportSpec against gold standard
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api_server.models import (
    GoldStandardCaseDetail,
    GoldStandardListResponse,
    ValidationResultResponse,
)
from api_server.services.gold_standard_service import get_gold_standard_service

router = APIRouter(prefix="/gold-standard-cases", tags=["gold-standard-cases"])


@router.get("", response_model=GoldStandardListResponse)
async def list_gold_standard_cases(
    platform: Optional[str] = Query(None, description="Filter by platform (OpenFOAM or SU2)"),
    tier: Optional[str] = Query(None, description="Filter by tier (core_seed, bridge, breadth)"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    has_gold_standard: Optional[bool] = Query(None, description="Filter by whether GoldStandard module is registered"),
):
    """
    List all GoldStandard cases with optional filters.

    Returns all 30 whitelist cases, marking which have registered GoldStandard modules.
    """
    service = get_gold_standard_service()
    return service.list_cases(
        platform=platform,
        tier=tier,
        difficulty=difficulty,
        has_gold_standard=has_gold_standard,
    )


@router.get("/{case_id}", response_model=GoldStandardCaseDetail)
async def get_gold_standard_case(case_id: str):
    """
    Get detailed GoldStandard case including ReportSpec and metadata.

    Returns ColdStartCase metadata from whitelist plus ReportSpec,
    mesh info, and solver config if registered.
    """
    service = get_gold_standard_service()
    detail = service.get_case_detail(case_id)

    if not detail:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    return detail


@router.get("/{case_id}/reference-data")
async def get_gold_standard_reference_data(case_id: str):
    """
    Get literature reference data for a GoldStandard case.

    Returns the published benchmark values (e.g., Ghia 1982 centerline velocities)
    that the GoldStandard validates against.
    """
    service = get_gold_standard_service()
    data = service.get_reference_data(case_id)

    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No reference data registered for {case_id}"
        )

    return {"case_id": case_id, "reference_data": data}


@router.post("/{case_id}/validate", response_model=ValidationResultResponse)
async def validate_gold_standard(case_id: str, result_spec: dict):
    """
    Validate a ReportSpec against the GoldStandard for a case.

    The result_spec should be a ReportSpec dict (as produced by ReportSpec.to_dict()).
    Returns per-metric pass/fail with error percentages.
    """
    service = get_gold_standard_service()
    return service.validate_result(case_id, result_spec)
