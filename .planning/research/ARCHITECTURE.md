# Architecture Research — v1.5.0 Advanced Visualization

**Domain:** ParaView Web advanced visualization (Volume Rendering, Advanced Filters, Screenshot Export)
**Project:** AI-CFD Knowledge Harness v1.5.0
**Researched:** 2026-04-11
**Confidence:** HIGH (verified against ParaView 5.10.0 source, existing codebase patterns, and established protocol conventions)

---

## Executive Summary

v1.5.0 adds three capability clusters to the existing v1.4.0 ParaView Web viewer:

1. **Volume Rendering** -- GPU ray-cast volume representation toggle
2. **Advanced Filters** -- Clip, Contour, and StreamTracer pipeline stages
3. **Screenshot Export** -- Base64 PNG capture of the current viewport

The architecture extends the existing sidecar Docker container pattern with **custom wslink protocol handler classes** registered at container startup. No new Docker images, npm packages, or infrastructure components are required. All three features are implemented as:

- **Server-side:** Python protocol classes in `paraview_adv_protocols.py` mounted into the container at `/tmp/`
- **Frontend-side:** TypeScript protocol message builders in `paraviewProtocol.ts` and React UI controls in `ParaViewViewer.tsx`

---

## 1. How the Existing Architecture Works

### 1.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  React Dashboard (Browser)                                              │
│  ┌─────────────────┐    ┌──────────────────────────────────────────┐  │
│  │ ParaViewViewer   │    │  WebSocket (wlink JSON-RPC bidirectional)  │  │
│  │ .tsx            │◄──►│                                          │  │
│  │  - state machine │    │  ┌──────────────────────────────────────┐│  │
│  │  - UI controls  │    │  │ ParaView Web Container (Docker)       ││  │
│  │  - WS connect   │    │  │  - vtkmodules/web/launcher.py         ││  │
│  └────────┬────────┘    │  │  - paraview_adv_protocols.py  (new)   ││  │
│           │ fetch       │  │  │    ↕ (Python simple API)            ││  │
│           ▼             │  │  │ ParaView/Simple (VTK rendering)     ││  │
│  ┌─────────────────┐   │  │  └──────────────────────────────────────┘│  │
│  │ FastAPI Backend  │   │  └──────────────────────────────────────────┘│  │
│  │ (uvicorn)        │   └──────────────────────────────────────────────┘  │
│  │  - visualization  │                                                  │
│  │    router         │                                                  │
│  │  - paraview_web  │                                                  │
│  │    _launcher.py   │                                                  │
│  └─────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Existing Component Map

| Component | File | Responsibility |
|-----------|------|----------------|
| `ParaviewWebManager` | `api_server/services/paraview_web_launcher.py` | Docker container lifecycle, session tracking, idle timeout |
| `visualization` router | `api_server/routers/visualization.py` | REST endpoints: launch, status, heartbeat, shutdown |
| `ParaViewViewer` | `dashboard/src/components/ParaViewViewer.tsx` | React component: WebSocket state machine, UI controls |
| `paraviewProtocol` | `dashboard/src/services/paraviewProtocol.ts` | JSON-RPC message builders (slice, LUT, scalar bar, render) |
| `paraview.ts` | `dashboard/src/services/paraview.ts` | REST API client for session launch/heartbeat |

### 1.3 Existing Data Flow

```
1. User clicks "Launch 3D Viewer"
2. React calls POST /visualization/launch → FastAPI
3. FastAPI starts Docker container (paraview_web_launcher.py)
4. Container runs: vtkmodules/web/launcher.py + openfoam/openfoam10-paraview510
5. WebSocket port (9000 inside, mapped to host) becomes available
6. React receives { session_id, session_url, auth_key } → opens WebSocket
7. React sends auth_key as first text message
8. React sends JSON-RPC: OpenFOAMReader.Open, GetPropertyList, GetTimeSteps
9. Server pushes rendered frames via viewport.image.push subscription
10. User interactions (mouse, controls) send JSON-RPC → server updates view
```

---

## 2. New Components

### 2.1 New Server-Side File: `paraview_adv_protocols.py`

This file is **mounted read-only into the ParaView Web container** at `/tmp/paraview_adv_protocols.py` and imported at server startup via the launcher config's `cmd` array. It defines three protocol classes:

```python
# api_server/services/paraview_adv_protocols.py  (conceptual)

from paraview.web.protocols import ParaViewWebProtocol
from wslink import register as exportRpc
from paraview import simple

class ParaViewWebVolumeRendering(ParaViewWebProtocol):
    """Volume representation toggle + opacity transfer function."""

    @exportRpc("volume.representation.create")
    def createVolumeRepresentation(self, sourceProxyId, viewId):
        # Get the source proxy and view
        source = self.mapIdToProxy(sourceProxyId)
        view = self.mapIdToProxy(viewId) if viewId else simple.GetActiveView()

        # Show source as Volume (activates vtkGPUVolumeRayCastMapper)
        rep = simple.GetRepresentation(proxy=source, view=view)
        rep.Representation = "Volume"

        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success", proxyId": source.GetGlobalIDAsString()}

    @exportRpc("volume.representation.surface")
    def setSurfaceRepresentation(self, sourceProxyId, viewId):
        source = self.mapIdToProxy(sourceProxyId)
        view = self.mapIdToProxy(viewId) if viewId else simple.GetActiveView()
        rep = simple.GetRepresentation(proxy=source, view=view)
        rep.Representation = "Surface"
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("volume.opacity.set")
    def setVolumeOpacity(self, arrayName, points):
        # points = [x0, y0, x1, y1, ...] control point pairs
        otf = simple.GetOpacityTransferFunction(arrayName)
        otf.Points = points
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}


class ParaViewWebAdvancedFilters(ParaViewWebProtocol):
    """Clip, Contour, StreamTracer filter pipeline."""

    @exportRpc("clip.create")
    def createClip(self, sourceProxyId, normal, origin):
        source = self.mapIdToProxy(sourceProxyId)
        view = simple.GetActiveView()

        clip = simple.Clip(Input=source, ClipType="Plane")
        clip.ClipType.Normal = normal
        clip.ClipType.Origin = origin
        simple.Show(clip, view)
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success", "proxyId": clip.GetGlobalIDAsString()}

    @exportRpc("clip.update")
    def updateClip(self, proxyId, normal, origin):
        proxy = self.mapIdToProxy(proxyId)
        proxy.ClipType.Normal = normal
        proxy.ClipType.Origin = origin
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("clip.delete")
    def deleteClip(self, proxyId):
        proxy = self.mapIdToProxy(proxyId)
        simple.Delete(proxy)
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("contour.create")
    def createContour(self, sourceProxyId, arrayName, isovalues):
        source = self.mapIdToProxy(sourceProxyId)
        view = simple.GetActiveView()

        contour = simple.Contour(Input=source)
        contour.ContourBy = ["POINTS", arrayName]
        contour.Isosurfaces = isovalues
        simple.Show(contour, view)
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success", "proxyId": contour.GetGlobalIDAsString()}

    @exportRpc("contour.update")
    def updateContour(self, proxyId, isovalues):
        proxy = self.mapIdToProxy(proxyId)
        proxy.Isosurfaces = isovalues
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("contour.delete")
    def deleteContour(self, proxyId):
        proxy = self.mapIdToProxy(proxyId)
        simple.Delete(proxy)
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("streamtracer.create")
    def createStreamTracer(self, sourceProxyId, seedType="maskingRegion"):
        source = self.mapIdToProxy(sourceProxyId)
        view = simple.GetActiveView()

        tracer = simple.StreamTracer(Input=source, SeedType=seedType)
        tracer.Vectors = ["POINTS", "U"]       # velocity field
        tracer.MaximumTrackLength = 100
        tracer.ComputeVorticity = 1
        simple.Show(tracer, view)
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success", "proxyId": tracer.GetGlobalIDAsString()}

    @exportRpc("streamtracer.delete")
    def deleteStreamTracer(self, proxyId):
        proxy = self.mapIdToProxy(proxyId)
        simple.Delete(proxy)
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}
```

**Key architectural note:** All three classes extend `ParaViewWebProtocol` and register RPC methods with `@exportRpc`. The `mapIdToProxy()` method (inherited from base class) converts integer proxy IDs from the frontend into ParaView `simple` proxy objects. This is the exact same pattern used by all built-in ParaView Web protocols.

### 2.2 New Frontend Protocol Message Builders

These extend `dashboard/src/services/paraviewProtocol.ts`:

```typescript
// dashboard/src/services/paraviewProtocol.ts  (additions)

// --- Volume Rendering ---

export function createVolumeRepresentationMessage(sourceProxyId: number): object {
  return {
    id: "pv-volume-create",
    method: "volume.representation.create",
    params: { sourceProxyId, viewId: -1 }
  };
}

export function createSurfaceRepresentationMessage(sourceProxyId: number): object {
  return {
    id: "pv-surface",
    method: "volume.representation.surface",
    params: { sourceProxyId, viewId: -1 }
  };
}

export function createVolumeOpacityMessage(arrayName: string, points: number[]): object {
  return {
    id: "pv-volume-opacity",
    method: "volume.opacity.set",
    params: { arrayName, points }
  };
}

// --- Clip Filter ---

export function createClipCreateMessage(
  sourceProxyId: number,
  normal: [number, number, number],
  origin: [number, number, number]
): object {
  return {
    id: "pv-clip-create",
    method: "clip.create",
    params: { sourceProxyId, normal, origin }
  };
}

export function createClipUpdateMessage(
  proxyId: number,
  normal: [number, number, number],
  origin: [number, number, number]
): object {
  return {
    id: "pv-clip-update",
    method: "clip.update",
    params: { proxyId, normal, origin }
  };
}

export function createClipDeleteMessage(proxyId: number): object {
  return {
    id: "pv-clip-delete",
    method: "clip.delete",
    params: { proxyId }
  };
}

// --- Contour Filter ---

export function createContourCreateMessage(
  sourceProxyId: number,
  arrayName: string,
  isovalues: number[]
): object {
  return {
    id: "pv-contour-create",
    method: "contour.create",
    params: { sourceProxyId, arrayName, isovalues }
  };
}

export function createContourUpdateMessage(proxyId: number, isovalues: number[]): object {
  return {
    id: "pv-contour-update",
    method: "contour.update",
    params: { proxyId, isovalues }
  };
}

export function createContourDeleteMessage(proxyId: number): object {
  return {
    id: "pv-contour-delete",
    method: "contour.delete",
    params: { proxyId }
  };
}

// --- StreamTracer ---

export function createStreamTracerCreateMessage(
  sourceProxyId: number,
  seedType: string = "maskingRegion"
): object {
  return {
    id: "pv-tracer-create",
    method: "streamtracer.create",
    params: { sourceProxyId, seedType }
  };
}

export function createStreamTracerDeleteMessage(proxyId: number): object {
  return {
    id: "pv-tracer-delete",
    method: "streamtracer.delete",
    params: { proxyId }
  };
}

// --- Screenshot Export ---

export function createScreenshotMessage(
  quality: number = 85,
  viewId: number = -1
): object {
  return {
    id: "pv-screenshot",
    method: "viewport.image.render",
    params: { view: viewId, quality, ratio: 1 }
  };
}

export function parseScreenshotResponse(response: { result?: { image?: string } }): string | null {
  return response?.result?.image ?? null;
}
```

### 2.3 New Backend Endpoint: Screenshot File Proxy

The built-in `viewport.image.render` RPC returns the PNG as a base64 string in the WebSocket JSON-RPC response. This requires **no new REST endpoint** for the basic flow.

However, if users want to save screenshots to the host filesystem (rather than download to browser), a new REST endpoint is needed:

**`POST /visualization/{session_id}/screenshot`** -- proxies `pv.data.save` result from container to a project reports directory.

This is deferred to v1.5.x (P3 in feature priorities).

---

## 3. Data Flows

### 3.1 Volume Rendering Data Flow

```
User clicks "Volume" toggle
    │
    ├──► React: sendProtocolMessage(createVolumeRepresentationMessage(sourceId))
    │         → WS JSON-RPC → container
    │
    ▼
Container: ParaViewWebVolumeRendering.createVolumeRepresentation()
    ├── rep.Representation = "Volume"    ← vtkGPUVolumeRayCastMapper activates
    ├── simple.Render()
    ├── InvokeEvent("UpdateEvent")
    └── Push updated frame via viewport.image.push (existing subscription)
    │
    ▼
React: No explicit response handling; view updates via pushed frame
```

### 3.2 Clip Filter Data Flow

```
User selects axis + origin → clicks "Apply"
    │
    ├──► WS JSON-RPC: clip.create { sourceProxyId, normal, origin }
    │
    ▼
Container: ParaViewWebAdvancedFilters.createClip()
    ├── clip = simple.Clip(Input=source, ClipType="Plane")
    ├── clip.ClipType.Normal = normal
    ├── clip.ClipType.Origin = origin
    ├── simple.Show(clip, view)
    ├── simple.Render()
    ├── InvokeEvent("UpdateEvent")
    └── return { result: "success", proxyId: "123" }
    │
    ▼
React: Stores proxyId in viewer state → enables Update/Delete buttons
```

### 3.3 Screenshot Export Data Flow

```
User clicks "Screenshot"
    │
    ├──► WS JSON-RPC: viewport.image.render { quality: 85 }
    │
    ▼
Container: ParaViewWebViewPort.viewportImageRender()  ← BUILT-IN, no custom code
    ├── Renders current view to offscreen framebuffer
    ├── Encodes as PNG via StillRenderToString()
    └── return { result: { image: "<base64 PNG>" } }
    │
    ▼
React: parseScreenshotResponse() → base64 string
    │
    ▼
React: atob(base64) → Uint8Array → Blob → URL.createObjectURL()
    │
    ▼
React: <a download="cfd-result.png"> → click → browser download
    URL.revokeObjectURL()  ← cleanup
```

### 3.4 State Flow (React)

Each active filter tracks its server-side proxy ID for update/delete operations:

```
ParaViewViewer state (additions):
  │
  ├── sourceProxyId: number          // OpenFOAM reader proxy (discovered at connect)
  │
  ├── representation: 'Surface' | 'Volume'
  │
  ├── activeClip: {
  │     proxyId: number,
  │     normal: [number, number, number],
  │     origin: [number, number, number]
  │   } | null
  │
  ├── activeContour: {
  │     proxyId: number,
  │     arrayName: string,
  │     isovalues: number[]
  │   } | null
  │
  └── activeStreamTracer: {
        proxyId: number
      } | null
```

---

## 4. Component Map: New vs Modified

### 4.1 New Components

| Component | File Path | Responsibility |
|-----------|-----------|----------------|
| Advanced protocols handler | `api_server/services/paraview_adv_protocols.py` | Python wslink protocol classes for volume, clip, contour, streamtracer |
| Advanced filter UI panel | `dashboard/src/components/AdvancedFilterPanel.tsx` (new file) | Collapsible panel with clip/contour/streamlines controls |
| Volume rendering toggle | Integrated into `ParaViewViewer.tsx` (new buttons) | Surface/Volume toggle button group |

### 4.2 Modified Components

| Component | Change |
|-----------|--------|
| `api_server/services/paraview_web_launcher.py` | `_build_launcher_config()`: add `--volume` flag to pvpython command to import `paraview_adv_protocols.py` at startup; mount `paraview_adv_protocols.py` as a volume |
| `dashboard/src/services/paraviewProtocol.ts` | Add all new message builders (volume, clip, contour, streamtracer, screenshot) |
| `dashboard/src/components/ParaViewViewer.tsx` | Add new React state for filter proxy IDs; add new UI sections for volume toggle, advanced filter panel, screenshot button; wire new `sendProtocolMessage` calls |
| `dashboard/src/components/ParaViewViewer.css` | Add CSS for new UI controls |
| `dashboard/src/services/api.ts` | Add `POST /visualization/{session_id}/screenshot` REST call (v1.5.x only) |

### 4.3 No Changes Needed

- `api_server/routers/visualization.py` -- No new REST endpoints required for WebSocket-based features. Screenshot file proxy (v1.5.x) only if saving to server filesystem.
- `api_server/models.py` -- No new Pydantic models needed.
- `dashboard/src/services/paraview.ts` -- Session lifecycle management unchanged.

---

## 5. Build Order (Considering Dependencies)

```
PHASE 1: Server-Side Protocol Handlers
────────────────────────────────────────
1. Create api_server/services/paraview_adv_protocols.py
   - Implement ParaViewWebVolumeRendering class
   - Implement ParaViewWebAdvancedFilters class
   - Each method: mapIdToProxy() → simple.XXX() → simple.Render() → InvokeEvent()
   Rationale: No frontend dependencies; pure Python. Implement and test first.

2. Update paraview_web_launcher.py _build_launcher_config()
   - Mount paraview_adv_protocols.py into container at /tmp/
   - Add python import command to launcher startup args
   - Add --volume flag to pvpython command
   Rationale: Launcher must pass the new protocols to the container.

3. Test: Start container, verify protocol methods appear in wslink registry
   (Check: pvpython -c "import paraview_adv_protocols" works inside container)


PHASE 2: Frontend Protocol Message Builders
──────────────────────────────────────────────
4. Extend dashboard/src/services/paraviewProtocol.ts
   - Add all message builder functions
   - Add parseScreenshotResponse()
   Rationale: Pure TypeScript; depends only on the protocol method names matching server.

5. Add response parsers to ParaViewViewer.tsx
   - Parse clip.create / contour.create / streamtracer.create responses
   - Extract and store proxyId in React state
   Rationale: Proxy IDs must be tracked before UI controls can offer Update/Delete.


PHASE 3: Frontend UI Controls
────────────────────────────────
6. Add Volume Rendering toggle to ParaViewViewer.tsx
   - Surface / Volume button group (below existing field selector)
   - sendProtocolMessage(createVolumeRepresentationMessage(...)) on Volume click
   - sendProtocolMessage(createSurfaceRepresentationMessage(...)) on Surface click
   Rationale: Simplest new feature; establishes proxy ID tracking pattern.

7. Add AdvancedFilterPanel.tsx component
   - Clip section: axis selector (X/Y/Z/Off) + origin slider
   - Contour section: field selector + isovalues input + Apply/Delete
   - Streamlines section: seed type dropdown + Show/Delete
   - Wire all to sendProtocolMessage() + parse response + update state
   Rationale: Self-contained component; clean separation from main viewer.

8. Add screenshot button to ParaViewViewer.tsx
   - Calls createScreenshotMessage() → parseScreenshotResponse()
   - Decodes base64 → triggers browser download
   Rationale: One-button flow; no state to track.


PHASE 4: Integration
────────────────────────
9. Integration test: full flow
   - Launch session → connect WS → discover sourceProxyId → create clip →
     update clip origin → delete clip → create contour → screenshot → delete
   Rationale: End-to-end validation of the complete v1.5.0 feature set.
```

**Dependency chain:** Phase 1 must complete before Phase 2 (server protocol names must exist before frontend message builders reference them). Phase 2 and 3 can proceed in parallel on different files (protocol builders vs. UI components). Phase 4 is the integration gate.

---

## 6. Architectural Patterns

### Pattern 1: Sidecar Protocol Registration

**What:** Custom Python protocol classes are mounted as files into the ParaView Web Docker container and imported at startup via the launcher configuration.

**When:** When the ParaView Web server needs to expose application-specific RPC methods beyond the built-in set.

**Why:** This avoids forking the ParaView Web Docker image. The image is unchanged; custom behavior comes from mounted files.

**Trade-offs:**
- Pro: No image maintenance burden; upgrades to base image automatically include security patches
- Con: File mount dependency between host and container; startup args become more complex
- Con: Protocol file must be synchronized with base image Python library versions

### Pattern 2: Proxy ID State Tracking

**What:** The frontend stores the ParaView proxy integer ID (returned from create operations) in React state, then passes it back to update/delete operations.

**When:** For any filter or representation that persists on the server and may be modified after creation.

**Example:**
```typescript
// Create: server returns proxyId
const resp = await sendAndWait(createClipMessage(sourceId, normal, origin));
setActiveClip({ proxyId: parseInt(resp.result.proxyId), normal, origin });

// Update: frontend uses stored proxyId
sendProtocolMessage(createClipUpdateMessage(activeClip.proxyId, newNormal, newOrigin));

// Delete: frontend uses stored proxyId
sendProtocolMessage(createClipDeleteMessage(activeClip.proxyId));
setActiveClip(null);
```

**Trade-offs:**
- Pro: Server is the source of truth for proxy state; frontend is stateless for server objects
- Con: Stale proxyId if server-side proxy is deleted out-of-band (e.g., container restart)

### Pattern 3: Frame-Push Rendering (Existing, Unchanged)

**What:** After any server-side state change (filter create/update, representation change), the server calls `InvokeEvent("UpdateEvent")` which triggers `viewport.image.push` to push a new rendered frame to all subscribed clients.

**When:** After any `simple.Render()` call.

**This pattern is unchanged for v1.5.0.** All new protocol methods follow it. The frontend does not poll for render completion -- it receives pushed frames.

### Pattern 4: Orthogonal Feature Composition

**What:** Each advanced filter (clip, contour, streamlines) is independent. Users can activate multiple simultaneously. Each `simple.Show()` adds a representation layer.

**When:** When the user wants to compose multiple visualizations (e.g., clipped geometry + iso-surfaces + streamlines in one view).

**Implementation:** Each filter tracks its own `proxyId` in React state. Deleting one does not affect others.

---

## 7. Anti-Patterns to Avoid

### 7.1 Do NOT Create Filters Without Tracking the Proxy ID

Creating a clip (`clip.create`) and not storing the returned `proxyId` makes the filter impossible to update or delete. Every create must immediately parse the response and store the ID.

### 7.2 Do NOT Call `simple.Render()` Synchronously After Filter Creation

ParaView's render pipeline is asynchronous. Calling `simple.Render()` in a tight loop after creating multiple filters can cause race conditions. Each filter create/update should complete its render before the next command is sent.

### 7.3 Do NOT Mount Write Permissions to paraview_adv_protocols.py

The protocol file should be mounted read-only (`:ro`) to prevent container processes from modifying it. The file is configuration, not a data output.

### 7.4 Do NOT Use Hard-Coded Proxy IDs

Proxy IDs are assigned by the ParaView session at runtime and differ between sessions. Never hard-code a proxy ID like `426` (the pattern seen in ParaView examples). Always use the ID returned from the create operation.

### 7.5 Do NOT Mix REST and WebSocket for Filter Operations

All filter create/update/delete operations must go through the WebSocket JSON-RPC channel. Using REST for some and WebSocket for others introduces ordering problems (REST calls may arrive before the WebSocket state has updated the view).

---

## 8. Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-5 concurrent viewers | Single ParaView Web container per session (existing pattern); each viewer = 1 container |
| 5-20 concurrent viewers | Container orchestrator needed (Docker Compose or Kubernetes); session pooling for idle containers |
| 20+ concurrent viewers | ParaView Web does not scale horizontally easily; pre-rendered static images as fallback |

**v1.5.0 is scoped for single-user sessions** (same as v1.4.0). Advanced filters and volume rendering add CPU/GPU load but do not change the session-per-user architecture.

**First bottleneck for advanced filters:** Large meshes (5M+ cells) with volume rendering can exhaust GPU memory. Mitigation: `Smart Volume Mapper` (adaptive) instead of default `GPU Volume Ray Cast Mapper` -- add as v1.5.x option.

---

## 9. Open Questions

1. **Container startup import timing:** The `paraview_adv_protocols.py` must be imported before the wslink server registers RPC methods. Confirm the `--volume` approach works with `vtkmodules/web/launcher.py` by testing the import sequence in the actual container.

2. **Large mesh volume rendering memory:** `vtkGPUVolumeRayCastMapper` for meshes > 5M cells may exceed GPU memory. Should v1.5.0 default to `Smart Volume Mapper` to be safe, or is `GPU Volume Ray Cast Mapper` acceptable for typical OpenFOAM case sizes (100K-1M cells)?

3. **Source proxy ID discovery:** The `sourceProxyId` (OpenFOAM reader proxy ID) is discovered from the `OpenFOAMReader.GetPropertyList` response. This needs validation -- confirm the response format includes the proxy's integer ID that can be passed to filter creation.

---

## 10. Sources

| Source | URL | Confidence | Verifies |
|--------|-----|------------|---------|
| ParaView 5.10.0 protocols.py (GitHub) | `https://raw.githubusercontent.com/Kitware/ParaView/v5.10.0/Web/Python/paraview/web/protocols.py` | HIGH | `@exportRpc` decorator pattern; `mapIdToProxy()`; `SaveScreenshot`; `ViewportImageRender` |
| Existing `paraview_web_launcher.py` | `api_server/services/paraview_web_launcher.py` | HIGH | Container lifecycle; `_build_launcher_config()` structure; mount pattern |
| Existing `paraviewProtocol.ts` | `dashboard/src/services/paraviewProtocol.ts` | HIGH | JSON-RPC message format; response parsing patterns |
| Existing `ParaViewViewer.tsx` | `dashboard/src/components/ParaViewViewer.tsx` | HIGH | WebSocket state machine; `sendProtocolMessage` pattern; UI control structure |
| Existing `visualization.py` router | `api_server/routers/visualization.py` | HIGH | REST endpoint pattern; session model |
| FEATURES.md v1.5.0 | `.planning/research/FEATURES.md` | HIGH | Protocol message flows; feature dependencies; MVP scope |
| STACK.md v1.5.0 | `.planning/research/STACK.md` | HIGH | Stack decisions; Python protocol handler structure |
