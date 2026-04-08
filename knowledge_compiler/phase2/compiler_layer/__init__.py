#!/usr/bin/env python3
"""
Phase 2 Compiler Layer

将解析后的教学知识编译为标准化的知识规范。
"""

# Schema types (re-exported for convenience)
from knowledge_compiler.phase2.schema import (
    CanonicalSpec,
    SpecType,
    CompilationResult,
    CompiledKnowledge,
    CompilerConfig,
)

# Compiler module
from knowledge_compiler.phase2.compiler_layer.compiler import (
    CanonicalCompiler,
)

# Publisher module
from knowledge_compiler.phase2.compiler_layer.publisher import (
    KnowledgePublisher,
    publish_knowledge,
    verify_spec,
)

__all__ = [
    # Schema (re-exports)
    "CanonicalSpec",
    "SpecType",
    "CompilationResult",
    "CompiledKnowledge",
    "CompilerConfig",
    # Compiler
    "CanonicalCompiler",
    # Publisher
    "KnowledgePublisher",
    "publish_knowledge",
    "verify_spec",
]
