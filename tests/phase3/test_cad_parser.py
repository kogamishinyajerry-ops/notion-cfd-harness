#!/usr/bin/env python3
"""
Tests for Phase 3 CAD Parser

Coverage:
1. Format detection
2. STL parsing (ASCII + binary)
3. OBJ parsing
4. Geometry calculations (bbox, surface area, volume, watertight)
5. CADParser: parse, mock mode, custom parser
6. BatchCADParser: batch parse, summary
7. Convenience functions
"""

import os
import tempfile

import pytest

from knowledge_compiler.phase3.schema import (
    GeometryFeature,
    MeshFormat,
    ParsedGeometry,
)
from knowledge_compiler.phase3.cad_parser.parser import (
    CADParser,
    BatchCADParser,
    create_parsed_geometry,
    detect_format,
    parse_geometry,
    _compute_bounding_box,
    _compute_surface_area,
    _compute_volume,
    _check_watertight,
    _cross,
    _sub,
    _parse_stl_ascii,
    _parse_stl_binary,
)


# ============================================================================
# Helpers
# ============================================================================

_ASCII_STL = """solid test
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
  facet normal 0 0 1
    outer loop
      vertex 1 0 0
      vertex 1 1 0
      vertex 0 1 0
    endloop
  endfacet
endsolid test
"""


def _write_ascii_stl(path: str) -> str:
    """写入 ASCII STL 测试文件"""
    with open(path, "w") as f:
        f.write(_ASCII_STL)
    return path


def _write_obj(path: str) -> str:
    """写入 OBJ 测试文件"""
    content = """
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
f 1 2 3
f 1 3 4
"""
    with open(path, "w") as f:
        f.write(content)
    return path


# ============================================================================
# Format Detection
# ============================================================================

class TestDetectFormat:
    def test_stl(self):
        assert detect_format("model.stl") == MeshFormat.STL

    def test_step(self):
        assert detect_format("model.step") == MeshFormat.STEP
        assert detect_format("model.stp") == MeshFormat.STEP

    def test_iges(self):
        assert detect_format("model.iges") == MeshFormat.IGES
        assert detect_format("model.igs") == MeshFormat.IGES

    def test_obj(self):
        assert detect_format("model.obj") == MeshFormat.OBJ

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="不支持"):
            detect_format("model.xyz")


# ============================================================================
# STL Parsing
# ============================================================================

class TestSTLParsing:
    def test_ascii_parse(self):
        result = _parse_stl_ascii(_ASCII_STL)
        assert len(result["facets"]) == 2
        assert len(result["vertices"]) == 6
        assert len(result["normals"]) == 2

    def test_ascii_normals(self):
        result = _parse_stl_ascii(_ASCII_STL)
        n = result["normals"][0]
        assert n == (0.0, 0.0, 1.0)

    def test_binary_parse_empty(self):
        result = _parse_stl_binary(b"\x00" * 84)
        assert result["facets"] == []

    def test_binary_parse_too_short(self):
        result = _parse_stl_binary(b"\x00" * 10)
        assert result["facets"] == []


# ============================================================================
# Geometry Calculations
# ============================================================================

class TestGeometryCalculations:
    def test_cross_product(self):
        result = _cross((1, 0, 0), (0, 1, 0))
        assert abs(result[0]) < 1e-10
        assert abs(result[1]) < 1e-10
        assert abs(result[2] - 1.0) < 1e-10

    def test_sub(self):
        result = _sub((3, 4, 5), (1, 2, 3))
        assert result == (2, 2, 2)

    def test_bounding_box(self):
        verts = [(0, 0, 0), (1, 2, 3)]
        bbox = _compute_bounding_box(verts)
        assert bbox is not None
        assert bbox["x_min"] == 0
        assert bbox["x_max"] == 1
        assert bbox["size_x"] == 1
        assert bbox["size_y"] == 2
        assert bbox["size_z"] == 3

    def test_bounding_box_empty(self):
        assert _compute_bounding_box([]) is None

    def test_surface_area_triangle(self):
        # 单位直角三角形面积 = 0.5
        facets = [((0, 0, 0), (1, 0, 0), (0, 1, 0))]
        area = _compute_surface_area(facets)
        assert abs(area - 0.5) < 1e-10

    def test_surface_area_empty(self):
        assert _compute_surface_area([]) == 0.0

    def test_volume_cube(self):
        # 单位立方体（2 三角形/面 × 6 面 = 12 三角形）
        s = 0.5
        v = [
            (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
            (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s),
        ]
        facets = [
            (v[0], v[1], v[2]), (v[0], v[2], v[3]),
            (v[4], v[6], v[5]), (v[4], v[7], v[6]),
            (v[0], v[4], v[5]), (v[0], v[5], v[1]),
            (v[2], v[6], v[7]), (v[2], v[7], v[3]),
            (v[0], v[3], v[7]), (v[0], v[7], v[4]),
            (v[1], v[5], v[6]), (v[1], v[6], v[2]),
        ]
        vol = _compute_volume(facets)
        assert abs(vol - 1.0) < 1e-6  # unit cube = 1.0

    def test_watertight_cube(self):
        s = 0.5
        v = [
            (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
            (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s),
        ]
        facets = [
            (v[0], v[1], v[2]), (v[0], v[2], v[3]),
            (v[4], v[6], v[5]), (v[4], v[7], v[6]),
            (v[0], v[4], v[5]), (v[0], v[5], v[1]),
            (v[2], v[6], v[7]), (v[2], v[7], v[3]),
            (v[0], v[3], v[7]), (v[0], v[7], v[4]),
            (v[1], v[5], v[6]), (v[1], v[6], v[2]),
        ]
        is_wt, issues = _check_watertight(facets)
        assert is_wt is True
        assert issues == []

    def test_not_watertight(self):
        # 缺少一个面
        facets = [
            ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        ]
        is_wt, issues = _check_watertight(facets)
        assert is_wt is False
        assert len(issues) > 0

    def test_watertight_empty(self):
        is_wt, issues = _check_watertight([])
        assert is_wt is False


# ============================================================================
# CADParser Tests
# ============================================================================

class TestCADParser:
    def test_mock_parse(self):
        parser = CADParser(mock_mode=True)
        result = parser.parse("test.stl")
        assert result.is_watertight is True
        assert result.surface_area > 0
        assert result.volume > 0
        assert len(result.features) > 0

    def test_mock_parse_format(self):
        parser = CADParser(mock_mode=True)
        result = parser.parse("test.stl", format=MeshFormat.STL)
        assert result.format == MeshFormat.STL

    def test_file_not_found(self):
        parser = CADParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/model.stl")

    def test_parse_ascii_stl(self):
        with tempfile.NamedTemporaryFile(suffix=".stl", mode="w", delete=False) as f:
            f.write(_ASCII_STL)
            f.flush()
            try:
                parser = CADParser()
                result = parser.parse(f.name)
                assert result.source_file == f.name
                assert result.format == MeshFormat.STL
                assert result.surface_area > 0
                assert isinstance(result.features, list)
            finally:
                os.unlink(f.name)

    def test_parse_obj(self):
        with tempfile.NamedTemporaryFile(suffix=".obj", mode="w", delete=False) as f:
            _write_obj(f.name)
            try:
                parser = CADParser()
                result = parser.parse(f.name)
                assert result.format == MeshFormat.OBJ
                assert isinstance(result.features, list)
            finally:
                os.unlink(f.name)

    def test_custom_parser(self):
        def my_parser(path):
            return {
                "facets": [((0, 0, 0), (1, 0, 0), (0, 1, 0))],
                "vertices": [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
                "normals": [],
            }

        parser = CADParser(custom_parser=my_parser)
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            f.write(b"dummy")
            f.flush()
            try:
                result = parser.parse(f.name)
                assert result.surface_area > 0
            finally:
                os.unlink(f.name)

    def test_mock_bounding_box(self):
        parser = CADParser(mock_mode=True)
        result = parser.parse("test.stl")
        assert result.bounding_box is not None
        assert "size_x" in result.bounding_box

    def test_step_returns_empty(self):
        """STEP 格式暂不支持，返回空数据"""
        parser = CADParser()
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
            f.write(b"dummy step data")
            f.flush()
            try:
                result = parser.parse(f.name)
                assert result.format == MeshFormat.STEP
                assert result.features == []
            finally:
                os.unlink(f.name)


# ============================================================================
# BatchCADParser Tests
# ============================================================================

class TestBatchCADParser:
    def test_batch_mock(self):
        batch = BatchCADParser(mock_mode=True)
        results = batch.parse_batch(["a.stl", "b.stl", "c.obj"])
        assert len(results) == 3

    def test_batch_summary(self):
        batch = BatchCADParser(mock_mode=True)
        results = batch.parse_batch(["a.stl", "b.stl"])
        summary = batch.get_summary(results)
        assert summary["total"] == 2
        assert summary["watertight"] == 2
        assert "stl" in summary["formats"]

    def test_batch_error_handling(self):
        """单个文件失败不影响其他文件"""
        batch = BatchCADParser()
        with tempfile.NamedTemporaryFile(suffix=".stl", mode="w", delete=False) as f:
            f.write(_ASCII_STL)
            f.flush()
            try:
                results = batch.parse_batch([f.name, "/nonexistent.stl"])
                assert len(results) == 2
                assert results[0].is_watertight or results[0].surface_area >= 0
                assert len(results[1].repair_needed) > 0
            finally:
                os.unlink(f.name)


# ============================================================================
# Convenience Functions
# ============================================================================

class TestConvenienceFunctions:
    def test_create_parsed_geometry(self):
        geom = create_parsed_geometry(
            source_file="test.stl",
            format=MeshFormat.STL,
            surface_area=10.0,
            volume=5.0,
            is_watertight=True,
        )
        assert geom.source_file == "test.stl"
        assert geom.surface_area == 10.0
        assert geom.volume == 5.0
        assert geom.is_watertight is True

    def test_create_parsed_geometry_defaults(self):
        geom = create_parsed_geometry()
        assert geom.format == MeshFormat.STL
        assert geom.features == []
        assert geom.repair_needed == []
