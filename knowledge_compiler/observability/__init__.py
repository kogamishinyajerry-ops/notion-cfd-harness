#!/usr/bin/env python3
"""
P5-04~P5-06: Observability Module - Metrics, Logging, Tracing

Provides observability for Memory Network operations.
"""

from knowledge_compiler.observability.metrics import (
    MetricsCollector,
    get_metrics_collector,
    Counter,
    Gauge,
    Histogram,
    MemoryNetworkMetrics,
)

from knowledge_compiler.observability.logging import (
    LogLevel,
    LogEntry,
    StructuredLogger,
    get_logger,
    configure_logging,
    setup_standard_logging,
    get_correlation_id,
    set_correlation_id,
    new_correlation_id,
    with_correlation_id,
    correlation_context,
)

from knowledge_compiler.observability.tracing import (
    SpanStatus,
    Span,
    Tracer,
    get_tracer,
    trace,
    trace_function,
)

# Export main classes
__all__ = [
    # Metrics (P5-04)
    "MetricsCollector",
    "get_metrics_collector",
    "Counter",
    "Gauge",
    "Histogram",
    "MemoryNetworkMetrics",
    # Logging (P5-05)
    "LogLevel",
    "LogEntry",
    "StructuredLogger",
    "get_logger",
    "configure_logging",
    "setup_standard_logging",
    "get_correlation_id",
    "set_correlation_id",
    "new_correlation_id",
    "with_correlation_id",
    "correlation_context",
    # Tracing (P5-06)
    "SpanStatus",
    "Span",
    "Tracer",
    "get_tracer",
    "trace",
    "trace_function",
]
