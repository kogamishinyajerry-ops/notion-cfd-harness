# AI-CFD Knowledge Harness — Project

**Version:** v1.3.0 (Next)
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

## Milestones

| Milestone | Phases | Status | Ship Date |
|-----------|--------|--------|-----------|
| M1 | 1-7 | ✅ Shipped | 2026-04-07 |
| v1.1.0 | 8-9 | ✅ Shipped | 2026-04-10 |
| v1.2.0 | 10-11 | ✅ Shipped | 2026-04-10 |
| v1.3.0 | TBD | 🔄 Planning | TBD |

## v1.3.0 — Real-time Convergence Monitoring

**Goal:** 仿真运行时实时追踪收敛曲线，Dashboard 可视化

**Target features:**
- **RC-01**: 仿真进程残差数据 WebSocket 推送（日志解析）
- **RC-02**: Dashboard 实时残差曲线（Plotly，随迭代更新）
- **RC-03**: Job detail 页面收敛监控面板
- **RC-04**: 收敛完成后结果摘要展示

**Key context:**
- 基于现有 Phase 10 WebSocket + Phase 11 Dashboard
- OpenFOAM solver 日志解析获取残差
- Plotly.js 前端实时图表
- Phase 12+ 再做 3D 场可视化（ParaView Web）

## Evolution

This document evolves at phase transitions and milestone boundaries.

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
