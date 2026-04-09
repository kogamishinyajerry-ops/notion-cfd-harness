#!/usr/bin/env python3
"""
Phase 3 Mesh Builder Module

网格生成模块。
"""

# Schema types (re-exported for convenience)
from knowledge_compiler.phase3.schema import (
    MeshFormat,
    MeshQuality,
    MeshConfig,
    MeshStatistics,
    MeshResult,
)

# Builder module
from knowledge_compiler.phase3.mesh_builder.builder import (
    MeshBuilder,
    MeshBackend,
    GeometryType,
    generate_mesh,
    validate_stl,
)

__all__ = [
    # Schema (re-exports)
    "MeshFormat",
    "MeshQuality",
    "MeshConfig",
    "MeshStatistics",
    "MeshResult",
    # Builder
    "MeshBuilder",
    "MeshBackend",
    "GeometryType",
    "generate_mesh",
    "validate_stl",
]
