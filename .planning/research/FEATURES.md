# Feature Landscape: GoldStandard Expansion & System Integration

**Domain:** AI-CFD Knowledge Harness - CFD Case Validation & Literature Comparison
**Project:** AI-CFD Knowledge Harness v1.8.0
**Researched:** 2026-04-12
**Overall confidence:** HIGH (existing implementations provide clear pattern; literature-based reference data well-documented)

---

## Executive Summary

GoldStandards serve as the literature-validation anchor for the AI-CFD Knowledge Harness. Each GoldStandard is a Python module providing: (1) a `ReportSpec` template defining required plots/metrics/sections, (2) analytical `get_expected_*()` functions returning literature reference values, and (3) a `*GateValidator` class for comparing simulated results against benchmarks.

The current implementation covers 6 of 30 whitelist cases (OF-01, OF-02, SU2-01, SU2-02, SU2-03, SU2-06, SU2-07). The v1.8.0 expansion requires 24 additional GoldStandard implementations plus a `GoldStandardLoader` bridge to the `api_server`'s `ComparisonService`.

---

## GoldStandard Anatomy

### Core Components

Every GoldStandard module follows this structure:

| Component | Purpose | Example |
|-----------|---------|---------|
| `*Constants` class | Physical parameters, geometry, flow conditions, tabulated literature data | `CavityConstants.RE_VALUES = [100, 400, 1000, 3200, 5000, 7500, 10000]` |
| `create_*_spec()` | Returns `ReportSpec` with required plots, metrics, sections | Creates template for report generation |
| `get_expected_*()` | Returns literature reference data (analytical or tabulated) | `get_expected_ghia_data(Re)` returns velocity profiles |
| `*GateValidator` | Compares submitted `ReportSpec` against gold standard | Checks plot/metric/section coverage |
| `__all__` exports | Enables package-level imports | Must include all public symbols |

### ReportSpec Structure

```python
ReportSpec(
    report_spec_id=f"GOLD-{case_id}",
    name=f"Lid-Driven Cavity (Re={reynolds_number})",
    problem_type=ProblemType.INTERNAL_FLOW,  # INTERNAL_FLOW | EXTERNAL_FLOW | HEAT_TRANSFER | MULTIPHASE | FSI
    required_plots=[PlotSpec(name="...", plane="domain", colormap="viridis", range="auto")],
    required_metrics=[MetricSpec(name="lid_drag_coefficient", unit="-", comparison=ComparisonType.DIRECT)],
    critical_sections=[SectionSpec(name="centerline_vertical", type="centerline", position={"x": 0.5})],
    plot_order=["velocity_magnitude_contour", "pressure_contour", "streamlines", ...],
    comparison_method={"type": "direct", "tolerance_display": True},
    knowledge_layer=KnowledgeLayer.CANONICAL,
    knowledge_status=KnowledgeStatus.APPROVED,
)
```

### LiteratureComparison (Output of GoldStandardLoader)

```python
LiteratureComparison(
    metric_name="shock_angle",
    simulated_value=45.1,
    reference_value=45.34,
    error_pct=0.53,
    unit="deg",
    reference_source="theta-beta-M relation (weak shock)",
    reynolds_number=0,  # Compressible flow, Re not primary
    status="PASS",  # PASS if error_pct <= 5%, WARN if <= 10%, FAIL otherwise
)
```

### Verification Quantities by Case Type

| Case Type | Key Verification Quantity | Literature Source | Type |
|-----------|-------------------------|-------------------|------|
| Lid-driven cavity | u/v velocity centerline profiles | Ghia 1982 (Table I/II) | Tabulated array |
| Backward-facing step | Reattachment length xr/h | Armaly 1983 | Tabulated by Re |
| Inviscid wedge | Oblique shock angle | theta-beta-M relation | Analytical |
| Laminar flat plate | Skin friction coefficient Cf | Blasius: Cf = 0.664/sqrt(Re_x) | Analytical |
| Inviscid bump | Pressure ratio p_peak/p_inf | Isentropic relations | Analytical |
| Cylinder crossflow | Drag coefficient Cd, Strouhal number St | Zdravkovich 1997 | Tabulated |
| Von Karman vortex | Strouhal number St | Williamson 1989: St = 0.2 | Analytical |
| Turbulent flat plate | Cf(x), boundary layer thickness | Prandtl/Schlichting | Analytical |
| ONERA M6 | Cp distribution, CL | AGARD AR-303 | Tabulated |
| Dam break (VOF) | Alpha field evolution, front position | Qualitative validation | Qualitative |

---

## Table Stakes Features

Features users/configurers expect. Missing = GoldStandard expansion feels incomplete.

### For Each GoldStandard Module

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `*Constants` class | Provides physical parameters for all downstream functions | Low | Consistent naming convention |
| `create_*_spec()` | Generates ReportSpec template used by Report Generator | Low | Follows existing pattern |
| `get_expected_*()` | Returns literature reference values for comparison | Medium | May require tabulated data or analytical derivation |
| `*GateValidator` | Validates ReportSpec completeness against gold standard | Low | Template validation, not result validation |
| `__all__` exports | Enables `from gold_standards import *` | Low | Must include all public symbols |
| Unit tests | Validates physical constants, analytical functions, validator | Medium | See test pattern in `test_gold_standards_laminar_flat_plate.py` |
| Source citations | Literature references in docstrings | Low | Required for knowledge traceability |

### For GoldStandardLoader Integration

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Case-type mapping | Maps whitelist IDs to GoldStandard modules | Low | Extend existing `_case_type_loaders` dict |
| `get_reference_data()` | Returns literature data for given case type and Re | Medium | Needs per-case-type implementation |
| `compare_with_reference()` | Computes error_pct and PASS/WARN/FAIL status | Low | Already implemented in phase9_report |
| REST API endpoints | Exposes comparison via `api_server` | Medium | Bridge to `ComparisonService` |
| Whitelist-to-GoldStandard registry | Maps OF-01..OF-06, SU2-01..SU2-24 to modules | Low | Dict lookup |

---

## Differentiators

Features that elevate GoldStandard from "basic validation" to "powerful comparison engine." Not expected but highly valued.

### Advanced Literature Comparison

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Profile comparison (1D) | Compare full velocity profiles vs tabulated data, not just peak values | High | `lid_driven_cavity` has this for u/v centerlines |
| Multi-metric composite score | Aggregate PASS/WARN/FAIL across all metrics into single quality score | Medium | Useful for dashboard ranking |
| Uncertainty-aware comparison | Compare against range (min/max) rather than single value | High | Some literature provides confidence intervals |
| Regime detection | Automatically identify if case is laminar/transitional/turbulent | Medium | Relevant for SU2-17 (transitional flat plate) |

### Automation for New GoldStandards

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| GoldStandard template generator | Scaffold new GoldStandard from whitelist entry | Medium | Reads YAML, generates Python module skeleton |
| Batch literature lookup | Fetch reference data from known sources | High | Requires literature database or manual curation |
| Auto-validator generator | Generate `*GateValidator` from `ReportSpec` introspection | Medium | Reduce boilerplate |

### Knowledge Compilation Integration

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| E1-E6 analogy linking | Connect new cases to similar GoldStandards via analogy engine | High | Phase 3 feature, requires analogy schema |
| Correction propagation | When GoldStandard is corrected, propagate to derived cases | Medium | Would require provenance tracking |
| Multi-source reference | Compare against multiple literature sources | Medium | Some metrics have conflicting reference values |

---

## Anti-Features

Features to explicitly NOT build as part of GoldStandard expansion.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| CFD solver inside GoldStandard | Violates single responsibility; solver belongs in `execution_layer` | Keep GoldStandards as pure reference data |
| Runtime case execution | GoldStandards are static reference, not execution engines | Use `PipelineExecutor` for actual case runs |
| Non-physical tolerances | Setting tolerance too loose makes comparison meaningless | Default 5% threshold, document rationale |
| Hardcoded mesh requirements | Different cases have different mesh needs | Describe expected mesh class, not specific counts |
| Platform-specific reference values | Reference data should be solver-agnostic | Use physical quantities, not raw solver output |

---

## GoldStandard Coverage Analysis

### Current State (6 implemented)

| ID | Case Name | Verification Basis | Status |
|----|-----------|-------------------|--------|
| OF-01 | lid_driven_cavity | Ghia 1982 u/v profiles | Complete |
| OF-02 | backward_facing_step | Armaly 1983 reattachment | Complete |
| SU2-01 | inviscid_bump | Analytical pressure ratio | Complete |
| SU2-02 | inviscid_wedge | theta-beta-M shock angle | Complete |
| SU2-03 | laminar_flat_plate | Blasius Cf formula | Complete |
| SU2-06 | laminar_flat_plate_incompressible_heat_transfer | Heat transfer analogy | Partial (placeholder) |
| SU2-07 | laminar_backward_facing_step_incompressible | Armaly 1983 | Partial (placeholder) |

### Missing (24 cases)

**OpenFOAM (4 missing)**

| ID | Case Name | Priority | Difficulty | Key Reference | Verification Metric |
|----|-----------|----------|------------|---------------|---------------------|
| OF-03 | cylinder_crossflow | MEDIUM | Basic | Low-Re cylinder benchmark | Drag coefficient Cd |
| OF-04 | dam_break_laminar_vof | HIGH | Basic-to-Intermediate | Qualitative | Free-surface front position |
| OF-05 | cooling_cylinder_2d_cht | MEDIUM | Intermediate | Analytical CHT | Temperature distribution |
| OF-06 | heated_duct_cht | LOW | Intermediate | Analytical CHT | Wall-to-fluid heat transfer |

**SU2 (18 missing)**

| ID | Case Name | Priority | Difficulty | Key Reference | Verification Metric |
|----|-----------|----------|------------|---------------|---------------------|
| SU2-04 | laminar_cylinder_compressible | HIGH | Basic | Low-Re cylinder Zdravkovich | Drag coefficient Cd |
| SU2-05 | inviscid_hydrofoil | MEDIUM | Basic | Kantrowitz limit | Lift curve slope |
| SU2-08 | laminar_buoyancy_driven_cavity | MEDIUM | Basic | De Vahl Davis 1983 | Temperature gradient |
| SU2-09 | turbulent_flat_plate_incompressible | HIGH | Basic | Prandtl/Schlichting | Cf(x) distribution |
| SU2-10 | unsteady_von_karman_vortex_shedding | HIGH | Intermediate | Williamson 1989: St=0.2 | Strouhal number |
| SU2-11 | turbulent_naca0012_incompressible | MEDIUM | Basic-to-Intermediate | Abbott-von Doenhoff | Cp distribution |
| SU2-12 | species_transport_venturi_mixer | MEDIUM | Intermediate | Conservative scalar | Concentration profile |
| SU2-13 | species_transport_composition_dependent_kenics | MEDIUM | Intermediate | Mixture fraction | Blend uniformity |
| SU2-14 | streamwise_periodic_pin_fin | MEDIUM | Intermediate | Friction factor correlation | Pressure drop |
| SU2-15 | turbulent_bend_with_wall_functions | MEDIUM | Intermediate | Miller correlation | Loss coefficient |
| SU2-16 | turbulent_flat_plate_compressible | MEDIUM | Intermediate | Van Driest II | Cf(x) with compressibility |
| SU2-17 | transitional_flat_plate | LOW | Intermediate | Dhawan/R Narasimha | Transition location |
| SU2-18 | unsteady_naca0012_urans | MEDIUM | Intermediate | Time-accurate Cp | Hysteresis |
| SU2-19 | turbulent_onera_m6 | HIGH | Intermediate | AGARD AR-303 | Cp at 6 stations |
| SU2-20 | actuator_disk_variable_load | LOW | Intermediate | Actuator disk theory | Pressure jump |
| SU2-21 | static_conjugate_heat_transfer_three_cylinders | MEDIUM | Advanced | Analytical CHT | Temperature distribution |
| SU2-22 | radiative_heat_transfer_buoyancy_cavity | LOW | Advanced | Simple RHT | Net radiative flux |
| SU2-23 | unsteady_conjugate_heat_transfer | MEDIUM | Advanced | Time-accurate CHT | Temperature evolution |
| SU2-24 | solid_to_solid_cht_with_contact_resistance | LOW | Advanced | Thermal resistance network | Interface temperature drop |

### High-Value Priority Cases

From PROJECT.md v1.8.0 targets:
1. **SU2-02** (inviscid_wedge) - Already implemented
2. **SU2-04** (laminar_cylinder_compressible) - HIGH priority, basic bluff-body
3. **SU2-09** (turbulent_flat_plate_incompressible) - HIGH priority, first RANS seed
4. **SU2-10** (von_karman_vortex_shedding) - HIGH priority, first unsteady incompressible
5. **SU2-19** (turbulent_onera_m6) - HIGH priority, first compact 3D aerodynamic
6. **OF-04** (dam_break_laminar_vof) - HIGH priority, introduces multiphase

---

## Feature Dependencies

```
GoldStandard Module (per case)
    ├── Imports: knowledge_compiler.phase1.schema
    │   ├── ProblemType, ReportSpec, PlotSpec, MetricSpec, SectionSpec
    │   ├── ComparisonType, KnowledgeLayer, KnowledgeStatus
    │   └── LiteratureComparison (from gold_standard_loader.py)
    │
    ├── GoldStandardLoader.get_reference_data() calls get_expected_*()
    │
    └── api_server ComparisonService
            ├── Uses LiteratureComparison results
            ├── Displays in React Dashboard
            └── CSV/JSON export

GoldStandardLoader (bridge)
    ├── Maps case_type -> get_expected_* function
    ├── Returns Dict with reference data
    └── compare_with_reference() -> LiteratureComparison

PipelineExecutor (api_server)
    └── Runs cases, stores results
            └── ComparisonService queries GoldStandardLoader
```

### System Integration Architecture

```
knowledge_compiler/phase1/gold_standards/
    ├── __init__.py          # Exports all GoldStandard symbols
    ├── cold_start.py        # ColdStartWhitelist loader
    └── [case].py            # One module per GoldStandard case
                                 - *_constants.py (Constants class)
                                 - create_*_spec() (ReportSpec factory)
                                 - get_expected_*() (reference data)
                                 - *_validator.py (GateValidator class)

knowledge_compiler/phase9_report/gold_standard_loader.py
    ├── GoldStandardLoader   # Maps case_type -> get_expected_*()
    ├── LiteratureComparison # Result dataclass
    └── compare_with_reference()

api_server/
    └── comparison endpoints # Uses GoldStandardLoader for literature comparison
                                 - POST /comparisons (submit result for comparison)
                                 - GET /comparisons/{id} (get comparison result)
                                 - GET /goldstandards/{case_type} (get reference data)

PipelineExecutor (api_server)
    └── Runs cases, stores results
            └── ComparisonService queries GoldStandardLoader
```

---

## MVP Recommendation

Prioritize these for v1.8.0 GoldStandard expansion:

1. **SU2-04 (laminar_cylinder_compressible)**: Low complexity, high value - classic bluff-body benchmark
2. **SU2-09 (turbulent_flat_plate_incompressible)**: Low complexity - first RANS seed, analytical Cf formula well-established
3. **SU2-10 (von_karman_vortex_shedding)**: Medium complexity - Williamson St=0.2 is definitive, excellent validation target
4. **SU2-19 (turbulent_onera_m6)**: Medium complexity - first 3D aerodynamic case, AGARD data is authoritative
5. **OF-04 (dam_break_laminar_vof)**: High complexity - first multiphase seed, qualitative validation approach needed

**Also prioritize:**
- GoldStandardLoader bridge registration for all existing + new cases
- REST API integration with ComparisonService

**Defer:**
- SU2-24 (contact_resistance_cht): Advanced complexity, niche use case
- SU2-22 (radiative_heat_transfer): Radiation adds significant complexity

---

## Complexity Assessment

| Case | Complexity | Primary Challenge |
|------|------------|-------------------|
| SU2-04 (cylinder compressible) | Low | Tabulated drag data for low-Re range |
| SU2-09 (turbulent flat plate) | Low | Analytical Cf(x) formula well-established |
| SU2-10 (von Karman) | Medium | Unsteady extraction, St calculation, time-series comparison |
| SU2-19 (ONERA M6) | Medium | 3D case, tabulated AGARD Cp data at 6 stations |
| OF-04 (dam break VOF) | High | Qualitative validation, no single metric, free-surface tracking |
| SU2-21 (CHT 3 cylinders) | High | Multi-zone coupling, steady-state thermal distribution |
| SU2-24 (contact resistance) | High | Interface modeling, thermal resistance network |

---

## GoldStandard Module Template

New GoldStandard modules should follow this structure:

```python
#!/usr/bin/env python3
"""
Phase 1 Gold Standard: [Case Name]

Reference implementation for [Solver] Tutorial [ID].

[Brief description of physics and what is being validated].

Gold standard provides:
1. ReportSpec template for [Case Name]
2. Literature reference values via get_expected_*()
3. Gate validation via [Case]GateValidator
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt  # as needed
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
# [Case] Constants
# ============================================================================

class [Case]Constants:
    """Physical constants for [case name]"""

    # Geometry
    # ... constants ...

    # Flow conditions
    # ... constants ...

    # Literature reference values (tabulated or analytical)
    # ... constants ...


# ============================================================================
# Gold Standard ReportSpec
# ============================================================================

def create_[case]_spec(
    case_id: str = "[case_id]",
    # ... parameter list ...
) -> ReportSpec:
    """Create a gold standard ReportSpec for [case name]"""
    required_plots = _create_required_plots()
    required_metrics = _create_required_metrics()
    critical_sections = _create_required_sections()
    plot_order = [p.name for p in required_plots]

    return ReportSpec(
        report_spec_id=f"GOLD-{case_id}",
        name=f"[Case Name] ({param_description})",
        problem_type=ProblemType.[FLOW_TYPE],
        required_plots=required_plots,
        required_metrics=required_metrics,
        critical_sections=critical_sections,
        plot_order=plot_order,
        comparison_method={"type": "direct", "tolerance_display": True},
        anomaly_explanation_rules=[],
        knowledge_layer=KnowledgeLayer.CANONICAL,
        knowledge_status=KnowledgeStatus.APPROVED,
    )


def _create_required_plots() -> List[PlotSpec]:
    """Create required plot specifications"""
    plots = []
    plots.append(PlotSpec(name="...", plane="domain", colormap="viridis", range="auto"))
    return plots


def _create_required_metrics() -> List[MetricSpec]:
    """Create required metric specifications"""
    metrics = []
    metrics.append(MetricSpec(name="...", unit="...", comparison=ComparisonType.DIRECT))
    return metrics


def _create_required_sections() -> List[SectionSpec]:
    """Create required section specifications"""
    sections = []
    sections.append(SectionSpec(name="...", type="...", position={"x": ...}))
    return sections


# ============================================================================
# Expected Reference Values
# ============================================================================

def get_expected_[quantity](...) -> ...:
    """Get expected [quantity] from literature reference.

    [Description of formula or source].
    """
    # Implementation
    return result


# ============================================================================
# Gate Validation
# ============================================================================

class [Case]GateValidator:
    """Validates that a result meets the gold standard criteria."""

    def __init__(self):
        self.gold_spec = create_[case]_spec()

    def validate_report_spec(self, spec: ReportSpec) -> Dict[str, Any]:
        """Validate a ReportSpec against gold standard"""
        results = {"passed": True, "errors": [], "warnings": [], "details": {}}
        # Check required plots
        # Check required metrics
        # Check critical sections
        return results


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "[Case]Constants",
    "create_[case]_spec",
    "[Case]GateValidator",
    "get_expected_[quantity]",
]
```

---

## Sources

- **Ghia 1982**: Ghia, U., et al. (1982) "High-Re solutions for flow using Navier-Stokes equations and a multigrid method" JCP 48(3), 387-411
- **Armaly 1983**: Armaly, B.F., et al. (1983) "Experimental and theoretical investigation of backward-facing step flow" JFM 127, 473-496
- **Williamson 1989**: Williamson, C.H.K. (1989) "Oblique and parallel modes of vortex shedding in the wake of a cylinder" JFM 459, 67-82
- **AGARD AR-303**: ESDU 80020 (based on AGARD data) - ONERA M6 wing Cp distributions
- **Zdravkovich 1997**: Zdravkovich, M.M. (1997) "Flow Around Circular Cylinders, Vol. 1" Oxford University Press
- **De Vahl Davis 1983**: Natural convection of air in a square cavity - benchmark data
- **GoldStandard implementations**: `knowledge_compiler/phase1/gold_standards/*.py` — HIGH confidence
- **GoldStandardLoader**: `knowledge_compiler/phase9_report/gold_standard_loader.py` — HIGH confidence
- **Test patterns**: `tests/test_gold_standards_*.py` — HIGH confidence
- **Cold start whitelist**: `data/cold_start_whitelist.yaml` — HIGH confidence

---

*Feature research for: GoldStandard Expansion & System Integration (AI-CFD Knowledge Harness v1.8.0)*
*Researched: 2026-04-12*
