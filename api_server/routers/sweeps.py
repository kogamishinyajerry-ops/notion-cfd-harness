"""
Sweep Management Endpoints

REST API endpoints for parametric sweep CRUD and control (PIPE-10).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Query

from api_server.models import (
    SweepCreate,
    SweepListResponse,
    SweepResponse,
    SweepCaseResponse,
    SweepStatus,
)
from api_server.services.pipeline_db import get_sweep_db_service, get_pipeline_db_service
from api_server.services.sweep_runner import start_sweep_runner, cancel_sweep_runner, get_sweep_runner

router = APIRouter()


def get_sweep_service():
    return get_sweep_db_service()


@router.post("/sweeps", response_model=SweepResponse, status_code=201, tags=["sweeps"])
async def create_sweep(spec: SweepCreate):
    """
    Create a new parametric sweep.

    Validates that base_pipeline_id exists and param_grid is non-empty.
    Pre-generates all SweepCase entries via itertools.product.
    Does NOT start execution — call POST /sweeps/{id}/start separately.
    """
    service = get_sweep_service()

    # Validate base pipeline exists
    pipeline_db = get_pipeline_db_service()
    base_pipeline = pipeline_db.get_pipeline(spec.base_pipeline_id)
    if not base_pipeline:
        raise HTTPException(status_code=404, detail=f"Base pipeline not found: {spec.base_pipeline_id}")

    # Validate param_grid is non-empty
    if not spec.param_grid:
        raise HTTPException(status_code=400, detail="param_grid cannot be empty")

    # Validate all param lists are non-empty
    for param_name, values in spec.param_grid.items():
        if not values:
            raise HTTPException(
                status_code=400,
                detail=f"Parameter '{param_name}' has no values. Provide at least one value per parameter."
            )

    # Compute total combinations
    total_combinations = 1
    for values in spec.param_grid.values():
        total_combinations *= len(values)

    if total_combinations > 1000:
        raise HTTPException(
            status_code=400,
            detail=f"Sweep has {total_combinations} combinations (max 1000). Reduce parameter values."
        )

    sweep = service.create_sweep(spec, total_combinations)
    return sweep


@router.get("/sweeps", response_model=SweepListResponse, tags=["sweeps"])
async def list_sweeps(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """
    List all sweeps, newest first.
    """
    service = get_sweep_service()
    all_sweeps = service.list_sweeps()
    total = len(all_sweeps)
    paginated = all_sweeps[offset:offset + limit]
    return SweepListResponse(sweeps=paginated, total=total)


@router.get("/sweeps/{sweep_id}", response_model=SweepResponse, tags=["sweeps"])
async def get_sweep(sweep_id: str):
    """
    Get a sweep by ID with aggregate status.
    """
    service = get_sweep_service()
    sweep = service.get_sweep(sweep_id)
    if not sweep:
        raise HTTPException(status_code=404, detail=f"Sweep not found: {sweep_id}")
    return sweep


@router.get("/sweeps/{sweep_id}/cases", response_model=List[SweepCaseResponse], tags=["sweeps"])
async def get_sweep_cases(sweep_id: str):
    """
    Get all combination cases for a sweep.
    """
    service = get_sweep_service()
    sweep = service.get_sweep(sweep_id)
    if not sweep:
        raise HTTPException(status_code=404, detail=f"Sweep not found: {sweep_id}")
    return service.get_sweep_cases(sweep_id)


@router.delete("/sweeps/{sweep_id}", status_code=204, tags=["sweeps"])
async def delete_sweep(sweep_id: str):
    """
    Delete a sweep and all its cases.
    Cancels any running sweep runner first.
    """
    service = get_sweep_service()
    sweep = service.get_sweep(sweep_id)
    if not sweep:
        raise HTTPException(status_code=404, detail=f"Sweep not found: {sweep_id}")

    # Cancel runner if active
    runner = get_sweep_runner(sweep_id)
    if runner:
        runner.cancel()

    service.delete_sweep(sweep_id)
    return None


@router.post("/sweeps/{sweep_id}/start", tags=["sweeps"])
async def start_sweep(sweep_id: str):
    """
    Start sweep execution.

    Validates sweep is PENDING and starts SweepRunner in background thread.
    Returns immediately (non-blocking).
    """
    service = get_sweep_service()
    sweep = service.get_sweep(sweep_id)
    if not sweep:
        raise HTTPException(status_code=404, detail=f"Sweep not found: {sweep_id}")

    if sweep.status != SweepStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start sweep in state '{sweep.status}'. Only PENDING sweeps can be started."
        )

    try:
        start_sweep_runner(sweep_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"status": "started", "sweep_id": sweep_id}


@router.post("/sweeps/{sweep_id}/cancel", tags=["sweeps"])
async def cancel_sweep(sweep_id: str):
    """
    Cancel a running sweep.

    Signals the SweepRunner to stop. Already-running child pipelines
    continue until they finish their current step; no new cases start.
    """
    service = get_sweep_service()
    sweep = service.get_sweep(sweep_id)
    if not sweep:
        raise HTTPException(status_code=404, detail=f"Sweep not found: {sweep_id}")

    cancelled = cancel_sweep_runner(sweep_id)
    if not cancelled:
        # Runner not registered but sweep might be stuck in RUNNING — just update status
        if sweep.status == SweepStatus.RUNNING:
            service.update_sweep_status(sweep_id, SweepStatus.CANCELLED)

    return {"status": "cancelling", "sweep_id": sweep_id}


@router.get("/sweep-cases", response_model=List[SweepCaseResponse], tags=["sweeps"])
async def list_all_cases():
    """
    List all completed cases across all sweeps.
    Used by comparison UI for case selection (PIPE-12).
    """
    service = get_sweep_service()
    return service.get_all_completed_cases()

