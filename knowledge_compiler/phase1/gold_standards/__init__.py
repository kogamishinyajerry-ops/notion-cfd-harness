#!/usr/bin/env python3
"""
Phase 1 Gold Standards

Reference implementations for classic CFD benchmark cases.
Each gold standard provides:
- Complete ReportSpec template
- Required plots and metrics
- Gate validation criteria
- Reference to experimental/literature data
"""

from knowledge_compiler.phase1.gold_standards.backward_facing_step import (
    BackwardStepConstants,
    create_backward_facing_step_spec,
    BackwardStepGateValidator,
    get_expected_reattachment_length,
)

from knowledge_compiler.phase1.gold_standards.lid_driven_cavity import (
    CavityConstants,
    create_lid_driven_cavity_spec,
    CavityGateValidator,
    get_expected_ghia_data,
)

from knowledge_compiler.phase1.gold_standards.inviscid_bump import (
    InviscidBumpConstants,
    create_inviscid_bump_spec,
    InviscidBumpGateValidator,
    get_expected_pressure_ratio,
)

from knowledge_compiler.phase1.gold_standards.inviscid_wedge import (
    InviscidWedgeConstants,
    create_inviscid_wedge_spec,
    InviscidWedgeGateValidator,
    get_expected_shock_angle,
)

from knowledge_compiler.phase1.gold_standards.laminar_flat_plate import (
    LaminarFlatPlateConstants,
    create_laminar_flat_plate_spec,
    LaminarFlatPlateGateValidator,
    get_expected_blasius_cf,
)

from knowledge_compiler.phase1.gold_standards.supersonic_wedge import (
    SupersonicWedgeConstants,
    create_supersonic_wedge_spec,
    SupersonicWedgeGateValidator,
    get_expected_shock_angle as get_expected_shock_angle_wedge,
)

from knowledge_compiler.phase1.gold_standards.cylinder_compressible import (
    CylinderCompressibleConstants,
    create_cylinder_compressible_spec,
    CylinderCompressibleGateValidator,
    get_expected_drag_coefficient,
)

from knowledge_compiler.phase1.gold_standards.turbulent_flat_plate import (
    TurbulentFlatPlateConstants,
    create_turbulent_flat_plate_spec,
    TurbulentFlatPlateGateValidator,
    get_expected_skin_friction,
)

from knowledge_compiler.phase1.gold_standards.von_karman_vortex import (
    VonKarmanVortexConstants,
    create_von_karman_vortex_spec,
    VonKarmanVortexGateValidator,
    get_expected_strouhal,
)

from knowledge_compiler.phase1.gold_standards.onera_m6 import (
    OneraM6Constants,
    create_onera_m6_spec,
    OneraM6GateValidator,
    get_expected_pressure_distribution,
)

from knowledge_compiler.phase1.gold_standards.dam_break_vof import (
    DamBreakVOFConstants,
    create_dam_break_vof_spec,
    DamBreakVOFGateValidator,
    get_expected_column_height,
)

from knowledge_compiler.phase1.gold_standards.cold_start import (
    ColdStartCase,
    ColdStartWhitelist,
    load_cold_start_whitelist,
)

__all__ = [
    # Backward Facing Step
    "BackwardStepConstants",
    "create_backward_facing_step_spec",
    "BackwardStepGateValidator",
    "get_expected_reattachment_length",
    # Lid-Driven Cavity
    "CavityConstants",
    "create_lid_driven_cavity_spec",
    "CavityGateValidator",
    "get_expected_ghia_data",
    # Inviscid Bump (SU2)
    "InviscidBumpConstants",
    "create_inviscid_bump_spec",
    "InviscidBumpGateValidator",
    "get_expected_pressure_ratio",
    # Inviscid Wedge (SU2)
    "InviscidWedgeConstants",
    "create_inviscid_wedge_spec",
    "InviscidWedgeGateValidator",
    "get_expected_shock_angle",
    # Laminar Flat Plate (SU2)
    "LaminarFlatPlateConstants",
    "create_laminar_flat_plate_spec",
    "LaminarFlatPlateGateValidator",
    "get_expected_blasius_cf",
    # Supersonic Wedge (SU2-02) — Wave 2 Priority
    "SupersonicWedgeConstants",
    "create_supersonic_wedge_spec",
    "SupersonicWedgeGateValidator",
    "get_expected_shock_angle_wedge",
    # Cylinder Compressible (SU2-04) — Wave 2 Priority
    "CylinderCompressibleConstants",
    "create_cylinder_compressible_spec",
    "CylinderCompressibleGateValidator",
    "get_expected_drag_coefficient",
    # Turbulent Flat Plate (SU2-09) — Wave 2 Priority
    "TurbulentFlatPlateConstants",
    "create_turbulent_flat_plate_spec",
    "TurbulentFlatPlateGateValidator",
    "get_expected_skin_friction",
    # von Karman Vortex Street (SU2-10) — Wave 2 Priority
    "VonKarmanVortexConstants",
    "create_von_karman_vortex_spec",
    "VonKarmanVortexGateValidator",
    "get_expected_strouhal",
    # ONERA M6 Transonic Wing (SU2-19) — Wave 2 Priority
    "OneraM6Constants",
    "create_onera_m6_spec",
    "OneraM6GateValidator",
    "get_expected_pressure_distribution",
    # Dam Break VOF (OF-04) — Wave 2 Priority
    "DamBreakVOFConstants",
    "create_dam_break_vof_spec",
    "DamBreakVOFGateValidator",
    "get_expected_column_height",
    # Cold Start Whitelist
    "ColdStartCase",
    "ColdStartWhitelist",
    "load_cold_start_whitelist",
]

# Import all modules to trigger auto-registration
from knowledge_compiler.phase1.gold_standards import (
    lid_driven_cavity,
    backward_facing_step,
    inviscid_bump,
    inviscid_wedge,
    laminar_flat_plate,
    supersonic_wedge,
    cylinder_compressible,
    turbulent_flat_plate,
    von_karman_vortex,
    onera_m6,
    dam_break_vof,
)
