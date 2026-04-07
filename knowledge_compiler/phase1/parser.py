#!/usr/bin/env python3
"""
Phase 1 Module 1: Result Directory Parser

识别求解器类型并解析目录结构，提取可用的后处理素材。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from knowledge_compiler.phase1.schema import (
    ResultManifest,
    ResultAsset,
    ProblemType,
)


# ============================================================================
# Solver Type Detection
# ============================================================================

class SolverType:
    """CFD solver type identifiers"""
    OPENFOAM = "openfoam"
    FLUENT = "fluent"
    STAR_CCM_PLUS = "starccm+"
    SU2 = "su2"
    CONVERGE = "converge"
    UNKNOWN = "unknown"

    @classmethod
    def detect(cls, directory: Path | str) -> str:
        """
        Detect solver type from directory structure

        Args:
            directory: Path to result directory

        Returns:
            Solver type identifier
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return cls.UNKNOWN

        # Check for OpenFOAM signatures
        if (dir_path / "0.org" / "U" / "p").exists() or \
           (dir_path / "0" / "U" / "p").exists():
            return cls.OPENFOAM

        # Check for Fluent signatures (.cas and .dat files)
        if list(dir_path.glob("*.cas")) or list(dir_path.glob("*.dat")):
            return cls.FLUENT

        # Check for SU2 signatures
        if (dir_path / "solution.dat").exists() or \
           (dir_path / "restart_dat.0").exists():
            return cls.SU2

        # Check for CONVERGE signatures
        if (dir_path / "converge.dat").exists() or \
           (dir_path / "post.cnv").exists():
            return cls.CONVERGE

        # Check for Star-CCM+ signatures
        if (dir_path / "ccm").exists() or \
           list(dir_path.glob("*.ccm")):
            return cls.STAR_CCM_PLUS

        return cls.UNKNOWN


# ============================================================================
# Asset Type Detection
# ============================================================================

class AssetType:
    """Categorize result files by type"""

    FIELD_DATA = "field"  # Field data ( probes, sampling points)
    LINE_PLOT = "line_plot"  # Line plots (XY data)
    CONTOUR_PLOT = "contour_plot"  # Contour plots
    SURFACE_PLOT = "surface_plot"  # 3D surface plots
    MESH = "mesh"  # Mesh geometry
    RESIDUAL_FILE = "residual_file"  # Residual convergence history
    LOG_FILE = "log_file"  # Solver log
    GEOMETRY = "geometry"  # Geometry/mesh files
    SNAPSHOT = "snapshot"  # Visualization snapshots (images)

    @classmethod
    def classify(cls, file_path: Path, solver_type: str) -> Optional[str]:
        """
        Classify a file into asset type

        Args:
            file_path: Path to file
            solver_type: Detected solver type

        Returns:
            Asset type or None
        """
        if not file_path.is_file():
            return None

        name = file_path.name.lower()
        stem = file_path.stem.lower()

        # Field/probe data
        if stem.startswith("probe") or \
           name.startswith("U") or name.startswith("V") or \
           name.startswith("p") or \
           "probe" in stem or "sample" in stem:
            return cls.FIELD_DATA

        # Residual files
        if "residual" in stem or "convergence" in stem or name == "solverLog":
            return cls.RESIDUAL_FILE

        # Line plots
        if xy in file_path.read_text()[:1000] if file_path.suffix == ".dat" else False:
            # Simple heuristic: .dat with XY in first 1KB
            return cls.LINE_PLOT

        # Contour/Surface plots
        if name.endswith(".png") or name.endswith(".jpg") or \
           name.endswith(".svg"):
            # Could be line plot, contour, or surface
            if "xy" in stem or "line" in stem:
                return cls.LINE_PLOT
            elif "contour" in stem or "surface" in stem or "wall" in stem:
                return cls.CONTOUR_PLOT
            else:
                return cls.SURFACE_PLOT

        # Mesh files
        if name.endswith(".vtk") or name.endswith(".stl") or \
           name.endswith(".msh") or name.endswith(".obj"):
            return cls.MESH

        # Geometry
        if name.endswith(".geo") or name.endswith(".stl") or \
           name.endswith(".gmv"):
            return cls.GEOMETRY

        # Logs
        if name.endswith(".log") or stem == "log":
            return cls.LOG_FILE

        # Snapshots
        if name.endswith(".png") or name.endswith(".jpg"):
            return cls.SNAPSHOT

        return None


# ============================================================================
# Result Directory Parser
# ============================================================================

class ResultDirectoryParser:
    """
    Parser for CFD solver result directories

    Scans result directory, identifies solver type, and catalogs
    all available assets for report generation.
    """

    def __init__(self):
        self._solver_patterns = {
            "openfoam": self._parse_openfoam,
            "fluent": self._parse_fluent,
            "su2": self._parse_su2,
            "converge": self._parse_converge,
        }

    def parse(
        self,
        result_dir: Path | str,
        case_name: Optional[str] = None,
    ) -> ResultManifest:
        """
        Parse result directory and generate manifest

        Args:
            result_dir: Path to result directory
            case_name: Optional case name

        Returns:
            ResultManifest with all discovered assets
        """
        result_path = Path(result_dir)
        case_name = case_name or result_path.name

        # Detect solver type
        solver_type = SolverType.detect(result_path)

        # Parse using solver-specific handler
        assets = []
        if solver_type in self._solver_patterns:
            assets = self._solver_patterns[solver_type](result_path)
        else:
            # Generic parsing
            assets = self._parse_generic(result_path)

        return ResultManifest(
            solver_type=solver_type,
            case_name=case_name,
            result_root=str(result_path),
            assets=assets,
        )

    def _parse_openfoam(self, result_path: Path) -> List[ResultAsset]:
        """Parse OpenFOAM result directory"""
        assets = []

        # Common OpenFOAM directories/files
        for time_step in result_path.glob("[0-9]*"):
            if time_step.is_dir():
                # Check for field data
                for field_file in time_step.glob("*"):
                    assets.append(ResultAsset(
                        asset_type="field",
                        path=str(field_file.relative_to(result_path)),
                    ))

        # Check for processing directories
        proc_dir = result_path / "postProcessing"
        if proc_dir.exists():
            for plot_file in proc_dir.rglob("*.png"):
                assets.append(ResultAsset(
                    asset_type="snapshot",
                    path=str(plot_file.relative_to(result_path)),
                ))

        # Check for residual files
        for residual_file in result_path.glob("*residual*"):
            assets.append(ResultAsset(
                asset_type="residual_file",
                path=str(residual_file.relative_to(result_path)),
            ))

        return assets

    def _parse_fluent(self, result_path: Path) -> List[ResultAsset]:
        """Parse Fluent result directory"""
        assets = []

        # Fluent data files
        for data_file in result_path.glob("*.dat"):
            assets.append(ResultAsset(
                asset_type="line_plot",
                path=str(data_file.relative_to(result_path)),
            ))

        # Case files
        for case_file in result_path.glob("*.cas"):
            assets.append(ResultAsset(
                asset_type="snapshot",
                path=str(case_file.relative_to(result_path)),
            ))

        return assets

    def _parse_su2(self, result_path: Path) -> List[ResultAsset]:
        """Parse SU2 result directory"""
        assets = []

        # Solution data
        solution_file = result_path / "solution.dat"
        if solution_file.exists():
            assets.append(ResultAsset(
                asset_type="field",
                path=str(solution_file.relative_to(result_path)),
            ))

        # Restart files
        for restart_file in result_path.glob("restart_dat*"):
            assets.append(ResultAsset(
                asset_type="log_file",
                path=str(restart_file.relative_to(result_path)),
            ))

        return assets

    def _parse_converge(self, result_path: Path) -> List[ResultAsset]:
        """Parse CONVERGE result directory"""
        assets = []

        # Convergence data
        conv_file = result_path / "converge.dat"
        if conv_file.exists():
            assets.append(ResultAsset(
                asset_type="residual_file",
                path=str(conv_file.relative_to(result_path)),
            ))

        # Plot files
        for plot_file in result_path.glob("*.png"):
            assets.append(ResultAsset(
                asset_type="snapshot",
                path=str(plot_file.relative_to(result_path)),
            ))

        return assets

    def _parse_generic(self, result_path: Path) -> List[ResultAsset]:
        """Generic parsing for unknown solvers"""
        assets = []

        # Collect all files
        for file_path in result_path.rglob("*"):
            if file_path.is_file():
                assets.append(ResultAsset(
                    asset_type="snapshot",
                    path=str(file_path.relative_to(result_path)),
                ))

        return assets

    def detect_problem_type(
        self,
        task_spec: Dict[str, Any],
        result_path: Path,
    ) -> ProblemType:
        """
        Detect problem type from task spec and result directory

        Args:
            task_spec: Task specification
            result_path: Path to result directory

        Returns:
            Detected ProblemType
        """
        # Use task spec if available
        problem_type_str = task_spec.get("problem_type")
        if problem_type_str:
            try:
                return ProblemType(problem_type_str)
            except ValueError:
                pass

        # Heuristics based on directory name and contents
        dir_name = result_path.name.lower()

        if any(k in dir_name for k in ["heat", "thermal", "temperature"]):
            return ProblemType.HEAT_TRANSFER

        if any(k in dir_name for k in ["multiphase", "multi", "phase"]):
            return ProblemType.MULTIPHASE

        if any(k in dir_name for k in ["fsi", "free", "surface", "cavitation"]):
            return ProblemType.FSI

        # Default to internal flow
        return ProblemType.INTERNAL_FLOW


# ============================================================================
# Convenience Functions
# ============================================================================

def parse_result_directory(
    result_dir: Path | str,
    case_name: Optional[str] = None,
) -> ResultManifest:
    """
    Parse result directory and generate manifest

    Args:
        result_dir: Path to result directory
        case_name: Optional case name

    Returns:
        ResultManifest with all discovered assets
    """
    parser = ResultDirectoryParser()
    return parser.parse(result_dir, case_name)


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "SolverType",
    "ResultDirectoryParser",
    "parse_result_directory",
]
