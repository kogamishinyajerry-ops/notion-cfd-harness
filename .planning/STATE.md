---
gsd_state_version: 1.0
milestone: v1.6.0
milestone_name: ParaView Web → Trame Migration
status: roadmap_created
last_updated: "2026-04-11T23:45:00.000Z"
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# State

## Project

- **Name**: AI-CFD Knowledge Harness
- **Root**: /Users/Zhuanz/Desktop/notion-cfd-harness
- **Version**: v1.6.0
- **Milestone**: v1.6.0 — ParaView Web to Trame Migration

## Current Position

**Active milestone:** v1.6.0 ParaView Web to Trame Migration
**Active phase:** Phase 23 (Trame Backend Skeleton)
**Status:** Roadmap created — awaiting user approval to begin planning
**Next:** `/gsd-plan-phase 23`

## Phase Structure

| Phase | Goal | Requirements |
|-------|------|--------------|
| 23 - Trame Backend Skeleton | Trame + Docker integration, minimal sphere rendering | TRAME-01.1–01.4 |
| 24 - RPC Protocol Migration | 13 @exportRpc → @ctrl.add/@state.change, UUID registry | TRAME-02.1–02.6 |
| 25 - Session Manager Adaptation | TrameSessionManager, Docker lifecycle, idle timeout | TRAME-03.1–03.4 |
| 26 - Vue Frontend + Iframe Bridge | Vue.js viewer, CFDViewerBridge.ts, postMessage wiring | TRAME-04.1–04.6 |
| 27 - Integration + Feature Parity | End-to-end validation, all v1.4.0/v1.5.0 features | TRAME-05.1–05.6 |
| 28 - Cleanup + Old File Removal | Delete ParaView Web artifacts, no broken imports | TRAME-06.1–06.5 |

## Coverage

- **31/31** requirements mapped across 6 phases
- **0** orphaned requirements
- **0** duplicate mappings

## Key Architecture Decisions

- `@exportRpc` → `@ctrl.add`/`@state.change` (trame reactive pattern)
- React dashboard embeds trame Vue.js viewer as iframe
- `CFDViewerBridge.ts` uses `window.postMessage` for React-Vue communication
- Filter registry uses UUID keys (not Python `id()`) for restart stability
- `InvokeEvent` calls removed entirely (trame auto-pushes on state mutation)
- Single `pvpython /trame_server.py --port N` replaces `entrypoint_wrapper.sh` + launcher

## Research Notes (commit `291cccc`)

- MEDIUM confidence — no official migration guide exists
- Phase 1 must validate trame + ParaView 5.10 compatibility explicitly
- Phase 4 must validate `VtkLocalView` Apple Silicon Safari WebGL behavior
- `html_view.screenshot()` resolution behavior needs practical verification
- Multi-session isolation via `get_server(name=session_id)` needs runtime test

## Blockers

None — roadmap ready for planning

## Session Continuity

After approval: run `/gsd-plan-phase 23` to begin Phase 23 planning
