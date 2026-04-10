"""
WebSocket Router

Real-time job progress streaming via WebSocket connections.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from api_server.auth.rbac_middleware import get_current_user
from api_server.models import UserInfo
from api_server.services.job_service import JobService, get_job_service
from api_server.services.websocket_manager import get_websocket_manager, WebSocketManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(
    websocket: WebSocket,
    job_id: str,
    token: Optional[str] = Query(default=None, description="JWT access token for authentication"),
):
    """
    WebSocket endpoint for real-time job progress updates.

    Connects to the job's progress stream. Messages are sent as JSON:

    - {"type": "progress", "progress": float, "status": str}
    - {"type": "completion", "status": str, "result": dict}
    - {"type": "error", "error": str}
    - {"type": "status", "job": JobResponse}

    Args:
        websocket: The WebSocket connection
        job_id: The job ID to subscribe to
        token: Optional JWT token for authentication
    """
    manager = get_websocket_manager()
    job_service = get_job_service()

    # Verify job exists
    job = job_service.get_job(job_id)
    if not job:
        await websocket.close(code=4004, reason=f"Job not found: {job_id}")
        return

    # Optional: Verify JWT token if provided
    # Note: In production, you'd want to validate the token
    # For now, we allow anonymous access to job updates

    # Register connection
    await manager.connect(websocket, job_id)

    try:
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "job": {
                "job_id": job.job_id,
                "case_id": job.case_id,
                "job_type": job.job_type,
                "status": job.status.value,
                "progress": job.progress,
                "submitted_at": job.submitted_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
        })

        # Keep connection alive and handle incoming messages
        while True:
            # Wait for messages (ping/pong or commands)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: job_id={job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: job_id={job_id}, error={e}")
    finally:
        await manager.disconnect(websocket, job_id)


@router.get("/ws/jobs/{job_id}/subscribers", tags=["websocket"])
async def get_job_subscriber_count(
    job_id: str,
    current_user: UserInfo = Depends(get_current_user),
) -> dict:
    """
    Get the number of active WebSocket subscribers for a job.

    Args:
        job_id: The job ID
        current_user: Authenticated user

    Returns:
        Subscriber count information
    """
    manager = get_websocket_manager()
    count = manager.get_subscriber_count(job_id)
    return {
        "job_id": job_id,
        "subscriber_count": count,
    }


@router.get("/ws/status", tags=["websocket"])
async def get_websocket_status(
    current_user: UserInfo = Depends(get_current_user),
) -> dict:
    """
    Get overall WebSocket connection status.

    Returns:
        WebSocket connection statistics
    """
    manager = get_websocket_manager()
    return {
        "total_connections": manager.get_total_connections(),
    }
