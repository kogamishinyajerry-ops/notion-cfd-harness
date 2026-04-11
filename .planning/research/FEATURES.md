# Feature Research: ParaView Web to trame Migration

**Domain:** Scientific visualization — CFD field visualization via ParaView
**Project:** AI-CFD Knowledge Harness v1.6.0
**Researched:** 2026-04-11
**Confidence:** MEDIUM-HIGH (official Kitware/trame GitHub examples verified; documented patterns from `examples/07_paraview/`)

---

## 1. Feature Landscape

### Table Stakes (Existing ParaView Web Features — Must Preserve)

These are the features from v1.4.0/v1.5.0 that must have trame equivalents. Every row maps a specific `@exportRpc` method or WebSocket message pattern to its trame state-driven replacement.

| Feature | ParaView Web RPC / Message | trame Equivalent | Migration Complexity |
|---------|---------------------------|------------------|---------------------|
| OpenFOAM case loading | Manual WS message to `file.server.reader.openfoam` | `simple.OpenDataFile(caseDir)` / `simple.OpenFOAMReader()` | LOW — same ParaView API |
| Field selection (scalar) | `file.server.reader.properties` + `visualization.representation.colorby` | `simple.ColorBy(rep, array)` triggered by `state.change("field")` | LOW — same ParaView API |
| Slice controls (X/Y/Z/Off) | `visualization.slice.*` (manual WS message handler) | `simple.Slice(Input=source)` + `state.change("slice_axis")` / `state.change("slice_origin")` | MEDIUM — state listener replaces WS message dispatch |
| Color preset (Viridis/BlueRed/Grayscale) | `visualization.colors.preset` | `simple.GetColorTransferFunction()` with preset lookup | LOW — same ParaView API |
| Scalar range (auto/manual) | `visualization.scalar.range` | `representation.RescaleTransferFunctionToDataRange()` / `lut.RescaleTransferFunction(min, max)` | LOW — same ParaView API |
| Scalar bar visibility | `visualization.scalar.bar` toggle | State variable `show_scalar_bar` → `ScalarBarWidget` visibility property | LOW |
| Time step navigation | `visualization.time.step` | `animation_scene.TimeKeeper` API with `state.change("time_index")` | LOW — same ParaView API |
| Volume rendering toggle | `visualization.volume.rendering.toggle` | `representation.Representation = "Volume"` driven by `state.change("volume_enabled")` | MEDIUM — ParaView API identical; pattern is state-driven |
| Volume rendering status (GPU detection) | `visualization.volume.rendering.status` | In-process `subprocess.run(["eglinfo"])` + state initialization on `on_server_ready` | LOW — `eglinfo` subprocess unchanged, result stored in `state` |
| Clip filter create | `visualization.filters.clip.create` | `simple.Clip(Input=source)` + Python dict registry + `state.change("clip_*")` | MEDIUM — same `simple.Clip()` API; `@state.change` replaces `@exportRpc` |
| Clip filter delete | `visualization.filters.delete` | `simple.Delete(proxy)` from registry | LOW |
| Contour filter create | `visualization.filters.contour.create` | `simple.Contour(Input=source)` + registry | MEDIUM — same pattern as Clip |
| Contour filter delete | `visualization.filters.delete` | `simple.Delete(proxy)` from registry | LOW |
| StreamTracer filter create | `visualization.filters.streamtracer.create` | `simple.StreamTracer(Input=source)` + registry | MEDIUM — same pattern |
| StreamTracer filter delete | `visualization.filters.delete` | `simple.Delete(proxy)` from registry | LOW |
| Filter list view | `visualization.filters.list` | Python dict → push to `state.active_filters` on change | LOW |
| Viewport render (push to client) | `viewport.image.render` RPC | Automatic on state change via `VtkRemoteView`; explicit: `html_view.update_image()` | LOW — automatic push; no manual trigger needed |
| Screenshot export | `viewport.image.render` (same RPC, but triggered manually) | `html_view.screenshot()` → base64 PNG → download | MEDIUM — method differs: `html_view.screenshot()` vs RPC call |
| Heartbeat | Manual `wslink.protocol.register_method("heartbeat")` + 60s interval in React | NOT NEEDED — `TRAME_WS_HEART_BEAT` env var (default 30s) handles keepalive internally | N/A — remove entirely |
| Reconnect logic | Manual 5-attempt backoff (`RECONNECT_DELAYS`) in React `ws.onclose` | Built-in — trame manages WebSocket lifecycle | N/A — remove entirely |

### Differentiators (New Capabilities trame Unlocks)

Features not currently implemented but enabled by the migration.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Native Vuetify UI | Full Vuetify component library (VSlider, VSwitch, VBtn, VContainer) instead of custom HTML/CSS controls + React state machine. Professional look with zero additional styling. | MEDIUM | Rewrite `ParaViewViewer.tsx` React component as Vuetify layout in Python |
| Local rendering mode (`VtkLocalView`) | WebGL rendering in browser without server round-trips. Camera rotation/zoom is local. ParaView geometry is sent once; interaction is local. | MEDIUM-HIGH | `DynamicLocalRemoteRendering.py` example shows auto/local/remote toggle |
| Dashboard integration | React dashboard can serve trame via `server.start()` on a sub-route (`/viewer/$jobId`). JWT auth can be passed via cookie or header. | MEDIUM | Requires verifying `--auth` flag compatibility with existing JWT flow |
| Async time playback | `@asynchronous.task` decorator for animated time stepping without blocking the server. Background `while state.play` loop in `TimeAnimation` example. | LOW | Already demonstrated in official trame examples |
| State persistence / shareable links | `server.state` is serializable. Visualization state (camera, filters, colors) can be saved as JSON and restored. Enables "share this view" feature. | MEDIUM | `ctrl.on_server_ready` loads state; state is URL-serializable |
| Hot reload (dev) | Trame watches Python files; server reloads on save. No Docker rebuild during development. Dev loop is `save file → browser auto-updates. | LOW | Significant developer experience improvement |
| Multiple viewports | Single server can manage multiple `paraview.VtkRemoteView()` instances for side-by-side case comparison. | MEDIUM | Each view is a separate region in the Vuetify layout |
| Accelerated filters | `simple.LoadDistributedPlugin("AcceleratedAlgorithms")` enables `FlyingEdges3D` and other fast contour algorithms (shown in `ContourGeometry` example). | LOW | One-line addition to pipeline setup |

### Anti-Features (Don't Migrate As-Is)

Features from the existing implementation that should NOT be carried over to trame in their current form.

| Anti-Pattern | Why Problematic | Alternative |
|-------------|----------------|-------------|
| Keep React + ParaView Web protocol layer | Doubles the communication stack (React WS client → ParaView Web RPC → ParaView). trame removes this — Python UI binds directly to state. | Replace `ParaViewViewer.tsx` React component with trame Python UI; Dashboard serves trame app |
| Keep Docker sidecar (`ParaViewWebManager`) | ParaView Web requires a separate container with special entrypoint wrapper + `adv_protocols.py` import ordering. trame runs ParaView in the same Python process via `pvpython app.py`. | Single-process: `trame.server.start()` with ParaView initialized inside |
| Keep manual heartbeat | Added complexity in React (`sendHeartbeat()` every 60s); wslink heartbeat is a workaround for connection drops. trame handles this via `TRAME_WS_HEART_BEAT` (default 30s). | Remove `sendHeartbeat()` entirely |
| Keep reconnect backoff logic | ParaView Web's 5-attempt exponential backoff is required because the WS protocol is stateless. trame manages WebSocket lifecycle internally. | Remove `RECONNECT_DELAYS`, `MAX_RECONNECT_ATTEMPTS`, and all reconnect state |
| Keep `viewport.image.render` as render loop | ParaView Web sends images only on explicit RPC call. trame automatically pushes updates on any state change via `VtkRemoteView`. | Remove manual render triggering; rely on automatic state → render push |
| Keep `@exportRpc` decorator classes | wslink RPC decorators don't exist in trame. State-driven callbacks (`@state.change`) replace request-response RPC. | Convert protocol classes to `@state.change` handlers |
| Keep React `ViewerState` machine | The `idle/launching/connecting/connected/disconnected/reconnect-exhausted/error` state machine is necessitated by ParaView Web's session launch pattern. trame connects immediately on `server.start()`. | Simplified: `loading` (initializing) + `ready` (rendering) |

---

## 2. Feature Dependencies

```
OpenFOAM Reader (simple.OpenDataFile / simple.OpenFOAMReader)
    │
    ├──► Field Selection ──requires──► ColorBy(rep, array) on active reader
    │                              └──enhances──► Scalar Range (auto-computes from field data)
    │
    ├──► Slice Controls ──requires──► Active Source
    │                        └──conflicts──► Volume Rendering (mutually exclusive representations)
    │
    ├──► Volume Rendering ──requires──► Active Source + Field Selection
    │                           └──requires──► GPU detection (eglinfo) → state.gpu_available
    │                           └──conflicts──► Slice (can't slice a volume representation)
    │
    ├──► Advanced Filters (Clip/Contour/StreamTracer)
    │    ├──requires──► Active Source
    │    ├──requires──► Filter Registry (Python dict keyed by `id(proxy)`)
    │    └──enhances──► Filter List UI (registry → state.active_filters)
    │
    ├──► Screenshot ──requires──► VtkRemoteView (must have rendered frame)
    │                     └──enhances──► Any state change (volume/slice/filters affect what is captured)
    │
    └──► Time Step Navigation ──requires──► OpenFOAM Reader with time steps
         └──enhances──► Async Playback (@asynchronous.task decorator)

GPU Detection ──enhances──► Volume Rendering Toggle (disables if Mesa detected)
```

---

## 3. MVP Definition

### Launch With (trame migration — v1.6.0)

Core: full parity with existing ParaView Web functionality, via trame patterns.

- [ ] **OpenFOAM reader** — `simple.OpenDataFile(caseDir)` on `on_server_ready`
- [ ] **Field selection** — `simple.ColorBy()` + Vuetify `VSelect` bound to `state.field`
- [ ] **Slice controls** — Vuetify `VBtnToggle` (X/Y/Z/Off) + `VSlider` origin → `simple.Slice()` via `state.change("slice_axis")`
- [ ] **Color presets** — Viridis / BlueRed / Grayscale via `simple.GetColorTransferFunction()` with preset map
- [ ] **Scalar range** — auto (`RescaleTransferFunctionToDataRange()`) / manual (`lut.RescaleTransferFunction(min, max)`) with Vuetify `VSlider`
- [ ] **Scalar bar** — `show_scalar_bar` state → `ScalarBarWidget` visibility
- [ ] **Time step navigation** — Previous/Next `VBtn` → `animation_scene.TimeKeeper` via `state.change("time_index")`
- [ ] **Volume rendering toggle** — Vuetify `VSwitch` → `representation.Representation = "Volume"` via `state.change("volume_enabled")`
- [ ] **GPU detection + warning** — `subprocess.run(["eglinfo"])` in-process → `state.gpu_vendor` + `state.gpu_available`; warning banner via `vuetify.VAlert`
- [ ] **Screenshots** — `html_view.screenshot()` → base64 → Vuetify file download; debounced `500ms`
- [ ] **Filter registry** — Python `dict` keyed by `id(proxy)` (identical to current `ParaViewWebAdvancedFilters._filters`)
- [ ] **Clip filter** — create/delete with Vuetify `VChip` delete buttons; state-bound parameters
- [ ] **Contour filter** — create/delete with isovalues `VTextField`; up to 20 values
- [ ] **StreamTracer filter** — create/delete with integration direction `VBtnToggle` (FORWARD/BACKWARD)
- [ ] **Filter list panel** — `AdvancedFilterPanel` rewritten as Vuetify `VList` with delete actions

### Add After Validation (v1.7.0)

- [ ] **Filter parameter update** — live edit of clip origin, contour isovalues, streamtracer max steps (currently only create/delete; in-place update not in v1.5.0)
- [ ] **Local rendering mode** — `VtkLocalView` with auto/local/remote toggle (see `DynamicLocalRemoteRendering.py`)
- [ ] **Time playback** — `@asynchronous.task` for animated stepping (`while state.play:` loop)
- [ ] **Scalar bar position** — configurable scalar bar placement via `state.scalar_bar_position`

### Future Consideration (v2.0)

- [ ] **State persistence** — serialize `server.state` to JSON; restore on load for shareable links
- [ ] **Multiple viewports** — `paraview.VtkRemoteView()` x2 for side-by-side case comparison
- [ ] **Opacity transfer function editor** — `vuetify.VSlider` control points → `volumeProperty.GetGrayTransferFunction()` (deferred from v1.5.0 anti-feature)
- [ ] **JSON state export** — `pv.data.save` + REST endpoint for reproducible visualization state

---

## 4. Feature Prioritization Matrix

| Feature | User Value | Migration Cost | Priority |
|---------|------------|----------------|----------|
| OpenFOAM reader | HIGH | LOW | P1 |
| Field selection | HIGH | LOW | P1 |
| Slice controls | HIGH | MEDIUM | P1 |
| Color presets | MEDIUM | LOW | P1 |
| Volume rendering toggle | HIGH | MEDIUM | P1 |
| Advanced filters (Clip/Contour/StreamTracer) | MEDIUM | MEDIUM | P1 |
| Screenshot export | MEDIUM | MEDIUM | P1 |
| Time step navigation | MEDIUM | LOW | P1 |
| GPU detection + warning banner | MEDIUM | LOW | P1 |
| Scalar bar visibility | LOW | LOW | P2 |
| Filter parameter update (live edit) | MEDIUM | HIGH | P2 |
| Local rendering mode | MEDIUM | MEDIUM-HIGH | P2 |
| Async time playback | LOW | LOW | P2 |
| State persistence / shareable links | LOW | MEDIUM | P3 |
| Multiple viewports | LOW | MEDIUM | P3 |
| Opacity transfer function editor | HIGH | MEDIUM | P3 (was P2 in v1.5.0 anti-feature) |

**Priority rationale:**
- **P1 = must have for launch.** All ParaView Web features must be preserved. The `simple.*` ParaView API is unchanged — the migration cost is in the state-binding pattern, not the ParaView logic itself.
- **P2 = should add if time permits.** Filter parameter update and local rendering are high-value additions that follow naturally from the state-driven architecture.
- **P3 = defer to v2.** These require more design work or significant new UI surface area.

---

## 5. Architecture Comparison: ParaView Web vs trame

| Concern | ParaView Web (current) | trame (target) |
|---------|----------------------|----------------|
| RPC mechanism | `@exportRpc("method.name")` decorator → WebSocket JSON-RPC | `@state.change("var_name")` decorator → shared state → automatic render push |
| Base class | `ParaViewWebProtocol` | `trame.app.get_server()` |
| Server instantiation | `launcher.py` + separate Docker container | `get_server(client_type="vue2")` + same process |
| Render push | `viewport.image.render` RPC (on-demand) | `VtkRemoteView` automatically pushes on any state change |
| UI framework | Custom HTML/CSS + React state machine | Vuetify (Vue.js) components bound to state |
| Protocol registration | `entrypoint_wrapper.sh` imports `adv_protocols.py` → `@exportRpc` classes register | `server.state.change("x")` decorators register handlers |
| Connection management | Manual heartbeat, reconnect backoff | `TRAME_WS_HEART_BEAT` (default 30s), built-in |
| Multi-session | `ParaViewWebManager` Docker sidecar with lifecycle | Each `get_server()` call is its own session |
| File loading | WS message → `simple.OpenDataFile()` | Direct `simple.OpenDataFile()` in `on_server_ready` |
| Filter pipeline | Python dict registry + `@exportRpc` methods | Same Python dict registry + `@state.change` handlers |

### Key Migration Pattern: `@exportRpc` -> `@state.change`

**ParaView Web (current) — `paraview_adv_protocols.py`:**
```python
@exportRpc("visualization.volume.rendering.toggle")
def volumeRenderingToggle(self, fieldName: str, enabled: bool):
    display.SetRepresentationToVolume() if enabled else display.SetRepresentationToSurface()
    simple.Render()
    self._app.SMApplication.InvokeEvent("UpdateEvent", ())
    return {"success": True}
```

**trame equivalent:**
```python
@state.change("volume_enabled", "field_name")
def update_volume_rendering(volume_enabled, field_name, **kwargs):
    if volume_enabled:
        rep.Representation = "Volume"
    else:
        rep.Representation = "Surface"
    ctrl.view_update()   # triggers render push to client
```

The Vue.js UI binding:
```python
vuetify.VSwitch(
    v_model=("volume_enabled", False),
    label="Volume Rendering",
)
```

---

## 6. Research Gaps / Phase-Specific Investigation Flags

| Gap | Why It Matters | Action |
|-----|----------------|--------|
| **ParaView version compatibility** | trame v2 requires ParaView 5.11+. The existing Docker image uses ParaView 5.10.1 (from `openfoam/openfoam10-paraview510`). | Verify ParaView version in `openfoam/openfoam10-paraview510`; may need image upgrade |
| **Filter parameter update (live edit)** | Currently only create/delete exist. The existing `ParaViewWebAdvancedFilters` has no update method. In-place editing requires adding `state.change("clip_origin")` listeners. | Investigate during FILT implementation phase |
| **Dashboard auth integration** | React dashboard uses JWT for API auth. trame `--auth` flag needs verification with existing JWT flow (cookie vs header). | Investigate during dashboard integration phase |
| **`html_view.screenshot()` resolution behavior** | Needs verification: does it respect actual viewport DOM size or require explicit resolution parameter? | Test during SHOT phase |
| **OpenFOAM reader `Fields` property** | `paraview_adv_protocols.py` uses `if hasattr(props, "Fields"): props.Fields = fieldName`. Verify this works identically when called from trame state listener. | Test with actual OpenFOAM case during READER phase |
| **`VtkLocalView` browser requirements** | WebGL rendering in browser needs hardware GPU access. Apple Silicon Safari may have limitations. Fallback to `VtkRemoteView` (server-side rendering). | Investigate if local rendering mode is prioritized |
| **Multi-session / job isolation** | Current architecture: each job = separate ParaView Web Docker container (session). trame server starts per-job. How does the dashboard route to the correct trame instance? | Investigate during architecture phase |

---

## Sources

- [Kitware/trame GitHub](https://github.com/Kitware/trame) — official repository, verified source
  - `examples/07_paraview/Wavelet/app.py` — filter pipeline with `@state.change` listeners, async rendering
  - `examples/07_paraview/ContourGeometry/RemoteRendering.py` — contour rendering with `VtkRemoteView`, `ctrl.view_update`
  - `examples/07_paraview/ContourGeometry/DynamicLocalRemoteRendering.py` — auto/local/remote rendering toggle
  - `examples/07_paraview/TimeAnimation/app.py` — `animation_scene.TimeKeeper` + `@asynchronous.task` for playback
  - `examples/07_paraview/StateViewer/app.py` — `VtkRemoteView` + CLI state file loading
- [trame official docs](https://kitware.github.io/trame/) — framework overview, reserved state entries (`trame__*`)
- [trame API reference](https://trame.readthedocs.io/en/latest/) — `trame.app.core`, `trame.app.asynchronous`, `trame.widgets`
- [trame tutorial](https://kitware.github.io/trame/guide/tutorial/) — VTK + ParaView integration path

---

*Feature research for: ParaView Web to trame migration (AI-CFD Knowledge Harness v1.6.0)*
*Researched: 2026-04-11*
