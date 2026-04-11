# Research Summary -- v1.5.0 Advanced Visualization

**Project:** AI-CFD Knowledge Harness
**Milestone:** v1.5.0 Advanced Visualization (Volume Rendering, Advanced Filters, Screenshot Export)
**Synthesized:** 2026-04-11
**Confidence:** HIGH (verified against ParaView 5.10.0 source, existing codebase patterns, Docker image)

---

## Executive Summary

v1.5.0 adds three capability clusters -- Volume Rendering, Advanced Filters (Clip/Contour/StreamTracer), and Screenshot Export -- to the existing ParaView Web viewer. The research confirms **zero new Docker images, npm packages, or Python packages are required**. All infrastructure already exists in `openfoam/openfoam10-paraview510` (ParaView 5.10.1). Implementation is entirely custom wslink protocol handler classes (Python, ~150 LOC) registered at container startup, plus TypeScript protocol message builders (~80 LOC) in the frontend.

The highest-risk aspect is not feature complexity but **container integration timing**: the custom Python protocol file must be imported and registered with wslink before the first WebSocket connection is accepted. If the import happens too late, all new RPC methods silently return "method not found." The second risk is GPU memory exhaustion on large CFD datasets (>2M cells) when volume rendering is enabled without pre-check. The third risk is Apple Silicon software fallback (Mesa/llvmpipe) when using `--platform linux/amd64`, which silently degrades performance to unusable levels without throwing errors.

Architecture flows from existing patterns: `ParaViewWebProtocol` subclass with `@exportRpc` decorators on server, raw JSON-RPC message builders on frontend, frame-push rendering (unchanged), and proxy ID state tracking for filter lifecycle management.

---

## Key Findings

### From STACK.md

- **Zero new dependencies.** `openfoam/openfoam10-paraview510` already ships `vtkGPUVolumeRayCastMapper`, built-in filters (`Clip`, `Contour`, `StreamTracer`), and `viewport.image.render` RPC.
- **Server-side:** Single new file `api_server/services/paraview_adv_protocols.py` (~150 lines) with two protocol classes: `ParaViewWebVolumeRendering` (4 RPCs) and `ParaViewWebAdvancedFilters` (9 RPCs).
- **Frontend:** Add ~14 message builder functions to `paraviewProtocol.ts` (~80 lines), plus `downloadScreenshot()` utility.
- **Container integration is the main complexity.** Custom protocols must be mounted at `/tmp/adv_protocols.py` and imported via a custom entrypoint wrapper script before `launcher.py` starts the wslink server. Mounting the file alone is insufficient -- the import must happen programmatically in the container entrypoint.
- **Docker image:** No change. Existing `openfoam/openfoam10-paraview510` is the correct target.
- **Anti-patterns explicitly rejected:** `trame` (deferred to v1.6.0), `@kitware/vtk.js` (client-side VTK not needed), new Docker image (not needed), `pv.proxy.manager.create` (too low-level), screenshot via container file path + HTTP (use base64 over WS instead).

### From FEATURES.md

- **Table stakes (P1):** Volume Rendering toggle, Clip Filter (create/delete), Contour Filter (create/delete), Streamlines (create/delete), Screenshot PNG export.
- **MVP scope:** Volume toggle only (no opacity editor), static-plane clip only (no interactive widget), masking-region streamlines only (no seed type selection), isovalue list input (no range slider).
- **Differentiators (P2):** Opacity transfer function editor, live clip/contour parameter updates, multi-filter composition, JSON state export.
- **Anti-features explicitly deferred:** Real-time volume during solver run, multi-field volume rendering, interactive plane widget (drag), animated streamlines, 3D PDF/WebGL export, movie export.
- **Feature dependencies:** All filters require existing `sourceProxyId` (from v1.4.0 OpenFOAM Reader). StreamTracer additionally requires vector field `U` (velocity). Volume Rendering additionally requires scalar field selection (v1.4.0 PV-03). Screenshot is orthogonal to all filters.
- **Apple Silicon note:** `--platform linux/amd64` means GPU is unavailable; volume rendering falls back to Mesa software rasterization silently.

### From ARCHITECTURE.md

- **New components:** `paraview_adv_protocols.py` (server), `AdvancedFilterPanel.tsx` (new file), additions to `paraviewProtocol.ts` and `ParaViewViewer.tsx`.
- **Modified components:** `paraview_web_launcher.py` (_build_launcher_config + _start_container to mount and import the protocol file), `ParaViewViewer.tsx` (new state + new UI sections), `ParaViewViewer.css`.
- **Phase build order:** Server protocols (Phase 1) before frontend message builders (Phase 2) before UI controls (Phase 3) before integration (Phase 4). Phase 2 and Phase 3 can run in parallel on different files.
- **State tracking:** Each filter (clip, contour, streamlines) stores its `proxyId` in React state for update/delete. Proxy IDs are session-bound -- invalid after container restart.
- **Render flow unchanged:** All server-side state changes call `simple.Render()` + `InvokeEvent("UpdateEvent")` which triggers `viewport.image.push` (existing subscription).
- **Scaling:** v1.5.0 scoped to single-user sessions (1:1 container:user, same as v1.4.0).
- **Open questions confirmed:** Container startup import timing (must test), large mesh fallback (suggest `Smart Volume Mapper` for >2M cells), source proxy ID discovery (confirmed from `OpenFOAMReader.GetPropertyList`).

### From PITFALLS.md

**Critical pitfalls (4):**

1. **GPU memory exhaustion on large datasets** -- `vtkGPUVolumeRayCastMapper` silently falls back to software rendering on OOM, freezing the UI. Prevention: pre-check cell count, set container memory limits (`--memory 4g --memory-reservation 2g`), offer surface fallback.

2. **Protocol file not registered before first WebSocket connection** -- Silent "method not found" errors. Prevention: custom entrypoint wrapper script that imports `paraview_adv_protocols.py` before launcher.py starts. Not just a volume mount -- must be programmatic import in entrypoint.

3. **Apple Silicon software fallback** -- `--platform linux/amd64` + Docker virtiofs cannot access Apple GPU; volume rendering silently uses Mesa/llvmpipe at 1-5 FPS. Prevention: detect EGL vendor (`eglinfo | grep "EGL vendor"`) at startup; show explicit user warning; disable volume rendering gracefully.

4. **Screenshot blocks WebSocket event loop** -- Synchronous `viewport.image.render` freezes UI for 10-30s on large datasets. Prevention: async UX (disable button + spinner), debounce rapid clicks, consider background thread rendering.

**Moderate pitfalls (5):**

5. Filter proxy IDs invalid after session restart (session-bound; must track `sessionId` alongside `proxyId`).
6. Opacity transfer function expects flat `[x1,y1,x2,y2,...]` array; nested arrays silently fail (server-side validation required).
7. StreamTracer seed type mismatch with irregular blockMesh geometry (bounds validation needed).
8. Memory grows unboundedly with filter create/delete cycles (`simple.Delete()` without `simple.Render()` + periodic `gc.collect()`).
9. Screenshot resolution rounds down to current viewport size (programmatic resize before capture).

**Minor pitfalls (2):**

10. Opacity settings lost when switching scalar fields (persist per-field in React state).
11. Color LUT reset wipes custom volume opacity (save/restore opacity state on field switch).

---

## Implications for Roadmap

### Recommended Phase Structure (4 phases)

**Phase 1: Container Integration + Protocol Foundation**
- Register custom protocol Python file at container startup (custom entrypoint wrapper)
- Verify `paraview_adv_protocols.py` import before wslink server starts
- Mount file as volume with read-only flag
- **Delivers:** Protocol registration timing solved for all subsequent phases
- **Pitfalls to avoid:** Pitfall 2 (protocol registration timing), integration with `paraview_web_launcher.py` changes
- **Research flags:** Test import sequence in actual container; confirm `launcher.py` accepts custom entrypoint approach

**Phase 2: Volume Rendering + GPU Safety**
- Implement `ParaViewWebVolumeRendering` class
- Frontend: volume toggle (Surface/Volume) + opacity message builders
- Add GPU detection: check EGL vendor at container startup (NVIDIA = real GPU; Mesa = software)
- Add cell count check before enabling volume; container memory limits
- Show user-facing warning when software fallback detected
- **Delivers:** Volume rendering toggle with graceful degradation on Apple Silicon
- **Pitfalls to avoid:** Pitfall 1 (GPU memory), Pitfall 3 (Apple Silicon fallback), Pitfall 6 (opacity format)
- **Research flags:** GPU detection in Docker container environment; EGL vendor string verification

**Phase 3: Screenshot Export**
- `viewport.image.render` base64 decode + browser download
- Frontend: screenshot button, loading state, debounce
- Optional: programmatic resize for requested resolution
- **Delivers:** One-click PNG export
- **Pitfalls to avoid:** Pitfall 4 (WS loop blocking), Pitfall 9 (resolution mismatch)

**Phase 4: Advanced Filters (Clip + Contour + StreamTracer)**
- Implement `ParaViewWebAdvancedFilters` class
- Frontend: `AdvancedFilterPanel.tsx` (clip/contour/streamlines sections)
- Proxy ID state management with session binding
- Bounds validation for streamtracer seeds
- Memory management: render after delete + periodic gc
- **Delivers:** Full filter pipeline (create/update/delete for all three filter types)
- **Pitfalls to avoid:** Pitfall 5 (proxy ID reset), Pitfall 7 (seed mismatch), Pitfall 8 (memory growth)
- **Research flags:** blockMesh geometry seed validation; filter cycle memory behavior

**Phase 5 (v1.5.x): Opacity Editor + Live Filter Updates**
- Opacity transfer function control point editor
- Live clip origin sliders (no recreate)
- Live contour isovalue adjustment
- JSON state export via `pv.data.save` + REST proxy
- **Delivers:** Professional-grade control over advanced features
- **Research flags:** Control point UI design; REST endpoint security

### Research Flags

| Phase | Needs Research | Standard Patterns |
|-------|----------------|-------------------|
| Phase 1 | Custom entrypoint with `launcher.py` compatibility | Protocol subclass pattern (already established) |
| Phase 2 | EGL vendor detection in Docker; GPU memory thresholds for CFD data | Volume rendering via `rep.Representation = "Volume"` (confirmed) |
| Phase 3 | Async screenshot rendering feasibility | `viewport.image.render` base64 (confirmed built-in) |
| Phase 4 | blockMesh irregular geometry bounds; filter memory behavior at scale | Clip/Contour/StreamTracer `simple.XXX()` API (confirmed) |

### Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All tech verified against ParaView 5.10.0 source and existing Docker image. Zero new dependencies confirmed. |
| Features | HIGH | MVP scope clear; P1 priorities are all low-cost/low-risk. Anti-features explicitly deferred. |
| Architecture | HIGH | Existing codebase patterns fully confirmed. Build order validated. Open questions are minor (container timing, mesh thresholds). |
| Pitfalls | MEDIUM-HIGH | 4 critical pitfalls identified with prevention strategies. Moderate pitfalls have workarounds. Apple Silicon fallback behavior needs field validation. |

### Gaps to Address

1. **Apple Silicon + amd64 + GPU detection:** Exact EGL vendor strings when running in Docker with `--platform linux/amd64` on Apple Silicon. Need to verify `eglinfo | grep "EGL vendor"` returns "Mesa Project" not "NVIDIA" in this configuration.
2. **GPU memory thresholds for CFD volume rendering:** Literature confirms `vtkGPUVolumeRayCastMapper` works well up to ~2M cells. Beyond 5M cells, behavior is unknown -- need empirical testing with real CFD datasets.
3. **Custom entrypoint compatibility with `vtkmodules/web/launcher.py`:** The proposed approach (custom entrypoint that imports then execs `launcher.py`) needs verification against the actual container image.
4. **Opacity transfer function format:** ParaView docs are sparse. The flat `[x1,y1,x2,y2,...]` format is inferred from VTK conventions, not ParaView documentation -- needs unit test verification.
5. **Source proxy ID format:** Confirm `OpenFOAMReader.GetPropertyList` response includes integer proxy ID usable as `sourceProxyId` in filter create calls.

---

## Sources (Aggregated)

| Source | Confidence | Key Information |
|--------|------------|-----------------|
| ParaView 5.10.0 `protocols.py` (GitHub) | HIGH | Full `@exportRpc` method list; `mapIdToProxy()` pattern |
| ParaViewWeb API `api.md` (paraviewweb) | HIGH | Available protocol names |
| `openfoam/openfoam10-paraview510` (Docker Hub) | HIGH | ParaView 5.10.1 + VTK GPU volume rendering confirmed |
| Existing `paraviewProtocol.ts` | HIGH | Protocol message builder pattern |
| Existing `paraview_web_launcher.py` | HIGH | Container lifecycle; `_build_launcher_config()` structure |
| Existing `ParaViewViewer.tsx` | HIGH | WebSocket state machine; `sendProtocolMessage` pattern |
| Existing `visualization.py` router | HIGH | REST endpoint pattern; session model |
| VTK `vtkGPUVolumeRayCastMapper` docs | HIGH | Memory behavior; software fallback |
| ParaView `simple.py` API | MEDIUM | `Clip()`, `Contour()`, `StreamTracer()` parameters |
| Kitware Discussions (Apple Silicon) | MEDIUM | `--platform linux/amd64` GPU limitation |
