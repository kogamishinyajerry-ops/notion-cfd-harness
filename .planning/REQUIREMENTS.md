# AI-CFD Knowledge Harness — v1.8.0 Requirements

**Milestone:** v1.8.0 — System Integration & GoldStandard Expansion
**Status:** Active
**Created:** 2026-04-12

---

## Overview

v1.8.0 bridges the knowledge compilation system (`knowledge_compiler/`) with the pipeline orchestration system (`api_server/`), expands GoldStandard case coverage from 5 to 29, fixes known bugs WR-01/WR-02, and validates Phase 5 completion.

---

## Requirements

### GS-01: GoldStandard Registry & Loader

**Type:** Infrastructure
**Priority:** P0 (blocks all other requirements)
**Phase:** 35

GoldStandardRegistry auto-discovers all `gold_standards/` Python modules via `importlib.metadata` or filesystem scan, aggregates `ReportSpec` templates and literature reference data, and provides a thread-safe `GoldStandardLoader` with `get_case_ids()`, `get_report_spec(case_id)`, `get_reference_data(case_id)`, `get_mesh_info(case_id)`, and `get_solver_config(case_id)` methods.

- Thread-safe (registration lock for concurrent access)
- Covers all 30 whitelist cases
- Returns structured `GoldStandardCase` DTOs

### GS-02: GoldStandard Bridge Service & REST API

**Type:** API
**Priority:** P0
**Phase:** 35

`api_server/services/gold_standard_service.py` bridges `GoldStandardRegistry` to FastAPI. Exposes `GET /gold-standard-cases` (list all cases), `GET /gold-standard-cases/{case_id}` (detail + ReportSpec), `GET /gold-standard-cases/{case_id}/reference-data` (literature values), `POST /gold-standard-cases/{case_id}/validate` (validate ReportSpec output against gold standard).

- Follows existing router pattern from `cases.py` / `knowledge.py`
- Pydantic DTO translation layer at API boundary (decoupled from knowledge_compiler domain classes)

### GS-03: Priority GoldStandard Case Implementations

**Type:** Feature
**Priority:** P0
**Phase:** 35

Implement 6 priority cases from the 30-case whitelist, each following the existing GoldStandard pattern (Constants dataclass + `create_*_spec()` + `get_expected_*()` + `*GateValidator`):

| Case ID | Name | Literature Source |
|---------|------|------------------|
| SU2-02 | Supersonic Wedge (Mach 2.0) | Anderson Modern Compressible Flow (shock angle tables) |
| SU2-04 | Cylinder Compressible (Mach 0.61) | NASA TN D-556 (Drag coefficient tables) |
| SU2-09 | Turbulent Flat Plate (Re=10^6) | Schlichting turbulent boundary layer (skin friction tables) |
| SU2-10 | von Kármán Vortex Street (Re=100) | Strouhal number St=0.16-0.19 |
| SU2-19 | ONERA M6 Transonic Wing (Mach 0.84) | Schmitt ONERA M6 experimental pressure distribution |
| OF-04 | VOF Dam Break |流氓 Soft: experimental column height + arrival time data |

- Each case includes `get_mesh_info()` and `get_solver_config()`
- Each case has unit tests against published reference tables
- All 24 remaining cases listed in `.planning/research/FEATURES.md` as GS-03-ext

### GS-04: GoldStandard Pipeline Step Type

**Type:** Feature
**Priority:** P1
**Phase:** 36

`StepType.GOLDSTANDARD` added to `step_wrappers.py` dispatch. Pipeline can specify `gold_standard_case_id` as a step parameter. Step runs case generation + solver execution + convergence monitoring, then calls `ComparisonService.validate_against_gold_standard()` to produce structured validation result.

- Follows existing 5 step type wrapper pattern
- `StepResult` with `Status` enum: `success`, `diverged`, `validation_failed`, `error`

### GS-05: ComparisonService GoldStandard Validation

**Type:** Feature
**Priority:** P1
**Phase:** 36

`ComparisonService.validate_against_gold_standard(case_id, report_spec)` method that:
1. Calls `GoldStandardLoader.get_reference_data(case_id)`
2. Compares scalar metrics against literature values with configurable tolerance
3. Produces `ValidationResult` with per-metric delta percentages
4. Returns structured `LiteratureComparison` DTO

### GS-06: ColdStartWhitelist → Pipeline Template Wiring

**Type:** Feature
**Priority:** P1
**Phase:** 36

`POST /pipelines/from-gold-standard/{case_id}` endpoint that:
1. Loads `ColdStartCase` metadata from YAML
2. Expands into `PipelineCreate` spec with appropriate step types
3. Returns ready-to-start pipeline

Enables one-click pipeline creation from GoldStandard case.

### GS-07: Provenance Hash Computation

**Type:** Feature
**Priority:** P1
**Phase:** 36

Provenance hash computation wired into `run_wrapper` post-execution:
- OpenFOAM version hash
- Mesh seed hash
- Solver config hash
- Compiler/interpreter hash
Populates 4 provenance columns on `sweep_cases` table (Schema v4).

### WR-01: pvpython Docker Script Path Fix

**Type:** Bug Fix
**Priority:** P0
**Phase:** 37

pvpython docker container cannot access host filesystem paths. Fix: use `docker cp` to copy script into container, or pass script via stdin `cat | docker run --rm -i ...`.

**Root cause:** `docker run -v /host/path:/container/path` requires pre-mounted host directory.

### WR-02: Subprocess Trame Session Cleanup

**Type:** Bug Fix
**Priority:** P1
**Phase:** 37

`subprocess.Popen` launched for trame server not cleaned up on pipeline abort or timeout. Fix: add TTL registry (`{session_id: (pid, expiry)}`) with background cleanup thread, or use `delete_after_launch` pattern.

### GS-08: Phase 5 Acceptance Validation

**Type:** Validation
**Priority:** P0
**Phase:** 38

Confirm Phase 5 (Production Readiness & Operations) completion:
- 301 tests pass (`python3 -m pytest tests/test_p5_*.py -v`)
- Full regression: 1,920+ tests pass (`python3 -m pytest tests/ -q`)
- Notion: Phase 5 record created with Status=Pass, ReviewDecision=Pass
- Project Current Phase updated to "Phase 5: Production Readiness & Operations (Pass)"

---

## Out of Scope

- HPC scheduler integration (SLURM/PBS) — single-node Docker target
- GoldStandard case implementation beyond the 6 priority cases (24 remaining deferred to v1.9)
- State persistence and recovery (PO-04) — deferred from v1.7.0
- Multi-user authentication/authorization — L0-L3 permission system already handles knowledge operations

---

## Dependencies

- Phase 35 (GoldStandard expansion) — zero external dependencies, starts first
- Phase 36 (System integration) — depends on Phase 35
- Phase 37 (Bug fixes) — independent, can run parallel to 35/36
- Phase 38 (Phase 5 validation) — depends on all prior phases passing tests

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| GoldStandardRegistry as service (not import) | Keeps knowledge_compiler and api_server decoupled; Pydantic DTO translation layer |
| Thread-safe loader via lock | PipelineExecutor uses threading.Thread; concurrent access must be safe |
| 6 priority cases first | Maximize coverage of diverse physics (supersonic, turbulent, vortex, transonic, VOF) |
| Provenance in run_wrapper post-execution | Pipeline owns Docker containers; provenance is a run artifact, not a launch parameter |

---

## Acceptance Criteria

| Requirement | Success Condition |
|-------------|-------------------|
| GS-01 | `GoldStandardRegistry().get_case_ids()` returns 30 entries |
| GS-02 | `GET /gold-standard-cases` returns 200 with array of 30 case summaries |
| GS-03 | SU2-02, SU2-04, SU2-09, SU2-10, SU2-19, OF-04 each have unit tests passing against literature tables |
| GS-04 | Pipeline with `StepType.GOLDSTANDARD` executes and produces `StepResult` |
| GS-05 | `validate_against_gold_standard()` returns structured `LiteratureComparison` with per-metric deltas |
| GS-06 | `POST /pipelines/from-gold-standard/SU2-02` returns valid `PipelineCreate` spec |
| GS-07 | `sweep_cases` provenance columns populated for pipeline runs |
| WR-01 | `pvpython` inside Docker container can execute script without host path mount |
| WR-02 | Trame subprocesses cleaned up within 30s of timeout/abort |
| GS-08 | 301 Phase 5 tests pass; Notion Phase 5 status = Pass |

---

*Last updated: 2026-04-12 — v1.8.0 requirements defined*
