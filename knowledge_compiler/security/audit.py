#!/usr/bin/env python3
"""
P5-08: Audit Logging - Security event tracking

Provides:
- Audit event recording
- User operation tracking
- Event filtering and querying
- JSON export
- Integration with RBAC
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from collections import deque

from knowledge_compiler.observability.logging import get_correlation_id


# ============================================================================
# Audit Event Types
# ============================================================================

class AuditEventType(Enum):
    """Types of audit events"""
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"

    # Authorization
    AUTHZ_GRANT = "authz.grant"
    AUTHZ_DENY = "authz.deny"

    # Data operations
    DATA_READ = "data.read"
    DATA_WRITE = "data.write"
    DATA_DELETE = "data.delete"

    # Admin operations
    ADMIN_USER_CREATE = "admin.user_create"
    ADMIN_USER_DELETE = "admin.user_delete"
    ADMIN_ROLE_ASSIGN = "admin.role_assign"
    ADMIN_POLICY_ADD = "admin.policy_add"

    # System operations
    SYSTEM_CONFIG_CHANGE = "system.config_change"
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"


class AuditEventStatus(Enum):
    """Status of audit events"""
    SUCCESS = "success"
    FAILURE = "failure"
    ATTEMPT = "attempt"


# ============================================================================
# Audit Event
# ============================================================================

@dataclass
class AuditEvent:
    """
    A single audit event

    Attributes:
        event_type: Type of event
        status: Event status
        user_id: User who performed the action
        resource: Resource affected (if any)
        action: Action performed
        timestamp: Event timestamp
        correlation_id: Request correlation ID
        details: Additional event details
        ip_address: Client IP address (if available)
        user_agent: Client user agent (if available)
    """

    event_type: AuditEventType
    status: AuditEventStatus
    user_id: str
    resource: Optional[str] = None
    action: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    event_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "status": self.status.value,
            "user_id": self.user_id,
            "resource": self.resource,
            "action": self.action,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.utcfromtimestamp(self.timestamp).isoformat() + "Z",
            "correlation_id": self.correlation_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }

    def to_json(self) -> str:
        """Convert event to JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


# ============================================================================
# Audit Logger
# ============================================================================

class AuditLogger:
    """
    Audit logger for security events

    Features:
    - In-memory event storage
    - Optional file output
    - Event filtering
    - Thread-safe
    """

    def __init__(
        self,
        max_events: int = 10000,
        output_file: Path | str | None = None,
    ):
        """
        Initialize audit logger

        Args:
            max_events: Maximum events to keep in memory
            output_file: Optional file to append events
        """
        self.max_events = max_events
        self.output_file = Path(output_file) if output_file else None
        self._events: deque[AuditEvent] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._event_counter = 0

    def log(
        self,
        event_type: AuditEventType,
        user_id: str,
        status: AuditEventStatus = AuditEventStatus.SUCCESS,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Dict[str, Any] | None = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log an audit event

        Args:
            event_type: Type of event
            user_id: User who performed the action
            status: Event status
            resource: Resource affected
            action: Action performed
            details: Additional details
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Created AuditEvent
        """
        event = AuditEvent(
            event_type=event_type,
            status=status,
            user_id=user_id,
            resource=resource,
            action=action,
            correlation_id=get_correlation_id(),
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            event_id=self._generate_event_id(),
        )

        with self._lock:
            self._events.append(event)

        # Write to file if configured
        if self.output_file:
            try:
                with open(self.output_file, "a", encoding="utf-8") as f:
                    f.write(event.to_json() + "\n")
            except Exception:
                pass  # Don't fail on write errors

        return event

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        self._event_counter += 1
        return f"evt_{int(time.time() * 1000)}_{self._event_counter}"

    def get_events(
        self,
        limit: Optional[int] = None,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        resource: Optional[str] = None,
        since: Optional[float] = None,
    ) -> List[AuditEvent]:
        """
        Get audit events with optional filtering

        Args:
            limit: Maximum events to return
            user_id: Filter by user ID
            event_type: Filter by event type
            resource: Filter by resource
            since: Only events after this timestamp

        Returns:
            List of matching events
        """
        with self._lock:
            events = list(self._events)

        # Apply filters
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if resource:
            events = [e for e in events if e.resource == resource]
        if since:
            events = [e for e in events if e.timestamp >= since]

        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        if limit:
            events = events[:limit]

        return events

    def export_json(
        self,
        **filter_kwargs,
    ) -> str:
        """
        Export events as JSON

        Args:
            **filter_kwargs: Filter arguments for get_events()

        Returns:
            JSON string
        """
        events = self.get_events(**filter_kwargs)
        data = [e.to_dict() for e in events]
        return json.dumps(data, ensure_ascii=False, default=str, indent=2)

    def export_file(
        self,
        file_path: Path | str,
        **filter_kwargs,
    ) -> None:
        """
        Export events to file

        Args:
            file_path: Output file path
            **filter_kwargs: Filter arguments for get_events()
        """
        json_str = self.export_json(**filter_kwargs)
        Path(file_path).write_text(json_str, encoding="utf-8")

    def clear(self) -> None:
        """Clear all events"""
        with self._lock:
            self._events.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit statistics"""
        with self._lock:
            events = list(self._events)

        if not events:
            return {
                "total_events": 0,
                "by_status": {},
                "by_type": {},
                "by_user": {},
            }

        by_status = {}
        by_type = {}
        by_user = {}

        for event in events:
            # Count by status
            status = event.status.value
            by_status[status] = by_status.get(status, 0) + 1

            # Count by type
            etype = event.event_type.value
            by_type[etype] = by_type.get(etype, 0) + 1

            # Count by user
            user = event.user_id
            by_user[user] = by_user.get(user, 0) + 1

        return {
            "total_events": len(events),
            "oldest_event": min(e.timestamp for e in events),
            "newest_event": max(e.timestamp for e in events),
            "by_status": by_status,
            "by_type": by_type,
            "by_user": by_user,
        }


# ============================================================================
# RBAC Integration
# ============================================================================

class AuditRBACMixin:
    """
    Mixin to add audit logging to RBAC operations
    """

    def __init__(self, *args, audit_logger: AuditLogger | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.audit_logger = audit_logger or get_audit_logger()

    def log_authz(
        self,
        user_id: str,
        resource: str,
        action: str,
        granted: bool,
        details: Dict[str, Any] | None = None,
    ) -> None:
        """Log authorization decision"""
        event_type = AuditEventType.AUTHZ_GRANT if granted else AuditEventType.AUTHZ_DENY
        status = AuditEventStatus.SUCCESS

        self.audit_logger.log(
            event_type=event_type,
            user_id=user_id,
            status=status,
            resource=resource,
            action=action,
            details=details or {},
        )


# ============================================================================
# Decorators for Audit Logging
# ============================================================================

def audit_operation(
    event_type: AuditEventType,
    resource_arg: str | int = 0,  # Index or name of resource argument
    action_arg: str | int | None = None,
):
    """
    Decorator to audit function calls

    Args:
        event_type: Type of event to log
        resource_arg: Index or keyword name of resource argument
        action_arg: Index or keyword name of action argument (optional)

    Returns:
        Decorated function
    """

    def decorator(func):
        # Get parameter names for positional argument lookup
        import inspect
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        def wrapper(*args, **kwargs):
            audit_logger = get_audit_logger()

            # Try to get user_id from kwargs or positional args
            user_id = kwargs.get("user_id")
            if not user_id and len(args) > 0:
                user_id = args[0]

            # Get resource
            resource = None
            if isinstance(resource_arg, int):
                if resource_arg < len(args):
                    resource = str(args[resource_arg])
                elif resource_arg < len(param_names):
                    # Try to get from kwargs by parameter name
                    param_name = param_names[resource_arg]
                    resource = kwargs.get(param_name)
            elif isinstance(resource_arg, str):
                resource = kwargs.get(resource_arg)
                # If not in kwargs, try to find by parameter name
                if resource is None and resource_arg in param_names:
                    idx = param_names.index(resource_arg)
                    if idx < len(args):
                        resource = str(args[idx])

            # Get action
            action = None
            if action_arg is not None:
                if isinstance(action_arg, int):
                    if action_arg < len(args):
                        action = str(args[action_arg])
                    elif action_arg < len(param_names):
                        param_name = param_names[action_arg]
                        action = kwargs.get(param_name)
                elif isinstance(action_arg, str):
                    action = kwargs.get(action_arg)
                    if action is None and action_arg in param_names:
                        idx = param_names.index(action_arg)
                        if idx < len(args):
                            action = str(args[idx])

            try:
                result = func(*args, **kwargs)

                audit_logger.log(
                    event_type=event_type,
                    user_id=user_id or "system",
                    resource=resource,
                    action=action,
                )

                return result

            except Exception as e:
                audit_logger.log(
                    event_type=event_type,
                    user_id=user_id or "system",
                    status=AuditEventStatus.FAILURE,
                    resource=resource,
                    action=action,
                    details={"error": str(e)},
                )
                raise

        return wrapper

    return decorator


# ============================================================================
# Global Audit Logger
# ============================================================================

_global_audit_logger: Optional[AuditLogger] = None
_audit_lock = threading.Lock()


def get_audit_logger(
    max_events: int = 10000,
    output_file: Path | str | None = None,
) -> AuditLogger:
    """
    Get global audit logger

    Args:
        max_events: Maximum events to keep in memory
        output_file: Optional file to append events

    Returns:
        AuditLogger instance
    """
    global _global_audit_logger

    with _audit_lock:
        if _global_audit_logger is None:
            _global_audit_logger = AuditLogger(
                max_events=max_events,
                output_file=output_file,
            )

    return _global_audit_logger


def configure_audit_logging(
    max_events: int = 10000,
    output_file: Path | str | None = None,
) -> AuditLogger:
    """
    Configure global audit logging

    Args:
        max_events: Maximum events to keep in memory
        output_file: Optional file to append events

    Returns:
        Configured audit logger
    """
    global _global_audit_logger

    with _audit_lock:
        _global_audit_logger = AuditLogger(
            max_events=max_events,
            output_file=output_file,
        )

    return _global_audit_logger


# ============================================================================
# Convenience Functions
# ============================================================================

def log_auth_login(
    user_id: str,
    success: bool,
    ip_address: Optional[str] = None,
) -> AuditEvent:
    """Log authentication attempt"""
    logger = get_audit_logger()
    return logger.log(
        event_type=AuditEventType.AUTH_LOGIN if success else AuditEventType.AUTH_FAILED,
        user_id=user_id,
        status=AuditEventStatus.SUCCESS if success else AuditEventStatus.FAILURE,
        ip_address=ip_address,
    )


def log_authz_check(
    user_id: str,
    resource: str,
    action: str,
    granted: bool,
) -> AuditEvent:
    """Log authorization check"""
    logger = get_audit_logger()
    return logger.log(
        event_type=AuditEventType.AUTHZ_GRANT if granted else AuditEventType.AUTHZ_DENY,
        user_id=user_id,
        resource=resource,
        action=action,
    )


def log_data_operation(
    event_type: AuditEventType,
    user_id: str,
    resource: str,
    success: bool = True,
    details: Dict[str, Any] | None = None,
) -> AuditEvent:
    """Log data operation"""
    logger = get_audit_logger()
    return logger.log(
        event_type=event_type,
        user_id=user_id,
        resource=resource,
        status=AuditEventStatus.SUCCESS if success else AuditEventStatus.FAILURE,
        details=details,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "AuditEventType",
    "AuditEventStatus",
    "AuditEvent",
    "AuditLogger",
    "AuditRBACMixin",
    "get_audit_logger",
    "configure_audit_logging",
    "audit_operation",
    "log_auth_login",
    "log_authz_check",
    "log_data_operation",
]
