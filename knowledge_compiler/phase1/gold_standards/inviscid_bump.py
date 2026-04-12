#!/usr/bin/env python3
"""
Phase 1 Gold Standard: Inviscid Bump in Channel

Reference implementation for SU2 Tutorial SU2-01 (rank 3, core_seed).
2D inviscid compressible flow over a bump in a channel.
Based on SU2 tutorial case: inviscid flow with M=0.5 over a circular-arc bump.

Gold standard provides a reference ReportSpec that can be used as:
1. Validation template for new cases
2. Gate validation criteria
3. Benchmark for testing the system
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
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
# Inviscid Bump Constants
# ============================================================================

class InviscidBumpConstants:
    """Physical constants for inviscid bump in channel case"""

    # Geometry
    CHANNEL_LENGTH = 3.0  # Total channel length
    CHANNEL_HEIGHT = 1.0  # Channel height
    BUMP_HEIGHT = 0.05  # Max bump height (5% of channel height)
    BUMP_LENGTH = 1.0  # Bump chord length

    # Flow conditions
    MACH = 0.5  # Freestream Mach number
    GAMMA = 1.4  # Ratio of specific heats
    AOAs = 0.0  # Angle of attack (degrees)

    # Expected pressure ratio (isentropic, small perturbation)
    # For M=0.5 bump at 5% height, p_ratio ~ 1.0 + small perturbation
    EXPECTED_PRESSURE_RATIO = 1.07  # Approximate peak p/p_inf at bump crest


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_inviscid_bump_spec(
    case_id: str = "inviscid_bump",
    mach_number: float = 0.5,
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for inviscid bump in channel case

    Args:
        case_id: Unique case identifier
        mach_number: Freestream Mach number

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
        "velocity_magnitude",
    ]

    # Create ReportSpec
    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"Inviscid Bump in Channel (M={mach_number})",
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

    # Plot 3: Velocity magnitude
    plots.append(PlotSpec(
        name="velocity_magnitude",
        plane="domain",
        colormap="viridis",
        range="auto",
    ))

    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    # Metric 1: Maximum Mach number on bump
    metrics.append(MetricSpec(
        name="max_mach",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    # Metric 2: Pressure ratio (peak/bulk)
    metrics.append(MetricSpec(
        name="pressure_ratio",
        unit="-",
        comparison=ComparisonType.RATIO,
    ))

    # Metric 3: Mass flow rate (conservation check)
    metrics.append(MetricSpec(
        name="mass_flow_rate",
        unit="kg/s",
        comparison=ComparisonType.DIRECT,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    # Section 1: Inlet
    sections.append(SectionSpec(
        name="inlet",
        type="plane",
        position={"x": -1.0},
    ))

    # Section 2: Bump surface
    sections.append(SectionSpec(
        name="bump_surface",
        type="wall",
        position={"y": 0.0},
    ))

    # Section 3: Outlet
    sections.append(SectionSpec(
        name="outlet",
        type="plane",
        position={"x": 3.0},
    ))

    return sections


# ============================================================================
# Expected Pressure Ratio
# ============================================================================

def get_expected_pressure_ratio(mach_number: float = 0.5) -> float:
    """
    Get expected peak pressure ratio for inviscid bump

    Uses linearized subsonic thin-airfoil theory as approximation.
    For a small bump in a channel, the peak pressure ratio depends on
    the blockage ratio and Mach number.

    Args:
        mach_number: Freestream Mach number

    Returns:
        Expected peak pressure ratio p/p_inf
    """
    gamma = InviscidBumpConstants.GAMMA
    bump_ratio = InviscidBumpConstants.BUMP_HEIGHT / InviscidBumpConstants.CHANNEL_HEIGHT

    # Isentropic pressure ratio correction for small perturbation
    # p/p_inf ~ 1 + gamma * M^2 * (blockage correction)
    correction = gamma * mach_number ** 2 * bump_ratio * 2.0
    return 1.0 + correction


# ============================================================================
# Gate Validation
# ============================================================================

class InviscidBumpGateValidator:
    """
    Gate validator for inviscid bump gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_inviscid_bump_spec()

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
        if "pressure_ratio" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: pressure_ratio")

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

# Mapping: module case_id -> whitelist ID (from cold_start_whitelist.yaml)
WHITELIST_ID = "SU2-01"


def register(registry: "GoldStandardRegistry") -> None:
    """Register this GoldStandard case with the global registry.

    Called by GoldStandardRegistry._register_all_cases() via importlib.
    """
    registry.register(
        case_id="inviscid_bump",
        whitelist_id=WHITELIST_ID,
        spec_factory=create_inviscid_bump_spec,
        validator_class=InviscidBumpGateValidator,
        reference_fn=None,
        mesh_info_fn=None,
        solver_config_fn=None,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "InviscidBumpConstants",
    "create_inviscid_bump_spec",
    "InviscidBumpGateValidator",
    "get_expected_pressure_ratio",
    "register",
]
