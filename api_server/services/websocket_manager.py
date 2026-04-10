"""
WebSocket Connection Manager

Manages WebSocket connections for real-time job progress updates.
Supports multiple subscribers per job and handles connection lifecycle.
"""

import asyncio
import logging
from typing import Dict, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for job progress streaming.

    Maintains a registry of connections per job_id, allowing multiple
    clients to subscribe to the same job's progress updates.
    """

    def __init__(self):
        """Initialize the WebSocket manager."""
        # job_id -> set of WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, job_id: str) -> None:
        """
        Register a new WebSocket connection for a job.

        Args:
            websocket: The WebSocket connection
            job_id: The job ID to subscribe to
        """
        await websocket.accept()
        async with self._lock:
            if job_id not in self._connections:
                self._connections[job_id] = set()
            self._connections[job_id].add(websocket)
        logger.info(f"WebSocket connected: job_id={job_id}, total_subscribers={len(self._connections[job_id])}")

    async def disconnect(self, websocket: WebSocket, job_id: str) -> None:
        """
        Unregister a WebSocket connection from a job.

        Args:
            websocket: The WebSocket connection
            job_id: The job ID to unsubscribe from
        """
        async with self._lock:
            if job_id in self._connections:
                self._connections[job_id].discard(websocket)
                if not self._connections[job_id]:
                    del self._connections[job_id]
        logger.info(f"WebSocket disconnected: job_id={job_id}")

    async def broadcast(self, job_id: str, message: dict) -> None:
        """
        Broadcast a message to all subscribers of a job.

        Args:
            job_id: The job ID to broadcast to
            message: The message dict to send
        """
        async with self._lock:
            connections = self._connections.get(job_id, set()).copy()

        if not connections:
            return

        # Send to all connections, removing any that fail
        failed_connections = set()
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                failed_connections.add(websocket)

        # Clean up failed connections
        if failed_connections:
            async with self._lock:
                if job_id in self._connections:
                    self._connections[job_id] -= failed_connections

    def get_subscriber_count(self, job_id: str) -> int:
        """
        Get the number of subscribers for a job.

        Args:
            job_id: The job ID

        Returns:
            Number of active WebSocket connections
        """
        return len(self._connections.get(job_id, set()))

    def get_total_connections(self) -> int:
        """
        Get total number of active WebSocket connections.

        Returns:
            Total connection count across all jobs
        """
        return sum(len(conns) for conns in self._connections.values())


# Global WebSocket manager instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the global WebSocket manager instance."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
