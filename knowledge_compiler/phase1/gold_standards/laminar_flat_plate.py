#!/usr/bin/env python3
"""
Phase 1 Gold Standard: Laminar Flat Plate (Compressible)

Reference implementation for SU2 Tutorial SU2-03 (rank 5, core_seed).
Classic Blasius boundary layer validation for compressible laminar flow.
Based on SU2 tutorial case: laminar flow at M=0.3, Re_L=5000 over a flat plate.

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
# Laminar Flat Plate Constants
# ============================================================================

class LaminarFlatPlateConstants:
    """Physical constants for laminar flat plate case"""

    # Geometry
    PLATE_LENGTH = 1.0  # Flat plate length (m)
    PLATE_START = 0.0  # Leading edge x-position
    DOMAIN_HEIGHT = 0.5  # Domain height above plate

    # Flow conditions
    MACH = 0.3  # Freestream Mach number (low enough for incompressible comparison)
    RE_LENGTH = 5000.0  # Reynolds number based on plate length
    FREESTREAM_TEMP = 300.0  # Freestream temperature (K)
    GAMMA = 1.4  # Ratio of specific heats
    PRANDTL = 0.72  # Prandtl number (air)

    # Blasius reference values
    # At x = 1.0 (plate length):
    # delta ~ 5.0 * x / sqrt(Re_x) = 5.0 / sqrt(5000) = 0.0707
    # delta* ~ 1.7208 * x / sqrt(Re_x) = 1.7208 / sqrt(5000) = 0.02434
    BLASIUS_DELTA = 0.0707  # BL thickness at x=1.0 (99% of U_inf)
    BLASIUS_DELTA_STAR = 0.02434  # Displacement thickness at x=1.0


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_laminar_flat_plate_spec(
    case_id: str = "laminar_flat_plate",
    reynolds_length: float = 5000.0,
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for laminar flat plate case

    Args:
        case_id: Unique case identifier
        reynolds_length: Reynolds number based on plate length

    Returns:
        Complete ReportSpec with all required plots and metrics
    """
    # Required plots
    required_plots = _create_required_plots()

    # Required metrics
    required_metrics = _create_required_metrics(reynolds_length)

    # Required sections
    critical_sections = _create_required_sections()

    # Plot order
    plot_order = [
        "velocity_magnitude",
        "boundary_layer_profile",
        "skin_friction",
    ]

    # Create ReportSpec
    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"Laminar Flat Plate (Re_L={reynolds_length})",
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

    # Plot 1: Velocity magnitude contour over domain
    plots.append(PlotSpec(
        name="velocity_magnitude",
        plane="domain",
        colormap="viridis",
        range="auto",
    ))

    # Plot 2: Boundary layer velocity profile at wall
    plots.append(PlotSpec(
        name="boundary_layer_profile",
        plane="wall",
        colormap="viridis",
        range="auto",
    ))

    # Plot 3: Skin friction coefficient along plate
    plots.append(PlotSpec(
        name="skin_friction",
        plane="wall",
        colormap="plasma",
        range="auto",
    ))

    return plots


def _create_required_metrics(reynolds_length: float) -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    # Metric 1: Skin friction coefficient at x=1.0
    metrics.append(MetricSpec(
        name="cf_at_x1",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    # Metric 2: Boundary layer thickness at trailing edge
    metrics.append(MetricSpec(
        name="boundary_layer_thickness",
        unit="m",
        comparison=ComparisonType.DIFF,
    ))

    # Metric 3: Displacement thickness at trailing edge
    metrics.append(MetricSpec(
        name="displacement_thickness",
        unit="m",
        comparison=ComparisonType.DIFF,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    # Section 1: Leading edge
    sections.append(SectionSpec(
        name="leading_edge",
        type="wall",
        position={"x": 0.0},
    ))

    # Section 2: Mid-plate
    sections.append(SectionSpec(
        name="mid_plate",
        type="plane",
        position={"x": 0.5},
    ))

    # Section 3: Trailing edge
    sections.append(SectionSpec(
        name="trailing_edge",
        type="plane",
        position={"x": 1.0},
    ))

    return sections


# ============================================================================
# Expected Blasius Cf
# ============================================================================

def get_expected_blasius_cf(x_position: float, plate_length: float = 1.0) -> float:
    """
    Calculate expected Blasius skin friction coefficient at given x position.

    Blasius solution for laminar flat plate:
        Cf = 0.664 / sqrt(Re_x)

    where Re_x = Re_L * (x / L)

    Args:
        x_position: Position along the plate (m)
        plate_length: Total plate length (m)

    Returns:
        Expected skin friction coefficient at x_position
    """
    re_x = LaminarFlatPlateConstants.RE_LENGTH * (x_position / plate_length)

    if re_x <= 0:
        return float("inf")

    return 0.664 / sqrt(re_x)


# ============================================================================
# Gate Validation
# ============================================================================

class LaminarFlatPlateGateValidator:
    """
    Gate validator for laminar flat plate gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_laminar_flat_plate_spec()

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
        if "cf_at_x1" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: cf_at_x1")

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
        case_id="laminar_flat_plate",
        spec_factory=create_laminar_flat_plate_spec,
        validator_class=LaminarFlatPlateGateValidator,
        reference_fn=None,
        mesh_info_fn=None,
        solver_config_fn=None,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "LaminarFlatPlateConstants",
    "create_laminar_flat_plate_spec",
    "LaminarFlatPlateGateValidator",
    "get_expected_blasius_cf",
    "register",
]
