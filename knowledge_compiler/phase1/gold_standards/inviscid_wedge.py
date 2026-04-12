#!/usr/bin/env python3
"""
Phase 1 Gold Standard: Inviscid Supersonic Wedge

Reference implementation for SU2 Tutorial SU2-02 (rank 4, core_seed).
2D supersonic flow over a wedge generating an oblique shock.
Based on SU2 tutorial case: inviscid flow at M=2.0 over a 15-degree wedge.

Gold standard provides a reference ReportSpec that can be used as:
1. Validation template for new cases
2. Gate validation criteria
3. Benchmark for testing the system
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan, asin, sin, cos, tan, radians, degrees, sqrt
from pathlib import Path
from typing import Any, Dict, List, Optional

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
# Inviscid Wedge Constants
# ============================================================================

class InviscidWedgeConstants:
    """Physical constants for inviscid supersonic wedge case"""

    # Geometry
    WEDGE_ANGLE = 15.0  # Wedge half-angle (degrees)
    WEDGE_LENGTH = 2.0  # Wedge surface length

    # Flow conditions
    MACH = 2.0  # Freestream Mach number
    GAMMA = 1.4  # Ratio of specific heats

    # Expected shock angle from theta-beta-M relation
    # For M=2.0, theta=15deg: beta ~ 45.34 deg (weak shock solution)
    SHOCK_ANGLE = 45.34  # Oblique shock angle (degrees)

    # Expected post-shock conditions (normal shock relations applied
    # to normal component of velocity)
    # M_n1 = M * sin(beta) = 2.0 * sin(45.34) ~ 1.423
    # M_n2 from normal shock: M_n2 ~ 0.732
    # M_2 = M_n2 / sin(beta - theta) ~ 1.45
    DOWNSTREAM_MACH = 1.45  # Post-shock Mach number

    # Pressure jump: p2/p1 from oblique shock relation
    PRESSURE_JUMP_RATIO = 2.19  # p2/p1


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_inviscid_wedge_spec(
    case_id: str = "inviscid_wedge",
    mach_number: float = 2.0,
    wedge_angle: float = 15.0,
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for inviscid supersonic wedge case

    Args:
        case_id: Unique case identifier
        mach_number: Freestream Mach number
        wedge_angle: Wedge half-angle in degrees

    Returns:
        Complete ReportSpec with all required plots and metrics
    """
    # Required plots
    required_plots = _create_required_plots()

    # Required metrics
    required_metrics = _create_required_metrics()

    # Required sections
    critical_sections = _create_required_sections()

    # Plot order
    plot_order = [
        "mach_contour",
        "pressure_contour",
        "density_gradient",
    ]

    # Create ReportSpec
    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"Inviscid Supersonic Wedge (M={mach_number}, theta={wedge_angle}deg)",
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

    # Plot 1: Mach number contour
    plots.append(PlotSpec(
        name="mach_contour",
        plane="domain",
        colormap="jet",
        range="auto",
    ))

    # Plot 2: Pressure contour
    plots.append(PlotSpec(
        name="pressure_contour",
        plane="domain",
        colormap="coolwarm",
        range="auto",
    ))

    # Plot 3: Density gradient magnitude (captures shock structure)
    plots.append(PlotSpec(
        name="density_gradient",
        plane="domain",
        colormap="plasma",
        range="auto",
    ))

    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    # Metric 1: Shock angle
    metrics.append(MetricSpec(
        name="shock_angle",
        unit="deg",
        comparison=ComparisonType.DIRECT,
    ))

    # Metric 2: Downstream Mach number
    metrics.append(MetricSpec(
        name="downstream_mach",
       unit="-",
        comparison=ComparisonType.DIFF,
    ))

    # Metric 3: Pressure jump ratio across shock
    metrics.append(MetricSpec(
        name="pressure_jump_ratio",
        unit="-",
        comparison=ComparisonType.RATIO,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    # Section 1: Upstream of shock
    sections.append(SectionSpec(
        name="upstream",
        type="plane",
        position={"x": -0.5},
    ))

    # Section 2: Post-shock region
    sections.append(SectionSpec(
        name="post_shock",
        type="plane",
        position={"x": 1.0},
    ))

    # Section 3: Wedge surface
    sections.append(SectionSpec(
        name="wedge_surface",
        type="wall",
        position={"y": 0.0},
    ))

    return sections


# ============================================================================
# Expected Shock Angle (theta-beta-M Relation)
# ============================================================================

def get_expected_shock_angle(
    mach_number: float = 2.0,
    wedge_angle: float = 15.0,
    gamma: float = 1.4,
) -> float:
    """
    Calculate expected oblique shock angle using theta-beta-M relation.

    Uses iterative solution of:
        tan(theta) = 2 * cot(beta) * [M1^2 * sin^2(beta) - 1] /
                     [M1^2 * (gamma + cos(2*beta)) + 2]

    Args:
        mach_number: Freestream Mach number
        wedge_angle: Wedge deflection angle in degrees
        gamma: Ratio of specific heats

    Returns:
        Weak shock angle in degrees
    """
    theta = radians(wedge_angle)
    M1 = mach_number

    # Iterative bisection to find beta from theta-beta-M relation
    # Beta must be between mach angle and 90 degrees
    mach_angle = degrees(asin(1.0 / M1))
    beta_low = radians(mach_angle + 0.1)
    beta_high = radians(89.9)

    for _ in range(200):
        beta = (beta_low + beta_high) / 2.0

        # theta-beta-M relation
        numerator = 2.0 * (1.0 / tan(beta)) * (M1 ** 2 * sin(beta) ** 2 - 1.0)
        denominator = M1 ** 2 * (gamma + cos(2.0 * beta)) + 2.0

        if abs(denominator) < 1e-12:
            beta_high = beta
            continue

        theta_calc = atan(numerator / denominator)

        if theta_calc > theta:
            # Weak shock solution: beta too large
            beta_high = beta
        else:
            beta_low = beta

        if abs(theta_calc - theta) < 1e-10:
            break

    return degrees((beta_low + beta_high) / 2.0)


# ============================================================================
# Gate Validation
# ============================================================================

class InviscidWedgeGateValidator:
    """
    Gate validator for inviscid supersonic wedge gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_inviscid_wedge_spec()

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

        # Check 1: Required plots
        gold_plot_names = {p.name for p in self.gold_spec.required_plots}
        actual_plot_names = {p.name for p in spec.required_plots}

        missing_plots = gold_plot_names - actual_plot_names
        if missing_plots:
            results["passed"] = False
            results["errors"].append(f"Missing required plots: {missing_plots}")

        results["details"]["plot_coverage"] = len(gold_plot_names & actual_plot_names) / len(gold_plot_names)

        # Check 2: Required metrics
        gold_metric_names = {m.name for m in self.gold_spec.required_metrics}
        actual_metric_names = {m.name for m in spec.required_metrics}

        missing_metrics = gold_metric_names - actual_metric_names
        if "shock_angle" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: shock_angle")

        results["details"]["metric_coverage"] = len(gold_metric_names & actual_metric_names) / len(gold_metric_names)

        # Check 3: Critical sections
        gold_section_names = {s.name for s in self.gold_spec.critical_sections}
        actual_section_names = {s.name for s in spec.critical_sections}

        missing_sections = gold_section_names - actual_section_names
        if missing_sections:
            results["warnings"].append(f"Missing recommended sections: {missing_sections}")

        return results


# ============================================================================
# GoldStandard Auto-Registration
# ============================================================================

def register(registry: "GoldStandardRegistry") -> None:
    """Register this GoldStandard case with the global registry.

    Called by GoldStandardRegistry._register_all_cases() via importlib.
    """
    registry.register(
        case_id="inviscid_wedge",
        spec_factory=create_inviscid_wedge_spec,
        validator_class=InviscidWedgeGateValidator,
        reference_fn=None,
        mesh_info_fn=None,
        solver_config_fn=None,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "InviscidWedgeConstants",
    "create_inviscid_wedge_spec",
    "InviscidWedgeGateValidator",
    "get_expected_shock_angle",
    "register",
]
