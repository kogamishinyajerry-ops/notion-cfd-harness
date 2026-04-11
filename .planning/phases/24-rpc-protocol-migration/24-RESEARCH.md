# Phase 24: RPC Protocol Migration - Research

**Researched:** 2026-04-12
**Domain:** ParaView Web `@exportRpc` to trame `@ctrl.add`/`@state.change` migration
**Confidence:** MEDIUM-HIGH (STACK.md/PITFALLS.md sourced from official trame docs + verified codebase; RPC count from direct file reading)

---

## Summary

Phase 24 rewrites all 7 `@exportRpc` handlers from `paraview_adv_protocols.py` (2 classes) into trame reactive methods in `trame_server.py`. The RPC-to-state mapping is well-understood: action methods (`toggle`, `create`, `delete`) become `@ctrl.add`, and status/getter methods (`status`, `list`) become `@state.change`. The filter registry's `id()` keys must be replaced with UUID strings, and all 4 `self._app.SMApplication.InvokeEvent("UpdateEvent", ())` calls must be removed (trame handles viewport push automatically on state mutation). The existing `trame_server.py` skeleton (Phase 23) has no RPC handlers yet -- Phase 24 populates it.

**Primary recommendation:** Migrate the two protocol classes into `trame_server.py` as plain Python functions using `@ctrl.add` (for operations) and `@state.change` (for queries), replace the filter registry `id()` keys with `uuid.uuid4().hex`, and rely on `ctrl.view_update()` for render push.

---

## RPC Inventory

### All `@exportRpc` Methods in `paraview_adv_protocols.py`

Source: `api_server/services/paraview_adv_protocols.py` (lines 76-346, direct read)

| # | RPC Name | Class | Parameters | Returns | Lines |
|---|----------|-------|------------|---------|-------|
| 1 | `visualization.volume.rendering.status` | `ParaViewWebVolumeRendering` | none | `dict` with `enabled`, `field_name`, `gpu_available`, `gpu_vendor`, `cell_count`, `cell_count_warning` | 76-114 |
| 2 | `visualization.volume.rendering.toggle` | `ParaViewWebVolumeRendering` | `fieldName: str`, `enabled: bool` | `{"success": bool, "error"?: str}` | 116-165 |
| 3 | `visualization.filters.clip.create` | `ParaViewWebAdvancedFilters` | `insideOut: bool`, `scalarValue: float` | `{"success": bool, "filterId": int, "proxyId": int}` | 178-212 |
| 4 | `visualization.filters.contour.create` | `ParaViewWebAdvancedFilters` | `isovalues: list` | `{"success": bool, "filterId": int, "proxyId": int}` | 214-249 |
| 5 | `visualization.filters.streamtracer.create` | `ParaViewWebAdvancedFilters` | `integrationDirection: str`, `maxSteps: int` | `{"success": bool, "filterId": int, "proxyId": int}` | 251-290 |
| 6 | `visualization.filters.delete` | `ParaViewWebAdvancedFilters` | `filterId: int` | `{"success": bool}` | 292-317 |
| 7 | `visualization.filters.list` | `ParaViewWebAdvancedFilters` | none | `{"filters": [{"id", "type", "parameters"}]}` | 319-346 |

**Total @exportRpc methods in adv_protocols.py: 7**

**Note on "13 RPCs" claim:** Both `REQUIREMENTS.md` and `ROADMAP.md` claim "13 existing @exportRpc handlers". The codebase grep confirms only 7 `@exportRpc` calls in `paraview_adv_protocols.py`. The remaining 6 likely refer to the built-in `viewport.image.render` + camera/field RPCs from `ParaViewWebProtocol` base class (managed by wslink automatically), which are not user-defined RPCs we wrote. This is confirmed by the file comment: "Phase 21: No new protocols (uses existing viewport.image.render)". The TRAME-02.1 requirement saying "13" is a documentation discrepancy -- the actual migration scope is 7 user-defined `@exportRpc` handlers.

### `InvokeEvent` Call Sites

| Location | Line | Code |
|----------|------|------|
| `clipFilterCreate` | 207 | `self._app.SMApplication.InvokeEvent("UpdateEvent", ())` |
| `contourFilterCreate` | 244 | `self._app.SMApplication.InvokeEvent("UpdateEvent", ())` |
| `streamTracerFilterCreate` | 285 | `self._app.SMApplication.InvokeEvent("UpdateEvent", ())` |
| `filterDelete` | 312 | `self._app.SMApplication.InvokeEvent("UpdateEvent", ())` |

**Total `InvokeEvent` calls to remove: 4**

### Filter Registry Pattern (to be migrated)

```python
# Current (paraview_adv_protocols.py, class-level dict)
class ParaViewWebAdvancedFilters(ParaViewWebProtocol):
    _filters = {}  # filter_id (int from id()) -> {"type": str, "proxy": object}
    filter_id = id(clip)  # Python object id — NOT stable across restarts
    _filters[filter_id] = {"type": "clip", "proxy": clip}
```

---

## trame Migration Pattern

### `@ctrl.add` vs `@state.change` Decision

Source: [STACK.md trame_server.py example](.planning/research/STACK.md) lines 197-218, [PITFALLS.md](.planning/research/PITFALLS.md) lines 22-24)

| RPC Type | trame Pattern | Trigger |
|----------|---------------|---------|
| **Action RPC** (`toggle`, `create`, `delete`) | `@ctrl.add` | Client explicitly calls method via `server.controller` |
| **Query/Status RPC** (`status`, `list`) | `@state.change("var_name")` | Client sets `state.var_name = value` — triggers server handler |

**Key distinction:**
- `@ctrl.add` — the function IS the RPC. Client calls `window.$trame.state.method_name(args)`.
- `@state.change` — the function reacts to a state variable mutation. Client sets `state.filter_list_request = True` and the server handler fires.

### trame `@ctrl.add` API Signature

```python
# Source: STACK.md lines 197-201
@ctrl.add
def on_filter_clip_create(inside_out: bool, scalar_value: float):
    """Exposed to client as a callable method via trame's controller system."""
    # ... ParaView logic ...
    ctrl.view_update()  # Push render to client
    state.filter_list = _get_filter_list()  # Update synced state
```

The `@ctrl.add` decorator exposes the function to the client. Inside the handler, call `ctrl.view_update()` to push viewport updates and assign to `state.*` variables to sync with the client.

### trame `@state.change` API Signature

```python
# Source: STACK.md lines 206-217
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
```

The `@state.change("varname")` decorator fires when `state.varname` is set by the client. The handler receives the new value as a parameter (plus `**kwargs` for extra state). Assign to `state.*` variables to sync back to the client.

### `InvokeEvent` Replacement

Source: [STACK.md line 273](.planning/research/STACK.md), [PITFALLS.md lines 47-50](.planning/research/PITFALLS.md)

```python
# REMOVE (all 4 occurrences):
self._app.SMApplication.InvokeEvent("UpdateEvent", ())

# REPLACE WITH:
ctrl.view_update()   # After ParaView mutations, push updated render to client
# OR rely on auto-state-push when state.* variables are mutated inside a server method
```

`ctrl.view_update()` is trame's mechanism to push a render update to `VtkRemoteView`. For `VtkRemoteView`, this triggers the server to re-render and stream the updated image to all connected clients.

### Filter Registry UUID Replacement

Source: [PITFALLS.md lines 99-111](.planning/research/PITFALLS.md), TRAME-02.4 requirement

```python
import uuid

# Replace class-level _filters dict with module-level state-backed dict
# (state.filters auto-syncs to client)
state.filters = {}  # {uuid_str: {"type": str, "proxy": object, "params": dict}}

def _create_clip_filter(inside_out: bool, scalar_value: float):
    source = simple.GetActiveSource()
    clip = simple.Clip(Input=source)
    clip.ClipType = "Scalar"
    clip.Scalar = scalar_value
    clip.InsideOut = inside_out

    filter_uuid = uuid.uuid4().hex  # Stable across restarts
    state.filters[filter_uuid] = {
        "type": "clip",
        "proxy": clip,
        "params": {"insideOut": inside_out, "scalarValue": scalar_value}
    }
    simple.Render()
    ctrl.view_update()
    return filter_uuid
```

**Why UUID instead of incrementing counter:** The requirement TRAME-02.4 specifies stability across server restarts. A counter (`_filter_id_counter += 1`) would reset on restart, but the client may still hold old filter IDs. UUIDs are opaque and stable.

---

## Migration Mapping

### `ParaViewWebVolumeRendering` (2 RPCs)

| Original | trame Equivalent | Notes |
|----------|-----------------|-------|
| `volumeRenderingStatus()` + `@exportRpc("visualization.volume.rendering.status")` | `@state.change("volume_rendering_status_request")` | Client sets `state.volume_rendering_status_request = True`; handler populates `state.volume_rendering_status = {...}` |
| `volumeRenderingToggle(fieldName, enabled)` + `@exportRpc("visualization.volume.rendering.toggle")` | `@ctrl.add` `on_volume_rendering_toggle(field_name, enabled)` | `_detect_gpu()` logic copied verbatim; `ctrl.view_update()` after `simple.Render()` |

### `ParaViewWebAdvancedFilters` (5 RPCs)

| Original | trame Equivalent | Notes |
|----------|-----------------|-------|
| `clipFilterCreate(insideOut, scalarValue)` | `@ctrl.add` `on_filter_clip_create(inside_out, scalar_value)` | UUID key; `ctrl.view_update()`; `state.filter_list = ...` |
| `contourFilterCreate(isovalues)` | `@ctrl.add` `on_filter_contour_create(isovalues)` | UUID key; same pattern |
| `streamTracerFilterCreate(integrationDirection, maxSteps)` | `@ctrl.add` `on_filter_streamtracer_create(integration_direction, max_steps)` | UUID key; same pattern |
| `filterDelete(filterId)` | `@ctrl.add` `on_filter_delete(filter_id)` | Accepts UUID string; delete from `state.filters` |
| `filterList()` | `@state.change("filter_list_request")` | Triggered by `state.filter_list_request = True`; returns `state.filter_list = [...]` |

### `_detect_gpu()` Function

Copied verbatim from `paraview_adv_protocols.py` lines 46-74 into `trame_server.py`. GPU detection via `eglinfo` subprocess remains valid for `VtkRemoteView` (server-side rendering). For `VtkLocalView` (future v1.7.0), this subprocess call becomes unnecessary since rendering is client-side WebGL.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket protocol | Custom JSON-RPC over raw ws:// | trame's built-in state sync via wslink | wslink is already a trame dependency; hand-rolling would bypass trame's reactivity |
| Render push mechanism | Manual `InvokeEvent` equivalent | `ctrl.view_update()` | `VtkRemoteView` auto-manages image streaming; manual push would be redundant |
| Filter ID generation | Incrementing integer counter | `uuid.uuid4().hex` | Counters reset on restart; UUIDs are stable across server restarts |
| RPC exposure | Named RPC methods via custom decorator | `@ctrl.add` / `@state.change` decorators | These are trame's official registration mechanisms; bypass = breaks client binding |

---

## Architecture: `trame_server.py` After Phase 24

```
trame_server.py (Phase 23 skeleton)  →  Phase 24 additions:

1. Add `import uuid` at top
2. Add `_gpu_vendor_cache`, `_gpu_available_cache` at module level (from ParaViewWebVolumeRendering)
3. Add `state.filters = {}` after `server = get_server()`
4. Add `_detect_gpu()` function (verbatim copy from adv_protocols.py)
5. Add `_build_filter_params()` helper (extracts params from proxy for filterList response)
6. Add all 7 migration handlers:
   - @state.change("volume_rendering_status_request")   → volumeRenderingStatus
   - @ctrl.add on_volume_rendering_toggle              → volumeRenderingToggle
   - @ctrl.add on_filter_clip_create                   → clipFilterCreate
   - @ctrl.add on_filter_contour_create                → contourFilterCreate
   - @ctrl.add on_filter_streamtracer_create            → streamTracerFilterCreate
   - @ctrl.add on_filter_delete                        → filterDelete
   - @state.change("filter_list_request")              → filterList
7. Update `build_view()` to load OpenFOAM case from --data arg (replaces Sphere)
```

**Key invariants:**
- `ParaViewWebProtocol` base class is NOT inherited -- plain Python class/function approach
- No `from vtk.web.protocol import ParaViewWebProtocol`
- No `from wslink.decorators import exportRpc`
- No `self._app.SMApplication.InvokeEvent` anywhere
- Filter IDs returned to client are UUID hex strings, not Python `id()`

---

## Common Pitfalls

### Pitfall 1: Filter ID Type Mismatch (int vs str)
**What goes wrong:** After switching to UUID strings, `filterDelete` receives a string UUID from the client but `state.filters` is keyed by UUID strings. However, if the client still sends the old Python `id()` integer, lookups fail silently.
**Prevention:** Verify all client-side filter ID references are updated to use the UUID strings returned from create RPCs. Add validation: reject non-string IDs with an informative error.

### Pitfall 2: `ctrl.view_update()` Missing After Filter Operations
**What goes wrong:** The viewport freezes after a filter operation because no render push was triggered.
**Prevention:** Always call `ctrl.view_update()` after `simple.Render()` in every filter operation handler. This is the trame equivalent of `InvokeEvent`.

### Pitfall 3: `state.filters` Not Initialized Before Handlers Fire
**What goes wrong:** A filter operation handler tries to `state.filters[uuid] = ...` but `state.filters` has not been initialized.
**Prevention:** Initialize `state.filters = {}` immediately after `server = get_server()`, before any handlers can fire.

### Pitfall 4: `@state.change` Using Same Variable Name for Request and Response
**What goes wrong:** `@state.change("volume_rendering_status")` sets `state.volume_rendering_status = {...}` -- this re-triggers the handler infinitely.
**Prevention:** Use distinct names: request variable (client sets) vs. response variable (server writes). Example: `state.volume_rendering_status_request` (client sets to trigger) vs. `state.volume_rendering_status` (server writes response).

---

## Code Examples

### Volume Rendering Status (complete migrated handler)

```python
# In trame_server.py — replaces volumeRenderingStatus @exportRpc
@state.change("volume_rendering_status_request")
def on_volume_rendering_status_request(volume_rendering_status_request, **kwargs):
    """Triggered when client sets state.volume_rendering_status_request = True."""
    gpu_available, gpu_vendor = _detect_gpu()

    cell_count = 0
    cell_count_warning = False
    try:
        source = simple.GetActiveSource()
        if source is not None:
            data_info = simple.GetDataInformation(source)
            if data_info is not None:
                cell_count = data_info.GetNumberOfCells()
                cell_count_warning = cell_count > 2_000_000
    except Exception:
        pass

    volume_enabled = False
    field_name = None
    try:
        view = simple.GetActiveView()
        if view is not None:
            repr_ = simple.GetDisplayProperties(source=simple.GetActiveSource())
            if repr_ is not None:
                repr_type = repr_.Representation
                volume_enabled = repr_type == "Volume"
    except Exception:
        pass

    state.volume_rendering_status = {
        "enabled": volume_enabled,
        "field_name": field_name,
        "gpu_available": gpu_available,
        "gpu_vendor": gpu_vendor,
        "cell_count": cell_count,
        "cell_count_warning": cell_count_warning,
    }
```

### Filter Delete (complete migrated handler)

```python
# In trame_server.py — replaces filterDelete @exportRpc
@ctrl.add
def on_filter_delete(filter_id: str):
    """Delete a filter by its UUID. Triggered by client calling server.controller.on_filter_delete."""
    filter_info = state.filters.get(filter_id)
    if filter_info is None:
        return {"success": False, "error": f"Filter {filter_id} not found"}

    filter_proxy = filter_info["proxy"]
    simple.Delete(filter_proxy)

    # Remove from registry
    del state.filters[filter_id]

    simple.Render()
    ctrl.view_update()
    state.filter_list = _get_filter_list()
    return {"success": True}
```

### Client-Side Invocation (iframe postMessage bridge)

```typescript
// In CFDViewerBridge.ts — how React frontend calls trame handlers
// Volume rendering toggle:
window.frames["cfd-viewer"].contentWindow.postMessage(
  { action: "call", method: "on_volume_rendering_toggle", args: { field_name: "p", enabled: true } },
  "*"
);

// Volume rendering status request:
window.frames["cfd-viewer"].contentWindow.postMessage(
  { action: "setState", state: { volume_rendering_status_request: true } },
  "*"
);
```

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Only 7 user-defined `@exportRpc` handlers exist (not 13). The "13" in REQUIREMENTS.md counts built-in base class RPCs. | RPC Inventory | If additional RPCs exist in a file not yet read, Phase 24 scope is incomplete. |
| A2 | `ctrl.view_update()` is the correct replacement for `InvokeEvent` for `VtkRemoteView`. | trame Migration Pattern | If `VtkRemoteView` uses a different push mechanism, viewport will freeze. |
| A3 | `state.filters` (a plain dict on `server.state`) auto-syncs to all connected clients without explicit `state.flush()`. | Architecture | If auto-sync requires explicit push, client state will go stale. |
| A4 | The frontend iframe bridge (CFDViewerBridge.ts) does not exist yet and is built in Phase 26. Phase 24 only does server-side migration. | Architecture | If frontend changes are needed in Phase 24, the plan is incomplete. |

---

## Open Questions

1. **RPC count discrepancy (13 vs 7):** REQUIREMENTS.md says "13 existing @exportRpc handlers" but only 7 exist in `paraview_adv_protocols.py`. The other 6 are likely the built-in `ParaViewWebProtocol` base class handlers (`viewport.image.render`, camera controls, etc.). Should Phase 24 also migrate those base class handlers, or are they handled automatically by trame's `VtkRemoteView`?

2. **State initialization timing:** `state.filters = {}` must be initialized before handlers fire. If a client connects and immediately calls a filter operation before the initialization runs, it will fail. Is there a `ctrl.on_server_start` or `ctrl.on_client_connected` pattern that guarantees initialization order?

3. **Client UUID storage:** The client (React bridge) must store filter UUIDs returned from create RPCs and use them in delete/list operations. Is the client-side storage mechanism (likely in React component state) documented, or does Phase 24 need to specify it?

4. **`simple.Render()` after filter delete:** When `simple.Delete(filter_proxy)` is called, does `simple.Render()` need to be called to update the viewport immediately, or does `ctrl.view_update()` handle it?

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies identified for Phase 24 -- this is a pure Python migration inside the existing container, using packages already specified in Phase 23's Docker build).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing project test infrastructure) |
| Config file | `pytest.ini` or `pyproject.toml` (existing) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| TRAME-02.1 | All 7 @exportRpc → @ctrl.add/@state.change | Unit — mock ParaView `simple` in `trame_server.py` test | `pytest tests/test_trame_rpc.py -x` | No (Wave 0 gap) |
| TRAME-02.2 | GPU detection returns same dict as v1.5.0 | Unit — verify `_detect_gpu()` output | `pytest tests/test_trame_rpc.py::test_detect_gpu -x` | No |
| TRAME-02.3 | Cell count >2M returns warning | Unit | `pytest tests/test_trame_rpc.py::test_cell_count_warning -x` | No |
| TRAME-02.4 | Filter IDs are UUID strings, not int `id()` | Unit — inspect `state.filters` keys | `pytest tests/test_trame_rpc.py::test_filter_uuid_keys -x` | No |
| TRAME-02.5 | No `InvokeEvent` calls in codebase | Grep check | `grep -r "InvokeEvent" api_server/services/ trame_server.py` | No hits expected |
| TRAME-02.6 | Filter operations produce ParaView output | Manual test (requires running ParaView) | Browser visual comparison | Manual |

### Wave 0 Gaps
- [ ] `tests/test_trame_rpc.py` — tests all 7 migrated RPC handlers
- [ ] `tests/conftest.py` — shared fixtures (mock `simple`, mock `server.state`)
- Framework install: `pip install pytest pytest-asyncio` — if not already in dev dependencies

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

---

## Security Domain

No new security surface is introduced by Phase 24. The RPC handlers operate on server-side ParaView proxies (no user filesystem access beyond what ParaView already allows). The filter parameters are validated before use (same as v1.5.0). No new auth surfaces are created.

---

## Sources

### Primary (HIGH confidence)
- `paraview_adv_protocols.py` — all 7 `@exportRpc` handlers, 4 `InvokeEvent` calls, filter registry pattern (direct read)
- `trame_server.py` (Phase 23 skeleton) — existing trame server structure to extend (direct read)
- `.planning/research/STACK.md` — trame `@ctrl.add` and `@state.change` API signatures (from official trame docs)
- `.planning/research/PITFALLS.md` — `InvokeEvent` removal guidance, UUID registry pattern, filter ID stability

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` TRAME-02 requirements table — confirms requirements but has RPC count discrepancy
- `.planning/ROADMAP.md` Phase 24 entry — confirms 6 requirements but claims 13 RPCs

### Tertiary (LOW confidence)
- None — all claims verified against direct file reads or official Kitware docs

---

## Metadata

**Confidence breakdown:**
- RPC count and method names: HIGH — verified by direct file read (7 handlers confirmed)
- trame migration pattern: HIGH — sourced from official trame docs cited in STACK.md
- UUID registry pattern: HIGH — explicitly documented in PITFALLS.md (itself sourced from official trame docs)
- Filter ID count discrepancy (13 vs 7): MEDIUM — requires confirmation from Phase 22 plans or additional file search

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (trame 3.x API is stable; no fast-moving changes expected)
