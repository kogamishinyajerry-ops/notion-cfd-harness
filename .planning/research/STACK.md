# Technology Stack: v1.5.0 Advanced Visualization

**Project:** AI-CFD Knowledge Harness
**Milestone:** v1.5.0 -- Advanced Visualization (Volume Rendering, Advanced Filters, Screenshot Export)
**Date:** 2026-04-11
**Confidence:** HIGH (verified against ParaView 5.10.0 source via GitHub API; Docker image verified)

---

## Executive Summary

The existing ParaView Web stack already contains all required infrastructure for Volume Rendering, Advanced Filters, and Screenshot Export. **No new Docker images, Python packages, npm packages, or framework changes are needed.** The work is entirely in:

1. **Server-side:** Add custom wslink protocol handler classes (Python) registered at container startup
2. **Frontend:** Add matching protocol message builders (TypeScript) and UI controls

The existing `openfoam/openfoam10-paraview510` image provides:
- `vtkGPUVolumeRayCastMapper` for GPU volume rendering
- Built-in filters: `Clip`, `Contour`, `StreamTracer`, `Slice`
- `viewport.image.render` RPC for screenshot delivery

---

## Existing Stack (Do Not Change)

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Docker image | `openfoam/openfoam10-paraview510` | 5.10.1 | ParaView + OpenFOAM + VTK GPU volume mapper |
| Server protocols | `paraview.web.protocols` + custom | -- | wslink JSON-RPC method handlers |
| Frontend client | Raw WebSocket + manual JSON-RPC | -- | No npm dependency on @kitware/paraview-web |
| Frontend protocols | `paraviewProtocol.ts` | -- | Protocol message builders |
| Frontend component | `ParaViewViewer.tsx` | React 19 | Viewer UI |

**Key architectural note:** The system uses a custom subclass pattern of `ParaViewWebProtocol` for protocol methods. Methods like `Slice.Create`, `UpdateLUT`, `CreateScalarBar` already exist as custom handlers registered at container startup. The new features follow the exact same pattern.

---

## v1.5.0: Stack Additions

### 1. Volume Rendering

**Goal:** GPU-based volume representation for 3D scalar fields (density, temperature, velocity magnitude).

**No new libraries.** `vtkGPUVolumeRayCastMapper` is already in the Docker image.

**Approach:** Custom protocol class `ParaViewWebVolumeRendering` (extends `ParaViewWebProtocol`) registered at container startup. Volume rendering is enabled by setting `rep.Representation = "Volume"` on an existing proxy.

**Server-side (new file: `api_server/services/paraview_adv_protocols.py`):**

```python
"""
Custom ParaView Web protocol handlers for v1.5.0 Advanced Visualization.

Classes:
  - ParaViewWebVolumeRendering: Volume representation + opacity transfer function
  - ParaViewWebAdvancedFilters: Clip, Contour, StreamTracer filters

Mounted into the container at /tmp/adv_protocols.py and imported at server startup.
"""

from paraview import simple
from paraview.web.protocols import ParaViewWebProtocol
from wslink import register as exportRpc


class ParaViewWebVolumeRendering(ParaViewWebProtocol):
    """Volume rendering via GPU ray cast mapper -- ParaView 5.10 built-in."""

    @exportRpc("volume.representation.create")
    def createVolumeRepresentation(self, sourceProxyId: int, viewId: int = -1):
        """
        Switch a proxy's representation to GPU volume rendering.
        Uses vtkGPUVolumeRayCastMapper already available in the Docker image.
        """
        source = self.mapIdToProxy(sourceProxyId)
        view = self.getView(viewId)
        rep = simple.GetRepresentation(proxy=source, target=view)
        rep.Representation = "Volume"
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success", "representation": "Volume"}

    @exportRpc("volume.representation.surface")
    def createSurfaceRepresentation(self, sourceProxyId: int, viewId: int = -1):
        """Switch a proxy's representation back to surface (disable volume)."""
        source = self.mapIdToProxy(sourceProxyId)
        view = self.getView(viewId)
        rep = simple.GetRepresentation(proxy=source, target=view)
        rep.Representation = "Surface"
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success", "representation": "Surface"}

    @exportRpc("volume.opacity.set")
    def setVolumeOpacity(self, arrayName: str, points: list):
        """
        Configure the opacity transfer function for volume rendering.

        Args:
            arrayName: Name of the scalar array (e.g., "U", "p", "T")
            points: Flat list [x1, y1, x2, y2, ...] where
                    x = scalar value, y = opacity (0.0 to 1.0)

        Example: points=[0, 0, 1, 0.2, 5, 1.0] means transparent at 0,
                 semi-opaque at 1, fully opaque at 5
        """
        volumeProperty = simple.GetOpacityTransferFunction(arrayName)
        volumeProperty.Points = points
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("volume.opacity.default")
    def setDefaultOpacity(self, arrayName: str):
        """Reset opacity to ParaView default (linear ramp)."""
        volumeProperty = simple.GetOpacityTransferFunction(arrayName)
        volumeProperty.Points = []
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}


class ParaViewWebAdvancedFilters(ParaViewWebProtocol):
    """Clip, Contour, and StreamTracer filters -- all ParaView 5.10 built-ins."""

    @exportRpc("clip.create")
    def createClip(self, sourceProxyId: int, normal: list, origin: list, viewId: int = -1):
        """
        Create a Clip filter (half-space cut).

        Args:
            sourceProxyId: Proxy ID of the input source/reader
            normal: [nx, ny, nz] -- plane normal direction
            origin: [ox, oy, oz] -- point the plane passes through
        """
        source = self.mapIdToProxy(sourceProxyId)
        clip = simple.Clip(Input=source, ClipType="Plane")
        clip.ClipType.Normal = normal
        clip.ClipType.Origin = origin
        simple.Show(clip, self.getView(viewId))
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success", "proxyId": int(clip.GetGlobalIDAsString())}

    @exportRpc("clip.delete")
    def deleteClip(self, proxyId: int):
        """Delete a clip proxy by ID."""
        proxy = self.mapIdToProxy(proxyId)
        if proxy:
            simple.Delete(proxy)
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("clip.update")
    def updateClip(self, proxyId: int, normal: list = None, origin: list = None):
        """Update an existing clip's plane parameters."""
        proxy = self.mapIdToProxy(proxyId)
        if proxy is None:
            return {"result": "error", "message": "Proxy not found"}
        if normal is not None:
            proxy.ClipType.Normal = normal
        if origin is not None:
            proxy.ClipType.Origin = origin
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("contour.create")
    def createContour(self, sourceProxyId: int, arrayName: str, isovalues: list, viewId: int = -1):
        """
        Create an iso-surface Contour filter.

        Args:
            sourceProxyId: Proxy ID of the input source
            arrayName: Scalar array name (e.g., "U", "p", "T")
            isovalues: List of scalar values at which to draw surfaces
        """
        source = self.mapIdToProxy(sourceProxyId)
        contour = simple.Contour(Input=source)
        contour.ContourBy = ["POINTS", arrayName]
        contour.Isosurfaces = isovalues
        simple.Show(contour, self.getView(viewId))
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success", "proxyId": int(contour.GetGlobalIDAsString())}

    @exportRpc("contour.delete")
    def deleteContour(self, proxyId: int):
        proxy = self.mapIdToProxy(proxyId)
        if proxy:
            simple.Delete(proxy)
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("contour.update")
    def updateContour(self, proxyId: int, isovalues: list = None):
        """Update an existing contour's iso-values."""
        proxy = self.mapIdToProxy(proxyId)
        if proxy is None:
            return {"result": "error", "message": "Proxy not found"}
        if isovalues is not None:
            proxy.Isosurfaces = isovalues
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}

    @exportRpc("streamtracer.create")
    def createStreamTracer(self, sourceProxyId: int, seedType: str = "maskingRegion", viewId: int = -1):
        """
        Create a StreamTracer filter (particle traces along velocity field).

        Args:
            sourceProxyId: Proxy ID of the input source
            seedType: "maskingRegion" (seeds throughout the volume) or
                      "point" (single point -- use with SeedPoint)
        """
        source = self.mapIdToProxy(sourceProxyId)
        tracer = simple.StreamTracer(Input=source, SeedType=seedType)
        tracer.Vectors = ["POINTS", "U"]  # Default: use velocity field
        tracer.MaximumTrackLength = 100
        tracer.ComputeVorticity = 1
        simple.Show(tracer, self.getView(viewId))
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success", "proxyId": int(tracer.GetGlobalIDAsString())}

    @exportRpc("streamtracer.delete")
    def deleteStreamTracer(self, proxyId: int):
        proxy = self.mapIdToProxy(proxyId)
        if proxy:
            simple.Delete(proxy)
        simple.Render()
        self.getApplication().InvokeEvent("UpdateEvent")
        return {"result": "success"}
```

---

### 2. Screenshot Export

**Goal:** Export current viewport as PNG download.

**No new libraries.** The built-in `viewport.image.render` RPC (ParaViewWebViewPortImageDelivery) delivers screenshots as base64 PNG. No custom server code needed.

**Frontend protocol message (add to `paraviewProtocol.ts`):**

```typescript
/**
 * Create a protocol message to capture a viewport screenshot.
 * The response contains a base64 PNG string to be decoded by the frontend.
 *
 * @param quality - JPEG-like quality 1-100 (85 recommended for balance)
 * @param viewId  - View proxy ID (-1 = active view)
 */
export function createScreenshotMessage(quality = 85, viewId = -1): object {
  return {
    id: "pv-screenshot",
    method: "viewport.image.render",
    params: { view: viewId, quality, ratio: 1 }
  };
}

/**
 * Parse base64 PNG from a viewport.image.render response.
 *
 * @param response - The JSON-RPC response from the ParaView Web server
 * @returns base64 PNG string, or null if not present
 */
export function parseScreenshotResponse(
  response: { id?: string; result?: { image?: string } }
): string | null {
  return response?.result?.image ?? null;
}

/**
 * Trigger a browser download of a base64 PNG screenshot.
 *
 * @param base64Image - base64 PNG string from parseScreenshotResponse
 * @param filename    - Desired filename (without extension)
 */
export function downloadScreenshot(base64Image: string, filename = "paraview-screenshot"): void {
  const binStr = atob(base64Image);
  const bytes = new Uint8Array(binStr.length);
  for (let i = 0; i < binStr.length; i++) {
    bytes[i] = binStr.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: "image/png" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.png`;
  a.click();
  URL.revokeObjectURL(url);
}
```

**JSON state export:** `pv.data.save` (built-in) writes data to a file path inside the container. Requires a new REST endpoint in `visualization.py` to proxy the file from container to client.

---

## Server Integration: How to Register Custom Protocols

The current launcher spawns the container with the standard `vtkmodules/web/launcher.py`. Custom protocol classes must be registered with the wslink server before it starts accepting connections.

**Recommended approach: Custom entrypoint script.**

The `paraview_web_launcher.py` should be extended to mount and import the custom protocols at startup. The approach:

1. Write `paraview_adv_protocols.py` on the host (part of the api_server source)
2. Mount it into the container at `/tmp/adv_protocols.py`
3. Add a custom entrypoint script that:
   ```python
   import sys
   sys.path.insert(0, "/tmp")
   from paraview_adv_protocols import ParaViewWebVolumeRendering, ParaViewWebAdvancedFilters
   # Register protocols with the application...
   ```

The cleanest integration is to modify `_build_launcher_config` in `paraview_web_launcher.py` to:

- Mount the custom protocol file as a volume: `-v {host_path}/paraview_adv_protocols.py:/tmp/adv_protocols.py:ro`
- Set the entrypoint to a custom launcher script that imports and registers the protocols before delegating to the standard launcher

**Launcher config change (in `_build_launcher_config`):**

```python
def _build_launcher_config(self, ...):
    config = {
        # ... existing fields ...
    }
    # No structural change to config needed -- custom protocols
    # are registered via Python import before the launcher starts
    return config

# _start_container changes:
# 1. Mount the custom protocols file as a volume
# 2. Prepend import to the command or use a custom entrypoint wrapper
```

---

## Frontend Changes (TypeScript)

**File: `dashboard/src/services/paraviewProtocol.ts`** -- add these functions:

| Function | Protocol Method | Notes |
|----------|----------------|-------|
| `createVolumeRepresentationMessage(sourceId)` | `volume.representation.create` | Switch to volume |
| `createSurfaceRepresentationMessage(sourceId)` | `volume.representation.surface` | Switch back to surface |
| `createVolumeOpacityMessage(arrayName, points)` | `volume.opacity.set` | Configure opacity TF |
| `createClipMessage(sourceId, axis, origin)` | `clip.create` | Clip filter |
| `createClipDeleteMessage(proxyId)` | `clip.delete` | Remove clip |
| `createClipUpdateMessage(proxyId, normal, origin)` | `clip.update` | Update clip plane |
| `createContourMessage(sourceId, arrayName, isovalues)` | `contour.create` | Iso-surface filter |
| `createContourDeleteMessage(proxyId)` | `contour.delete` | Remove contour |
| `createContourUpdateMessage(proxyId, isovalues)` | `contour.update` | Update iso-values |
| `createStreamTracerMessage(sourceId, seedType)` | `streamtracer.create` | Particle traces |
| `createStreamTracerDeleteMessage(proxyId)` | `streamtracer.delete` | Remove tracer |
| `createScreenshotMessage(quality, viewId)` | `viewport.image.render` | Capture PNG |
| `parseScreenshotResponse(response)` | -- | Extract base64 |
| `downloadScreenshot(base64, filename)` | -- | Trigger download |

---

## What NOT to Add

| Anti-pattern | Why Avoid | Correct Approach |
|--------------|-----------|----------------|
| `trame` or any new Python framework | Explicitly deferred to v1.6.0; current ParaView Web approach is working | Stay with custom protocol subclass pattern |
| `@kitware/vtk.js` npm package | All rendering is server-side; no client-side VTK needed | Keep raw WebSocket protocol layer |
| New Docker image | `openfoam/openfoam10-paraview510` is current and ships vtkGPUVolumeRayCastMapper | No image change needed |
| `pv.proxy.manager.create` for filters | Too low-level; requires property XML knowledge; custom named methods are cleaner and type-safe | Use `clip.create`, `contour.create`, etc. |
| `vtkExternalPCAFilter` or third-party VTK filters | Outside CFD use case scope | Stick to built-in Clip/Contour/StreamTracer |
| Screenshot via container file path + HTTP | `viewport.image.render` base64 is simpler and works over existing WS connection | Use `viewport.image.render` |
| Change frontend framework | React 19 is current; no reason to change | Add UI controls within existing ParaViewViewer.tsx |

---

## Summary: Zero New Dependencies

| Category | Already Available | Work Required |
|----------|-------------------|----------------|
| Volume rendering | `vtkGPUVolumeRayCastMapper` in image | Custom protocol handler |
| Clip filter | Built-in `Clip()` | Custom protocol + update + delete |
| Contour filter | Built-in `Contour()` | Custom protocol + update + delete |
| Streamlines | Built-in `StreamTracer()` | Custom protocol + delete |
| Screenshot PNG | `viewport.image.render` | Frontend base64 decode + download only |
| JSON state export | `pv.data.save` | REST endpoint for file proxy |
| NPM packages | None | TypeScript only |
| Python packages | None | Only custom protocol Python file |
| Docker image | `openfoam/openfoam10-paraview510` | No change -- mount custom protocols as volume |

**Implementation complexity:** LOW. The server-side is ~150 lines of Python (mostly boilerplate `simple.FilterName()` calls). The frontend is ~80 lines of TypeScript protocol message builders. The main complexity is in the container integration (mounting the Python file and registering protocols at startup).

---

## Sources

| Source | URL | Confidence | Verifies |
|--------|-----|------------|---------|
| ParaView 5.10.0 protocols.py | `https://raw.githubusercontent.com/Kitware/ParaView/v5.10.0/Web/Python/paraview/web/protocols.py` | HIGH | Full `@exportRpc` method list |
| ParaViewWeb API | `https://raw.githubusercontent.com/Kitware/paraviewweb/master/src/IO/WebSocket/ParaViewWebClient/api.md` | HIGH | Available protocol names |
| ParaView Web protocols | GitHub API: `repos/Kitware/ParaView/contents/Web/Python/paraview/web/protocols.py?ref=v5.10.0` | HIGH | All RPC methods confirmed |
| Existing implementation | `paraviewProtocol.ts`, `ParaViewViewer.tsx`, `paraview_web_launcher.py` | HIGH | Message patterns confirmed |
| openfoam/openfoam10-paraview510 | Docker Hub | HIGH | Contains ParaView 5.10.1 with VTK GPU volume rendering |
