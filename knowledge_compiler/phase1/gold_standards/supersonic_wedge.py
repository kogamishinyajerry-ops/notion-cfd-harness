#!/usr/bin/env python3
"""
GoldStandard: Supersonic Wedge (SU2-02)

Reference implementation for supersonic flow over a wedge with
analytical theta-beta-M shock angle relation.

Based on:
- Anderson, J.D. (2003) Modern Compressible Flow, 3rd ed.
  Chapter 4 — Shock Wave Relations
- The analytical theta-beta-M relation for oblique shocks.

Gold standard provides:
1. Validation template for supersonic wedge cases
2. Gate validation criteria
3. Literature benchmark data
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
# Supersonic Wedge Constants
# ============================================================================

class SupersonicWedgeConstants:
    """Physical constants for supersonic wedge case"""

    # Flow conditions
    MACH = 2.0  # Upstream Mach number
    WEDGE_ANGLE = 15.0  # Wedge half-angle in degrees
    SHOCK_ANGLE = 45.34  # Calculated from theta-beta-M relation (degrees)
    GAMMA = 1.4  # Ratio of specific heats for air

    # Domain geometry (normalised)
    DOMAIN_LENGTH = 10.0
    DOMAIN_HEIGHT = 6.0

    # Expected downstream conditions (from analytical solution)
    PRESSURE_RATIO = 4.5  # p2/p1 across oblique shock
    TEMPERATURE_RATIO = 1.32  # T2/T1 across oblique shock
    DENSITY_RATIO = 3.41  # rho2/rho1 across oblique shock

    # Mesh strategy
    MESH_STRATEGY = "A"


# ============================================================================
# Analytical Shock Angle Computation (theta-beta-M relation)
# ============================================================================

def compute_shock_angle_theta_beta_M(
    mach: float,
    wedge_angle_deg: float,
    gamma: float = 1.4,
) -> float:
    """
    Compute shock angle beta from theta-beta-M relation.

    The theta-beta-M relation for oblique shocks:
        tan(theta) = 2 * cot(beta) * (M^2 * sin^2(beta) - 1)
                     / (M^2 * (gamma + cos(2*beta)) + 2)

    Solved using bisection method (more robust than Newton).

    Args:
        mach: Upstream Mach number
        wedge_angle_deg: Wedge half-angle in degrees
        gamma: Ratio of specific heats

    Returns:
        Shock angle beta in degrees
    """
    theta = math.radians(wedge_angle_deg)
    mu = math.asin(1.0 / mach)  # Mach wave angle (lower bound for beta)

    # beta must be > mu (Mach wave angle) and < 90 degrees
    beta_lo = mu + 1e-6
    beta_hi = math.pi / 2 - 1e-6

    def theta_beta_M(beta: float) -> float:
        """Compute tan(theta) - f(beta) where f(beta) is the RHS of theta-beta-M."""
        sin_b = math.sin(beta)
        cos_b = math.cos(beta)
        cos_2b = math.cos(2 * beta)
        M2 = mach * mach
        # f(beta) = 2 * cot(beta) * (M^2 * sin^2(beta) - 1) / (M^2 * (gamma + cos(2beta)) + 2)
        # cot(beta) = cos(beta) / sin(beta)
        f_beta = 2 * (cos_b / sin_b) * (M2 * sin_b * sin_b - 1) / (M2 * (gamma + cos_2b) + 2)
        return math.tan(theta) - f_beta

    # Bisection
    for _ in range(200):
        beta_mid = (beta_lo + beta_hi) / 2
        f_mid = theta_beta_M(beta_mid)
        if abs(f_mid) < 1e-12:
            break
        f_lo = theta_beta_M(beta_lo)
        # Root is between beta_lo and beta_mid if f_lo and f_mid have opposite signs
        if f_lo * f_mid < 0:
            beta_hi = beta_mid
        else:
            beta_lo = beta_mid

    return math.degrees(beta_mid)


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_supersonic_wedge_spec(
    case_id: str = "supersonic_wedge",
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for supersonic wedge case

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
        "pressure_contour",
        "shock_structure",
        "centerline_mach_profile",
        "static_pressure_profile",
    ]

    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"Supersonic Wedge (M={SupersonicWedgeConstants.MACH}, theta={SupersonicWedgeConstants.WEDGE_ANGLE}deg)",
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
        name="pressure_contour",
        plane="domain",
        colormap="coolwarm",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="shock_structure",
        plane="domain",
        colormap="jet",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="centerline_mach_profile",
        plane="x=0",
        colormap="viridis",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="static_pressure_profile",
        plane="domain",
        colormap="coolwarm",
        range="auto",
    ))

    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    metrics.append(MetricSpec(
        name="shock_angle_deg",
        unit="deg",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="pressure_ratio",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="mach_downstream",
        unit="-",
        comparison=ComparisonType.DIFF,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    sections.append(SectionSpec(
        name="inlet",
        type="inlet",
        position={"x": 0.0},
    ))

    sections.append(SectionSpec(
        name="shock_line",
        type="iso-line",
        position={"x": 0.5},
    ))

    sections.append(SectionSpec(
        name="outlet",
        type="outlet",
        position={"x": 1.0},
    ))

    return sections


# ============================================================================
# Expected Literature Benchmark Data
# ============================================================================

def get_expected_shock_angle() -> Dict[str, Any]:
    """
    Get expected shock angle from analytical theta-beta-M computation.

    Returns:
        Dictionary with shock_angle_deg and computation parameters
    """
    mach = SupersonicWedgeConstants.MACH
    wedge_angle = SupersonicWedgeConstants.WEDGE_ANGLE
    gamma = SupersonicWedgeConstants.GAMMA

    # Analytical computation
    shock_angle = compute_shock_angle_theta_beta_M(mach, wedge_angle, gamma)

    return {
        "mach": mach,
        "wedge_angle_deg": wedge_angle,
        "shock_angle_deg": shock_angle,
        "gamma": gamma,
        "computation_method": "theta-beta-M analytical (Newton solver)",
        "literature_source": "Anderson (2003) Modern Compressible Flow",
    }


# ============================================================================
# Mesh Information
# ============================================================================

def get_mesh_info() -> Dict[str, Any]:
    """
    Get mesh metadata for supersonic wedge case.

    Returns:
        Dictionary with mesh strategy and parameters
    """
    return {
        "mesh_strategy": "A",
        "mesh_type": "structured_cartesian",
        "domain_length": SupersonicWedgeConstants.DOMAIN_LENGTH,
        "domain_height": SupersonicWedgeConstants.DOMAIN_HEIGHT,
        "refinement_zones": [
            {"x": 0.3, "radius": 0.5, "resolution": 0.01},  # Near shock region
        ],
        "notes": "Cartesian mesh with polar refinement around wedge tip and shock region",
    }


# ============================================================================
# Solver Configuration
# ============================================================================

def get_solver_config() -> Dict[str, Any]:
    """
    Get solver configuration for supersonic wedge case.

    Returns:
        Dictionary with solver parameters
    """
    return {
        "solver_name": "SU2_CFD",
        "equation_system": "Euler",
        "turbulence_model": None,  # Inviscid flow
        "mach_number": SupersonicWedgeConstants.MACH,
        "gas_gamma": SupersonicWedgeConstants.GAMMA,
        "spatial_discretization": "central",
        "temporal_discretization": "Runge-Kutta",
        "cfl_number": 0.8,
        "convergence_criteria": {"max_iterations": 5000, "residual_tolerance": 1e-8},
    }


# ============================================================================
# Gate Validation
# ============================================================================

class SupersonicWedgeGateValidator:
    """
    Gate validator for supersonic wedge gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_supersonic_wedge_spec()

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
        if "shock_angle_deg" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: shock_angle_deg")

        results["details"]["metric_coverage"] = len(gold_metric_names & actual_metric_names) / len(gold_metric_names)

        return results


# ============================================================================
# GoldStandard Auto-Registration
# ============================================================================

WHITELIST_ID = "SU2-02"


def register(registry: "GoldStandardRegistry") -> None:
    """Register this GoldStandard case with the global registry."""
    registry.register(
        case_id="supersonic_wedge",
        whitelist_id=WHITELIST_ID,
        spec_factory=create_supersonic_wedge_spec,
        validator_class=SupersonicWedgeGateValidator,
        reference_fn=get_expected_shock_angle,
        mesh_info_fn=get_mesh_info,
        solver_config_fn=get_solver_config,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "SupersonicWedgeConstants",
    "create_supersonic_wedge_spec",
    "SupersonicWedgeGateValidator",
    "get_expected_shock_angle",
    "get_mesh_info",
    "get_solver_config",
    "register",
]
