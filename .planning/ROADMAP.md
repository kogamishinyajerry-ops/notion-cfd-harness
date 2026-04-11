# AI-CFD Knowledge Harness — Roadmap

## Milestones

- ✅ **M1** — Well-Harness AI-CFD OS (Phases 1-7, shipped 2026-04-07)
- ✅ **v1.1.0** — Report Automation & CaseGenerator v2 (Phases 8-9, shipped 2026-04-10)
- ✅ **v1.2.0** — API & Web Interface (Phases 10-11, shipped 2026-04-10)
- ✅ **v1.3.0** — Real-time Convergence Monitoring (shipped 2026-04-11)

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
<summary>✅ v1.2.0 — Phases 10-11 (shipped 2026-04-10)</summary>

### Phase 10: REST API Server
- **Goal**: FastAPI-based REST API exposing all CLI functionality
- **Status**: ✅ Complete (6/6 verification passed)
- **Plans**: 10-01, 10-02, 10-03

### Phase 11: Web Dashboard
- **Goal**: React-based UI for case management, job monitoring, report viewing
- **Status**: ✅ Complete (5/5 verification passed)
- **Plans**: 11-01, 11-02, 11-03

**Archive:** [v1.2.0-ROADMAP.md](./milestones/v1.2.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.3.0 — Real-time Convergence Monitoring (shipped 2026-04-11)</summary>

**Goal:** 仿真运行时实时追踪收敛曲线，Dashboard 可视化

### Phase 12: Residual Streaming Backend
- **Goal**: OpenFOAM log residual parser + WebSocket streaming + job abort
- **Status**: ✅ Complete
- **Depends on**: Phase 11
- **Plans**: 12-01, 12-02, 12-03
- **Requirements**: MON-01 (残差数据 WS 推送), MON-05 (Job abort 按钮)
- **Key decisions**: Remove --rm from Docker for abort; ResidualStreamer as asyncio.Task alongside solver subprocess; debounce to 500ms

### Phase 13: Real-time Convergence Frontend
- **Goal**: Dashboard real-time residual charts + Job detail page
- **Status**: ✅ Complete (10/10 verification passed)
- **Depends on**: Phase 12
- **Plans**: 13-01, 13-02
- **Requirements**: MON-02 (实时残差曲线), MON-03 (Job detail 收敛监控面板)

### Phase 14: Convergence Intelligence
- **Goal**: Divergence detection + result summary
- **Status**: ✅ Complete (2/2 plans, verification passed)
- **Depends on**: Phase 13
- **Plans**: 14-01 (backend divergence detection), 14-02 (frontend result summary)
- **Requirements**: MON-04 (收敛完成后结果摘要), MON-06 (收敛异常检测 + 告警)

**Archive:** [v1.3.0-ROADMAP.md](./milestones/v1.3.0-ROADMAP.md)

</details>

<details>
<summary>🔄 v1.4.0 — ParaView Web 3D Visualization (planning)</summary>

**Goal:** Embed ParaView Web viewer in Dashboard for interactive 3D CFD field visualization

### Phase 15: ParaView Web Server Integration
- **Goal**: PV-01 — ParaView Web launcher + lifecycle management
- **Status**: ✅ Complete (2/2 plans)
- **Depends on**: Phase 11
- **Requirements**: PV-01 (ParaView Web server launch + lifecycle)
- **Plans**: 15-01 (core manager), 15-02 (API router + idle monitor)

### Phase 16: Dashboard 3D Viewer
- **Goal**: PV-02 — React component embedding ParaView Web client
- **Status**: 🔄 Planning (2/2 plans)
- **Depends on**: Phase 15
- **Requirements**: PV-02 (embedded 3D viewer)
- **Plans**: 16-01 (API service + ParaViewViewer component + CSS), 16-02 (JobDetailPage viewer tab integration)

### Phase 17: Case Result Loading & Field Selection
- **Goal**: PV-03 — Load OpenFOAM case, field selection, time stepping
- **Status**: 🔄 Planning
- **Depends on**: Phase 16
- **Requirements**: PV-03 (field selection + time navigation)

### Phase 18: Basic Interaction
- **Goal**: PV-04 — Rotation, zoom, slicing, color mapping
- **Status**: 🔄 Planning
- **Depends on**: Phase 17
- **Requirements**: PV-04 (camera, slice, color map)

**Key decisions**: ParaView Web (not trame) for v1.4.0; OpenFOAMReader native (no export); Slice only (defer Clip/Contour); 3 presets (defer custom)

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
| 12 | v1.3.0 | 3/3 | Complete   | 2026-04-11 |
| 13 | v1.3.0 | 2/2 | Complete   | 2026-04-11 |
| 14 | v1.3.0 | 2/2 | Complete | 2026-04-11 |
| 15 | v1.4.0 | 2/2 | Complete    | 2026-04-11 |
| 16 | v1.4.0 | 2/2 | Planning | - |
| 17 | v1.4.0 | TBD | Planning | - |
| 18 | v1.4.0 | TBD | Planning | - |

---

**Full milestone history:** `.planning/MILESTONES.md`
