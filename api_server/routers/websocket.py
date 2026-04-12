"""
WebSocket Router

Real-time job progress streaming via WebSocket connections.
"""

import asyncio
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


# =========================================================================
# Pipeline WebSocket Endpoint (PIPE-05)
# =========================================================================
HEARTBEAT_INTERVAL = 30  # seconds (PIPE-05: WebSocket.ping() every 30s)


@router.websocket("/ws/pipelines/{pipeline_id}")
async def pipeline_websocket(
    websocket: WebSocket,
    pipeline_id: str,
    last_seq: int = Query(default=0, description="Last received sequence number for replay"),
):
    """
    Real-time pipeline event stream with connection resilience.

    Protocol:
    1. Client connects to /ws/pipelines/{pipeline_id}?last_seq=N
    2. Server validates pipeline_id exists in DB; closes with 4004 if not found
    3. Server replays all buffered events with sequence > last_seq
    4. Server streams new events as they are published
    5. Server sends WebSocket.ping() every 30 seconds
    6. On disconnect, server unregisters subscriber queue

    Event shape:
    {
      "type": "pipeline_started" | "step_started" | "step_completed" | "step_failed" |
              "pipeline_completed" | "pipeline_failed" | "pipeline_cancelled",
      "pipeline_id": str,
      "sequence": int,
      "timestamp": str,
      "payload": dict
    }
    """
    from api_server.services.pipeline_db import get_pipeline_db_service
    from api_server.services.pipeline_websocket import get_event_bus

    # Validate pipeline exists before accepting connection
    db = get_pipeline_db_service()
    pipeline = db.get_pipeline(pipeline_id)
    if pipeline is None:
        await websocket.close(code=4004, reason=f"Pipeline not found: {pipeline_id}")
        return

    await websocket.accept()
    bus = get_event_bus()

    # Subscribe to new events
    subscriber_queue = bus.subscribe(pipeline_id)

    try:
        # Replay missed events above last_seq
        missed = bus.replay_from(pipeline_id, last_seq=last_seq)
        for event in missed:
            await websocket.send_json(event.to_dict())

        # Stream new events + heartbeat
        while True:
            try:
                # Wait for next event with heartbeat timeout
                event = await asyncio.wait_for(
                    subscriber_queue.get(),
                    timeout=HEARTBEAT_INTERVAL
                )
                await websocket.send_json(event.to_dict())
            except asyncio.TimeoutError:
                # Send heartbeat ping (PIPE-05: every 30s)
                await websocket.send_bytes(b"")   # send_bytes keeps connection alive
                try:
                    await websocket.send_text('{"type":"ping"}')
                except Exception:
                    break  # connection lost
            except Exception as e:
                logger.warning(f"Pipeline WS error for {pipeline_id}: {e}")
                break

    except Exception as e:
        logger.warning(f"Pipeline WebSocket disconnected for {pipeline_id}: {e}")
    finally:
        bus.unsubscribe(pipeline_id, subscriber_queue)
        logger.info(f"Pipeline WebSocket closed: {pipeline_id}")
