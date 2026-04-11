# Requirements — v1.6.0 ParaView Web → Trame Migration

**Milestone:** v1.6.0
**Status:** Active
**Created:** 2026-04-11
**Research:** `.planning/research/SUMMARY.md` (commit `291cccc`)

---

## TRAME-01: Trame Backend Skeleton

**Type:** Backend / Infrastructure
**Priority:** MUST

### Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| TRAME-01.1 | Trame packages (trame 3.12.0, trame-vtk 2.11.6, trame-vuetify 3.2.1) install successfully in cfd-workbench:openfoam-v10 Docker image | `docker run` with pip install succeeds |
| TRAME-01.2 | Minimal trame app.py renders ParaView geometry (sphere) and serves at allocated port | Viewer loads in browser at sub-URL |
| TRAME-01.3 | Container startup does NOT use entrypoint_wrapper.sh | Single `pvpython /trame_server.py --port N` replaces wrapper |
| TRAME-01.4 | Docker image build installs trame packages without conflicting with ParaView 5.10 Python environment | Import check passes inside container |

---

## TRAME-02: RPC Protocol Migration

**Type:** Backend
**Priority:** MUST

### Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| TRAME-02.1 | All 13 existing @exportRpc handlers rewritten as @ctrl.add or @state.change methods in trame server | All RPC method names respond to client calls |
| TRAME-02.2 | GPU detection (eglinfo subprocess) copied verbatim to trame server — behavior unchanged | GPU/Mesa vendor string returned in status |
| TRAME-02.3 | Cell count check (>2M threshold) preserved in trame server | Warning returned for datasets >2M cells |
| TRAME-02.4 | Filter registry uses UUID keys instead of Python `id()` for stability across server restarts | Filter survives server restart without stale ID errors |
| TRAME-02.5 | All `self._app.SMApplication.InvokeEvent()` calls removed (no trame equivalent) | No AttributeError on any filter operation |
| TRAME-02.6 | Filter operations (Clip threshold, Contour isovalues, StreamTracer direction/maxSteps) produce identical ParaView output | Visual comparison matches v1.5.0 output |

---

## TRAME-03: FastAPI Session Manager Adaptation

**Type:** Backend / Infrastructure
**Priority:** MUST

### Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| TRAME-03.1 | TrameSessionManager launches Docker container with `pvpython /trame_server.py --port N` as CMD | Container starts, port allocated, trame serves |
| TRAME-03.2 | Idle timeout (30 min) gracefully stops trame server | Container exits after idle period |
| TRAME-03.3 | Job completion auto-launch launches trame for completed job | Viewer available in dashboard for completed job |
| TRAME-03.4 | AuthKey routing to correct trame instance still functions | Dashboard connects to correct session |

---

## TRAME-04: Vue.js Frontend + React Iframe Bridge

**Type:** Frontend
**Priority:** MUST

### Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| TRAME-04.1 | Vue.js viewer component serves inside trame app (trame-vuetify layout) | Vue viewer renders at viewer sub-URL |
| TRAME-04.2 | CFDViewerBridge.ts handles postMessage between React dashboard and Vue viewer | Bidirectional communication verified |
| TRAME-04.3 | React dashboard loads trame viewer as embedded iframe at viewer sub-route | ParaViewViewer.tsx replaced by iframe |
| TRAME-04.4 | Field selector (U, p, etc.) controls trame viewer state via postMessage | Field change updates 3D view |
| TRAME-04.5 | Camera controls (rotate, zoom, pan) propagate from Vue viewer to React state | React dashboard reflects current camera state |
| TRAME-04.6 | Slice slider, color map controls, volume toggle, and filter panel all work through bridge | All v1.4.0/v1.5.0 controls functional |

---

## TRAME-05: Integration + Feature Parity

**Type:** Integration
**Priority:** MUST

### Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| TRAME-05.1 | All v1.4.0 viewer features (rotation, zoom, slicing, color mapping) work identically through trame | Manual test checklist passes |
| TRAME-05.2 | Volume rendering toggle matches v1.5.0 behavior (GPU detection, Apple Silicon warning, 2M cell OOM guard) | Same warning banners appear |
| TRAME-05.3 | Clip, Contour, StreamTracer filters visible and update parameters through bridge | Filter re-renders on parameter change |
| TRAME-05.4 | Screenshot export captures at viewport resolution with debounce (same UX as v1.5.0) | PNG downloads with correct dimensions |
| TRAME-05.5 | Multiple filters (Clip + Contour + StreamTracer) visible simultaneously | All active filters render together |
| TRAME-05.6 | Time step navigation works with trame animation state | Prev/Next/Play controls update view |

---

## TRAME-06: Cleanup + Old File Removal

**Type:** Maintenance
**Priority:** MUST

### Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| TRAME-06.1 | entrypoint_wrapper.sh removed from project and Docker build | File deleted, container starts without it |
| TRAME-06.2 | paraview_adv_protocols.py removed from api_server/services/ | File deleted, no import references remain |
| TRAME-06.3 | AdvProtocols volume mount removed from paraview_web_launcher.py | Docker run command has no :ro mount for adv_protocols |
| TRAME-06.4 | ParaViewViewer.tsx, ParaViewViewer.css, AdvancedFilterPanel.tsx removed or replaced | Old viewer files archived or deleted |
| TRAME-06.5 | All call sites updated (paraviewProtocol.ts export functions adjusted) | No broken imports or missing references |

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| VtkLocalView (WebGL direct, no server round-trips) | Complex, untested on Apple Silicon; deferred to v1.7.0 |
| Hot reload (no Docker rebuild during development) | Developer convenience only; not user-facing |
| Animated streamlines | Needs animation player; deferred |
| Real-time volume during solver run | Significant complexity; deferred |
| Multi-field volume rendering | Complex UX; deferred |

---

## Traceability

| Phase | Requirements | Status |
|-------|-------------|--------|
| 23 | TRAME-01.1–01.4 | Not started |
| 24 | TRAME-02.1–02.6 | Not started |
| 25 | TRAME-03.1–03.4 | Not started |
| 26 | TRAME-04.1–04.6 | Not started |
| 27 | TRAME-05.1–05.6 | Not started |
| 28 | TRAME-06.1–06.5 | Not started |
