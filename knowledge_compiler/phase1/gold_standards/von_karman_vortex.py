#!/usr/bin/env python3
"""
GoldStandard: von Karman Vortex Street (SU2-10)

Reference implementation for vortex shedding behind a bluff body
with Strouhal number St = 0.16-0.19.

Based on:
- von Karman, T. & Rubach, H. (1912) "Physikalische Grundlagen"
  Mechanische Aehnlichkeit und dimensionslosen Kennzahlen
- Williamson, C.H.K. (1996) "Vortex Dynamics in the Cylinder Wake"
  Annual Review of Fluid Mechanics, 28, 477-539.
- Strouhal, V. (1878) "Ueber eine besondere Art der Tonerregung"

Gold standard provides:
1. Validation template for vortex shedding cases
2. Gate validation criteria
3. Literature benchmark data (Strouhal number)
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
# von Karman Vortex Constants
# ============================================================================

class VonKarmanVortexConstants:
    """Physical constants for von Karman vortex street case"""

    # Flow conditions
    REYNOLDS = 100.0  # Low Re for laminar vortex shedding
    STROUHAL_NUMBER = 0.164  # Characteristic St = 0.16-0.19 for cylinder

    # Geometry
    CYLINDER_DIAMETER = 1.0  # Normalised diameter

    # Domain
    DOMAIN_WIDTH = 30.0  # Width (perpendicular to flow)
    DOMAIN_HEIGHT = 15.0  # Height (along wake direction)
    UPSTREAM_LENGTH = 5.0
    DOWNSTREAM_LENGTH = 25.0

    # Non-dimensional shedding frequency
    # St = f * D / U_inf
    SHEDDING_FREQUENCY_NON_DIM = STROUHAL_NUMBER

    # Vortex street characteristics (from Williamson 1996)
    VORTEX_SPACING_RATIO = 0.295  # a/b ratio in von Karman theory
    CIRCULATION_RATIO = 1.0  # Ratio of upper/lower vortex strength

    # Mesh strategy
    MESH_STRATEGY = "A"


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_von_karman_vortex_spec(
    case_id: str = "von_karman_vortex",
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for von Karman vortex street case

    Args:
        case_id: Unique case identifier

    Returns:
        Complete ReportSpec with all required plots and metrics
    """
    required_plots = _create_required_plots()
    required_metrics = _create_required_metrics()
    critical_sections = _create_required_sections()

    plot_order = [
        "vorticity_contour",
        "pressure_contour",
        "velocity_magnitude_contour",
        "power_spectral_density",
        "phase_averaged_velocity",
    ]

    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"von Karman Vortex Street (Re={VonKarmanVortexConstants.REYNOLDS})",
        problem_type=ProblemType.EXTERNAL_FLOW,
        required_plots=required_plots,
        required_metrics=required_metrics,
        critical_sections=critical_sections,
        plot_order=plot_order,
        comparison_method={
            "type": "probe",
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
        name="vorticity_contour",
        plane="domain",
        colormap="RdBu",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="pressure_contour",
        plane="domain",
        colormap="coolwarm",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="velocity_magnitude_contour",
        plane="domain",
        colormap="viridis",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="power_spectral_density",
        plane="domain",
        colormap="Blues",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="phase_averaged_velocity",
        plane="x=5",
        colormap="jet",
        range="auto",
    ))

    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    metrics.append(MetricSpec(
        name="strouhal_number",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="shedding_frequency_hz",
        unit="Hz",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="vortex_spacing_ratio",
        unit="-",
        comparison=ComparisonType.DIFF,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    sections.append(SectionSpec(
        name="cylinder_surface",
        type="wall",
        position={"r": 0.5},
    ))

    sections.append(SectionSpec(
        name="wake_centerline",
        type="centerline",
        position={"y": 0.0},
    ))

    sections.append(SectionSpec(
        name="lateral_probe",
        type="rake",
        position={"x": 5.0},
    ))

    sections.append(SectionSpec(
        name="near_wake",
        type="plane",
        position={"x": 2.0},
    ))

    return sections


# ============================================================================
# Expected Literature Benchmark Data
# ============================================================================

def get_expected_strouhal() -> Dict[str, Any]:
    """
    Get expected Strouhal number from Williamson (1996) data.

    Returns:
        Dictionary with Strouhal number and reference data
    """
    st = VonKarmanVortexConstants.STROUHAL_NUMBER

    return {
        "reynolds_number": VonKarmanVortexConstants.REYNOLDS,
        "strouhal_number": st,
        "strouhal_range": {"min": 0.16, "max": 0.19},
        "vortex_spacing_ratio": VonKarmanVortexConstants.VORTEX_SPACING_RATIO,
        "literature_source": "Williamson (1996) Annual Review of Fluid Mechanics",
        "secondary_source": "von Karman & Rubach (1912)",
        "notes": "St is nearly constant (0.16-0.19) for 250 < Re < 2e5, slight decrease at lower Re",
        "dimensionless_frequency": st,
    }


# ============================================================================
# Mesh Information
# ============================================================================

def get_mesh_info() -> Dict[str, Any]:
    """
    Get mesh metadata for von Karman vortex street case.

    Returns:
        Dictionary with mesh strategy and parameters
    """
    return {
        "mesh_strategy": "A",
        "mesh_type": "structured_overset",
        "domain_width": VonKarmanVortexConstants.DOMAIN_WIDTH,
        "domain_height": VonKarmanVortexConstants.DOMAIN_HEIGHT,
        "cylinder_diameter": VonKarmanVortexConstants.CYLINDER_DIAMETER,
        "refinement_zones": [
            {"zone": "near_cylinder", "radius_ratio": 3.0, "resolution": 0.01},
            {"zone": "wake_region", "x_min": 0.5, "x_max": 15.0, "resolution": 0.02},
        ],
        "notes": "Overset mesh with wake refinement for accurate vortex shedding capture",
    }


# ============================================================================
# Solver Configuration
# ============================================================================

def get_solver_config() -> Dict[str, Any]:
    """
    Get solver configuration for von Karman vortex street case.

    Returns:
        Dictionary with solver parameters
    """
    return {
        "solver_name": "SU2_CFD",
        "equation_system": "Navier-Stokes",
        "turbulence_model": "LES Smagorinsky",  # LES for unsteady vortex shedding
        "mach_number": 0.1,  # Low speed
        "reynolds_number": VonKarmanVortexConstants.REYNOLDS,
        "spatial_discretization": "central",
        "temporal_discretization": "BDF2",
        "time_step": 0.01,  # CFL ~ 0.3
        "num_iterations_shedding": 20000,  # Need sufficient time for vortex formation
        "convergence_criteria": {"max_iterations": 20000, "residual_tolerance": 1e-5},
        "unsteady": True,
        "physical_time": 50.0,  # Sufficient for 3-5 shedding cycles
    }


# ============================================================================
# Gate Validation
# ============================================================================

class VonKarmanVortexGateValidator:
    """
    Gate validator for von Karman vortex street gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_von_karman_vortex_spec()

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
        if "strouhal_number" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: strouhal_number")

        results["details"]["metric_coverage"] = len(gold_metric_names & actual_metric_names) / len(gold_metric_names)

        return results


# ============================================================================
# GoldStandard Auto-Registration
# ============================================================================

WHITELIST_ID = "SU2-10"


def register(registry: "GoldStandardRegistry") -> None:
    """Register this GoldStandard case with the global registry."""
    registry.register(
        case_id="von_karman_vortex",
        whitelist_id=WHITELIST_ID,
        spec_factory=create_von_karman_vortex_spec,
        validator_class=VonKarmanVortexGateValidator,
        reference_fn=get_expected_strouhal,
        mesh_info_fn=get_mesh_info,
        solver_config_fn=get_solver_config,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "VonKarmanVortexConstants",
    "create_von_karman_vortex_spec",
    "VonKarmanVortexGateValidator",
    "get_expected_strouhal",
    "get_mesh_info",
    "get_solver_config",
    "register",
]
