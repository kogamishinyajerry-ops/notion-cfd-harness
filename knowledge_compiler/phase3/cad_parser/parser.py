#!/usr/bin/env python3
"""
Phase 3: CAD Parser

解析 CAD 几何文件，提取特征，检测水密性，推荐修复方案。

复用策略:
- 文件解析: 委托 Phase 2 CADParser（STL/OBJ/STEP 读取）
- 几何计算: 使用 Phase 3 实现（更精确的体积/水密性检测）
- Phase 3 特有: mock 模式、自定义解析器、批量解析

核心组件:
- CADParser: 几何文件解析器（委托 Phase 2 + Phase 3 几何分析）
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

from knowledge_compiler.phase3.adapter import (
    bounding_box_to_p3,
    p2_parsed_geometry_to_p3,
)
from knowledge_compiler.phase3.schema import (
    GeometryFeature,
    MeshFormat,
    ParsedGeometry,
)

logger = logging.getLogger(__name__)

# ============================================================================
# STL 格式常量
# ============================================================================

STL_HEADER_SIZE = 80
STL_TRIANGLE_COUNT_SIZE = 4
STL_TRIANGLE_SIZE = 50  # 12 (normal) + 36 (3 vertices) + 2 (attribute)

# 水密性检测的浮点容差（顶点合并精度）
_VERTEX_MERGE_TOLERANCE = 1e-8


# ============================================================================
# 文件格式检测
# ============================================================================

def detect_format(file_path: str) -> MeshFormat:
    """根据文件扩展名检测几何格式"""
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
# STL 解析（Phase 3 实现，用于 mock 和自定义解析器场景）
# ============================================================================

def _parse_stl_ascii(content: str) -> Dict[str, Any]:
    """解析 ASCII STL 文件"""
    facets = []
    normals = []
    vertices = []

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
    """解析二进制 STL 文件"""
    if len(data) < STL_HEADER_SIZE + STL_TRIANGLE_COUNT_SIZE:
        return {"facets": [], "normals": [], "vertices": []}

    n_facets = struct.unpack("<I", data[STL_HEADER_SIZE:STL_HEADER_SIZE + STL_TRIANGLE_COUNT_SIZE])[0]
    facets = []
    normals = []
    vertices = []

    offset = STL_HEADER_SIZE + STL_TRIANGLE_COUNT_SIZE
    for _ in range(n_facets):
        if offset + STL_TRIANGLE_SIZE > len(data):
            break
        nx, ny, nz = struct.unpack("<fff", data[offset:offset + 12])
        v1 = struct.unpack("<fff", data[offset + 12:offset + 24])
        v2 = struct.unpack("<fff", data[offset + 24:offset + 36])
        v3 = struct.unpack("<fff", data[offset + 36:offset + 48])

        facets.append((v1, v2, v3))
        normals.append((nx, ny, nz))
        vertices.extend([v1, v2, v3])
        offset += STL_TRIANGLE_SIZE

    return {"facets": facets, "normals": normals, "vertices": vertices}


# ============================================================================
# 几何计算（Phase 3 精确实现）
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
    """计算封闭网格体积（散度定理）"""
    total = 0.0
    for tri in facets:
        if len(tri) < 3:
            continue
        v1, v2, v3 = tri[0], tri[1], tri[2]
        cross = _cross(v2, v3)
        total += v1[0] * cross[0] + v1[1] * cross[1] + v1[2] * cross[2]
    return abs(total) / 6.0


def _quantize_vertex(v: Tuple[float, ...], tolerance: float = _VERTEX_MERGE_TOLERANCE) -> Tuple[float, ...]:
    """将顶点坐标量化到容差网格，用于浮点容差合并"""
    return tuple(round(c / tolerance) * tolerance for c in v)


def _check_watertight(facets: List[Tuple]) -> Tuple[bool, List[str]]:
    """检查网格水密性"""
    if not facets:
        return False, ["无面片数据"]

    edge_count: Dict[Tuple, int] = {}
    for tri in facets:
        if len(tri) < 3:
            continue
        verts = [_quantize_vertex(tri[0]), _quantize_vertex(tri[1]), _quantize_vertex(tri[2])]
        for i in range(3):
            v_a = verts[i]
            v_b = verts[(i + 1) % 3]
            edge = tuple(sorted([v_a, v_b]))
            edge_count[edge] = edge_count.get(edge, 0) + 1

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
# CADParser: 主解析器（委托 Phase 2 + Phase 3 几何分析）
# ============================================================================

class CADParser:
    """CAD 几何文件解析器

    文件读取委托 Phase 2 CADParser，
    几何分析使用 Phase 3 精确实现（体积/水密性）。
    """

    def __init__(
        self,
        mock_mode: bool = False,
        custom_parser: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        self._mock_mode = mock_mode
        self._custom_parser = custom_parser
        # 延迟导入 Phase 2 CADParser（仅在非 mock/非 custom 场景使用）
        self._p2_parser = None

    def _get_p2_parser(self):
        """延迟初始化 Phase 2 CADParser"""
        if self._p2_parser is None:
            from knowledge_compiler.phase2.execution_layer.cad_parser import CADParser as P2CADParser
            self._p2_parser = P2CADParser()
        return self._p2_parser

    def parse(self, file_path: str, format: Optional[MeshFormat] = None) -> ParsedGeometry:
        """解析几何文件

        Args:
            file_path: 几何文件路径
            format: 文件格式（None=自动检测）

        Returns:
            ParsedGeometry 解析结果
        """
        if format is None:
            format = detect_format(file_path)

        # Mock 模式 — 使用 Phase 3 生成模拟数据
        if self._mock_mode:
            return self._mock_parse(file_path, format)

        # 自定义解析器 — 使用 Phase 3 处理
        if self._custom_parser:
            return self._custom_parse(file_path, format)

        # 标准模式 — 委托 Phase 2 进行文件解析
        return self._delegate_to_p2(file_path)

    def _delegate_to_p2(self, file_path: str) -> ParsedGeometry:
        """委托 Phase 2 CADParser 解析文件"""
        # Phase 2 不抛 FileNotFoundError，需要提前检查
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"几何文件不存在: {file_path}")

        p2_parser = self._get_p2_parser()
        p2_geom = p2_parser.parse(file_path, extract_features=True)
        return p2_parsed_geometry_to_p3(p2_geom)

    def _custom_parse(self, file_path: str, format: MeshFormat) -> ParsedGeometry:
        """使用自定义解析器"""
        raw = self._custom_parser(file_path)
        return self._build_geometry(file_path, format, raw)

    def _build_geometry(
        self,
        file_path: str,
        format: MeshFormat,
        raw: Dict[str, Any],
    ) -> ParsedGeometry:
        """从原始数据构建 ParsedGeometry（Phase 3 精确几何分析）"""
        facets = raw.get("facets", [])
        vertices = raw.get("vertices", [])

        unique_verts = list(set(vertices)) if vertices else []

        bbox = _compute_bounding_box(unique_verts)
        surface_area = _compute_surface_area(facets)
        is_watertight, issues = _check_watertight(facets)
        volume = _compute_volume(facets) if is_watertight else 0.0

        repair_needed = []
        if not is_watertight:
            repair_needed.extend(issues)
            repair_needed.append("建议: 执行表面封闭/缝合操作")
        if surface_area == 0.0:
            repair_needed.append("零表面积: 检查几何数据有效性")

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
        s = 1.0
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
    """批量几何解析器"""

    def __init__(self, mock_mode: bool = False):
        self._parser = CADParser(mock_mode=mock_mode)

    def parse_batch(
        self,
        file_paths: List[str],
        formats: Optional[List[MeshFormat]] = None,
    ) -> List[ParsedGeometry]:
        """批量解析几何文件"""
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
        """汇总统计"""
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
