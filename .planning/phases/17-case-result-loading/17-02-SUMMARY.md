---
phase: "17"
plan: "02"
subsystem: "ParaView Web Protocol Integration"
tags:
  - "paraview-web"
  - "protocol"
  - "field-selection"
  - "time-step-navigation"
  - "PV-03"
dependency_graph:
  requires:
    - "17-01: ParaView Web server launch and WebSocket lifecycle"
  provides:
    - "PV-03: Case result loading and field selection"
  affects:
    - "dashboard/src/components/ParaViewViewer.tsx"
    - "dashboard/src/services/paraviewProtocol.ts"
tech_stack:
  added:
    - "paraviewProtocol.ts: 6 message builders + 2 parsers"
  patterns:
    - "JSON-RPC style protocol over WebSocket"
    - "Message ID-based response correlation"
    - "Protocol discovery on connection"
key_files:
  created:
    - "dashboard/src/services/paraviewProtocol.ts"
  modified:
    - "dashboard/src/components/ParaViewViewer.tsx"
decisions:
  - "Use string message IDs (pv-1, pv-fields, pv-timesteps) for response correlation"
  - "Send Render message after every state change (field selection, time step change)"
  - "Parse both nested (result.fields) and flat (result[]) response formats"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-11T07:20:00Z"
  tasks_completed: 3
---

# Phase 17 Plan 02: ParaView Web Protocol Integration Summary

## One-liner

ParaView Web protocol message builders and parsers created; field selector and time step navigator now communicate with ParaView Web server via WebSocket.

## What Was Built

### paraviewProtocol.ts (New File)

Created `dashboard/src/services/paraviewProtocol.ts` with 6 message builder functions:

| Function | Purpose |
|----------|---------|
| `createOpenFOAMReaderMessage(caseDir)` | Open an OpenFOAM case reader |
| `createGetFieldsMessage()` | Request available scalar fields |
| `createFieldDisplayMessage(fieldName)` | Set active field for display |
| `createGetTimeStepsMessage()` | Request available time steps |
| `createTimeStepMessage(timeStepIndex)` | Set active time step |
| `createRenderMessage()` | Trigger render update |

Plus 2 parser functions:
- `parseAvailableFields(response)` - Extracts field list from protocol response
- `parseAvailableTimeSteps(response)` - Extracts time step list from protocol response

### ParaViewViewer.tsx Wiring

**Step 2a-2c: Import and helper function**
- Added protocol function imports
- Added `sendProtocolMessage()` helper that wraps `wsRef.current.send(JSON.stringify(message))`

**Step 2d: ws.onopen discovery**
After authentication, automatically sends:
1. OpenFOAMReader.Open with case directory
2. OpenFOAMReader.GetPropertyList to discover available fields
3. OpenFOAMReader.GetTimeSteps to discover available time steps

**Step 2e: ws.onmessage parsing**
- Parses `pv-fields` response → updates `availableFields` state
- Parses `pv-timesteps` response → updates `availableTimeSteps` state
- Falls through on non-JSON messages (normal protocol traffic)

**Step 2f: Field selector onChange**
```typescript
onChange={(e) => {
  const field = e.target.value;
  setSelectedField(field);
  sendProtocolMessage(createFieldDisplayMessage(field));
  sendProtocolMessage(createRenderMessage());
}}
```

**Step 2g: Time step navigator buttons**
Previous/Next buttons now send `createTimeStepMessage(newIndex)` + `createRenderMessage()` on click.

## Verification Results

| Command | Expected | Actual |
|---------|----------|--------|
| `grep -c "export function create" paraviewProtocol.ts` | 6 | 6 |
| `grep -c "sendProtocolMessage\|createFieldDisplayMessage\|parseAvailableFields" ParaViewViewer.tsx` | >0 | 13 |
| `grep -c "createTimeStepMessage\|createRenderMessage" ParaViewViewer.tsx` | >0 | 7 |
| `npx tsc --noEmit` | No errors | No errors |

## Commit

```
1158819 feat(17-02): wire field selector and time step navigator to ParaView Web protocol
```

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all protocol functions are fully wired with actual WebSocket communication.

## Threat Surface Scan

No new security surface introduced. All protocol messages are sent via existing authenticated WebSocket connection. Protocol functions only build JSON objects and parse responses.

---

## CHECKPOINT: Human Verification Required

Protocol wiring for field selector and time step navigator is complete.

**Human verification requires:**
1. Running ParaView Web Docker container with OpenFOAM case
2. Completed job with case directory
3. Navigate to Viewer tab → Launch → verify field/time controls work

**Verification steps:**
1. Navigate to a completed job in the Dashboard
2. Click on the job to open JobDetailPage
3. Click the "Viewer" tab
4. Click "Launch 3D Viewer" button
5. Wait for connection to establish

**Test field selector:**
- Change the selected field from the default
- Observe that the 3D display updates (color/values should change)

**Test time step navigator:**
- Click "Next" to advance to the next time step
- Observe that the 3D display updates
- Click "Previous" to go back

**Expected:** Both controls visibly affect the 3D rendering.

---

Type "approved" to mark 17-02 complete, or describe issues.
