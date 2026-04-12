# AI-CFD Knowledge Harness — Project

**Version:** v1.7.0 (Next)
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
- **ParaView Web 3D Visualization**: Embedded interactive CFD viewer (v1.4.0+v1.5.0) — migrating to trame (v1.6.0)

## Milestones

| Milestone | Phases | Status | Ship Date |
|-----------|--------|--------|-----------|
| M1 | 1-7 | ✅ Shipped | 2026-04-07 |
| v1.1.0 | 8-9 | ✅ Shipped | 2026-04-10 |
| v1.2.0 | 10-11 | ✅ Shipped | 2026-04-10 |
| v1.3.0 | 12-14 | ✅ Shipped | 2026-04-11 |
| v1.4.0 | 15-18 | ✅ Shipped | 2026-04-11 |
| v1.5.0 | 19-22 | ✅ Shipped | 2026-04-11 |
| v1.6.0 | 23-28 | ✅ Shipped | 2026-04-12 |

## v1.3.0 — Real-time Convergence Monitoring ✅

<details>
<summary>Archived — shipped 2026-04-11</summary>

**Goal:** 仿真运行时实时追踪收敛曲线，Dashboard 可视化

**Delivered:**
- MON-01: OpenFOAM residual log parsing + WebSocket streaming (500ms debounce)
- MON-02: Dashboard real-time residual LineChart (Recharts, log-scale)
- MON-03: Job detail page convergence monitoring panel
- MON-04: Post-convergence ResultSummaryPanel (iteration, execution time, final residuals, Y+ placeholder)
- MON-05: Job abort button (docker kill)
- MON-06: DivergenceDetector with rolling 5-iteration window per variable + divergence_alert WebSocket message

**Archive:** `.planning/milestones/v1.3.0-ROADMAP.md`
</details>

## v1.4.0 — ParaView Web 3D Visualization ✅

**Goal:** Embed ParaView Web viewer in Dashboard for interactive 3D CFD field visualization (velocity, pressure)

**Delivered:**
- **PV-01**: ParaView Web server integration (launch + lifecycle management)
- **PV-02**: Dashboard embedded 3D viewer (React + ParaView Web client)
- **PV-03**: Case result loading and field selection (velocity/pressure scalar fields)
- **PV-04**: Basic interaction (rotation, zoom, slicing, color mapping)

**Archive:** `.planning/milestones/v1.4.0-ROADMAP.md`

## v1.5.0 — Advanced Visualization ✅

**Goal:** Enhance ParaView Web 3D viewer with volume rendering, advanced filters, and screenshot export

**Delivered:**
- **VOL-01**: GPU-accelerated volume rendering toggle with Apple Silicon Mesa fallback warning and 2M cell OOM guard
- **FILT-01**: Clip, Contour, and StreamTracer filters via ParaView Web protocols with tabbed AdvancedFilterPanel UI
- **SHOT-01**: PNG screenshot export via viewport.image.render at viewport resolution with 500ms debounce

**Key decisions:**
- PID 1 entrypoint wrapper for protocol import ordering (vs CMD override)
- Smart Volume Mapper (adaptive) for volume rendering
- Filter registry via Python class-level dict tracking proxy id()

**Archive:** `.planning/milestones/v1.5.0-ROADMAP.md`

## v1.6.0 — ParaView Web → Trame Migration ✅

**Goal:** Replace ParaView Web infrastructure (wslink/vtkmodules/web) with trame (Kitware's official successor), achieving full feature parity with a modern reactive state architecture.

**Delivered:**
- **TRAME-01**: Trame backend skeleton — `pvpython /trame_server.py` in Docker, trame-vtk + trame-vuetify
- **TRAME-02**: All 7 `@exportRpc` → `@ctrl.add`/`@state.change`, UUID filter registry
- **TRAME-03**: `TrameSessionManager` — Docker lifecycle, 30-min idle timeout, job auto-launch
- **TRAME-04**: React-Vue iframe bridge — `CFDViewerBridge.ts` with origin-restricted postMessage, `TrameViewer.tsx`
- **TRAME-05**: Feature parity validated — 102 Python + 22 JS tests passing
- **TRAME-06**: 6 ParaView Web artifacts deleted (entrypoint_wrapper.sh, paraview_adv_protocols.py, paraview_web_launcher.py, ParaViewViewer.tsx, ParaViewViewer.css, paraviewProtocol.ts)

**Key decisions:**
- `@exportRpc` → `@ctrl.add`/`@state.change` (trame reactive pattern)
- React dashboard embeds trame Vue.js viewer as iframe
- Filter registry uses UUID keys (not Python `id()`) for restart stability
- `InvokeEvent` calls removed entirely (trame auto-pushes on state mutation)

**Archive:** `.planning/milestones/v1.6.0-ROADMAP.md`

## v1.7.0 — Pipeline Orchestration & Automation (Planning)

**Goal:** 将孤立的组件（case generation → solver execution → convergence monitoring → 3D visualization → report generation）串联为端到端自动化流水线，一键触发全流程。

**Target features:**
- **PO-01**: Pipeline 编排引擎 — 输入自然语言/参数，依次触发 generate → run → monitor → visualize → report
- **PO-02**: 批量作业调度 — 支持参数化扫描（parametric sweep）和批量运行
- **PO-03**: 跨 case 比较引擎 — 对比多个 case 的收敛历史、场分布、关键指标
- **PO-04**: Pipeline 状态持久化与恢复 — 中断后可恢复
- **PO-05**: Pipeline 可视化 DAG — Dashboard 展示作业依赖关系图

**Key context:**
- v1.6.0刚完成Trame迁移，所有可视化基础设施就绪
- 当前各组件通过独立API调用工作，需要 orchestration layer 串联
- 项目根部（api_server + dashboard）与 knowledge_compiler/ 平行发展

**Archive:** `.planning/milestones/v1.6.0-ROADMAP.md`

## Evolution

*Last updated: 2026-04-12 — v1.7.0 planning started*

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
