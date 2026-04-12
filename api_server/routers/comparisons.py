"""
Cross-Case Comparison REST Endpoints (PIPE-11).

GET  /comparisons           — list all comparisons
POST /comparisons           — create a new comparison
GET  /comparisons/{id}      — get comparison by ID
POST /comparisons/{id}/delta — trigger delta field computation
POST /comparisons/{id}/delta-session — launch trame session on delta VTU
GET  /comparisons/delta/{filename} — serve computed delta VTU file
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api_server.models import ComparisonCreate, ComparisonResponse, ComparisonListResponse
from api_server.services.comparison_service import ComparisonService
from api_server.services.pipeline_db import get_sweep_db_service

router = APIRouter()

_DELTA_OUTPUT_DIR = Path("/tmp/comparisons")


def _get_comparison_service():
    sweep_db = get_sweep_db_service()
    return ComparisonService(sweep_db, _DELTA_OUTPUT_DIR)


@router.get("/comparisons", response_model=ComparisonListResponse, tags=["comparisons"])
async def list_comparisons():
    """List all saved comparison results."""
    service = _get_comparison_service()
    return ComparisonListResponse(comparisons=service.list_comparisons())


@router.post("/comparisons", response_model=ComparisonResponse, status_code=201, tags=["comparisons"])
async def create_comparison(spec: ComparisonCreate):
    """
    Create a new cross-case comparison.

    Parses convergence history from solver logs, checks provenance mismatches,
    optionally computes delta field (CaseB - CaseA), and builds metrics table.
    """
    service = _get_comparison_service()
    try:
        return service.create_comparison(spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/comparisons/{comparison_id}", response_model=ComparisonResponse, tags=["comparisons"])
async def get_comparison(comparison_id: str):
    """Get a comparison result by ID."""
    service = _get_comparison_service()
    result = service.get_comparison(comparison_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Comparison not found: {comparison_id}")
    return result


@router.post("/comparisons/{comparison_id}/delta", response_model=ComparisonResponse, tags=["comparisons"])
async def compute_delta_field(comparison_id: str, field_name: str = "p"):
    """
    Trigger delta field computation for an existing comparison.

    Uses the comparison's delta_case_a_id and delta_case_b_id to compute
    CaseB.{field} - CaseA.{field} via pvpython in ParaView container.
    Returns updated ComparisonResponse with delta_vtu_url set.
    """
    service = _get_comparison_service()
    comparison = service.get_comparison(comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail=f"Comparison not found: {comparison_id}")
    if not comparison.delta_case_a_id or not comparison.delta_case_b_id:
        raise HTTPException(status_code=400, detail="Comparison has no delta case pair set")

    ok, err, vtu_path = service.compute_delta(
        comparison.delta_case_a_id, comparison.delta_case_b_id, field_name
    )
    if not ok:
        raise HTTPException(status_code=500, detail=f"Delta computation failed: {err}")

    # Update comparison with delta VTU URL
    comparison.delta_vtu_url = f"/comparisons/delta/{Path(vtu_path).name}"
    comparison.delta_field_name = field_name
    return comparison


@router.post("/comparisons/{comparison_id}/delta-session", tags=["comparisons"])
async def launch_delta_trame_session(comparison_id: str, field_name: str = "p"):
    """
    Launch a trame session on a computed delta VTU file and return the trame URL.

    This endpoint:
    1. Calls compute_delta if no delta VTU exists yet
    2. Launches a trame server on the delta .vtu file
    3. Returns {trame_url} for use as iframe src in DeltaFieldViewer
    """
    service = _get_comparison_service()
    comparison = service.get_comparison(comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail=f"Comparison not found: {comparison_id}")

    # Ensure delta VTU exists
    vtu_path = None
    if comparison.delta_vtu_url:
        # Extract path from stored URL
        filename = Path(comparison.delta_vtu_url).name
        vtu_path = _DELTA_OUTPUT_DIR / filename

    if not vtu_path or not vtu_path.exists():
        if not comparison.delta_case_a_id or not comparison.delta_case_b_id:
            raise HTTPException(status_code=400, detail="Comparison has no delta case pair set")
        ok, err, computed_path = service.compute_delta(
            comparison.delta_case_a_id, comparison.delta_case_b_id, field_name
        )
        if not ok:
            raise HTTPException(status_code=500, detail=f"Delta computation failed: {err}")
        vtu_path = Path(computed_path)

    # Launch trame session on the VTU
    port = 9000 + hash(str(vtu_path)) % 10000
    session_id = uuid.uuid4().hex[:8]
    trame_script = f"""\
from trame.app import get_server
from trame.ui.vtk import *
from paraview.simple import *
import os

server = get_server(name="{session_id}")
state = server.state

# Load delta VTU
reader = XMLUnstructuredGridReader(FileName="{vtu_path}")
rep = Show(reader)
Render()
view = GetActiveViewOrCreate('RenderView')
view.ResetCamera()

ui = VtkUi(server, view)
server.start(port={port})
"""
    _DELTA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trame_script_path = _DELTA_OUTPUT_DIR / f"trame_session_{session_id}.py"
    trame_script_path.write_text(trame_script)

    trame_url = f"http://localhost:{port}/trame"

    # Spawn trame in background (fire-and-forget for the HTTP response)
    try:
        subprocess.Popen(
            ["python3", str(trame_script_path)],
            cwd=str(_DELTA_OUTPUT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch trame session: {e}")

    return {"trame_url": trame_url, "session_id": session_id}


@router.get("/comparisons/delta/{filename}", tags=["comparisons"])
async def serve_delta_vtu(filename: str):
    """Serve a computed delta field VTU file."""
    vtu_path = _DELTA_OUTPUT_DIR / filename
    if not vtu_path.exists():
        raise HTTPException(status_code=404, detail=f"Delta file not found: {filename}")
    return FileResponse(
        path=str(vtu_path),
        media_type="application/octet-stream",
        filename=f"delta_{filename}",
    )
