#!/usr/bin/env python3
"""
Phase 3 Mesh Builder: 网格生成器

支持 OpenFOAM (snappyHexMesh) 和 gmsh 网格生成。
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from knowledge_compiler.phase3.schema import (
    MeshFormat,
    MeshQuality,
    MeshConfig,
    MeshStatistics,
    MeshResult,
    SolverStatus,
)


class MeshBackend(Enum):
    """网格生成后端"""
    SNAPPYHEXMESH = "snappyHexMesh"
    GMSH = "gmsh"
    CFMESHSIM = "cfmesh"


class GeometryType(Enum):
    """几何类型"""
    STL = "stl"
    STEP = "step"
    IGES = "iges"
    OBJ = "obj"
    TRI_SURFACE = "tri_surface"


class MeshBuilder:
    """
    网格生成器

    根据几何配置生成计算网格。
    """

    def __init__(self, backend: MeshBackend = MeshBackend.SNAPPYHEXMESH):
        """
        Initialize the mesh builder

        Args:
            backend: 网格生成后端
        """
        self.backend = backend
        self._running_processes: Dict[str, subprocess.Popen] = {}

    def detect_format(self, geometry_file: str) -> GeometryType:
        """
        检测几何文件格式

        Args:
            geometry_file: 几何文件路径

        Returns:
            几何类型
        """
        path = Path(geometry_file)
        ext = path.suffix.lower().lstrip(".")

        # 映射扩展名到 GeometryType
        ext_to_type = {
            "stl": GeometryType.STL,
            "step": GeometryType.STEP,
            "stp": GeometryType.STEP,
            "iges": GeometryType.IGES,
            "igs": GeometryType.IGES,
            "obj": GeometryType.OBJ,
        }

        return ext_to_type.get(ext, GeometryType.TRI_SURFACE)

    def validate_geometry(self, geometry_file: str) -> Tuple[bool, List[str]]:
        """
        验证几何文件

        Args:
            geometry_file: 几何文件路径

        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        if not os.path.exists(geometry_file):
            errors.append(f"Geometry file not found: {geometry_file}")
            return False, errors

        # 检查文件大小
        size = os.path.getsize(geometry_file)
        if size == 0:
            errors.append("Geometry file is empty")
            return False, errors

        # 检查格式
        geo_type = self.detect_format(geometry_file)

        # STL 格式验证
        if geo_type == GeometryType.STL:
            try:
                with open(geometry_file, "rb") as f:
                    header = f.read(80).decode("ascii", errors="ignore")
                    if "solid" not in header.lower():
                        errors.append("Invalid STL file: missing 'solid' header")
            except Exception as e:
                errors.append(f"Failed to read STL file: {e}")

        return len(errors) == 0, errors

    def build_snappyhexmesh_config(
        self,
        config: MeshConfig,
        output_dir: str,
    ) -> str:
        """
        构建 snappyHexMesh 配置文件

        Args:
            config: 网格配置
            output_dir: 输出目录

        Returns:
            配置文件路径
        """
        output_path = Path(output_dir) / "snappyHexMeshDict"

        # 构建配置
        dict_content = {
            "castellatedMesh": {
                "maxLocalCells": 1000000,
                "minRefinementCells": 10,
                "nCellsBetweenLevels": 3,
                "features": [
                    {
                        "file": f"{config.base_geometry}",
                        "level": config.refinement_levels,
                    }
                ],
            },
            "snap": {
                "implicit": True,
                "tolerance": 1e-6,
                "multiRegion": False,
            },
            "addLayers": {
                "relativeSizes": "Yes",
                "layers": {
                    "nSurfaceLayers": config.n_boundary_layers if config.boundary_layer else 0,
                    "expansionRatio": 1.3,
                    "finalLayerThickness": 0.5,
                    "minThickness": 0.001,
                    "growAngle": 180,
                },
                "featureAngle": 60,
            },
        }

        # 写入配置文件
        import json

        with open(output_path, "w") as f:
            # snappyHexMesh 使用特殊的字典格式
            f.write("/*--------------------------------*- C++ -*----------------------------------*\\\n")
            f.write("| =========                 |                                                |\n")
            f.write("| \\\\      /  F ield         | foamFiles: snappyHexMeshDict                     |\n")
            f.write("|  \\\\    /   Operation       |                                                |\n")
            f.write("|   \\\\  /    And           |                                                |\n")
            f.write("|    \\\\/     M anipulation  |                                                |\n")
            f.write("| \\\\ /                         |                                                |\n")
            f.write("|  \\\\                          |                                                |\n")
            f.write("|   \\\\                         |                                                |\n")
            f.write("|    \\\\                        |                                                |\n")
            f.write("\\*---------------------------------------------------------------------------*/\n")
            f.write("\n")
            f.write("FoamFile\n")
            f.write("{\n")
            f.write("    version     2.0;\n")
            f.write("    format      ascii;\n")
            f.write("    class       dictionary;\n")
            f.write("    location    \"system\";\n")
            f.write("    object      snappyHexMeshDict;\n")
            f.write("}\n")
            f.write("// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //\n")

            # 简化的字典内容
            f.write("\n// Castellated mesh controls\n")
            f.write("castellatedMesh on;\n")

            if config.boundary_layer:
                f.write("\n// Add layers\n")
                f.write("addLayers on;\n")
                f.write(f"nSurfaceLayers {config.n_boundary_layers};\n")

            # 其他配置
            f.write("\n// Geometry\n")
            f.write(f"geometry {{ {Path(config.base_geometry).name} }};\n")

            # 细化级别
            f.write("\n// Refinement levels\n")
            f.write(f"refinementLevels {config.refinement_levels};\n")

            # 最小质量
            f.write("\n// Mesh quality\n")
            f.write(f"minQuality {config.min_quality};\n")

        return str(output_path)

    def build_gmsh_config(
        self,
        config: MeshConfig,
        output_dir: str,
    ) -> str:
        """
        构建 gmsh 配置文件

        Args:
            config: 网格配置
            output_dir: 输出目录

        Returns:
            配置文件路径
        """
        output_path = Path(output_dir) / "mesh.geo"

        with open(output_path, "w") as f:
            f.write("// GMSH geometry file\n")
            f.write(f"// Auto-generated by MeshBuilder\n")
            f.write(f"\n")

            # 加载几何
            if config.format == MeshFormat.STL:
                f.write(f"Merge \"{config.base_geometry}\";\n")

            # 网格尺寸
            f.write(f"\n// Mesh size\n")
            f.write(f"Mesh.CharacteristicLengthMin = {config.target_element_size * 0.5};\n")
            f.write(f"Mesh.CharacteristicLengthMax = {config.target_element_size * 2.0};\n")

            # 算法
            f.write(f"\n// Mesh algorithm\n")
            f.write(f"Mesh.Algorithm = 6;  // Frontal-Delaunay for 2D, Delaunay for 3D\n")
            f.write(f"Mesh.RecombinationAlgorithm = 2;  // 2: full, 1: simple\n")

            # 边界层
            if config.boundary_layer:
                f.write(f"\n// Boundary layers\n")
                f.write(f"Mesh.CharacteristicLengthFromCurvature = 1;\n")

        return str(output_path)

    def generate(
        self,
        config: MeshConfig,
        output_dir: Optional[str] = None,
    ) -> MeshResult:
        """
        生成网格

        Args:
            config: 网格配置
            output_dir: 输出目录

        Returns:
            网格生成结果
        """
        result = MeshResult(status=SolverStatus.PENDING)

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="mesh_")
        result.output_dir = output_dir

        # 验证几何
        valid, errors = self.validate_geometry(config.base_geometry)
        if not valid:
            result.status = SolverStatus.FAILED
            result.error_message = "; ".join(errors)
            return result

        result.status = SolverStatus.RUNNING
        start_time = time.time()

        try:
            if self.backend == MeshBackend.SNAPPYHEXMESH:
                result = self._generate_snappyhexmesh(config, output_dir, result)
            elif self.backend == MeshBackend.GMSH:
                result = self._generate_gmsh(config, output_dir, result)
            else:
                result.error_message = f"Unsupported backend: {self.backend}"
                result.status = SolverStatus.FAILED

        except Exception as e:
            result.status = SolverStatus.FAILED
            result.error_message = str(e)

        # 统计网格
        if result.status == SolverStatus.COMPLETED:
            result.statistics = self._collect_statistics(output_dir)
            result.quality = self._assess_quality(result.statistics)

        return result

    def _generate_snappyhexmesh(
        self,
        config: MeshConfig,
        output_dir: str,
        result: MeshResult,
    ) -> MeshResult:
        """使用 snappyHexMesh 生成网格"""
        # 构建配置
        config_file = self.build_snappyhexmesh_config(config, output_dir)

        # 执行 snappyHexMesh
        cmd = ["snappyHexMesh", "-overwrite", "-case", output_dir]

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=output_dir,
            timeout=300,  # 5 分钟超时
        )

        result.stdout = process.stdout
        result.stderr = process.stderr

        # 检查结果
        mesh_dir = Path(output_dir) / "1"  # snappyHexMesh 输出到 1/ 目录
        if mesh_dir.exists():
            poly_mesh = mesh_dir / "polyMesh"
            if poly_mesh.exists():
                result.status = SolverStatus.COMPLETED
                result.mesh_files = [
                    str(poly_mesh / "points"),
                    str(poly_mesh / "faces"),
                    str(poly_mesh / "owner"),
                    str(poly_mesh / "neighbour"),
                ]
                # 只保留存在的文件
                result.mesh_files = [f for f in result.mesh_files if Path(f).exists()]
            else:
                result.status = SolverStatus.FAILED
                result.error_message = "polyMesh not found in output"
        else:
            result.status = SolverStatus.FAILED
            if process.returncode != 0:
                result.error_message = f"snappyHexMesh failed: {result.stderr[:200]}"
            else:
                result.error_message = "Output directory not created"

        return result

    def _generate_gmsh(
        self,
        config: MeshConfig,
        output_dir: str,
        result: MeshResult,
    ) -> MeshResult:
        """使用 gmsh 生成网格"""
        # 构建配置
        config_file = self.build_gmsh_config(config, output_dir)

        # 执行 gmsh
        output_file = Path(output_dir) / "mesh.msh"
        cmd = [
            "gmsh",
            "-3",  # 3D 网格
            "-o", str(output_file),
            str(config.base_geometry),
        ]

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        result.stdout = process.stdout
        result.stderr = process.stderr

        # 检查结果
        if output_file.exists():
            result.status = SolverStatus.COMPLETED
            result.mesh_files = [str(output_file)]
        else:
            result.status = SolverStatus.FAILED
            result.error_message = f"gmsh failed: {result.stderr[:200]}"

        return result

    def _collect_statistics(self, mesh_dir: str) -> MeshStatistics:
        """
        收集网格统计信息

        Args:
            mesh_dir: 网格目录

        Returns:
            网格统计
        """
        stats = MeshStatistics()

        # 检查 polyMesh 目录
        poly_mesh = Path(mesh_dir) / "1" / "polyMesh"
        if not poly_mesh.exists():
            poly_mesh = Path(mesh_dir) / "constant" / "polyMesh"

        if not poly_mesh.exists():
            return stats

        # 统计点数
        points_file = poly_mesh / "points"
        if points_file.exists():
            with open(points_file) as f:
                # 跳过注释行
                lines = [l for l in f if not l.strip().startswith("//")]
                stats.n_points = len(lines) - 1  # 减去头部行数

        # 统计面数
        faces_file = poly_mesh / "faces"
        if faces_file.exists():
            with open(faces_file) as f:
                lines = [l for l in f if not l.strip().startswith("//")]
                stats.n_faces = len(lines) - 1

        # 估算单元数
        # 对于四面体网格: n_cells ≈ n_points / 5
        # 对于六面体网格: n_cells ≈ n_points / 8
        stats.n_cells = stats.n_points // 6

        return stats

    def _assess_quality(self, stats: MeshStatistics) -> MeshQuality:
        """
        评估网格质量

        Args:
            stats: 网格统计

        Returns:
            质量等级
        """
        if stats.min_quality >= 0.5:
            return MeshQuality.EXCELLENT
        elif stats.min_quality >= 0.3:
            return MeshQuality.GOOD
        elif stats.min_quality >= 0.1:
            return MeshQuality.FAIR
        else:
            return MeshQuality.POOR

    def optimize_geometry(
        self,
        input_file: str,
        output_file: str,
        operations: List[str],
    ) -> bool:
        """
        优化几何文件

        Args:
            input_file: 输入文件
            output_file: 输出文件
            operations: 优化操作列表

        Returns:
            是否成功
        """
        try:
            # 简单实现：复制文件
            # 实际实现可以使用 CADfix、SurfaceMesh 等工具
            import shutil
            shutil.copy2(input_file, output_file)
            return True
        except Exception:
            return False


# ============================================================================
# Convenience Functions
# ============================================================================

def generate_mesh(
    geometry_file: str,
    element_size: float = 1.0,
    backend: MeshBackend = MeshBackend.SNAPPYHEXMESH,
    output_dir: Optional[str] = None,
) -> MeshResult:
    """
    便捷函数：生成网格

    Args:
        geometry_file: 几何文件
        element_size: 目标单元尺寸
        backend: 网格生成后端
        output_dir: 输出目录

    Returns:
        网格生成结果
    """
    from knowledge_compiler.phase3.schema import MeshConfig, MeshFormat

    # 检测格式
    builder = MeshBuilder(backend=backend)
    geo_type = builder.detect_format(geometry_file)

    # 映射 GeometryType 到 MeshFormat
    geo_to_mesh = {
        GeometryType.STL: MeshFormat.STL,
        GeometryType.STEP: MeshFormat.STEP,
        GeometryType.IGES: MeshFormat.IGES,
        GeometryType.OBJ: MeshFormat.OBJ,
        GeometryType.TRI_SURFACE: MeshFormat.STL,  # 默认使用 STL
    }

    mesh_format = geo_to_mesh.get(geo_type, MeshFormat.STL)

    config = MeshConfig(
        format=mesh_format,
        base_geometry=geometry_file,
        target_element_size=element_size,
    )

    return builder.generate(config, output_dir)


def validate_stl(
    stl_file: str,
) -> Tuple[bool, List[str]]:
    """
    便捷函数：验证 STL 文件

    Args:
        stl_file: STL 文件路径

    Returns:
        (是否有效, 错误列表)
    """
    builder = MeshBuilder()
    return builder.validate_geometry(stl_file)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "MeshBuilder",
    "MeshBackend",
    "GeometryType",
    "generate_mesh",
    "validate_stl",
]
