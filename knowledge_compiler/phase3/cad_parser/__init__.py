#!/usr/bin/env python3
"""
Phase 3: CAD Parser

解析 CAD 几何文件，提取特征，检测水密性。
"""

# Schema types (re-exported)
from knowledge_compiler.phase3.schema import (
    GeometryFeature,
    MeshFormat,
    ParsedGeometry,
)

# Main module
from knowledge_compiler.phase3.cad_parser.parser import (
    CADParser,
    BatchCADParser,
    detect_format,
    parse_geometry,
    create_parsed_geometry,
)

__all__ = [
    # Schema
    "GeometryFeature",
    "MeshFormat",
    "ParsedGeometry",
    # Parser
    "CADParser",
    "BatchCADParser",
    # Convenience
    "detect_format",
    "parse_geometry",
    "create_parsed_geometry",
]
