# Phase 20 Plan 01 Summary: ParaViewWebVolumeRendering Protocol + Volume Toggle UI

## Overview
**Plan:** 20-01 | **Phase:** 20-volume-rendering | **Status:** Complete
**Subsystem:** ParaView Web Volume Rendering | **Tags:** `paraview` `volume-rendering` `protocol`

## One-liner
ParaViewWebVolumeRendering protocol class (4 RPCs) with GPU detection and volume toggle UI in the 3D viewer dashboard.

## Requirements Covered
| Requirement | Description | Status |
|-------------|-------------|--------|
| VOL-01.1 | Volume rendering toggle RPC | Implemented |
| VOL-01.2 | GPU availability status RPC | Implemented |
| VOL-01.3 | Cell count warning status RPC | Implemented |

## What Was Built

### Backend: ParaViewWebVolumeRendering Protocol (`api_server/services/paraview_adv_protocols.py`)
- **`ParaViewWebVolumeRendering`** class extending `ParaViewWebProtocol`
- **`_detect_gpu()`** — Static method that runs `eglinfo` subprocess to detect NVIDIA/Mesa/unknown GPU vendor. Results cached in class-level `_gpu_vendor_cache` and `_gpu_available_cache`.
- **`visualization.volume.rendering.status`** RPC (VOL-01.2/01.3) — Returns `enabled`, `field_name`, `gpu_available`, `gpu_vendor`, `cell_count`, `cell_count_warning` (warns if >2M cells)
- **`visualization.volume.rendering.toggle`** RPC (VOL-01.1) — Toggles between `SetRepresentationToVolume()` and `SetRepresentationToSurface()`, uses `simple._create_vtkSmartVolumeMapper()` for GPU-accelerated rendering

### Frontend: Protocol Message Builders (`dashboard/src/services/paraviewProtocol.ts`)
- **`createVolumeRenderingToggle(fieldName, enabled)`** — Builds RPC message for toggle RPC
- **`createVolumeRenderingStatus()`** — Builds RPC message for status query
- **`parseVolumeRenderingStatus(response)`** — Parses status response into `VolumeRenderingStatus` interface with GPU warning and cell count warning detection
- **`VolumeRenderingStatus` interface** — TypeScript interface for status response shape

### Frontend: Volume Toggle UI (`dashboard/src/components/ParaViewViewer.tsx`)
- **New state:** `volumeEnabled` (bool), `volumeWarning` (string | null)
- **On connect:** Polls `createVolumeRenderingStatus()` to detect GPU and cell count
- **On response:** Parses status, builds warning messages for Apple Silicon/Mesa, unknown GPU, and large datasets (>2M cells)
- **`renderVolumeControls()`** — Warning banner + On/Off toggle button (disabled when no field selected)
- **Render order:** `renderFieldSelector()` → `renderSliceControls()` → `renderColorPresetControls()` → `renderVolumeControls()` → `renderScalarRangeControls()` → `renderTimeStepNavigator()`

### CSS: Volume Controls Styling (`dashboard/src/components/ParaViewViewer.css`)
- `.volume-controls` — Flex column, secondary background
- `.volume-warning-banner` — Red-tinted alert banner with `!` icon
- `.volume-toggle-btn` — 32px height toggle button (On/Off), accent color when active
- `.volume-hint` — Secondary text hint below toggle

## Files Changed

| File | Change |
|------|--------|
| `api_server/services/paraview_adv_protocols.py` | Replaced placeholder with `ParaViewWebVolumeRendering` class |
| `dashboard/src/services/paraviewProtocol.ts` | Added 3 new exports + `VolumeRenderingStatus` interface |
| `dashboard/src/components/ParaViewViewer.tsx` | Added state, polling, parsing, render function, render order update |
| `dashboard/src/components/ParaViewViewer.css` | Appended volume controls CSS |

## Verification Results
- Python syntax check: PASS
- Frontend function exports: 3/3 found
- ParaViewViewer wiring: 6 references
- CSS class names: 3/3 found

## Key Decisions
- GPU detection via `eglinfo` subprocess (EGL vendor string parsing) — standard approach for ParaView Web GPU detection
- Cell count warning threshold: 2,000,000 cells (configurable in protocol)
- Apple Silicon detection: Identifies Mesa/llvmpipe as software rendering with warning
- Volume toggle disabled when no field selected (prevents invalid state)
