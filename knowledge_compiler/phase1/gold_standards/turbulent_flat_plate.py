#!/usr/bin/env python3
"""
GoldStandard: Turbulent Flat Plate (SU2-09)

Reference implementation for turbulent boundary layer on a flat plate
with skin friction from Schlichting correlation.

Based on:
- Schlichting, H. (1979) Boundary-Layer Theory, 7th ed.
  Chapter XII — Turbulent Boundary Layers
- White, F.M. (2006) Viscous Fluid Flow, 3rd ed.
- Pohlhausen (1921) approximate solution for turbulent flat plate

Gold standard provides:
1. Validation template for turbulent flat plate cases
2. Gate validation criteria
3. Literature benchmark data (skin friction coefficient)
"""

from __future__ import annotations

import math
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
# Turbulent Flat Plate Constants
# ============================================================================

class TurbulentFlatPlateConstants:
    """Physical constants for turbulent flat plate case"""

    # Flow conditions
    REYNOLDS = 1.0e6  # Rex = rho*U*x/mu at x=1m
    PLATE_LENGTH = 1.0  # Length of flat plate (m)
    FREE_STREAM_VELOCITY = 1.0  # U_inf (m/s)

    # Schlichting correlation parameters (turbulent flat plate, 0 < Rex < 10^9)
    # Local skin friction: Cf_x = 0.026 * Rex_x^(-1/7)
    SCHLICHTING_EXPONENT = -1/7
    SCHLICHTING_COEFFICIENT = 0.026

    # Average skin friction (integrated over plate length)
    # Cf_bar = 0.036 * Re_L^(-1/5)
    AVERAGE_CF_EXPONENT = -1/5
    AVERAGE_CF_COEFFICIENT = 0.036

    # Blasius-like solution constant for turbulent layer
    BLASIUS_CF = 0.0592 * REYNOLDS ** (-1/5)  # Average Cf at Re=10^6

    # Transition (user may specify)
    TRANSITION_REYNOLDS = 5.0e5  # Critical Rex for transition

    # Mesh strategy
    MESH_STRATEGY = "A"


# ============================================================================
# Schlichting Skin Friction Computation
# ============================================================================

def compute_schlichting_cf_local(reynolds_x: float) -> float:
    """
    Compute local skin friction coefficient from Schlichting correlation.

    Cf_x = 0.026 * Rex^(-1/7)  [valid for 10^6 < Rex < 10^9]

    Args:
        reynolds_x: Local Reynolds number (rho*U*x/mu)

    Returns:
        Local skin friction coefficient Cf_x
    """
    if reynolds_x < 1e6:
        raise ValueError(f"Reynolds {reynolds_x:.0e} below Schlichting range (Rex > 10^6)")
    return 0.026 * (reynolds_x ** (-1/7))


def compute_schlichting_cf_average(reynolds_l: float) -> float:
    """
    Compute average skin friction coefficient from Schlichting correlation.

    Cf_bar = 0.036 * Re_L^(-1/5)  [integrated over plate length]

    Args:
        reynolds_l: Reynolds number at plate end (rho*U*L/mu)

    Returns:
        Average skin friction coefficient Cf_bar
    """
    return 0.036 * (reynolds_l ** (-1/5))


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_turbulent_flat_plate_spec(
    case_id: str = "turbulent_flat_plate",
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for turbulent flat plate case

    Args:
        case_id: Unique case identifier

    Returns:
        Complete ReportSpec with all required plots and metrics
    """
    required_plots = _create_required_plots()
    required_metrics = _create_required_metrics()
    critical_sections = _create_required_sections()

    plot_order = [
        "velocity_contour",
        "boundary_layer_profile",
        "skin_friction_coefficient",
        "velocity_defect_profile",
        "reynolds_stress_contour",
    ]

    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"Turbulent Flat Plate (Re={TurbulentFlatPlateConstants.REYNOLDS:.0e})",
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
        name="velocity_contour",
        plane="domain",
        colormap="viridis",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="boundary_layer_profile",
        plane="x=0.5",
        colormap="jet",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="skin_friction_coefficient",
        plane="wall",
        colormap="coolwarm",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="velocity_defect_profile",
        plane="x=0.8",
        colormap="RdBu",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="reynolds_stress_contour",
        plane="domain",
        colormap="Blues",
        range="auto",
    ))

    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    metrics.append(MetricSpec(
        name="skin_friction_coefficient_cf",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="boundary_layer_height_delta99",
        unit="m",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="displacement_thickness_delta_star",
        unit="m",
        comparison=ComparisonType.DIFF,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    sections.append(SectionSpec(
        name="leading_edge",
        type="plane",
        position={"x": 0.0},
    ))

    sections.append(SectionSpec(
        name="mid_plate",
        type="plane",
        position={"x": 0.5},
    ))

    sections.append(SectionSpec(
        name="trailing_edge",
        type="plane",
        position={"x": 1.0},
    ))

    sections.append(SectionSpec(
        name="plate_surface",
        type="wall",
        position={"y": 0.0},
    ))

    return sections


# ============================================================================
# Expected Literature Benchmark Data
# ============================================================================

def get_expected_skin_friction() -> Dict[str, Any]:
    """
    Get expected skin friction from Schlichting correlation.

    Returns:
        Dictionary with skin friction coefficients and reference data
    """
    reynolds = TurbulentFlatPlateConstants.REYNOLDS
    reynolds_l = reynolds  # Plate length = 1m

    cf_local = compute_schlichting_cf_local(reynolds_l)
    cf_average = compute_schlichting_cf_average(reynolds_l)

    return {
        "reynolds_number": reynolds,
        "reynolds_number_end": reynolds_l,
        "local_cf_x": cf_local,
        "average_cf": cf_average,
        "blasius_cf": TurbulentFlatPlateConstants.BLASIUS_CF,
        "schlichting_method": "Cf_x = 0.026 * Rex^(-1/7)",
        "average_method": "Cf_bar = 0.036 * Re_L^(-1/5)",
        "literature_source": "Schlichting (1979) Boundary-Layer Theory",
        "valid_range": "10^6 < Rex < 10^9",
        "transition_reynolds": TurbulentFlatPlateConstants.TRANSITION_REYNOLDS,
    }


# ============================================================================
# Mesh Information
# ============================================================================

def get_mesh_info() -> Dict[str, Any]:
    """
    Get mesh metadata for turbulent flat plate case.

    Returns:
        Dictionary with mesh strategy and parameters
    """
    return {
        "mesh_strategy": "A",
        "mesh_type": "structured_cartesian",
        "plate_length": TurbulentFlatPlateConstants.PLATE_LENGTH,
        "domain_height": 0.5,  # Height above plate
        "domain_length": 1.5,  # Extended domain length
        "refinement_zones": [
            {"y": 0.0, "y_plus_target": 1.0, "resolution": 1e-5},  # Near-wall refinement
            {"x": 0.0, "x": 1.0, "resolution": 0.002},  # Along plate
        ],
        "y_plus_target": 1.0,
        "notes": "Highly refined near-wall mesh for accurate boundary layer resolution",
    }


# ============================================================================
# Solver Configuration
# ============================================================================

def get_solver_config() -> Dict[str, Any]:
    """
    Get solver configuration for turbulent flat plate case.

    Returns:
        Dictionary with solver parameters
    """
    return {
        "solver_name": "SU2_CFD",
        "equation_system": "Navier-Stokes",
        "turbulence_model": "k-omega SST",
        "mach_number": 0.2,  # Low speed for incompressible regime
        "reynolds_number": TurbulentFlatPlateConstants.REYNOLDS,
        "free_stream_velocity": TurbulentFlatPlateConstants.FREE_STREAM_VELOCITY,
        "spatial_discretization": "Jameson-Austin",
        "temporal_discretization": "Runge-Kutta",
        "cfl_number": 0.8,
        "wall_treatment": "low_y_plus_wall_function",
        "convergence_criteria": {"max_iterations": 10000, "residual_tolerance": 1e-8},
    }


# ============================================================================
# Gate Validation
# ============================================================================

class TurbulentFlatPlateGateValidator:
    """
    Gate validator for turbulent flat plate gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_turbulent_flat_plate_spec()

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
        if "skin_friction_coefficient_cf" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: skin_friction_coefficient_cf")

        results["details"]["metric_coverage"] = len(gold_metric_names & actual_metric_names) / len(gold_metric_names)

        return results


# ============================================================================
# GoldStandard Auto-Registration
# ============================================================================

WHITELIST_ID = "SU2-09"


def register(registry: "GoldStandardRegistry") -> None:
    """Register this GoldStandard case with the global registry."""
    registry.register(
        case_id="turbulent_flat_plate",
        whitelist_id=WHITELIST_ID,
        spec_factory=create_turbulent_flat_plate_spec,
        validator_class=TurbulentFlatPlateGateValidator,
        reference_fn=get_expected_skin_friction,
        mesh_info_fn=get_mesh_info,
        solver_config_fn=get_solver_config,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "TurbulentFlatPlateConstants",
    "create_turbulent_flat_plate_spec",
    "TurbulentFlatPlateGateValidator",
    "get_expected_skin_friction",
    "get_mesh_info",
    "get_solver_config",
    "register",
]
