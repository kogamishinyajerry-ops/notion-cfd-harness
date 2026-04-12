# AI-CFD Knowledge Harness — Roadmap

## Milestones

- [x] **M1** — Well-Harness AI-CFD OS (Phases 1-7, shipped 2026-04-07)
- [x] **v1.1.0** — Report Automation & CaseGenerator v2 (Phases 8-9, shipped 2026-04-10)
- [x] **v1.2.0** — API & Web Interface (Phases 10-11, shipped 2026-04-10)
- [x] **v1.3.0** — Real-time Convergence Monitoring (shipped 2026-04-11)
- [x] **v1.4.0** — ParaView Web 3D Visualization (shipped 2026-04-11)
- [x] **v1.5.0** — Advanced Visualization (Phases 19-22, shipped 2026-04-11)
- [x] **v1.6.0** — ParaView Web to Trame Migration (Phases 23-28, shipped 2026-04-12)
- [x] **v1.7.0** — Pipeline Orchestration & Automation (Phases 29-34, shipped 2026-04-12)
- [ ] **v1.8.0** — System Integration & GoldStandard Expansion (Phase 35 complete, Phase 36-38 pending)

<details>
<summary>✅ v1.7.0 — Pipeline Orchestration & Automation (SHIPPED 2026-04-12)</summary>

- [x] Phase 29: Foundation — Data Models + SQLite Persistence (2/2 plans) — completed 2026-04-12
- [x] Phase 30: PO-01 Orchestration Engine (4/4 plans) — completed 2026-04-12
- [x] Phase 31: Pipeline REST API + React Dashboard (4/4 plans) — completed 2026-04-12
- [x] Phase 32: PO-02 Parametric Sweep (2/2 plans) — completed 2026-04-12
- [x] Phase 33: PO-05 DAG Visualization (1/1 plans) — completed 2026-04-12
- [x] Phase 34: PO-03 Cross-Case Comparison (2/2 plans) — completed 2026-04-12

</details>

---

## v1.7.0 Coverage (Archived)

**13/13 requirements shipped (PIPE-01 through PIPE-13)**

| Phase | Requirement | Description | Status |
|-------|-------------|-------------|--------|
| 29 | PIPE-01 | Pipeline Data Model | ✅ Complete |
| 30 | PIPE-02 | Pipeline State Machine | ✅ Complete |
| 30 | PIPE-03 | Structured Result Objects | ✅ Complete |
| 30 | PIPE-04 | Component Wrapping | ✅ Complete |
| 30 | PIPE-05 | WebSocket Pipeline Events | ✅ Complete |
| 30 | PIPE-06 | Cleanup Handler | ✅ Complete |
| 30 | PIPE-07 | Async/Sync Separation | ✅ Complete |
| 31 | PIPE-08 | Pipeline REST API | ✅ Complete |
| 31 | PIPE-09 | Dashboard Pipeline Pages | ✅ Complete |
| 32 | PIPE-10 | Parametric Sweep | ✅ Complete |
| 33 | PIPE-13 | Pipeline DAG Visualization | ✅ Complete |
| 34 | PIPE-11 | Cross-Case Comparison Engine | ✅ Complete |
| 34 | PIPE-12 | Cross-Case Comparison UI | ✅ Complete |

For full phase details, see: `.planning/milestones/v1.7.0-ROADMAP.md`

---

## v1.8.0 — System Integration & GoldStandard Expansion (Planning)

**Target features:**
1. **GoldStandard 扩展** — 实现 24 个缺失冷启动案例的 GoldStandard，重点：SU2-02/04/09/10/19, OF-04
2. **系统集成** — `knowledge_compiler/` GoldStandardLoader ↔ `api_server/` PipelineExecutor/ComparisonService 桥接
3. **WR-01/WR-02 修复** — pvpython docker path + subprocess trame session cleanup
4. **Phase 5 验收** — 301 tests pass + Opus 审查 Pass

### Phase 35: GoldStandard Registry & Priority Cases (2 plans, 2 waves) ✅ COMPLETE
**Plans:** 2/2 — committed `3f6417a` `8a33e6e` `5bc699d` `5b97937` `3863e07` `3254590` `e43d6bc` `17e4898`

Plans:
- [x] 35-01-PLAN.md — Wave 1: GS-01 GoldStandardRegistry + GS-02 Bridge Service + REST API
- [x] 35-02-PLAN.md — Wave 2: GS-03 6 Priority Cases + GS-04 Mesh/Solver Metadata

| Requirement | Description | Status |
|-------------|-------------|--------|
| GS-01 | GoldStandardRegistry + GoldStandardLoader | ✅ Complete |
| GS-02 | Bridge Service + REST API | ✅ Complete |
| GS-03 | 6 Priority Case Implementations | ✅ Complete |
| GS-04 | Mesh/Solver Metadata Functions | ✅ Complete |

### Phase 36: System Integration (2 plans, 2 waves)

**Plans:**
- [ ] 36-01-PLAN.md — Wave 1: GS-05 GOLDSTANDARD StepType + GS-06 validate_against_gold_standard()
- [ ] 36-02-PLAN.md — Wave 2: GS-07 from-gold-standard endpoint + GS-08 Provenance hash computation

| Requirement | Description | Status |
|-------------|-------------|--------|
| GS-05 | GOLDSTANDARD Step Type in PipelineExecutor | Pending |
| GS-06 | ComparisonService GoldStandard Validation | Pending |
| GS-07 | ColdStartWhitelist → Pipeline Template Wiring | Pending |
| GS-08 | Provenance Hash Computation | Pending |

### Phase 37: Bug Fixes
| Requirement | Description | Status |
|-------------|-------------|--------|
| WR-01 | pvpython Docker Script Path Fix | Pending |
| WR-02 | Subprocess Trame Session Cleanup | Pending |

### Phase 38: Phase 5 Acceptance
| Requirement | Description | Status |
|-------------|-------------|--------|
| GS-V1 | Phase 5 Tests Pass (301 tests) | Pending |
| GS-V2 | Full Regression Pass (1,920+ tests) | Pending |
| GS-V3 | Notion Phase 5 Record = Pass | Pending |

---

*Full milestone history: `.planning/MILESTONES.md`*
