# AI-CFD Knowledge Harness — Project

**Version:** v1.4.0 (Next)
**Status:** Planning

---

## Overview

AI-CFD Knowledge Harness is an intelligent system for Computational Fluid Dynamics knowledge management, case generation, solver execution, and report automation. It uses natural language parsing, analogical reasoning, and literature-validated results.

## Architecture

- **PermissionLevel L0-L3**: Gate-based access control for knowledge operations
- **E1-E6 Analogical Reasoning**: Case similarity and transfer learning
- **Notion SSOT**: Single source of truth for project state and specifications
- **OpenFOAM Docker Executor**: Real solver integration with validation
- **Generic CaseGenerator v2**: Programmatic blockMeshDict generation
- **Report Generator**: Multi-format (HTML/PDF/JSON) with literature comparison
- **REST API Server**: FastAPI exposing all CLI functionality
- **Web Dashboard**: React-based UI for case management
- **Real-time Convergence Monitoring**: WebSocket residual streaming + DivergenceDetector

## Milestones

| Milestone | Phases | Status | Ship Date |
|-----------|--------|--------|-----------|
| M1 | 1-7 | ✅ Shipped | 2026-04-07 |
| v1.1.0 | 8-9 | ✅ Shipped | 2026-04-10 |
| v1.2.0 | 10-11 | ✅ Shipped | 2026-04-10 |
| v1.3.0 | 12-14 | ✅ Shipped | 2026-04-11 |

## v1.3.0 — Real-time Convergence Monitoring ✅

**Goal:** 仿真运行时实时追踪收敛曲线，Dashboard 可视化

**Delivered:**
- MON-01: OpenFOAM residual log parsing + WebSocket streaming (500ms debounce)
- MON-02: Dashboard real-time residual LineChart (Recharts, log-scale)
- MON-03: Job detail page convergence monitoring panel
- MON-04: Post-convergence ResultSummaryPanel (iteration, execution time, final residuals, Y+ placeholder)
- MON-05: Job abort button (docker kill)
- MON-06: DivergenceDetector with rolling 5-iteration window per variable + divergence_alert WebSocket message

**Archive:** `.planning/milestones/v1.3.0-ROADMAP.md`

---

## v1.4.0 — Next Milestone (TBD)

**Goal:** TBD

## Evolution

*Last updated: 2026-04-11 after v1.3.0 milestone*

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state
