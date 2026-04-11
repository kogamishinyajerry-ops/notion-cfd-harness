"""
Visualization Endpoints

REST API endpoints for ParaView Web session lifecycle management.
Provides session launch, status monitoring, heartbeat, and shutdown.
"""

import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from api_server.config import DATA_DIR, REPORTS_DIR
from api_server.models import ParaViewWebSession
from api_server.services.trame_session_manager import (
    TrameSessionError,
    get_trame_session_manager,
)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class VisualizationLaunchRequest(BaseModel):
    """Request to launch a new ParaView Web session."""
    job_id: str = Field(..., description="Associated job ID")
    case_dir: str = Field(..., description="Path to OpenFOAM case directory")
    port: Optional[int] = Field(default=None, description="Preferred port (auto-allocated if not specified)")


class VisualizationLaunchResponse(BaseModel):
    """Response after launching a ParaView Web session."""
    session_id: str
    session_url: str  # ws://host:port/ws
    auth_key: str
    port: int
    job_id: str


class VisualizationStatusResponse(BaseModel):
    """Response for session status query."""
    session_id: str
    job_id: Optional[str]
    status: str
    port: int
    case_dir: str
    created_at: datetime
    last_activity: datetime


# =============================================================================
# Helpers
# =============================================================================


def _validate_case_dir(case_dir: str) -> None:
    """
    Validate that case_dir is an absolute path, exists, and is under an allowed root.

    Args:
        case_dir: The case directory path to validate

    Raises:
        HTTPException: 400 if validation fails
    """
    # Must be absolute
    if not os.path.isabs(case_dir):
        raise HTTPException(
            status_code=400,
            detail="case_dir must be an absolute path"
        )

    # Must exist
    if not os.path.exists(case_dir):
        raise HTTPException(
            status_code=400,
            detail=f"case_dir does not exist: {case_dir}"
        )

    if not os.path.isdir(case_dir):
        raise HTTPException(
            status_code=400,
            detail=f"case_dir is not a directory: {case_dir}"
        )

    # Must be under an allowed root (DATA_DIR or REPORTS_DIR)
    case_dir_resolved = os.path.realpath(case_dir)
    allowed_roots = [
        os.path.realpath(DATA_DIR),
        os.path.realpath(REPORTS_DIR),
    ]

    # Also allow any subdirectory of the project root that contains polyMesh or case.foam
    # (for flexibility during development)
    has_mesh = os.path.isdir(os.path.join(case_dir, "polyMesh"))
    has_foam = os.path.isfile(os.path.join(case_dir, "case.foam"))

    is_under_allowed_root = any(
        case_dir_resolved.startswith(root) for root in allowed_roots
    )

    if not is_under_allowed_root and not (has_mesh or has_foam):
        raise HTTPException(
            status_code=400,
            detail=(
                f"case_dir must be under an allowed root ({DATA_DIR} or {REPORTS_DIR}) "
                f"or contain polyMesh/case.foam"
            )
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/visualization/launch",
    response_model=VisualizationLaunchResponse,
    status_code=201,
    tags=["visualization"],
)
async def launch_visualization_session(request: VisualizationLaunchRequest):
    """
    Launch a new ParaView Web session.

    Creates a Docker sidecar container running ParaView Web, scoped to the
    specified case directory. Returns session info including WebSocket URL.
    """
    # Validate case_dir
    _validate_case_dir(request.case_dir)

    # Generate session ID
    session_id = f"PVW-{uuid.uuid4().hex[:8].upper()}"

    # Get manager and launch session
    manager = get_trame_session_manager()

    try:
        session = await manager.launch_session(
            session_id=session_id,
            case_dir=request.case_dir,
            port=request.port,
            job_id=request.job_id,
        )
    except TrameSessionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to launch trame session: {str(e)}"
        )

    # Build session URL
    session_url = f"http://localhost:{session.port}"

    return VisualizationLaunchResponse(
        session_id=session.session_id,
        session_url=session_url,
        auth_key=session.auth_key,
        port=session.port,
        job_id=session.job_id or request.job_id,
    )


@router.get(
    "/visualization/{session_id}",
    response_model=VisualizationStatusResponse,
    tags=["visualization"],
)
async def get_visualization_session(
    session_id: str = Path(..., description="Session identifier"),
):
    """
    Get ParaView Web session status.

    Returns current status, timestamps, and configuration for the session.
    Raises 404 if session not found.
    """
    manager = get_trame_session_manager()
    session = manager.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )

    return VisualizationStatusResponse(
        session_id=session.session_id,
        job_id=session.job_id,
        status=session.status,
        port=session.port,
        case_dir=session.case_dir,
        created_at=session.created_at,
        last_activity=session.last_activity,
    )


@router.post(
    "/visualization/{session_id}/activity",
    tags=["visualization"],
)
async def update_session_activity(
    session_id: str = Path(..., description="Session identifier"),
):
    """
    Heartbeat endpoint to update session last_activity timestamp.

    Clients should call this endpoint periodically while the session is active
    to prevent idle timeout shutdown.
    """
    manager = get_trame_session_manager()
    session = manager.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )

    manager.update_activity(session_id)
    return {"status": "ok"}


@router.delete(
    "/visualization/{session_id}",
    tags=["visualization"],
)
async def shutdown_visualization_session(
    session_id: str = Path(..., description="Session identifier"),
):
    """
    Shutdown a ParaView Web session.

    Stops the Docker container and frees the session resources.
    """
    manager = get_trame_session_manager()
    session = manager.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )

    await manager.shutdown_session(session_id)
    return {"session_id": session_id, "status": "stopped"}
