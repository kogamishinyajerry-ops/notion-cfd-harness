# Phase 14: Convergence Intelligence - Research

**Researched:** 2026-04-10
**Domain:** Real-time CFD simulation divergence detection + result summarization
**Confidence:** HIGH (architecture verified from existing Phase 12/13 implementation)

## Summary

Phase 14 implements two capabilities: (1) divergence detection using rolling 5-iteration windows per variable, firing an alert when residual increases 5 consecutive times; (2) result summary display upon convergence completion showing final pressure/velocity/Y+ metrics. The existing WebSocket streaming architecture (Phase 12) and Recharts residual chart (Phase 13) provide the foundation.

**Primary recommendation:** Implement `DivergenceDetector` as an async-aware class in `api_server/services/` that wraps the `residual_callback`, detects divergence, and broadcasts `DivergenceAlert` messages via WebSocket. On the frontend, add a `ResultSummaryPanel` component triggered when `status: "converged"` is received.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Rolling 5-iteration window per variable for divergence detection
- Divergence alert fires when residual increases 5 consecutive times
- Convergence criteria overlay at 1e-5
- MON-04: Display result summary (pressure, velocity, Y+) on convergence completion
- MON-06: Divergence detection + alert

### Claude's Discretion
- Implementation location (divergence detector in backend vs frontend)
- UI placement of divergence alert and result summary
- Alert mechanism (badge vs banner vs modal)

### Deferred Ideas (OUT OF SCOPE)
- MON-07: Multi-metric overlay display
- MON-08: 3D velocity/pressure field visualization
- MON-09: Multi-case parallel convergence comparison

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MON-04 | 收敛完成后自动展示结果摘要（压力、速度、Y+） | Section 2 (result summary metrics), Section 3 (trigger mechanism) |
| MON-06 | 收敛异常检测 + 告警（divergence detection） | Section 1 (divergence detection algorithm), Section 4 (alert integration) |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `collections.deque` | stdlib | Rolling window buffer (maxlen=5) | Thread-safe, O(1) append/pop, memory-bounded |
| Pydantic `BaseModel` | api_server dependency | `DivergenceAlert` message model | Already used for `ConvergenceMessage` in Phase 12 |
| Recharts `LineChart` | dashboard dependency (3.8.1) | Convergence criteria overlay line | Already installed, used in Phase 13 ResidualChart |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| Python `asyncio` | Async callback handling | Already used in Phase 12 executor |
| React `useState/useCallback` | Local state for alert/summary | Already used in JobDetailPage |

### No New Dependencies Required
All required primitives (deque, async, WebSocket broadcast) are already in the codebase.

---

## Architecture Patterns

### Recommended Project Structure

```
api_server/services/
├── divergence_detector.py    # NEW: Rolling window divergence detection
├── job_service.py            # MODIFY: Wire divergence detector into residual_callback

dashboard/src/
├── components/
│   ├── DivergenceAlert.tsx   # NEW: Alert banner for divergence
│   └── ResultSummaryPanel.tsx # NEW: Post-convergence metrics display
├── services/
│   └── websocket.ts          # MODIFY: Handle divergence_alert message type
└── pages/
    └── JobDetailPage.tsx     # MODIFY: Wire alert + summary components
```

### Pattern 1: Async Divergence Detection Wrapper

**What:** A `DivergenceDetector` class that wraps the existing `residual_callback` chain.

**When to use:** In `job_service._run_case()`, when setting up the `residual_callback` for `execute_streaming`.

**Example:**
```python
# api_server/services/divergence_detector.py
from collections import deque
from typing import Callable, Awaitable, Dict, Any
import asyncio

class DivergenceDetector:
    """Tracks residual history per variable with rolling 5-iteration window."""

    def __init__(self, callback: Callable[[Dict[str, Any]], Awaitable[None]], window_size: int = 5):
        self._callback = callback
        self._window_size = window_size
        # Rolling window per variable: var_name -> deque of (iteration, residual_value)
        self._history: Dict[str, deque] = {var: deque(maxlen=window_size) for var in ("Ux", "Uy", "Uz", "p")}

    async def __call__(self, residual_data: Dict[str, Any]) -> None:
        """Process residual update, detect divergence, forward to callback."""
        iteration = residual_data.get("iteration", 0)
        residuals = residual_data.get("residuals", {})
        status = residual_data.get("status", "running")

        # Check divergence for each variable
        alert_triggered = False
        for var in ("Ux", "Uy", "Uz", "p"):
            value = residuals.get(var)
            if value is None:
                continue
            history = self._history[var]
            history.append((iteration, value))

            if self._check_increase(history):
                alert_triggered = True
                break  # One alert per update, not one per variable

        # Always forward the original data
        await self._callback(residual_data)

        # If diverged, send alert
        if alert_triggered:
            await self._callback({
                **residual_data,
                "type": "divergence_alert",
                "diverged_variable": var,
                "message": f"Residual for {var} increased 5 consecutive iterations",
            })

    def _check_increase(self, history: deque) -> bool:
        """Return True if residual has increased 5 consecutive times."""
        if len(history) < self._window_size:
            return False
        values = [v for _, v in history]
        # Check strictly increasing
        return all(values[i] < values[i+1] for i in range(len(values)-1))
```

**Integration in job_service.py:**
```python
# In _run_case(), replace residual_callback with wrapped version
original_callback = residual_callback  # saved from closure
detector = DivergenceDetector(original_callback)
streaming_result = await executor.execute_streaming(
    config=config,
    residual_callback=detector,  # wrapped
)
```

**Source:** Implementation pattern verified from Phase 12 `_run_solver_streaming` callback chain.

---

### Pattern 2: Convergence Overlay on Recharts

**What:** Add a horizontal reference line at 1e-5 on the existing log-scale Y-axis.

**When to use:** In `ResidualChart.tsx` alongside the existing Ux/Uy/Uz/p lines.

**Example:**
```tsx
// In ResidualChart.tsx LineChart
<ReferenceLine
  y={1e-5}
  stroke="#f59e0b"
  strokeDasharray="5 5"
  label={{ value: "Convergence Criteria (1e-5)", position: "right", fill: "#f59e0b" }}
/>
```

**Source:** Recharts `ReferenceLine` API (verified from recharts docs).

---

### Pattern 3: Result Summary Trigger on Convergence

**What:** Frontend detects `status: "converged"` from `ResidualMessage` and renders `ResultSummaryPanel`.

**When to use:** In `JobDetailPage.tsx` WebSocket message handler.

**Example:**
```tsx
// In JobDetailPage.tsx
} else if (message.type === 'residual') {
  const residualMsg = message as ResidualMessage;
  // ...
  // Trigger result summary on convergence
  if (residualMsg.status === 'converged' && !showResultSummary) {
    setShowResultSummary(true);
  }
}
```

**Source:** `JobDetailPage.tsx` lines 149-156 already handle residual messages.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rolling window buffer | Custom list with manual index management | `collections.deque(maxlen=5)` | Memory-bounded, O(1) operations, thread-safe |
| Async callback chaining | Manual callback list management | `DivergenceDetector` wrapper class | Clean separation of concerns, testable |
| Scientific notation formatting | Custom formatter | `toExponential(2)` on number | Already used in ResidualChart tooltip |

---

## Common Pitfalls

### Pitfall 1: Divergence Detection Fires During Solver Startup
**What goes wrong:** OpenFOAM residuals can spike during mesh initialization (first 1-2 iterations), triggering false positives.
**Why it happens:** Initial residual values are typically high (1e+0 to 1e-1), then drop sharply.
**How to avoid:** Only arm divergence detection after iteration >= 5 (skip first 4 iterations).
**Warning signs:** Alert fires before iteration 10.

### Pitfall 2: Multiple Divergence Alerts
**What goes wrong:** Once diverged, every subsequent iteration sends another alert.
**Why it happens:** Divergence is a persistent state, but our check runs every iteration.
**How to avoid:** Once `diverged` status is set, stop sending further alerts for that variable until job restarts or new run.
**Warning signs:** Rapid-fire alert messages flooding WebSocket.

### Pitfall 3: Frontend Alert Overwrites Critical Error
**What goes wrong:** Divergence alert might overlap with job failure error banner.
**Why it happens:** Both are async WebSocket messages rendered in similar positions.
**How to avoid:** Use distinct visual styling (warning yellow for divergence, red for failure) and separate DOM locations.

### Pitfall 4: Stale Result Summary
**What goes wrong:** Summary displays with empty/null values because final residuals were not captured.
**Why it happens:** If `status: "converged"` callback race-condition-misses the last residual data.
**How to avoid:** Capture final residuals in the job result object (already done in `_run_solver_streaming` line 416-417 with `status: "converged"`), use that for summary not the frontend's last received message.

---

## Code Examples

### Backend: DivergenceAlert Pydantic Model

```python
# api_server/models.py — add to Convergence Models section

class DivergenceAlert(BaseModel):
    """Divergence detection alert streamed during job execution."""
    type: Literal["divergence_alert"] = "divergence_alert"
    job_id: str
    iteration: int
    diverged_variable: str  # e.g., "p", "Ux"
    current_value: float
    previous_values: list[float]  # last 5 values for context
    message: str
    timestamp: datetime
```

### Backend: WebSocket Broadcast with Alert

```python
# In job_service._run_case()
async def residual_callback(residual_data: Dict) -> None:
    # Check if this is a divergence alert (injected by detector)
    if residual_data.get("type") == "divergence_alert":
        await ws_manager.broadcast(job_id, {
            "type": "divergence_alert",
            "job_id": job_id,
            "iteration": residual_data["iteration"],
            "diverged_variable": residual_data["diverged_variable"],
            "current_value": residual_data["residuals"].get(residual_data["diverged_variable"]),
            "previous_values": [v for _, v in _history.get(residual_data["diverged_variable"], deque())],
            "message": residual_data["message"],
            "timestamp": datetime.utcnow().isoformat(),
        })
    else:
        # Normal residual broadcast
        await ws_manager.broadcast(job_id, {
            "type": "residual",
            **residual_data,
        })
```

### Frontend: DivergenceAlertMessage Type

```typescript
// dashboard/src/services/websocket.ts

export interface DivergenceAlertMessage {
  type: 'divergence_alert';
  job_id: string;
  iteration: number;
  diverged_variable: string;
  current_value: number;
  previous_values: number[];
  message: string;
  timestamp: string;
}
```

### Frontend: Alert Banner Component

```tsx
// dashboard/src/components/DivergenceAlert.tsx

interface DivergenceAlertProps {
  variable: string;
  iteration: number;
  currentValue: number;
  onDismiss: () => void;
}

export default function DivergenceAlert({ variable, iteration, currentValue, onDismiss }: DivergenceAlertProps) {
  return (
    <div className="divergence-alert-banner">
      <span className="alert-icon">⚠</span>
      <div className="alert-content">
        <strong>Divergence Detected</strong>
        <p>
          {variable} residual increased 5 consecutive iterations at iteration {iteration}.
          Current value: {currentValue.toExponential(2)}
        </p>
      </div>
      <button className="alert-dismiss" onClick={onDismiss}>×</button>
    </div>
  );
}
```

### Frontend: Result Summary Panel

```tsx
// dashboard/src/components/ResultSummaryPanel.tsx

interface ResultSummary {
  finalResiduals: { Ux?: number; Uy?: number; Uz?: number; p?: number };
  iteration: number;
  executionTime: number;
}

interface ResultSummaryPanelProps {
  summary: ResultSummary;
  onClose?: () => void;
}

export default function ResultSummaryPanel({ summary, onClose }: ResultSummaryPanelProps) {
  const formatSci = (v?: number) => v?.toExponential(4) ?? '-';

  return (
    <div className="result-summary-panel">
      <h3>Simulation Complete</h3>
      <div className="summary-grid">
        <div className="summary-item">
          <span className="summary-label">Final Iteration</span>
          <span className="summary-value">{summary.iteration}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Execution Time</span>
          <span className="summary-value">{summary.executionTime.toFixed(1)}s</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Pressure (p)</span>
          <span className="summary-value">{formatSci(summary.finalResiduals.p)}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Velocity X (Ux)</span>
          <span className="summary-value">{formatSci(summary.finalResiduals.Ux)}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Velocity Y (Uy)</span>
          <span className="summary-value">{formatSci(summary.finalResiduals.Uy)}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Velocity Z (Uz)</span>
          <span className="summary-value">{formatSci(summary.finalResiduals.Uz)}</span>
        </div>
      </div>
      <p className="summary-note">Y+ metrics require post-processing (yPlus utility) — available in Phase 15+</p>
    </div>
  );
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual log inspection | Automated divergence detection | Phase 14 | Real-time alerting, no human monitoring required |
| Post-hoc result review | Auto-display result summary | Phase 14 | Immediate insight upon convergence |

**Note on Y+:** Y+ (dimensionless wall distance) requires running OpenFOAM's `yPlus` utility post-solver. This is currently out of scope (MON-04 specifies "Y+" but the actual computation is a post-processing step not yet implemented). Display placeholder noting this is Phase 15+.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OpenFOAM `yPlus` utility output is parseable similarly to residuals | MON-04 metrics | Phase 15 might need additional parsing logic for Y+ |
| A2 | `status: "converged"` is always sent with final residuals (not just "End" line) | Result summary trigger | Summary might show stale data; verify Phase 12 executor behavior |
| A3 | No existing `divergence_alert` message type in websocket.ts | Frontend types | Name collision unlikely but possible |

---

## Open Questions

1. **Y+ Post-processing**
   - What we know: OpenFOAM has a `yPlus` utility that writes to `postProcessing/yPlus/0/yPlus.dat`
   - What's unclear: Whether to implement Y+ extraction in Phase 14 or defer to Phase 15
   - Recommendation: Phase 14 should store placeholder in summary; Phase 15 implements actual Y+ extraction

2. **Alert Persistence**
   - What we know: Divergence state persists until job is cancelled
   - What's unclear: Should alert dismiss require user action or auto-hide after N seconds?
   - Recommendation: Manual dismiss button (no auto-hide) to ensure user is aware

3. **Result Summary Data Source**
   - What we know: Phase 12 streams residuals via WebSocket; Phase 13 displays them
   - What's unclear: Should result summary use WebSocket data or REST API result object?
   - Recommendation: Use WebSocket data for real-time display, but also check `job.result` as fallback

---

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies identified for Phase 14)
> All required tools (Python asyncio, Recharts) are already part of the existing implementation.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing project standard) |
| Config file | `pytest.ini` at project root |
| Quick run command | `pytest tests/ -x -q --tb=short` |
| Full suite command | `pytest tests/ --tb=long` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MON-06 | Divergence alert fires after 5 consecutive increases | unit | `pytest tests/ -k divergence -x` | ❌ Missing |
| MON-06 | No alert fires within first 4 iterations | unit | `pytest tests/ -k divergence -x` | ❌ Missing |
| MON-04 | Result summary shows on `status: "converged"` | unit/integration | `pytest tests/ -k result_summary -x` | ❌ Missing |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q --tb=short`
- **Per wave merge:** `pytest tests/ --tb=long`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_divergence_detector.py` — tests `DivergenceDetector` class
- [ ] `tests/test_result_summary.py` — tests `ResultSummaryPanel` rendering
- [ ] `tests/conftest.py` — shared fixtures for mock WebSocket messages

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Pydantic models (`DivergenceAlert`, `ResultSummary`) validate all incoming residual data before processing |
| V4 Access Control | no | WebSocket auth already handled in Phase 12 (`token` query param) |

### No New Security Concerns
Phase 14 adds only:
- In-memory rolling window (no persistent storage of residuals)
- WebSocket message forwarding (existing infrastructure)
- UI rendering of already-validated numeric data

---

## Sources

### Primary (HIGH confidence)
- `api_server/models.py` lines 219-227 — `ConvergenceMessage` model structure
- `api_server/services/job_service.py` lines 160-211 — `execute_streaming` integration
- `knowledge_compiler/phase2/execution_layer/openfoam_docker.py` lines 241-318 — streaming executor
- `dashboard/src/services/websocket.ts` — WebSocket message types
- `dashboard/src/components/ResidualChart.tsx` — existing Recharts integration

### Secondary (MEDIUM confidence)
- Recharts `ReferenceLine` API — convergence criteria overlay
- Python `collections.deque` documentation — rolling window implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all required primitives are existing codebase dependencies
- Architecture: HIGH — verified from Phase 12/13 implementation paths
- Pitfalls: MEDIUM — based on known OpenFOAM solver behavior patterns

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (30 days — architecture is stable)
