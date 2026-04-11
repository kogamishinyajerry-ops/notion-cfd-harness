# Project Research Summary

**Project:** AI-CFD Knowledge Harness v1.6.0 — ParaView Web to trame Migration
**Domain:** Server-side 3D CFD visualization web framework
**Researched:** 2026-04-11
**Confidence:** MEDIUM

---

## Executive Summary

This is a **full-stack rewrite** of the ParaView Web visualization layer, not a port. The entire server protocol stack (`wslink` + `vtkmodules.web`), Docker entrypoint pattern (`entrypoint_wrapper.sh` + JSON launcher config), and frontend viewer component (`ParaViewViewer.tsx` + custom WebSocket RPC) must be replaced. The target framework is trame 3.12.0 (Kitware's official ParaView Web successor), which runs ParaView in a single `pvpython` process with a Vue.js frontend served alongside the Python server. The most significant changes are: (1) `@exportRpc` decorators become `@state.change` reactive handlers, (2) the React WebSocket RPC layer becomes a Vue.js application served by trame, and (3) the Docker container launches a single Python file directly rather than a multi-process launcher with a bash wrapper.

The recommended approach is a phased migration: establish the trame backend skeleton and Docker integration first, then migrate RPC protocol handlers, then adapt the FastAPI session manager, then build the Vue frontend, then integrate and validate feature parity. The core ParaView operations (OpenFOAMReader, Clip, Contour, StreamTracer, Volume Rendering) are unchanged -- only the wiring layer changes. The primary risk is that no official ParaView Web-to-trame migration guide exists; the team has no prior trame experience, so phase 1 must include significant manual testing and verification before committing to the approach.

---

## Key Findings

### Recommended Stack

The migration installs three pip packages into the existing `openfoam/openfoam10-paraview510` image: `trame==3.12.0`, `trame-vtk==2.11.6`, and `trame-vuetify==3.2.1`. The meta-package `trame` transitively brings `wslink >= 2.3.3`, so `wslink` must NOT be installed separately. Python 3.9.18 (shipped with ParaView 5.10) satisfies all version requirements. The Dockerfile replaces the `entrypoint_wrapper.sh` + `launcher.py` pattern with `pvpython /trame_server.py --port N`. The frontend Vue.js application is served automatically by trame at the same URL as the server itself.

**Core technologies:**
- `trame 3.12.0`: Python web framework -- replaces `vtk.web.launcher`, `wslink.decorators`, and `ParaViewWebProtocol` base class entirely
- `trame-vtk 2.11.6`: `VtkRemoteView` / `VtkLocalView` widgets -- replaces custom WebSocket image streaming (`ParaViewWebViewPortImageDelivery`)
- `trame-vuetify 3.2.1`: Vue.js Vuetify component bindings -- replaces React custom UI controls; use this (Vuetify 2), NOT `trame-vuetify3` (Vuetify 3)
- `pvpython`: Runs trame server directly -- single process, no multi-process launcher, no JSON config
- `openfoam/openfoam10-paraview510`: Unchanged Docker base image; ParaView 5.10, Python 3.9.18

### Expected Features

**Must have (table stakes -- all ParaView Web features must be preserved):**
- OpenFOAM case loading (`simple.OpenDataFile`) -- same ParaView API, different invocation pattern
- Field selection, slice controls (X/Y/Z/Off), color presets (Viridis/BlueRed/Grayscale), scalar range auto/manual, scalar bar visibility
- Volume rendering toggle with GPU detection (eglinfo subprocess) -- same detection logic, result stored in `state` instead of RPC response
- Clip, Contour, StreamTracer filters (create/delete) -- same `simple.*` API, registry pattern preserved as Python dict
- Screenshot export (`html_view.screenshot()`) -- different method than `viewport.image.render` RPC
- Time step navigation -- same `animation_scene.TimeKeeper` API
- **Remove entirely**: manual heartbeat, reconnect backoff logic, `@exportRpc` decorator classes, React viewer state machine

**Should have (differentiators trame unlocks):**
- Native Vuetify UI (professional look, zero custom CSS) -- rewrite React viewer controls as Vuetify Python components
- Local rendering mode (`VtkLocalView`) -- WebGL in browser, no server GPU needed on Apple Silicon
- Hot reload during development -- trame watches Python files, no Docker rebuild needed
- Async time playback (`@asynchronous.task` decorator) -- animated stepping without blocking server
- Filter parameter live editing (in-place update of clip origin, isovalues) -- deferred from v1.5.0 anti-feature

**Defer (v2+):**
- State persistence / shareable links (serialize `server.state` to JSON)
- Multiple viewports for side-by-side case comparison
- Opacity transfer function editor

### Architecture Approach

The current system is a React dashboard (port 8080) that launches ParaView Web Docker sidecar containers (port 9000 per session) via FastAPI `ParaviewWebManager`. Each sidecar runs `entrypoint_wrapper.sh` importing `adv_protocols.py` to register `@exportRpc` handlers, then starts `launcher.py` with a JSON config. The React frontend communicates via raw WebSocket with a custom JSON-RPC router.

The target system replaces the Docker sidecar launch mechanism with a simpler `pvpython /trame_server.py` invocation and replaces the React WebSocket viewer with a Vue.js application served by trame. The React dashboard will embed the trame viewer as an iframe, communicating via `window.postMessage`. FastAPI session management remains but is simplified: no JSON config, no entrypoint wrapper, no port range restrictions beyond standard allocation. Session isolation stays at the container level (one container per session), matching current security posture.

**Major components:**
1. `trame_server.py` (NEW, replaces `adv_protocols.py` + `entrypoint_wrapper.sh`): Contains `get_server()`, `VtkRemoteView`, `@state.change` handlers for all ParaView operations, and a Vuetify UI layout
2. `TrameSessionManager` (NEW, replaces `ParaviewWebManager`): Docker container lifecycle -- `docker run ... pvpython /trame_server.py --port N` instead of JSON config + launcher; uses `docker kill` for shutdown
3. `CFDViewerBridge.ts` (NEW, replaces `ParaViewViewer.tsx` + `paraviewProtocol.ts`): React iframe bridge using `window.postMessage`; communicates with Vue frontend inside iframe
4. `Dockerfile` (MODIFY): Adds `pip install trame trame-vtk trame-vuetify`; removes `entrypoint_wrapper.sh` and launcher references

### Critical Pitfalls

1. **`@exportRpc` protocol classes have no direct trame equivalent** -- The mental model inverts: ParaView Web is RPC-centric (client calls named method), trame is state-centric (client mutates shared state, server reacts). Every `@exportRpc` handler must be rewritten as either a `@state.change` reactive handler or a `@controller.add` callback. No class-level filter registry exists in trame; use `state.filters` dict instead. All `self._app.SMApplication.InvokeEvent("UpdateEvent")` calls must be removed -- trame handles render push automatically on state mutation.

2. **Docker container architecture is replaced entirely** -- `ParaviewWebManager.launch_session()` with its JSON config launcher, port allocation (8081-8090), entrypoint wrapper, and idle monitor is replaced by a simple `docker run ... pvpython /trame_server.py --port N`. The container name changes from `pvweb-{session_id}` to `trame-{session_id}`. The `_verify_image()` method checking for `vtk.web.launcher` is replaced by `pip show trame`. No polling for "Starting factory" -- `server.start()` is blocking and port is immediately available.

3. **Filter IDs using `id(proxy)` are not stable across server restarts** -- `id()` returns memory addresses that change on restart. Client-side filter references break after server restart. Use a UUID or incremental counter stored in `state.filters` as stable string keys.

4. **Multi-client session isolation requires explicit design** -- ParaView Web's per-container process model provides hard isolation. trame's default mode shares the server process across all connected clients. One user's filter operations could leak into another user's viewport. Use client-ID-prefixed filter keys in `state.filters` and `ctrl.on_client_connected()` to initialize per-client state.

5. **GPU detection (`_detect_gpu`) using eglinfo subprocess is unnecessary for `VtkLocalView`** -- With local rendering, geometry serializes to the browser and renders via WebGL -- server has no GPU involvement. For `VtkRemoteView` (server-side rendering), use VTK API (`vtkGraphicsFactory.GetBackEnd()`) instead of shelling out to `eglinfo`. Volume rendering toggle will fail silently on Apple Silicon without proper view type selection.

---

## Implications for Roadmap

### Suggested Phase Structure

#### Phase 1: Trame Backend Skeleton + Docker Integration
**Rationale:** Must verify trame runs correctly inside the existing Docker image before committing to the full migration. This is the foundation all other phases depend on.
**Delivers:** `trame_server.py` with minimal server (`VtkRemoteView` rendering a cone), updated `Dockerfile`, manual browser verification of 3D rendering.
**Implements:** `get_server()`, basic layout, `pvpython /trame_server.py --port N` inside container.
**Avoids:** "Looks done but isn't" -- verify rendering before building features on top.
**Research flag:** MEDIUM -- no official migration guide; validate trame + ParaView 5.10 compatibility during this phase.

#### Phase 2: RPC Protocol Migration
**Rationale:** All `@exportRpc` handlers in `adv_protocols.py` must be converted to trame's `@state.change` / `@controller.add` pattern before the frontend can drive any ParaView operations.
**Delivers:** Full `trame_server.py` with all 13 RPC equivalents: volume rendering toggle/status, clip/contour/streamtracer create/delete, filter list, GPU detection.
**Implements:** All `@state.change` handlers, filter registry as `state.filters` dict with stable UUID keys, removal of all `InvokeEvent` calls.
**Avoids:** Pitfalls 1, 3, 5.

#### Phase 3: FastAPI Session Manager Adaptation
**Rationale:** `ParaviewWebManager` must be replaced with `TrameSessionManager` before the React frontend can launch trame sessions. This is the integration point between FastAPI and the Docker container.
**Delivers:** `trame_session_manager.py` with `start_session()`, `get_session()`, `shutdown_session()`, idle monitoring. Updated `paraview.ts` API client. Image verification replaced.
**Implements:** `docker run ... pvpython /trame_server.py --port N`, port allocation, container lifecycle.
**Avoids:** Pitfall 2 (container architecture replacement). Must verify `server.start()` is blocking with port immediately available vs. polling for "Starting factory".

#### Phase 4: Vue Frontend + React Iframe Bridge
**Rationale:** The React dashboard must embed the trame Vue application. This phase builds the replacement for `ParaViewViewer.tsx` and `paraviewProtocol.ts`.
**Delivers:** `CFDViewerBridge.ts` (postMessage bridge), iframe embedding of trame viewer URL, all React controls (field selector, slice, color, volume toggle, filter panel) wired to bridge.
**Avoids:** "Keep React + ParaView Web protocol layer" anti-pattern. The Vue frontend is the viewer -- React does not drive ParaView directly.
**Research flag:** MEDIUM -- `VtkLocalView` WebGL rendering on Apple Silicon Safari needs validation if local rendering mode is pursued.

#### Phase 5: Integration + Feature Parity Validation
**Rationale:** Must verify the full launch flow (API call -> container start -> Vue connects -> all RPCs work -> screenshot captures -> time steps navigate) before considering migration complete.
**Delivers:** End-to-end test of all P1 features from FEATURES.md. Multi-client isolation test (two browser tabs).
**Avoids:** Pitfalls 2 (session isolation), OpenFOAM path mounting, multi-client state leakage.

#### Phase 6: Cleanup + v1.7.0 Additions
**Rationale:** Delete all old ParaView Web files only after migration is verified. Add v1.7.0 differentiators.
**Delivers:** Deleted files: `adv_protocols.py`, `entrypoint_wrapper.sh`, `ParaViewViewer.tsx`, `paraviewProtocol.ts`, `paraview_web_launcher.py`. Added: filter parameter live editing, local rendering mode toggle, async time playback.
**Avoids:** "Partial migration" anti-pattern -- old files must be removed to prevent accidental use.

### Phase Ordering Rationale

- **Phase 1 before 2**: Cannot migrate RPCs without a running trame server to test against.
- **Phase 2 before 3**: Session manager must launch the correct trame command (not the old launcher); this requires knowing what the server entrypoint looks like.
- **Phase 3 before 4**: Frontend needs a session manager that can start/stop trame containers to test against.
- **Phase 4 before 5**: Integration testing requires the full stack.
- **Phase 5 before 6**: Old files deleted only after verified feature parity.

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 1 (Skeleton)**: No official ParaView Web-to-trame migration guide exists. Must validate `VtkRemoteView` vs `VtkLocalView` rendering behavior with actual OpenFOAM mesh inside the container. Also: confirm `server.start(port=0)` auto-allocation works inside Docker.
- **Phase 4 (Vue Frontend)**: `VtkLocalView` WebGL browser rendering on Apple Silicon needs testing -- Safari WebGL limitations are undocumented in trame. Also: `html_view.screenshot()` resolution behavior must be verified against actual viewport size.

**Phases with standard patterns (skip research-phase):**
- **Phase 2 (RPC Migration)**: Official Kitware examples (`trame/examples/07_paraview/`) provide verified patterns for all filter types. `@state.change` decorator behavior is documented.
- **Phase 3 (Session Manager)**: Docker container lifecycle is unchanged from current implementation; only the `docker run` command arguments change.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | PyPI release data verified; Kitware official docs and GitHub examples confirmed; Python 3.9 compatibility verified via paraview.web.venv docs; no known version conflicts |
| Features | MEDIUM-HIGH | Official Kitware trame/paraview examples verified; all ParaView `simple.*` API calls are unchanged; team has implemented all P1 features in current system |
| Architecture | MEDIUM-HIGH | Verified against trame source on GitHub (Kitware/trame, Kitware/trame-server); ParaView Web source patterns confirmed in existing codebase; no official migration guide (MEDIUM uncertainty) |
| Pitfalls | MEDIUM | No official migration guide from Kitware exists; team has no prior trame production experience; some trame APIs (`VtkLocalView` geometry export) incompletely documented |

**Overall confidence:** MEDIUM

### Gaps to Address

- **No official migration guide**: All recommendations are synthesized from trame source code, official docs, and wslink protocol docs. Phase 1 must include explicit verification that the approach works before proceeding to later phases.
- **`VtkLocalView` Apple Silicon WebGL**: Safari WebGL limitations for trame's local rendering mode are not documented. If local rendering is prioritized (P2 differentiator), Phase 1 must test this explicitly.
- **`html_view.screenshot()` resolution**: Needs verification against actual viewport DOM size. Research notes this is unclear in current docs.
- **OpenFOAM reader `Fields` property**: `paraview_adv_protocols.py` uses `props.Fields = fieldName` for the OpenFOAM reader. Must verify this works identically when called from trame state listener.
- **Dashboard auth integration**: React dashboard uses JWT for API auth. trame `--auth` flag compatibility with existing JWT flow (cookie vs header) needs verification in Phase 3/4.
- **Multi-session within one container**: Conflicting signals in research -- `get_server(name=session_id)` may be a singleton per name. If true, container-per-session is still correct. Must verify during Phase 3.

---

## Sources

### Primary (HIGH confidence)
- **Kitware/trame GitHub** (https://github.com/Kitware/trame) -- v3.12.0 confirmed; wslink as dependency confirmed; `@controller.add`, `@state.change` patterns verified
- **trame PyPI** (https://pypi.org/pypi/trame/3.12.0/json) -- package metadata, dependencies, trame-client version verified
- **trame-vtk PyPI** (https://pypi.org/pypi/trame-vtk/2.11.6/json) -- Python >= 3.9 requirement, trame-client version constraint confirmed
- **Kitware/trame examples** (`examples/07_paraview/`) -- official verified patterns for RemoteRendering, ContourGeometry, DynamicLocalRemoteRendering, TimeAnimation, StateViewer
- **trame.readthedocs.io** -- `get_server()`, `server.start()`, `VtkRemoteView`, `VtkLocalView`, lifecycle callbacks
- **ParaViewWeb GitHub README** -- maintenance mode status confirmed; trame as official successor confirmed
- **openfoam/openfoam10-paraview510 Docker image** -- image name, ParaView 5.10, Python 3.9 confirmed

### Secondary (MEDIUM confidence)
- **trame GitHub discussions** (https://github.com/Kitware/trame/discussions/840) -- ParaView 6.1+ bundle "hoped for" but not confirmed; ParaView version compatibility gap noted
- **Architecture source code analysis** -- `get_server()` singleton behavior, `AVAILABLE_SERVERS` dict, `Server.start()` blocking behavior inferred from source; needs runtime verification
- **Integration gotchas** -- compiled from documented trame behavior, ParaView Web source, and cross-source synthesis; no single authoritative source

### Tertiary (LOW confidence)
- **Session isolation in multi-user scenario** -- `get_server(name=session_id)` singleton claim is inferred from source; may need explicit runtime test
- **`html_view.screenshot()` resolution behavior** -- not documented in current sources; needs practical verification
- **Apple Silicon Safari WebGL compatibility for `VtkLocalView`** -- not documented; requires hardware testing

---

*Research completed: 2026-04-11*
*Ready for roadmap: yes -- with MEDIUM overall confidence and explicit research flags for Phases 1 and 4*
