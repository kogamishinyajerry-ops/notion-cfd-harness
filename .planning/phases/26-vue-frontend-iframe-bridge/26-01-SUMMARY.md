---
phase: "26"
plan: "01"
type: execute
wave: "1"
subsystem: dashboard
tags:
  - trame
  - iframe
  - postMessage
  - vue-frontend
  - bridge
dependency_graph:
  requires:
    - "Phase 25: Session Manager Adaptation (TrameSessionManager launchVisualizationSession)"
  provides:
    - "CFDViewerBridge.ts: postMessage wrapper"
    - "TrameViewer.tsx: iframe viewer component"
    - "JobDetailPage.tsx: TrameViewer wired in"
  affects:
    - "dashboard/src/pages/JobDetailPage.tsx"
tech_stack:
  added:
    - TypeScript class (framework-agnostic)
    - React hooks (useState, useEffect, useRef, useCallback, useMemo)
    - window.postMessage API
    - iframe DOM element
key_files:
  created:
    - "dashboard/src/services/CFDViewerBridge.ts"
    - "dashboard/src/components/TrameViewer.tsx"
  modified:
    - "dashboard/src/pages/JobDetailPage.tsx"
decisions:
  - "Bridge is framework-agnostic (no React imports) so it can be reused if Vue layer changes"
  - "FilterInfo.id changed from number to string (UUID hex from trame backend)"
  - "AdvancedFilterPanel wired via bridgeSend wrapper that maps legacy protocol method names"
  - "No WebSocket code in TrameViewer — only postMessage to iframe"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-12"
  files_created: 2
  files_modified: 1
  lines_added: ~758
  commits: 3
---

# Phase 26 Plan 01 Summary: Vue Frontend + Iframe Bridge

## One-liner

PostMessage bridge (`CFDViewerBridge.ts`) and iframe viewer component (`TrameViewer.tsx`) that replaces the ParaView Web WebSocket viewer with a Vue.js trame viewer embedded via iframe.

## What Was Built

### Task 1: CFDViewerBridge.ts (commit `19414a5`)

Framework-agnostic TypeScript class providing postMessage communication between the React dashboard and the Vue.js trame iframe viewer.

**14 outbound message types:**
- `field`, `slice`, `slice_off`, `color_preset`, `scalar_range`, `volume_toggle`, `timestep`, `clip_create`, `contour_create`, `streamtracer_create`, `filter_delete`, `filter_list`, `screenshot`, `volume_status`

**7 inbound message types:**
- `ready`, `fields`, `volume_status`, `filter_response`, `filter_list`, `screenshot_data`, `camera`

**Key methods:** `send(msg)`, `onMessage(handler)` returns unsubscribe, `destroy()` removes listener.

No React dependencies.

### Task 2: TrameViewer.tsx (commit `12ad843`)

React component replacing `ParaViewViewer.tsx`. Embeds the Vue.js trame viewer as an `<iframe>` with `src={sessionUrl}`.

**State:** All viewer state mirrored from ParaViewViewer (viewerState, field, slice, color, volume, filters, timestep, camera) plus bridge state.

**Bridge lifecycle:**
- Bridge created on iframe ref via `useMemo` + `useEffect`
- `onMessage(handleBridgeMessage)` registers inbound handler
- `destroy()` called on cleanup

**All 15 control handlers** send via `bridge.send({ type: ..., ... })`.

**AdvancedFilterPanel wiring:** `bridgeSend` wrapper maps legacy protocol method names (`visualization.filters.clip.create`, etc.) to bridge message types. FilterInfo.id is `string` (UUID hex from trame).

**No WebSocket code** — confirmed by grep.

### Task 3: JobDetailPage.tsx wiring (commit `c0b369a`)

- Replaced `import ParaViewViewer from '../components/ParaViewViewer'` with `import TrameViewer from '../components/TrameViewer'`
- Replaced `<ParaViewViewer .../>` JSX with `<TrameViewer .../>` (identical props: jobId, caseDir, onError, onConnected)

## Verification

| Check | Result |
|-------|--------|
| `CFDViewerBridge.ts` exists, no React imports | PASS |
| 11+ outbound message patterns in bridge | PASS (13 matches) |
| `TrameViewer.tsx` exists, no WebSocket code | PASS (only comment mention) |
| `grep -n "ParaViewViewer" JobDetailPage.tsx` | PASS (no results) |
| `grep -n "TrameViewer" JobDetailPage.tsx` | PASS (import + JSX usage) |

## Deviations from Plan

**None** — plan executed exactly as written.

## Threat Surface

No new security surface introduced. The bridge uses `postMessage` with `origin === 'null'` check for local iframe, matching the architecture described in the plan. Session URLs are HTTP from the FastAPI backend (not user-controlled).

## Deferred Issues

None.
