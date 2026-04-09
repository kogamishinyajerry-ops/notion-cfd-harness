#!/usr/bin/env python3
"""
Phase 2: Knowledge Compiler

知识编译层，负责将 Phase 1 的原始知识编译为标准化的可复用知识。

核心功能：
- Teach Capture: 捕获工程师教学操作
- Knowledge Parser: 解析并理解教学内容
- Canonical Compiler: 编译为标准知识规范
- Publish Contract: 知识发布流程
"""

# Schema
from knowledge_compiler.phase2.schema import (
    # Enums
    TeachIntent,
    SpecType,
    CompilationStatus,
    # Teach Layer
    CaptureContext,
    TeachCapture,
    ParsedTeach,
    # Compiler Layer
    CanonicalSpec,
    CompilationResult,
    # Input/Output
    CompilerConfig,
    Phase2Input,
    CompiledKnowledge,
    # Factory
    create_phase2_input,
    create_compiled_knowledge,
)

__all__ = [
    # Enums
    "TeachIntent",
    "SpecType",
    "CompilationStatus",
    # Teach Layer
    "CaptureContext",
    "TeachCapture",
    "ParsedTeach",
    # Compiler Layer
    "CanonicalSpec",
    "CompilationResult",
    # Input/Output
    "CompilerConfig",
    "Phase2Input",
    "CompiledKnowledge",
    # Factory
    "create_phase2_input",
    "create_compiled_knowledge",
]
