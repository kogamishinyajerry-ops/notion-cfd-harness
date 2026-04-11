# AI-CFD Knowledge Harness — Roadmap

## Milestones

- [x] **M1** — Well-Harness AI-CFD OS (Phases 1-7, shipped 2026-04-07)
- [x] **v1.1.0** — Report Automation & CaseGenerator v2 (Phases 8-9, shipped 2026-04-10)
- [x] **v1.2.0** — API & Web Interface (Phases 10-11, shipped 2026-04-10)
- [x] **v1.3.0** — Real-time Convergence Monitoring (shipped 2026-04-11)
- [x] **v1.4.0** — ParaView Web 3D Visualization (shipped 2026-04-11)
- [x] **v1.5.0** — Advanced Visualization (Phases 19-22, shipped 2026-04-11)
- [ ] **v1.6.0** — ParaView Web to Trame Migration (Phases 23-28)

## v1.6.0 — ParaView Web to Trame Migration

<details>
<summary>Phase checklist</summary>

- [x] **Phase 23: Trame Backend Skeleton** — Trame + trame-vtk + trame-vuetify in Docker, minimal sphere rendering
- [x] **Phase 24: RPC Protocol Migration** — All 7 @exportRpc converted to @ctrl.add/@state.change, UUID filter registry
- [ ] **Phase 25: Session Manager Adaptation** — TrameSessionManager replacing ParaViewWebManager, Docker lifecycle
- [ ] **Phase 26: Vue Frontend + Iframe Bridge** — Vue.js viewer, CFDViewerBridge.ts, postMessage wiring
- [ ] **Phase 27: Integration + Feature Parity** — End-to-end validation of all v1.4.0/v1.5.0 features
- [ ] **Phase 28: Cleanup + Old File Removal** — Delete all ParaView Web artifacts

</details>

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1 | M1 | - | Complete | 2026-04-07 |
| 2a-c | M1 | - | Complete | 2026-04-07 |
| 3 | M1 | - | Complete | 2026-04-07 |
| 4 | M1 | - | Complete | 2026-04-07 |
| 5 | M1 | - | Complete | 2026-04-07 |
| 6 | M1 | - | Complete | 2026-04-07 |
| 7 | M1 | - | Complete | 2026-04-07 |
| 8 | v1.1.0 | 4/4 | Complete | 2026-04-10 |
| 9 | v1.1.0 | 3/3 | Complete | 2026-04-10 |
| 10 | v1.2.0 | 3/3 | Complete | 2026-04-10 |
| 11 | v1.2.0 | 3/3 | Complete | 2026-04-10 |
| 12 | v1.3.0 | 3/3 | Complete | 2026-04-11 |
| 13 | v1.3.0 | 2/2 | Complete | 2026-04-11 |
| 14 | v1.3.0 | 2/2 | Complete | 2026-04-11 |
| 15 | v1.4.0 | 2/2 | Complete | 2026-04-11 |
| 16 | v1.4.0 | 2/2 | Complete | 2026-04-11 |
| 17 | v1.4.0 | 2/2 | Complete | 2026-04-11 |
| 18 | v1.4.0 | 1/1 | Complete | 2026-04-11 |
| 19 | v1.5.0 | 1/1 | Complete | 2026-04-11 |
| 20 | v1.5.0 | 1/1 | Complete | 2026-04-11 |
| 21 | v1.5.0 | 1/1 | Complete | 2026-04-11 |
| 22 | v1.5.0 | 1/1 | Complete | 2026-04-11 |
| 23 | v1.6.0 | 1/1 | Complete    | 2026-04-11 |
| 24 | v1.6.0 | 1/1 | Complete    | 2026-04-12 |
| 25 | v1.6.0 | 1/1 | Complete   | 2026-04-11 |
| 26 | v1.6.0 | 2/2 | Complete    | 2026-04-11 |
| 27 | v1.6.0 | 0/1 | Not started | - |
| 28 | v1.6.0 | 0/1 | Not started | - |

---

## Phase Details

### Phase 23: Trame Backend Skeleton

**Goal:** Trame serves a minimal ParaView geometry (sphere) inside the Docker container via `pvpython /trame_server.py --port N`, with no dependency on the old entrypoint wrapper.

**Depends on:** None (first phase of v1.6.0)

**Requirements:** TRAME-01.1, TRAME-01.2, TRAME-01.3, TRAME-01.4

**Success Criteria** (what must be TRUE):
1. `pip install trame==3.12.0 trame-vtk==2.11.6 trame-vuetify==3.2.1` succeeds inside `openfoam/openfoam10-paraview510` Docker image
2. `pvpython /trame_server.py --port N` serves a 3D sphere (or cone) viewable in a browser at the allocated port
3. Docker container starts without `entrypoint_wrapper.sh` (single `pvpython` command replaces the wrapper)
4. `import trame; import trame_vtk; import trame_vuetify` succeeds inside the container with no conflicts against ParaView 5.10 Python environment

**Plans:**
1/1 plans complete

### Phase 24: RPC Protocol Migration

**Goal:** All 13 ParaView Web RPC handlers (`@exportRpc`) are rewritten as trame reactive methods (`@ctrl.add`/`@state.change`), with UUID-based filter registry and no `InvokeEvent` calls.

**Depends on:** Phase 23

**Requirements:** TRAME-02.1, TRAME-02.2, TRAME-02.3, TRAME-02.4, TRAME-02.5, TRAME-02.6

**Success Criteria** (what must be TRUE):
1. All RPC method names that existed in `paraview_adv_protocols.py` respond correctly to client calls through trame's state system
2. GPU detection (eglinfo subprocess) returns the same vendor/memory strings as v1.5.0
3. Cell count check returns a warning for datasets exceeding 2,000,000 cells
4. Filter operations (Clip threshold, Contour isovalues, StreamTracer direction/maxSteps) produce visually identical ParaView output compared to v1.5.0 (manual side-by-side comparison)
5. No `InvokeEvent` calls remain in the codebase — trame automatically pushes renders on state mutation
6. Filter registry survives server restart without stale ID errors (UUID keys persist across restart)

**Plans:**
- [x] 24-01-PLAN.md — Migrate all 7 @exportRpc handlers to @ctrl.add/@state.change with UUID registry

### Phase 25: Session Manager Adaptation

**Goal:** FastAPI can launch, route to, and shut down trame Docker containers via `TrameSessionManager`, with idle timeout and job completion auto-launch preserved from v1.5.0.

**Depends on:** Phase 23

**Requirements:** TRAME-03.1, TRAME-03.2, TRAME-03.3, TRAME-03.4

**Success Criteria** (what must be TRUE):
1. `POST /visualization/sessions` launches a Docker container running `pvpython /trame_server.py --port N` with an allocated port returned in the response
2. Session container is gracefully stopped after 30 minutes of inactivity (idle timeout)
3. Job completion handler triggers trame session launch for the completed job, making the viewer available in the dashboard without manual intervention
4. Multiple concurrent sessions are isolated — dashboard connects to the correct trame instance via auth key routing

**Plans:**
1/1 plans complete

### Phase 26: Vue Frontend + Iframe Bridge

**Goal:** React dashboard embeds the trame Vue.js viewer as an iframe, with bidirectional communication via `CFDViewerBridge.ts` postMessage, and all viewer controls (field, slice, color, volume, filters) wired through the bridge.

**Depends on:** Phase 25

**Requirements:** TRAME-04.1, TRAME-04.2, TRAME-04.3, TRAME-04.4, TRAME-04.5, TRAME-04.6

**Success Criteria** (what must be TRUE):
1. Vue.js viewer renders inside trame's Vuetify layout at the viewer sub-URL (separate from the React dashboard)
2. `CFDViewerBridge.ts` successfully sends field selection, slice, and color map changes from React to Vue, updating the 3D view
3. Camera state (rotation, zoom, pan) in Vue propagates back to React state via postMessage, reflecting accurately in the dashboard
4. All filter panel controls (Clip threshold, Contour isovalues, StreamTracer direction/maxSteps) update trame viewer state through the bridge
5. Volume rendering toggle, slice slider, and color map controls all function identically to v1.5.0 through the bridge
6. `ParaViewViewer.tsx` is replaced by an iframe embedding the trame viewer URL — no direct ParaView Web protocol calls remain in React

**Plans:**
2/2 plans complete
- [x] 26-02-PLAN.md — trame_server.py postMessage listener, camera polling, and state handlers

**UI hint:** yes

### Phase 27: Integration + Feature Parity

**Goal:** End-to-end validation confirms all v1.4.0 and v1.5.0 viewer features work correctly through the trame stack, with no regressions.

**Depends on:** Phase 26

**Requirements:** TRAME-05.1, TRAME-05.2, TRAME-05.3, TRAME-05.4, TRAME-05.5, TRAME-05.6

**Success Criteria** (what must be TRUE):
1. Manual test checklist for all v1.4.0 features (rotation, zoom, slicing, color mapping) passes without deviation from expected behavior
2. Volume rendering toggle shows the same GPU detection, Apple Silicon Mesa warning, and 2M cell OOM guard as v1.5.0
3. Clip, Contour, and StreamTracer filters render simultaneously with correct parameter updates through the bridge
4. Screenshot export downloads a PNG at the correct viewport resolution with the same 500ms debounce UX as v1.5.0
5. Time step navigation (prev/next/play) correctly updates the trame animation state and the 3D view
6. Two concurrent browser tabs connected to different sessions see isolated state (no cross-contamination of filter or camera state)

**Plans:**
- [x] 26-01-PLAN.md — CFDViewerBridge.ts postMessage layer + TrameViewer.tsx iframe component + JobDetailPage wiring
- [x] 26-02-PLAN.md — trame_server.py postMessage listener, camera polling, and state handlers

### Phase 28: Cleanup + Old File Removal

**Goal:** All ParaView Web artifacts are removed from the project, with no broken imports or stale references remaining.

**Depends on:** Phase 27

**Requirements:** TRAME-06.1, TRAME-06.2, TRAME-06.3, TRAME-06.4, TRAME-06.5

**Success Criteria** (what must be TRUE):
1. `entrypoint_wrapper.sh` does not exist in the repository and is not referenced in any Docker build step
2. `api_server/services/paraview_adv_protocols.py` does not exist and no Python file imports it
3. Docker `docker run` commands for trame sessions contain no `:ro` volume mount for `adv_protocols`
4. `ParaViewViewer.tsx`, `ParaViewViewer.css`, and `AdvancedFilterPanel.tsx` are deleted or archived — the React viewer directory has no broken component imports
5. All call sites in `paraviewProtocol.ts` and other API client files are updated — no `import { ... } from './paraviewProtocol'` references that would cause build failures

**Plans:**
- [x] 26-01-PLAN.md — CFDViewerBridge.ts postMessage layer + TrameViewer.tsx iframe component + JobDetailPage wiring
- [x] 26-02-PLAN.md — trame_server.py postMessage listener, camera polling, and state handlers

---

## Coverage

| Requirement | Phase |
|-------------|-------|
| TRAME-01.1 | 23 |
| TRAME-01.2 | 23 |
| TRAME-01.3 | 23 |
| TRAME-01.4 | 23 |
| TRAME-02.1 | 24 |
| TRAME-02.2 | 24 |
| TRAME-02.3 | 24 |
| TRAME-02.4 | 24 |
| TRAME-02.5 | 24 |
| TRAME-02.6 | 24 |
| TRAME-03.1 | 25 |
| TRAME-03.2 | 25 |
| TRAME-03.3 | 25 |
| TRAME-03.4 | 25 |
| TRAME-04.1 | 26 |
| TRAME-04.2 | 26 |
| TRAME-04.3 | 26 |
| TRAME-04.4 | 26 |
| TRAME-04.5 | 26 |
| TRAME-04.6 | 26 |
| TRAME-05.1 | 27 |
| TRAME-05.2 | 27 |
| TRAME-05.3 | 27 |
| TRAME-05.4 | 27 |
| TRAME-05.5 | 27 |
| TRAME-05.6 | 27 |
| TRAME-06.1 | 28 |
| TRAME-06.2 | 28 |
| TRAME-06.3 | 28 |
| TRAME-06.4 | 28 |
| TRAME-06.5 | 28 |

**Mapped:** 31/31 requirements across 6 phases

---

*Full milestone history: `.planning/MILESTONES.md`*
