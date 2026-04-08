#!/usr/bin/env python3
"""
Phase 3: CAD Parser

解析 CAD 几何文件，提取特征，检测水密性，推荐修复方案。

核心组件:
- CADParser: 几何文件解析器
- BatchCADParser: 批量解析器
- 便捷函数: parse_geometry, create_parsed_geometry
"""

from __future__ import annotations

import logging
import os
import re
import struct
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from knowledge_compiler.phase3.schema import (
    GeometryFeature,
    MeshFormat,
    ParsedGeometry,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 文件格式检测
# ============================================================================

def detect_format(file_path: str) -> MeshFormat:
    """根据文件扩展名和内容检测几何格式

    Args:
        file_path: 几何文件路径

    Returns:
        检测到的 MeshFormat

    Raises:
        ValueError: 不支持的格式
    """
    ext = Path(file_path).suffix.lower()
    ext_map = {
        ".stl": MeshFormat.STL,
        ".step": MeshFormat.STEP,
        ".stp": MeshFormat.STEP,
        ".iges": MeshFormat.IGES,
        ".igs": MeshFormat.IGES,
        ".obj": MeshFormat.OBJ,
    }
    fmt = ext_map.get(ext)
    if fmt is None:
        raise ValueError(f"不支持的几何格式: {ext}")
    return fmt


# ============================================================================
# STL 解析
# ============================================================================

def _parse_stl_ascii(content: str) -> Dict[str, Any]:
    """解析 ASCII STL 文件

    Returns:
        包含 facets, normals, vertices 的字典
    """
    facets = []
    normals = []
    vertices = []

    # 提取所有 facet
    facet_pattern = re.compile(
        r"facet\s+normal\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s*"
        r"outer\s+loop\s*"
        r"vertex\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s*"
        r"vertex\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s*"
        r"vertex\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s*"
        r"endloop\s*endfacet",
        re.IGNORECASE,
    )

    for m in facet_pattern.finditer(content):
        nx, ny, nz = float(m.group(1)), float(m.group(2)), float(m.group(3))
        v1 = (float(m.group(4)), float(m.group(5)), float(m.group(6)))
        v2 = (float(m.group(7)), float(m.group(8)), float(m.group(9)))
        v3 = (float(m.group(10)), float(m.group(11)), float(m.group(12)))

        facets.append((v1, v2, v3))
        normals.append((nx, ny, nz))
        vertices.extend([v1, v2, v3])

    return {"facets": facets, "normals": normals, "vertices": vertices}


def _parse_stl_binary(data: bytes) -> Dict[str, Any]:
    """解析二进制 STL 文件

    Returns:
        包含 facets, normals, vertices 的字典
    """
    # 跳过 80 字节头
    if len(data) < 84:
        return {"facets": [], "normals": [], "vertices": []}

    n_facets = struct.unpack("<I", data[80:84])[0]
    facets = []
    normals = []
    vertices = []

    offset = 84
    for _ in range(n_facets):
        if offset + 50 > len(data):
            break
        nx, ny, nz = struct.unpack("<fff", data[offset:offset + 12])
        v1 = struct.unpack("<fff", data[offset + 12:offset + 24])
        v2 = struct.unpack("<fff", data[offset + 24:offset + 36])
        v3 = struct.unpack("<fff", data[offset + 36:offset + 48])

        facets.append((v1, v2, v3))
        normals.append((nx, ny, nz))
        vertices.extend([v1, v2, v3])
        offset += 50  # 12 + 36 + 2 bytes attribute

    return {"facets": facets, "normals": normals, "vertices": vertices}


def _parse_stl(file_path: str) -> Dict[str, Any]:
    """解析 STL 文件（自动检测 ASCII/二进制）"""
    with open(file_path, "rb") as f:
        data = f.read()

    # 检测是否为 ASCII STL
    try:
        content = data.decode("ascii")
        if "facet" in content.lower() and "vertex" in content.lower():
            return _parse_stl_ascii(content)
    except UnicodeDecodeError:
        pass

    return _parse_stl_binary(data)


# ============================================================================
# OBJ 解析
# ============================================================================

def _parse_obj(file_path: str) -> Dict[str, Any]:
    """解析 OBJ 文件

    Returns:
        包含 vertices, faces, normals 的字典
    """
    vertices = []
    faces = []
    normals = []
    face_normals = []

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("v "):
                parts = line.split()[1:4]
                vertices.append(tuple(float(x) for x in parts))
            elif line.startswith("vn "):
                parts = line.split()[1:4]
                normals.append(tuple(float(x) for x in parts))
            elif line.startswith("f "):
                # f v1/vt1/vn1 v2/vt2/vn2 ...
                face_verts = []
                face_n = []
                for part in line.split()[1:]:
                    indices = part.split("/")
                    vi = int(indices[0]) - 1 if indices[0] else None
                    if vi is not None:
                        face_verts.append(vi)
                    if len(indices) > 2 and indices[2]:
                        face_n.append(int(indices[2]) - 1)
                if face_verts:
                    faces.append(face_verts)
                if face_n:
                    face_normals.append(face_n)

    # 转换为三角面片
    facets = []
    for face in faces:
        for i in range(1, len(face) - 1):
            if face[0] < len(vertices) and face[i] < len(vertices) and face[i + 1] < len(vertices):
                facets.append((vertices[face[0]], vertices[face[i]], vertices[face[i + 1]]))

    return {
        "facets": facets,
        "vertices": vertices,
        "faces": faces,
        "normals": normals,
    }


# ============================================================================
# 几何计算
# ============================================================================

def _compute_bounding_box(vertices: List[Tuple[float, ...]]) -> Optional[Dict[str, float]]:
    """计算边界盒"""
    if not vertices:
        return None

    xs = [v[0] for v in vertices if len(v) > 0]
    ys = [v[1] for v in vertices if len(v) > 1]
    zs = [v[2] for v in vertices if len(v) > 2]

    if not xs:
        return None

    return {
        "x_min": min(xs), "x_max": max(xs),
        "y_min": min(ys), "y_max": max(ys),
        "z_min": min(zs), "z_max": max(zs),
        "size_x": max(xs) - min(xs),
        "size_y": max(ys) - min(ys),
        "size_z": max(zs) - min(zs),
    }


def _cross(a: Tuple[float, ...], b: Tuple[float, ...]) -> Tuple[float, float, float]:
    """向量叉积"""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a: Tuple[float, ...], b: Tuple[float, ...]) -> Tuple[float, float, float]:
    """向量减法"""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _compute_surface_area(facets: List[Tuple]) -> float:
    """计算总表面积（三角面片面积之和）"""
    total = 0.0
    for tri in facets:
        if len(tri) < 3:
            continue
        v1, v2, v3 = tri[0], tri[1], tri[2]
        edge1 = _sub(v2, v1)
        edge2 = _sub(v3, v1)
        cross = _cross(edge1, edge2)
        area = 0.5 * (cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2) ** 0.5
        total += area
    return total


def _compute_volume(facets: List[Tuple]) -> float:
    """计算封闭网格体积（散度定理）

    仅当网格水密时结果有意义。
    """
    total = 0.0
    for tri in facets:
        if len(tri) < 3:
            continue
        v1, v2, v3 = tri[0], tri[1], tri[2]
        # 有符号体积 = v1 · (v2 × v3) / 6
        cross = _cross(v2, v3)
        total += v1[0] * cross[0] + v1[1] * cross[1] + v1[2] * cross[2]
    return abs(total) / 6.0


def _check_watertight(facets: List[Tuple]) -> Tuple[bool, List[str]]:
    """检查网格水密性

    简化检查：每条边应该恰好出现在 2 个面中。
    """
    if not facets:
        return False, ["无面片数据"]

    # 构建边 → 面计数
    edge_count: Dict[Tuple, int] = {}
    for tri in facets:
        if len(tri) < 3:
            continue
        verts = [tri[0], tri[1], tri[2]]
        for i in range(3):
            v_a = verts[i]
            v_b = verts[(i + 1) % 3]
            # 归一化边（小端在前）
            edge = tuple(sorted([v_a, v_b]))
            edge_count[edge] = edge_count.get(edge, 0) + 1

    # 检查非流形边
    boundary_edges = sum(1 for c in edge_count.values() if c != 2)
    non_manifold_edges = sum(1 for c in edge_count.values() if c > 2)

    issues = []
    if boundary_edges > 0:
        issues.append(f"边界边（仅 1 个面共享）: {boundary_edges}")
    if non_manifold_edges > 0:
        issues.append(f"非流形边（>2 个面共享）: {non_manifold_edges}")

    is_watertight = boundary_edges == 0 and non_manifold_edges == 0 and len(facets) > 0
    return is_watertight, issues


def _extract_features(
    facets: List[Tuple],
    vertices: List[Tuple],
    bbox: Optional[Dict[str, float]],
) -> List[GeometryFeature]:
    """提取几何特征"""
    features = []

    # 整体体积特征
    if facets:
        features.append(GeometryFeature(
            type="volume",
            id="vol-0",
            name="main_volume",
            properties={
                "n_facets": len(facets),
                "n_vertices": len(set(vertices)),
            },
        ))

    # 边界盒特征
    if bbox:
        features.append(GeometryFeature(
            type="volume",
            id="bbox-0",
            name="bounding_box",
            properties={
                "size": [bbox["size_x"], bbox["size_y"], bbox["size_z"]],
                "center": [
                    (bbox["x_min"] + bbox["x_max"]) / 2,
                    (bbox["y_min"] + bbox["y_max"]) / 2,
                    (bbox["z_min"] + bbox["z_max"]) / 2,
                ],
            },
        ))

    # 面特征（按法向量聚类 — 简化：按主方向分组）
    if facets and len(facets) > 10:
        features.append(GeometryFeature(
            type="face",
            id="faces-all",
            name="surface_mesh",
            properties={
                "total_facets": len(facets),
            },
        ))

    return features


# ============================================================================
# CADParser: 主解析器
# ============================================================================

class CADParser:
    """CAD 几何文件解析器

    支持 STL（ASCII/二进制）、OBJ 格式。
    提取特征、计算几何属性、检测水密性。
    """

    def __init__(
        self,
        mock_mode: bool = False,
        custom_parser: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        self._mock_mode = mock_mode
        self._custom_parser = custom_parser

    def parse(self, file_path: str, format: Optional[MeshFormat] = None) -> ParsedGeometry:
        """解析几何文件

        Args:
            file_path: 几何文件路径
            format: 文件格式（None=自动检测）

        Returns:
            ParsedGeometry 解析结果

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不支持的格式
        """
        if not self._mock_mode and not os.path.exists(file_path):
            raise FileNotFoundError(f"几何文件不存在: {file_path}")

        if format is None:
            format = detect_format(file_path)

        # Mock 模式
        if self._mock_mode:
            return self._mock_parse(file_path, format)

        # 使用自定义解析器
        if self._custom_parser:
            raw = self._custom_parser(file_path)
        else:
            raw = self._parse_by_format(file_path, format)

        return self._build_geometry(file_path, format, raw)

    def _parse_by_format(self, file_path: str, format: MeshFormat) -> Dict[str, Any]:
        """按格式选择解析器"""
        if format == MeshFormat.STL:
            return _parse_stl(file_path)
        elif format == MeshFormat.OBJ:
            return _parse_obj(file_path)
        elif format in (MeshFormat.STEP, MeshFormat.IGES):
            # STEP/IGES 需要专业库（OpenCASCADE），提供桩实现
            logger.warning("STEP/IGES 格式需要 OpenCASCADE 支持，返回基础信息")
            return {"facets": [], "vertices": [], "normals": []}
        else:
            return {"facets": [], "vertices": [], "normals": []}

    def _build_geometry(
        self,
        file_path: str,
        format: MeshFormat,
        raw: Dict[str, Any],
    ) -> ParsedGeometry:
        """从原始数据构建 ParsedGeometry"""
        facets = raw.get("facets", [])
        vertices = raw.get("vertices", [])

        # 去重顶点用于边界盒计算
        unique_verts = list(set(vertices)) if vertices else []

        bbox = _compute_bounding_box(unique_verts)
        surface_area = _compute_surface_area(facets)
        is_watertight, issues = _check_watertight(facets)

        # 水密时才计算体积
        volume = _compute_volume(facets) if is_watertight else 0.0

        # 修复建议
        repair_needed = []
        if not is_watertight:
            repair_needed.extend(issues)
            repair_needed.append("建议: 执行表面封闭/缝合操作")
        if surface_area == 0.0:
            repair_needed.append("零表面积: 检查几何数据有效性")

        # 提取特征
        features = _extract_features(facets, unique_verts, bbox)

        return ParsedGeometry(
            source_file=file_path,
            format=format,
            features=features,
            bounding_box=bbox,
            surface_area=surface_area,
            volume=volume,
            is_watertight=is_watertight,
            repair_needed=repair_needed,
        )

    def _mock_parse(self, file_path: str, format: MeshFormat) -> ParsedGeometry:
        """Mock 解析（测试用）"""
        # 生成简单的立方体几何
        s = 1.0  # 半边长
        v = [
            (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
            (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s),
        ]
        # 12 个三角面片（6 面 × 2 三角形）
        facets = [
            (v[0], v[1], v[2]), (v[0], v[2], v[3]),  # 底面
            (v[4], v[6], v[5]), (v[4], v[7], v[6]),  # 顶面
            (v[0], v[4], v[5]), (v[0], v[5], v[1]),  # 前面
            (v[2], v[6], v[7]), (v[2], v[7], v[3]),  # 后面
            (v[0], v[3], v[7]), (v[0], v[7], v[4]),  # 左面
            (v[1], v[5], v[6]), (v[1], v[6], v[2]),  # 右面
        ]

        bbox = _compute_bounding_box(v)
        surface_area = _compute_surface_area(facets)
        is_watertight, issues = _check_watertight(facets)
        volume = _compute_volume(facets) if is_watertight else 0.0

        features = _extract_features(facets, v, bbox)

        return ParsedGeometry(
            source_file=file_path,
            format=format,
            features=features,
            bounding_box=bbox,
            surface_area=surface_area,
            volume=volume,
            is_watertight=is_watertight,
            repair_needed=[],
        )


# ============================================================================
# BatchCADParser
# ============================================================================

class BatchCADParser:
    """批量几何解析器

    支持并行解析多个几何文件，汇总统计信息。
    """

    def __init__(self, mock_mode: bool = False):
        self._parser = CADParser(mock_mode=mock_mode)

    def parse_batch(
        self,
        file_paths: List[str],
        formats: Optional[List[MeshFormat]] = None,
    ) -> List[ParsedGeometry]:
        """批量解析几何文件

        Args:
            file_paths: 文件路径列表
            formats: 对应格式列表（None=自动检测）

        Returns:
            解析结果列表
        """
        results = []
        fmts = formats or [None] * len(file_paths)

        for fp, fmt in zip(file_paths, fmts):
            try:
                geom = self._parser.parse(fp, format=fmt)
                results.append(geom)
            except Exception as e:
                logger.error("解析失败: %s - %s", fp, e)
                results.append(ParsedGeometry(
                    source_file=fp,
                    is_watertight=False,
                    repair_needed=[f"解析错误: {e}"],
                ))

        return results

    def get_summary(self, results: List[ParsedGeometry]) -> Dict[str, Any]:
        """汇总统计

        Args:
            results: 解析结果列表

        Returns:
            统计信息
        """
        total = len(results)
        watertight = sum(1 for r in results if r.is_watertight)
        needs_repair = sum(1 for r in results if r.repair_needed)

        return {
            "total": total,
            "watertight": watertight,
            "needs_repair": needs_repair,
            "avg_surface_area": (
                sum(r.surface_area for r in results) / total
                if total > 0 else 0.0
            ),
            "formats": list(set(r.format.value for r in results)),
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def parse_geometry(file_path: str, format: Optional[MeshFormat] = None) -> ParsedGeometry:
    """便捷函数：解析单个几何文件"""
    parser = CADParser()
    return parser.parse(file_path, format=format)


def create_parsed_geometry(
    source_file: str = "",
    format: MeshFormat = MeshFormat.STL,
    features: Optional[List[GeometryFeature]] = None,
    bounding_box: Optional[Dict[str, float]] = None,
    surface_area: float = 0.0,
    volume: float = 0.0,
    is_watertight: bool = True,
    repair_needed: Optional[List[str]] = None,
) -> ParsedGeometry:
    """便捷函数：手动创建 ParsedGeometry"""
    return ParsedGeometry(
        source_file=source_file,
        format=format,
        features=features or [],
        bounding_box=bounding_box,
        surface_area=surface_area,
        volume=volume,
        is_watertight=is_watertight,
        repair_needed=repair_needed or [],
    )
