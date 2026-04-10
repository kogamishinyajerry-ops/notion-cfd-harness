# Phase 12: Residual Streaming Backend - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

OpenFOAM solver residual data is parsed from log output and streamed via WebSocket to the React dashboard in real-time. Job abort capability via Docker container management.

**This phase delivers:**
- MON-01: Residual data WebSocket push (≤500ms debounce)
- MON-05: Job abort button

</domain>

<decisions>
## Implementation Decisions

### Residual Parser
- **D-01:** Extend existing `Monitor` class — Add `stream_residuals()` async generator method to Monitor. Keeps related logic together. `Monitor` in `knowledge_compiler/orchestrator/monitor.py` is the canonical location.

### Job Abort
- **D-02:** Container ID tracking + `docker kill` — Remove `--rm` flag from Docker run command. Track container ID in `_ACTIVE_JOBS` dict. On abort, call `docker kill <container_id>`. Clean container after completion.

### WebSocket Message Format
- **D-03:** Separate `residual` message type — New `ConvergenceMessage` Pydantic model with `type: "residual"`. Clean, explicit, frontend subscribes to `residual` events. Not piggybacking on progress.

### Streaming Architecture
- **D-04:** ResidualStreamer as asyncio.Task alongside solver subprocess — Debounce to ≤500ms. Use `asyncio.create_subprocess_exec()` for Docker with streaming stdout line-by-line.

### Monitor State Extension
- **D-05:** `Monitor.state` already has `DIVERGED` enum value — use it. Rolling 5-iteration window per variable for divergence detection (deferred to Phase 14, but Monitor should track it).

### Key Integration Points
- `api_server/services/job_service.py` — Replace fake progress loop with real residual streaming
- `api_server/services/websocket_manager.py` — Add `ConvergenceMessage` broadcast
- `api_server/models.py` — Add `ConvergenceMessage` model
- `knowledge_compiler/orchestrator/monitor.py` — Add `stream_residuals()` generator method

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### WebSocket
- `api_server/services/websocket_manager.py` — Existing WebSocket fan-out manager
- `api_server/routers/websocket.py` — Existing WS endpoint `/ws/jobs/{job_id}`

### Job Service
- `api_server/services/job_service.py` — Current job execution (fake progress loop)

### Monitor
- `knowledge_compiler/orchestrator/monitor.py` — Existing Monitor class to extend
- `knowledge_compiler/orchestrator/contract.py` — MonitorReport, ConvergenceStatus dataclasses

### Docker
- `knowledge_compiler/openfoam_docker.py` — Existing Docker executor (Phase 7)

### API Models
- `api_server/models.py` — Existing Pydantic models

### Dashboard
- `dashboard/src/services/websocket.ts` — Existing WS client

</canonical_refs>

<codebase_context>
## Existing Code Insights

### Reusable Assets
- `Monitor._parse_residuals()` — Existing regex parsing but for one-shot batch (not streaming)
- `WebSocketManager.broadcast()` — Already handles multi-subscriber fan-out
- `ConvergenceEvent` dataclass — Already defined in contract.py

### Integration Points
- JobService calls Docker executor → subprocess stdout → Monitor parses → WebSocketManager broadcasts → dashboard
- `_ACTIVE_JOBS` dict in job_service.py tracks active asyncio.Tasks (can add container_id field)

### Constraints
- Recharts already installed in dashboard (no new npm packages needed)
- OpenFOAM log format: `Initial residual: X, Final residual: Y, ...`
- Docker executor uses `subprocess.run()` — needs to become async streaming

</codebase_context>

<specifics>
## Specific Ideas

- ResidualParser regex: `r"Initial residual:\s+(\S+).*?Final residual:\s+(\S+)"` for `p` and `U` residuals
- Container ID captured from `docker run` output
- Debounce: 500ms sliding window, only broadcast when new residual values arrive

</specifics>

<deferred>
## Deferred Ideas

- **Multi-metric overlay (MON-07)** — Phase 13 or later
- **3D visualization (MON-08)** — Phase 14+
- **Divergence detection alert (MON-06)** — Phase 14 (Monitor tracks state, Phase 14 adds alerting)
- **Simulation mid-run parameter adjustment** — Out of scope

</deferred>
