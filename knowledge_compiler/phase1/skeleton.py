#!/usr/bin/env python3
"""
Phase 1 Module 2: Report Skeleton Generator

生成报告骨架，基于TaskSpec和ResultManifest创建ReportDraft。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeLayer,
    KnowledgeStatus,
    ComparisonType,
    PlotSpec,
    MetricSpec,
    SectionSpec,
    AnomalyRule,
    ReportSpec,
    ReportDraft,
    ResultManifest,
    ResultAsset,
    create_report_spec_id,
)


# ============================================================================
# Chart Standards (from chart_standards.md)
# ============================================================================

class ChartStandard:
    """CFD chart rendering standards"""

    # Marker styles for multi-dataset comparison
    MARKERS = {
        "experiment": {"marker": "o", "facecolors": "none", "edgecolors": "blue"},
        "cfd": {"marker": "o", "facecolors": "C0", "edgecolors": "C0"},
        "intermediate": {"marker": "^", "facecolors": "C1"},
        "literature": {"marker": "v", "facecolors": "C2"},
        "other_model": {"marker": "s", "facecolors": "C3"},
        "sensitivity": {"marker": "D", "facecolors": "C4"},
    }

    # Colormap standards
    COLORMAPS = {
        "default": "viridis",
        "pressure": "coolwarm",
        "temperature": "inferno",
        "velocity": "viridis",
        "vorticity": "RdBu",
    }

    # Standard figure sizes
    FIGURE_SIZES = {
        "profile": (8, 6),
        "contour": (10, 8),
        "convergence": (10, 6),
        "comparison": (10, 6),
    }


# ============================================================================
# Report Structure Templates (from ReportSpec v1.1)
# ============================================================================

REPORT_STRUCTURE = {
    "1.0_geometry": {
        "title": "Geometry",
        "description": "Geometric description, dimensions, coordinate system, boundary condition types",
        "required_fields": ["dimensions", "coordinate_system", "boundary_types"],
    },
    "1.1_mesh": {
        "title": "Mesh",
        "description": "Mesh generation tool, algorithm, quality metrics, grid independence",
        "required_fields": ["mesh_tool", "grid_levels", "quality_metrics", "gci_table"],
    },
    "1.2_solver": {
        "title": "Solver Settings",
        "description": "Solver name/version, turbulence model, convergence criteria",
        "required_fields": ["solver_name", "turbulence_model", "convergence_criteria"],
    },
    "1.3_boundary": {
        "title": "Boundary Conditions",
        "description": "Complete boundary condition list with parameter values",
        "required_fields": ["boundary_list", "inlet_conditions", "outlet_conditions"],
    },
    "1.4_results": {
        "title": "Results",
        "description": "Convergence history, field visualization, performance metrics",
        "required_fields": ["convergence_plots", "field_visualizations", "performance_metrics"],
    },
    "1.5_validation": {
        "title": "Validation",
        "description": "Comparison with experimental/analytical data, error metrics",
        "required_fields": ["comparison_plots", "error_metrics", "data_table"],
    },
}


# ============================================================================
# Problem Type Defaults
# ============================================================================

PROBLEM_TYPE_DEFAULTS = {
    ProblemType.INTERNAL_FLOW: {
        "required_plots": [
            PlotSpec(name="velocity_magnitude", plane="xy", colormap="viridis", range="auto"),
            PlotSpec(name="pressure_coefficient", plane="xy", colormap="coolwarm", range="auto"),
            PlotSpec(name="streamlines", plane="xy", colormap="viridis", range="auto"),
        ],
        "required_metrics": [
            MetricSpec(name="max_velocity", unit="m/s", comparison=ComparisonType.DIRECT),
            MetricSpec(name="pressure_drop", unit="Pa", comparison=ComparisonType.DIRECT),
            MetricSpec(name="mass_flow_rate", unit="kg/s", comparison=ComparisonType.RATIO),
        ],
    },
    ProblemType.EXTERNAL_FLOW: {
        "required_plots": [
            PlotSpec(name="pressure_coefficient", plane="surface", colormap="coolwarm", range="auto"),
            PlotSpec(name="wall_shear_stress", plane="surface", colormap="inferno", range="auto"),
            PlotSpec(name="velocity_field", plane="symmetry", colormap="viridis", range="auto"),
        ],
        "required_metrics": [
            MetricSpec(name="drag_coefficient", unit="-", comparison=ComparisonType.RATIO),
            MetricSpec(name="lift_coefficient", unit="-", comparison=ComparisonType.RATIO),
            MetricSpec(name="strouhal_number", unit="-", comparison=ComparisonType.DIRECT),
        ],
    },
    ProblemType.HEAT_TRANSFER: {
        "required_plots": [
            PlotSpec(name="temperature_field", plane="midplane", colormap="inferno", range="auto"),
            PlotSpec(name="heat_flux", plane="wall", colormap="coolwarm", range="auto"),
            PlotSpec(name="nußelt_number", plane="wall", colormap="viridis", range="auto"),
        ],
        "required_metrics": [
            MetricSpec(name="heat_transfer_coefficient", unit="W/(m²K)", comparison=ComparisonType.RATIO),
            MetricSpec(name="total_heat_flux", unit="W", comparison=ComparisonType.DIRECT),
            MetricSpec(name="max_temperature", unit="K", comparison=ComparisonType.DIRECT),
        ],
    },
    ProblemType.MULTIPHASE: {
        "required_plots": [
            PlotSpec(name="volume_fraction", plane="xy", colormap="viridis", range="[0, 1]"),
            PlotSpec(name="interface_topology", plane="3d", colormap="coolwarm", range="auto"),
            PlotSpec(name="velocity_magnitude", plane="xy", colormap="viridis", range="auto"),
        ],
        "required_metrics": [
            MetricSpec(name="interface_area", unit="m²", comparison=ComparisonType.RATIO),
            MetricSpec(name="mass_transfer_rate", unit="kg/s", comparison=ComparisonType.DIRECT),
        ],
    },
    ProblemType.FSI: {
        "required_plots": [
            PlotSpec(name="displacement_field", plane="deformed", colormap="coolwarm", range="auto"),
            PlotSpec(name="von_mises_stress", plane="structure", colormap="inferno", range="auto"),
            PlotSpec(name="fluid_velocity", plane="midplane", colormap="viridis", range="auto"),
        ],
        "required_metrics": [
            MetricSpec(name="max_displacement", unit="m", comparison=ComparisonType.RATIO),
            MetricSpec(name="max_stress", unit="Pa", comparison=ComparisonType.RATIO),
        ],
    },
}


# ============================================================================
# Gate Definitions (Phase 1 Gates)
# ============================================================================

@dataclass
class GateResult:
    """Result of a gate check"""
    gate_id: str
    gate_name: str
    passed: bool
    score: float  # 0-100
    required_score: float
    details: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class Phase1Gates:
    """Phase 1 Gate implementations"""

    @staticmethod
    def p1_g1_field_completeness(
        manifest: ResultManifest,
        problem_type: ProblemType,
    ) -> GateResult:
        """
        G1-P1: Field Completeness Gate

        Checks if required field data is available for the problem type.
        """
        required_assets = {
            ProblemType.INTERNAL_FLOW: ["field", "monitor_point"],
            ProblemType.EXTERNAL_FLOW: ["field", "surface_plot"],
            ProblemType.HEAT_TRANSFER: ["field", "contour_plot"],
            ProblemType.MULTIPHASE: ["field", "line_plot"],
            ProblemType.FSI: ["field", "line_plot"],
        }

        needed_types = required_assets.get(problem_type, ["field"])
        available_types = {a.asset_type for a in manifest.assets}

        missing = [t for t in needed_types if t not in available_types]
        present = [t for t in needed_types if t in available_types]

        score = (len(present) / len(needed_types)) * 100 if needed_types else 100
        passed = score >= 80  # 80% threshold

        warnings = []
        if missing:
            warnings.append(f"Missing asset types: {missing}")

        return GateResult(
            gate_id="G1-P1",
            gate_name="Field Completeness",
            passed=passed,
            score=score,
            required_score=80.0,
            details={
                "required_types": needed_types,
                "available_types": list(available_types),
                "present": present,
                "missing": missing,
            },
            warnings=warnings,
        )

    @staticmethod
    def p1_g2_plot_standards(draft: ReportDraft) -> GateResult:
        """
        G2-P1: Plot Standards Gate

        Checks if plot specifications follow chart_standards.md rules.
        """
        issues = []
        total_checks = 0
        passed_checks = 0

        for plot_spec in draft.plots:
            total_checks += 1

            # Check colormap
            colormap = plot_spec.get("colormap", "")
            if colormap not in ChartStandard.COLORMAPS.values() and colormap != "auto":
                issues.append(f"Plot '{plot_spec.get('name')}': non-standard colormap '{colormap}'")
            else:
                passed_checks += 1

            # Check plane is specified
            if not plot_spec.get("plane"):
                issues.append(f"Plot '{plot_spec.get('name')}': missing plane specification")
            else:
                passed_checks += 1
                total_checks += 1

        score = (passed_checks / total_checks * 100) if total_checks > 0 else 100
        passed = score >= 70  # 70% threshold for plot standards

        return GateResult(
            gate_id="G2-P1",
            gate_name="Plot Standards",
            passed=passed,
            score=score,
            required_score=70.0,
            details={
                "total_plots": len(draft.plots),
                "checks": passed_checks,
                "total_checks": total_checks,
            },
            warnings=issues[:5],  # Limit to first 5 warnings
        )


# ============================================================================
# Report Skeleton Generator
# ============================================================================

class ReportSkeletonGenerator:
    """
    Generate report skeleton from TaskSpec and ResultManifest

    Module 2 of Phase 1: Creates ReportDraft with populated plot/metric slots.
    """

    def __init__(self, report_specs: Optional[List[ReportSpec]] = None):
        """
        Initialize generator

        Args:
            report_specs: Optional list of existing ReportSpecs to match against
        """
        self.report_specs = report_specs or []
        self._spec_index = self._build_spec_index()

    def _build_spec_index(self) -> Dict[str, ReportSpec]:
        """Build index for quick ReportSpec lookup"""
        index = {}
        for spec in self.report_specs:
            # Index by problem type
            key = f"{spec.problem_type.value}_{spec.knowledge_layer.value}"
            index[key] = spec
        return index

    def generate(
        self,
        task_spec: Dict[str, Any],
        manifest: ResultManifest,
        case_id: Optional[str] = None,
    ) -> ReportDraft:
        """
        Generate report skeleton

        Args:
            task_spec: Task specification with problem type and requirements
            manifest: Result manifest from Module 1
            case_id: Optional case identifier

        Returns:
            ReportDraft with populated plot and metric slots
        """
        # Parse problem type
        problem_type_str = task_spec.get("problem_type", "InternalFlow")
        try:
            problem_type = ProblemType(problem_type_str)
        except ValueError:
            problem_type = ProblemType.INTERNAL_FLOW

        # Try to match existing ReportSpec
        matched_spec = self._match_report_spec(problem_type, task_spec)

        # Generate draft ID
        draft_id = f"DRAFT-{uuid.uuid4().hex[:8].upper()}"
        case_id = case_id or manifest.case_name
        task_spec_id = task_spec.get("task_spec_id", "UNKNOWN")

        # Generate plot specifications
        plots = self._generate_plots(
            problem_type,
            manifest,
            matched_spec,
        )

        # Generate metric specifications
        metrics = self._generate_metrics(
            problem_type,
            manifest,
            matched_spec,
        )

        # Generate report structure
        structure = self._generate_structure(
            problem_type,
            manifest,
        )

        # Create draft
        draft = ReportDraft(
            draft_id=draft_id,
            case_id=case_id,
            task_spec_id=task_spec_id,
            report_spec_id=matched_spec.report_spec_id if matched_spec else None,
            plots=plots,
            metrics=metrics,
            structure=structure,
            gates_status={},
        )

        # Run Phase 1 gates
        self._run_gates(draft, manifest, problem_type)

        return draft

    def _match_report_spec(
        self,
        problem_type: ProblemType,
        task_spec: Dict[str, Any],
    ) -> Optional[ReportSpec]:
        """Find matching ReportSpec for problem type"""
        # Prefer Canonical layer specs
        key = f"{problem_type.value}_Canonical"
        if key in self._spec_index:
            return self._spec_index[key]

        # Fall back to Approved specs
        key = f"{problem_type.value}_Approved"
        if key in self._spec_index:
            return self._spec_index[key]

        # Then Candidate
        key = f"{problem_type.value}_Candidate"
        if key in self._spec_index:
            return self._spec_index[key]

        return None

    def _generate_plots(
        self,
        problem_type: ProblemType,
        manifest: ResultManifest,
        matched_spec: Optional[ReportSpec],
    ) -> List[Dict[str, Any]]:
        """Generate plot specifications"""
        plots = []

        # If matched spec exists, use its plots
        if matched_spec and matched_spec.required_plots:
            for plot_spec in matched_spec.required_plots:
                plots.append({
                    "name": plot_spec.name,
                    "plane": plot_spec.plane,
                    "colormap": plot_spec.colormap,
                    "range": plot_spec.range,
                    "source": "report_spec",
                })
        else:
            # Use problem type defaults
            defaults = PROBLEM_TYPE_DEFAULTS.get(problem_type, {})
            for plot_spec in defaults.get("required_plots", []):
                plots.append({
                    "name": plot_spec.name,
                    "plane": plot_spec.plane,
                    "colormap": plot_spec.colormap,
                    "range": plot_spec.range,
                    "source": "default",
                })

        # Augment with available assets from manifest
        available_plots = manifest.get_plot_assets()
        for asset in available_plots:
            # Check if we already have a similar plot
            existing_names = {p["name"] for p in plots}
            asset_name = Path(asset.path).stem

            if asset_name not in existing_names:
                # Infer colormap from asset name
                colormap = "auto"
                if "pressure" in asset_name.lower():
                    colormap = ChartStandard.COLORMAPS["pressure"]
                elif "temperature" in asset_name.lower():
                    colormap = ChartStandard.COLORMAPS["temperature"]
                elif "velocity" in asset_name.lower():
                    colormap = ChartStandard.COLORMAPS["velocity"]
                else:
                    colormap = ChartStandard.COLORMAPS["default"]

                plots.append({
                    "name": asset_name,
                    "plane": "inferred",
                    "colormap": colormap,
                    "range": "auto",
                    "source": "manifest",
                    "asset_path": asset.path,
                })

        return plots

    def _generate_metrics(
        self,
        problem_type: ProblemType,
        manifest: ResultManifest,
        matched_spec: Optional[ReportSpec],
    ) -> List[Dict[str, Any]]:
        """Generate metric specifications"""
        metrics = []

        # If matched spec exists, use its metrics
        if matched_spec and matched_spec.required_metrics:
            for metric_spec in matched_spec.required_metrics:
                metrics.append({
                    "name": metric_spec.name,
                    "unit": metric_spec.unit,
                    "comparison": metric_spec.comparison.value,
                    "source": "report_spec",
                })
        else:
            # Use problem type defaults
            defaults = PROBLEM_TYPE_DEFAULTS.get(problem_type, {})
            for metric_spec in defaults.get("required_metrics", []):
                metrics.append({
                    "name": metric_spec.name,
                    "unit": metric_spec.unit,
                    "comparison": metric_spec.comparison.value,
                    "source": "default",
                })

        return metrics

    def _generate_structure(
        self,
        problem_type: ProblemType,
        manifest: ResultManifest,
    ) -> Dict[str, Any]:
        """Generate report structure based on problem type"""
        structure = {
            "chapters": [],
            "metadata": {
                "problem_type": problem_type.value,
                "solver_type": manifest.solver_type,
                "generated_at": time.time(),
            },
        }

        # Add standard chapters
        for chapter_id, chapter_def in REPORT_STRUCTURE.items():
            chapter = {
                "id": chapter_id,
                "title": chapter_def["title"],
                "description": chapter_def["description"],
                "required_fields": chapter_def["required_fields"],
                "status": "pending",
            }
            structure["chapters"].append(chapter)

        return structure

    def _run_gates(
        self,
        draft: ReportDraft,
        manifest: ResultManifest,
        problem_type: ProblemType,
    ) -> None:
        """Run Phase 1 gates and populate gates_status"""
        # G1-P1: Field Completeness
        g1_result = Phase1Gates.p1_g1_field_completeness(manifest, problem_type)
        draft.gates_status["G1-P1"] = {
            "passed": g1_result.passed,
            "score": g1_result.score,
            "required": g1_result.required_score,
            "warnings": g1_result.warnings,
        }

        # G2-P1: Plot Standards
        g2_result = Phase1Gates.p1_g2_plot_standards(draft)
        draft.gates_status["G2-P1"] = {
            "passed": g2_result.passed,
            "score": g2_result.score,
            "required": g2_result.required_score,
            "warnings": g2_result.warnings,
        }

    def create_report_spec_from_draft(
        self,
        draft: ReportDraft,
        name: str,
        problem_type: ProblemType,
    ) -> ReportSpec:
        """
        Convert a reviewed draft into a ReportSpec

        Called after engineer Teach Mode review.
        """
        spec_id = create_report_spec_id()

        # Convert plots to PlotSpec
        required_plots = []
        for plot_dict in draft.plots:
            required_plots.append(PlotSpec(
                name=plot_dict["name"],
                plane=plot_dict["plane"],
                colormap=plot_dict["colormap"],
                range=plot_dict["range"],
            ))

        # Convert metrics to MetricSpec
        required_metrics = []
        for metric_dict in draft.metrics:
            required_metrics.append(MetricSpec(
                name=metric_dict["name"],
                unit=metric_dict["unit"],
                comparison=ComparisonType(metric_dict["comparison"]),
            ))

        # Create ReportSpec at Raw layer
        spec = ReportSpec(
            report_spec_id=spec_id,
            name=name,
            problem_type=problem_type,
            required_plots=required_plots,
            required_metrics=required_metrics,
            knowledge_layer=KnowledgeLayer.RAW,
            knowledge_status=KnowledgeStatus.DRAFT,
            source_cases=[draft.case_id],
        )

        return spec


# ============================================================================
# Convenience Functions
# ============================================================================

def generate_report_skeleton(
    task_spec: Dict[str, Any],
    manifest: ResultManifest,
    report_specs: Optional[List[ReportSpec]] = None,
    case_id: Optional[str] = None,
) -> ReportDraft:
    """
    Generate report skeleton from task spec and result manifest

    Args:
        task_spec: Task specification
        manifest: Result manifest from Module 1
        report_specs: Optional list of existing ReportSpecs
        case_id: Optional case identifier

    Returns:
        ReportDraft with populated slots
    """
    generator = ReportSkeletonGenerator(report_specs)
    return generator.generate(task_spec, manifest, case_id)


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "ChartStandard",
    "REPORT_STRUCTURE",
    "PROBLEM_TYPE_DEFAULTS",
    "GateResult",
    "Phase1Gates",
    "ReportSkeletonGenerator",
    "generate_report_skeleton",
]
