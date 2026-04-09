#!/usr/bin/env python3
"""
P5-05: Structured Logging - JSON logging with correlation_id

Provides:
- StructuredLogger: JSON-based structured logging
- correlation_id propagation across async contexts
- log level management
- integration with structlog (optional)
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional, TextIO
from pathlib import Path

# Context variable for correlation_id propagation
_correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id",
)


# ============================================================================
# Log Levels
# ============================================================================

class LogLevel(Enum):
    """Log severity levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_python(cls, level: int) -> "LogLevel":
        """Convert Python logging level to LogLevel"""
        mapping = {
            logging.DEBUG: cls.DEBUG,
            logging.INFO: cls.INFO,
            logging.WARNING: cls.WARNING,
            logging.ERROR: cls.ERROR,
            logging.CRITICAL: cls.CRITICAL,
        }
        return mapping.get(level, cls.INFO)

    def to_python(self) -> int:
        """Convert to Python logging level"""
        return {
            self.DEBUG: logging.DEBUG,
            self.INFO: logging.INFO,
            self.WARNING: logging.WARNING,
            self.ERROR: logging.ERROR,
            self.CRITICAL: logging.CRITICAL,
        }[self]


# ============================================================================
# Log Entry
# ============================================================================

@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: str
    level: str
    message: str
    logger: str = "knowledge_compiler"
    correlation_id: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    line: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert log entry to JSON string"""
        data = {
            k: v for k, v in asdict(self).items()
            if v is not None and v != ""
        }
        return json.dumps(data, ensure_ascii=False, default=str)

    def to_text(self) -> str:
        """Convert log entry to readable text"""
        parts = [
            f"[{self.timestamp}]",
            self.level,
            f"{self.logger}",
        ]
        if self.correlation_id:
            parts.append(f"corr:{self.correlation_id[:8]}")
        parts.append(f"- {self.message}")
        if self.extra:
            parts.append(f"({json.dumps(self.extra, ensure_ascii=False)})")
        return " ".join(parts)


# ============================================================================
# Structured Logger
# ============================================================================

class StructuredLogger:
    """
    Structured JSON logger with correlation_id support

    Features:
    - JSON or text output
    - correlation_id propagation via contextvars
    - Thread-safe
    - Configurable log levels
    """

    def __init__(
        self,
        name: str = "knowledge_compiler",
        level: LogLevel = LogLevel.INFO,
        output: TextIO | None = None,
        json_format: bool = True,
        include_caller: bool = True,
    ):
        """
        Initialize structured logger

        Args:
            name: Logger name
            level: Minimum log level
            output: Output stream (default: stderr)
            json_format: Use JSON format (False for readable text)
            include_caller: Include module/function/line in output
        """
        self.name = name
        self.level = level
        self.output = output or sys.stderr
        self.json_format = json_format
        self.include_caller = include_caller
        self._lock = threading.Lock()

    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on level"""
        levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]
        return levels.index(level) >= levels.index(self.level)

    def _get_correlation_id(self) -> Optional[str]:
        """Get current correlation_id from context"""
        try:
            return _correlation_id_ctx.get()
        except LookupError:
            return None

    def _log(
        self,
        level: LogLevel,
        message: str,
        extra: Dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """Internal logging method"""
        if not self._should_log(level):
            return

        import inspect
        frame = inspect.currentframe()
        caller_frame = frame.f_back.f_back if frame else None

        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=level.value,
            message=message,
            logger=self.name,
            correlation_id=self._get_correlation_id(),
        )

        if self.include_caller and caller_frame:
            entry.module = caller_frame.f_globals.get("__name__")
            entry.function = caller_frame.f_code.co_name
            entry.line = caller_frame.f_lineno

        if extra:
            entry.extra.update(extra)
        if kwargs:
            entry.extra.update(kwargs)

        with self._lock:
            if self.json_format:
                self.output.write(entry.to_json() + "\n")
            else:
                self.output.write(entry.to_text() + "\n")
            self.output.flush()

    def debug(self, message: str, **kwargs) -> None:
        """Log DEBUG message"""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log INFO message"""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log WARNING message"""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log ERROR message"""
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log CRITICAL message"""
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log ERROR with exception info"""
        import traceback
        exc_info = traceback.format_exc()
        kwargs["exception"] = exc_info
        self._log(LogLevel.ERROR, message, **kwargs)

    def set_level(self, level: LogLevel) -> None:
        """Set minimum log level"""
        self.level = level


# ============================================================================
# Correlation ID Management
# ============================================================================

def get_correlation_id() -> Optional[str]:
    """Get current correlation_id from context"""
    try:
        return _correlation_id_ctx.get()
    except LookupError:
        return None


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation_id for current context"""
    _correlation_id_ctx.set(correlation_id)


def new_correlation_id() -> str:
    """Generate and set a new correlation_id"""
    import uuid
    cid = str(uuid.uuid4())[:8]
    set_correlation_id(cid)
    return cid


def with_correlation_id(
    correlation_id: str,
) -> Callable:
    """
    Decorator to run function with correlation_id context

    Args:
        correlation_id: Correlation ID to set

    Returns:
        Decorated function with correlation_id set
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            token = _correlation_id_ctx.set(correlation_id)
            try:
                return func(*args, **kwargs)
            finally:
                _correlation_id_ctx.reset(token)

        async def async_wrapper(*args, **kwargs):
            token = _correlation_id_ctx.set(correlation_id)
            try:
                return await func(*args, **kwargs)
            finally:
                _correlation_id_ctx.reset(token)

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


# ============================================================================
# Logger Factory
# ============================================================================

_loggers: Dict[str, StructuredLogger] = {}
_logger_lock = threading.Lock()


def get_logger(
    name: str = "knowledge_compiler",
    level: LogLevel = LogLevel.INFO,
    json_format: bool = True,
) -> StructuredLogger:
    """
    Get or create a structured logger

    Args:
        name: Logger name
        level: Log level
        json_format: Use JSON format

    Returns:
        StructuredLogger instance
    """
    with _logger_lock:
        if name not in _loggers:
            _loggers[name] = StructuredLogger(
                name=name,
                level=level,
                json_format=json_format,
            )
        return _loggers[name]


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    json_format: bool = True,
    output_file: str | None = None,
) -> StructuredLogger:
    """
    Configure global logging

    Args:
        level: Log level
        json_format: Use JSON format
        output_file: Optional file path for output

    Returns:
        Configured logger instance
    """
    output = None
    if output_file:
        output = open(output_file, "a", encoding="utf-8")

    logger = get_logger(
        name="knowledge_compiler",
        level=level,
        json_format=json_format,
    )
    if output:
        logger.output = output

    return logger


# ============================================================================
# Context Manager for Correlation ID
# ============================================================================

class correlation_context:
    """Context manager for correlation_id"""

    def __init__(self, correlation_id: str | None = None):
        """
        Initialize correlation context

        Args:
            correlation_id: ID to use (auto-generated if None)
        """
        self.correlation_id = correlation_id or new_correlation_id()
        self.token = None

    def __enter__(self) -> str:
        """Set correlation_id for context"""
        self.token = _correlation_id_ctx.set(self.correlation_id)
        return self.correlation_id

    def __exit__(self, *args):
        """Reset correlation_id"""
        if self.token:
            _correlation_id_ctx.reset(self.token)


# ============================================================================
# Standard Python Logging Handler
# ============================================================================

class StructuredLogHandler(logging.Handler):
    """
    Python logging.Handler that outputs structured logs
    """

    def __init__(self, logger: StructuredLogger):
        super().__init__()
        self.logger = logger

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to structured logger"""
        level = LogLevel.from_python(record.levelno)
        if not self.logger._should_log(level):
            return

        extra = {
            "python_logger": record.name,
            "process": record.process,
            "thread": record.thread,
        }

        self.logger._log(
            level,
            record.getMessage(),
            extra=extra,
        )


def setup_standard_logging(
    level: LogLevel = LogLevel.INFO,
    json_format: bool = True,
) -> StructuredLogger:
    """
    Setup structured logging for standard Python logging

    Args:
        level: Log level
        json_format: Use JSON format

    Returns:
        StructuredLogger instance attached to root logger
    """
    struct_logger = get_logger(level=level, json_format=json_format)
    handler = StructuredLogHandler(struct_logger)
    handler.setLevel(level.to_python())

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level.to_python())

    return struct_logger


# ============================================================================
# Export
# ============================================================================

__all__ = [
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
]
