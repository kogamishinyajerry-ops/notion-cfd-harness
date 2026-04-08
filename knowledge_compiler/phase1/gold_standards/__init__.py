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
    # Cold Start Whitelist
    "ColdStartCase",
    "ColdStartWhitelist",
    "load_cold_start_whitelist",
]
