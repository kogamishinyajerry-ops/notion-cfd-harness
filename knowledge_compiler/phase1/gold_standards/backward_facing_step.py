#!/usr/bin/env python3
"""
Phase 1 Gold Standard: Backward Facing Step

Reference implementation for the classic CFD benchmark case.
Based on:
- Armaly, B.F., et al. (1983) "Experimental and theoretical investigation of
  backward-facing step flow"
- Le, H., et al. (1997) "Direct numerical simulation of turbulent
  flow over a backward-facing step"

Gold standard provides a reference ReportSpec that can be used as:
1. Validation template for new cases
2. Gate validation criteria
3. Benchmark for testing the system
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
# Backward Facing Step Constants
# ============================================================================

class BackwardStepConstants:
    """Physical constants for backward-facing step case"""

    # Geometry
    STEP_HEIGHT = 0.1  # h = 0.1 m
    CHANNEL_HEIGHT = 0.2  # H = 0.2 m
    EXPANSION_RATIO = 2.0  # ER = (H + h) / h
    STEP_LENGTH = 1.0  # Length before step
    CHANNEL_LENGTH = 10.0  # Length after step

    # Expected reattachment lengths (xr/h)
    # Based on Armaly et al. (1983)
    REATTACHMENT_LENGTHS = {
        "laminar_100": 6.5,   # Re = 100
        "laminar_200": 8.0,   # Re = 200
        "laminar_400": 10.0,  # Re = 400
        "laminar_600": 12.0,  # Re = 600
        "laminar_800": 14.0,  # Re = 800
        "laminar_1000": 15.0, # Re = 1000
        "turbulent": 6.5,     # Turbulent (Re > 4000)
    }

    # Reference x/h positions for velocity profiles
    PROFILE_POSITIONS = [1.0, 3.0, 5.0, 7.0, 10.0]


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_backward_facing_step_spec(
    case_id: str = "backward_facing_step",
    reynolds_number: float = 400.0,
    is_turbulent: bool = False,
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for backward-facing step case

    Args:
        case_id: Unique case identifier
        reynolds_number: Reynolds number based on step height
        is_turbulent: Whether the simulation is turbulent

    Returns:
        Complete ReportSpec with all required plots and metrics
    """
    flow_type = "turbulent" if is_turbulent else "laminar"

    # Required plots (using existing PlotSpec schema)
    required_plots = _create_required_plots(flow_type)

    # Required metrics (using existing MetricSpec schema)
    required_metrics = _create_required_metrics(reynolds_number)

    # Required sections (using existing SectionSpec schema)
    critical_sections = _create_required_sections()

    # Plot order
    plot_order = [
        "velocity_magnitude_contour",
        "streamlines",
        "vector_field_recirculation",
    ] + [f"u_profile_x{x:.0f}" for x in BackwardStepConstants.PROFILE_POSITIONS]

    if flow_type == "turbulent":
        plot_order.append("wall_shear_stress")

    # Create ReportSpec
    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"Backward Facing Step ({flow_type} Re={reynolds_number})",
        problem_type=ProblemType.INTERNAL_FLOW,
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


def _create_required_plots(flow_type: str) -> List[PlotSpec]:
    """Create required plot specifications"""
    plots = []

    # Plot 1: Velocity magnitude contour
    plots.append(PlotSpec(
        name="velocity_magnitude_contour",
        plane="domain",
        colormap="viridis",
        range="auto",
    ))

    # Plot 2: Streamlines
    plots.append(PlotSpec(
        name="streamlines",
        plane="domain",
        colormap="jet",
        range="auto",
    ))

    # Plot 3: Velocity vector field (zoomed on recirculation zone)
    plots.append(PlotSpec(
        name="vector_field_recirculation",
        plane="recirculation",
        colormap="coolwarm",
        range="auto",
    ))

    # Plot 4-8: U-velocity profiles at reference positions
    for x_h in BackwardStepConstants.PROFILE_POSITIONS:
        plots.append(PlotSpec(
            name=f"u_profile_x{x_h:.0f}",
            plane=f"x={x_h * BackwardStepConstants.STEP_HEIGHT:.3f}",
            colormap="viridis",
            range="auto",
        ))

    # Plot 9: Wall shear stress (for turbulent cases)
    if flow_type == "turbulent":
        plots.append(PlotSpec(
            name="wall_shear_stress",
            plane="bottom_wall",
            colormap="plasma",
            range="auto",
        ))

    return plots


def _create_required_metrics(reynolds_number: float) -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    # Metric 1: Reattachment length (xr/h) - THE critical metric
    metrics.append(MetricSpec(
        name="reattachment_length",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    # Metric 2: Maximum reverse velocity
    metrics.append(MetricSpec(
        name="max_reverse_velocity",
        unit="m/s",
        comparison=ComparisonType.DIFF,
    ))

    # Metric 3: Recirculation zone height
    metrics.append(MetricSpec(
        name="recirculation_height",
        unit="m",
        comparison=ComparisonType.DIFF,
    ))

    # Metric 4: Pressure recovery
    metrics.append(MetricSpec(
        name="pressure_recovery",
        unit="-",
        comparison=ComparisonType.RATIO,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    # Section 1: Inlet profile
    sections.append(SectionSpec(
        name="inlet_profile",
        type="plane",
        position={"x": -0.5, "z": 0.5},
    ))

    # Section 2: Step edge vicinity
    sections.append(SectionSpec(
        name="step_edge",
        type="plane",
        position={"x": 0.0, "z": 0.5},
    ))

    # Section 3: Reattachment point
    sections.append(SectionSpec(
        name="reattachment_point",
        type="plane",
        position={"x": 1.0, "z": 0.5},  # Will be updated based on flow
    ))

    # Section 4: Far downstream
    sections.append(SectionSpec(
        name="outlet_profile",
        type="plane",
        position={"x": 8.0, "z": 0.5},
    ))

    return sections


# ============================================================================
# Expected Reattachment Length
# ============================================================================

def get_expected_reattachment_length(reynolds_number: float) -> float:
    """Get expected reattachment length based on Reynolds number"""
    if reynolds_number < 1200:
        # Laminar regime - interpolate from Armaly data
        re_data = BackwardStepConstants.REATTACHMENT_LENGTHS
        if reynolds_number <= 100:
            return re_data["laminar_100"]
        elif reynolds_number <= 200:
            return re_data["laminar_200"]
        elif reynolds_number <= 400:
            return re_data["laminar_400"]
        elif reynolds_number <= 600:
            return re_data["laminar_600"]
        elif reynolds_number <= 800:
            return re_data["laminar_800"]
        else:
            return re_data["laminar_1000"]
    else:
        # Turbulent regime
        return BackwardStepConstants.REATTACHMENT_LENGTHS["turbulent"]


# ============================================================================
# Gate Validation
# ============================================================================

class BackwardStepGateValidator:
    """
    Gate validator for backward-facing step gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_backward_facing_step_spec()

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
        if "reattachment_length" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: reattachment_length")

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
WHITELIST_ID = "OF-02"


def register(registry: "GoldStandardRegistry") -> None:
    """Register this GoldStandard case with the global registry.

    Called by GoldStandardRegistry._register_all_cases() via importlib.
    """
    registry.register(
        case_id="backward_facing_step",
        whitelist_id=WHITELIST_ID,
        spec_factory=create_backward_facing_step_spec,
        validator_class=BackwardStepGateValidator,
        reference_fn=None,
        mesh_info_fn=None,
        solver_config_fn=None,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "BackwardStepConstants",
    "create_backward_facing_step_spec",
    "BackwardStepGateValidator",
    "get_expected_reattachment_length",
    "register",
]
