# Phase 28 Plan 01: Cleanup + Old File Removal Summary

## Plan Metadata

| Field | Value |
|-------|-------|
| Phase | 28 |
| Plan | 01 |
| Subsystem | cleanup (TRAME-06) |
| Committed | 2026-04-12 |
| Requirements | TRAME-06.1, TRAME-06.2, TRAME-06.3, TRAME-06.4, TRAME-06.5 |
| Tech Stack | TypeScript (React), Python (FastAPI) |

## One-liner

Deleted 6 ParaView Web artifacts and refactored AdvancedFilterPanel to use direct bridge callbacks, removing the last dependency on paraviewProtocol.ts.

## What Was Built

### Deleted 6 Files

| File | Reason |
|------|--------|
| `entrypoint_wrapper.sh` | Old Docker container entrypoint; Dockerfile already not referencing it |
| `api_server/services/paraview_adv_protocols.py` | Old `@exportRpc` protocol classes; GPU detection code already copied to trame_server.py |
| `api_server/services/paraview_web_launcher.py` | `ParaviewWebManager` class; replaced by `TrameSessionManager` |
| `dashboard/src/components/ParaViewViewer.tsx` | Old React viewer; replaced by `TrameViewer.tsx` |
| `dashboard/src/components/ParaViewViewer.css` | Renamed to `TrameViewer.css` (styles preserved) |
| `dashboard/src/services/paraviewProtocol.ts` | Old JSON-RPC message builders; last used by `AdvancedFilterPanel` (refactored) |

### Refactored: AdvancedFilterPanel.tsx

**Before:** imported `createClipFilterMessage`, `createContourFilterMessage`, `createStreamTracerFilterMessage`, `createDeleteFilterMessage`, `FilterInfo` from `paraviewProtocol.ts`. Used `sendProtocolMessage` callback that created legacy JSON-RPC message objects.

**After:** No imports from `paraviewProtocol.ts`. Uses 4 direct callback props:
- `onCreateClip(insideOut: boolean, scalarValue: number)`
- `onCreateContour(isovalues: number[])`
- `onCreateStreamTracer(direction: 'FORWARD'|'BACKWARD', maxSteps: number)`
- `onDeleteFilter(filterId: string)`

Owns `FilterInfo` interface locally (with `id: string` for UUID-based IDs).

### Refactored: TrameViewer.tsx

**Removed:** `bridgeSend` useCallback wrapper (lines 321-358) that mapped legacy JSON-RPC method names to bridge message types.

**Added:** 4 direct filter handler functions:
```typescript
const handleCreateClip = useCallback((insideOut, scalarValue) => {
  bridgeRef.current?.send({ type: 'clip_create', insideOut, scalarValue });
}, []);
const handleCreateContour = useCallback((isovalues) => {
  bridgeRef.current?.send({ type: 'contour_create', isovalues });
}, []);
const handleCreateStreamTracer = useCallback((direction, maxSteps) => {
  bridgeRef.current?.send({ type: 'streamtracer_create', direction, maxSteps });
}, []);
const handleDeleteFilter = useCallback((filterId) => {
  bridgeRef.current?.send({ type: 'filter_delete', filterId });
}, []);
```

**Updated:** `AdvancedFilterPanel` JSX props to pass direct callbacks instead of `bridgeSend`.

**Added:** `export type { FilterInfo }` re-export for `AdvancedFilterPanel`.

**Updated:** CSS import from `./ParaViewViewer.css` → `./TrameViewer.css` (file renamed via git).

### Cleaned: trame_server.py

Removed stale comments referencing deleted files:
- `# GPU Detection — copied verbatim from paraview_adv_protocols.py` → `# GPU Detection`
- Removed docstring attribution to `paraview_adv_protocols.py ParaViewWebVolumeRendering._detect_gpu()`

### Preserved (not deleted)

- `dashboard/src/services/paraview.ts` — API client functions (`launchVisualizationSession`, `sendHeartbeat`) actively used by `TrameViewer`
- `dashboard/src/services/websocket.ts` — WebSocket job progress streaming (not ParaView Web)
- `dashboard/src/services/websocket_manager.py` — WebSocket connection manager
- `api_server/routers/websocket.py` — WebSocket FastAPI router
- `AdvancedFilterPanel.tsx` — Filter creation UI (refactored, not deleted)

## Verification Results

```
tsc --noEmit  → 0 errors
pytest tests/phase27/  →  88 passed, 3 warnings
node tests/phase27/test_cfd_viewer_bridge.js  →  22 passed, 0 failed
```

**TRAME-06 criteria:**

| Requirement | Status |
|------------|--------|
| TRAME-06.1: `entrypoint_wrapper.sh` removed | ✅ Deleted |
| TRAME-06.2: `paraview_adv_protocols.py` removed | ✅ Deleted |
| TRAME-06.3: `:ro` volume mount for `adv_protocols` | ✅ `paraview_web_launcher.py` deleted (contained the mount) |
| TRAME-06.4: `ParaViewViewer.tsx/.css` removed/replaced | ✅ Deleted (CSS → TrameViewer.css); `AdvancedFilterPanel.tsx` kept (refactored) |
| TRAME-06.5: `paraviewProtocol.ts` call sites updated | ✅ `AdvancedFilterPanel` refactored; no broken imports |

## Commits

| Hash | Message |
|------|---------|
| `102435f` | refactor(28): delete all ParaView Web artifacts, refactor AdvancedFilterPanel |
| `b25f017` | chore: update STATE.md — Phase 28 complete, v1.6.0 progress |
