#!/usr/bin/env python3
"""
GoldStandard: Cylinder Compressible Flow (SU2-04)

Reference implementation for transonic/supersonic flow over a circular
cylinder with drag coefficient from NASA TN D-556.

Based on:
- NASA Technical Note D-556 (1969) "Pressure Distribution and Force
  Coefficients for Cylinders at Mach Numbers from 0.20 to 5.50"
- Hoerner, S.F. (1965) Fluid-Dynamic Drag

Gold standard provides:
1. Validation template for cylinder compressible cases
2. Gate validation criteria
3. Literature benchmark data (drag coefficient)
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
# Cylinder Compressible Constants
# ============================================================================

class CylinderCompressibleConstants:
    """Physical constants for compressible cylinder flow case"""

    # Flow conditions (NASA TN D-556)
    MACH = 0.61  # Upstream Mach number (transonic)
    DRAG_COEFFICIENT = 1.15  # From NASA TN D-556 at M=0.61
    REYNOLDS_NUMBER = 4.0e6  # Characteristic Reynolds number

    # Geometry
    CYLINDER_DIAMETER = 1.0  # Normalized diameter

    # Domain
    DOMAIN_RADIUS = 20.0  # Far-field radius (normalised to cylinder diameter)
    WAKE_LENGTH = 10.0

    # Expected flow features
    STAGNATION_POINT = "x=0, y=0 (front)"
    SEPARATION_POINTS = {"upper": "x ~ 70deg", "lower": "x ~ -70deg"}

    # Mesh strategy
    MESH_STRATEGY = "A"


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_cylinder_compressible_spec(
    case_id: str = "cylinder_compressible",
) -> ReportSpec:
    """
    Create a gold standard ReportSpec for compressible cylinder flow case

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
        "pressure_coefficient_cp",
        "surface_pressure_distribution",
        "wake_velocity_profile",
    ]

    spec = ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"Compressible Cylinder (M={CylinderCompressibleConstants.MACH})",
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
        name="pressure_coefficient_cp",
        plane="surface",
        colormap="RdBu",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="surface_pressure_distribution",
        plane="surface",
        colormap="jet",
        range="auto",
    ))

    plots.append(PlotSpec(
        name="wake_velocity_profile",
        plane="x=5",
        colormap="viridis",
        range="auto",
    ))

    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []

    metrics.append(MetricSpec(
        name="drag_coefficient_cd",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="pressure_drag_coefficient_cdp",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    metrics.append(MetricSpec(
        name="mach_maximum",
        unit="-",
        comparison=ComparisonType.DIRECT,
    ))

    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []

    sections.append(SectionSpec(
        name="stagnation_point",
        type="point",
        position={"x": 0.0, "y": 0.0},
    ))

    sections.append(SectionSpec(
        name="cylinder_surface",
        type="wall",
        position={"r": 0.5},
    ))

    sections.append(SectionSpec(
        name="far_wake",
        type="plane",
        position={"x": 5.0},
    ))

    sections.append(SectionSpec(
        name="near_wake",
        type="plane",
        position={"x": 1.0},
    ))

    return sections


# ============================================================================
# Expected Literature Benchmark Data
# ============================================================================

def get_expected_drag_coefficient() -> Dict[str, Any]:
    """
    Get expected drag coefficient from NASA TN D-556.

    Returns:
        Dictionary with drag coefficient and reference data
    """
    mach = CylinderCompressibleConstants.MACH
    cd = CylinderCompressibleConstants.DRAG_COEFFICIENT

    return {
        "mach": mach,
        "drag_coefficient_cd": cd,
        "reynolds_number": CylinderCompressibleConstants.REYNOLDS_NUMBER,
        "pressure_drag_coefficient_cdp": 0.82,  # Estimated from NASA data
        "wave_drag_coefficient": 0.0,  # Sub-critical Mach
        "literature_source": "NASA TN D-556 (1969)",
        "hoerner_cd": 1.17,  # Hoerner (1965) high Re value for comparison
        "notes": "CD at transonic Mach numbers shows local peak due to wave effects",
    }


# ============================================================================
# Mesh Information
# ============================================================================

def get_mesh_info() -> Dict[str, Any]:
    """
    Get mesh metadata for compressible cylinder case.

    Returns:
        Dictionary with mesh strategy and parameters
    """
    return {
        "mesh_strategy": "A",
        "mesh_type": "structured_overset",
        "domain_radius": CylinderCompressibleConstants.DOMAIN_RADIUS,
        "cylinder_diameter": CylinderCompressibleConstants.CYLINDER_DIAMETER,
        "refinement_zones": [
            {"zone": "near_cylinder", "radius_ratio": 2.0, "resolution": 0.005},
            {"zone": "wake_region", "x_min": 0.5, "x_max": 10.0, "resolution": 0.02},
        ],
        "notes": "Overset mesh with cylinder and far-field blocks",
    }


# ============================================================================
# Solver Configuration
# ============================================================================

def get_solver_config() -> Dict[str, Any]:
    """
    Get solver configuration for compressible cylinder case.

    Returns:
        Dictionary with solver parameters
    """
    return {
        "solver_name": "SU2_CFD",
        "equation_system": "Navier-Stokes",
        "turbulence_model": "SA",  # Spalart-Allmaras
        "mach_number": CylinderCompressibleConstants.MACH,
        "gas_gamma": 1.4,
        "spatial_discretization": "AUSM+",
        "temporal_discretization": "Runge-Kutta",
        "cfl_number": 0.6,
        "reynolds_number": CylinderCompressibleConstants.REYNOLDS_NUMBER,
        "convergence_criteria": {"max_iterations": 8000, "residual_tolerance": 1e-7},
    }


# ============================================================================
# Gate Validation
# ============================================================================

class CylinderCompressibleGateValidator:
    """
    Gate validator for compressible cylinder gold standard

    Validates that a result meets the gold standard criteria.
    """

    def __init__(self):
        self.gold_spec = create_cylinder_compressible_spec()

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
        if "drag_coefficient_cd" in missing_metrics:
            results["passed"] = False
            results["errors"].append("Missing critical metric: drag_coefficient_cd")

        results["details"]["metric_coverage"] = len(gold_metric_names & actual_metric_names) / len(gold_metric_names)

        return results


# ============================================================================
# GoldStandard Auto-Registration
# ============================================================================

WHITELIST_ID = "SU2-04"


def register(registry: "GoldStandardRegistry") -> None:
    """Register this GoldStandard case with the global registry."""
    registry.register(
        case_id="cylinder_compressible",
        whitelist_id=WHITELIST_ID,
        spec_factory=create_cylinder_compressible_spec,
        validator_class=CylinderCompressibleGateValidator,
        reference_fn=get_expected_drag_coefficient,
        mesh_info_fn=get_mesh_info,
        solver_config_fn=get_solver_config,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "CylinderCompressibleConstants",
    "create_cylinder_compressible_spec",
    "CylinderCompressibleGateValidator",
    "get_expected_drag_coefficient",
    "get_mesh_info",
    "get_solver_config",
    "register",
]
