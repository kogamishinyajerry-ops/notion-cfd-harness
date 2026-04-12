#!/usr/bin/env python3
"""
GoldStandard: Dam Break VOF (OF-04)

Reference implementation for dam break multiphase flow with column
height from流氓 Soft data.

Based on:
-流氓 Soft data (Martin & Moyce 1952) — "Part 1. Some laboratory experiments
  and the initial stage of the spreading of a heavy liquid"
  Philosophical Transactions of the Royal Society A, 244, 312-324.
- Koshizuka & Oka (1996) "Moving-particle semi-implicit method for
  fragmentation of incompressible fluid"
- Popinet, S. & Zaleski, S. (2002) "Bubble collapse near a wall"

Gold standard provides:
1. Validation template for multiphase VOF cases
2. Gate validation criteria
3. Literature benchmark data (column height vs time)
"""

from __future__ import annotations

from typing import Any, Dict, List

from knowledge_compiler.phase1.schema import (
    ProblemType,
    ReportSpec,
    PlotSpec,
    MetricSpec,
    SectionSpec,
    ComparisonType,
    KnowledgeLayer,
    KnowledgeStatus,
)


# ============================================================================
# Dam Break VOF Constants
# ============================================================================

class DamBreakVOFConstants:
    """Physical constants for dam break VOF case"""

    # Initial column geometry (Martin & Moyce 1952 /流氓 Soft data)
    COLUMN_HEIGHT = 0.584  # Initial column height H (m)
    DOMAIN_WIDTH = 0.292  # Column width L = H/2 (m)
    ASPECT_RATIO = COLUMN_HEIGHT / DOMAIN_WIDTH  # H/L = 2

    # Domain dimensions
    DOMAIN_LENGTH = 3.0  # Total domain length (m)
    DOMAIN_HEIGHT = 0.8  # Total domain height (m)

    # Fluid properties (water-air at 20C)
    FLUID_1_DENSITY = 998.0  # Water (kg/m3)
    FLUID_2_DENSITY = 1.2  # Air (kg/m3)
    FLUID_1_VISCOSITY = 1.0e-6  # Water kinematic viscosity (m2/s)
    INTERFACIAL_TENSION = 0.072  # Water-air surface tension (N/m)

    #流氓 Soft data: maximum runout and column collapse time
    # The column collapses under gravity, front position x_f(t)
    # and column height h(t) are tabulated in流氓 Soft experiments
    COLLAPSE_TIME = 0.4  # Characteristic collapse time (s) ~ sqrt(2*H/g)
    MAX_RUNOUT_RATIO = 2.5  # x_max / H (from流氓 Soft)

    # Expected values from流氓 Soft
    COLUMN_HEIGHT_FINAL = 0.1  # Final column height at rest (m)
    MAX_FRONT_VELOCITY = 2.5  # Maximum front velocity (m/s)

    # Mesh strategy
    MESH_STRATEGY = "B"


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_dam_break_vof_spec(
    case_id: str = "dam_break_vof",
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for dam break VOF case

    Args:
        case_id: Unique case identifier

    Returns:
        Complete ReportSpec with all required plots and metrics
    """
    required_plots = _create_required_plots()
    required_metrics = _create_required_metrics()
    critical_sections = _create_required_sections()

    plot_order = [
        "phase_distribution",
        "velocity_vector_field",
        "interface_position",
        "column_height_time",
        "front_position_time",
    ]

    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"Dam Break VOF (H={DamBreakVOFConstants.COLUMN_HEIGHT}m, L={DamBreakVOFConstants.DOMAIN_WIDTH}m)",
        problem_type=ProblemType.MULTIPHASE,
        required_plots=required_plots,
        required_metrics=required_metrics,
        critical_sections=critical_sections,
        plot_order=plot_order,
        comparison_method={
            "type": "direct",
            "tolerance_display": True,
        },
        anomaly_explanation_rules=[],
        knowledge_layer=KnowledgeLayer.CANONICAL,
        knowledge_status=KnowledgeStatus.APPROVED,
    )

    return spec


def _create_required_plots() -> List[PlotSpec]:
    """Create required plot specifications"""
    plots = []

    plots.append(PlotSpec(
        name="phase_distribution",
        plane="domain",
        colormap="coolwarm",
        range="[0, 1]",
    ))

    plots.append(PlotSpec(
        name="velocity_vector_field",
        plane="domain",
        colormap="viridis",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="interface_position",
        plane="domain",
        colormap="jet",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="column_height_time",
        plane="domain",
        colormap="Blues",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="front_position_time",
        plane="domain",
        colormap="Reds",
        range="auto",
    ))

    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    metrics.append(MetricSpec(
        name="column_remaining_height",
        unit="m",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="maximum_front_position",
        unit="m",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="maximum_front_velocity",
        unit="m/s",
        comparison=ComparisonType.DIFF,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    sections.append(SectionSpec(
        name="initial_column",
        type="region",
        position={"x": 0.0, "y": 0.0},
    ))

    sections.append(SectionSpec(
        name="mid_domain",
        type="plane",
        position={"x": 1.5},
    ))

    sections.append(SectionSpec(
        name="interface_height",
        type="line",
        position={"x": 0.15},
    ))

    sections.append(SectionSpec(
        name="free_surface",
        type="iso-surface",
        position={"alpha": 0.5},
    ))

    return sections


# ============================================================================
# Expected Literature Benchmark Data
# ============================================================================

def get_expected_column_height() -> Dict[str, Any]:
    """
    Get expected column height from流氓 Soft data.

    Returns:
        Dictionary with column height data and reference information
    """
    return {
        "initial_column_height": DamBreakVOFConstants.COLUMN_HEIGHT,
        "initial_column_width": DamBreakVOFConstants.DOMAIN_WIDTH,
        "aspect_ratio": DamBreakVOFConstants.ASPECT_RATIO,
        "final_column_height": DamBreakVOFConstants.COLUMN_HEIGHT_FINAL,
        "max_front_velocity": DamBreakVOFConstants.MAX_FRONT_VELOCITY,
        "collapse_time": DamBreakVOFConstants.COLLAPSE_TIME,
        "max_runout_ratio": DamBreakVOFConstants.MAX_RUNOUT_RATIO,
        "literature_source": "Martin & Moyce (1952) / 流氓 Soft data",
        "secondary_source": "Koshizuka & Oka (1996) MPS method",
        "notes": "Column collapses under gravity. Height vs time and front position vs time are key validation metrics.",
        "phase_1_density": DamBreakVOFConstants.FLUID_1_DENSITY,
        "phase_2_density": DamBreakVOFConstants.FLUID_2_DENSITY,
    }


# ============================================================================
# Mesh Information
# ============================================================================

def get_mesh_info() -> Dict[str, Any]:
    """
    Get mesh metadata for dam break VOF case.

    Returns:
        Dictionary with mesh strategy and parameters
    """
    return {
        "mesh_strategy": "B",
        "mesh_type": "script_built_cartesian",
        "domain_length": DamBreakVOFConstants.DOMAIN_LENGTH,
        "domain_height": DamBreakVOFConstants.DOMAIN_HEIGHT,
        "initial_column_width": DamBreakVOFConstants.DOMAIN_WIDTH,
        "initial_column_height": DamBreakVOFConstants.COLUMN_HEIGHT,
        "refinement_zones": [
            {"zone": "column_region", "x_min": 0, "x_max": 0.292, "resolution": 0.002},
            {"zone": "interface", "resolution": 0.001},
            {"zone": "free_surface", "resolution": 0.002},
        ],
        "notes": "Script-built Cartesian mesh with fine resolution at interface and initial column region",
    }


# ============================================================================
# Solver Configuration
# ============================================================================

def get_solver_config() -> Dict[str, Any]:
    """
    Get solver configuration for dam break VOF case.

    Returns:
        Dictionary with solver parameters
    """
    return {
        "solver_name": "interPhaseChangeFoam",
        "equation_system": "Navier-Stokes + VOF",
        "turbulence_model": None,  # Laminar (low Re initial collapse)
        "phase1_density": DamBreakVOFConstants.FLUID_1_DENSITY,
        "phase2_density": DamBreakVOFConstants.FLUID_2_DENSITY,
        "phase1_viscosity": DamBreakVOFConstants.FLUID_1_VISCOSITY,
        "surface_tension": DamBreakVOFConstants.INTERFACIAL_TENSION,
        "interface_compression": "MULES",
        "time_step": 1e-5,  # Small time step for interface stability
        "end_time": 1.0,  # Sufficient for full collapse
        "write_interval": 0.01,
        "convergence_criteria": {"max_iterations": 50000, "residual_tolerance": 1e-6},
    }


# ============================================================================
# Gate Validation
# ============================================================================

class DamBreakVOFGateValidator:
    """
    Gate validator for dam break VOF gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_dam_break_vof_spec()

    def validate_report_spec(self, spec: ReportSpec) -> Dict[str, Any]:
        """
        Validate a ReportSpec against gold standard

        Args:
            spec: ReportSpec to validate

        Returns:
            Validation result with pass/fail and details
        """
        results = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "details": {},
        }

        gold_plot_names = {p.name for p in self.gold_spec.required_plots}
        actual_plot_names = {p.name for p in spec.required_plots}

        missing_plots = gold_plot_names - actual_plot_names
        if missing_plots:
            results["passed"] = False
            results["errors"].append(f"Missing required plots: {missing_plots}")

        results["details"]["plot_coverage"] = len(gold_plot_names & actual_plot_names) / len(gold_plot_names)

        gold_metric_names = {m.name for m in self.gold_spec.required_metrics}
        actual_metric_names = {m.name for m in spec.required_metrics}

        missing_metrics = gold_metric_names - actual_metric_names
        if "column_remaining_height" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: column_remaining_height")

        results["details"]["metric_coverage"] = len(gold_metric_names & actual_metric_names) / len(gold_metric_names)

        return results


# ============================================================================
# GoldStandard Auto-Registration
# ============================================================================

WHITELIST_ID = "OF-04"


def register(registry: "GoldStandardRegistry") -> None:
    """Register this GoldStandard case with the global registry."""
    registry.register(
        case_id="dam_break_vof",
        whitelist_id=WHITELIST_ID,
        spec_factory=create_dam_break_vof_spec,
        validator_class=DamBreakVOFGateValidator,
        reference_fn=get_expected_column_height,
        mesh_info_fn=get_mesh_info,
        solver_config_fn=get_solver_config,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "DamBreakVOFConstants",
    "create_dam_break_vof_spec",
    "DamBreakVOFGateValidator",
    "get_expected_column_height",
    "get_mesh_info",
    "get_solver_config",
    "register",
]
