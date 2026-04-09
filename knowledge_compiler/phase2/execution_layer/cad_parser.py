#!/usr/bin/env python3
"""
CAD Parser - CAD 几何解析器

解析 CAD 文件并提取几何特征，对应 G4-P1 运行 Gate 前的技术基础。
支持 STL、OBJ、STEP 格式。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class GeometryFormat(Enum):
    """几何格式"""
    STL = "stl"
    OBJ = "obj"
    STEP = "step"
    STP = "stp"
    UNKNOWN = "unknown"


class GeometryType(Enum):
    """几何类型"""
    SURFACE = "surface"  # 面模型（STL/OBJ）
    SOLID = "solid"  # 实体模型（STEP）
    WIREFRAME = "wireframe"  # 线框
    POINT_CLOUD = "point_cloud"  # 点云


@dataclass
class BoundingBox:
    """边界框"""
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def length(self) -> float:
        """X 方向长度"""
        return self.max_x - self.min_x

    @property
    def width(self) -> float:
        """Y 方向宽度"""
        return self.max_y - self.min_y

    @property
    def height(self) -> float:
        """Z 方向高度"""
        return self.max_z - self.min_z

    @property
    def center(self) -> Tuple[float, float, float]:
        """中心点"""
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
            (self.min_z + self.max_z) / 2,
        )

    @property
    def volume(self) -> float:
        """包围盒体积"""
        return self.length * self.width * self.height

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "min_x": self.min_x,
            "min_y": self.min_y,
            "min_z": self.min_z,
            "max_x": self.max_x,
            "max_y": self.max_y,
            "max_z": self.max_z,
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "volume": self.volume,
        }


@dataclass
class GeometryFeature:
    """几何特征"""
    feature_type: str  # "face", "edge", "vertex", "hole", "fillet", etc.
    name: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    location: Optional[Tuple[float, float, float]] = None


@dataclass
class ParsedGeometry:
    """解析后的几何"""
    geometry_id: str = field(default_factory=lambda: f"GEOM-{time.time():.0f}")
    source_file: str = ""
    format: GeometryFormat = GeometryFormat.UNKNOWN
    geometry_type: GeometryType = GeometryType.SURFACE

    # 几何特征
    bounding_box: Optional[BoundingBox] = None
    surface_area: float = 0.0
    volume: float = 0.0
    n_faces: int = 0
    n_edges: int = 0
    n_vertices: int = 0

    # 额外特征
    features: List[GeometryFeature] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 解析状态
    is_valid: bool = True
    error_message: str = ""
    parse_time: float = 0.0

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            "geometry_id": self.geometry_id,
            "source_file": self.source_file,
            "format": self.format.value,
            "geometry_type": self.geometry_type.value,
            "is_valid": self.is_valid,
            "bounding_box": self.bounding_box.to_dict() if self.bounding_box else None,
            "surface_area": self.surface_area,
            "volume": self.volume,
            "n_faces": self.n_faces,
            "n_edges": self.n_edges,
            "n_vertices": self.n_vertices,
            "parse_time": self.parse_time,
        }


class STLParser:
    """STL 文件解析器"""

    @staticmethod
    def detect_format(content: str) -> bool:
        """检测是否为 STL 格式"""
        return "solid" in content.lower() or "facet" in content.lower()

    @staticmethod
    def parse_ascii(content: str) -> Tuple[List[float], List[int]]:
        """解析 ASCII STL"""
        vertices = []
        triangles = []

        lines = content.split("\n")
        vertex_count = 0

        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("vertex"):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        vertices.extend([x, y, z])
                        vertex_count += 1
                    except ValueError:
                        continue
            elif line.startswith("endfacet"):
                if vertex_count == 3:
                    # 记录三角形顶点索引
                    base_idx = len(vertices) // 3 - 3
                    triangles.extend([base_idx, base_idx + 1, base_idx + 2])
                vertex_count = 0

        return vertices, triangles

    @staticmethod
    def parse_binary(data: bytes) -> Tuple[List[float], List[int]]:
        """解析二进制 STL"""
        import struct

        # 跳过 84 字节头部
        if len(data) < 84:
            return [], []

        # 读取三角形数量
        n_triangles = struct.unpack("<I", data[84:88])[0]

        vertices = []
        triangles = []

        offset = 88
        triangle_size = 50  # 每个三角形 50 字节

        vertex_map = {}  # 用于去重顶点

        for i in range(n_triangles):
            if offset + triangle_size > len(data):
                break

            # 跳过法向量 (12 字节)
            # 读取 3 个顶点 (每个 12 字节)
            tri_vertices = []
            for j in range(3):
                v_offset = offset + 12 + j * 12
                x, y, z = struct.unpack("<fff", data[v_offset:v_offset + 12])
                v_key = (round(x, 6), round(y, 6), round(z, 6))

                if v_key not in vertex_map:
                    vertex_map[v_key] = len(vertices)
                    vertices.extend([x, y, z])

                tri_vertices.append(vertex_map[v_key])

            triangles.extend(tri_vertices)
            offset += triangle_size

        return vertices, triangles

    @staticmethod
    def compute_area(vertices: List[float], triangles: List[int]) -> float:
        """计算表面积"""
        if len(triangles) < 3:
            return 0.0

        area = 0.0
        for i in range(0, len(triangles), 3):
            if i + 2 >= len(triangles):
                break

            i0, i1, i2 = triangles[i], triangles[i + 1], triangles[i + 2]

            if i0 * 3 + 2 >= len(vertices) or i1 * 3 + 2 >= len(vertices) or i2 * 3 + 2 >= len(vertices):
                continue

            # 获取三个顶点
            v0 = vertices[i0 * 3:i0 * 3 + 3]
            v1 = vertices[i1 * 3:i1 * 3 + 3]
            v2 = vertices[i2 * 3:i2 * 3 + 3]

            # 计算叉积
            ax = v1[0] - v0[0]
            ay = v1[1] - v0[1]
            az = v1[2] - v0[2]
            bx = v2[0] - v0[0]
            by = v2[1] - v0[1]
            bz = v2[2] - v0[2]

            cross_x = ay * bz - az * by
            cross_y = az * bx - ax * bz
            cross_z = ax * by - ay * bx

            # 三角形面积
            tri_area = 0.5 * (cross_x ** 2 + cross_y ** 2 + cross_z ** 2) ** 0.5
            area += tri_area

        return area

    @staticmethod
    def compute_bounding_box(vertices: List[float]) -> Optional[BoundingBox]:
        """计算边界框"""
        if not vertices:
            return None

        n_coords = len(vertices)
        min_x = min_y = min_z = float('inf')
        max_x = max_y = max_z = float('-inf')

        for i in range(0, n_coords, 3):
            if i + 2 >= n_coords:
                break
            x, y, z = vertices[i], vertices[i + 1], vertices[i + 2]
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            min_z, max_z = min(min_z, z), max(max_z, z)

        return BoundingBox(min_x, min_y, min_z, max_x, max_y, max_z)


class OBJParser:
    """OBJ 文件解析器"""

    @staticmethod
    def parse(content: str) -> Tuple[List[float], List[int]]:
        """解析 OBJ 文件"""
        vertices = []
        faces = []

        lines = content.split("\n")
        vertex_offset = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if not parts:
                continue

            if parts[0] == "v" and len(parts) >= 4:
                # 顶点
                try:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    vertices.extend([x, y, z])
                except ValueError:
                    continue
            elif parts[0] == "f" and len(parts) >= 4:
                # 面（可能是三角形或四边形）
                face_verts = []
                for part in parts[1:]:
                    # 处理 v/vt/vn 格式
                    v_idx = int(part.split("/")[0])
                    if v_idx < 0:
                        v_idx = len(vertices) // 3 + v_idx + 1
                    face_verts.append(v_idx - 1)  # OBJ 索引从 1 开始

                # 三角化
                if len(face_verts) == 3:
                    faces.extend(face_verts)
                elif len(face_verts) == 4:
                    # 四边形分成两个三角形
                    faces.extend([face_verts[0], face_verts[1], face_verts[2]])
                    faces.extend([face_verts[0], face_verts[2], face_verts[3]])
                elif len(face_verts) > 4:
                    # 多边形扇形三角化
                    for i in range(1, len(face_verts) - 1):
                        faces.extend([face_verts[0], face_verts[i], face_verts[i + 1]])

        return vertices, faces


class GeometryAnalyzer:
    """几何分析器"""

    @staticmethod
    def detect_features(geometry: ParsedGeometry) -> List[GeometryFeature]:
        """检测几何特征"""
        features = []

        if geometry.bounding_box:
            # 检测长宽比
            bb = geometry.bounding_box
            dims = sorted([bb.length, bb.width, bb.height])
            aspect_ratio = dims[2] / (dims[0] or 1)

            if aspect_ratio > 10:
                features.append(GeometryFeature(
                    feature_type="high_aspect_ratio",
                    properties={"aspect_ratio": aspect_ratio}
                ))

            # 检测扁平几何
            if min(bb.length, bb.width, bb.height) / max(bb.length, bb.width, bb.height) < 0.01:
                features.append(GeometryFeature(
                    feature_type="thin_shell",
                    properties={"thickness": min(bb.length, bb.width, bb.height)}
                ))

            # 检测立方体/长方体
            if aspect_ratio < 1.5:
                features.append(GeometryFeature(
                    feature_type="box_like",
                    properties={}
                ))

        return features


class CADParser:
    """CAD 解析器主类"""

    def __init__(self):
        self.stl_parser = STLParser()
        self.obj_parser = OBJParser()
        self.analyzer = GeometryAnalyzer()

    def detect_format(self, file_path: str) -> GeometryFormat:
        """检测文件格式"""
        path = Path(file_path)
        suffix = path.suffix.lower()

        format_map = {
            ".stl": GeometryFormat.STL,
            ".obj": GeometryFormat.OBJ,
            ".step": GeometryFormat.STEP,
            ".stp": GeometryFormat.STP,
        }

        return format_map.get(suffix, GeometryFormat.UNKNOWN)

    def parse(
        self,
        file_path: str,
        extract_features: bool = True,
    ) -> ParsedGeometry:
        """解析 CAD 文件"""
        start_time = time.time()

        result = ParsedGeometry(
            source_file=file_path,
            format=self.detect_format(file_path),
        )

        try:
            path = Path(file_path)
            if not path.exists():
                result.is_valid = False
                result.error_message = f"文件不存在: {file_path}"
                return result

            # 根据格式解析
            if result.format == GeometryFormat.STL:
                result = self._parse_stl(path, result)
            elif result.format == GeometryFormat.OBJ:
                result = self._parse_obj(path, result)
            elif result.format in [GeometryFormat.STEP, GeometryFormat.STP]:
                result = self._parse_step(path, result)
            else:
                result.is_valid = False
                result.error_message = f"不支持的格式: {result.format}"

            # 提取特征
            if extract_features and result.is_valid:
                result.features = self.analyzer.detect_features(result)

        except Exception as e:
            result.is_valid = False
            result.error_message = f"解析错误: {str(e)}"

        result.parse_time = time.time() - start_time
        return result

    def _parse_stl(
        self,
        path: Path,
        result: ParsedGeometry,
    ) -> ParsedGeometry:
        """解析 STL 文件"""
        with open(path, 'rb') as f:
            data = f.read()

        # 检测二进制还是 ASCII
        try:
            content = data.decode('utf-8', errors='ignore')
            if self.stl_parser.detect_format(content):
                # ASCII STL
                vertices, triangles = self.stl_parser.parse_ascii(content)
            else:
                # 二进制 STL
                vertices, triangles = self.stl_parser.parse_binary(data)
        except:
            # 尝试二进制解析
            vertices, triangles = self.stl_parser.parse_binary(data)

        if not vertices:
            result.is_valid = False
            result.error_message = "无法解析 STL 文件"
            return result

        # 计算几何属性
        result.geometry_type = GeometryType.SURFACE
        result.n_vertices = len(vertices) // 3
        result.n_faces = len(triangles) // 3

        # 边数估计（每条边被两个面共享）
        result.n_edges = max(result.n_faces * 3 // 2, result.n_vertices)

        # 计算表面积
        result.surface_area = self.stl_parser.compute_area(vertices, triangles)

        # 计算边界框
        result.bounding_box = self.stl_parser.compute_bounding_box(vertices)

        # 体积估计（使用包围盒）
        if result.bounding_box:
            result.volume = result.bounding_box.volume * 0.3  # 粗略估计

        result.metadata["raw_vertices"] = vertices[:100]  # 保存前 100 个顶点用于调试
        result.metadata["n_triangles"] = len(triangles) // 3

        return result

    def _parse_obj(
        self,
        path: Path,
        result: ParsedGeometry,
    ) -> ParsedGeometry:
        """解析 OBJ 文件"""
        with open(path, 'r') as f:
            content = f.read()

        vertices, faces = self.obj_parser.parse(content)

        if not vertices:
            result.is_valid = False
            result.error_message = "无法解析 OBJ 文件"
            return result

        result.geometry_type = GeometryType.SURFACE
        result.n_vertices = len(vertices) // 3
        result.n_faces = len(faces) // 3
        result.n_edges = max(result.n_faces * 3 // 2, result.n_vertices)

        # 计算表面积
        result.surface_area = self.stl_parser.compute_area(vertices, faces)

        # 计算边界框
        result.bounding_box = self.stl_parser.compute_bounding_box(vertices)

        if result.bounding_box:
            result.volume = result.bounding_box.volume * 0.3

        return result

    def _parse_step(
        self,
        path: Path,
        result: ParsedGeometry,
    ) -> ParsedGeometry:
        """解析 STEP 文件（简化版）"""
        # STEP 解析需要专业库，这里做基本检测
        with open(path, 'r') as f:
            content = f.read()

        # 检测是否为有效 STEP 文件
        if "ISO-10303-21" not in content:
            result.is_valid = False
            result.error_message = "无效的 STEP 文件"
            return result

        result.geometry_type = GeometryType.SOLID

        # 尝试提取基本尺寸
        # 寻找 CARTESIAN_POINT 实体
        points = re.findall(r'CARTESIAN_POINT\s*\([^,]+,\s*\(([^)]+)\)', content)
        if points:
            coords = []
            for point in points[:100]:  # 限制处理数量
                try:
                    parts = [float(x.strip()) for x in point.split(",")]
                    if len(parts) >= 3:
                        coords.extend(parts[:3])
                except ValueError:
                    continue

            if coords:
                result.n_vertices = len(coords) // 3
                result.bounding_box = self.stl_parser.compute_bounding_box(coords)

        result.metadata["step_entities"] = len(re.findall(r'DATA;', content))
        result.metadata["requires_pythonocc"] = True

        return result

    def validate(self, geometry: ParsedGeometry) -> Tuple[bool, List[str]]:
        """验证几何"""
        errors = []
        warnings = []

        if not geometry.is_valid:
            return False, [geometry.error_message]

        if geometry.n_vertices == 0:
            errors.append("没有检测到顶点")

        if geometry.n_faces == 0 and geometry.geometry_type == GeometryType.SURFACE:
            warnings.append("没有检测到面")

        if geometry.bounding_box:
            if geometry.bounding_box.volume <= 0:
                errors.append("边界框体积为零或负")

            dims = [geometry.bounding_box.length, geometry.bounding_box.width, geometry.bounding_box.height]
            if any(d <= 0 for d in dims):
                errors.append("边界框尺寸为零或负")

        is_valid = len(errors) == 0
        return is_valid, errors + warnings


# 便捷函数
def parse_cad_file(file_path: str) -> ParsedGeometry:
    """便捷函数：解析 CAD 文件"""
    parser = CADParser()
    return parser.parse(file_path)


def get_geometry_info(file_path: str) -> Dict[str, Any]:
    """便捷函数：获取几何信息摘要"""
    parser = CADParser()
    result = parser.parse(file_path)
    return result.get_summary()
