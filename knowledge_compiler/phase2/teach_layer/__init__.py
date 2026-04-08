#!/usr/bin/env python3
"""
Phase 2 Teach Layer

捕获并解析工程师的教学操作，提取可复用的知识。
"""

# Schema types (re-exported for convenience)
from knowledge_compiler.phase2.schema import (
    TeachCapture,
    ParsedTeach,
    CaptureContext,
    TeachIntent,
)

# Capture module
from knowledge_compiler.phase2.teach_layer.capture import (
    TeachCaptureExtractor,
    extract_captures,
    capture_teach_session,
)

# Parser module
from knowledge_compiler.phase2.teach_layer.parser import (
    KnowledgeParser,
    TeachParser,
    ParseResult,
    ParseMetadata,
    parse_teach_capture,
    parse_teach_captures,
)

__all__ = [
    # Schema (re-exports)
    "TeachCapture",
    "ParsedTeach",
    "CaptureContext",
    "TeachIntent",
    # Capture
    "TeachCaptureExtractor",
    "extract_captures",
    "capture_teach_session",
    # Parser
    "KnowledgeParser",
    "TeachParser",
    "ParseResult",
    "ParseMetadata",
    "parse_teach_capture",
    "parse_teach_captures",
]
