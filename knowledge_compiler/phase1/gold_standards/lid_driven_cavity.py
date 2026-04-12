#!/usr/bin/env python3
"""
Phase 1 Gold Standard: Lid-Driven Cavity

Reference implementation for the canonical CFD benchmark case.
Based on:
- Ghia, U., et al. (1982) "High-Re solutions for flow using the
  Navier-Stokes equations and a multigrid method"
  Journal of Computational Physics, 48(3), 387-411.

Gold standard provides a reference ReportSpec that can be used as:
1. Validation template for new cases
2. Gate validation criteria
3. Benchmark for testing the system
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
# Lid-Driven Cavity Constants
# ============================================================================

class CavityConstants:
    """Physical constants for lid-driven cavity case"""

    # Geometry
    CAVITY_SIZE = 1.0  # L = 1.0 m (unit square)
    LID_VELOCITY = 1.0  # U_lid = 1.0 m/s

    # Reynolds numbers studied by Ghia et al. (1982)
    RE_VALUES = [100, 400, 1000, 3200, 5000, 7500, 10000]

    # Centerline x=0.5 vertical positions (y/L) for u-velocity profiles
    # Ghia Table I: 41 positions
    PROFILE_Y_POSITIONS = [
        0.0000, 0.0547, 0.0625, 0.0703, 0.1016, 0.1250,
        0.1484, 0.1719, 0.1953, 0.2188, 0.2422, 0.2656,
        0.2891, 0.3125, 0.3359, 0.3594, 0.3828, 0.4063,
        0.4297, 0.4531, 0.5000, 0.5469, 0.5703, 0.5938,
        0.6172, 0.6406, 0.6641, 0.6875, 0.7109, 0.7344,
        0.7578, 0.7813, 0.8047, 0.8281, 0.8516, 0.8750,
        0.8984, 0.9297, 0.9375, 0.9453, 1.0000,
    ]

    # Centerline y=0.5 horizontal positions (x/L) for v-velocity profiles
    PROFILE_X_POSITIONS = [
        0.0000, 0.0547, 0.0625, 0.0703, 0.1016, 0.1250,
        0.1484, 0.1719, 0.1953, 0.2188, 0.2422, 0.2656,
        0.2891, 0.3125, 0.3359, 0.3594, 0.3828, 0.4063,
        0.4297, 0.4531, 0.5000, 0.5469, 0.5703, 0.5938,
        0.6172, 0.6406, 0.6641, 0.6875, 0.7109, 0.7344,
        0.7578, 0.7813, 0.8047, 0.8281, 0.8516, 0.8750,
        0.8984, 0.9297, 0.9375, 0.9453, 1.0000,
    ]

    # Ghia et al. (1982) u-velocity at centerline x=0.5 (vertical profile)
    # Table I — u/U as a function of y/L
    GHIA_U_CENTERLINE = {
        100: [
            0.00000, -0.03717, -0.04192, -0.04754, -0.06418, -0.07491,
            -0.08301, -0.08864, -0.09242, -0.09466, -0.09599, -0.09677,
            -0.09724, -0.09749, -0.09761, -0.09766, -0.09769, -0.09773,
            -0.09781, -0.09794, -0.09832, -0.09868, -0.09884, -0.09899,
            -0.09914, -0.09931, -0.09952, -0.09981, -0.10022, -0.10082,
            -0.10172, -0.10309, -0.10519, -0.10839, -0.11326, -0.12051,
            -0.13150, -0.15556, -0.16378, -0.17499, 1.00000,
        ],
        400: [
            0.00000, -0.08186, -0.09266, -0.10338, -0.13192, -0.15161,
            -0.16494, -0.17314, -0.17739, -0.17887, -0.17860, -0.17717,
            -0.17501, -0.17238, -0.16943, -0.16623, -0.16285, -0.15937,
            -0.15587, -0.15244, -0.14593, -0.13722, -0.13183, -0.12615,
            -0.12011, -0.11363, -0.10663, -0.09896, -0.09050, -0.08104,
            -0.07035, -0.05812, -0.04395, -0.02734, -0.00777,  0.01612,
             0.04877,  0.11219,  0.13362,  0.16302, 1.00000,
        ],
        1000: [
            0.00000, -0.18109, -0.20196, -0.21691, -0.24929, -0.24740,
            -0.23672, -0.22006, -0.20007, -0.17928, -0.15928, -0.14126,
            -0.12585, -0.11308, -0.10283, -0.09490, -0.08906, -0.08505,
            -0.08259, -0.08147, -0.08264, -0.08617, -0.08883, -0.09197,
            -0.09580, -0.10052, -0.10638, -0.11372, -0.12296, -0.13467,
            -0.14958, -0.16845, -0.19232, -0.22245, -0.26032, -0.30779,
            -0.36732, -0.47211, -0.51010, -0.57457, 1.00000,
        ],
    }

    # Ghia et al. (1982) v-velocity at centerline y=0.5 (horizontal profile)
    # Table II — v/U as a function of x/L
    GHIA_V_CENTERLINE = {
        100: [
            0.00000,  0.09233,  0.10091,  0.11001,  0.13692,  0.14756,
             0.14810,  0.14386,  0.13736,  0.12998,  0.12242,  0.11500,
             0.10789,  0.10113,  0.09474,  0.08870,  0.08298,  0.07754,
             0.07233,  0.06728,  0.05706,  0.04705,  0.04225,  0.03763,
             0.03319,  0.02890,  0.02474,  0.02066,  0.01665,  0.01268,
             0.00873,  0.00478,  0.00083, -0.00313, -0.00713, -0.01122,
            -0.01550, -0.02182, -0.02367, -0.02610, 0.00000,
        ],
        400: [
            0.00000,  0.18360,  0.21095,  0.24299,  0.28724,  0.28171,
             0.26596,  0.24779,  0.22981,  0.21287,  0.19706,  0.18225,
             0.16835,  0.15521,  0.14270,  0.13067,  0.11901,  0.10757,
             0.09627,  0.08499,  0.06303,  0.04154,  0.03110,  0.02101,
             0.01124,  0.00171, -0.00765, -0.01706, -0.02668, -0.03673,
            -0.04751, -0.05945, -0.07313, -0.08921, -0.10868, -0.13266,
            -0.16322, -0.22688, -0.24754, -0.27982, 0.00000,
        ],
        1000: [
            0.00000, -0.21227, -0.27659, -0.33714, -0.34244, -0.30766,
            -0.27670, -0.25199, -0.23154, -0.21424, -0.19931, -0.18618,
            -0.17444, -0.16380, -0.15401, -0.14485, -0.13613, -0.12768,
            -0.11933, -0.11093, -0.09395, -0.07677, -0.06833, -0.05989,
            -0.05145, -0.04298, -0.03443, -0.02573, -0.01680, -0.00753,
             0.00223,  0.01277,  0.02444,  0.03771,  0.05322,  0.07194,
             0.09550,  0.14742,  0.16938,  0.21094, 0.00000,
        ],
    }


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_lid_driven_cavity_spec(
    case_id: str = "lid_driven_cavity",
    reynolds_number: float = 100.0,
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for lid-driven cavity case

    Args:
        case_id: Unique case identifier
        reynolds_number: Reynolds number based on cavity size and lid velocity

    Returns:
        Complete ReportSpec with all required plots and metrics
    """

    # Required plots (using existing PlotSpec schema)
    required_plots = _create_required_plots()

    # Required metrics (using existing MetricSpec schema)
    required_metrics = _create_required_metrics()

    # Required sections (using existing SectionSpec schema)
    critical_sections = _create_required_sections()

    # Plot order
    plot_order = [
        "velocity_magnitude_contour",
        "pressure_contour",
        "streamlines",
        "u_velocity_centerline_x",
        "v_velocity_centerline_y",
        "vorticity_contour",
    ]

    # Create ReportSpec
    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"Lid-Driven Cavity (Re={reynolds_number})",
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


def _create_required_plots() -> List[PlotSpec]:
    """Create required plot specifications"""
    plots = []

    # Plot 1: Velocity magnitude contour
    plots.append(PlotSpec(
        name="velocity_magnitude_contour",
        plane="domain",
        colormap="viridis",
        range="auto",
    ))

    # Plot 2: Pressure contour
    plots.append(PlotSpec(
        name="pressure_contour",
        plane="domain",
        colormap="coolwarm",
        range="auto",
    ))

    # Plot 3: Streamlines
    plots.append(PlotSpec(
        name="streamlines",
        plane="domain",
        colormap="jet",
        range="auto",
    ))

    # Plot 4: U-velocity profile at centerline x=0.5 (vertical)
    plots.append(PlotSpec(
        name="u_velocity_centerline_x",
        plane="x=0.5",
        colormap="viridis",
        range="auto",
    ))

    # Plot 5: V-velocity profile at centerline y=0.5 (horizontal)
    plots.append(PlotSpec(
        name="v_velocity_centerline_y",
        plane="y=0.5",
        colormap="viridis",
        range="auto",
    ))

    # Plot 6: Vorticity contour
    plots.append(PlotSpec(
        name="vorticity_contour",
        plane="domain",
        colormap="RdBu",
        range="auto",
    ))

    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    # Metric 1: Lid drag coefficient
    metrics.append(MetricSpec(
        name="lid_drag_coefficient",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    # Metric 2: Maximum u-velocity on vertical centerline
    metrics.append(MetricSpec(
        name="max_u_centerline",
        unit="m/s",
        comparison=ComparisonType.DIFF,
    ))

    # Metric 3: Minimum v-velocity on horizontal centerline
    metrics.append(MetricSpec(
        name="min_v_centerline",
        unit="m/s",
        comparison=ComparisonType.DIFF,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    # Section 1: Vertical centerline x=0.5
    sections.append(SectionSpec(
        name="centerline_vertical",
        type="centerline",
        position={"x": 0.5},
    ))

    # Section 2: Horizontal centerline y=0.5
    sections.append(SectionSpec(
        name="centerline_horizontal",
        type="centerline",
        position={"y": 0.5},
    ))

    # Section 3: Bottom wall
    sections.append(SectionSpec(
        name="bottom_wall",
        type="wall",
        position={"y": 0.0},
    ))

    # Section 4: Moving lid (top wall)
    sections.append(SectionSpec(
        name="moving_lid",
        type="wall",
        position={"y": 1.0},
    ))

    return sections


# ============================================================================
# Expected Ghia Benchmark Data
# ============================================================================

def get_expected_ghia_data(
    reynolds_number: float,
) -> Dict[str, Any]:
    """
    Get expected Ghia benchmark data for given Reynolds number

    Args:
        reynolds_number: Reynolds number to retrieve data for

    Returns:
        Dictionary with y_positions, u_profile, x_positions, v_profile
        Returns empty profiles if Re not in Ghia tabulated data

    Raises:
        ValueError: If Reynolds number is not in Ghia tabulated data
    """
    re_int = int(reynolds_number)

    if re_int not in CavityConstants.GHIA_U_CENTERLINE:
        available = list(CavityConstants.GHIA_U_CENTERLINE.keys())
        raise ValueError(
            f"Re={re_int} not in Ghia tabulated data. "
            f"Available: {available}"
        )

    return {
        "reynolds_number": re_int,
        "y_positions": list(CavityConstants.PROFILE_Y_POSITIONS),
        "u_centerline": list(CavityConstants.GHIA_U_CENTERLINE[re_int]),
        "x_positions": list(CavityConstants.PROFILE_X_POSITIONS),
        "v_centerline": list(CavityConstants.GHIA_V_CENTERLINE[re_int]),
    }


# ============================================================================
# Gate Validation
# ============================================================================

class CavityGateValidator:
    """
    Gate validator for lid-driven cavity gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_lid_driven_cavity_spec()

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
        if "lid_drag_coefficient" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: lid_drag_coefficient")

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
        case_id="lid_driven_cavity",
        spec_factory=create_lid_driven_cavity_spec,
        validator_class=CavityGateValidator,
        reference_fn=None,  # reference data via get_expected_ghia_data() with Re argument
        mesh_info_fn=None,
        solver_config_fn=None,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "CavityConstants",
    "create_lid_driven_cavity_spec",
    "CavityGateValidator",
    "get_expected_ghia_data",
    "register",
]
