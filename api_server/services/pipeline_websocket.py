"""
Pipeline WebSocket Event Bus.

Implements PIPE-05: sequence-numbered events, 100-event ring buffer per pipeline,
broadcast to all subscribers, reconnect replay above last-received sequence.
"""
import asyncio
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

BUFFER_SIZE = 100  # events buffered per pipeline (PIPE-05)


@dataclass
class PipelineEvent:
    """Pipeline lifecycle event emitted by PipelineExecutor."""
    event_type: str      # pipeline_started | step_started | step_completed |
                         # step_failed | pipeline_completed | pipeline_failed | pipeline_cancelled
    pipeline_id: str
    sequence: int = 0    # assigned by PipelineEventBus.publish()
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type,
            "pipeline_id": self.pipeline_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


class PipelineEventBus:
    """
    Thread-safe event bus for pipeline events.

    - Global monotonic sequence counter across all pipelines
    - Per-pipeline ring buffer of last BUFFER_SIZE events
    - Per-pipeline set of subscriber asyncio.Queues
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._sequence = 0
        # pipeline_id -> deque of PipelineEvent (max BUFFER_SIZE)
        self._buffers: Dict[str, Deque[PipelineEvent]] = {}
        # pipeline_id -> set of asyncio.Queue
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def publish(self, event: PipelineEvent) -> PipelineEvent:
        """
        Assign sequence number, buffer event, notify subscribers.
        Returns the event with sequence number set.
        Thread-safe; called from background executor thread via asyncio.run_coroutine_threadsafe.
        """
        with self._lock:
            event.sequence = self._next_sequence()

            # Buffer
            pid = event.pipeline_id
            if pid not in self._buffers:
                self._buffers[pid] = deque(maxlen=BUFFER_SIZE)
            self._buffers[pid].append(event)

            # Collect subscriber queues
            queues = list(self._subscribers.get(pid, set()))

        # Put into subscriber queues (outside lock to avoid deadlock)
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    f"Subscriber queue full for pipeline {pid}; "
                    f"dropping event {event.sequence}"
                )

        logger.debug(
            f"Published event {event.event_type} seq={event.sequence} pipeline={pid}"
        )
        return event

    def get_buffer(self, pipeline_id: str) -> List[PipelineEvent]:
        """Return buffered events for pipeline, oldest first."""
        with self._lock:
            return list(self._buffers.get(pipeline_id, deque()))

    def replay_from(self, pipeline_id: str, last_seq: int) -> List[PipelineEvent]:
        """Return events with sequence > last_seq for reconnecting clients."""
        with self._lock:
            buf = self._buffers.get(pipeline_id, deque())
            return [e for e in buf if e.sequence > last_seq]

    def subscribe(self, pipeline_id: str) -> asyncio.Queue:
        """Register a subscriber queue for pipeline events."""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            if pipeline_id not in self._subscribers:
                self._subscribers[pipeline_id] = set()
            self._subscribers[pipeline_id].add(q)
        return q

    def unsubscribe(self, pipeline_id: str, q: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        with self._lock:
            subs = self._subscribers.get(pipeline_id)
            if subs:
                subs.discard(q)
                if not subs:
                    del self._subscribers[pipeline_id]

    def subscriber_count(self, pipeline_id: str) -> int:
        with self._lock:
            return len(self._subscribers.get(pipeline_id, set()))


# --- Module-level singleton ---

_event_bus: Optional[PipelineEventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> PipelineEventBus:
    """Get or create the global PipelineEventBus singleton."""
    global _event_bus
    with _bus_lock:
        if _event_bus is None:
            _event_bus = PipelineEventBus()
    return _event_bus


async def broadcast_pipeline_event(event: PipelineEvent) -> None:
    """
    Publish event to the global PipelineEventBus.
    Called from PipelineExecutor (background thread) via await.
    The actual publish() is synchronous (thread-safe); this async wrapper
    exists for consistency with PipelineExecutor's async _emit() interface.
    """
    bus = get_event_bus()
    bus.publish(event)
