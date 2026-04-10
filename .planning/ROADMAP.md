# AI-CFD Knowledge Harness — Roadmap

## Milestones

- ✅ **M1** — Well-Harness AI-CFD OS (Phases 1-7, shipped 2026-04-07)
- ✅ **v1.1.0** — Report Automation & CaseGenerator v2 (Phases 8-9, shipped 2026-04-10)
- 🔄 **v1.2.0** — API & Web Interface (Phases 10-11, planning)

## Phases

<details>
<summary>✅ M1 — Phases 1-7 (completed 2026-04-07)</summary>

### Phase 1: Knowledge Compiler
- **Goal**: NL parser / Gates(G1-G2) / Gold Standards / Teach Mode
- **Status**: ✅ Complete (Opus Approved)

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

</details>

<details>
<summary>✅ v1.1.0 — Phases 8-9 (completed 2026-04-10)</summary>

### Phase 8: 通用 CaseGenerator
- **Goal**: 从 template-based preset (3个case) 进化到任意 OpenFOAM geometry 参数化生成
- **Status**: ✅ Complete
- **Depends on**: Phase 7
- **Plans**: 08-01, 08-02, 08-03, 08-04

### Phase 9: Report Automation & Postprocess Intelligence
- **Goal**: 从 SolverResult 自动生成结构化报告 — PostprocessPipeline + ReportGenerator + ReportTeachMode + ComparisonEngine
- **Status**: ✅ Complete
- **Depends on**: Phase 8
- **Plans**: 09-01, 09-02, 09-03

</details>

<details>
<summary>🔄 v1.2.0 — Phases 10-11 (planning)</summary>

### Phase 10: REST API Server
- **Goal**: FastAPI-based REST API exposing all CLI functionality
- **Status**: 🔄 Planning
- **Depends on**: Phase 9
- **Plans**: 10-01, 10-02, 10-03

### Phase 11: Web Dashboard
- **Goal**: React-based UI for case management, job monitoring, report viewing
- **Status**: 🔄 Planning
- **Depends on**: Phase 10
- **Plans**: 11-01, 11-02, 11-03

</details>

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1 | M1 | - | Complete | 2026-04-07 |
| 2a-c | M1 | - | Complete | 2026-04-07 |
| 3 | M1 | - | Complete | 2026-04-07 |
| 4 | M1 | - | Complete | 2026-04-07 |
| 5 | M1 | - | Complete | 2026-04-07 |
| 6 | M1 | - | Complete | 2026-04-07 |
| 7 | M1 | - | Complete | 2026-04-07 |
| 8 | v1.1.0 | 4/4 | Complete | 2026-04-10 |
| 9 | v1.1.0 | 3/3 | Complete | 2026-04-10 |
| 10 | v1.2.0 | 3/3 | Complete   | 2026-04-10 |
| 11 | v1.2.0 | 3/3 | Complete   | 2026-04-10 |

---

**Full milestone history:** `.planning/MILESTONES.md`
