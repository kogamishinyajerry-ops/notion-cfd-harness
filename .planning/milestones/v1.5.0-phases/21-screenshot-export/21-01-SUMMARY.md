---
phase: 21
plan: "01"
subsystem: dashboard / ParaView Web viewer
tags: [screenshot, PNG, viewport, ParaView-Web]
dependency_graph:
  requires: []
  provides:
    - dashboard/src/services/paraviewProtocol.ts
      - createScreenshotMessage(viewportWidth, viewportHeight)
    - dashboard/src/components/ParaViewViewer.tsx
      - screenshotCapturing state
      - handleScreenshot debounced callback
      - pv-screenshot response parser
      - renderScreenshotButton()
    - dashboard/src/components/ParaViewViewer.css
      - .screenshot-btn
      - .screenshot-spinner
  affects:
    - ParaViewViewer component (SHOT-01.1/01.2/01.3/01.4)
tech_stack:
  added:
    - viewport.image.render RPC call (ParaView Web built-in)
    - base64-to-Blob download pattern
    - debounce via screenshotTimeoutRef + 500ms setTimeout
  patterns:
    - Message builder pattern (paraviewProtocol.ts) — consistent with all other RPCs
    - useCallback with debounce guard
    - DOM-based viewport dimension detection (offsetWidth/offsetHeight)
key_files:
  created: []
  modified:
    - dashboard/src/services/paraviewProtocol.ts
    - dashboard/src/components/ParaViewViewer.tsx
    - dashboard/src/components/ParaViewViewer.css
key_decisions:
  - "SHOT-01.2 enforced: passing offsetWidth/offsetHeight from DOM ensures captured resolution matches display, not internal buffer"
  - "SHOT-01.4 debounce: screenshotTimeoutRef guard prevents rapid re-triggers; 500ms re-enable window prevents WS flooding"
  - "SHOT-01.3 async UX: button disabled + spinner immediately on click; WebSocket response triggers download asynchronously"
metrics:
  duration: 91s
  tasks_completed: 3
  files_modified: 3
  completed: "2026-04-11"
---

# Phase 21 Plan 01: Screenshot Export Summary

## One-liner

PNG screenshot export via ParaView Web `viewport.image.render` RPC with debounce, viewport-dimension fidelity, and async non-blocking UI.

## What Was Built

### SHOT-01.1: Screenshot RPC message builder
Added `createScreenshotMessage(viewportWidth, viewportHeight)` to `paraviewProtocol.ts`. Builds a `viewport.image.render` RPC with `{ quality: 95, size: [width, height] }` params. ID is `pv-screenshot` for response routing.

### SHOT-01.2: Viewport resolution enforcement
`handleScreenshot` reads `offsetWidth`/`offsetHeight` directly from the `#paraview-viewport` DOM element. These values are passed to `createScreenshotMessage`, ensuring the captured PNG matches the displayed viewport, not the internal render buffer.

### SHOT-01.3: Non-blocking async UI
`screenshotCapturing` boolean state drives button disabled state and spinner display. Button is disabled immediately on click (non-blocking — main thread not blocked). Download is triggered asynchronously in the `ws.onmessage` handler upon RPC response.

### SHOT-01.4: Debounce
`screenshotTimeoutRef` tracks pending re-enable timer. Both `screenshotCapturing` and `screenshotTimeoutRef` are checked at the top of `handleScreenshot` — rapid clicks within the 500ms window are silently ignored. Cleanup useCallback clears the timer on unmount.

### Base64 decode and download
On receiving `pv-screenshot` response, the base64 image string is decoded to an ArrayBuffer, wrapped in a Blob, object URL is created, an anchor is appended/clicked/removed, and the URL is revoked.

## Files Modified

| File | Change |
|------|--------|
| `dashboard/src/services/paraviewProtocol.ts` | Added `createScreenshotMessage()` at end of file |
| `dashboard/src/components/ParaViewViewer.tsx` | Added import, state, ref, cleanup, `handleScreenshot`, response parser in `ws.onmessage`, `renderScreenshotButton()`, updated `connected` case div |
| `dashboard/src/components/ParaViewViewer.css` | Appended `.screenshot-btn` and `.screenshot-spinner` CSS |

## Verification

```bash
grep -n "createScreenshotMessage" dashboard/src/services/paraviewProtocol.ts
# 271:export function createScreenshotMessage(...)

grep -c "handleScreenshot\|screenshotCapturing\|pv-screenshot\|createScreenshotMessage" dashboard/src/components/ParaViewViewer.tsx
# 4

grep -c "screenshot-btn\|screenshot-spinner" dashboard/src/components/ParaViewViewer.css
# 2
```

All checks passed.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| None | — | `viewport.image.render` is a built-in ParaView Web RPC; no new endpoints or auth paths introduced. Base64 decode is client-side only. |

## Known Stubs

None.
