#!/usr/bin/env python3
"""
P5-04: Metrics Collection tests
"""

from __future__ import annotations

import time
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.observability.metrics import (
    MetricsCollector,
    get_metrics_collector,
    Counter,
    Gauge,
    Histogram,
    MemoryNetworkMetrics,
)


class TestCounter:
    def test_counter_creation(self):
        """Counter should initialize with zero"""
        counter = Counter(name="test_counter", help="Test counter")

        assert counter.name == "test_counter"
        assert counter.help == "Test counter"
        assert counter.get() == 0

    def test_counter_increment(self):
        """Counter should increment value"""
        counter = Counter(name="test_counter", help="Test counter")

        counter.inc()
        assert counter.get() == 1

        counter.inc(5)
        assert counter.get() == 6

    def test_counter_negative_increment_fails(self):
        """Counter should not allow negative increment"""
        counter = Counter(name="test_counter", help="Test counter")

        try:
            counter.inc(-1)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # Expected

    def test_counter_inc_to(self):
        """Counter should inc_to higher value"""
        counter = Counter(name="test_counter", help="Test counter")

        counter.inc_to(10)
        assert counter.get() == 10

        # inc_to lower value should not change
        counter.inc_to(5)
        assert counter.get() == 10  # Still 10

    def test_counter_reset(self):
        """Counter should reset to zero"""
        counter = Counter(name="test_counter", help="Test counter")

        counter.inc()
        counter.inc()
        assert counter.get() == 2

        counter.reset()
        assert counter.get() == 0


class TestGauge:
    def test_gauge_creation(self):
        """Gauge should initialize with zero"""
        gauge = Gauge(name="test_gauge", help="Test gauge")

        assert gauge.name == "test_gauge"
        assert gauge.get() == 0.0

    def test_gauge_set(self):
        """Gauge should set value"""
        gauge = Gauge(name="test_gauge", help="Test gauge")

        gauge.set(42.0)
        assert gauge.get() == 42.0

    def test_gauge_inc(self):
        """Gauge should increment"""
        gauge = Gauge(name="test_gauge", help="Test gauge")

        gauge.inc()
        assert gauge.get() == 1.0

        gauge.inc(5.0)
        assert gauge.get() == 6.0

    def test_gauge_dec(self):
        """Gauge should decrement"""
        gauge = Gauge(name="test_gauge", help="Test gauge")

        gauge.set(10.0)
        gauge.dec()
        assert gauge.get() == 9.0

        gauge.dec(3.0)
        assert gauge.get() == 6.0


class TestHistogram:
    def test_histogram_creation(self):
        """Histogram should initialize with default buckets"""
        hist = Histogram(name="test_hist", help="Test histogram")

        assert hist.name == "test_hist"
        assert hist.get_count() == 0
        assert hist.get_sum() == 0.0

    def test_histogram_observe(self):
        """Histogram should observe values"""
        hist = Histogram(name="test_hist", help="Test histogram")

        hist.observe(0.001)  # In first bucket
        hist.observe(0.5)     # In middle bucket
        hist.observe(5.0)     # In high bucket

        assert hist.get_count() == 3
        assert hist.get_sum() == 5.501

    def test_histogram_negative_value_fails(self):
        """Histogram should not allow negative values"""
        hist = Histogram(name="test_hist", help="Test histogram")

        try:
            hist.observe(-1.0)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # Expected

    def test_histogram_buckets(self):
        """Histogram should distribute values across buckets"""
        hist = Histogram(name="test_hist", help="Test histogram")

        hist.observe(0.001)  # <= 0.001
        hist.observe(0.002)  # <= 0.005
        hist.observe(0.01)   # <= 0.01
        hist.observe(0.05)   # <= 0.05
        hist.observe(0.2)    # <= 0.5
        hist.observe(3.0)    # <= 5.0
        hist.observe(15.0)   # > 10.0 (+Inf)

        buckets, counts = hist.get_buckets()

        # Default buckets: 12 defined + Inf = 13 total
        assert len(buckets) == 13
        assert len(counts) == 13

        # Check that observations are distributed
        assert sum(counts) == 7  # Total observations

    def test_histogram_reset(self):
        """Histogram should reset all data"""
        hist = Histogram(name="test_hist", help="Test histogram")

        hist.observe(1.0)
        hist.observe(2.0)
        assert hist.get_count() == 2

        hist.reset()

        assert hist.get_count() == 0
        assert hist.get_sum() == 0.0


class TestMetricsCollector:
    def test_collector_creation(self):
        """MetricsCollector should initialize"""
        collector = MetricsCollector()

        assert len(collector._counters) == 0
        assert len(collector._gauges) == 0
        assert len(collector._histograms) == 0

    def test_collector_counter(self):
        """MetricsCollector should create counter"""
        collector = MetricsCollector()

        counter = collector.counter("test_total", "Test counter")
        assert counter is not None
        assert counter.name == "test_total"

        # Should be reusable
        counter2 = collector.counter("test_total", "Test counter")
        assert counter is counter2  # Same instance

    def test_collector_inc_counter(self):
        """MetricsCollector should increment counter"""
        collector = MetricsCollector()

        collector.inc_counter("test_total", 5)
        assert collector.counter("test_total", "").get() == 5

    def test_collector_gauge(self):
        """MetricsCollector should create gauge"""
        collector = MetricsCollector()

        gauge = collector.gauge("test_gauge", "Test gauge")
        assert gauge is not None

    def test_collector_set_gauge(self):
        """MetricsCollector should set gauge"""
        collector = MetricsCollector()

        collector.set_gauge("test_gauge", 42.0)
        assert collector.gauge("test_gauge", "").get() == 42.0

    def test_collector_histogram(self):
        """MetricsCollector should create histogram"""
        collector = MetricsCollector()

        hist = collector.histogram("test_hist", "Test histogram")
        assert hist is not None

    def test_collector_observe_histogram(self):
        """MetricsCollector should observe histogram"""
        collector = MetricsCollector()

        collector.observe_histogram("test_hist", 0.5)
        assert collector.histogram("test_hist", "").get_count() == 1

    def test_collector_time_it(self):
        """MetricsCollector time_it decorator should time functions"""
        collector = MetricsCollector()

        @collector.time_it("test_function_duration")
        def test_function():
            time.sleep(0.01)
            return "done"

        result = test_function()

        assert result == "done"
        assert collector.histogram("test_function_duration", "").get_count() == 1

    def test_collector_time_it_async(self):
        """MetricsCollector time_it decorator should time async functions"""
        import asyncio

        async def run_test():
            collector = MetricsCollector()

            @collector.time_it("test_async_function_duration")
            async def test_async_function():
                await asyncio.sleep(0.01)
                return "async_done"

            result = await test_async_function()

            assert result == "async_done"
            assert collector.histogram("test_async_function_duration", "").get_count() == 1

        asyncio.run(run_test())

    def test_collector_expose(self):
        """MetricsCollector should expose Prometheus format"""
        collector = MetricsCollector()

        collector.counter("expose_test_total", "Expose test counter")
        collector.gauge("expose_test_value", "Expose test gauge")

        output = collector.expose()

        assert "# HELP expose_test_total" in output
        assert "# TYPE expose_test_total counter" in output
        assert "expose_test_total " in output

    def test_collector_reset_all(self):
        """MetricsCollector should reset all metrics"""
        collector = MetricsCollector()

        counter = collector.counter("reset_test", "Reset test counter")
        counter.inc(10)
        gauge = collector.gauge("reset_test_gauge", "Reset test gauge")
        gauge.set(5.0)

        collector.reset_all()

        assert counter.get() == 0
        assert gauge.get() == 0.0

    def test_collector_get_summary(self):
        """MetricsCollector should return summary"""
        collector = MetricsCollector()

        collector.counter("summary_test", "Summary test counter")
        collector.gauge("summary_test_gauge", "Summary test gauge")
        collector.histogram("summary_test_hist", "Summary test histogram")

        collector.counter("summary_test", "").inc(5)
        collector.gauge("summary_test_gauge", "").set(3.0)
        collector.histogram("summary_test_hist", "").observe(0.5)

        summary = collector.get_metric_summary()

        assert "counters" in summary
        assert "gauges" in summary
        assert "histograms" in summary
        assert summary["counters"]["summary_test"] == 5
        assert summary["gauges"]["summary_test_gauge"] == 3.0


class TestMemoryNetworkMetrics:
    def test_memory_network_metrics_initialization(self):
        """MemoryNetworkMetrics should initialize"""
        metrics = MemoryNetworkMetrics()

        assert metrics.collector is not None
        assert metrics.nodes_counter is not None
        assert metrics.changes_counter is not None

    def test_memory_network_metrics_inc_nodes(self):
        """MemoryNetworkMetrics should increment node counter"""
        metrics = MemoryNetworkMetrics()

        metrics.inc_nodes(5)

        assert metrics.nodes_counter.get() == 5

    def test_memory_network_metrics_inc_changes(self):
        """MemoryNetworkMetrics should increment changes counter"""
        metrics = MemoryNetworkMetrics()

        metrics.inc_changes(3)

        assert metrics.changes_counter.get() == 3

    def test_memory_network_metrics_inc_gate_result(self):
        """MemoryNetworkMetrics should increment gate result counter"""
        metrics = MemoryNetworkMetrics()

        metrics.inc_gate_result("G3", "PASS")
        metrics.inc_gate_result("G3", "PASS")
        metrics.inc_gate_result("G4", "FAIL")

        assert metrics.gate_results_counter.get() == 3

    def test_memory_network_metrics_set_cache_size(self):
        """MemoryNetworkMetrics should set cache size"""
        metrics = MemoryNetworkMetrics()

        metrics.set_cache_size(100)

        assert metrics.cache_size_gauge.get() == 100.0

    def test_memory_network_metrics_set_index_size(self):
        """MemoryNetworkMetrics should set index size"""
        metrics = MemoryNetworkMetrics()

        metrics.set_index_size(50)

        assert metrics.index_size_gauge.get() == 50.0

    def test_memory_network_metrics_observe_version_query(self):
        """MemoryNetworkMetrics should observe version query duration"""
        metrics = MemoryNetworkMetrics()

        metrics.observe_version_query(0.050)
        metrics.observe_version_query(0.100)
        metrics.observe_version_query(0.200)

        assert metrics.version_query_histogram.get_count() == 3
        assert abs(metrics.version_query_histogram.get_sum() - 0.350) < 0.001

    def test_memory_network_metrics_observe_propagation(self):
        """MemoryNetworkMetrics should observe propagation duration"""
        metrics = MemoryNetworkMetrics()

        metrics.observe_propagation(0.5)
        metrics.observe_propagation(1.0)

        assert metrics.propagation_histogram.get_count() == 2

    def test_memory_network_metrics_observe_cache_lookup(self):
        """MemoryNetworkMetrics should observe cache lookup duration"""
        metrics = MemoryNetworkMetrics()

        metrics.observe_cache_lookup(0.001)
        metrics.observe_cache_lookup(0.010)

        assert metrics.cache_lookup_histogram.get_count() == 2


class TestGlobalCollector:
    def test_get_metrics_collector_singleton(self):
        """get_metrics_collector should return singleton"""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        assert collector1 is collector2  # Same instance


class TestPrometheusExposition:
    def test_expose_format_valid(self):
        """Exposed format should be valid Prometheus format"""
        collector = MetricsCollector()

        collector.counter("prometheus_test_total", "Prometheus test counter")
        collector.gauge("prometheus_test_value", "Prometheus test gauge")
        collector.histogram("prometheus_test_duration", "Prometheus test histogram")

        output = collector.expose()

        # Check format
        lines = output.split("\n")

        # Should have HELP lines
        help_text_lines = [l for l in lines if l.startswith("# HELP")]
        assert len(help_text_lines) >= 3

        # Should have TYPE lines
        type_lines = [l for l in lines if l.startswith("# TYPE")]
        assert len(type_lines) >= 3

        # Should have metric values
        value_lines = [l for l in lines if not l.startswith("#")]
        assert len(value_lines) >= 1

    def test_expose_histogram_format(self):
        """Histogram exposition should include bucket lines"""
        collector = MetricsCollector()

        collector.histogram("expose_hist", "Expose histogram")
        collector.observe_histogram("expose_hist", 0.1)

        output = collector.expose()

        # Check histogram format
        assert "# TYPE expose_hist histogram" in output
        assert "_bucket" in output
        assert "_sum" in output
        assert "_count" in output


class TestMetricNaming:
    def test_metric_name_formatting(self):
        """Metric names should be formatted for Prometheus"""
        counter = Counter(name="test-metric.with-dots", help="Test")

        formatted = counter.format_name()

        assert formatted == "test_metric_with_dots"  # Dots replaced

    def test_label_formatting(self):
        """Labels should be formatted correctly"""
        counter = Counter(
            name="test_counter",
            help="Test",
            labels=("unit", "version"),
        )

        formatted = counter.format_labels({"unit": "FORM-009", "version": "v1.0"})

        assert 'unit="FORM-009"' in formatted
        assert 'version="v1.0"' in formatted
        assert formatted.startswith("{") and formatted.endswith("}")


class TestCreateFunctions:
    def test_get_metrics_collector(self):
        """get_metrics_collector should return collector"""
        collector = get_metrics_collector()

        assert collector is not None
        assert isinstance(collector, MetricsCollector)
