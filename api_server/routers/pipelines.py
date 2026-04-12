"""
Pipeline Management Endpoints

REST API endpoints for pipeline CRUD operations and DAG management.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from api_server.models import (
    PipelineCreate,
    PipelineListResponse,
    PipelineResponse,
    PipelineStatus,
    PipelineUpdate,
)
from api_server.services import get_pipeline_db_service

router = APIRouter()

_pipeline_service: Optional = None


def get_pipeline_service():
    """Get or create pipeline service instance."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = get_pipeline_db_service()
    return _pipeline_service


@router.post("/pipelines", response_model=PipelineResponse, status_code=201, tags=["pipelines"])
async def create_pipeline(spec: PipelineCreate):
    """
    Create a new pipeline with N steps and branching dependencies.

    Stores the pipeline definition in data/pipelines.db.
    The DAG is stored as an adjacency list in pipeline.config.
    """
    service = get_pipeline_service()
    pipeline = service.create_pipeline(spec)
    return pipeline


@router.get("/pipelines", response_model=PipelineListResponse, tags=["pipelines"])
async def list_pipelines(
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
):
    """
    List all pipelines.

    Returns a paginated list sorted by creation date (newest first).
    """
    service = get_pipeline_service()
    all_pipelines = service.list_pipelines()
    total = len(all_pipelines)
    paginated = all_pipelines[offset:offset + limit]
    return PipelineListResponse(pipelines=paginated, total=total)


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse, tags=["pipelines"])
async def get_pipeline(pipeline_id: str):
    """
    Get a pipeline by ID with its DAG adjacency list and step definitions.

    Raises 404 if not found.
    """
    service = get_pipeline_service()
    pipeline = service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
    return pipeline


@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse, tags=["pipelines"])
async def update_pipeline(pipeline_id: str, update: PipelineUpdate):
    """
    Update a PENDING pipeline's name, description, or config.

    Only pipelines with status=PENDING can be updated.
    Raises 404 if not found, 400 if pipeline is not PENDING.
    """
    service = get_pipeline_service()

    if update.status is not None and update.status != PipelineStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail="Can only update status to PENDING via this endpoint"
        )

    try:
        pipeline = service.update_pipeline(pipeline_id, update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
    return pipeline


@router.delete("/pipelines/{pipeline_id}", status_code=204, tags=["pipelines"])
async def delete_pipeline(
    pipeline_id: str,
    cancel: bool = Query(default=False, description="If true, cancel running pipeline before deletion"),
):
    """
    Delete a pipeline and all its persisted state.

    If cancel=true, cancels a running pipeline first and stops its Docker containers.
    Raises 404 if not found.
    """
    from api_server.services.cleanup_handler import get_cleanup_handler

    service = get_pipeline_service()
    pipeline = service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    if cancel:
        pipeline_status = pipeline.status.value if hasattr(pipeline.status, 'value') else pipeline.status
        running_statuses = ("running", "monitoring", "visualizing", "reporting")
        if pipeline_status in running_statuses:
            cleanup = get_cleanup_handler()
            await cleanup.cancel_and_cleanup(pipeline_id)

    deleted = service.delete_pipeline(pipeline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
    return None


# =========================================================================
# Pipeline Control Endpoints (PIPE-02, PIPE-06)
# =========================================================================

@router.post("/pipelines/{pipeline_id}/start", tags=["pipelines"])
async def start_pipeline(pipeline_id: str, request: Request):
    """
    Start pipeline execution.

    Transitions pipeline from PENDING -> RUNNING and launches PipelineExecutor
    in a dedicated background thread.

    Returns 409 if pipeline is already running.
    Returns 404 if pipeline not found.
    """
    from api_server.services.pipeline_executor import start_pipeline_executor
    import asyncio

    service = get_pipeline_service()
    pipeline = service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    pipeline_status = pipeline.status.value if hasattr(pipeline.status, 'value') else pipeline.status
    if pipeline_status not in ("pending",):
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline is already in state '{pipeline_status}'. Only PENDING pipelines can be started."
        )

    if not pipeline.steps:
        raise HTTPException(status_code=400, detail="Pipeline has no steps to execute")

    try:
        loop = asyncio.get_running_loop()
        start_pipeline_executor(pipeline_id, loop)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"status": "started", "pipeline_id": pipeline_id}


@router.post("/pipelines/{pipeline_id}/cancel", tags=["pipelines"])
async def cancel_pipeline(pipeline_id: str):
    """
    Cancel a running pipeline.

    Signals PipelineExecutor to cancel, stops Docker containers started by
    pipeline steps (solver containers only — trame viewer containers are
    managed by TrameSessionManager and are NOT stopped).

    Gives running steps 10 seconds to finish before force-killing containers.
    COMPLETED step outputs are preserved.
    """
    from api_server.services.cleanup_handler import get_cleanup_handler

    service = get_pipeline_service()
    pipeline = service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    cleanup = get_cleanup_handler()
    await cleanup.cancel_and_cleanup(pipeline_id)

    return {"status": "cancelling", "pipeline_id": pipeline_id}


@router.get("/pipelines/{pipeline_id}/steps", response_model=List[dict], tags=["pipelines"])
async def get_pipeline_steps(pipeline_id: str):
    """
    Get all steps for a pipeline with their current statuses.

    Returns a list of step objects with: step_id, step_type, step_order, depends_on, params, status.
    """
    service = get_pipeline_service()
    pipeline = service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    steps = []
    for step in pipeline.steps:
        step_dict = {
            "id": step.step_id,
            "pipeline_id": pipeline_id,
            "step_type": step.step_type.value if hasattr(step.step_type, 'value') else step.step_type,
            "step_order": step.step_order,
            "depends_on": step.depends_on,
            "params": step.params,
            "status": step.status.value if hasattr(step.status, 'value') else step.status,
        }
        steps.append(step_dict)
    return steps


@router.get("/pipelines/{pipeline_id}/events", response_model=List[dict], tags=["pipelines"])
async def get_pipeline_events(pipeline_id: str):
    """
    Get buffered pipeline events (last 100).

    Returns events with sequence numbers for reconnect replay.
    """
    from api_server.services.pipeline_websocket import get_event_bus

    service = get_pipeline_service()
    pipeline = service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    bus = get_event_bus()
    events = bus.get_buffer(pipeline_id)
    return [e.to_dict() for e in events]


@router.post("/pipelines/{pipeline_id}/pause", tags=["pipelines"])
async def pause_pipeline(pipeline_id: str):
    """
    Pause a running pipeline.

    Signals the PipelineExecutor to pause after the current step completes.
    Transitions pipeline status to PAUSED.
    """
    from api_server.services.pipeline_executor import get_pipeline_executor

    service = get_pipeline_service()
    pipeline = service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    pipeline_status = pipeline.status.value if hasattr(pipeline.status, 'value') else pipeline.status
    running_statuses = ("running", "monitoring", "visualizing", "reporting")
    if pipeline_status not in running_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot pause pipeline in state '{pipeline_status}'. Only RUNNING pipelines can be paused."
        )

    executor = get_pipeline_executor(pipeline_id)
    if executor:
        executor.pause()

    service.update_pipeline_status(pipeline_id, PipelineStatus.PAUSED)

    return {"status": "paused", "pipeline_id": pipeline_id}


@router.post("/pipelines/{pipeline_id}/resume", tags=["pipelines"])
async def resume_pipeline(pipeline_id: str):
    """
    Resume a paused pipeline.

    Signals the PipelineExecutor to continue. Transitions pipeline status back to RUNNING.
    """
    from api_server.services.pipeline_executor import get_pipeline_executor

    service = get_pipeline_service()
    pipeline = service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    pipeline_status = pipeline.status.value if hasattr(pipeline.status, 'value') else pipeline.status
    if pipeline_status != "paused":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot resume pipeline in state '{pipeline_status}'. Only PAUSED pipelines can be resumed."
        )

    executor = get_pipeline_executor(pipeline_id)
    if executor:
        executor.resume()

    service.update_pipeline_status(pipeline_id, PipelineStatus.RUNNING)

    return {"status": "resumed", "pipeline_id": pipeline_id}

