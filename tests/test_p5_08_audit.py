#!/usr/bin/env python3
"""
P5-08: Audit Logging tests
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.security.audit import (
    AuditEventType,
    AuditEventStatus,
    AuditEvent,
    AuditLogger,
    get_audit_logger,
    configure_audit_logging,
    audit_operation,
    log_auth_login,
    log_authz_check,
    log_data_operation,
)


class TestAuditEventType:
    def test_event_type_values(self):
        """AuditEventType should have correct values"""
        assert AuditEventType.AUTH_LOGIN.value == "auth.login"
        assert AuditEventType.AUTHZ_GRANT.value == "authz.grant"
        assert AuditEventType.DATA_READ.value == "data.read"


class TestAuditEventStatus:
    def test_status_values(self):
        """AuditEventStatus should have correct values"""
        assert AuditEventStatus.SUCCESS.value == "success"
        assert AuditEventStatus.FAILURE.value == "failure"
        assert AuditEventStatus.ATTEMPT.value == "attempt"


class TestAuditEvent:
    def test_audit_event_creation(self):
        """AuditEvent should initialize"""
        event = AuditEvent(
            event_type=AuditEventType.DATA_READ,
            status=AuditEventStatus.SUCCESS,
            user_id="user123",
            resource="cache",
            action="get",
        )

        assert event.event_type == AuditEventType.DATA_READ
        assert event.user_id == "user123"
        assert event.resource == "cache"

    def test_audit_event_to_dict(self):
        """AuditEvent should convert to dictionary"""
        event = AuditEvent(
            event_type=AuditEventType.DATA_WRITE,
            status=AuditEventStatus.SUCCESS,
            user_id="user123",
            resource="cache",
            action="set",
            details={"key": "value"},
        )

        data = event.to_dict()

        assert data["event_type"] == "data.write"
        assert data["user_id"] == "user123"
        assert data["resource"] == "cache"
        assert data["action"] == "set"
        assert data["details"]["key"] == "value"
        assert "timestamp_iso" in data

    def test_audit_event_to_json(self):
        """AuditEvent should convert to JSON"""
        event = AuditEvent(
            event_type=AuditEventType.DATA_READ,
            status=AuditEventStatus.SUCCESS,
            user_id="user123",
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["user_id"] == "user123"


class TestAuditLogger:
    def test_audit_logger_creation(self):
        """AuditLogger should initialize"""
        logger = AuditLogger(max_events=100)

        assert logger.max_events == 100
        assert len(logger.get_events()) == 0

    def test_audit_logger_log_event(self):
        """AuditLogger should log events"""
        logger = AuditLogger()

        event = logger.log(
            event_type=AuditEventType.DATA_READ,
            user_id="user123",
            resource="cache",
        )

        assert event.event_id is not None
        assert event.user_id == "user123"

        events = logger.get_events()
        assert len(events) == 1
        assert events[0] is event

    def test_audit_logger_max_events(self):
        """AuditLogger should enforce max_events limit"""
        logger = AuditLogger(max_events=5)

        for i in range(10):
            logger.log(
                event_type=AuditEventType.DATA_READ,
                user_id=f"user{i}",
            )

        events = logger.get_events()
        assert len(events) == 5

    def test_audit_logger_filter_by_user(self):
        """AuditLogger should filter by user_id"""
        logger = AuditLogger()

        logger.log(AuditEventType.DATA_READ, "user1")
        logger.log(AuditEventType.DATA_WRITE, "user2")
        logger.log(AuditEventType.DATA_READ, "user1")

        events = logger.get_events(user_id="user1")
        assert len(events) == 2
        assert all(e.user_id == "user1" for e in events)

    def test_audit_logger_filter_by_type(self):
        """AuditLogger should filter by event type"""
        logger = AuditLogger()

        logger.log(AuditEventType.DATA_READ, "user1")
        logger.log(AuditEventType.DATA_WRITE, "user1")
        logger.log(AuditEventType.AUTH_LOGIN, "user2")

        events = logger.get_events(event_type=AuditEventType.DATA_READ)
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.DATA_READ

    def test_audit_logger_filter_by_resource(self):
        """AuditLogger should filter by resource"""
        logger = AuditLogger()

        logger.log(AuditEventType.DATA_READ, "user1", resource="cache")
        logger.log(AuditEventType.DATA_READ, "user1", resource="index")

        events = logger.get_events(resource="cache")
        assert len(events) == 1
        assert events[0].resource == "cache"

    def test_audit_logger_filter_by_since(self):
        """AuditLogger should filter by timestamp"""
        logger = AuditLogger()

        logger.log(AuditEventType.DATA_READ, "user1")
        time.sleep(0.01)
        cutoff = time.time()
        time.sleep(0.01)
        logger.log(AuditEventType.DATA_WRITE, "user2")

        events = logger.get_events(since=cutoff)
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.DATA_WRITE

    def test_audit_logger_limit(self):
        """AuditLogger should respect limit parameter"""
        logger = AuditLogger()

        for i in range(10):
            logger.log(AuditEventType.DATA_READ, f"user{i}")

        events = logger.get_events(limit=5)
        assert len(events) == 5

    def test_audit_logger_export_json(self):
        """AuditLogger should export to JSON"""
        logger = AuditLogger()

        logger.log(
            AuditEventType.DATA_READ,
            "user123",
            resource="cache",
            action="get",
        )

        json_str = logger.export_json()
        data = json.loads(json_str)

        assert len(data) == 1
        assert data[0]["user_id"] == "user123"
        assert data[0]["resource"] == "cache"

    def test_audit_logger_export_file(self):
        """AuditLogger should export to file"""
        import tempfile

        logger = AuditLogger()

        logger.log(
            AuditEventType.DATA_READ,
            "user123",
            resource="cache",
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name

        try:
            logger.export_file(temp_path)

            content = Path(temp_path).read_text()
            data = json.loads(content)

            assert len(data) == 1
            assert data[0]["user_id"] == "user123"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_audit_logger_clear(self):
        """AuditLogger should clear events"""
        logger = AuditLogger()

        logger.log(AuditEventType.DATA_READ, "user1")
        logger.log(AuditEventType.DATA_WRITE, "user2")

        assert len(logger.get_events()) == 2

        logger.clear()

        assert len(logger.get_events()) == 0

    def test_audit_logger_statistics(self):
        """AuditLogger should provide statistics"""
        logger = AuditLogger()

        logger.log(AuditEventType.DATA_READ, "user1")
        logger.log(AuditEventType.DATA_WRITE, "user2")
        logger.log(AuditEventType.DATA_READ, "user1")

        stats = logger.get_statistics()

        assert stats["total_events"] == 3
        assert stats["by_type"]["data.read"] == 2
        assert stats["by_type"]["data.write"] == 1
        assert stats["by_user"]["user1"] == 2
        assert stats["by_user"]["user2"] == 1

    def test_audit_logger_statistics_empty(self):
        """AuditLogger statistics should handle empty state"""
        logger = AuditLogger()

        stats = logger.get_statistics()

        assert stats["total_events"] == 0
        assert stats["by_status"] == {}


class TestGlobalAuditLogger:
    def test_get_audit_logger_singleton(self):
        """get_audit_logger should return singleton"""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is logger2

    def test_configure_audit_logging(self):
        """configure_audit_logging should create new logger"""
        logger = configure_audit_logging(max_events=500)

        assert logger.max_events == 500

        # Should be the new global logger
        assert get_audit_logger() is logger


class TestConvenienceFunctions:
    def test_log_auth_login_success(self):
        """log_auth_login should log successful login"""
        event = log_auth_login("user123", success=True, ip_address="127.0.0.1")

        assert event.event_type == AuditEventType.AUTH_LOGIN
        assert event.status == AuditEventStatus.SUCCESS
        assert event.ip_address == "127.0.0.1"

    def test_log_auth_login_failure(self):
        """log_auth_login should log failed login"""
        event = log_auth_login("user123", success=False)

        assert event.event_type == AuditEventType.AUTH_FAILED
        assert event.status == AuditEventStatus.FAILURE

    def test_log_authz_check_granted(self):
        """log_authz_check should log granted access"""
        event = log_authz_check("user123", "cache", "read", granted=True)

        assert event.event_type == AuditEventType.AUTHZ_GRANT
        assert event.resource == "cache"
        assert event.action == "read"

    def test_log_authz_check_denied(self):
        """log_authz_check should log denied access"""
        event = log_authz_check("user123", "cache", "write", granted=False)

        assert event.event_type == AuditEventType.AUTHZ_DENY

    def test_log_data_operation(self):
        """log_data_operation should log data operations"""
        event = log_data_operation(
            AuditEventType.DATA_WRITE,
            "user123",
            "cache",
            success=True,
            details={"key": "test"},
        )

        assert event.event_type == AuditEventType.DATA_WRITE
        assert event.details["key"] == "test"


class TestAuditDecorator:
    def test_audit_operation_success(self):
        """audit_operation decorator should log successful operations"""
        logger = get_audit_logger()
        logger.clear()

        @audit_operation(AuditEventType.DATA_READ, resource_arg="resource")
        def read_data(user_id: str, resource: str):
            return f"data_from_{resource}"

        result = read_data("user123", "cache")

        assert result == "data_from_cache"

        events = logger.get_events(user_id="user123")
        assert len(events) >= 1
        assert any(e.resource == "cache" for e in events)

    def test_audit_operation_failure(self):
        """audit_operation decorator should log failures"""
        logger = get_audit_logger()
        logger.clear()

        @audit_operation(AuditEventType.DATA_WRITE, resource_arg=0)
        def write_data(resource: str):
            raise ValueError("Write failed")

        try:
            write_data("cache")
        except ValueError:
            pass

        events = logger.get_events()
        assert any(e.status == AuditEventStatus.FAILURE for e in events)

    def test_audit_operation_with_positional_resource(self):
        """audit_operation should work with positional resource arg"""
        logger = get_audit_logger()
        logger.clear()

        @audit_operation(AuditEventType.DATA_READ, resource_arg=0)
        def read_resource(resource: str, user_id: str = "system"):
            return f"data_from_{resource}"

        read_resource("index")

        events = logger.get_events()
        assert len(events) >= 1


class TestIntegration:
    def test_correlation_id_propagation(self):
        """Audit events should capture correlation_id"""
        from knowledge_compiler.observability.logging import set_correlation_id

        logger = get_audit_logger()
        logger.clear()

        set_correlation_id("test-corr-456")

        event = logger.log(
            AuditEventType.DATA_READ,
            "user123",
            resource="cache",
        )

        assert event.correlation_id == "test-corr-456"

    def test_multiple_events_ordering(self):
        """Events should be ordered by timestamp (newest first)"""
        logger = get_audit_logger()
        logger.clear()

        logger.log(AuditEventType.DATA_READ, "user1")
        time.sleep(0.01)
        logger.log(AuditEventType.DATA_WRITE, "user2")
        time.sleep(0.01)
        logger.log(AuditEventType.DATA_READ, "user3")

        events = logger.get_events()

        assert events[0].user_id == "user3"
        assert events[1].user_id == "user2"
        assert events[2].user_id == "user1"


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
