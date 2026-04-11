# Domain Pitfalls: ParaView Web Advanced Visualization (v1.5.0)

**Domain:** ParaView Web -- Volume Rendering, Advanced Filters (Clip/Contour/Streamlines), Screenshot Export
**Project:** AI-CFD Knowledge Harness
**Researched:** 2026-04-11
**Confidence:** MEDIUM-HIGH (verified against existing codebase patterns, Kitware docs, ParaView source)

---

## Critical Pitfalls

Mistakes that cause rewrites, crashes, or integration breakage for the specific v1.5.0 features.

---

### Pitfall 1: Volume Rendering GPU Memory Exhaustion on Large CFD Datasets

**What goes wrong:** Volume rendering crashes the Docker container's VTK render process or causes OOM kills, leaving the viewer in a broken state.

**Why it happens:**
- `vtkGPUVolumeRayCastMapper` requires loading the entire 3D scalar field into GPU memory
- CFD datasets (e.g., 5M+ cell engine simulation) easily exceed typical GPU memory limits in a containerized environment
- VTK falls back to `vtkSoftwareVolumeRayCastMapper` silently (no error thrown), causing 10-100x performance degradation that manifests as a frozen UI
- The `--platform linux/amd64` detached container has no direct GPU access on Apple Silicon (already acknowledged in PROJECT.md); even on Linux with GPU, container memory limits are set at container start, not dynamically

**Consequences:**
- Container OOM kill: ParaView Web session dies, user loses visualization state
- Silent software fallback: viewer freezes during interaction, user blames "bug" not hardware
- Memory growth: repeated volume on/off toggles leak GPU memory references, eventually crashing

**How to avoid:**
```python
# In paraview_adv_protocols.py -- check data size before enabling volume rendering
@exportRpc("volume.representation.create")
def createVolumeRepresentation(self, sourceProxyId: int, viewId: int = -1):
    source = self.mapIdToProxy(sourceProxyId)
    dataInfo = servermanager.PropertyIterator(source)
    # Get approximate memory footprint
    wholeDataInfo = source.GetDataInformation()
    numCells = wholeDataInfo.GetNumberOfCells()
    numPoints = wholeDataInfo.GetNumberOfPoints()
    # Warn if > 2M cells (heuristic for ~500MB GPU memory)
    if numCells > 2_000_000:
        # Fall back to surface representation instead of crashing
        # Or set lower resolution for volume
        pass
    # ... rest of volume creation
```

```python
# Set memory limits on the container at start (in _start_container):
"--memory", "4g",          # Hard limit
"--memory-reservation", "2g",  # Soft limit
```

```typescript
// Frontend: implement progressive loading UX
// Show "Preparing volume..." with progress, then reveal
// Detect if volume rendering is taking > 10s and offer fallback
```

**Warning signs:**
- Container logs: `Killed` (dmesg OOM)
- Container logs: `Abort` during `vtkGPUVolumeRayCastMapper::Render()`
- Frontend: viewer unresponsive for > 5s after enabling volume
- `nvidia-smi` inside container shows GPU memory at 95%+

**Phase to address:** Volume Rendering implementation phase -- must include memory estimation before enabling volume, container memory limits at launch, and software fallback path.

---

### Pitfall 2: Custom Protocol File Not Registered Before First WebSocket Connection

**What goes wrong:** User connects to the ParaView Web session but the custom protocol methods (`volume.representation.create`, `clip.create`, etc.) return "method not found" errors.

**Why it happens:**
- The current `paraview_web_launcher.py` starts the container with `vtkmodules/web/launcher.py` directly
- The custom protocol Python file is mounted at `/tmp/adv_protocols.py` but is never imported or registered with the wslink server
- wslink's `register` decorator adds methods to a global servermanager registry that must be populated before the server starts accepting connections
- If the import happens too late (after the first client connects), the protocol methods are not available for that session

**Consequences:**
- All volume rendering and filter buttons fail silently or return protocol errors
- Works on second try only if the session restarts (which it doesn't)
- Debugging is hard because the container starts successfully and the WebSocket handshake completes

**How to avoid:**
```python
# The custom entrypoint MUST import and register protocols BEFORE
# the launcher starts the wslink server.
# This means a custom entrypoint wrapper script, NOT just mounting a .py file.

# /tmp/paraview_entrypoint.sh (mounted and set as entrypoint):
#!/bin/bash
set -e
cd /tmp

# Pre-import and register all custom protocols
pvpython -c "
import sys
sys.path.insert(0, '/tmp')
from paraview_adv_protocols import ParaViewWebVolumeRendering, ParaViewWebAdvancedFilters
# Import registers @exportRpc decorators with wslink
print('Custom protocols registered')
"

# Now run the standard launcher (which picks up the registered methods)
exec pvpython lib/site-packages/vtkmodules/web/launcher.py /tmp/launcher_config.json
```

```python
# In _start_container, change entrypoint:
"--entrypoint", "/tmp/paraview_entrypoint.sh",  # NOT pvpython directly
```

**Verification test:** After container starts, connect a test WebSocket client and call `volume.representation.create` -- it must respond within 100ms with a valid result or `{"result": {"code": 1, "message": "..."}}`, NOT a transport-level error.

**Warning signs:**
- Frontend console: `RPC method not found: volume.representation.create`
- Container logs: no Python import of `paraview_adv_protocols` at startup
- The `/tmp/adv_protocols.py` file exists inside the container but is never executed

**Phase to address:** Container integration phase for advanced protocols -- the custom protocol registration must be verified at container startup, not at first use.

---

### Pitfall 3: Apple Silicon `--platform linux/amd64` Volume Rendering Falls Back to Software

**What goes wrong:** Volume rendering appears to work but is extremely slow (1-5 FPS) or crashes because it runs via Mesa software rasterization on Apple Silicon.

**Why it happens:**
- The PROJECT.md explicitly notes `--platform linux/amd64` is required for Apple Silicon
- However, `--platform linux/amd64` on Apple Silicon (M1/M2/M3) uses Rosetta 2 x86 emulation AND the Docker virtiofs/guestfs graphics stack cannot access the Apple GPU
- Volume rendering via `vtkGPUVolumeRayCastMapper` in this configuration typically uses `vtkOpenGLGPUVolumeRayCastMapper` which tries to use GPU but fails to initialize, falling back to CPU rendering
- This fallback is silent -- there is no error thrown, only a performance degradation that makes the UI unusable

**Consequences:**
- Volume rendering of any non-trivial dataset freezes the UI during interaction
- Users on Apple Silicon Macs get a broken experience that works fine on Linuxamd64 servers
- Appears as a bug in the code rather than a platform limitation

**How to avoid:**
```python
# In paraview_adv_protocols.py -- detect GPU availability before enabling volume:
@exportRpc("volume.representation.create")
def createVolumeRepresentation(self, sourceProxyId: int, viewId: int = -1):
    # Check if we have real GPU support
    from vtkmodules.vtkRenderingOpenGL2 import *
    from paraview.vtk import vtkRenderingOpenGL2

    # If not on a real GPU, surface is the only reliable option
    # Detect software fallback by checking if GPU context is real
    # (This is hard to detect reliably, so be conservative)
    pass  # Fall through to normal path but log the limitation

# In paraview_web_launcher.py -- set explicit OpenGL flags:
"--env", "VTK_DEFAULT_SOFTWARE_RENDERING=0",
"--env", "DISPLAY=:0",
# AND ensure EGL is initialized
```

```typescript
// Frontend: detect software rendering and warn user
// Check renderer string for "llvmpipe" or "Software" which indicates no GPU
// Show a warning banner: "Volume rendering requires a server with GPU.
// Current server uses software rendering, which may be slow."
```

**Warning signs:**
- Container inside: `eglinfo | grep "EGL vendor"` returns "Mesa Project" not "NVIDIA"
- `viewport.image.render` takes > 10s to return (software rendering is slow)
- Frontend detects "SwiftShader" or "Software" in WebGL renderer string

**Phase to address:** Volume Rendering implementation phase -- must include GPU capability detection, explicit EGL vendor verification at startup, and user-facing warning on software fallback.

---

### Pitfall 4: Screenshot `viewport.image.render` Blocks the WebSocket Event Loop

**What goes wrong:** Calling `viewport.image.render` freezes the entire viewer for the duration of the render, sometimes 10-30 seconds on large datasets.

**Why it happens:**
- `viewport.image.render` is a synchronous RPC call -- it blocks the wslink server event loop until the render completes and the base64 image is sent over the wire
- A full-resolution screenshot of a volume-rendered CFD model at 1920x1080 can be 5-10MB base64-encoded
- During this time, no other protocol messages (camera updates, filter changes) can be processed
- The user sees a completely frozen UI with no feedback

**Consequences:**
- User clicks "Screenshot" and UI freezes -- user may click again, triggering another blocking call
- Multiple rapid clicks queue up multiple blocking renders
- If the render takes too long, the WebSocket may time out (60s default) and the session appears dead

**How to avoid:**
```python
# Server-side: use a background thread for screenshot rendering
@exportRpc("viewport.image.render")
def render_viewport(self, viewId: int = -1, quality: int = 85, **kwargs):
    import threading
    def render_in_background():
        # VTK render + base64 encode happens here
        # Result is pushed via self.getApplication().InvokeEvent("UpdateEvent")
        pass
    thread = threading.Thread(target=render_in_background)
    thread.start()
    return {"status": "rendering"}  # Immediate return, non-blocking
```

```typescript
// Frontend: show loading state and disable button during capture
async function takeScreenshot() {
  setIsCapturing(true);
  disableButton();
  try {
    await sendProtocolMessage(createScreenshotMessage(quality));
    // Show brief "Capturing..." state
  } finally {
    setIsCapturing(false);
    enableButton();
  }
}
```

**Phase to address:** Screenshot Export phase -- must implement async capture UX and debounce/throttle screenshot requests.

---

## Moderate Pitfalls

Issues causing significant debugging but with clear workarounds.

---

### Pitfall 5: Clip/Contour Filter Proxy IDs Not Tracked Across Server Restarts

**What goes wrong:** User creates a clip, then restarts the visualization session. The clip proxy ID from the old session is still stored in frontend state, causing `clip.update` to operate on the wrong (or non-existent) proxy.

**Why it happens:**
- Proxy IDs are assigned by the VTK session on the server and are only valid within that session
- When the container restarts (idle timeout, crash), all proxy IDs become invalid
- The frontend may have a list of "active" filters in React state that still holds the old proxy IDs

**How to avoid:**
```typescript
// Frontend: track filter state with session ID binding
interface ActiveFilter {
  sessionId: string;  // Must match current session
  proxyId: number;
  type: 'clip' | 'contour' | 'streamtracer';
}

// On session change/restart, clear all active filter state
function onSessionChange(newSessionId: string) {
  setActiveFilters([]);
}
```

**Warning signs:**
- `clip.update` returns `{"result": "error", "message": "Proxy not found"}`
- Filter controls in UI stop responding after a session reconnect
- Multiple clips appear when only one is expected (ID collision across sessions)

**Phase to address:** Advanced Filters phase -- must handle session lifecycle for filter state.

---

### Pitfall 6: Volume Opacity Transfer Function Points Format Mismatch

**What goes wrong:** User sets an opacity transfer function but the rendered volume appears fully opaque or fully transparent regardless of the scalar values.

**Why it happens:**
- `volumeProperty.Points` expects a flat list `[x1, y1, x2, y2, ...]` where x is scalar value and y is opacity (0-1)
- If the frontend sends `[[x1,y1], [x2,y2]]` (nested arrays), VTK silently fails to apply the transfer function
- If the scalar range of the CFD field doesn't match the x-values in the transfer function, the result looks wrong
- `simple.GetOpacityTransferFunction(arrayName).Points` format documentation is sparse

**How to avoid:**
```typescript
// Frontend: always send flat list
function createVolumeOpacityMessage(
  arrayName: string,
  points: Array<[number, number]>  // [[x,y], [x,y], ...]
): object {
  // Flatten to 1D array before sending
  const flatPoints: number[] = points.flat();
  return {
    id: "pv-volume-opacity",
    method: "volume.opacity.set",
    params: { arrayName, points: flatPoints }
  };
}
```

```python
# Server-side: validate points format before applying
@exportRpc("volume.opacity.set")
def setVolumeOpacity(self, arrayName: str, points: list):
    if not isinstance(points, list):
        return {"result": "error", "message": "points must be a flat list"}
    if len(points) % 2 != 0:
        return {"result": "error", "message": "points must be flat [x1,y1,x2,y2,...]"}
    # Validate x values are in ascending order
    x_vals = points[::2]
    if x_vals != sorted(x_vals):
        return {"result": "error", "message": "x values must be strictly increasing"}
```

**Warning signs:**
- Volume appears fully opaque regardless of opacity function settings
- `volume.opacity.set` returns success but rendering doesn't change
- VTK warning in container logs about "Transfer function points out of range"

**Phase to address:** Volume Rendering implementation phase -- validate input format server-side.

---

### Pitfall 7: StreamTracer Seed Type Mismatch with CFD Data Geometry

**What goes wrong:** Streamlines appear broken, incomplete, or crash when the seed type does not match the actual CFD mesh geometry.

**Why it happens:**
- `StreamTracer` with `SeedType="maskingRegion"` requires the input to have a valid "masking region" (a common issue with clipped/blockMesh-generated geometry)
- `StreamTracer` with `SeedType="point"` needs a valid seed point that exists within the domain
- Many OpenFOAM cases (especially those from blockMesh) have irregular geometry where the default seed regions fall outside the fluid domain
- The `MaximumTrackLength` default of 100 may be too small for large domains or too large for small ones, causing truncated or runaway traces

**How to avoid:**
```python
@exportRpc("streamtracer.create")
def createStreamTracer(self, sourceProxyId: int, seedType: str = "maskingRegion",
                        seedPoint: list = None, viewId: int = -1):
    source = self.mapIdToProxy(sourceProxyId)
    tracer = simple.StreamTracer(Input=source, SeedType=seedType)
    tracer.Vectors = ["POINTS", "U"]  # Default to velocity field

    # Validate that the seed point is within the domain bounds
    if seedPoint:
        bounds = source.GetDataInformation().GetBounds()
        if not (bounds[0] <= seedPoint[0] <= bounds[1] and
                bounds[2] <= seedPoint[1] <= bounds[3] and
                bounds[4] <= seedPoint[2] <= bounds[5]):
            return {"result": "error",
                    "message": f"Seed point {seedPoint} outside domain bounds {bounds}"}

    # Set reasonable defaults but allow override
    tracer.MaximumTrackLength = 200  # Increased default for CFD
    tracer.IntegrationStepUnit = "CellLength"  # More stable than PointLength
    tracer.MaximumSteps = 1000
    # ... show and render
```

**Warning signs:**
- Streamlines appear to stop at domain boundaries prematurely
- `streamtracer.create` returns success but no streamlines are visible
- VTK warning about "Seed point outside data bounds"

**Phase to address:** Advanced Filters (Streamlines) phase -- validate seed geometry against mesh bounds before creating tracer.

---

### Pitfall 8: Container Memory Grows Unboundedly with Filter Creation/Deletion Cycles

**What goes wrong:** Each clip/contour/streamline creation allocates VTK objects. Deletion via `simple.Delete()` does not immediately free GPU memory. Over time, repeated filter creation cycles exhaust GPU or system memory.

**Why it happens:**
- VTK's reference counting means objects are not freed immediately when `simple.Delete()` is called
- GPU resources (textures, buffers for each filter's representation) persist until the next `Render()`
- On Apple Silicon with `--platform linux/amd64`, GPU memory management is especially fragile
- Without an explicit `simple.Render()` after delete, the memory is not reclaimed

**How to avoid:**
```python
@exportRpc("clip.delete")
def deleteClip(self, proxyId: int):
    proxy = self.mapIdToProxy(proxyId)
    if proxy:
        simple.Delete(proxy)
    # CRITICAL: explicitly render to free GPU resources
    simple.Render()
    self.getApplication().InvokeEvent("UpdateEvent")
    # Force garbage collection periodically
    import gc
    gc.collect()
```

```typescript
// Frontend: limit number of simultaneous filters
const MAX_ACTIVE_FILTERS = 5;
function canCreateNewFilter(): boolean {
  return activeFilters.length < MAX_ACTIVE_FILTERS;
}
```

**Warning signs:**
- Container memory steadily increases with each filter operation
- After 10+ clip/contour cycles, container becomes sluggish
- `docker stats` shows increasing memory usage that never stabilizes

**Phase to address:** Advanced Filters phase -- must include memory management (gc.collect, render after delete) and filter count limits.

---

## Minor Pitfalls

Easily worked-around issues.

---

### Pitfall 9: Screenshot Resolution Rounds Down Unexpectedly

**What goes wrong:** User requests 1920x1080 screenshot but gets a smaller image.

**Why it happens:**
- `viewport.image.render` uses the current view size, not an arbitrary requested size
- The `ratio: 1` parameter multiplies the current size but if the view is smaller than expected, the output is smaller
- The render quality is also tied to the current viewport's on-screen size

**How to avoid:**
```python
# Before calling viewport.image.render, resize the view programmatically:
@exportRpc("screenshot.capture")
def captureScreenshot(self, viewId: int = -1, width: int = 1920, height: int = 1080,
                       quality: int = 90):
    view = self.getView(viewId)
    # Save current size
    orig_width, orig_height = view.ViewSize
    # Force render at requested size
    view.ViewSize = [width, height]
    simple.Render()
    # Capture...
    # Restore original size
    view.ViewSize = orig_width, orig_height
    simple.Render()
```

**Phase to address:** Screenshot Export phase.

---

### Pitfall 10: Color Lookup Table Reset Wipes User's Custom Volume Opacity

**What goes wrong:** User carefully adjusts opacity transfer function for volume rendering, then switches the scalar field. The `UpdateLUT` protocol resets the opacity function to default, losing the user's work.

**Why it happens:**
- `UpdateLUT` operates on the lookup table but does not preserve the separate opacity transfer function
- The opacity transfer function is stored per-array and switching fields loads the new field's opacity defaults
- The frontend may not track opacity settings per field

**How to avoid:**
```typescript
// Frontend: save opacity state per field before switching
const opacityState: Map<string, number[]> = new Map();

function onFieldChange(newField: string) {
  // Save current opacity
  if (currentField) {
    opacityState.set(currentField, currentOpacityPoints);
  }
  // Switch field
  sendProtocolMessage(createFieldDisplayMessage(newField));
  // Restore opacity if previously set
  const saved = opacityState.get(newField);
  if (saved) {
    sendProtocolMessage(createVolumeOpacityMessage(newField, saved));
  }
}
```

**Phase to address:** Volume Rendering phase -- handle opacity state per field.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode `MaximumTrackLength=100` for streamlines | Works for most cases | CFD domains vary widely; wrong default makes streamlines useless | Never -- make it configurable |
| Skip memory check before volume rendering | Faster to ship | OOM crash in production | Only in MVP with explicit "may crash" warning |
| Reuse proxy IDs in filter delete/recreate | Simpler frontend state | ID collision across session restart | Only with session ID binding |
| Mount custom protocols as `.py` file without entrypoint wrapper | Works locally in dev | Silent registration failure in prod | Only during initial development |
| `simple.Render()` after every filter operation | Simpler code | Performance hit with many filters | Never in production -- batch renders |

---

## Integration Gotchas

Common mistakes when connecting the new features to the existing infrastructure.

| Integration Point | Common Mistake | Correct Approach |
|------------------|----------------|------------------|
| Container startup | Mounting `.py` file but not importing it | Custom entrypoint that imports before launcher starts |
| Protocol registration | Assuming `@exportRpc` auto-registers globally | Must import module to trigger decorator |
| WebSocket message | Sending nested array `[[x,y]]` instead of flat `[x,y]` | Always flatten opacity points |
| Filter state | Storing proxyId without sessionId | Include sessionId for cross-session validity |
| GPU detection | Checking if container starts, not if GPU is used | Explicitly check `EGL vendor string` or use `eglinfo` |
| Memory management | `simple.Delete()` without `simple.Render()` | Always render after delete to free GPU memory |
| Screenshot | Blocking `viewport.image.render` call | Async with loading state and debounce |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Volume rendering without memory check | OOM kill or frozen UI | Pre-check cell count, set container memory limits | Datasets > 2M cells |
| Synchronous screenshot | UI freeze > 5s | Background thread + progressive loading | Large viewports |
| Many simultaneous filters without GC | Memory leak, degraded performance | `gc.collect()` after delete, limit filter count | > 5 filter cycles |
| Software fallback volume | 1-5 FPS interaction | EGL vendor check at startup, warn user | Apple Silicon + amd64 container |
| Large base64 screenshot over WS | WS frame drops, timeout | Compress before send, chunk if needed | Viewport > 4K |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| No proxy ID validation | User could reference another user's filter via ID | Validate proxyId belongs to current session's sessionId |
| Arbitrary file write via screenshot path | Path traversal if screenshot path is user-controlled | Screenshot always goes to `/tmp`, proxied via REST endpoint |
| Unbounded filter count | DoS via creating thousands of filters | Enforce MAX_ACTIVE_FILTERS server-side |
| No auth on WebSocket connection | Unauthorized visualization access | AuthKey validation at WebSocket handshake (already implemented) |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Volume rendering silently uses software fallback | User thinks "buggy software", doesn't know about hardware limitation | Show explicit banner when GPU not available |
| Clip/contour dialog with no feedback | User clicks "Apply" and nothing happens | Show loading state + result/error feedback |
| Screenshot button with no loading state | User clicks, UI freezes, clicks again | Disable + spinner during capture |
| Streamlines fail silently with irregular mesh | User sees nothing, doesn't know why | Show explicit error with bounds diagnostic |
| Opacity function lost on field switch | User carefully sets opacity, loses it | Persist opacity per field in React state |

---

## "Looks Done But Isn't" Checklist

Verify these during implementation, not just during demo:

- [ ] **Volume Rendering:** Container starts with EGL GPU (not Mesa) -- verify with `eglinfo | grep "EGL vendor"` in startup logs
- [ ] **Volume Rendering:** Memory check prevents OOM -- test with > 5M cell dataset, verify container survives
- [ ] **Volume Rendering:** Opacity function persists correctly -- verify flat array format with multiple points
- [ ] **Advanced Filters:** Custom entrypoint imports protocols BEFORE launcher starts -- verify in container logs
- [ ] **Advanced Filters:** Filter delete actually frees memory -- verify with `docker stats` after 5 create/delete cycles
- [ ] **Advanced Filters:** Proxy IDs are invalid after session restart -- verify with reconnect test
- [ ] **Screenshot:** Does not block UI -- verify UI remains responsive during capture (send camera move while capturing)
- [ ] **Screenshot:** Resolution matches request -- verify output dimensions against requested dimensions
- [ ] **Protocol Registration:** All new methods respond to `RPC.list` -- verify `volume.representation.create` and others appear in protocol list
- [ ] **Apple Silicon:** Volume rendering shows warning when using software fallback -- verify banner appears on M1/M2/M3

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| OOM during volume rendering | MEDIUM | Container auto-restarts; user reconnects; implement session state recovery |
| Protocol not registered | LOW | Restart container with fixed entrypoint; no data loss |
| Filter state lost on restart | MEDIUM | Frontend detects session change; prompts user to re-apply filters |
| Memory leak from filter cycles | MEDIUM | Container restart clears GPU memory; periodic `docker exec` gc.collect |
| Software fallback on Apple Silicon | HIGH (no fix possible) | Detect at startup; show user warning; disable volume rendering gracefully |

---

## Pitfall-to-Phase Mapping

How the v1.5.0 roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| GPU memory exhaustion (Pitfall 1) | Volume Rendering (VR-01) -- memory estimation + container limits | Test with 5M+ cell case; container must survive |
| Protocol registration timing (Pitfall 2) | Container Integration (CI-01) -- custom entrypoint | Container logs must show import before "Starting factory" |
| Apple Silicon software fallback (Pitfall 3) | Volume Rendering (VR-01) -- EGL detection + warning | Verify `EGL vendor: NVIDIA` in container; banner on fallback |
| Screenshot blocks WS loop (Pitfall 4) | Screenshot Export (SS-01) -- async capture | UI remains interactive during capture |
| Filter proxy ID reset (Pitfall 5) | Advanced Filters (AF-01) -- session-bound state | Reconnect test: filters cleared on session change |
| Opacity TF format mismatch (Pitfall 6) | Volume Rendering (VR-02) -- server-side validation | Unit test with malformed input returns error |
| StreamTracer seed mismatch (Pitfall 7) | Advanced Filters (AF-02) -- bounds validation | Test with blockMesh case; validate error returned |
| Memory growth from filter cycles (Pitfall 8) | Advanced Filters (AF-01) -- gc + render after delete | `docker stats` memory stable after 10 cycles |
| Screenshot resolution mismatch (Pitfall 9) | Screenshot Export (SS-01) -- programmatic resize | Verify output PNG dimensions |
| Opacity lost on field switch (Pitfall 10) | Volume Rendering (VR-02) -- per-field opacity state | Switch field twice; opacity preserved |

---

## Sources

| Source | URL | Confidence | Verifies |
|--------|-----|------------|---------|
| Kitware ParaView Web GitHub - protocols.py | `https://raw.githubusercontent.com/Kitware/ParaView/v5.10.0/Web/Python/paraview/web/protocols.py` | HIGH | Protocol registration pattern |
| Kitware ParaView Web GitHub - viewport.py | `https://raw.githubusercontent.com/Kitware/ParaView/v5.10.0/Web/Python/paraview/web/viewport.py` | HIGH | Screenshot protocol implementation |
| VTK GPU Volume Ray Cast Mapper docs | `https://vtk.org/doc/nightly/html/classvtkGPUVolumeRayCastMapper.html` | HIGH | Memory behavior |
| Existing paraview_web_launcher.py | `api_server/services/paraview_web_launcher.py` | HIGH | Container integration pattern |
| Existing paraviewProtocol.ts | `dashboard/src/services/paraviewProtocol.ts` | HIGH | Protocol message patterns |
| Existing PITFALLS.md | `.planning/research/PITFALLS.md` (v1.4.0) | HIGH | Prior pitfalls context |
| openfoam/openfoam10-paraview510 | Docker Hub | HIGH | Image capabilities |
| Kitware Discussions - AMD GPU Docker | Community | MEDIUM | Apple Silicon + amd64 limitations |

---

## Research Gaps

- Specific memory thresholds for `vtkGPUVolumeRayCastMapper` with CFD data (tested only up to ~2M cells in literature; beyond is unknown)
- Whether `vtkOpenGLGPUVolumeRayCastMapper` actually detects software fallback gracefully on Apple Silicon Rosetta2
- Exact format of opacity transfer function `Points` property in ParaView 5.10.1 (ParaView docs are sparse)
- Whether wslink `viewport.image.render` can be made truly async via event-driven push rather than blocking RPC
