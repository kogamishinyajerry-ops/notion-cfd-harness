# Milestones

## v1.3.0 Real-time Convergence Monitoring (Shipped: 2026-04-11)

**Phases completed:** 7 phases, 20 plans, 14 tasks

**Key accomplishments:**

- 11 tests
- Core Methods:
- GenericCaseAdapter wrapping GenericOpenFOAMCaseGenerator with CasePreset-style interface + ExecutorFactory.get_generator() integration with 5 new Wave 3 tests
- Gap closure: 8-block hex generation for BODY_IN_CHANNEL geometry (was returning empty list)
- Phase:
- FastAPI REST API with case CRUD, job submission/status, knowledge registry queries, and OpenAPI/Swagger documentation - 32 tests passing
- WebSocket endpoint `/ws/jobs/{job_id}` for real-time job progress streaming with event broadcasting and connection management - 14 tests passing
- New State:
- Gap:

---

---

## v1.2.0 — API & Web Interface

**Shipped:** 2026-04-10
**Phases:** 10-11 (6 plans, 6 summaries)
**Status:** ✅ SHIPPED

### Key Accomplishments

1. **Phase 10: REST API Server** — FastAPI + JWT auth + WebSocket + case/job endpoints
2. **Phase 11: Web Dashboard** — React + TypeScript + case builder + job queue + report viewer

### Phase Details

#### Phase 10: REST API Server

- 10-01: FastAPI project structure, case/job endpoints (12 tests)
- 10-02: JWT authentication with RBAC (36 auth tests)
- 10-03: WebSocket streaming (14 WS tests)

#### Phase 11: Web Dashboard

- 11-01: React + TypeScript + Vite, routing, dark/light theme
- 11-02: Case builder UI with wizard
- 11-03: Job queue, real-time updates, report viewer

### Stats

- **LOC added:** ~5,000 (api_server/ + dashboard/)
- **Tests:** 1905 passed, 1 skipped
- **Tag:** v1.2.0

---

## v1.3.0 — Real-time Convergence Monitoring

**Planned:** 2026-04-10
**Phases:** TBD
**Status:** 🔄 Planning

### Target Features

- **RC-01**: 仿真进程残差数据 WebSocket 推送（日志解析）
- **RC-02**: Dashboard 实时残差曲线（Plotly，随迭代更新）
- **RC-03**: Job detail 页面收敛监控面板
- **RC-04**: 收敛完成后结果摘要展示

---

## v1.1.0 — Report Automation & CaseGenerator v2

**Shipped:** 2026-04-10
**Phases:** 8-9 (7 plans, 7 summaries)
**Status:** ✅ SHIPPED

### Key Accomplishments

1. **Phase 8: Generic CaseGenerator** — 从 template-based preset (3 case) 进化到任意 OpenFOAM geometry 参数化生成 (blockMeshDict programmatic generation, BC rendering, solver-aware assembly)

2. **Phase 9: Report Automation** — ReportGenerator (HTML+PDF+JSON multi-format), GoldStandardLoader (literature comparison Ghia 1982/Armaly 1983), ReportTeachMode (inline correction auto-apply D-10), CorrectionCallback (D-09)

### Phase Details

#### Phase 8: 通用 CaseGenerator

- 08-01: Typed dataclasses (GeometrySpec, MeshSpec, PhysicsSpec, BoundarySpec)
- 08-02: GenericOpenFOAMCaseGenerator core (blockMeshDict + BC + solver assembly)
- 08-03: Integration tests + Docker round-trip verification
- 08-04: Gap closure (BODY_IN_CHANNEL 8-block hex generation)

#### Phase 9: Report Automation

- 09-01: ReportGenerator core + Jinja2 HTML template (two-tier structure)
- 09-02: PDF (weasyprint) + JSON output formats
- 09-03: ReportTeachMode + CorrectionCallback + integration tests (14 tests)

### Stats

- **LOC added:** ~2,200 (knowledge_compiler/)
- **Tests:** 1823 passed, 1 skipped
- **Tag:** v1.1.0

---

## M1 — Well-Harness AI-CFD OS

**Shipped:** 2026-04-07
**Phases:** 1-7
**Status:** ✅ SHIPPED

### Key Accomplishments

1. **Phase 1: Knowledge Compiler** — NL parser, Gates (G1-G2), Gold Standards, Teach Mode
2. **Phase 2a-c: Execution Layer** — G1/G2 validation, Physics Planner, Result Validator
3. **Phase 3: Analogical Orchestrator** — E1-E6 analogy reasoning, PermissionLevel L0-L3
4. **Phase 4: Memory Network** — Versioned registry, propagation, Notion integration
5. **Phase 5: Production Readiness** — Cache, Connection Pool, Auth, RBAC, Audit, Backup
6. **Phase 6: Operational Validation** — SSOT cleanup, Whitelist ≥50, Mock E2E, Correction闭环
7. **Phase 7: Real Solver E2E** — OpenFOAM Docker executor, Real CFD vs literature validation
