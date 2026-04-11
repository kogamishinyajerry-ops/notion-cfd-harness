---
phase: 26-vue-frontend-iframe-bridge
reviewed: 2026-04-12T12:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - dashboard/src/services/CFDViewerBridge.ts
  - dashboard/src/components/TrameViewer.tsx
  - dashboard/src/pages/JobDetailPage.tsx
  - trame_server.py
findings:
  critical: 2
  warning: 5
  info: 6
  total: 13
status: issues_found
---

# Phase 26: Code Review Report

**Reviewed:** 2026-04-12
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 26 implements a Vue iframe postMessage bridge for the Trame 3D viewer migration. The architecture is sound (framework-agnostic bridge class, clean TypeScript types), but two critical bugs were found: a callback invocation bug that prevents error propagation, and a widespread use of `postMessage` with `targetOrigin: '*'` which is a security vulnerability. Several logic errors (stale closures, unused variable, empty catch blocks) and one confirmed typo in a ParaView parameter are also present.

---

## Critical Issues

### CR-01: Error callback invoked instead of passed — error never propagates

**File:** `dashboard/src/components/TrameViewer.tsx:258`
**Issue:** `onError` is called as a function invocation (`onError(errorMessage)`) rather than being passed as a callback. Since `errorMessage` is `''` at the time of the catch block (the `setErrorMessage` call is on the line above but React state updates are asynchronous), the callback receives an empty string. More critically, the intent is clearly to pass the error handler for later invocation, not call it immediately.
**Fix:**
```typescript
// WRONG (current):
if (onError) onError(errorMessage);

// CORRECT:
onError?.(err instanceof Error ? err.message : 'Launch failed');
```
This bug means `onError` prop is completely non-functional.

---

### CR-02: postMessage uses wildcard targetOrigin `'*'` — sensitive data leakage risk

**File:** `dashboard/src/services/CFDViewerBridge.ts:74`, `trame_server.py:418-420, 446-449, 664`
**Issue:** All postMessage calls use `targetOrigin: '*'`, which allows any website to receive messages intended for the iframe. Screenshot data (base64 images containing CFD visualization), camera positions, and filter configurations are all broadcast to `window.parent` with no origin restriction.

Similarly, the Python trame backend uses `window._trameBridge.postMessage(..., '*')` to send messages to the parent React app, and the injected JS `postMessage({type:'ready'}, '*')` is also unrestricted.
**Fix:**
```typescript
// CFDViewerBridge.ts:74 — use the actual iframe origin when available
const origin = this.iframe.src.startsWith('http') ? new URL(this.iframe.src).origin : '*';
this.iframe.contentWindow?.postMessage(msg, origin);
```
For the Python side, the origin of the parent page should be known (same origin in production) and should replace `'*'`. If cross-origin is required, use `event.source.postMessage` from the inbound listener instead of hardcoding `'*'`.

---

## Warnings

### WR-01: Stale closure in handleLaunch — errorMessage dependency is always ''

**File:** `dashboard/src/components/TrameViewer.tsx:258-260`
**Issue:** `errorMessage` is in the dependency array of `useCallback` at line 260, but it is read inside the callback before `setErrorMessage` is called (lines 248, 256). Due to React's closure semantics, `errorMessage` inside the callback will always be the value from the last render, not the one set in the current invocation. This means `onError(errorMessage)` receives a stale value.
**Fix:** Remove `errorMessage` from the dependency array. The error is already captured via `err instanceof Error ? err.message : 'Launch failed'`:
```typescript
}, [jobId, caseDir, onError]); // errorMessage removed
```

---

### WR-02: Stale closure in WebSocket subscription — job.status, showResultSummary missing from dependency array

**File:** `dashboard/src/pages/JobDetailPage.tsx:175`
**Issue:** `job?.status` and `showResultSummary` are used inside the useEffect callback but are NOT in the dependency array. While `job` is in the array, accessing `job?.status` creates a new reference every render if status hasn't changed. More critically, `showResultSummary` is captured in a stale closure — the comparison `!showResultSummary` in the residual handler may see an outdated value.
**Fix:**
```typescript
// Add to dependency array:
}, [jobId, job?.status, showResultSummary]);
```

---

### WR-03: Empty catch blocks swallow errors silently

**File:** `dashboard/src/components/TrameViewer.tsx:199, 225`, `trame_server.py:158-159, 171-172, 199-200, 212-213, 472, 487, 517-518, 534-535, 547-548`
**Issue:** Empty `except Exception: pass` blocks in Python and silent `catch {}` in TypeScript make debugging impossible. At minimum, errors should be logged.
**Fix (Python example):**
```python
# Instead of:
except Exception:
    pass
# Use:
except Exception as e:
    logger.debug("field change failed: %s", e)
```
For TypeScript:
```typescript
// Instead of:
catch { }
// Use:
catch (err) {
  console.warn('[CFDViewerBridge] send failed:', err);
}
```

---

### WR-04: on_color_preset_change defines lut_map but never applies it

**File:** `trame_server.py:507-518`
**Issue:** A `lut_map` dictionary is defined to map preset names to ParaView LUT names ("Viridis" -> "Viridis", "BlueRed" -> "BlueRedRainbow", "Grayscale" -> "Grayscale"), but the body of the function only calls `simple.Render()` without actually setting the LookupTable on the display properties. The color preset command has no effect.
**Fix:**
```python
lut_map = {"Viridis": "Viridis", "BlueRed": "BlueRedRainbow", "Grayscale": "Grayscale"}
try:
    display = simple.GetDisplayProperties()
    if display is not None:
        lut_name = lut_map.get(color_preset, "Viridis")
        # Apply LUT via color map / LookupTable
        # e.g., simple.SetLookupTable(display, lut_name)
        simple.Render()
        _ctrl.view_update()
except Exception:
    pass
```

---

### WR-05: Screenshot timeout ref cleaned up in wrong useEffect

**File:** `dashboard/src/components/TrameViewer.tsx:236-241`
**Issue:** `screenshotTimeoutRef` is created at line 109 but its cleanup is inside the unmount useEffect (line 236). However, the screenshot timeout is also cleared inside the `screenshot_data` handler (lines 180-186). If the component is unmounted while a screenshot is in progress, the timeout ref cleanup at line 239 works correctly. However, the interaction between `screenshotCapturing` state and the timeout ref creates a race: the timeout's callback at line 183 resets `screenshotCapturing`, but if the component unmounts before the timeout fires, the ref cleanup handles it. The design is fragile — the timeout callback at line 183 should check if the component is still mounted.
**Fix:** Add a mounted flag:
```typescript
const mountedRef = useRef(true);
useEffect(() => {
  return () => { mountedRef.current = false; };
}, []);
```
Then in the timeout callback:
```typescript
screenshotTimeoutRef.current = setTimeout(() => {
  if (mountedRef.current) setScreenshotCapturing(false);
  screenshotTimeoutRef.current = null;
}, 500);
```

---

## Info

### IN-01: Unused CSS import references ParaView naming

**File:** `dashboard/src/components/TrameViewer.tsx:11`
**Issue:** `import './ParaViewViewer.css';` references a file named after the old ParaView viewer that TrameViewer replaces. While functional (the CSS class names still match), this creates a confusing naming mismatch.
**Fix:** Rename to `TrameViewer.css`.

---

### IN-02: Missing console.warn for non-fatal heartbeat failure

**File:** `dashboard/src/components/TrameViewer.tsx:220-226`
**Issue:** Heartbeat errors are caught and silently swallowed. If heartbeats are failing, operators have no indication.
**Fix:** Add `console.warn('[TrameViewer] heartbeat failed:', err);` inside the catch block.

---

### IN-03: Contour filter parameter has a leading space typo

**File:** `trame_server.py:284`
**Issue:** `contour.ContourBy = ["POINTS", " scalars"]` has a leading space before "scalars". The comment says it is "preserved from v1.5.0" — confirm this is intentional. If not, fix to `"scalars"`.
**Fix:** Verify against ParaView documentation. If unintentional, change to:
```python
contour.ContourBy = ["POINTS", "scalars"]
```

---

### IN-04: Debug console.log in production callback

**File:** `dashboard/src/pages/JobDetailPage.tsx:377`
**Issue:** `onConnected={() => console.log('Viewer connected')}` is a debug artifact left in a production callback prop.
**Fix:** Remove the console.log, or use a proper logging mechanism if behavioral tracking is needed.

---

### IN-05: handleSliceOriginChange always resets Y and Z to 0

**File:** `dashboard/src/components/TrameViewer.tsx:365`
**Issue:** When the slice origin slider changes, the new origin is always `[val, 0, 0]`. Only the X component is user-adjustable. This is a UX limitation but may be intentional. If so, add a comment explaining this constraint.

---

### IN-06: bridgeSend type cast uses Record<string, unknown> for msg

**File:** `dashboard/src/components/TrameViewer.tsx:325-327`
**Issue:** `bridgeSend` accepts `Record<string, unknown>` and casts `method` and `params` via `as string` and `as Record<string, unknown>`. This type-unsafe approach could cause runtime errors if the caller passes malformed data. No validation is performed before the cast.
**Fix:** Define a strict union type for the method/params pairs and use discriminated unions instead of runtime casting.

---

_Reviewed: 2026-04-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
