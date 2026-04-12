# Project Research Summary

**Project:** AI-CFD Knowledge Harness v1.8.0 — System Integration & GoldStandard Expansion
**Domain:** CFD Knowledge Compilation + Workflow Orchestration Integration
**Researched:** 2026-04-12
**Confidence:** MEDIUM-HIGH

## Executive Summary

v1.8.0 bridges two previously isolated systems: `knowledge_compiler/` (GoldStandardLoader, BenchmarkSuite) and `api_server/` (PipelineExecutor, ComparisonService). The core deliverable is a `GoldStandardRegistry` service that auto-discovers all 30 whitelist cases, a FastAPI bridge to expose it, and integration into the pipeline orchestration so cases can be validated against literature benchmarks as part of any pipeline run.

Stack additions are minimal: zero new pip packages, zero new npm packages. All work is pure Python + TypeScript additions using existing patterns.

## Key Findings

### GoldStandard Coverage Gap

| Category | Count | Status |
|----------|-------|--------|
| Total whitelist cases | 30 | OF-01~06 + SU2-01~24 |
| Existing GoldStandard modules | 5 | lid_driven_cavity, backward_facing_step, inviscid_bump, inviscid_wedge, laminar_flat_plate |
| Missing | 24 | SU2-02,04,09,10,19 + 19 others |
| Priority missing | 6 | SU2-02, SU2-04, SU2-09, SU2-10, SU2-19, OF-04 |

### Architecture: Bridge Pattern

```
knowledge_compiler/phase1/gold_standards/
  ├── registry.py          ← GoldStandardRegistry (auto-discovery)
  ├── cold_start.py        ← ColdStartWhitelist YAML loader
  ├── lid_driven_cavity.py ← existing pattern reference
  └── SU2_02/, OF_04/, ... ← 24 new case modules

api_server/services/
  └── gold_standard_service.py  ← Bridge service

api_server/routers/
  └── gold_standards.py         ← REST API router

PipelineExecutor step type: GOLDSTANDARD
ComparisonService: validate_against_gold_standard()
```

**Build order:** Registry (zero deps) → Bridge service → API router → PipelineExecutor dispatch → 24 case modules (parallelizable)

### Integration Points

1. `StepType.GOLDSTANDARD` added to step_wrappers.py dispatch
2. `GoldStandardLoader.get_reference_data(case_id)` → ComparisonService.validate_against_gold_standard()
3. `ColdStartCase.solver_command` → PipelineCreate template expansion
4. Provenance hash computation wired into `run_wrapper` post-execution

### Critical Pitfalls (from v1.8.0 research)

| ID | Severity | Issue | Fix |
|----|----------|-------|-----|
| GS-2.1 | Critical | Circular import: KnowledgeService lazy-imports KnowledgeRegistry | Import isolation via DTO translation layer |
| GS-1.2 | High | Mesh strategy not encoded in GoldStandard modules | Add `get_mesh_info()` function to each case |
| GS-1.3 | High | Solver config not captured | Add `get_solver_config()` function to each case |
| GS-2.3 | High | GoldStandardLoader not thread-safe | Add registration lock or thread-local registry |
| GS-2.5 | High | LiteratureComparison vs MetricsRow model mismatch | Unified `ReferenceComparison` Pydantic DTO |
| WR-01 | High | pvpython docker script path | Use `docker cp` or stdin cat |
| WR-02 | Medium | subprocess trame session cleanup | Add TTL registry or delete script after launch |

### Phase 5 Validation

Phase 5 (Production Readiness) implementation complete:
- 4 modules: performance/, observability/, security/, operations/
- 5,211 LOC core code + 301 tests
- Opus 4.6 review: CONDITIONAL_PASS (6 findings, all fixed)
- Remaining: sync Notion Phase 5 status + confirm full regression (1,920+ tests)

## Research Agent Results

| Agent | Status | Key Output |
|-------|--------|------------|
| Stack research | ✅ Complete | STACK.md: zero new deps, registry pattern |
| Features research | ✅ Complete | FEATURES.md: GoldStandard anatomy + 6 priority cases |
| Architecture research | ✅ Complete | ARCHITECTURE.md: bridge pattern + 3-phase build order |
| Pitfalls research | ✅ Complete | PITFALLS.md: 11 pitfalls (3 Critical, 5 High, 3 Medium) |

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Stack | HIGH | Zero new deps confirmed; existing patterns from 5 GS modules + 5 API routers |
| Architecture | MEDIUM-HIGH | Bridge pattern clear; SU2/sweep integration open questions |
| Case implementation | HIGH | 5 confirmed implementations to copy from; literature data is the bottleneck |
| Integration | MEDIUM | No existing integration tests; patterns are sound but untested |

## Implications for Roadmap

### Phase 35: GoldStandard Expansion (Foundation)
- GS-01: GoldStandardRegistry + GoldStandardLoader service
- GS-02: Bridge service + API router
- GS-03: Priority case implementations (SU2-02, SU2-04, SU2-09, SU2-10, SU2-19, OF-04)
- GS-04: Mesh/solver metadata functions

### Phase 36: System Integration
- GS-05: PipelineExecutor GOLDSTANDARD step type dispatch
- GS-06: ComparisonService gold_standard validation method
- GS-07: ColdStartCase → PipelineCreate template wiring
- GS-08: Provenance hash computation in run_wrapper

### Phase 37: Bug Fixes
- WR-01: pvpython docker script path fix
- WR-02: subprocess trame session cleanup
- Thread-safety fixes (GS-2.3, GS-2.1)

### Phase 38: Phase 5 Acceptance
- 301 tests confirmed + Opus review Pass

---

*Research completed: 2026-04-12*
*Ready for roadmap: yes*
