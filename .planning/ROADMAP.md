# AI-CFD Knowledge Harness — Roadmap

## Phases

### Phase 1: Knowledge Compiler
- **Goal**: NL parser / Gates(G1-G2) / Gold Standards / Teach Mode
- **Status**: ✅ Complete (Opus Approved)
- **Plans**: Phase1_PLAN.md

### Phase 2a: Execution Layer — NL Parse & Gate
- **Goal**: G1/G2 gate validation for NL parsing pipeline
- **Status**: ✅ Complete (Score: 8.5)

### Phase 2b: Execution Layer — Physics Planner
- **Goal**: Physics planning from parsed NL
- **Status**: ✅ Complete (Score: 8.5)

### Phase 2c: Execution Layer — Result Validator
- **Goal**: Validation of solver results against physical constraints
- **Status**: ✅ Complete (Score: 8.5)

### Phase 3: Analogical Orchestrator
- **Goal**: E1-E6 analogy reasoning engine / PermissionLevel L0-L3
- **Status**: ✅ Complete (Score: 8.5)

### Phase 4: Memory Network
- **Goal**: Versioned registry / propagation / Notion integration
- **Status**: ✅ Complete

### Phase 5: Production Readiness
- **Goal**: Cache / Connection Pool / Auth / RBAC / Audit / Backup
- **Status**: ✅ Complete

### Phase 6: Operational Validation & Reliability Hardening
- **Goal**: SSOT cleanup / Whitelist ≥50 / Mock E2E / Correction闭环
- **Status**: ✅ Complete (Score: 9.0)

### Phase 7: Real Solver E2E
- **Goal**: OpenFOAM Docker executor / Real CFD vs literature validation
- **Status**: ✅ Complete
- **Depends on**: Phase 6

### Phase 8: 通用 CaseGenerator
- **Goal**: 从 template-based preset (3个case) 进化到任意 OpenFOAM geometry 参数化生成
- **Status**: ✅ Complete
- **Depends on**: Phase 7
- **Plans**:
  - [x] 08-01-PLAN.md — Typed dataclasses (GeometrySpec, MeshSpec, PhysicsSpec, BoundarySpec) + validation + test scaffold
  - [x] 08-02-PLAN.md — GenericOpenFOAMCaseGenerator: programmatic blockMeshDict + BC rendering + solver-aware file assembly
  - [x] 08-03-PLAN.md — Integration tests + backward compatibility + Docker round-trip verification
  - [x] 08-04-PLAN.md — Gap closure: BODY_IN_CHANNEL 8-block hex generation fix

### Phase 9: Report Automation & Postprocess Intelligence
- **Goal**: 从 SolverResult 自动生成结构化报告 — PostprocessPipeline + ReportGenerator + ReportTeachMode + ComparisonEngine
- **Status**: Planned
- **Depends on**: Phase 8
- **Plans**:
  - [x] 09-01-PLAN.md — ReportGenerator core + HTML template (two-tier structure, chart embedding, gold standards query)
  - [ ] 09-02-PLAN.md — PDF + JSON output formats (weasyprint integration, JSON schema)
  - [ ] 09-03-PLAN.md — ReportTeachMode + integration tests (inline correction, pipeline integration)
