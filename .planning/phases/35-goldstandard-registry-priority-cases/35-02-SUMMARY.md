---
phase: 35
plan: "02"
subsystem: knowledge-compiler
tags: [gold-standard, cfd, su2, openfoam, vof, schlichting, williamson, schmitt]

# Dependency graph
requires:
  - phase: "35-01"
    provides: GoldStandardRegistry singleton + GoldStandardService bridge + REST API router
provides:
  - 6 new GoldStandard case modules (SU2-02, SU2-04, SU2-09, SU2-10, SU2-19, OF-04)
  - Registry whitelist ID lookups for get_spec/get_validator/get_reference_data/get_mesh_info/get_solver_config
  - Corrected theta-beta-M bisection solver for oblique shock angle
affects:
  - Phase 36 (pipeline execution with GoldStandard validation gates)
  - api_server/services/gold_standard_service.py

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GoldStandard case module pattern: Constants dataclass + create_*_spec() factory + *GateValidator + get_expected_*() + get_mesh_info() + get_solver_config() + register(registry)"
    - "theta-beta-M oblique shock bisection solver (more robust than Newton)"
    - "Registry whitelist ID bidirectional lookup"

key-files:
  created:
    - knowledge_compiler/phase1/gold_standards/supersonic_wedge.py
    - knowledge_compiler/phase1/gold_standards/cylinder_compressible.py
    - knowledge_compiler/phase1/gold_standards/turbulent_flat_plate.py
    - knowledge_compiler/phase1/gold_standards/von_karman_vortex.py
    - knowledge_compiler/phase1/gold_standards/onera_m6.py
    - knowledge_compiler/phase1/gold_standards/dam_break_vof.py
  modified:
    - knowledge_compiler/phase1/gold_standards/__init__.py
    - knowledge_compiler/phase1/gold_standards/registry.py

key-decisions:
  - "Use bisection method for theta-beta-M oblique shock angle instead of Newton (robust convergence)"
  - "OF-04 DamBreak uses MULTIPHASE problem type + interPhaseChangeFoam (script-built mesh strategy B)"
  - "Registry get_spec() etc. fall back to whitelist_id_map lookup when case_id not found directly"
  - "6 new modules registered under both case_id (module name) and whitelist_id (SU2-02 etc.)"

patterns-established:
  - "Pattern: Constants dataclass + spec factory + validator + reference_fn + mesh_info_fn + solver_config_fn + register()"
  - "Pattern: Literature benchmark data dict returned by get_expected_*() with source citations"

requirements-completed: [GS-03, GS-04]

# Metrics
duration: 41min
completed: 2026-04-12
---

# Phase 35 Plan 02: 6 Priority GoldStandard Case Modules Summary

6 new priority GoldStandard case modules (SU2-02/04/09/10/19 + OF-04) registered and verified with 30 total cases in registry.

## Truths Established

| Case | Key Literature Value | Source |
|------|---------------------|--------|
| SU2-02 | shock_angle_deg = 45.34 (M=2.0, theta=15deg) | theta-beta-M analytical (bisection) |
| SU2-04 | drag_coefficient_cd = 1.15 (M=0.61) | NASA TN D-556 |
| SU2-09 | average_cf = 0.00227 (Re=1e6) | Schlichting Cf_bar = 0.036*Re^(-1/5) |
| SU2-10 | strouhal_number = 0.164 (range 0.16-0.19) | Williamson (1996) |
| SU2-19 | CL=0.275, CD=0.012, alpha=3.06deg | Schmitt (1994) AGARD-AR-138 |
| OF-04 | initial_column_height = 0.584m, H/L=2 | Martin & Moyce (1952) |

## Verification Results

All 6 cases pass:
- `registry.get_spec(case_id)` returns correct ReportSpec
- `registry.get_mesh_info(case_id)` returns mesh_strategy (A for SU2 cases, B for OF-04)
- `registry.get_solver_config(case_id)` returns solver_name and turbulence_model
- `registry.get_reference_data(case_id)` returns literature benchmark dict
- `registry.get_case_ids()` returns 30 entries (24 from whitelist + 6 new modules)
- Both module case_id (`supersonic_wedge`) and whitelist_id (`SU2-02`) work as lookup keys

## Case Module Structure

Each module follows the canonical pattern from `lid_driven_cavity.py`:
1. `*Constants` dataclass with literature values
2. `create_*_spec()` factory returning ReportSpec
3. `*GateValidator` class with `validate_report_spec()`
4. `get_expected_*()` returning literature benchmark data dict
5. `get_mesh_info()` returning mesh metadata dict
6. `get_solver_config()` returning solver config dict
7. `register(registry)` for auto-registration on import

## Deviations from Plan

- Fixed SU2-02 theta-beta-M solver: replaced broken Newton method with robust bisection (Rule 1 - bug fix)
- Fixed onera_m6.py: merged orphaned string literal in notes dict (Rule 1 - syntax bug)
- Enhanced registry.py: added whitelist_id bidirectional lookup to get_spec/get_validator/get_reference_data/get_mesh_info/get_solver_config (Rule 2 - missing critical functionality)

## Threat Flags

None - no new security surface introduced.

## Known Stubs

None identified.

## Commits

| Hash | Message |
|------|---------|
| 3863e07 | feat(35-02): Task 1 — SU2-02 Supersonic Wedge + SU2-04 Cylinder Compressible GoldStandard modules |
| 3254590 | feat(35-02): Task 2 — SU2-09 Turbulent Flat Plate + SU2-10 von Karman Vortex GoldStandard modules |
| e43d6bc | feat(35-02): Task 3 — SU2-19 ONERA M6 + OF-04 Dam Break VOF GoldStandard modules |
| 17e4898 | feat(35-02): Task 4 — Update gold_standards __init__.py with 6 new case modules |
| b3d1677 | fix(35-02): fix SU2-02 shock angle bisection solver and registry whitelist ID lookup |

## Self-Check: PASSED

- [x] All 6 case modules created and syntactically valid
- [x] All 6 cases register under both module case_id and whitelist_id
- [x] All 6 have spec, mesh_info, solver_config, reference_data
- [x] SU2-02 shock_angle_deg = 45.34 (bisection verified)
- [x] SU2-04 drag_coefficient = 1.15
- [x] SU2-09 average_cf = 0.00227
- [x] SU2-10 strouhal = 0.164 (in 0.16-0.19 range)
- [x] SU2-19 CL = 0.275, alpha = 3.06
- [x] OF-04 column_height = 0.584m
- [x] 30 total cases in registry (24 + 6 new)
