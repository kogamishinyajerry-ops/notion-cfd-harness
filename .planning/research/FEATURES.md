# Feature Research — v1.5.0 Advanced Visualization

**Domain:** ParaView Web advanced visualization features (Volume Rendering, Clip/Contour/Streamlines, Screenshot Export)
**Project:** AI-CFD Knowledge Harness v1.5.0
**Researched:** 2026-04-11
**Confidence:** HIGH (protocol patterns verified against existing codebase; features confirmed in ParaView 5.10.0 source and openfoam/openfoam10-paraview510 Docker image)

---

## 1. Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in any professional CFD visualization tool. Missing these = product feels broken or incomplete for advanced use cases.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Volume Rendering** | 3D scalar fields (density, temperature, velocity magnitude) cannot be fully understood from 2D slices alone | MEDIUM | Requires GPU in container (`--gpus all` or Mesa fallback); existing ParaView Web session | `vtkGPUVolumeRayCastMapper` is in the Docker image; enabled by `rep.Representation = "Volume"` |
| **Clip Filter** | Cutting a mesh to see internal structure is a fundamental CFD operation | LOW | Existing reader/proxy infrastructure | Half-space cut via plane equation (normal + origin); ParaView built-in `Clip()` filter |
| **Contour Filter** | Iso-surfaces at specific scalar values are standard for understanding flow features | LOW | Existing scalar field selection | Iso-surface extraction; ParaView built-in `Contour()` filter |
| **Streamlines / StreamTracer** | Visualizing flow direction and velocity paths is core to CFD | MEDIUM | Requires vector field (velocity `U`); seed type configuration | Particle traces along velocity vectors; ParaView built-in `StreamTracer()` |
| **Screenshot Export** | Users need to include visualizations in reports and presentations | LOW | Built-in `viewport.image.render` RPC | Base64 PNG over WebSocket; no new libraries needed |

### Differentiators (Competitive Advantage)

Features that set the product apart from basic viewers and justify the engineering investment.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **Opacity Transfer Function Editor** | Default linear opacity is often suboptimal; letting users tune opacity for specific scalar ranges is a professional feature | MEDIUM | Volume Rendering | Custom protocol `volume.opacity.set` with control point editor UI; high user value for CFD analysis |
| **Filter Parameter Updates (live)** | Users want to adjust clip plane or contour values without recreating the filter | LOW | Clip/Contour filters already built | `clip.update` and `contour.update` protocol methods allow real-time parameter changes |
| **Multi-filter Composition** | Combining volume + clip + streamlines in a single view enables rich analysis | MEDIUM | All three filter types + UI panel | Users can toggle each filter independently; clean composition of representations |
| **JSON State Export** | Archiving the exact visualization state (camera, filters, colors) enables reproducible analysis | MEDIUM | `pv.data.save` built-in + REST proxy | File written inside container; proxied to client via new REST endpoint |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems or are out of scope for v1.5.0.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|-------------|-----------------|-------------|
| **Real-time volume rendering during solver run** | "See results as they compute" | Requires time-step streaming architecture; adds complexity for marginal benefit (convergence monitoring is more useful) | Use existing MON-03/MON-04 convergence monitoring while solver runs; volume render after completion |
| **Multiple simultaneous volume rendered fields** | "Show temperature AND pressure at once" | ParaView volume rendering is per-source; compositing multiple volumes is complex and GPU-intensive | Use clip/contour to show different fields on different cross-sections; use side-by-side views (future) |
| **Interactive plane widget for clip (drag to move)** | "Move the clip plane by dragging" | Requires ParaView's interactive plane widget which has complex WebSocket state sync; exceeds v1.5.0 scope | Numeric input for origin (X/Y/Z sliders) is sufficient for most use cases |
| **Animated streamlines (time-varying)** | "See flow evolution over time" | Requires time-step looping + seed tracking; complex state management | Show streamlines at final time step; animate by stepping through time manually |
| **3D PDF / WebGL export** | "Embed interactive 3D in a PDF" | Requires additional libraries (vtk.js, export frameworks); not core to CFD report workflow | Screenshot PNG is sufficient for reports; consider Three.js export in v2.x |
| **Movie export (MP4/GIF)** | "Export an animation as MP4" | Requires ffmpeg inside container + encoding compute + file transfer; adds significant complexity | Screenshot sequence export + client-side GIF/video creation is a v2.x item |

---

## 2. Feature Dependencies

```
OpenFOAM Reader (existing v1.4.0)
    │
    ├──► [Volume Rendering] ──requires──► Scalar field selection (existing)
    │                                    └──requires──► Opacity transfer function (new)
    │
    ├──► [Clip Filter] ──requires──► Plane normal + origin parameters (new)
    │                       └─────► Delete clip (new)
    │
    ├──► [Contour Filter] ──requires──► Scalar array + isovalues (new)
    │                          └─────► Delete contour (new)
    │
    ├──► [StreamTracer] ──requires──► Vector field (velocity U) ──requires──► OpenFOAM Reader (existing)
    │                    └──requires──► Seed type configuration (new)
    │
    └──► [Screenshot Export] ──no additional deps──► Built-in viewport.image.render

[Multi-filter Composition] ──enhances──► Each individual filter (clip + contour + streamlines + volume)
```

### Dependency Notes

- **Volume Rendering requires scalar field selection:** The user must first select a scalar field (e.g., velocity magnitude, pressure) before volume rendering is meaningful. This is already implemented in v1.4.0 (PV-03 field selection).
- **Opacity transfer function requires volume rendering to be active:** The `volume.opacity.set` RPC modifies the transfer function for the currently volume-rendered source. If no volume representation is active, the RPC still succeeds but has no visible effect.
- **Clip/Contour/StreamTracer all require an existing reader proxy:** They take `sourceProxyId` as input. The delete/update operations require tracking proxy IDs returned at creation time.
- **StreamTracer requires velocity field (`U`):** Unlike clip/contour which work on any scalar, streamlines need a vector field. The protocol defaults to `["POINTS", "U"]` (velocity magnitude). If the case has different field names, the protocol would need extension.
- **Screenshot is orthogonal:** `viewport.image.render` works regardless of active filters or representation type. It captures whatever is currently displayed.

---

## 3. MVP Definition

### Launch With (v1.5.0 — this milestone)

Essential features to validate the advanced visualization concept.

- [ ] **Volume Rendering toggle** -- One-button switch between Surface and Volume representation. No opacity editing in v1.5.0 (defer to v1.5.x). Why: Core differentiator; GPU volume rendering is the main new capability.
- [ ] **Clip Filter (static plane)** -- Create a clip with X/Y/Z axis-aligned normal + numeric origin input. No interactive widget. Delete clip. Why: Fundamental CFD operation; straightforward protocol implementation.
- [ ] **Contour Filter (iso-surfaces)** -- Create iso-surfaces by selecting scalar field and entering one or more isovalues. Delete contour. Why: Standard post-processing feature; builds on existing field selection.
- [ ] **Streamlines (masking region seeds)** -- Create streamlines with default "masking region" (seeds throughout volume). Uses velocity field `U`. Delete streamlines. Why: Flow visualization core feature.
- [ ] **Screenshot Export (PNG download)** -- Capture current viewport as base64 PNG, decode in browser, trigger download. Why: Low cost, high value for reports.

### Add After Validation (v1.5.x — incremental)

Features to add once core is working and user feedback guides priorities.

- [ ] **Opacity Transfer Function Editor** -- Add control points to customize opacity curve. Trigger: User feedback requesting "can only see outer shell, need to look inside."
- [ ] **Clip plane parameter update** -- Sliders to adjust clip origin in real-time without deleting/recreating. Trigger: User workflow study showing repeated clip operations.
- [ ] **Contour value update** -- Adjust isovalues without deleting/recreating. Trigger: Same as above.
- [ ] **JSON state export** -- `pv.data.save` + REST endpoint proxying file from container. Trigger: User request for reproducible visualization state.

### Future Consideration (v2.x)

Features to defer until product-market fit is established.

- [ ] **Interactive clip plane widget (drag to move)** -- Requires ParaView interactive plane widget which is complex in WebSocket context.
- [ ] **Animated streamlines** -- Time-step looping for particle animation.
- [ ] **Multi-field volume rendering** -- Side-by-side or composited volume rendering for multiple scalar fields.
- [ ] **Movie export (MP4/GIF)** -- Server-side ffmpeg encoding of animation sequence.

---

## 4. Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Risk | Priority |
|---------|-----------|---------------------|------|----------|
| Volume Rendering toggle | HIGH | LOW | LOW | **P1** |
| Screenshot Export | HIGH | LOW | LOW | **P1** |
| Clip Filter (create/delete) | HIGH | LOW | LOW | **P1** |
| Contour Filter (create/delete) | MEDIUM | LOW | LOW | **P1** |
| Streamlines (create/delete) | MEDIUM | MEDIUM | MEDIUM | **P2** |
| Clip plane parameter update | MEDIUM | LOW | LOW | **P2** |
| Contour value update | MEDIUM | LOW | LOW | **P2** |
| Opacity transfer function editor | HIGH | MEDIUM | MEDIUM | **P2** |
| JSON state export | MEDIUM | MEDIUM | LOW | **P3** |
| Interactive clip plane widget | MEDIUM | HIGH | HIGH | **P3** |
| Animated streamlines | MEDIUM | HIGH | HIGH | **P3** |
| Multi-field volume | LOW | HIGH | HIGH | **P3** |

**Priority rationale:**
- **P1 features are all LOW cost/LOW risk** and provide immediate user value. No excuse to defer.
- **P2 features have slightly higher cost or uncertainty** but are well-understood. Add after P1s ship.
- **P3 features involve significant complexity or uncertain payoff.** Defer to v2.x based on user feedback.

---

## 5. Competitor Feature Analysis

| Feature | ParaView GUI | VisIt | Our Approach |
|---------|-------------|-------|-------------|
| Volume Rendering | Full GPU ray cast with opacity/palette editing | GPU volume rendering | MVP: simple Surface/Volume toggle; P2: opacity TF editor |
| Clip Filter | Interactive plane widget + box/sphere clip types | Interactive clip plane | MVP: axis-aligned clip with numeric origin; P2: live update sliders |
| Contour Filter | Iso-surface generation with range slider | Multiple iso-values at once | MVP: single array + list of isovalues; P2: live update |
| Streamlines | Point/line/plane/radius seed sources; animated | Multiple algorithm choices | MVP: masking region (volume seeds), default velocity; P2: seed type selection |
| Screenshot Export | Save as PNG/PS/EPS | Active viewport capture | MVP: `viewport.image.render` base64 PNG download; P2: JSON state |
| UI Model | Desktop application (full interactive) | Desktop application | Web dashboard embedded viewer (less interactive than desktop, but accessible) |

**Key insight:** The web-based approach intentionally trades some interactivity (no drag-to-move clip plane) for accessibility (no desktop app install). The priority should be on features that work well in the web model (one-click toggles, numeric inputs, screenshot export) rather than mimicking all desktop interactions.

---

## 6. Protocol Message Flows

### 6.1 Volume Rendering Flow

```
User clicks "Volume" toggle
    │
    ├──► Frontend: createVolumeRepresentationMessage(sourceId)
    │         → WS JSON-RPC: { method: "volume.representation.create", params: { sourceProxyId, viewId } }
    │
    ▼
Server: ParaViewWebVolumeRendering.createVolumeRepresentation()
    ├── rep.Representation = "Volume"       ← vtkGPUVolumeRayCastMapper activates
    ├── simple.Render()
    └── InvokeEvent("UpdateEvent")          ← triggers frame push to client
    │
    ▼
Client: Rendered view updates with volume rendering
    (No explicit response handling needed; server pushes updated frame)
```

**Opacity tuning flow:**
```
User adjusts opacity TF control points
    │
    ├──► Frontend: createVolumeOpacityMessage("U", [0, 0, 1, 0.2, 5, 1.0])
    │         → WS JSON-RPC: { method: "volume.opacity.set", params: { arrayName, points } }
    │
    ▼
Server: setVolumeOpacity()
    ├── simple.GetOpacityTransferFunction(arrayName).Points = points
    ├── simple.Render()
    └── InvokeEvent("UpdateEvent")
```

### 6.2 Clip Filter Flow

```
User sets clip axis + origin → clicks "Apply"
    │
    ├──► Frontend: createClipMessage(sourceId, axis, origin)
    │         → WS JSON-RPC: { method: "clip.create", params: { sourceProxyId, normal, origin } }
    │
    ▼
Server: ParaViewWebAdvancedFilters.createClip()
    ├── clip = simple.Clip(Input=source, ClipType="Plane")
    ├── clip.ClipType.Normal = normal        ← e.g., [1, 0, 0] for X-axis
    ├── clip.ClipType.Origin = origin        ← e.g., [0.5, 0, 0]
    ├── simple.Show(clip, view)
    ├── simple.Render()
    ├── InvokeEvent("UpdateEvent")
    └── return { result: "success", proxyId: "123" }    ← proxyId stored in frontend state
    │
    ▼
Client: Rendered view shows half of mesh removed

User adjusts origin → clicks "Update"
    │
    ├──► Frontend: createClipUpdateMessage(proxyId, normal, origin)
    │         → WS JSON-RPC: { method: "clip.update", params: { proxyId, normal, origin } }
    │
    ▼
Server: updateClip()
    ├── proxy.ClipType.Normal = normal
    ├── proxy.ClipType.Origin = origin
    ├── simple.Render()
    └── InvokeEvent("UpdateEvent")

User clicks "Delete Clip"
    │
    ├──► Frontend: createClipDeleteMessage(proxyId)
    │         → WS JSON-RPC: { method: "clip.delete", params: { proxyId } }
    │
    ▼
Server: deleteClip()
    ├── simple.Delete(proxy)
    ├── simple.Render()
    └── InvokeEvent("UpdateEvent")
```

### 6.3 Contour Filter Flow

```
User selects scalar field + enters isovalues → clicks "Apply"
    │
    ├──► Frontend: createContourMessage(sourceId, "p", [101325, 100000])
    │         → WS JSON-RPC: { method: "contour.create", params: { sourceProxyId, arrayName, isovalues } }
    │
    ▼
Server: ParaViewWebAdvancedFilters.createContour()
    ├── contour = simple.Contour(Input=source)
    ├── contour.ContourBy = ["POINTS", "p"]
    ├── contour.Isosurfaces = [101325, 100000]
    ├── simple.Show(contour, view)
    ├── simple.Render()
    ├── InvokeEvent("UpdateEvent")
    └── return { result: "success", proxyId: "456" }

User updates isovalues → "Update"
    │
    ├──► Frontend: createContourUpdateMessage(proxyId, isovalues)
    │         → WS JSON-RPC: { method: "contour.update", params: { proxyId, isovalues } }
    │
    ▼
Server: updateContour()
    ├── proxy.Isosurfaces = isovalues
    ├── simple.Render()
    └── InvokeEvent("UpdateEvent")
```

### 6.4 Streamlines Flow

```
User clicks "Show Streamlines"
    │
    ├──► Frontend: createStreamTracerMessage(sourceId, "maskingRegion")
    │         → WS JSON-RPC: { method: "streamtracer.create", params: { sourceProxyId, seedType } }
    │
    ▼
Server: ParaViewWebAdvancedFilters.createStreamTracer()
    ├── tracer = simple.StreamTracer(Input=source, SeedType="maskingRegion")
    ├── tracer.Vectors = ["POINTS", "U"]     ← velocity field
    ├── tracer.MaximumTrackLength = 100
    ├── tracer.ComputeVorticity = 1
    ├── simple.Show(tracer, view)
    ├── simple.Render()
    ├── InvokeEvent("UpdateEvent")
    └── return { result: "success", proxyId: "789" }

User clicks "Delete Streamlines"
    │
    ├──► Frontend: createStreamTracerDeleteMessage(proxyId)
    │         → WS JSON-RPC: { method: "streamtracer.delete", params: { proxyId } }
    │
    ▼
Server: deleteStreamTracer()
    ├── simple.Delete(proxy)
    ├── simple.Render()
    └── InvokeEvent("UpdateEvent")
```

### 6.5 Screenshot Export Flow

```
User clicks "Screenshot"
    │
    ├──► Frontend: createScreenshotMessage(quality=85, viewId=-1)
    │         → WS JSON-RPC: { method: "viewport.image.render", params: { view: -1, quality: 85, ratio: 1 } }
    │
    ▼
Server: ParaViewWebViewPortImageDelivery.viewportImageRender()  ← built-in, no custom code
    ├── Renders current view to offscreen framebuffer
    ├── Encodes as PNG
    └── return { result: { image: "<base64 PNG string>" } }
    │
    ▼
Frontend: parseScreenshotResponse(response) → base64 string
    │
    ▼
Frontend: downloadScreenshot(base64, "cfd-result") → browser download "cfd-result.png"
    (atob decode → Uint8Array → Blob → object URL → <a> click → revoke)
```

---

## 7. Implementation Notes

### 7.1 Frontend State Management

Each filter (clip, contour, streamlines) must track its `proxyId` returned from the server so it can be updated or deleted later. Recommended state shape:

```typescript
interface ViewerState {
  sourceProxyId: number;         // The OpenFOAM reader proxy ID
  representation: 'Surface' | 'Volume';
  activeClip: { proxyId: number; normal: number[]; origin: number[] } | null;
  activeContour: { proxyId: number; arrayName: string; isovalues: number[] } | null;
  activeStreamTracer: { proxyId: number } | null;
}
```

### 7.2 Filter Composition

Multiple filters can be active simultaneously (e.g., volume rendering + clip + streamlines). Each filter's `simple.Show()` adds a new representation to the view. The frontend should allow independent toggling of each filter's visibility.

### 7.3 StreamTracer Seed Types

ParaView's `StreamTracer` supports multiple `SeedType` values:
- `"MaskingRegion"` (default) -- seeds throughout the volume
- `"Point"` -- single seed point (requires `SeedPoint` parameter)
- `"PointCloud"` -- cloud of points (requires `SeedPoint` and `NumberOfPoints`)
- `"Line"` -- line of seeds (requires `SeedPoint`, `LineEndPoint`, `Resolution`)
- `"Plane"` -- plane of seeds (requires `SeedPoint`, `Normal`, `Offset`)
- `"Sphere"` -- spherical shell of seeds (requires `SeedPoint`, `Radius`)

For v1.5.0 MVP: only `"MaskingRegion"` (default, simplest). P2 could add seed type selection dropdown.

### 7.4 Volume Rendering Limitations on Apple Silicon

The project notes acknowledge Apple Silicon detached-container limitation (`--platform linux/amd64` required on amd64 servers). Volume rendering via `vtkGPUVolumeRayCastMapper` requires GPU access. On Apple Silicon, this means the container must run on a remote Linux/amd64 machine with GPU, not locally via Rosetta. This is an infrastructure constraint, not a code constraint.

### 7.5 Large Mesh Considerations

Volume rendering is memory-intensive. For meshes > 5M cells, `vtkGPUVolumeRayCastMapper` may exceed GPU memory. ParaView provides alternatives:
- `"GPU Volume Ray Cast Mapper"` (default, fastest)
- `"Smart Volume Mapper"` (adaptive, handles larger datasets)

The v1.5.0 MVP can default to the built-in mapper. A future enhancement could add mapper type selection.

---

## Sources

| Source | URL | Confidence | Verifies |
|--------|-----|------------|---------|
| ParaView 5.10.0 protocols.py (GitHub) | `https://raw.githubusercontent.com/Kitware/ParaView/v5.10.0/Web/Python/paraview/web/protocols.py` | HIGH | All `@exportRpc` method signatures |
| ParaViewWeb API (paraviewweb) | `https://raw.githubusercontent.com/Kitware/paraviewweb/master/src/IO/WebSocket/ParaViewWebClient/api.md` | HIGH | Available protocol names |
| openfoam/openfoam10-paraview510 (Docker Hub) | `https://hub.docker.com/r/openfoam/openfoam10-paraview510` | HIGH | Contains ParaView 5.10.1 + vtkGPUVolumeRayCastMapper |
| Existing codebase: `paraviewProtocol.ts` | `dashboard/src/services/paraviewProtocol.ts` | HIGH | Protocol message pattern, JSON-RPC format |
| Existing codebase: `paraview_web_launcher.py` | `api_server/services/paraview_web_launcher.py` | HIGH | Container lifecycle, launcher config structure |
| Existing codebase: STACK.md v1.5.0 | `.planning/research/STACK.md` | HIGH | Detailed Python protocol handlers for all 3 features |
| ParaView `Clip()` filter docs | ParaView GUI documentation + `simple.py` API | MEDIUM | Clip parameters (Plane, Box, Scalar) |
| ParaView `Contour()` filter docs | ParaView GUI documentation + `simple.py` API | MEDIUM | Iso-surface parameters |
| ParaView `StreamTracer()` filter docs | ParaView GUI documentation + `simple.py` API | MEDIUM | Seed types, integration parameters |
