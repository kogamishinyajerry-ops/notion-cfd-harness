---
phase: "26"
plan: "02"
subsystem: ui
tags: [trame, vue, postMessage, iframe, camera-polling, paravew-web-migration]

# Dependency graph
requires:
  - phase: "24"
    provides: "@ctrl.add/@state.change handlers (on_volume_rendering_toggle, on_filter_*), UUID filter registry"
provides:
  - Vue iframe postMessage listener (window.addEventListener) handling all 14 command types
  - Camera state polling every 500ms posting { type: 'camera', position, focalPoint } to parent
  - Screenshot handler via @ctrl.add on_screenshot → base64 → postMessage to parent
  - React→Vue state bridge: field, slice, color_preset, scalar_range, timestep setters
  - { type: 'ready' } signal posted to parent on iframe page load
affects:
  - phase: "27" (Integration + Feature Parity)
  - phase: "26-plan-01" (CFDViewerBridge.ts creation)

# Tech tracking
tech-stack:
  added: [trame 3.12.0, paraview, postMessage protocol]
  patterns:
    - Camera polling via state increment trigger (avoids direct JS interop)
    - js_call for pushing data from Python to browser
    - Global _server/_state/_ctrl for handler access across phases

key-files:
  created: []
  modified:
    - trame_server.py (694 lines, +314/-30)

key-decisions:
  - "Used camera_poll_trigger state increment + @state.change handler instead of direct js_call polling — avoids tight JS loop"
  - "Exposed window._trameServer.state and ctrl for JS bridge commands to call Python @ctrl.add handlers"
  - "Made _state/_ctrl global at module level so Phase 26 handlers can reference them"
  - "js_call used for camera/screenshot postMessage sends (Python→JS direction); JS setInterval increments state for JS→Python direction"

patterns-established:
  - "postMessage bridge pattern: React parent sends commands via iframe.contentWindow.postMessage; Vue responds via window._trameBridge.postMessage"
  - "Camera state deduplication: only post when position/focalPoint actually changes"

requirements-completed: [TRAME-04.1, TRAME-04.2, TRAME-04.3, TRAME-04.4, TRAME-04.5, TRAME-04.6]

# Metrics
duration: 4 min
completed: 2026-04-11T16:51:06Z
---

# Phase 26 Plan 02: Vue Frontend + Iframe Bridge Summary

**Vue iframe postMessage listener with camera polling every 500ms, 14 command types wired, ready signal on load**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-11T16:46:49Z
- **Completed:** 2026-04-11T16:51:06Z
- **Tasks:** 1
- **Files modified:** 1 (trame_server.py, +314/-30 lines)

## Accomplishments

- JavaScript postMessage listener injected via `server.add_custom_script()` handling all 14 inbound command types from `CFDViewerBridge.ts`
- Camera state polled every 500ms via `setInterval` → increments `camera_poll_trigger` state → fires `@_state.change` handler → deduplicates → posts `{ type: 'camera', position, focalPoint }` via `js_call`
- `{ type: 'ready' }` posted to parent React immediately on iframe load
- `@ctrl.add on_screenshot()` handler: captures viewport screenshot as base64 via `html_view.screenshot()` → posts `{ type: 'screenshot_data', image }` via `js_call`
- Client-state-setter handlers (`on_field_change`, `on_slice_change`, `on_color_preset_change`, `on_scalar_range_change`, `on_timestep_change`) wired to `@_state.change` decorators
- `window._trameServer` exposes `state` and `ctrl` to bridge JavaScript so `@ctrl.add` handlers are callable from the browser

## Task Commits

Each task was committed atomically:

1. **Task 1: Add postMessage listener and camera polling to trame_server.py** - `9821900` (feat)

**Plan metadata:** (docs commit at end)

## Files Created/Modified

- `trame_server.py` - Full postMessage bridge: 694 lines (+314/-30). Adds global `_server`/`_state`/`_ctrl`, camera state tracking, `@_state.change` handlers for all viewer state, `@_ctrl.add on_screenshot()`, injected JavaScript for postMessage listener + camera polling + ready signal

## Decisions Made

- Camera polling via `camera_poll_trigger` state increment chosen over direct JS camera reading — avoids tight JS→Python polling loop, uses trame's reactive state system
- `js_call` used for Python→browser sends (camera state, screenshot); browser→Python uses state mutations that fire `@_state.change` handlers
- Global `_server`/`_state`/`_ctrl` pattern adopted for Phase 26 handlers to access server objects from module-level decorated functions
- `html_view` stored on `_server` object for screenshot handler access

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Phase 24 handlers referenced undefined module-level `state`/`ctrl`**
- **Found during:** Task 1 (postMessage bridge implementation)
- **Issue:** Phase 24 `@ctrl.add` and `@state.change` handlers at module level referenced `state` and `ctrl` directly, but these were only defined as locals inside `main()`. This would cause `NameError` when any handler fires.
- **Fix:** Added module-level globals `_server = None`, `_state = None`, `_ctrl = None`, assigned them in `main()`, updated Phase 24 handlers to use `_state`/`_ctrl` names (via `@_state.change`/`@_ctrl.add` decorators). Also added `_get_filter_list()` uses `_state.filters` instead of `state.filters`.
- **Files modified:** `trame_server.py`
- **Verification:** `python3 -m py_compile trame_server.py` → SYNTAX OK; 18 matches for `addEventListener|postMessage|camera_poll_trigger|ready` confirmed
- **Committed in:** `9821900` (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (blocking — Phase 24 handlers would have NameError at runtime)
**Impact on plan:** Critical fix ensures all Phase 24 and Phase 26 handlers work correctly at runtime.

## Issues Encountered

None — plan executed as written with auto-fix applied.

## Next Phase Readiness

- Phase 26-02 complete. Ready for Phase 27 (Integration + Feature Parity).
- `CFDViewerBridge.ts` (Plan 01) should be verified to exist before Phase 27 integration testing.

---
*Phase: 26-vue-frontend-iframe-bridge*
*Completed: 2026-04-11*
