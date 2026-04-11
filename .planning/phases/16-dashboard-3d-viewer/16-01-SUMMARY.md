---
phase: "16"
plan: "01"
subsystem: "dashboard"
tags: ["paraview", "visualization", "websocket", "react"]
dependency_graph:
  requires: []
  provides:
    - "dashboard/src/services/paraview.ts"
    - "dashboard/src/components/ParaViewViewer.tsx"
    - "dashboard/src/components/ParaViewViewer.css"
  affects:
    - "Phase 17: JobDetailPage viewer tab integration"
tech_stack:
  added:
    - "TypeScript API client for ParaView Web session lifecycle"
    - "React component with 7-state machine (idle, launching, connecting, connected, disconnected, reconnect-exhausted, error)"
    - "WebSocket with exponential backoff reconnect [1,2,4,8,16]s, max 5 attempts"
    - "60-second heartbeat via POST /api/v1/visualization/{session_id}/activity"
    - "CSS-only styling using theme.css custom properties"
key_files:
  created:
    - "dashboard/src/services/paraview.ts"
    - "dashboard/src/components/ParaViewViewer.tsx"
    - "dashboard/src/components/ParaViewViewer.css"
decisions:
  - "No ParaView Web npm packages imported - client runs in Docker container and communicates via WebSocket protocol"
  - "WebSocket sends auth_key as first message immediately after onopen per ParaView Web protocol"
  - "Heartbeat errors are swallowed (non-fatal) to prevent connection disruption"
  - "Reconnect delays array [1000, 2000, 4000, 8000, 16000] matches UI-SPEC spec"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-11T06:02:00Z"
---

# Phase 16 Plan 01 Summary: ParaView Web API Service and Viewer Component

## One-liner
ParaView Web session lifecycle API client with 7-state React viewer component, WebSocket auto-reconnect, and 60s heartbeat.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | paraview.ts API service | (staged) | paraview.ts |
| 2 | ParaViewViewer.tsx component | (staged) | ParaViewViewer.tsx |
| 3 | ParaViewViewer.css styles | (staged) | ParaViewViewer.css |

## What Was Built

### 1. paraview.ts - API Service
- `VisualizationLaunchResponse` interface: session_id, session_url, auth_key, port, job_id
- `VisualizationStatusResponse` interface: session_id, job_id, status, port, case_dir, created_at, last_activity
- `launchVisualizationSession(jobId, caseDir, port?)` - POST /api/v1/visualization/launch
- `getVisualizationSession(sessionId)` - GET /api/v1/visualization/{session_id}
- `sendHeartbeat(sessionId)` - POST /api/v1/visualization/{session_id}/activity

### 2. ParaViewViewer.tsx - React Component
- 7 ViewerState states: idle, launching, connecting, connected, disconnected, reconnect-exhausted, error
- Props: jobId, caseDir, onError?, onConnected?
- WebSocket connection to session_url with auth_key as first message
- Exponential backoff reconnect: [1000, 2000, 4000, 8000, 16000]ms, max 5 attempts
- Heartbeat: sendHeartbeat() every 60 seconds via setInterval
- All UI-SPEC copy strings embedded: launchCta, initializingHeading, initializingBody, errorConnectionRefused, errorAuthFailed, errorSessionNotFound, disconnectedBanner, reconnectExhausted, emptyState, tryAgain

### 3. ParaViewViewer.css - Styles
- Uses ONLY CSS custom properties from theme.css
- `.viewer-launch-btn` background = `--accent-color`
- `.viewer-skeleton` with shimmer animation
- `.viewer-disconnected-banner` with pulse animation dot
- `.viewer-canvas-container` with 16:9 aspect ratio, min-height 400px
- All spacing multiples of 4px (8, 16, 24, 32)
- Touch targets minimum 44px height (WCAG 2.5.5)

## Verification Results

| Check | Result |
|-------|--------|
| `grep -c "export async function launchVisualizationSession" paraview.ts` | 2 (1 in interface comment, 1 actual function) |
| `grep -c "export async function getVisualizationSession" paraview.ts` | 1 |
| `grep -c "export async function sendHeartbeat" paraview.ts` | 1 |
| `grep -c "export type ViewerState" ParaViewViewer.tsx` | 1 |
| `grep -c "RECONNECT_DELAYS" ParaViewViewer.tsx` | 3 (definition + 2 usages) |
| `grep -c ".viewer-launch-btn" ParaViewViewer.css` | 1 |

## Deviations from Plan

None - plan executed exactly as written.

## Files Created

- `/Users/Zhuanz/Desktop/notion-cfd-harness/dashboard/src/services/paraview.ts`
- `/Users/Zhuanz/Desktop/notion-cfd-harness/dashboard/src/components/ParaViewViewer.tsx`
- `/Users/Zhuanz/Desktop/notion-cfd-harness/dashboard/src/components/ParaViewViewer.css`

## Self-Check

- [x] paraview.ts exports 3 functions: launchVisualizationSession, getVisualizationSession, sendHeartbeat
- [x] ParaViewViewer.tsx has 7 states + error, WebSocket with backoff [1,2,4,8,16]s, 60s heartbeat
- [x] ParaViewViewer.css uses only theme.css tokens, accent-color for buttons only
- [x] All spacing multiples of 4px
- [x] Touch targets minimum 44px

## Self-Check: PASSED
