#!/usr/bin/env python3
"""
GoldStandard: ONERA M6 Transonic Wing (SU2-19)

Reference implementation for transonic flow over the ONERA M6 wing
with pressure distribution from Schmitt (1994).

Based on:
- Schmitt, V. & Charpin, F. (1994) "Pressure Distributions on the ONERA M6-Wing
  at Transonic Mach Numbers" AGARD-AR-138, Chapter 4.
- Lesieurre, M. & Coutanceau, C. (1988) transition measurements
- Spalart, P.R. & Allmaras, S.R. (1992) SA turbulence model development

Gold standard provides:
1. Validation template for transonic wing cases
2. Gate validation criteria
3. Literature benchmark data (pressure distribution Cp)
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
# ONERA M6 Wing Constants
# ============================================================================

class OneraM6Constants:
    """Physical constants for ONERA M6 transonic wing case"""

    # Flow conditions (from AGARD-AR-138)
    MACH = 0.84  # Free stream Mach number (transonic)
    ANGLE_OF_ATTACK = 3.06  # degrees

    # Wing geometry (ONERA M6)
    WING_SPAN = 1.1963  # Semi-span (m)
    ROOT_CHORD = 0.64607  # Root chord (m)
    TIP_CHORD = 0.22009  # Tip chord (m)
    ASPECT_RATIO = 3.8  # Wing aspect ratio
    SWEEP_ANGLE = 30.0  # Quarter-chord sweep (degrees)

    # Wing sections for data comparison (from Schmitt)
    # x/c positions and corresponding Cp values (representative)
    SECTION_ETA = [0.15, 0.30, 0.44, 0.65, 0.80, 0.90, 0.95]  # Spanwise stations

    # Shock location (upper surface, eta=0.9)
    SHOCK_XC_UPPER = 0.3  # x/c at shock on upper surface

    # Expected coefficients
    CL = 0.275  # Lift coefficient from AGARD
    CD = 0.0120  # Drag coefficient
    CM = -0.094  # Pitching moment

    # Mesh strategy
    MESH_STRATEGY = "A"


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_onera_m6_spec(
    case_id: str = "onera_m6",
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for ONERA M6 transonic wing case

    Args:
        case_id: Unique case identifier

    Returns:
        Complete ReportSpec with all required plots and metrics
    """
    required_plots = _create_required_plots()
    required_metrics = _create_required_metrics()
    critical_sections = _create_required_sections()

    plot_order = [
        "mach_number_contour",
        "pressure_coefficient_contour",
        "cp_upper_surface",
        "cp_lower_surface",
        "spanwise_efficiency",
    ]

    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"ONERA M6 Transonic Wing (M={OneraM6Constants.MACH}, alpha={OneraM6Constants.ANGLE_OF_ATTACK}deg)",
        problem_type=ProblemType.EXTERNAL_FLOW,
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
        name="mach_number_contour",
        plane="domain",
        colormap="viridis",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="pressure_coefficient_contour",
        plane="domain",
        colormap="coolwarm",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="cp_upper_surface",
        plane="spanwise",
        colormap="RdBu",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="cp_lower_surface",
        plane="spanwise",
        colormap="coolwarm",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="spanwise_efficiency",
        plane="wing",
        colormap="jet",
        range="auto",
    ))

    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    metrics.append(MetricSpec(
        name="lift_coefficient_cl",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="drag_coefficient_cd",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="shock_position_xc",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    sections.append(SectionSpec(
        name="root_section",
        type="section",
        position={"eta": 0.15},
    ))

    sections.append(SectionSpec(
        name="mid_section",
        type="section",
        position={"eta": 0.65},
    ))

    sections.append(SectionSpec(
        name="tip_section",
        type="section",
        position={"eta": 0.90},
    ))

    sections.append(SectionSpec(
        name="wing_surface",
        type="wall",
        position={},
    ))

    return sections


# ============================================================================
# Expected Literature Benchmark Data
# ============================================================================

def get_expected_pressure_distribution() -> Dict[str, Any]:
    """
    Get expected pressure distribution from Schmitt (1994) ONERA M6 data.

    Returns:
        Dictionary with pressure coefficients and reference data
    """
    return {
        "mach": OneraM6Constants.MACH,
        "angle_of_attack_deg": OneraM6Constants.ANGLE_OF_ATTACK,
        "lift_coefficient_cl": OneraM6Constants.CL,
        "drag_coefficient_cd": OneraM6Constants.CD,
        "pitching_moment_cm": OneraM6Constants.CM,
        "shock_position_xc_upper": OneraM6Constants.SHOCK_XC_UPPER,
        "spanwise_stations": OneraM6Constants.SECTION_ETA,
        "literature_source": "Schmitt & Charpin (1994) AGARD-AR-138",
        "secondary_source": "Spalart-Allmaras (1992) for turbulence closure",
        "notes": "Upper surface shows lambda shock at inboard stations, regular shock near tip",
        " Cp data available at eta = 0.15, 0.30, 0.44, 0.65, 0.80, 0.90, 0.95",
    }


# ============================================================================
# Mesh Information
# ============================================================================

def get_mesh_info() -> Dict[str, Any]:
    """
    Get mesh metadata for ONERA M6 wing case.

    Returns:
        Dictionary with mesh strategy and parameters
    """
    return {
        "mesh_strategy": "A",
        "mesh_type": "unstructured_volume",
        "wing_span": OneraM6Constants.WING_SPAN,
        "root_chord": OneraM6Constants.ROOT_CHORD,
        "tip_chord": OneraM6Constants.TIP_CHORD,
        "refinement_zones": [
            {"zone": "leading_edge", "resolution": 0.001},
            {"zone": "trailing_edge", "resolution": 0.002},
            {"zone": "shock_region", "resolution": 0.005},
        ],
        "notes": "Unstructured mesh with surface refinement on wing and shock region",
    }


# ============================================================================
# Solver Configuration
# ============================================================================

def get_solver_config() -> Dict[str, Any]:
    """
    Get solver configuration for ONERA M6 wing case.

    Returns:
        Dictionary with solver parameters
    """
    return {
        "solver_name": "SU2_CFD",
        "equation_system": "Navier-Stokes",
        "turbulence_model": "SA",
        "mach_number": OneraM6Constants.MACH,
        "angle_of_attack_deg": OneraM6Constants.ANGLE_OF_ATTACK,
        "gas_gamma": 1.4,
        "spatial_discretization": "AUSM+",
        "temporal_discretization": "Runge-Kutta",
        "cfl_number": 0.6,
        "convergence_criteria": {"max_iterations": 10000, "residual_tolerance": 1e-7},
    }


# ============================================================================
# Gate Validation
# ============================================================================

class OneraM6GateValidator:
    """
    Gate validator for ONERA M6 transonic wing gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_onera_m6_spec()

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
        if "lift_coefficient_cl" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: lift_coefficient_cl")

        results["details"]["metric_coverage"] = len(gold_metric_names & actual_metric_names) / len(gold_metric_names)

        return results


# ============================================================================
# GoldStandard Auto-Registration
# ============================================================================

WHITELIST_ID = "SU2-19"


def register(registry: "GoldStandardRegistry") -> None:
    """Register this GoldStandard case with the global registry."""
    registry.register(
        case_id="onera_m6",
        whitelist_id=WHITELIST_ID,
        spec_factory=create_onera_m6_spec,
        validator_class=OneraM6GateValidator,
        reference_fn=get_expected_pressure_distribution,
        mesh_info_fn=get_mesh_info,
        solver_config_fn=get_solver_config,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OneraM6Constants",
    "create_onera_m6_spec",
    "OneraM6GateValidator",
    "get_expected_pressure_distribution",
    "get_mesh_info",
    "get_solver_config",
    "register",
]
