---
phase: 22
plan: "01"
subsystem: dashboard / ParaView Web viewer
tags: [filters, clip, contour, streamtracer, ParaView-Web]
dependency_graph:
  requires:
    - Phase 20: ParaViewWebVolumeRendering protocol (GPU volume rendering)
    - Phase 15: ParaView Web server integration
  provides:
    - api_server/services/paraview_adv_protocols.py
      - ParaViewWebAdvancedFilters class (5 RPCs)
    - dashboard/src/services/paraviewProtocol.ts
      - FilterInfo interface
      - createClipFilterMessage, createContourFilterMessage, createStreamTracerFilterMessage
      - createDeleteFilterMessage, createListFiltersMessage
      - parseFilterListResponse
    - dashboard/src/components/AdvancedFilterPanel.tsx
      - Tabbed panel (Clip / Contour / Streamlines)
      - Active filter list with delete buttons
    - dashboard/src/components/ParaViewViewer.tsx
      - activeFilters state
      - Filter response handlers in ws.onmessage
      - AdvancedFilterPanel wired into connected render
    - dashboard/src/components/ParaViewViewer.css
      - .advanced-filter-panel and all filter-* CSS classes
  affects:
    - ParaViewViewer component (FILT-01.1 through FILT-01.6)
tech_stack:
  added:
    - ParaViewWebAdvancedFilters protocol class with 5 @exportRpc-decorated methods
    - FilterInfo TypeScript interface with discriminated union type
    - AdvancedFilterPanel React component with tabbed UI
    - Active filter registry via class-level _filters dict (tracks proxy ID -> filter)
  patterns:
    - Filter registry pattern: Python class-level dict tracks all created filters by id()
    - Tabbed panel: Clip / Contour / Streamlines with local per-tab state
    - WS response routing: message.id checked in ws.onmessage for each filter type
    - Optimistic UI update: setActiveFilters appended immediately on success response
key_files:
  created:
    - dashboard/src/components/AdvancedFilterPanel.tsx
  modified:
    - api_server/services/paraview_adv_protocols.py
    - dashboard/src/services/paraviewProtocol.ts
    - dashboard/src/components/ParaViewViewer.tsx
    - dashboard/src/components/ParaViewViewer.css
key_decisions:
  - "FILT-01.1 Clip: scalar threshold clip using simple.Clip with ClipType=Scalar; insideOut boolean flips which side is retained"
  - "FILT-01.2 Contour: isosurface extraction via simple.Contour; max 20 isovalues enforced at RPC boundary"
  - "FILT-01.3 StreamTracer: integrates along velocity field U using FORWARD/BACKWARD direction; maxSteps capped at 10000"
  - "Filter registry: class-level _filters dict uses id(filter_proxy) as key; delete RPC removes from dict after simple.Delete()"
  - "Optimistic add: setActiveFilters([...prev, newFilter]) called immediately on success response; delete updates state via callback"
metrics:
  duration: 82s
  tasks_completed: 4
  files_modified: 5
  completed: "2026-04-11"
---

# Phase 22 Plan 01: Advanced Filters Summary

## One-liner

ParaViewWebAdvancedFilters protocol (Clip / Contour / StreamTracer / Delete / List) with tabbed AdvancedFilterPanel UI wired into ParaViewViewer.

## What Was Built

### FILT-01.1: Clip Filter RPC
`visualization.filters.clip.create` accepts `insideOut: bool` and `scalarValue: float`. Creates `simple.Clip(Input=source)` with `ClipType="Scalar"`. Filter registered in `_filters[id(clip)]`. After creation, calls `simple.Render()` + `InvokeEvent("UpdateEvent")` to push viewport update.

### FILT-01.2: Contour (Isovalue) Filter RPC
`visualization.filters.contour.create` accepts `isovalues: list`. Enforces max 20 values at RPC boundary. Creates `simple.Contour(Input=source)` with `ContourBy=["POINTS", " scalars"]`. Same render/update pattern.

### FILT-01.3: StreamTracer Filter RPC
`visualization.filters.streamtracer.create` accepts `integrationDirection: str` ("FORWARD"/"BACKWARD") and `maxSteps: int` (capped at 10000). Uses velocity field `["POINTS", "U"]`. Creates `simple.StreamTracer` with configured integration parameters.

### FILT-01.4: Filter Delete RPC
`visualization.filters.delete` accepts `filterId: int`. Looks up in `_filters` registry, calls `simple.Delete(filter_proxy)`, removes from registry, pushes viewport update. Returns `{"success": true}`.

### FILT-01.5: Filter List RPC
`visualization.filters.list` returns all active filters with their types and parameters by iterating `_filters` and extracting relevant properties via `getattr` with safe defaults.

### FILT-01.6: Frontend Integration
- `FilterInfo` TypeScript interface with discriminated union for filter type
- `createClipFilterMessage`, `createContourFilterMessage`, `createStreamTracerFilterMessage`, `createDeleteFilterMessage`, `createListFiltersMessage` message builders
- `AdvancedFilterPanel.tsx` with Clip/Contour/Streamlines tabs, local state per tab, active filter list with delete buttons
- `ws.onmessage` handlers for `pv-filter-clip`, `pv-filter-contour`, `pv-filter-streamtracer`, `pv-filter-delete` responses
- `activeFilters` state updated optimistically on filter creation

## Files Modified

| File | Change |
|------|--------|
| `api_server/services/paraview_adv_protocols.py` | Appended `ParaViewWebAdvancedFilters` class with 5 RPC methods |
| `dashboard/src/services/paraviewProtocol.ts` | Appended `FilterInfo` interface + 6 filter functions |
| `dashboard/src/components/AdvancedFilterPanel.tsx` | Created new tabbed panel component (318 lines) |
| `dashboard/src/components/ParaViewViewer.tsx` | Added filter imports, `activeFilters` state, filter WS handlers, wired panel |
| `dashboard/src/components/ParaViewViewer.css` | Appended `.advanced-filter-panel` and all filter-* CSS classes |

## Verification

```bash
python3 -m py_compile api_server/services/paraview_adv_protocols.py  # SYNTAX OK
grep -c "createClipFilterMessage\|createContourFilterMessage\|createStreamTracerFilterMessage\|createDeleteFilterMessage\|createListFiltersMessage" dashboard/src/services/paraviewProtocol.ts  # 5
ls -la dashboard/src/components/AdvancedFilterPanel.tsx  # -rw-r--r--@ 1 Zhuanz 6687 bytes
grep -c "AdvancedFilterPanel\|activeFilters" dashboard/src/components/ParaViewViewer.tsx  # 4
grep -c "\.filter-tabs\|\.filter-apply-btn\|\.active-filter-row" dashboard/src/components/ParaViewViewer.css  # 3
```

All checks passed.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| None | — | All filter RPCs operate on the active source only; no file system access, no new network endpoints, no auth path changes. Input validation on all RPC parameters (isovalues count, scalar range, maxSteps cap). |

## Known Stubs

None.
