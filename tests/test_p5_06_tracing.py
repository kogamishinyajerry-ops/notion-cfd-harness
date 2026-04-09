#!/usr/bin/env python3
"""
P5-06: Request Tracing tests
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.observability.tracing import (
    SpanStatus,
    SpanContext,
    Span,
    Tracer,
    get_tracer,
    trace,
    trace_function,
    _current_span_ctx,
)


class TestSpanStatus:
    def test_span_status_values(self):
        """SpanStatus should have correct values"""
        assert SpanStatus.OK.value == "ok"
        assert SpanStatus.ERROR.value == "error"
        assert SpanStatus.CANCELED.value == "canceled"


class TestSpanContext:
    def test_span_context_creation(self):
        """SpanContext should initialize with all fields"""
        ctx = SpanContext(
            trace_id="trace-123",
            span_id="span-456",
            parent_span_id="span-789",
        )

        assert ctx.trace_id == "trace-123"
        assert ctx.span_id == "span-456"
        assert ctx.parent_span_id == "span-789"

    def test_span_context_to_dict(self):
        """SpanContext should convert to dictionary"""
        ctx = SpanContext(
            trace_id="trace-123",
            span_id="span-456",
            parent_span_id="span-789",
        )

        data = ctx.to_dict()

        assert data["trace_id"] == "trace-123"
        assert data["span_id"] == "span-456"
        assert data["parent_span_id"] == "span-789"


class TestSpan:
    def test_span_creation(self):
        """Span should initialize with required fields"""
        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
        )

        assert span.name == "test_operation"
        assert span.trace_id == "trace-123"
        assert span.span_id == "span-456"
        assert span.status == SpanStatus.OK
        assert span.end_time is None

    def test_span_duration(self):
        """Span should calculate duration after end"""
        import time

        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
        )

        time.sleep(0.01)
        span.end()

        assert span.duration_ms is not None
        assert span.duration_ms >= 10  # At least 10ms
        assert span.duration_seconds is not None
        assert span.duration_seconds >= 0.01

    def test_span_tags(self):
        """Span should support tags"""
        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
        )

        span.set_tag("user_id", "123")
        span.set_tag("action", "login")

        assert span.tags["user_id"] == "123"
        assert span.tags["action"] == "login"

    def test_span_set_tags_multiple(self):
        """Span should support setting multiple tags"""
        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
        )

        span.set_tags({"key1": "value1", "key2": "value2"})

        assert span.tags["key1"] == "value1"
        assert span.tags["key2"] == "value2"

    def test_span_events(self):
        """Span should support events"""
        import time

        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
        )

        span.add_event("event1", {"data": "value1"})
        time.sleep(0.01)
        span.add_event("event2", {"data": "value2"})

        assert len(span.events) == 2
        assert span.events[0]["name"] == "event1"
        assert span.events[1]["name"] == "event2"

    def test_span_set_error_exception(self):
        """Span should capture error from exception"""
        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
        )

        try:
            raise ValueError("Test error")
        except ValueError as e:
            span.set_error(e)

        assert span.status == SpanStatus.ERROR
        assert span.tags["error.type"] == "ValueError"
        assert span.tags["error.message"] == "Test error"

    def test_span_set_error_string(self):
        """Span should capture error from string"""
        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
        )

        span.set_error("Custom error message")

        assert span.status == SpanStatus.ERROR
        assert span.tags["error.message"] == "Custom error message"

    def test_span_set_canceled(self):
        """Span should be marked as canceled"""
        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
        )

        span.set_canceled()

        assert span.status == SpanStatus.CANCELED

    def test_span_to_dict(self):
        """Span should convert to dictionary"""
        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
            parent_span_id="span-789",
        )

        span.set_tag("key", "value")
        span.end()

        data = span.to_dict()

        assert data["name"] == "test_operation"
        assert data["trace_id"] == "trace-123"
        assert data["span_id"] == "span-456"
        assert data["parent_span_id"] == "span-789"
        assert data["status"] == "ok"
        assert data["tags"]["key"] == "value"
        assert data["duration_ms"] is not None

    def test_span_to_json(self):
        """Span should convert to JSON"""
        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456",
        )

        json_str = span.to_json()
        data = json.loads(json_str)

        assert data["name"] == "test_operation"
        assert data["trace_id"] == "trace-123"

    def test_span_context_manager(self):
        """Span should work as context manager"""
        tracer = Tracer()

        with tracer.start_span("test_span") as span:
            assert _current_span_ctx.get() is span
            assert span.end_time is None

        # After exit, span should be ended
        assert span.end_time is not None

    def test_span_context_manager_with_error(self):
        """Span context manager should capture errors"""
        tracer = Tracer()

        try:
            with tracer.start_span("test_span") as span:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert span.status == SpanStatus.ERROR
        assert "Test error" in span.tags["error.message"]


class TestTracer:
    def test_tracer_creation(self):
        """Tracer should initialize"""
        tracer = Tracer(service_name="test_service")

        assert tracer.service_name == "test_service"
        assert len(tracer.get_root_spans()) == 0

    def test_tracer_start_span_root(self):
        """Tracer should create root spans"""
        tracer = Tracer()

        span = tracer.start_span("root_operation")

        assert span.name == "root_operation"
        assert span.parent_span_id is None
        assert len(tracer.get_root_spans()) == 1

    def test_tracer_start_span_child(self):
        """Tracer should create child spans"""
        tracer = Tracer()

        parent = tracer.start_span("parent_operation")
        child = tracer.start_span("child_operation", parent=parent)

        assert child.parent_span_id == parent.span_id
        assert child.trace_id == parent.trace_id
        assert len(parent.children) == 1
        assert parent.children[0] is child

    def test_tracer_start_span_with_context(self):
        """Tracer should use current span from context as parent"""
        tracer = Tracer()

        with tracer.start_span("parent") as parent:
            # Inside this context, parent is current span
            child = tracer.start_span("child")

            assert child.parent_span_id == parent.span_id

    def test_tracer_span_method(self):
        """Tracer.span() should create span for context manager"""
        tracer = Tracer()

        with tracer.span("test_operation") as span:
            assert span.name == "test_operation"

    def test_tracer_span_with_tags(self):
        """Tracer.span() should accept tags"""
        tracer = Tracer()

        with tracer.span("test_operation", tags={"key": "value"}) as span:
            assert span.tags["key"] == "value"

    def test_tracer_export_spans(self):
        """Tracer should export spans as dictionaries"""
        tracer = Tracer()

        with tracer.span("parent") as parent:
            with tracer.span("child"):
                pass

        spans = tracer.export_spans()

        assert len(spans) == 1
        assert spans[0]["name"] == "parent"
        assert len(spans[0]["children"]) == 1
        assert spans[0]["children"][0]["name"] == "child"

    def test_tracer_export_json(self):
        """Tracer should export spans as JSON"""
        tracer = Tracer()

        with tracer.span("test_operation"):
            pass

        json_str = tracer.export_json()
        data = json.loads(json_str)

        assert len(data) == 1
        assert data[0]["name"] == "test_operation"

    def test_tracer_clear_spans(self):
        """Tracer should clear all spans"""
        tracer = Tracer()

        with tracer.span("test_operation"):
            pass

        assert len(tracer.get_root_spans()) == 1

        tracer.clear_spans()

        assert len(tracer.get_root_spans()) == 0


class TestTraceDecorator:
    def test_trace_decorator_sync(self):
        """trace decorator should trace sync functions"""
        tracer = Tracer()

        @trace(tracer, name="custom_operation")
        def test_function(x: int) -> int:
            return x * 2

        result = test_function(5)

        assert result == 10
        assert len(tracer.get_root_spans()) == 1
        assert tracer.get_root_spans()[0].name == "custom_operation"

    def test_trace_decorator_auto_name(self):
        """trace decorator should use function name if not provided"""
        tracer = Tracer()

        @trace(tracer)
        def my_function(x: int) -> int:
            return x * 2

        my_function(5)

        assert tracer.get_root_spans()[0].name == "test_p5_06_tracing.my_function"

    def test_trace_decorator_with_tags(self):
        """trace decorator should apply tags"""
        tracer = Tracer()

        @trace(tracer, tags={"function": "test"})
        def test_function():
            pass

        test_function()

        span = tracer.get_root_spans()[0]
        assert span.tags["function"] == "test"

    def test_trace_decorator_captures_error(self):
        """trace decorator should capture errors"""
        tracer = Tracer()

        @trace(tracer)
        def failing_function():
            raise ValueError("Function error")

        try:
            failing_function()
        except ValueError:
            pass

        span = tracer.get_root_spans()[0]
        assert span.status == SpanStatus.ERROR
        assert "Function error" in span.tags["error.message"]

    def test_trace_decorator_async(self):
        """trace decorator should trace async functions"""
        tracer = Tracer()

        async def run_test():
            @trace(tracer)
            async def async_function(x: int) -> int:
                await asyncio.sleep(0.001)
                return x * 2

            result = await async_function(5)
            assert result == 10
            assert len(tracer.get_root_spans()) == 1

        asyncio.run(run_test())


class TestGlobalTracer:
    def test_get_tracer_singleton(self):
        """get_tracer should return same instance"""
        tracer1 = get_tracer()
        tracer2 = get_tracer()

        assert tracer1 is tracer2

    def test_trace_function_decorator(self):
        """trace_function decorator should use global tracer"""
        # Clear spans from previous tests
        get_tracer().clear_spans()

        @trace_function(name="decorated_func")
        def test_func():
            pass

        test_func()

        spans = get_tracer().get_root_spans()
        assert len(spans) >= 1
        # Find our span (may be last)
        found = any(s["name"] == "decorated_func" for s in get_tracer().export_spans())
        assert found


class TestNestedSpans:
    def test_nested_context_managers(self):
        """Nested spans should maintain parent-child relationship"""
        tracer = Tracer()

        with tracer.span("operation1") as span1:
            with tracer.span("operation2") as span2:
                with tracer.span("operation3") as span3:
                    pass

        assert span2.parent_span_id == span1.span_id
        assert span3.parent_span_id == span2.span_id
        assert len(span1.children) == 1
        assert len(span2.children) == 1

    def test_export_nested_structure(self):
        """Export should preserve nested structure"""
        tracer = Tracer()

        with tracer.span("parent") as parent:
            with tracer.span("child1"):
                pass
            with tracer.span("child2"):
                with tracer.span("grandchild"):
                    pass

        exported = tracer.export_spans()

        assert len(exported) == 1
        parent_data = exported[0]
        assert parent_data["name"] == "parent"
        assert len(parent_data["children"]) == 2
        assert parent_data["children"][0]["name"] == "child1"
        assert parent_data["children"][1]["name"] == "child2"
        assert len(parent_data["children"][1]["children"]) == 1
        assert parent_data["children"][1]["children"][0]["name"] == "grandchild"


class TestCorrelationIntegration:
    def test_span_captures_correlation_id(self):
        """Span should capture correlation_id from logging module"""
        from knowledge_compiler.observability.logging import set_correlation_id
        tracer = Tracer()

        set_correlation_id("test-corr-123")

        with tracer.span("test_op") as span:
            pass

        assert span.correlation_id == "test-corr-123"


# Run tests
if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
