"""
Pipeline WebSocket Event Bus — stub implementation (completed by Plan 03).

Architecture (PIPE-05):
  - PipelineEventBus buffers the last 100 events per pipeline with monotonic
    sequence numbers so reconnecting clients receive only missed events.
  - WebSocket.ping() heartbeats fire every 30 seconds during long-running pipelines.
  - Stub: replaced by real PipelineEventBus in Plan 03.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class PipelineEvent:
    """Pipeline lifecycle event emitted by PipelineExecutor."""
    event_type: str          # pipeline_started, step_started, step_completed, etc.
    pipeline_id: str
    sequence: int = 0        # set by PipelineEventBus
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)


# Stub: replaced by PipelineEventBus in Plan 03
async def broadcast_pipeline_event(event: PipelineEvent) -> None:
    """Broadcast a pipeline event to all subscribers. Stub — logs only."""
    logger.info(
        f"[PIPELINE_EVENT_STUB] {event.event_type} "
        f"pipeline={event.pipeline_id} seq={event.sequence}"
    )


def get_event_bus():
    """Placeholder — returns None until Plan 03 installs real bus."""
    return None
