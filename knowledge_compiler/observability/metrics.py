#!/usr/bin/env python3
"""
P5-04: Metrics Collection - Prometheus integration

Provides:
- Counter: Monotonically increasing counter
- Gauge: Arbitrary up/down value
- Histogram: Distribution of values (latency, request sizes)
- MetricsCollector: Central metrics registry
- Prometheus exposition format
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict
from functools import wraps
from threading import Lock

logger = logging.getLogger(__name__)


# ============================================================================
# Metric Types
# ============================================================================

@dataclass
class Metric:
    """Base metric class"""
    name: str
    help: str
    labels: tuple[str, ...] = ()

    def format_name(self) -> str:
        """Format metric name for Prometheus"""
        # Replace invalid characters with underscore
        name = self.name.replace("-", "_").replace(".", "_")
        return name

    def format_labels(self, label_values: dict[str, str] | None = None) -> str:
        """Format labels for Prometheus"""
        if not self.labels and not label_values:
            return ""

        values = label_values or {}
        parts = []
        for i, label_name in enumerate(self.labels):
            value = values.get(label_name, "")
            parts.append(f'{label_name}="{value}"')

        # Add dynamic labels
        if label_values:
            for key, value in label_values.items():
                if key not in self.labels:
                    parts.append(f'{key}="{value}"')

        if parts:
            return "{" + ",".join(parts) + "}"
        return ""


@dataclass
class Counter(Metric):
    """
    Counter metric - monotonically increasing value

    Use for:
    - Request counts
    - Error counts
    - Task completions
    """
    name: str
    help: str
    labels: tuple[str, ...] = ()
    _value: int = 0
    _created: float = field(default_factory=time.time)
    # For labeled counters: dict[str, int]
    _labeled_values: dict[str, int] = field(default_factory=dict)
    # Total count (including all label combinations)
    _total_count: int = 0

    def inc(self, value: int = 1, labels: dict[str, str] | None = None) -> None:
        """
        Increment counter

        Args:
            value: Amount to increment (default: 1)
            labels: Label values
        """
        if value < 0:
            raise ValueError("Counter cannot be decremented")

        # Always increment total
        self._total_count += value

        if labels is None:
            self._value += value
        else:
            # Create label key
            label_key = tuple(sorted(labels.items()))
            key = f"{self.name}:{label_key}"
            self._labeled_values[key] = self._labeled_values.get(key, 0) + value

    def inc_to(self, value: int) -> None:
        """Set counter to specific value (only if higher)"""
        if value < 0:
            raise ValueError("Counter cannot be negative")
        if value > self._value:
            # Update _total_count to reflect the increase
            self._total_count += (value - self._value)
            self._value = value

    def get(self, labels: dict[str, str] | None = None) -> int:
        """
        Get current value

        Args:
            labels: Optional label values to get labeled counter

        Returns:
            Current value (for unlabeled: _value, for labeled counter: sum of all labeled values)
        """
        if labels is None:
            # If this counter has labels defined, return sum of all labeled values
            # Otherwise return the base value
            if self._labeled_values:
                return sum(self._labeled_values.values())
            return self._value

        label_key = tuple(sorted(labels.items()))
        key = f"{self.name}:{label_key}"
        return self._labeled_values.get(key, 0)

    def get_total(self) -> int:
        """Get total count (all label combinations)"""
        return self._total_count

    def reset(self) -> None:
        """Reset counter to 0"""
        self._value = 0
        self._labeled_values.clear()
        self._total_count = 0


@dataclass
class Gauge(Metric):
    """
    Gauge metric - arbitrary up/down value

    Use for:
    - Current state (queue size, active connections)
    - Temperature, memory usage
    - Percentages
    """
    name: str
    help: str
    labels: tuple[str, ...] = ()
    _value: float = 0.0

    def set(self, value: float) -> None:
        """Set gauge value"""
        self._value = value

    def inc(self, delta: float = 1.0) -> None:
        """Increment gauge"""
        self._value += delta

    def dec(self, delta: float = 1.0) -> None:
        """Decrement gauge"""
        self._value -= delta

    def get(self) -> float:
        """Get current value"""
        return self._value


@dataclass
class Histogram(Metric):
    """
    Histogram metric - distribution of values

    Use for:
    - Request latency
    - Request/response sizes
    - Processing times

    Uses predefined buckets for latency: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0] seconds
    """
    name: str
    help: str
    labels: tuple[str, ...] = ()
    _buckets: list[float] = field(default_factory=lambda: [
        0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
    ])
    _counts: list[int] = field(default_factory=list)
    _sum: float = 0.0
    _count: int = 0

    def __post_init__(self):
        """Initialize bucket counts"""
        if not self._counts:
            self._counts = [0] * (len(self._buckets) + 1)  # +1 for +Inf

    def observe(self, value: float) -> None:
        """
        Observe a value

        Args:
            value: Value to observe (must be positive)
        """
        if value < 0:
            raise ValueError("Histogram values must be non-negative")

        # Find the right bucket
        for i, bucket in enumerate(self._buckets):
            if value <= bucket:
                self._counts[i] += 1
                break
        else:
            # Value exceeds all buckets
            self._counts[-1] += 1

        self._sum += value
        self._count += 1

    def get_buckets(self) -> tuple[list[float], list[int]]:
        """Get buckets and counts"""
        # Add +Inf bucket
        buckets = self._buckets + [float("inf")]
        return buckets, self._counts

    def get_count(self) -> int:
        """Get total observation count"""
        return self._count

    def get_sum(self) -> float:
        """Get sum of all observations"""
        return self._sum

    def reset(self) -> None:
        """Reset histogram"""
        self._counts = [0] * (len(self._buckets) + 1)
        self._sum = 0.0
        self._count = 0


# ============================================================================
# Metrics Collector
# ============================================================================

class MetricsCollector:
    """
    Central metrics registry for Prometheus exposition

    Provides:
    - Metric registration and retrieval
    - Prometheus text format exposition
    - Thread-safe operations
    """

    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock = Lock()

        # Built-in metrics
        self._setup_builtin_metrics()

    def _setup_builtin_metrics(self):
        """Setup built-in metrics about the collector itself"""
        pass  # Can add self-metrics later

    # Counter methods

    def counter(
        self,
        name: str,
        help_text: str,
        labels: tuple[str, ...] = (),
    ) -> Counter:
        """
        Get or create a counter

        Args:
            name: Metric name
            help_text: Metric description
            labels: Label names

        Returns:
            Counter instance
        """
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(
                    name=name,
                    help=help_text,
                    labels=labels,
                )
            return self._counters[name]

    def inc_counter(
        self,
        name: str,
        value: int = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Increment a counter

        Args:
            name: Counter name
            value: Amount to increment
            labels: Label values
        """
        counter = self.counter(name, "")
        counter.inc(value, labels)

    # Gauge methods

    def gauge(
        self,
        name: str,
        help_text: str,
        labels: tuple[str, ...] = (),
    ) -> Gauge:
        """
        Get or create a gauge

        Args:
            name: Metric name
            help_text: Metric description
            labels: Label names

        Returns:
            Gauge instance
        """
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(
                    name=name,
                    help=help_text,
                    labels=labels,
                )
            return self._gauges[name]

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Set a gauge value

        Args:
            name: Gauge name
            value: Value to set
            labels: Label values
        """
        gauge = self.gauge(name, "")
        gauge.set(value)

    # Histogram methods

    def histogram(
        self,
        name: str,
        help_text: str,
        labels: tuple[str, ...] = (),
        buckets: list[float] | None = None,
    ) -> Histogram:
        """
        Get or create a histogram

        Args:
            name: Metric name
            help_text: Metric description
            labels: Label names
            buckets: Bucket boundaries

        Returns:
            Histogram instance
        """
        with self._lock:
            if name not in self._histograms:
                hist = Histogram(
                    name=name,
                    help=help_text,
                    labels=labels,
                )
                if buckets is not None:
                    hist._buckets = buckets
                    hist._counts = [0] * (len(buckets) + 1)
                self._histograms[name] = hist
            return self._histograms[name]

    def observe_histogram(
        self,
        name: str,
        value: float,
    ) -> None:
        """
        Observe a value in a histogram

        Args:
            name: Histogram name
            value: Value to observe
        """
        histogram = self.histogram(name, "")
        histogram.observe(value)

    # Helper methods

    def time_it(
        self,
        histogram_name: str,
        labels: dict[str, str] | None = None,
    ):
        """
        Decorator to time function execution

        Args:
            histogram_name: Histogram metric name
            labels: Optional labels

        Returns:
            Decorator function
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    elapsed = time.perf_counter() - start
                    self.observe_histogram(histogram_name, elapsed)

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    elapsed = time.perf_counter() - start
                    self.observe_histogram(histogram_name, elapsed)

            # Return appropriate wrapper based on whether function is async
            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return wrapper

        return decorator

    # Exposition

    def expose(self) -> str:
        """
        Generate Prometheus text format exposition

        Returns:
            Prometheus metrics text
        """
        lines = []

        # Help line
        lines.append("# " + "-" * 40)

        # Counters
        with self._lock:
            for counter in self._counters.values():
                # HELP
                lines.append(f"# HELP {counter.format_name()} {counter.help}")
                # TYPE
                lines.append(f"# TYPE {counter.format_name()} counter")
                # VALUE
                name = counter.format_name()
                label_str = counter.format_labels()
                lines.append(f"{name}{label_str} {counter.get()}")

        # Gauges
        with self._lock:
            for gauge in self._gauges.values():
                lines.append(f"# HELP {gauge.format_name()} {gauge.help}")
                lines.append(f"# TYPE {gauge.format_name()} gauge")
                name = gauge.format_name()
                label_str = gauge.format_labels()
                lines.append(f"{name}{label_str} {gauge.get()}")

        # Histograms
        with self._lock:
            for hist in self._histograms.values():
                lines.append(f"# HELP {hist.format_name()} {hist.help}")
                lines.append(f"# TYPE {hist.format_name()} histogram")
                name = hist.format_name()
                label_str = hist.format_labels()

                buckets, counts = hist.get_buckets()

                # BUCKETS
                bucket_line = name + label_str
                bucket_line += "_bucket"
                lines.append(f"# BUCKETS {bucket_line}")

                # Sample
                sample_line = name + label_str
                for bucket, count in zip(buckets, counts):
                    lines.append(f'{sample_line}_bucket{{le="{bucket}"}} {count}')

                # Sum and count
                lines.append(f"{sample_line}_sum {hist.get_sum()}")
                lines.append(f"{sample_line}_count {hist.get_count()}")

        return "\n".join(lines)

    def reset_all(self) -> None:
        """Reset all metrics to initial state"""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()

            # Gauges don't have reset, set to 0
            for gauge in self._gauges.values():
                gauge.set(0.0)

            for hist in self._histograms.values():
                hist.reset()

    def get_metric_summary(self) -> dict:
        """
        Get summary of all metrics

        Returns:
            Dict with metric counts and values
        """
        with self._lock:
            return {
                "counters": {
                    name: counter.get()
                    for name, counter in self._counters.items()
                },
                "gauges": {
                    name: gauge.get()
                    for name, gauge in self._gauges.items()
                },
                "histograms": {
                    name: {
                        "count": hist.get_count(),
                        "sum": hist.get_sum(),
                    }
                    for name, hist in self._histograms.items()
                },
            }


# Global metrics collector instance
_global_collector: MetricsCollector | None = None
_collector_lock = Lock()


def get_metrics_collector() -> MetricsCollector:
    """
    Get global metrics collector instance

    Returns:
        MetricsCollector instance
    """
    global _global_collector

    with _collector_lock:
        if _global_collector is None:
            _global_collector = MetricsCollector()

    return _global_collector


# ============================================================================
# Predefined Metrics
# ============================================================================

class MemoryNetworkMetrics:
    """
    Predefined metrics for Memory Network operations

    Counters:
    - memory_network_nodes_total: Total number of nodes
    - memory_network_changes_total: Total number of changes
    - gate_results_total: Gate results by status

    Gauges:
    - memory_network_cache_size: Current cache size
    - memory_network_index_size: Current index size

    Histograms:
    - version_query_duration_seconds: Version query latency
    - propagation_duration_seconds: Propagation latency
    - cache_lookup_duration_seconds: Cache lookup latency
    """

    def __init__(self, collector: MetricsCollector | None = None):
        """
        Initialize Memory Network metrics

        Args:
            collector: Metrics collector (uses global if None)
        """
        self.collector = collector or get_metrics_collector()
        self._setup_metrics()

    def _setup_metrics(self):
        """Setup predefined metrics"""

        # Counters
        self.nodes_counter = self.collector.counter(
            "memory_network_nodes_total",
            "Total number of memory network nodes",
        )

        self.changes_counter = self.collector.counter(
            "memory_network_changes_total",
            "Total number of memory network changes",
        )

        self.gate_results_counter = self.collector.counter(
            "gate_results_total",
            "Total number of gate results",
            labels=("gate", "status"),
        )

        # Gauges
        self.cache_size_gauge = self.collector.gauge(
            "memory_network_cache_size",
            "Current number of cached nodes",
        )

        self.index_size_gauge = self.collector.gauge(
            "memory_network_index_size",
            "Current number of indexed versions",
        )

        # Histograms
        self.version_query_histogram = self.collector.histogram(
            "version_query_duration_seconds",
            "Version query latency distribution",
        )

        self.propagation_histogram = self.collector.histogram(
            "propagation_duration_seconds",
            "Propagation latency distribution",
        )

        self.cache_lookup_histogram = self.collector.histogram(
            "cache_lookup_duration_seconds",
            "Cache lookup latency distribution",
        )

    # Convenience methods

    def inc_nodes(self, delta: int = 1) -> None:
        """Increment node counter"""
        self.nodes_counter.inc(delta)

    def inc_changes(self, delta: int = 1) -> None:
        """Increment changes counter"""
        self.changes_counter.inc(delta)

    def inc_gate_result(self, gate: str, status: str) -> None:
        """Increment gate result counter"""
        self.collector.inc_counter(
            "gate_results_total",
            1,
            labels={"gate": gate, "status": status},
        )

    def set_cache_size(self, size: int) -> None:
        """Set cache size gauge"""
        self.cache_size_gauge.set(float(size))

    def set_index_size(self, size: int) -> None:
        """Set index size gauge"""
        self.index_size_gauge.set(float(size))

    def observe_version_query(self, duration: float) -> None:
        """Observe version query duration"""
        self.version_query_histogram.observe(duration)

    def observe_propagation(self, duration: float) -> None:
        """Observe propagation duration"""
        self.propagation_histogram.observe(duration)

    def observe_cache_lookup(self, duration: float) -> None:
        """Observe cache lookup duration"""
        self.cache_lookup_histogram.observe(duration)


# Export main classes
__all__ = [
    "MetricsCollector",
    "get_metrics_collector",
    "Counter",
    "Gauge",
    "Histogram",
    "MemoryNetworkMetrics",
]
