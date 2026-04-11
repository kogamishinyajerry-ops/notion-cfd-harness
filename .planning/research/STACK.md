# Technology Stack: ParaView Web to trame Migration

**Project:** AI-CFD Knowledge Harness
**Domain:** Server-side 3D ParaView visualization web framework
**Researched:** 2026-04-11
**Confidence:** MEDIUM-HIGH (PyPI release data verified; integration patterns from official Kitware docs; openfoam/paraview510 Python 3.9 compatibility confirmed via paraview.web.venv docs)

---

## Executive Summary

Migrating from ParaView Web (`wslink` + `vtkmodules.web`) to trame replaces the entire server protocol layer and frontend viewer component. The migration is **not additive** — it is a full replacement of the ParaView Web stack. The Python server changes from a multi-process launcher (JSON config + `vtk.web.launcher`) to a single `pvpython script.py` running trame. The frontend changes from a custom React WebSocket RPC layer to trame's served Vue.js application (Option A: iframe embedding recommended). The Docker sidecar pattern is retained, but the entrypoint changes from wrapper script + launcher to direct `pvpython trame_server.py`.

---

## Migration Overview

**What is trame?**

Trame (Kitware, [GitHub](https://github.com/Kitware/trame)) is the successor to ParaView Web. It is a Python web framework that weaves open-source components into interactive web applications written entirely in Python. Trame builds on wslink (which it ships as a dependency), VTK, and ParaView. It replaces `vtk.web.protocol`, `vtk.web.launcher`, and `wslink.decorators` with a unified `get_server()` + reactive state architecture.

**Relationship to ParaView Web / wslink:**
- `trame` meta-package depends on `wslink >= 2.3.3` — wslink is not abandoned; it is absorbed as a trame dependency.
- `trame` replaces `vtk.web.protocol`, `vtk.web.launcher`, and `wslink.decorators` entirely.
- `trame` serves its own Vue.js frontend (trame-client bundles Vue 2.7 or 3.5 depending on configuration).
- Source: [PyPI trame 3.12.0 dependencies](https://pypi.org/pypi/trame/3.12.0/json), [trame README](https://github.com/Kitware/trame)

---

## Package Compatibility with openfoam/openfoam10-paraview510

**Base image:** `openfoam/openfoam10-paraview510`
- **ParaView version:** 5.10
- **Python version:** 3.9.18 (from `paraview.web.venv` docs — ParaView 5.10/5.11 use Python 3.9)
- **Included VTK:** VTK from ParaView 5.10 distribution

**Python compatibility:**
- trame requires Python >= 3.9. `openfoam10-paraview510` ships Python 3.9.18. **COMPATIBLE.**
- `trame-vtk` 2.11.6 requires Python >= 3.9. **COMPATIBLE.**

### Package Ecosystem (all mutually compatible)

| Package | Version | Role | Key Dependencies |
|---------|---------|------|----------------|
| `trame` | 3.12.0 | Core meta-package; replaces `vtk.web.launcher` + `wslink` | `trame-server >= 3.4`, `trame-client >= 3.10.1`, `trame-common >= 1`, `wslink >= 2.3.3`, `pyyaml` |
| `trame-vtk` | 2.11.6 | `VtkRemoteView` / `VtkLocalView` widgets for ParaView 3D rendering | `trame-client >= 3.4, < 4` |
| `trame-vuetify` | 3.2.1 | Vue.js UI component library (buttons, sliders, containers) | `trame-client >= 3.7, < 4` |

**Compatibility chain:**
- `trame` 3.12.0 brings `trame-client >= 3.10.1` — satisfies both `trame-vtk` (>= 3.4) and `trame-vuetify` (>= 3.7). All three are fully compatible.
- `trame-vuetify` 3.x = Vuetify 2 widget bindings. Do NOT use `trame-vuetify3` (Vuetify 3) — that package uses a different trame-client version range and may not be compatible with `trame-vtk` 2.x.

### What NOT to Add

| Anti-pattern | Why Avoid | Correct Approach |
|-------------|-----------|-----------------|
| `wslink` as separate package | Already installed transitively by `trame` | Do not install separately |
| `vtkmodules.web` | Replaced by trame's server architecture | Not needed |
| `paraview.web.venv` | Only needed when using system Python with ParaView; container uses `pvpython` directly | Not needed for pvpython execution |
| `trame-vuetify3` | Different trame-client version range than `trame-vtk` | Use `trame-vuetify` (Vuetify 2) |
| `@kitware/vtk.js` npm | Not needed — trame serves its own Vue.js frontend for 3D | Not needed |
| Any WebSocket npm package | Custom WS RPC layer is replaced by trame's state sync | Not needed |

---

## Docker Image Changes

### Dockerfile Modifications

**Current (`openfoam/openfoam10-paraview510`-based):**
```dockerfile
FROM openfoam/openfoam10-paraview510
COPY entrypoint_wrapper.sh /entrypoint_wrapper.sh
RUN chmod +x /entrypoint_wrapper.sh
ENTRYPOINT ["/entrypoint_wrapper.sh"]
# CMD passed at runtime: pvpython lib/site-packages/vtkmodules/web/launcher.py /tmp/launcher_config.json
```

**Migrated:**
```dockerfile
FROM openfoam/openfoam10-paraview510

# Install trame stack — replaces vtk.web.launcher + wslink server stack
RUN pip install --no-cache-dir \
    trame==3.12.0 \
    trame-vtk==2.11.6 \
    trame-vuetify==3.2.1

# Copy trame server entrypoint script (replaces entrypoint_wrapper.sh + launcher.py + adv_protocols.py)
COPY trame_server.py /trame_server.py

# Direct start — no entrypoint wrapper needed
# Protocol imports are handled inline in trame_server.py
CMD ["pvpython", "/trame_server.py"]
```

### Entrypoint / Container Launch Changes

**Current (`paraview_web_launcher.py` — `ParaviewWebManager._start_container`):**
```python
# JSON launcher config → vtk.web.launcher multi-process
"cmd": [
    "pvpython", "-dr",
    "lib/site-packages/vtkmodules/web/launcher.py",
    "--port", "${port}",
    "--data", "/data",
    "--authKey", "${secret}",
    "-f",
],
```

**Migrated (Docker container start):**
```python
# Single pvpython process — no launcher config needed
# trame_server.py handles case loading, view setup, and trame server start
# All protocol handlers are imported directly in trame_server.py

docker run -d \
    --platform linux/amd64 \
    --name pvweb-{session_id} \
    -v {case_path}:/data:ro \
    -p {host_port}:9000 \
    cfd-workbench:openfoam-v10 \
    pvpython /trame_server.py --port 9000 --data /data --session-id {session_id}
```

**Key differences:**
- The entire `vtk.web.launcher` multi-process session manager (JSON config, process spawner) is eliminated.
- One `pvpython` process = one trame server = one case viewer.
- Session isolation remains at the container level (one container per session, same as current).
- Port inside container maps to same host port via `-p {host_port}:9000` — same port number, now serving HTTP+WebSocket instead of pure WebSocket.
- `sessionURL` changes from `ws://host:port/ws` to `http://host:port` (trame handles WebSocket upgrade transparently).

### Image Verification Change

**Current (`paraview_web_launcher.py` — `verify_paraview_web_image`):**
```python
# OLD — checks for vtk.web.launcher
"pvpython -c \"import vtk.web.launcher; print(os.path.dirname(vtk.web.launcher.__file__))\""
```

**Migrated:**
```python
# NEW — checks for trame
"pvpython -c \"import trame; print(trame.__file__)\""
```

---

## Server-Side Changes

### Protocol / RPC Pattern — BREAKING CHANGE

This is the most significant code change. The entire `ParaViewWebProtocol` + `@exportRpc` pattern is replaced.

**Current (`paraview_adv_protocols.py`):**
```python
from paraview import simple
from vtk.web.protocol import ParaViewWebProtocol
from wslink.decorators import exportRpc

class ParaViewWebVolumeRendering(ParaViewWebProtocol):
    @exportRpc("visualization.volume.rendering.toggle")
    def volumeRenderingToggle(self, fieldName: str, enabled: bool):
        display.SetRepresentationToVolume()
        simple.Render()
        self._app.SMApplication.InvokeEvent("UpdateEvent", ())
        return {"success": True}
```

**Migrated (`trame_server.py`):**
```python
from paraview import simple
from trame.app import get_server
from trame.ui.vuetify import SinglePageLayout
from trame.html import paraview
from trame.widgets import vuetify

server = get_server()
state, ctrl = server.state, server.controller

# -----------------------------------------------------------
# Volume rendering toggle — replaces @exportRpc handler
# -----------------------------------------------------------
def _volume_rendering_toggle(field_name: str, enabled: bool):
    """Server-side ParaView operation. Called by client via ctrl method."""
    source = simple.GetActiveSource()
    if source is None:
        return
    display = simple.GetDisplayProperties(source=source)
    if enabled:
        display.SetRepresentationToVolume()
    else:
        display.SetRepresentationToSurface()
    simple.Render()

@ctrl.add
def on_volume_rendering_toggle(field_name: str, enabled: bool):
    """Exposed to client as a callable method via trame's controller system."""
    _volume_rendering_toggle(field_name, enabled)
    ctrl.view_update()

# -----------------------------------------------------------
# Volume rendering status — replaces @exportRpc status handler
# -----------------------------------------------------------
@state.change("volume_rendering_status_request")
def on_volume_rendering_status_request(volume_rendering_status_request, **kwargs):
    """Reactive state handler — called when client sets this state variable."""
    gpu_available, gpu_vendor = _detect_gpu()
    # ... same GPU detection logic as current _detect_gpu()
    state.volume_rendering_status = {
        "enabled": volume_enabled,
        "field_name": field_name,
        "gpu_available": gpu_available,
        "gpu_vendor": gpu_vendor,
        "cell_count": cell_count,
    }

# -----------------------------------------------------------
# Clip filter — replaces ParaViewWebAdvancedFilters.clipFilterCreate
# -----------------------------------------------------------
_filter_registry = {}  # Replaces class-level _filters dict

@ctrl.add
def on_filter_clip_create(inside_out: bool, scalar_value: float):
    source = simple.GetActiveSource()
    clip = simple.Clip(Input=source)
    clip.ClipType = "Scalar"
    clip.Scalar = scalar_value
    clip.InsideOut = inside_out
    filter_id = id(clip)
    _filter_registry[filter_id] = {"type": "clip", "proxy": clip}
    simple.Render()
    ctrl.view_update()
    state.filter_list = _get_filter_list()

# -----------------------------------------------------------
# Server startup — replaces vtk.web.launcher
# -----------------------------------------------------------
def _build_view():
    """Set up ParaView scene from /data case directory."""
    # ... load case, get active source, configure view ...
    view = simple.GetActiveView()
    return view

view = _build_view()
html_view = paraview.VtkRemoteView(view)  # server renders, streams images

layout = SinglePageLayout(server)
layout.title.set("CFD Viewer")
with layout.content:
    vuetify.VContainer(fluid=True, children=[html_view])

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--data", default="/data")
    parser.add_argument("--session-id", default="default")
    args = parser.parse_args()

    server.start(
        port=args.port,
        host="0.0.0.0",
        open_browser=False,
        show_connection_info=False,
    )
```

**Key differences:**
- No `@exportRpc` decorator. Server methods are exposed via `ctrl.add` decorator.
- No `ParaViewWebProtocol` base class. Plain Python functions + `get_server()`.
- `self._app.SMApplication.InvokeEvent("UpdateEvent", ())` (wslink push) replaced by `ctrl.view_update()`.
- `@state.change("varname")` decorator provides reactive binding (client sets `state.varname` → server handler fires).
- `state.filter_list = ...` — assigning to `state` variables syncs them to the client automatically.
- Filter registry persists as a module-level dict (same as current class-level dict).

### port and Host Configuration

**Current (`paraview_web_launcher.py` — `_build_launcher_config`):**
```python
config = {
    "host": "0.0.0.0",
    "port": 9000,           # inside container
    "sessionURL": f"ws://${{host}}:{port}/ws",
    "timeout": 10,
    "fields": ["sessionURL", "secret", "id"],
    "apps": { ... }
}
```

**Migrated (`trame_server.py`):**
```python
server.start(
    port=9000,              # inside container (same port)
    host="0.0.0.0",
    open_browser=False,
)
# sessionURL is now simply http://host:port (WS upgrade automatic)
```

### Argument Parsing

The current launcher uses JSON config files mounted into the container. Trame uses direct `argparse`:
```python
# Current: config JSON → launcher.py parses it
# Migrated:
parser.add_argument("--port", type=int, default=9000)
parser.add_argument("--data", default="/data")
parser.add_argument("--session-id", default="default")
```

The `paraview_web_launcher.py` needs to pass these args to the container instead of writing a JSON config file:
```python
# Instead of mounting /tmp/launcher_config.json
# Just pass args to pvpython:
f"pvpython /trame_server.py --port {allocated_port} --data /data --session-id {session_id}"
```

---

## Client-Side Changes

### Package Changes (dashboard/package.json)

**Remove:**
- No npm packages need to be removed — the current dashboard has no direct dependency on `wslink` (it uses raw WebSocket). The custom WebSocket communication code will be replaced or isolated.

**Add:**
- No additional npm packages needed. Trame serves its own Vue.js frontend automatically at the viewer URL.
- If using `window.postMessage` bridge between React and trame iframe: no new npm packages needed.

### Frontend 3D Viewer Integration Options

The React `ParaViewViewer.tsx` cannot be directly migrated to use trame's Vue.js widgets. Two options:

**Option A — Iframe embedding (RECOMMENDED):**
The React dashboard loads the trame viewer as an isolated Vue.js application in an `<iframe>`. The dashboard and viewer communicate via `window.postMessage`.

```tsx
// ParaViewViewer.tsx — migrated approach
function ParaViewViewer({ sessionUrl, caseDir }: Props) {
  const viewerUrl = `${sessionUrl}/viewer?case=${encodeURIComponent(caseDir)}`;

  return (
    <iframe
      src={viewerUrl}
      style={{ width: "100%", height: "100%", border: "none" }}
      title="CFD Viewer"
      allow="fullscreen"
    />
  );
}
```

**Option B — Hybrid React + trame-client:**
The React app imports `trame-client` and uses its state API directly, making the React app a consumer of the trame state layer. This is architecturally complex and not recommended for v1.6.0.

**Recommendation: Option A** — cleanest separation, least rewriting, preserves the existing React dashboard architecture. The iframe URL can include the case directory as a query parameter, which the trame server reads at startup to load the correct case.

### WebSocket Communication Layer

**Current (custom React WebSocket):**
```typescript
// Custom protocol message builders + ws.onmessage routing
ws.current.send(JSON.stringify({
  id: "toggleVolumeRendering",
  data: { fieldName, enabled }
}));

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id === "toggleVolumeRendering") { ... }
  if (msg.method === "viewport.image.render") { ... }
};
```

**Migrated (iframe postMessage bridge — Option A):**
```typescript
// dashboard/src/components/CFDViewerBridge.ts
// Bridges React UI controls → trame iframe

function sendToViewer(action: string, payload: unknown) {
  const iframe = document.getElementById("cfd-viewer") as HTMLIFrameElement;
  iframe?.contentWindow?.postMessage({ action, payload }, "*");
}

// Example: toggle volume rendering from React UI
function onVolumeToggle(fieldName: string, enabled: boolean) {
  sendToViewer("volume_rendering_toggle", { field_name: fieldName, enabled: enabled });
}
```

```javascript
// Inside trame iframe (trame_server.py served Vue app)
// listens for postMessage from parent React app:
window.addEventListener("message", (event) => {
  const { action, payload } = event.data;
  if (action === "volume_rendering_toggle") {
    window.$trame.state.volume_rendering_toggle = payload;
  }
});
```

**Communication loss relative to current architecture:**
- Tight coupling between React field selector dropdowns and the ParaView viewer state requires explicit postMessage bridging.
- The `viewport.image.render` screenshot flow changes — the iframe exposes a `getScreenshot()` method via postMessage instead of a WebSocket response.
- These bridging components are new code to write.

### What the React Dashboard Keeps

- All non-visualization React components (job list, convergence charts, filter panels, field selectors) remain unchanged.
- The WebSocket connection for residual streaming (`divergence_alert`, residual plots) is unaffected — it uses a separate WebSocket endpoint (the API server's own WS server), not ParaView Web.

### What the React Dashboard Rewrites

- `ParaViewViewer.tsx` — replaced by iframe embed or new bridge component
- `paraviewProtocol.ts` — replaced by `CFDViewerBridge.ts` using postMessage
- All call sites of `sendProtocolMessage()` for ParaView RPCs — redirected to bridge

---

## RPC Mapping: Current to Trame

| Current RPC | Current File | Trame Equivalent | Notes |
|------------|-------------|-----------------|-------|
| `visualization.volume.rendering.toggle` | `paraview_adv_protocols.py` | `ctrl.on_volume_rendering_toggle()` | Decorator: `@ctrl.add` |
| `visualization.volume.rendering.status` | `paraview_adv_protocols.py` | `@state.change("volume_rendering_status_request")` | Reactive getter |
| `visualization.filters.clip.create` | `paraview_adv_protocols.py` | `ctrl.on_filter_clip_create()` | `@ctrl.add` |
| `visualization.filters.contour.create` | `paraview_adv_protocols.py` | `ctrl.on_filter_contour_create()` | Same pattern |
| `visualization.filters.streamtracer.create` | `paraview_adv_protocols.py` | `ctrl.on_filter_streamtracer_create()` | Same pattern |
| `visualization.filters.delete` | `paraview_adv_protocols.py` | `ctrl.on_filter_delete()` | Same pattern |
| `visualization.filters.list` | `paraview_adv_protocols.py` | `@state.change("filter_list")` | Reactive list update |
| `viewport.image.render` | Built-in (ParaViewWebViewPortImageDelivery) | `ctrl.view_update()` (via `VtkRemoteView.update()`) | Trame pushes render as image stream |

---

## Key Breaking Changes Summary

| Area | Current | After Migration |
|------|---------|----------------|
| Python server framework | `vtk.web.launcher` + `wslink` + `ParaViewWebProtocol` | `trame` 3.12.0 + `get_server()` |
| RPC registration | `@exportRpc` decorator | `@ctrl.add` / `@state.change` decorator |
| Protocol base class | `ParaViewWebProtocol` | None (plain Python functions) |
| State push | `self._app.SMApplication.InvokeEvent("UpdateEvent")` | `ctrl.view_update()` / `state.var = val` |
| Server startup | JSON config + multi-process launcher spawner | Single `pvpython trame_server.py` |
| 3D viewport | Custom WebSocket image streaming (ParaViewWebViewPortImageDelivery) | `paraview.VtkRemoteView(view)` |
| Frontend framework | React + custom WebSocket RPC | Vue.js (served by trame) — iframe embedded in React |
| Client-server protocol | Custom `message.id` JSON-RPC over ws:// | Trame reactive state (HTTP+WS auto-upgrade) |
| Session/auth | wslink `secret` authKey + launcher config | Trame built-in auth or remove (container isolation is sufficient) |
| UI components | React Vuetify components | `trame-vuetify` Vue components in iframe |
| Port inside container | 9000 (WebSocket) | 9000 (HTTP + WebSocket upgrade) |
| Port mapping | `-p {host}:9000:9000` (same) | Same — just the protocol changes |
| Case loading | Launcher reads `--data` from launcher config | `argparse --data` in `trame_server.py` |
| Entrypoint | `entrypoint_wrapper.sh` → imports adv_protocols → launcher.py | `pvpython /trame_server.py` (direct) |
| Image verification | `import vtk.web.launcher` | `import trame` |

---

## Implementation Complexity Assessment

| Component | Complexity | Notes |
|-----------|-----------|-------|
| Dockerfile + entrypoint | Low | Replace 3 lines; install 3 pip packages |
| `trame_server.py` (new) | Medium | Rewrite all protocol handlers; new view setup pattern |
| `paraview_web_launcher.py` | Medium | Remove launcher config; change container start command |
| React iframe bridge | Medium | New `CFDViewerBridge.ts` + postMessage wiring |
| Protocol handler migration | Medium | ~13 RPCs to rewrite as `@ctrl.add` methods |
| Filter registry | Low | Same module-level dict pattern |

---

## Sources

| Source | URL | Confidence | Verifies |
|--------|-----|------------|---------|
| trame GitHub | https://github.com/Kitware/trame | HIGH | Core architecture, v3.x confirmed |
| trame PyPI meta-package | https://pypi.org/pypi/trame/3.12.0/json | HIGH | wslink as dependency, trame-client 3.10.1 |
| trame-vtk PyPI | https://pypi.org/pypi/trame-vtk/2.11.6/json | HIGH | trame-client >= 3.4, Python >= 3.9 |
| trame-vuetify PyPI | https://pypi.org/pypi/trame-vuetify/json | HIGH | trame-client >= 3.7 |
| trame-client PyPI | https://pypi.org/pypi/trame-client/json | HIGH | Bundles Vue.js; included in trame meta-package |
| trame ParaView tutorial | https://kitware.github.io/trame/guide/tutorial/paraview.html | HIGH | Server pattern, VtkRemoteView, venv setup |
| trame concepts | https://kitware.github.io/trame/guide/concepts/ | HIGH | State management, ctrl.add, state.change |
| trame widgets.paraview | https://trame.readthedocs.io/en/latest/trame.widgets.paraview.html | HIGH | VtkRemoteView vs VtkLocalView methods |
| trame Server API | https://trame.readthedocs.io/en/latest/trame.app.html | MEDIUM | server.start() parameters |
| trame GitHub releases | https://github.com/Kitware/trame/releases | HIGH | v3.12.0 release date Aug 2025 |
| openfoam/paraview510 | https://hub.docker.com/r/openfoam/openfoam10-paraview510 | HIGH | Image name, ParaView 5.10, Python 3.9 |
| paraview.web.venv | https://kitware.github.io/trame/guide/tutorial/paraview.html | HIGH | Python 3.9 for ParaView 5.10/5.11 |
