# Feature Parity Checklist — TRAME-05 Requirements

**Plan:** 27-02
**Created:** 2026-04-11
**Test Runner:** Manual / browser-based
**Files:** `dashboard/src/components/TrameViewer.tsx`, `dashboard/src/services/CFDViewerBridge.ts`

---

## TRAME-05.1 — v1.4.0 Viewer Features (Rotation, Zoom, Slicing, Color Mapping)

| # | Feature       | Test Step                                                                 | Expected Result                        | Pass/Fail | Notes |
|---|---------------|--------------------------------------------------------------------------|----------------------------------------|-----------|-------|
| 1 | Rotation      | Open trame viewer iframe, click-drag on 3D model                        | Model rotates smoothly in all directions |           |       |
| 2 | Zoom          | Scroll mouse wheel over 3D viewport                                      | Zoom in/out smoothly                   |           |       |
| 3 | Pan           | Right-click-drag or shift-drag on 3D viewport                           | Camera pans smoothly                   |           |       |
| 4 | Slice X       | Click "X" slice button in slice controls                                 | Plane appears at configured origin on X axis |        |       |
| 5 | Slice Y       | Click "Y" slice button                                                   | Plane appears on Y axis                |           |       |
| 6 | Slice Z       | Click "Z" slice button                                                   | Plane appears on Z axis                |           |       |
| 7 | Slice Off     | Click "Off" button                                                       | All slice planes removed               |           |       |
| 8 | Color Viridis | Select "Viridis" preset button                                           | Colormap changes to Viridis gradient   |           |       |
| 9 | Color BlueRed | Select "BlueRed" preset                                                  | Colormap changes to Blue-Red gradient  |           |       |
|10 | Color Grayscale | Select "Grayscale" preset                                            | Colormap changes to grayscale          |           |       |

---

## TRAME-05.2 — Volume Rendering Toggle

| # | Feature                    | Test Step                                                                           | Expected Result                                         | Pass/Fail | Notes |
|---|----------------------------|-------------------------------------------------------------------------------------|---------------------------------------------------------|-----------|-------|
|11 | GPU detection              | Toggle volume on, open browser DevTools console                                    | GPU vendor string appears in volume_status response     |           |       |
|12 | Apple Silicon Mesa warning | Toggle volume on Apple Silicon hardware (Mesa driver)                                | Warning banner: "Apple Silicon detected: volume rendering uses Mesa software" |           |       |
|13 | Large dataset OOM guard    | Load a dataset with cell_count > 2M, toggle volume on                              | Warning banner: "Large dataset (X.XM cells): may cause memory issues" |         |       |
|14 | Volume toggle off           | Toggle volume button to "Off"                                                      | Surface rendering returns, volume disabled              |           |       |
|15 | Volume disabled without field | Click volume toggle without selecting a field                                   | Button is disabled until field is selected              |           |       |

---

## TRAME-05.3 — Filter Parameter Updates Through Bridge

| # | Filter       | Test Step                                                              | Expected Result                                    | Pass/Fail | Notes |
|---|--------------|-----------------------------------------------------------------------|----------------------------------------------------|-----------|-------|
|16 | Clip create  | Open AdvancedFilterPanel, create clip with insideOut=false, scalarValue=0 | Clip appears in viewport                          |           |       |
|17 | Clip update  | Change scalarValue from 0 to 0.5, re-apply                            | Clip re-renders at new position                   |           |       |
|18 | Contour create | Create contour with isovalues=[0.1]                                  | Isosurface appears at 0.1 value                   |           |       |
|19 | Contour update | Update to isovalues=[0.1, 0.3, 0.5]                                   | Three isosurfaces appear                          |           |       |
|20 | StreamTracer create | Create streamtracer with direction=FORWARD, maxSteps=100        | Stream lines appear from seeds                    |           |       |
|21 | StreamTracer update  | Update maxSteps to 500                                           | Stream lines extend further                       |           |       |

---

## TRAME-05.4 — Screenshot Export

| # | Feature              | Test Step                                                                          | Expected Result                                      | Pass/Fail | Notes |
|---|----------------------|------------------------------------------------------------------------------------|-------------------------------------------------------|-----------|-------|
|22 | Debounce guard       | Click Screenshot button twice in rapid succession (< 500ms apart)                  | Only one PNG download triggered                       |           |       |
|23 | Viewport resolution  | Capture screenshot, note PNG dimensions, compare to DevTools viewport size          | PNG dimensions match viewport offsetWidth x offsetHeight |         |       |
|24 | Filename format      | Check downloaded filename                                                          | Filename matches `cfd-screenshot-{YYYYMMDDHHMMSS}.png` |         |       |
|25 | Screenshot disabled during capture | Click Screenshot, observe button while capture is in progress   | Button shows disabled/spinner state                  |           |       |

---

## TRAME-05.5 — Multiple Simultaneous Filters

| # | Scenario                  | Test Step                                                              | Expected Result                                      | Pass/Fail | Notes |
|---|----------------------------|------------------------------------------------------------------------|-------------------------------------------------------|-----------|-------|
|26 | Clip + Contour simultaneous | Create clip, then create contour while clip is active                | Both clip plane and isosurface visible               |           |       |
|27 | All three filters active  | Create clip + contour + streamtracer simultaneously                    | All three filter visualizations visible              |           |       |
|28 | Delete one filter         | While clip+contour+streamtracer active, delete clip via filter panel   | Contour and streamtracer remain; clip removed       |           |       |
|29 | Filter list updates       | Create and delete several filters, observe filter list panel          | List accurately reflects all active filter IDs/types |           |       |

---

## TRAME-05.6 — Time Step Navigation

| # | Action   | Test Step                                                     | Expected Result                           | Pass/Fail | Notes |
|---|----------|--------------------------------------------------------------|--------------------------------------------|-----------|-------|
|30 | Next     | Click "Next" timestep button                                 | View advances to next time step            |           |       |
|31 | Previous | Click "Previous" timestep button                            | View returns to previous time step         |           |       |
|32 | Boundary | Click "Next" at last time step                               | Button disabled at boundary                |           |       |
|33 | Play     | If play button exists, click it                              | Animated playback through time steps       |           |       |
|34 | Time step display | Verify step counter shows "Step X / Y"                  | Counter updates correctly on navigation     |           |       |

---

## Session Isolation (Bonus)

| # | Scenario           | Test Step                                                                              | Expected Result                                     | Pass/Fail | Notes |
|---|--------------------|----------------------------------------------------------------------------------------|-----------------------------------------------------|-----------|-------|
|35 | Multi-tab session A | Open Tab 1, connect to session A, create a clip filter                                 | Clip visible in Tab 1                              |           |       |
|36 | Multi-tab session B | Open Tab 2, connect to session B, apply different color preset                         | Tab 2 shows different color preset (no cross-talk) |           |       |
|37 | Camera isolation    | Rotate camera in Tab 1, observe camera in Tab 2 (should not change)                  | Camera positions independent per session           |           |       |

---

## Summary Table

| Requirement | Description                         | Tested Date | Pass |
|-------------|-------------------------------------|-------------|------|
| TRAME-05.1  | v1.4.0 viewer features (rotation/zoom/slice/color) |             |      |
| TRAME-05.2  | Volume rendering toggle + GPU/OOM warnings |          |      |
| TRAME-05.3  | Filter parameter updates through bridge |          |      |
| TRAME-05.4  | Screenshot export (debounce/viewport/download) |        |      |
| TRAME-05.5  | Multiple simultaneous filters               |          |      |
| TRAME-05.6  | Time step navigation                      |          |      |
| Bonus        | Session isolation (multi-tab)             |          |      |

**Total:** 37 checklist items across 7 requirement groups

---

## Test Execution Log

| Date       | Tester | Items Tested | Pass | Fail | Notes |
|------------|--------|--------------|------|------|-------|
|            |        |              |      |      |       |

---

*Last updated: 2026-04-11*
