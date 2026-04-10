# Milestones

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

