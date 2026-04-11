# Architecture Research: ParaView Web to Trame Migration

**Domain:** Interactive 3D CFD Visualization Server
**Project:** AI-CFD Knowledge Harness v1.6.0 (trame migration)
**Researched:** 2026-04-11
**Confidence:** MEDIUM-HIGH (verified against trame source on GitHub, ParaView Web source patterns, official docs)

Sources: ParaView Web source (v3.2.21), trame source (Kitware/trame, Kitware/trame-server GitHub), official docs (trame.readthedocs.io, kitware.github.io/trame)

---

## Executive Summary

The migration from ParaView Web to trame is a full-stack rewrite, not a port. The most significant changes are:

1. **Frontend**: React + raw WebSocket is replaced by Vue 3 + trame client library with automatic state synchronization. The `ParaViewViewer.tsx` component must be completely rewritten as a Vue component.

2. **Backend protocol registration**: The `@exportRpc` + `ParaViewWebProtocol` pattern is replaced by `@controller.add()` decorators on a `Server` instance. No global registry, no entrypoint wrapper script.

3. **Docker entrypoint**: The custom `entrypoint_wrapper.sh` that imports Python files before `launcher.py` starts is eliminated. The trame application runs directly as `pvpython app.py --port N`.

4. **Session model**: Container-per-session remains the recommended pattern, but lifecycle management shifts from ParaView Web's JSON config launcher to trame's native `server.start(port=N)` API.

The ParaView operations (OpenFOAMReader, Clip, Contour, StreamTracer, Volume Rendering) remain unchanged -- only the wiring layer changes.

---

## Current Architecture: ParaView Web

### System Overview

```
React Dashboard (port 8080)
        |
        | HTTP REST (FastAPI)
        v
FastAPI Backend (port 3001)
        |
        | docker run ... -p HOST_PORT:9000
        v
ParaView Web Container (cfd-workbench:openfoam-v10)
  /entrypoint_wrapper.sh (PID 1)
    -> imports /tmp/adv_protocols.py (registers @exportRpc classes)
    -> exec pvpython launcher.py ...
        |
        | wslink + JSON over WebSocket (port 9000)
        v
ParaView Web Server (wslink + vtk.web.protocol.ParaViewWebProtocol)
  - ParaViewWebVolumeRendering (4 RPCs)
  - ParaViewWebAdvancedFilters (9 RPCs)
  - Built-in protocols (Render, OpenFOAMReader, viewport.image.render, ...)
```

### Current Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| `ParaviewWebManager` | `paraview_web_launcher.py` | Docker container lifecycle, port allocation (`8081-8090`), session management |
| `entrypoint_wrapper.sh` | `entrypoint_wrapper.sh` | PID 1 inside container; imports `adv_protocols.py` before wslink starts |
| `ParaViewWebVolumeRendering` | `paraview_adv_protocols.py` | GPU detection, volume toggle RPC |
| `ParaViewWebAdvancedFilters` | `paraview_adv_protocols.py` | Clip/Contour/StreamTracer filter RPCs |
| `ParaViewViewer.tsx` | `ParaViewViewer.tsx` | React component; raw `WebSocket` client; 9-state machine |
| `paraviewProtocol.ts` | `paraviewProtocol.ts` | JSON-RPC message builders/parsers |
| `paraview.ts` | `paraview.ts` | FastAPI session lifecycle API client |

### Current Protocol Pattern

ParaView Web uses wslink with JSON-RPC over WebSocket:

```typescript
// Frontend sends auth key as first raw string message
ws.send(authKey);

// Then sends JSON-RPC style messages
ws.send(JSON.stringify({
  id: "pv-volume-toggle",
  method: "visualization.volume.rendering.toggle",
  params: { fieldName, enabled }
}));

// Server responds with JSON
JSON.parse(event.data) as { id: "pv-volume-toggle", result: { success: true } }

// ws.onmessage routes by message.id (lines 214-327 in ParaViewViewer.tsx)
if (message.id === 'pv-volume-status' && message.result) { ... }
if (message.id === 'pv-filter-clip' && message.result) { ... }
```

### Current Docker/Entrypoint Pattern

```python
# paraview_web_launcher.py _start_container():
docker run -d \
  --name pvweb-{session_id} \
  -v case_dir:/data:ro \
  -v adv_protocols.py:/tmp/adv_protocols.py:ro \
  -p HOST_PORT:9000 \
  --entrypoint /entrypoint_wrapper.sh \
  cfd-workbench:openfoam-v10 \
  pvpython launcher.py /tmp/launcher_config.json
```

```bash
# entrypoint_wrapper.sh (lines 11-18)
if pvpython -c "import sys; sys.path.insert(0, '/tmp'); import adv_protocols"; then
  echo "Protocols registered with wslink."
fi
exec "$@"  # exec replaces shell with pvpython
```

The JSON config (lines 297-316) tells `launcher.py` to start wslink on port 9000 inside the container, with session URL `ws://${host}:{port}/ws`.

### Current Session Lifecycle

```
launch_session():
  1. validate_docker_available()
  2. build_custom_image()        # no-op if already built
  3. _verify_image()             # checks vtk.web.launcher exists
  4. allocate port from 8081-8090 range
  5. generate auth_key (secrets.token_urlsafe(16))
  6. write JSON config to temp file
  7. _start_container()         # docker run with entrypoint_wrapper.sh
  8. _wait_for_ready()           # poll "Starting factory" in logs
  9. return ParaViewWebSession { container_id, port, auth_key }

shutdown_session():
  docker kill pvweb-{session_id}
```

---

## Target Architecture: Trame

### System Overview

```
React Dashboard (port 8080)
        |
        | HTTP REST (FastAPI)
        v
FastAPI Backend (port 3001)
        |
        | docker run ... -p HOST_PORT:CONTAINER_PORT
        v
Trame Container (cfd-workbench:openfoam-v10 + trame installed)
  pvpython /app/app.py --port CONTAINER_PORT
    -> from trame.app import get_server
    -> server = get_server(name=session_id)
    -> @server.controller.add("rpc_name")    # RPC exposure
    -> @state.change("var")                   # auto state sync
    -> with SinglePageLayout(server) as layout:
    ->     paraview.VtkRemoteView(view)       # ParaView rendering widget
    -> server.start(port=CONTAINER_PORT)
        |
        | wslink + msgpack (binary) over WebSocket
        v
Trame Server (trame_server + aiohttp)
  - RPC methods via @controller.add() / @trigger()
  - ParaView via paraview.VtkRemoteView
```

### Trame Server Pattern (verified from trame source)

```python
# app.py (verified from Kitware/trame/examples/07_paraview/SimpleCone/RemoteRendering.py)
from trame.app import get_server
from trame.ui.vuetify import SinglePageLayout
from trame.widgets import paraview, vuetify
from paraview import simple
from trame.decorators import change, controller

# Server instance (singleton per name)
server = get_server(client_type="vue3")  # vue2 or vue3
state, ctrl = server.state, server.controller

# ParaView setup
cone = simple.Cone()
view = simple.Render()

# RPC method callable from frontend as ctrl.volume_toggle(...)
@controller.add("volume_toggle")
def volume_toggle(self, fieldName: str, enabled: bool):
    display = simple.GetDisplayProperties()
    if enabled:
        display.SetRepresentationToVolume()
    else:
        display.SetRepresentationToSurface()
    simple.Render()
    return {"success": True}

# State change reaction (auto-pushes to all clients when state.resolution changes)
@state.change("resolution")
def update_cone(resolution, **kwargs):
    cone.Resolution = resolution
    ctrl.view_update()

# Layout with ParaView rendering widget
with SinglePageLayout(server) as layout:
    with layout.content:
        html_view = paraview.VtkRemoteView(view)
        ctrl.view_reset_camera = html_view.reset_camera
        ctrl.view_update = html_view.update

if __name__ == "__main__":
    server.start(port=1234)  # blocking; port=0 for auto-allocation
```

### Key Trame Concepts (from source analysis)

| Concept | Source Location | Description |
|---------|-----------------|-------------|
| `get_server()` | `trame/app/__init__.py` | Returns `Server` singleton from `trame_server.core`; `name` parameter for multi-server |
| `Server.start(port=N)` | `trame_server/core.py` | Starts aiohttp server; `port=0` for auto; sets `server.port` after start |
| `@controller.add("name")` | `trame/decorators.py` | Exposes method as RPC callable as `ctrl.name()` on client |
| `@trigger("name")` | `trame/decorators.py` | Exposes method as `trigger("name", args)` on client |
| `@state.change("var")` | `trame/decorators.py` | Reacts when `state.var` changes; auto-pushes delta to client |
| `server.state` | `trame_server/state.py` | Shared `State` dict; assignment auto-syncs to client |
| `paraview.VtkRemoteView` | `trame-vtk` package | Server-side ParaView rendering widget; sends viewport over WS |
| `paraview.VtkLocalView` | `trame-vtk` package | Client-side VTK rendering (no server-side ParaView) |
| `WsLinkSession` | `trame_server/client.py` | wslink session; uses msgpack binary serialization (not JSON) |
| wslink auth | `WsLinkSession.auth()` | `wslink.hello` method with `authKey` as first message |

### Trame Server Lifecycle (from `trame_server/core.py`)

```python
def start(self, port=None, ..., backend="aiohttp", exec_mode="main", ...):
    # 1. enable_module(trame_client) if no _www set
    # 2. Parse CLI args (--port, --host, --timeout)
    # 3. CoreServer.bind_server(self)    # attach protocols
    # 4. CoreServer.configure(options)  # apply server options
    # 5. CoreServer.server_start(options, backend=backend, ...)
    #    -> starts aiohttp server on specified port
    # 6. For exec_mode="main": blocking run
    #    For exec_mode="task": returns asyncio.Task
```

Important: `server.start()` is blocking in `"main"` exec_mode. For a Docker container running as a sidecar, this means the container runs as long as the server runs. The FastAPI backend manages lifecycle via `docker kill`.

### Port Allocation in Trame

```python
# ParaView Web style (current)
port = self._next_port()  # cycles 8081-8090

# Trame style
server.start(port=1234)    # fixed port
server.start(port=0)       # auto-allocate to random open port
# After start:
print(server.port)         # returns actual port bound
```

---

## Architecture Comparison: ParaView Web vs Trame

### Protocol Layer

| Aspect | ParaView Web (current) | Trame (target) |
|--------|----------------------|----------------|
| **WebSocket protocol** | JSON (text) over wslink | msgpack (binary) over wslink |
| **RPC registration** | `@exportRpc("method.name")` on `ParaViewWebProtocol` subclasses | `@controller.add("method_name")` on `Server` instance |
| **Frontend RPC calls** | `ws.send(JSON.stringify({method, params}))` + `message.id` routing | `ctrl.method_name(args)` in Vue template or `trigger("name", args)` |
| **State sync** | Manual: client sends message, server responds | Automatic: `state.field = value` auto-pushes to all clients |
| **Server base class** | `ParaViewWebProtocol` (from `vtk.web.protocol`) | `Server` (from `trame_server.core`) |
| **Serialization** | JSON (human-readable) | msgpack (binary, faster) |
| **Auth** | Auth key as raw string on first WS message | wslink `wslink.hello` with `authKey` in kwargs |

### Frontend Architecture

| Aspect | ParaView Web | Trame |
|--------|--------------|-------|
| **Framework** | React (custom WebSocket client) | Vue.js 3 (trame client library) |
| **Component model** | `ParaViewViewer.tsx` manages raw WS connection manually | Vue components bound to `server.state` |
| **Connection** | `new WebSocket(sessionUrl)` + manual auth + reconnect logic | `trame_client` manages connection automatically |
| **Message routing** | Manual `message.id` switch statement | Automatic method routing via `ctrl.*` or `trigger()` |
| **Protocol URL** | `ws://host:port/ws` + auth key as first message | `ws://host:port/` + wslink hello protocol |
| **Rendering widget** | `#paraview-viewport` div + `viewport.image.render` RPC for updates | `<paraview-vtk-remote-view>` Vue component with auto-update |
| **Reactivity** | Manual setState on message receipt | Vue reactive `v_model` bound to state |

### Docker Container Architecture

| Aspect | ParaView Web | Trame |
|--------|--------------|-------|
| **Entrypoint** | Custom `entrypoint_wrapper.sh` (imports Python files before wslink starts) | Direct: `pvpython /app/app.py --port N` |
| **Protocol setup** | `launcher.py` reads JSON config, starts wslink at fixed port 9000 | `server.start(port=N)` starts aiohttp + wslink on configurable port |
| **Port mapping** | Host port mapped to container port 9000 (fixed internal port) | Host port mapped to container port N (same, configurable) |
| **Session identity** | Container name `pvweb-{session_id}` | Container name `trame-{session_id}` (or port-based) |
| **Protocol file import** | Mount `adv_protocols.py` at `/tmp/adv_protocols.py`, import via wrapper | Python code is the main module; `@controller.add` decorators at import time |
| **Ready signal** | `"Starting factory" in container logs` (polled by FastAPI) | `server.start()` is blocking call; port property available immediately |
| **PID 1** | Bash wrapper script | `pvpython` directly (no shell wrapper) |

### Session/Security Model

| Aspect | ParaView Web | Trame |
|--------|--------------|-------|
| **Session isolation** | One Docker container per session | One Docker container per session (recommended) |
| **Auth key** | `secrets.token_urlsafe(16)` passed via JSON config, sent as first WS message | Same key, passed as `wslink.hello` kwargs |
| **Idle timeout** | FastAPI `ParaviewWebManager._idle_monitor()` polls sessions every 60s | FastAPI could manage same way (container-level), or use `server.start(timeout=N)` |

---

## Data Flow Comparison

### Current Data Flow (ParaView Web)

```
1. User clicks "Launch 3D Viewer"
   -> React: launchVisualizationSession(jobId, caseDir) [paraview.ts:32]

2. FastAPI POST /visualization/launch
   -> ParaviewWebManager.launch_session() [paraview_web_launcher.py:188]
      a. validate_docker_available()
      b. build_custom_image()
      c. allocate port from 8081-8090
      d. generate auth_key
      e. write JSON config to temp file
      f. docker run (entrypoint_wrapper.sh)
         - imports /tmp/adv_protocols.py -> registers @exportRpc classes
         - exec pvpython launcher.py /tmp/launcher_config.json
      g. poll container logs for "Starting factory"
      h. return { session_url: ws://localhost:PORT/ws, auth_key, port }

3. React: new WebSocket(sessionUrl) [ParaViewViewer.tsx:185]
   -> ws.onopen: ws.send(authKey) // auth [line 201]
   -> ws.onopen: sendProtocolMessage(createOpenFOAMReaderMessage(caseDir)) [line 203]

4. Container: ParaViewWebProtocol.handle_request() [wslink]
   -> routes by method name to registered handler

5. Container: simple.Render() + InvokeEvent("UpdateEvent") [adv_protocols.py]
   -> pushes viewport update to client

6. React: ws.onmessage -> JSON.parse -> switch(message.id) [ParaViewViewer.tsx:209]
   -> setAvailableFields, setVolumeEnabled, etc.
```

### Target Data Flow (Trame)

```
1. User clicks "Launch 3D Viewer"
   -> React (or new Vue component): launchVisualizationSession(jobId, caseDir)
      (FastAPI session endpoint unchanged)

2. FastAPI POST /visualization/launch
   -> TrameSessionManager.start_session()
      a. docker run cfd-workbench:openfoam-v10 pvpython /app/app.py --port N
      b. return { session_url: http://localhost:PORT/, auth_key, port }
      (No polling needed; server.start() is synchronous)

3. Vue: trame_client auto-connects to WebSocket
   -> sends wslink.hello with authKey
   -> server responds with clientID

4. Vue: ctrl.volume_toggle(fieldName, enabled) [or v_model bound to state]
   -> serialized via msgpack, sent over WebSocket

5. Container: @controller.add("volume_toggle") handler runs
   -> simple.Render()
   -> ctrl.view_update() -> pushes viewport to client

6. Vue: automatic state update (no manual routing)
```

---

## Docker/Entrypoint Changes Detail

### Current Dockerfile

```dockerfile
# Dockerfile
FROM openfoam/openfoam10-paraview510
COPY entrypoint_wrapper.sh /entrypoint_wrapper.sh
RUN chmod +x /entrypoint_wrapper.sh
ENTRYPOINT ["/entrypoint_wrapper.sh"]
# Container run: pvpython launcher.py /tmp/launcher_config.json
```

### Target Dockerfile

```dockerfile
# Dockerfile
FROM openfoam/openfoam10-paraview510
RUN pip install trame trame-vuetify trame-vtk --quiet  # Add trame packages
COPY app.py /app/app.py
WORKDIR /app
# Container run: pvpython /app/app.py --port 1234
# No ENTRYPOINT needed; pvpython is effectively the entrypoint
```

### Current Container Run (from `paraview_web_launcher.py:337`)

```python
docker run -d \
  --name pvweb-{session_id} \
  --platform linux/amd64 \
  -v config_path:/tmp/launcher_config.json:ro \
  -v case_path:/data:ro \
  -v adv_protocols:/tmp/adv_protocols.py:ro \
  -p HOST_PORT:9000 \
  --entrypoint /entrypoint_wrapper.sh \
  cfd-workbench:openfoam-v10 \
  pvpython launcher.py /tmp/launcher_config.json
```

### Target Container Run

```python
docker run -d \
  --name trame-{session_id} \
  --platform linux/amd64 \
  -v case_path:/data:ro \
  -p HOST_PORT:CONTAINER_PORT \
  cfd-workbench:openfoam-v10 \
  pvpython /app/app.py --port CONTAINER_PORT
```

Key differences:
- No `--entrypoint` override
- No mounted protocol Python file
- No JSON config file
- Port is container-internal AND external (same, since no NAT)
- Python file IS the entrypoint

---

## New vs Modified Components

| Component | Status | Notes |
|-----------|--------|-------|
| `paraview_web_launcher.py` | **REPLACE** | New `trame_session_manager.py` with `TrameSessionManager` class |
| `paraview_adv_protocols.py` | **REPLACE** | New `app.py` inside container with `@controller.add()` patterns |
| `entrypoint_wrapper.sh` | **DELETE** | No longer needed |
| `paraviewProtocol.ts` | **DELETE** | Message builders replaced by Vue `ctrl.*` calls |
| `ParaViewViewer.tsx` | **REPLACE** | New Vue component; full rewrite |
| `paraview.ts` | **ADAPT** | Keep session launch/shutdown REST endpoints; update URL construction |
| `Dockerfile` | **MODIFY** | Add trame packages, change entrypoint |
| `AdvancedFilterPanel.tsx` | **ADAPT/MOVE** | Move into new Vue component as sub-component |

### Component Boundaries After Migration

```
FastAPI Backend
  -> /visualization/launch    -> TrameSessionManager.start_session()
  -> /visualization/{id}      -> TrameSessionManager.get_session()
  -> /visualization/{id}/stop -> TrameSessionManager.shutdown_session()

TrameSessionManager (NEW, replaces ParaviewWebManager)
  -> docker run trame-{session_id} pvpython /app/app.py --port N
  -> docker kill trame-{session_id}
  -> Tracks: session_id, container_id, port, auth_key

Trame Container (NEW app.py inside container)
  -> get_server(name=session_id)
  -> @controller.add RPC methods (volume, clip, contour, streamtracer)
  -> paraview.VtkRemoteView for rendering
  -> OpenFOAM reader opened on client connect or server_ready

Vue Frontend (NEW, replaces ParaViewViewer.tsx)
  -> trame-vuetify layout components
  -> paraview-vtk-remote-view for 3D rendering
  -> v_model bound controls (slice, color, volume)
  -> ctrl.filter_clip() etc. for RPC calls
```

---

## Suggested Migration Build Order

### Phase 1: Trame Backend Skeleton
- Install trame inside existing container image (`pip install trame trame-vuetify trame-vtk`)
- Create `app.py` with minimal trame server + `paraview.VtkRemoteView`
- Test `pvpython /app/app.py --port 1234` manually inside container
- Verify the ParaView cone rendering appears in browser
- Verify `server.start(port=0)` auto-allocation works

### Phase 2: Migrate RPC Protocols
- Convert `ParaViewWebVolumeRendering` methods to `@controller.add()` handlers
- Convert `ParaViewWebAdvancedFilters` methods to `@controller.add()` handlers
- Test each RPC from a simple Vue button
- Verify ParaView state changes (resolution, clip, etc.) reflect in viewport

### Phase 3: FastAPI Launcher Adaptation
- Create `TrameSessionManager` (mirrors `ParaviewWebManager` interface)
- Replace Docker container run command with trame-style command
- Remove JSON config file, entrypoint wrapper, launcher.py references
- Verify session list, get, shutdown, idle timeout still work
- Keep `ParaViewWebSession` model or rename to `TrameSession`

### Phase 4: Vue Frontend (from scratch)
- Create new Vue component replacing `ParaViewViewer.tsx`
- Implement field selector, slice controls, color presets as Vue components
- Implement volume toggle, advanced filters as Vue components
- Implement screenshot, time step navigation
- Test WebSocket connection and all RPC calls

### Phase 5: Integration
- Connect new Vue frontend to existing FastAPI endpoints
- Test full launch flow: API call -> container start -> Vue connects
- Test reconnect logic with trame client
- Test idle timeout, heartbeat

### Phase 6: Feature Parity + Cleanup
- Compare old and new viewer feature-by-feature
- Delete old files: `ParaViewViewer.tsx`, `paraviewProtocol.ts`, `adv_protocols.py`, `entrypoint_wrapper.sh`, `paraview_web_launcher.py`
- Delete old Docker build artifacts
- Update documentation

---

## Backward Compatibility Considerations

### v1.4.0/v1.5.0 Viewer State
The existing viewer state (field selection, slice axis, color preset, volume enabled, active filters) is held in React component state in `ParaViewViewer.tsx`. This state has no persistence -- it is lost on refresh. The new Vue-based viewer will have equivalent state in `server.state` which IS persisted and synced.

**Breaking change**: Users with active v1.4.0/v1.5.0 viewer sessions who update mid-session will lose their viewer state. This should be documented as a known breaking change for in-flight sessions.

### API Compatibility
The FastAPI REST endpoints (`/visualization/launch`, `/visualization/{id}`, `/visualization/{id}/activity`) should remain at the same paths. Only the response format may change (returning trame URLs instead of ParaView Web URLs).

### Docker Image
The custom `cfd-workbench:openfoam-v10` image will need trame packages added. This is a Dockerfile change that affects build pipeline.

---

## Open Questions

1. **Multi-session within one container**: Can `get_server(name=session_id)` provide isolated sessions within one container? The `AVAILABLE_SERVERS` dict suggests named servers are singletons -- so container-per-session is likely still correct.

2. **Screenshot method**: What is the trame-equivalent of `viewport.image.render`? Need to verify `paraview.VtkRemoteView` exposes a screenshot/export method.

3. **OpenFOAM reader lifecycle**: Currently opened after WebSocket auth (line 203 of ParaViewViewer.tsx). In trame, should this happen in `on_server_ready` callback or lazily on first client connection?

4. **Idle timeout**: Currently managed by FastAPI `ParaviewWebManager._idle_monitor()`. With trame, should this remain in FastAPI (container-level), or use `server.start(timeout=N)` for server-level idle shutdown?

5. **Docker base image**: Does `openfoam/openfoam10-paraview510` ship with trame pre-installed? If not, `pip install trame trame-vuetify trame-vtk` adds to Dockerfile build time.

6. **Vue integration with React app**: The existing dashboard is React-based. How does the Vue-based trame viewer integrate? Options: (a) iframe embedding the trame server URL, (b) React component that loads trame client library directly, (c) full page navigation to trame URL.

7. **Port range reuse**: Current port range is `8081-8090`. With trame, does this same range work, or does trame have its own port allocation preferences?

---

## Anti-Patterns to Avoid

### "Partial migration" of frontend
**What people do:** Try to keep React and gradually introduce trame concepts.
**Why it's wrong:** Trame's frontend requires Vue.js; the entire viewer component must be rewritten as Vue.
**Do this instead:** Keep existing ParaView Web viewer running in parallel until Vue version is complete and tested.

### "Keep the entrypoint wrapper"
**What people do:** Adapt the existing `entrypoint_wrapper.sh` to work with trame by wrapping `server.start()`.
**Why it's wrong:** Trame uses `server.start()` as blocking main loop; no shell wrapper needed.
**Do this instead:** Make the Python file the direct container entrypoint with `pvpython /app/app.py`.

### "Import-time protocol registration"
**What people do:** Try to import protocol modules at container start (like current `adv_protocols.py` mounted at `/tmp/`).
**Why it's wrong:** Trame's `@controller.add()` decorators work at class/function definition time; no global registry pattern like ParaView Web's wslink registration.
**Do this instead:** Define all RPC methods in the main `app.py` module.

### "One server for all sessions"
**What people do:** Try to use a single long-lived trame server with session isolation via namespaced state.
**Why it breaks:** Unless explicitly designed for multi-tenant use, this risks state leakage between users.
**Do this instead:** Each session is a separate container with its own trame server, using container name as session identity (same as current `pvweb-{session_id}` pattern).

---

## Sources

- **ParaView Web**: `vtk.web.protocol.ParaViewWebProtocol`, `vtk.web.launcher` (v3.2.21, from openfoam/openfoam10-paraview510)
- **trame server core**: `Server.start()`, port allocation, `get_server()` -- `Kitware/trame-server/trame_server/core.py`
- **trame client**: `Client`, `WsLinkSession` with msgpack -- `Kitware/trame-server/trame_server/client.py`
- **trame decorators**: `@controller.add`, `@trigger`, `@state.change` -- `Kitware/trame/trame/decorators.py`
- **trame ParaView example**: `RemoteRendering.py` -- `Kitware/trame/examples/07_paraview/SimpleCone/RemoteRendering.py`
- **trame VTK docker**: `Dockerfile`, `app.py` -- `Kitware/trame/examples/deploy/docker/VtkRendering/`
- **trame app module**: `get_server()`, `TrameApp` -- `Kitware/trame/trame/app/`
- **trame lifecycle callbacks**: `on_server_start`, `on_server_ready`, `on_client_connected` -- `Kitware/trame/trame/app/__init__.py`
