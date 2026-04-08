#!/usr/bin/env python3
"""
Tests for CAD Parser - CAD 几何解析器测试
"""

import tempfile
from pathlib import Path
import pytest

from knowledge_compiler.phase2.execution_layer.cad_parser import (
    BoundingBox,
    GeometryAnalyzer,
    GeometryFeature,
    GeometryFormat,
    GeometryType,
    OBJParser,
    ParsedGeometry,
    STLParser,
    CADParser,
    parse_cad_file,
    get_geometry_info,
)


class TestBoundingBox:
    """测试边界框"""

    def test_bounding_box_creation(self):
        """测试创建边界框"""
        bb = BoundingBox(0, 0, 0, 10, 20, 30)
        assert bb.length == 10
        assert bb.width == 20
        assert bb.height == 30
        assert bb.center == (5, 10, 15)
        assert bb.volume == 6000

    def test_bounding_box_to_dict(self):
        """测试边界框转字典"""
        bb = BoundingBox(0, 0, 0, 10, 10, 10)
        d = bb.to_dict()
        assert d["length"] == 10
        assert d["width"] == 10
        assert d["height"] == 10
        assert d["volume"] == 1000


class TestGeometryFeature:
    """测试几何特征"""

    def test_geometry_feature_creation(self):
        """测试创建几何特征"""
        feature = GeometryFeature(
            feature_type="face",
            name="test_face",
            properties={"area": 1.0},
            location=(0, 0, 0)
        )
        assert feature.feature_type == "face"
        assert feature.name == "test_face"
        assert feature.properties["area"] == 1.0


class TestParsedGeometry:
    """测试解析几何"""

    def test_parsed_geometry_creation(self):
        """测试创建解析几何"""
        geom = ParsedGeometry(
            source_file="test.stl",
            format=GeometryFormat.STL,
        )
        assert geom.geometry_id.startswith("GEOM-")
        assert geom.source_file == "test.stl"
        assert geom.format == GeometryFormat.STL
        assert geom.is_valid is True

    def test_parsed_geometry_get_summary(self):
        """测试获取摘要"""
        bb = BoundingBox(0, 0, 0, 10, 10, 10)
        geom = ParsedGeometry(
            source_file="test.stl",
            format=GeometryFormat.STL,
            bounding_box=bb,
            surface_area=100.0,
            n_vertices=100,
            n_faces=50,
        )
        summary = geom.get_summary()
        assert summary["source_file"] == "test.stl"
        assert summary["format"] == "stl"
        assert summary["n_vertices"] == 100
        assert summary["n_faces"] == 50


class TestSTLParser:
    """测试 STL 解析器"""

    def test_detect_format_ascii(self):
        """测试检测 ASCII STL"""
        content = "solid test\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nendloop\nendfacet\nendsolid"
        assert STLParser.detect_format(content) is True

    def test_detect_format_invalid(self):
        """测试检测非 STL"""
        content = "this is not an stl file"
        assert STLParser.detect_format(content) is False

    def test_parse_ascii_simple(self):
        """测试解析简单 ASCII STL"""
        content = """solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 0 1 0
  endloop
endfacet
endsolid test"""
        vertices, triangles = STLParser.parse_ascii(content)
        assert len(vertices) == 9  # 3 vertices * 3 coords
        assert len(triangles) == 3

    def test_parse_binary_header(self):
        """测试解析二进制 STL 头部"""
        # 创建最小二进制 STL (84 byte header + 4 byte count = 88 bytes)
        header = b'\x00' * 84
        count = b'\x01\x00\x00\x00'  # 1 triangle
        # 1 triangle = 50 bytes (12 normal + 9*3 vertex + 2 attr)
        triangle = b'\x00' * 12 + b'\x00' * 36 + b'\x00' * 2
        data = header + count + triangle

        vertices, triangles = STLParser.parse_binary(data)
        # 顶点数据可能为空（因为是零数据）
        assert isinstance(vertices, list)
        assert isinstance(triangles, list)

    def test_compute_area_triangle(self):
        """测试计算三角形面积"""
        # 单位三角形在 XY 平面
        vertices = [0, 0, 0, 1, 0, 0, 0, 1, 0]
        triangles = [0, 1, 2]
        area = STLParser.compute_area(vertices, triangles)
        assert area == pytest.approx(0.5, rel=0.01)

    def test_compute_bounding_box(self):
        """测试计算边界框"""
        vertices = [0, 0, 0, 10, 0, 0, 0, 10, 0, 0, 0, 10]
        bb = STLParser.compute_bounding_box(vertices)
        assert bb is not None
        assert bb.min_x == 0
        assert bb.max_x == 10
        assert bb.min_y == 0
        assert bb.max_y == 10
        assert bb.min_z == 0
        assert bb.max_z == 10

    def test_compute_bounding_box_empty(self):
        """测试空顶点列表"""
        bb = STLParser.compute_bounding_box([])
        assert bb is None


class TestOBJParser:
    """测试 OBJ 解析器"""

    def test_parse_simple_obj(self):
        """测试解析简单 OBJ"""
        content = """# Simple OBJ
v 0 0 0
v 1 0 0
v 0 1 0
f 1 2 3
"""
        vertices, faces = OBJParser.parse(content)
        assert len(vertices) == 9  # 3 vertices * 3 coords
        assert len(faces) == 3

    def test_parse_obj_quad(self):
        """测试解析四边形 OBJ"""
        content = """v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
f 1 2 3 4
"""
        vertices, faces = OBJParser.parse(content)
        # 四边形分成两个三角形
        assert len(faces) == 6  # 2 triangles * 3 indices

    def test_parse_obj_with_vertex_normal(self):
        """测试解析带顶点法向的 OBJ"""
        content = """v 0 0 0
v 1 0 0
v 0 1 0
vn 0 0 1
f 1//1 2//1 3//1
"""
        vertices, faces = OBJParser.parse(content)
        assert len(vertices) == 9
        assert len(faces) == 3

    def test_parse_obj_empty(self):
        """测试解析空 OBJ"""
        vertices, faces = OBJParser.parse("")
        assert len(vertices) == 0
        assert len(faces) == 0


class TestGeometryAnalyzer:
    """测试几何分析器"""

    def test_detect_features_high_aspect_ratio(self):
        """测试检测高宽长比"""
        geom = ParsedGeometry()
        geom.bounding_box = BoundingBox(0, 0, 0, 100, 1, 1)

        analyzer = GeometryAnalyzer()
        features = analyzer.detect_features(geom)

        assert any(f.feature_type == "high_aspect_ratio" for f in features)

    def test_detect_features_thin_shell(self):
        """测试检测薄壳"""
        geom = ParsedGeometry()
        geom.bounding_box = BoundingBox(0, 0, 0, 10, 10, 0.01)

        analyzer = GeometryAnalyzer()
        features = analyzer.detect_features(geom)

        assert any(f.feature_type == "thin_shell" for f in features)

    def test_detect_features_box_like(self):
        """测试检测类立方体"""
        geom = ParsedGeometry()
        geom.bounding_box = BoundingBox(0, 0, 0, 10, 10, 10)

        analyzer = GeometryAnalyzer()
        features = analyzer.detect_features(geom)

        assert any(f.feature_type == "box_like" for f in features)

    def test_detect_features_no_bounding_box(self):
        """测试无边界框"""
        geom = ParsedGeometry()
        geom.bounding_box = None

        analyzer = GeometryAnalyzer()
        features = analyzer.detect_features(geom)

        assert len(features) == 0


class TestCADParser:
    """测试 CAD 解析器"""

    def test_parser_init(self):
        """测试初始化"""
        parser = CADParser()
        assert parser.stl_parser is not None
        assert parser.obj_parser is not None
        assert parser.analyzer is not None

    def test_detect_format_stl(self):
        """测试检测 STL 格式"""
        parser = CADParser()
        fmt = parser.detect_format("model.stl")
        assert fmt == GeometryFormat.STL

    def test_detect_format_obj(self):
        """测试检测 OBJ 格式"""
        parser = CADParser()
        fmt = parser.detect_format("model.obj")
        assert fmt == GeometryFormat.OBJ

    def test_detect_format_step(self):
        """测试检测 STEP 格式"""
        parser = CADParser()
        fmt = parser.detect_format("model.step")
        assert fmt == GeometryFormat.STEP

    def test_detect_format_stp(self):
        """测试检测 STP 格式"""
        parser = CADParser()
        fmt = parser.detect_format("model.stp")
        assert fmt == GeometryFormat.STP

    def test_detect_format_unknown(self):
        """测试检测未知格式"""
        parser = CADParser()
        fmt = parser.detect_format("model.ply")
        assert fmt == GeometryFormat.UNKNOWN

    def test_parse_nonexistent_file(self):
        """测试解析不存在的文件"""
        parser = CADParser()
        result = parser.parse("/nonexistent/file.stl")
        assert result.is_valid is False
        assert "不存在" in result.error_message

    def test_parse_stl_file(self):
        """测试解析 STL 文件"""
        parser = CADParser()

        # 创建临时 STL 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.stl', delete=False) as f:
            f.write("""solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 0 1 0
  endloop
endfacet
endsolid test""")
            temp_path = f.name

        try:
            result = parser.parse(temp_path)
            assert result.is_valid is True
            assert result.format == GeometryFormat.STL
            assert result.geometry_type == GeometryType.SURFACE
            assert result.n_vertices > 0
            assert result.n_faces > 0
            assert result.bounding_box is not None
        finally:
            Path(temp_path).unlink()

    def test_parse_obj_file(self):
        """测试解析 OBJ 文件"""
        parser = CADParser()

        # 创建临时 OBJ 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write("""v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
f 1 2 3 4
""")
            temp_path = f.name

        try:
            result = parser.parse(temp_path)
            assert result.is_valid is True
            assert result.format == GeometryFormat.OBJ
            assert result.n_vertices == 4
        finally:
            Path(temp_path).unlink()

    def test_parse_step_file(self):
        """测试解析 STEP 文件"""
        parser = CADParser()

        # 创建临时 STEP 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.step', delete=False) as f:
            f.write("""ISO-10303-21;
HEADER;
ENDSEC;
DATA;
ENDSEC;
END-ISO-10303-21;
""")
            temp_path = f.name

        try:
            result = parser.parse(temp_path)
            assert result.format == GeometryFormat.STEP
            assert result.geometry_type == GeometryType.SOLID
        finally:
            Path(temp_path).unlink()

    def test_validate_valid_geometry(self):
        """测试验证有效几何"""
        parser = CADParser()
        geom = ParsedGeometry(
            bounding_box=BoundingBox(0, 0, 0, 10, 10, 10),
            n_vertices=100,
            n_faces=50,
        )

        is_valid, errors = parser.validate(geom)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_vertices(self):
        """测试验证无效顶点数"""
        parser = CADParser()
        geom = ParsedGeometry(
            bounding_box=BoundingBox(0, 0, 0, 10, 10, 10),
            n_vertices=0,
        )

        is_valid, errors = parser.validate(geom)
        assert is_valid is False
        assert any("顶点" in e for e in errors)

    def test_validate_zero_volume(self):
        """测试验证零体积"""
        parser = CADParser()
        geom = ParsedGeometry(
            bounding_box=BoundingBox(0, 0, 0, 0, 0, 0),
        )

        is_valid, errors = parser.validate(geom)
        assert is_valid is False
        assert any("体积" in e or "尺寸" in e for e in errors)


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_parse_cad_file(self):
        """测试 parse_cad_file 函数"""
        # 创建临时 STL 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.stl', delete=False) as f:
            f.write("""solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 0 1 0
  endloop
endfacet
endsolid test""")
            temp_path = f.name

        try:
            result = parse_cad_file(temp_path)
            assert result is not None
            assert result.is_valid is True
        finally:
            Path(temp_path).unlink()

    def test_get_geometry_info(self):
        """测试 get_geometry_info 函数"""
        # 创建临时 STL 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.stl', delete=False) as f:
            f.write("""solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 0 1 0
  endloop
endfacet
endsolid test""")
            temp_path = f.name

        try:
            info = get_geometry_info(temp_path)
            assert info is not None
            assert "geometry_id" in info
            assert "format" in info
            assert info["format"] == "stl"
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
