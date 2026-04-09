#!/usr/bin/env python3
"""
P5-06: Request Tracing - Lightweight distributed tracing

Provides:
- Span: Operation tracing with start/end/duration
- Parent/Child span relationships
- JSON export
- Integration with correlation_id
"""

from __future__ import annotations

import contextvars
import json
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from functools import wraps

from knowledge_compiler.observability.logging import get_correlation_id


# ============================================================================
# Span Status
# ============================================================================

class SpanStatus(Enum):
    """Span execution status"""
    OK = "ok"
    ERROR = "error"
    CANCELED = "canceled"


# ============================================================================
# Span Context
# ============================================================================

class SpanContext:
    """
    Span context for parent-child relationships

    Uses contextvars for automatic propagation in async contexts.
    """

    def __init__(
        self,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str] = None,
    ):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary"""
        data = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }
        if self.parent_span_id:
            data["parent_span_id"] = self.parent_span_id
        return data


# Context variable for active span
_current_span_ctx: contextvars.ContextVar[Optional["Span"]] = contextvars.ContextVar(
    "current_span",
    default=None,
)


# ============================================================================
# Span
# ============================================================================

@dataclass
class Span:
    """
    A span represents a single operation in a distributed trace

    Attributes:
        name: Operation name
        trace_id: Unique trace identifier
        span_id: Unique span identifier
        parent_span_id: Parent span ID (if any)
        start_time: Span start timestamp
        end_time: Span end timestamp (None until ended)
        status: Span status
        tags: Key-value metadata
        events: Timestamped events
        children: Child spans
    """

    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.OK
    tags: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    children: List["Span"] = field(default_factory=list)
    correlation_id: Optional[str] = None
    _parent_token: Optional[contextvars.Token] = field(default=None, init=False, repr=False)

    def __enter__(self) -> "Span":
        """Enter span context"""
        # Save previous context and set as current span
        self._parent_token = _current_span_ctx.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit span context"""
        self.end()
        if exc_type is not None:
            self.set_error(exc_val)
        # Restore previous context (parent span)
        if self._parent_token is not None:
            _current_span_ctx.reset(self._parent_token)
            self._parent_token = None

    def end(self) -> None:
        """Mark span as ended"""
        if self.end_time is None:
            self.end_time = time.time()

    def set_tag(self, key: str, value: Any) -> None:
        """Set a tag on the span"""
        self.tags[key] = value

    def set_tags(self, tags: Dict[str, Any]) -> None:
        """Set multiple tags"""
        self.tags.update(tags)

    def add_event(
        self,
        name: str,
        attributes: Dict[str, Any] | None = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """Add an event to the span"""
        event = {
            "name": name,
            "timestamp": timestamp or time.time(),
        }
        if attributes:
            event["attributes"] = attributes
        self.events.append(event)

    def set_error(self, error: Exception | str) -> None:
        """Mark span as errored"""
        self.status = SpanStatus.ERROR
        if isinstance(error, Exception):
            self.set_tag("error.type", type(error).__name__)
            self.set_tag("error.message", str(error))
        else:
            self.set_tag("error.message", error)

    def set_canceled(self) -> None:
        """Mark span as canceled"""
        self.status = SpanStatus.CANCELED

    @property
    def duration_ms(self) -> Optional[float]:
        """Get span duration in milliseconds"""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get span duration in seconds"""
        if self.end_time is None:
            return None
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary"""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "tags": self.tags,
            "events": self.events,
            "correlation_id": self.correlation_id,
        }

    def to_json(self) -> str:
        """Convert span to JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    def to_dict_full(self) -> Dict[str, Any]:
        """Convert span to dictionary with children"""
        data = self.to_dict()
        data["children"] = [child.to_dict_full() for child in self.children]
        return data


# ============================================================================
# Tracer
# ============================================================================

class Tracer:
    """
    Tracer for creating and managing spans

    Features:
    - Automatic trace_id/span_id generation
    - Parent-child relationship management
    - Integration with correlation_id
    - Thread-safe
    """

    def __init__(self, service_name: str = "knowledge_compiler"):
        self.service_name = service_name
        self._lock = threading.Lock()
        self._root_spans: List[Span] = []

    def start_span(
        self,
        name: str,
        parent: Optional[Span] = None,
        tags: Dict[str, Any] | None = None,
    ) -> Span:
        """
        Start a new span

        Args:
            name: Span name
            parent: Parent span (if None, uses current span from context)
            tags: Initial tags

        Returns:
            New span instance
        """
        import uuid

        # Get parent from context if not provided
        if parent is None:
            parent = _current_span_ctx.get()

        # Generate IDs
        if parent is None:
            # Root span - new trace
            trace_id = str(uuid.uuid4())[:16]
            parent_span_id = None
        else:
            # Child span - use parent's trace_id
            trace_id = parent.trace_id
            parent_span_id = parent.span_id

        span_id = str(uuid.uuid4())[:8]

        # Create span
        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            correlation_id=get_correlation_id(),
        )

        if tags:
            span.set_tags(tags)

        # Add to parent
        if parent is not None:
            parent.children.append(span)
        else:
            with self._lock:
                self._root_spans.append(span)

        return span

    def span(
        self,
        name: str,
        tags: Dict[str, Any] | None = None,
    ) -> Span:
        """
        Create a span for use as context manager

        Args:
            name: Span name
            tags: Initial tags

        Returns:
            Span instance ready for context manager use
        """
        return self.start_span(name, tags=tags)

    def get_root_spans(self) -> List[Span]:
        """Get all root spans (completed traces)"""
        with self._lock:
            return list(self._root_spans)

    def clear_spans(self) -> None:
        """Clear all stored spans"""
        with self._lock:
            self._root_spans.clear()

    def export_spans(self) -> List[Dict[str, Any]]:
        """Export all spans as dictionaries"""
        return [span.to_dict_full() for span in self.get_root_spans()]

    def export_json(self) -> str:
        """Export all spans as JSON"""
        return json.dumps(self.export_spans(), ensure_ascii=False, default=str, indent=2)


# ============================================================================
# Decorators
# ============================================================================

def trace(
    tracer: Tracer,
    name: Optional[str] = None,
    tags: Dict[str, Any] | None = None,
):
    """
    Decorator to trace function execution

    Args:
        tracer: Tracer instance
        name: Span name (default: function name)
        tags: Initial tags

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_span(span_name, tags=tags):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Get current span and mark as error
                    span = _current_span_ctx.get()
                    if span:
                        span.set_error(e)
                    raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracer.start_span(span_name, tags=tags):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    span = _current_span_ctx.get()
                    if span:
                        span.set_error(e)
                    raise

        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


# ============================================================================
# Global Tracer
# ============================================================================

_global_tracer: Optional[Tracer] = None
_tracer_lock = threading.Lock()


def get_tracer(service_name: str = "knowledge_compiler") -> Tracer:
    """
    Get or create global tracer

    Args:
        service_name: Service name for tracer

    Returns:
        Tracer instance
    """
    global _global_tracer

    with _tracer_lock:
        if _global_tracer is None:
            _global_tracer = Tracer(service_name=service_name)
        return _global_tracer


def trace_function(name: Optional[str] = None, tags: Dict[str, Any] | None = None):
    """
    Decorator using global tracer

    Args:
        name: Span name
        tags: Initial tags

    Returns:
        Decorator function
    """
    return trace(get_tracer(), name=name, tags=tags)


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "SpanStatus",
    "SpanContext",
    "Span",
    "Tracer",
    "get_tracer",
    "trace",
    "trace_function",
]
