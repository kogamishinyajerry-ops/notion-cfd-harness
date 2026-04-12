---
gsd_state_version: 1.0
milestone: v1.7.0
milestone_name: Pipeline Orchestration & Automation
status: defining_requirements
last_updated: "2026-04-12"
---

# State

## Project

- **Name**: AI-CFD Knowledge Harness
- **Root**: /Users/Zhuanz/Desktop/notion-cfd-harness
- **Version**: v1.7.0
- **Milestone**: v1.7.0 — Pipeline Orchestration & Automation

## Current Position

Phase: Not started (defining requirements)
Plan: —
**Active milestone:** v1.7.0 Pipeline Orchestration & Automation
**Status:** Defining requirements
**Next:** Requirements gathering in progress

## Active Milestone Context

**Goal:** 将孤立的组件（case generation → solver execution → convergence monitoring → 3D visualization → report generation）串联为端-to-end自动化流水线

**Target features (TBD — requirements in progress):**
- PO-01: Pipeline 编排引擎
- PO-02: 批量作业调度
- PO-03: 跨 case 比较引擎
- PO-04: Pipeline 状态持久化与恢复
- PO-05: Pipeline 可视化 DAG

## Key Architecture (from v1.6.0)

- `@exportRpc` → `@ctrl.add`/`@state.change` (trame reactive pattern)
- React dashboard embeds trame Vue.js viewer as iframe
- `CFDViewerBridge.ts` uses `window.postMessage` for React-Vue communication
- Filter registry uses UUID keys
- `TrameSessionManager` — Docker lifecycle, 30-min idle timeout

## Blockers

None — roadmap ready for planning

## Session Continuity

After requirements confirmed: spawn 4 parallel researchers → define requirements → create roadmap
