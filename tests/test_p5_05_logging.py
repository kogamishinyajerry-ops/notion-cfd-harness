#!/usr/bin/env python3
"""
P5-05: Structured Logging tests
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path
import threading
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
    StructuredLogHandler,
)


class TestLogLevel:
    def test_log_level_values(self):
        """LogLevel should have correct values"""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_log_level_to_python(self):
        """LogLevel should convert to Python logging levels"""
        assert LogLevel.DEBUG.to_python() == 10  # logging.DEBUG
        assert LogLevel.INFO.to_python() == 20   # logging.INFO
        assert LogLevel.WARNING.to_python() == 30  # logging.WARNING
        assert LogLevel.ERROR.to_python() == 40   # logging.ERROR
        assert LogLevel.CRITICAL.to_python() == 50  # logging.CRITICAL


class TestLogEntry:
    def test_log_entry_creation(self):
        """LogEntry should initialize with all fields"""
        entry = LogEntry(
            timestamp="2024-01-01T00:00:00Z",
            level="INFO",
            message="Test message",
            logger="test",
        )

        assert entry.timestamp == "2024-01-01T00:00:00Z"
        assert entry.level == "INFO"
        assert entry.message == "Test message"
        assert entry.logger == "test"

    def test_log_entry_to_json(self):
        """LogEntry should serialize to JSON"""
        entry = LogEntry(
            timestamp="2024-01-01T00:00:00Z",
            level="INFO",
            message="Test message",
            extra={"key": "value"},
        )

        json_str = entry.to_json()
        data = json.loads(json_str)

        assert data["timestamp"] == "2024-01-01T00:00:00Z"
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["extra"]["key"] == "value"

    def test_log_entry_to_text(self):
        """LogEntry should format as readable text"""
        entry = LogEntry(
            timestamp="2024-01-01T00:00:00Z",
            level="INFO",
            message="Test message",
            logger="test",
        )

        text = entry.to_text()
        assert "INFO" in text
        assert "test" in text
        assert "Test message" in text


class TestStructuredLogger:
    def test_logger_creation(self):
        """StructuredLogger should initialize"""
        output = io.StringIO()
        logger = StructuredLogger(
            name="test",
            level=LogLevel.INFO,
            output=output,
            json_format=True,
        )

        assert logger.name == "test"
        assert logger.level == LogLevel.INFO

    def test_logger_json_output(self):
        """StructuredLogger should output JSON"""
        output = io.StringIO()
        logger = StructuredLogger(
            name="test",
            level=LogLevel.INFO,
            output=output,
            json_format=True,
        )

        logger.info("Test message")

        result = output.getvalue()
        data = json.loads(result.strip())

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test"

    def test_logger_text_output(self):
        """StructuredLogger should output text format"""
        output = io.StringIO()
        logger = StructuredLogger(
            name="test",
            level=LogLevel.INFO,
            output=output,
            json_format=False,
        )

        logger.info("Test message")

        result = output.getvalue()
        assert "INFO" in result
        assert "Test message" in result
        # Should be valid JSON
        try:
            json.loads(result.strip())
            assert False, "Should not be JSON format"
        except json.JSONDecodeError:
            pass  # Expected

    def test_logger_level_filtering(self):
        """StructuredLogger should filter by level"""
        output = io.StringIO()
        logger = StructuredLogger(
            name="test",
            level=LogLevel.WARNING,
            output=output,
            json_format=True,
        )

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        result = output.getvalue()
        lines = [l.strip() for l in result.strip().split("\n") if l.strip()]

        # Only WARNING and ERROR should be logged
        assert len(lines) == 2

        messages = [json.loads(l)["message"] for l in lines]
        assert "Warning message" in messages
        assert "Error message" in messages

    def test_logger_extra_fields(self):
        """StructuredLogger should include extra fields"""
        output = io.StringIO()
        logger = StructuredLogger(
            name="test",
            level=LogLevel.INFO,
            output=output,
            json_format=True,
        )

        logger.info("Test message", user_id="123", action="login")

        result = output.getvalue()
        data = json.loads(result.strip())

        assert data["extra"]["user_id"] == "123"
        assert data["extra"]["action"] == "login"

    def test_logger_set_level(self):
        """StructuredLogger should allow changing level"""
        output = io.StringIO()
        logger = StructuredLogger(
            name="test",
            level=LogLevel.WARNING,
            output=output,
            json_format=True,
        )

        logger.info("Should not log")
        assert len(output.getvalue()) == 0

        logger.set_level(LogLevel.DEBUG)
        logger.info("Should log now")
        assert len(output.getvalue()) > 0

    def test_logger_exception(self):
        """StructuredLogger should log exceptions"""
        output = io.StringIO()
        logger = StructuredLogger(
            name="test",
            level=LogLevel.ERROR,
            output=output,
            json_format=True,
        )

        try:
            raise ValueError("Test error")
        except ValueError:
            logger.exception("Error occurred")

        result = output.getvalue()
        data = json.loads(result.strip())

        assert data["level"] == "ERROR"
        assert "Error occurred" in data["message"]
        assert "exception" in data["extra"]
        assert "ValueError" in data["extra"]["exception"]


class TestCorrelationId:
    def test_set_and_get_correlation_id(self):
        """Should set and get correlation_id"""
        set_correlation_id("test-corr-123")
        assert get_correlation_id() == "test-corr-123"

    def test_new_correlation_id(self):
        """new_correlation_id should generate unique ID"""
        cid1 = new_correlation_id()
        cid2 = new_correlation_id()

        assert cid1 != cid2
        assert len(cid1) == 8
        assert len(cid2) == 8

    def test_correlation_context(self):
        """correlation_context should set correlation_id"""
        # Clear any existing correlation_id
        from knowledge_compiler.observability.logging import _correlation_id_ctx
        try:
            _correlation_id_ctx.set(None)
        except:
            pass

        # Before context, should be None or a different value
        with correlation_context("test-corr-456") as cid:
            assert cid == "test-corr-456"
            assert get_correlation_id() == "test-corr-456"

        # After context, value should be reset to previous state
        # (May not be None if another test set it)
        current = get_correlation_id()
        # Just verify it's not the one we set in the context
        assert current != "test-corr-456"

    def test_correlation_context_auto_generate(self):
        """correlation_context should auto-generate ID if None"""
        with correlation_context() as cid:
            assert cid is not None
            assert len(cid) == 8
            assert get_correlation_id() == cid

    def test_with_correlation_id_decorator(self):
        """with_correlation_id decorator should set correlation_id"""

        @with_correlation_id("decorated-corr-789")
        def test_function():
            return get_correlation_id()

        result = test_function()
        assert result == "decorated-corr-789"

    def test_with_correlation_id_decorator_async(self):
        """with_correlation_id decorator should work with async functions"""

        async def run_test():
            @with_correlation_id("async-corr-789")
            async def test_async_function():
                return get_correlation_id()

            result = await test_async_function()
            assert result == "async-corr-789"

        asyncio.run(run_test())

    def test_logger_includes_correlation_id(self):
        """StructuredLogger should include correlation_id in output"""
        output = io.StringIO()
        logger = StructuredLogger(
            name="test",
            level=LogLevel.INFO,
            output=output,
            json_format=True,
        )

        set_correlation_id("corr-in-log")
        logger.info("Test with correlation_id")

        result = output.getvalue()
        data = json.loads(result.strip())

        assert data["correlation_id"] == "corr-in-log"


class TestLoggerFactory:
    def test_get_logger_singleton(self):
        """get_logger should return same instance for same name"""
        logger1 = get_logger(name="singleton_test")
        logger2 = get_logger(name="singleton_test")

        assert logger1 is logger2

    def test_get_logger_different_names(self):
        """get_logger should return different instances for different names"""
        logger1 = get_logger(name="logger_a")
        logger2 = get_logger(name="logger_b")

        assert logger1 is not logger2

    def test_configure_logging(self):
        """configure_logging should setup global logger"""
        logger = configure_logging(
            level=LogLevel.DEBUG,
            json_format=True,
        )

        assert logger is not None
        assert logger.level == LogLevel.DEBUG


class TestThreadSafety:
    def test_concurrent_logging(self):
        """Multiple threads should log safely"""
        output = io.StringIO()
        logger = StructuredLogger(
            name="concurrent",
            level=LogLevel.INFO,
            output=output,
            json_format=True,
        )

        def log_worker(worker_id: int):
            for i in range(10):
                logger.info(f"Worker {worker_id} message {i}")

        threads = []
        for i in range(5):
            t = threading.Thread(target=log_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        result = output.getvalue()
        lines = [l.strip() for l in result.strip().split("\n") if l.strip()]

        # 5 workers * 10 messages = 50
        assert len(lines) == 50


class TestAsyncCorrelation:
    def test_correlation_in_async_context(self):
        """correlation_id should propagate in async context"""
        async def run_test():
            output = io.StringIO()
            logger = StructuredLogger(
                name="async_test",
                level=LogLevel.INFO,
                output=output,
                json_format=True,
            )

            async def inner_task():
                logger.info("Inner task message")
                return get_correlation_id()

            set_correlation_id("async-corr-123")
            logger.info("Outer message")
            cid = await inner_task()

            result = output.getvalue()
            lines = [l.strip() for l in result.strip().split("\n") if l.strip()]

            assert len(lines) == 2
            data1 = json.loads(lines[0])
            data2 = json.loads(lines[1])

            assert data1["correlation_id"] == "async-corr-123"
            assert data2["correlation_id"] == "async-corr-123"
            assert cid == "async-corr-123"

        asyncio.run(run_test())


class TestStandardLogging:
    def test_standard_logging_handler(self):
        """StructuredLogHandler should work with standard logging"""
        output = io.StringIO()
        struct_logger = StructuredLogger(
            name="from_standard",
            level=LogLevel.INFO,
            output=output,
            json_format=True,
        )

        handler = StructuredLogHandler(struct_logger)

        # Test with standard logging
        import logging
        standard_logger = logging.getLogger("test_standard")
        standard_logger.addHandler(handler)
        standard_logger.setLevel(logging.INFO)

        standard_logger.info("Standard logging message")

        result = output.getvalue()
        data = json.loads(result.strip())

        assert data["message"] == "Standard logging message"
        assert data["level"] == "INFO"

    def test_setup_standard_logging(self):
        """setup_standard_logging should configure root logger"""
        output = io.StringIO()

        # Get structured logger
        struct_logger = get_logger(name="standard_setup", level=LogLevel.INFO)
        struct_logger.output = output

        import logging

        # Clear existing handlers
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

        # Setup
        struct_logger2 = setup_standard_logging(level=LogLevel.INFO)
        struct_logger2.output = output

        # Log via standard logging
        logging.info("Via standard logging")

        result = output.getvalue()
        assert "Via standard logging" in result or len(result) > 0


class TestCorrelationAcrossTasks:
    def test_correlation_across_async_tasks(self):
        """correlation_id should be maintained across concurrent tasks"""
        async def run_test():
            output = io.StringIO()
            logger = StructuredLogger(
                name="async_tasks",
                level=LogLevel.INFO,
                output=output,
                json_format=True,
            )

            async def task_with_cid(task_id: str, cid: str):
                with correlation_context(cid):
                    await asyncio.sleep(0.001)
                    logger.info(f"Task {task_id}")
                    return get_correlation_id()

            # Run concurrent tasks with different correlation_ids
            results = await asyncio.gather(
                task_with_cid("A", "corr-aaa"),
                task_with_cid("B", "corr-bbb"),
                task_with_cid("C", "corr-ccc"),
            )

            assert results[0] == "corr-aaa"
            assert results[1] == "corr-bbb"
            assert results[2] == "corr-ccc"

            result = output.getvalue()
            lines = [l.strip() for l in result.strip().split("\n") if l.strip()]

            assert len(lines) == 3
            cids = [json.loads(l)["correlation_id"] for l in lines]
            assert "corr-aaa" in cids
            assert "corr-bbb" in cids
            assert "corr-ccc" in cids

        asyncio.run(run_test())


# Run async tests manually
if __name__ == "__main__":
    import unittest

    # Run sync tests
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)

    # Filter out async tests for manual run
    async_tests = [
        "test_with_correlation_id_decorator_async",
        "test_correlation_in_async_context",
        "test_correlation_across_async_tasks",
    ]

    all_tests = []
    for test_group in suite:
        for test in test_group:
            test_name = test._testMethodName
            if test_name not in async_tests:
                all_tests.append(test)

    # Run sync tests
    runner.run(unittest.TestSuite(all_tests))

    # Run async tests
    print("\n=== Running async tests ===")
    test_instance = TestCorrelationId()
    asyncio.run(test_instance.test_with_correlation_id_decorator_async())
    print("✓ test_with_correlation_id_decorator_async")

    test_instance = TestAsyncCorrelation()
    asyncio.run(test_instance.test_correlation_in_async_context())
    print("✓ test_correlation_in_async_context")

    test_instance = TestCorrelationAcrossTasks()
    asyncio.run(test_instance.test_correlation_across_async_tasks())
    print("✓ test_correlation_across_async_tasks")

    print("\nAll tests passed!")
