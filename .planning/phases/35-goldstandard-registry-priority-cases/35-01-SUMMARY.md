---
phase: 35
plan: "01"
subsystem: GoldStandard Registry & Bridge
tags: [GS-01, GS-02, thread-safe, REST-API, bridge-pattern]
dependency_graph:
  requires: []
  provides:
    - GoldStandardRegistry (thread-safe singleton, knowledge_compiler/phase1/gold_standards/registry.py)
    - GoldStandardService (bridge, api_server/services/gold_standard_service.py)
    - REST API: /gold-standard-cases endpoints (api_server/routers/gold_standards.py)
  affects:
    - Phase 35 Plan 35-02 (GS-03: 6 case modules, GS-04: mesh/solver metadata)
tech_stack:
  added:
    - threading.Lock singleton pattern
    - Lazy import for circular import avoidance
    - Pydantic DTO bridge between knowledge_compiler and api_server
key_files:
  created:
    - knowledge_compiler/phase1/gold_standards/registry.py
    - api_server/services/gold_standard_service.py
    - api_server/routers/gold_standards.py
  modified:
    - knowledge_compiler/phase1/gold_standards/lid_driven_cavity.py
    - knowledge_compiler/phase1/gold_standards/backward_facing_step.py
    - knowledge_compiler/phase1/gold_standards/inviscid_bump.py
    - knowledge_compiler/phase1/gold_standards/inviscid_wedge.py
    - knowledge_compiler/phase1/gold_standards/laminar_flat_plate.py
    - api_server/models.py
    - api_server/main.py
decisions:
  - id: "WHITELIST-ID-MAPPING"
    decision: "Added WHITELIST_ID constant to each GS module + _whitelist_id_map in registry + is_case_registered()/get_module_case_id() methods"
    reason: "Whitelist IDs (OF-01, SU2-01) differ from module-level case_ids (lid_driven_cavity, inviscid_bump); registry must map between them for correct has_gold_standard detection"
  - id: "THREAD-SAFETY"
    decision: "GoldStandardRegistry uses threading.Lock for singleton + all register operations; GoldStandardService uses threading.Lock for singleton"
    reason: "PipelineExecutor uses threading.Thread; concurrent access to registry must be safe"
  - id: "LAZY-REGISTRY"
    decision: "get_gold_standard_registry() defers _register_all_cases() until first access; _get_registry() in service uses lazy import"
    reason: "Avoids circular import between knowledge_compiler and api_server (GS-2.1 pitfall)"
metrics:
  duration: "<computed by orchestrator>"
  completed: "2026-04-12"
  tasks_completed: 4
---

# Phase 35 Plan 01: GoldStandard Registry & Priority Cases Summary

## One-liner

Thread-safe GoldStandardRegistry singleton with auto-discovery, exposing 5 registered cases + 25 pending via REST API at `/api/v1/gold-standard-cases`.

## Completed Tasks

| Task | Commit | Key Files |
|------|--------|-----------|
| Task 1: GoldStandardRegistry | `3f6417a` | registry.py, lid_driven_cavity.py (+ 4 other GS modules) |
| Task 2: Pydantic models | `8a33e6e` | api_server/models.py |
| Task 3: GoldStandardService bridge | `5bc699d` | gold_standard_service.py, registry.py |
| Task 4: REST API router | `5b97937` | gold_standards.py, main.py |

## Verification Results

```
PASS: 30 case IDs returned (OF-01~06, SU2-01~24)
PASS: All Pydantic models importable
PASS: 30 cases listed via service
  GoldStandard cases: ['OF-01', 'OF-02', 'SU2-01', 'SU2-02', 'SU2-03']
PASS: Router registered in main.py (4 routes)
PASS: No circular import detected
```

## What Was Built

### GoldStandardRegistry (knowledge_compiler/phase1/gold_standards/registry.py)
- Thread-safe singleton via `threading.Lock` (double-checked locking)
- `_spec_factories`, `_validator_classes`, `_reference_fns`, `_mesh_info_fns`, `_solver_config_fns` dicts
- `_whitelist_id_map` maps whitelist IDs (OF-01) to module case_ids (lid_driven_cavity)
- `is_case_registered(whitelist_id)` and `get_module_case_id(whitelist_id)` methods
- `get_case_ids()` returns all 30 whitelist case IDs
- `_register_all_cases()` lazily imports 5 existing GS modules and calls their `register()` functions

### GoldStandardService (api_server/services/gold_standard_service.py)
- `list_cases()` → `GoldStandardListResponse` with 30 cases, 5 marked `has_gold_standard=True`
- `get_case_detail()` → `GoldStandardCaseDetail` with ReportSpec + metadata
- `get_reference_data()` → reference dict or None
- `validate_result()` → `ValidationResultResponse` with per-metric details
- Lazy singleton via `_get_registry()` (circular import avoidance)

### REST API (api_server/routers/gold_standards.py)
- `GET /api/v1/gold-standard-cases` — list with filters (platform, tier, difficulty, has_gold_standard)
- `GET /api/v1/gold-standard-cases/{case_id}` — case detail
- `GET /api/v1/gold-standard-cases/{case_id}/reference-data` — literature values
- `POST /api/v1/gold-standard-cases/{case_id}/validate` — validate ReportSpec

## Deviations from Plan

### Rule 2 — Auto-added missing critical functionality: whitelist ID mapping
- **Issue**: Plan's `list_cases()` checked `c.id in spec_factory_keys` where `c.id` is whitelist ID (OF-01) but `spec_factory_keys` contains module-level IDs (lid_driven_cavity). This would always return False.
- **Fix**: Added `WHITELIST_ID` constant to each GS module, `_whitelist_id_map` dict to registry, and `is_case_registered()`/`get_module_case_id()` methods. Service now uses these for correct lookup.
- **Files**: registry.py, all 5 GS modules, gold_standard_service.py

## Threat Flags

None — no new security surface introduced (internal registry + read-only API endpoints).

## Known Stubs

None — all stubs identified and resolved. The 5 registered cases (OF-01, OF-02, SU2-01, SU2-02, SU2-03) have full ReportSpecs; the remaining 25 cases have whitelist metadata but no GoldStandard module yet.

## Self-Check

- [x] `knowledge_compiler/phase1/gold_standards/registry.py` exists
- [x] `api_server/services/gold_standard_service.py` exists
- [x] `api_server/routers/gold_standards.py` exists
- [x] `api_server/models.py` updated with 7 new Pydantic models
- [x] `api_server/main.py` registers gold_standards router
- [x] All 4 commits present in git log
- [x] No circular import: `from api_server.services.gold_standard_service import ...; from knowledge_compiler.phase1.gold_standards.lid_driven_cavity import ...` succeeds

## Self-Check: PASSED
