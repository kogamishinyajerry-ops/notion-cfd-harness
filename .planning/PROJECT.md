# AI-CFD Knowledge Harness — Project

**Version:** v1.8.0 (Next)
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
| v1.7.0 | 29-34 | ✅ Shipped | 2026-04-12 |

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

## v1.7.0 — Pipeline Orchestration & Automation ✅

**Goal:** 将孤立的组件（case generation → solver execution → convergence monitoring → 3D visualization → report generation）串联为端到端自动化流水线，一键触发全流程。

**Delivered:**
- **PIPE-01**: Pipeline/Step Pydantic models + SQLite persistence in `data/pipelines.db`
- **PIPE-02 ~ PIPE-07**: PO-01 Orchestration Engine — PipelineExecutor with Kahn's DAG topological sort, `StepResult` structured result objects (status enum), 5 step type wrappers (generate/run/monitor/visualize/report), `PipelineEventBus` WebSocket with 100-event ring buffer + 30s heartbeat, `CleanupHandler` docker-stop, `asyncio.to_thread()` async separation
- **PIPE-08 ~ PIPE-09**: Full REST API (POST/GET/PUT/DELETE /pipelines, /pipelines/{id}/start/pause/resume/cancel, /pipelines/{id}/steps/events) + React Dashboard (PipelinesPage, PipelineDetailPage with real-time WebSocket updates, PipelineCreatePage with DAG builder + circular dependency validation)
- **PIPE-10**: PO-02 Parametric Sweep — SweepRunner with `itertools.product` expansion, concurrency control (max N Docker containers), aggregate progress, `sweep_{id}/{combination_hash}/` output organization
- **PIPE-13**: PO-05 DAG Visualization — `@xyflow/react` replacing Steps list, dagre auto-layout, live node color updates, 360px step detail drawer
- **PIPE-11 ~ PIPE-12**: PO-03 Cross-Case Comparison — `ComparisonService` with provenance mismatch detection + convergence log parser + pvpython delta field, REST API 6 endpoints, React ConvergenceOverlay (Recharts log-scale LineChart), DeltaFieldViewer (trame iframe), MetricsTable (sortable, CSV/JSON export)

**Key decisions:**
- Pipeline orchestrator runs in dedicated `threading.Thread` NOT FastAPI BackgroundTasks (PIPE-07 / PITFALL 5.1)
- Docker container ownership: pipeline owns all containers, `TrameSessionManager` retains viewer containers on idle timeout (PIPE-04 / PITFALL 2.2)
- `Status` enum (success/diverged/validation_failed/error) over raw exit_code (PIPE-03 / PITFALL 2.1)
- Schema v4: 4 provenance columns on `sweep_cases` + `comparisons` table

**Archive:** `.planning/milestones/v1.7.0-ROADMAP.md`

## v1.8.0 — System Integration & GoldStandard Expansion (Planning)

**Goal:** 桥接知识编译系统与流水线系统，扩展冷启动黄金样例覆盖。

**Target features:**
1. **GoldStandard 扩展** — 为 24 个缺失冷启动案例实现 GoldStandard，重点高价值：supersonic wedge (SU2-02), cylinder compressible (SU2-04), turbulent flat plate (SU2-09), von Karman vortex (SU2-10), ONERA M6 (SU2-19), VOF dam break (OF-04)
2. **系统集成** — `knowledge_compiler/` GoldStandardLoader ↔ `api_server/` PipelineExecutor/ComparisonService 桥接
3. **WR-01/WR-02 修复** — pvpython docker script path (stdin cat) + subprocess trame session cleanup
4. **Phase 5 验收** — 301 tests 确认 + Opus 审查 Pass 确认

## Evolution

*Last updated: 2026-04-12 — v1.7.0 shipped, v1.8.0 planning*

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
