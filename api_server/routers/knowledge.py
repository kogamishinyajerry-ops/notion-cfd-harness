"""
Knowledge Registry Endpoints

REST API endpoints for knowledge unit queries.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api_server.models import KnowledgeSearchRequest, KnowledgeSearchResponse, KnowledgeUnit
from api_server.services import KnowledgeService

router = APIRouter()

# Service instance
_knowledge_service: Optional[KnowledgeService] = None


def get_knowledge_service() -> KnowledgeService:
    """Get or create knowledge service instance."""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service


@router.get("/knowledge/search", response_model=KnowledgeSearchResponse, tags=["knowledge"])
async def search_knowledge(
    query: str = Query(..., description="Search query", min_length=1),
    unit_type: Optional[str] = Query(default=None, description="Filter by unit type"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
):
    """
    Search knowledge units.

    Performs a free-text search across all knowledge units.
    Optionally filter by unit type.
    """
    service = get_knowledge_service()
    results = service.search(
        query=query,
        unit_type=unit_type,
        limit=limit,
    )

    return KnowledgeSearchResponse(
        results=results,
        total=len(results),
    )


@router.get("/knowledge/units/{unit_id}", response_model=KnowledgeUnit, tags=["knowledge"])
async def get_knowledge_unit(unit_id: str):
    """
    Get a knowledge unit by ID.

    Returns detailed information about a specific knowledge unit.
    Raises 404 if unit is not found.
    """
    service = get_knowledge_service()
    unit = service.get_unit(unit_id)

    if not unit:
        raise HTTPException(status_code=404, detail=f"Knowledge unit not found: {unit_id}")

    return unit


@router.get("/knowledge/types/{unit_type}", response_model=KnowledgeSearchResponse, tags=["knowledge"])
async def query_by_type(
    unit_type: str,
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
):
    """
    Query knowledge units by type.

    Returns all units of a specific type (chapter, formula, data_point, chart_rule, evidence).
    """
    service = get_knowledge_service()
    results = service.query_by_type(
        unit_type=unit_type,
        limit=limit,
    )

    return KnowledgeSearchResponse(
        results=results,
        total=len(results),
    )


@router.get("/knowledge/trace/{unit_id}", tags=["knowledge"])
async def get_trace(unit_id: str):
    """
    Get trace chain for a knowledge unit.

    Returns the traceability chain showing the source of the unit.
    """
    service = get_knowledge_service()
    trace = service.get_trace(unit_id)

    if not trace:
        raise HTTPException(status_code=404, detail=f"Knowledge unit not found: {unit_id}")

    return {"unit_id": unit_id, "trace": trace}


@router.get("/knowledge/dependencies/{unit_id}", tags=["knowledge"])
async def get_dependencies(unit_id: str):
    """
    Get dependencies for a knowledge unit.

    Returns a list of unit IDs that this unit depends on.
    """
    service = get_knowledge_service()
    unit = service.get_unit(unit_id)

    if not unit:
        raise HTTPException(status_code=404, detail=f"Knowledge unit not found: {unit_id}")

    deps = service.get_dependencies(unit_id)

    return {"unit_id": unit_id, "dependencies": deps}
