---
gsd_state_version: 1.0
milestone: v1.6.0
milestone_name: — ParaView Web → Trame Migration
status: defining_requirements
last_updated: "2026-04-11T23:30:00.000Z"
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
- **Milestone**: v1.6.0 — ParaView Web → Trame Migration

## Current Position

**Active milestone:** v1.6.0 ParaView Web → Trame Migration
**Active phase:** Not started (defining requirements)
**Status:** Research complete — 4/4 agents + synthesizer done
**Next:** Requirements → Roadmap

## Research Summary

Research completed (4 agents + synthesizer, commit `291cccc`):
- **Stack:** trame 3.12.0 + trame-vtk 2.11.6 + trame-vuetify 3.2.1, Python 3.9 compatible
- **Key change:** @exportRpc → @ctrl.add/@state.change, React → Vue.js iframe, entrypoint_wrapper.sh → pvpython app.py
- **Risk:** No official migration guide exists; full rewrite not port
- **Open questions:** VtkLocalView Apple Silicon WebGL, html_view.screenshot resolution, multi-session isolation

## v1.6.0 Goals

- **TRAME-01**: Trame backend skeleton in Docker
- **TRAME-02**: RPC protocol migration (all 13 RPCs)
- **TRAME-03**: FastAPI Session Manager adaptation
- **TRAME-04**: Vue.js frontend + React iframe bridge
- **TRAME-05**: Integration + feature parity
- **TRAME-06**: Cleanup + old file removal

## Blockers

None — research complete, awaiting user confirmation to proceed
