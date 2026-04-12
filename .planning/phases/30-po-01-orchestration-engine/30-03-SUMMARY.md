---
phase: 30-po-01-orchestration-engine
plan: "03"
subsystem: orchestration
tags: [pipeline, websocket, event-bus, PIPE-05, heartbeat, replay]

# Dependency graph
requires:
  - phase: 30-po-01-orchestration-engine
    provides: PipelineExecutor, PipelineEvent stub, broadcast_pipeline_event stub
provides:
  - PipelineEventBus with global monotonic sequence counter
  - 100-event ring buffer per pipeline (BUFFER_SIZE = 100)
  - subscribe()/unsubscribe() per pipeline asyncio.Queue
  - replay_from(pipeline_id, last_seq=N) for reconnect replay
  - broadcast_pipeline_event() wired to singleton PipelineEventBus
  - /ws/pipelines/{pipeline_id} endpoint with 30-second heartbeat
  - Pipeline ID validated in DB before accepting WebSocket connection
affects:
  - 30-po-01 plan 04 — cleanup handler + control endpoints
  - 31-pipeline-rest-api-react-dashboard — WebSocket endpoint for live dashboard

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Thread-safe PipelineEventBus with threading.Lock (called from background executor thread)
    - asyncio.Queue per WebSocket subscriber (maxsize=200, QueueFull drops events)
    - Ring buffer via collections.deque(maxlen=BUFFER_SIZE) per pipeline
    - Monotonic global sequence counter across all pipelines
    - Reconnect replay via replay_from(last_seq=N)

key-files:
  created:
    - api_server/services/pipeline_websocket.py — full PipelineEventBus (replaces Plan 01 stub)
    - tests/test_pipeline_websocket.py — 14 unit tests for all PIPE-05 behaviors
  modified:
    - api_server/routers/websocket.py — added /ws/pipelines/{pipeline_id} endpoint

key-decisions:
  - "asyncio.QueueFull exception is caught and logged as a warning — slow WebSocket client does not block the publisher; event is dropped rather than blocking the bus"
  - "asyncio.wait_for with timeout=HEARTBEAT_INTERVAL used instead of raw asyncio.TimeoutError — cleaner async/await pattern"
  - "replay_from is called BEFORE subscribe to avoid race condition — client receives all events from last_seq+1 to present before any new ones"

patterns-established:
  - "PipelineEventBus.publish() is synchronous (thread-safe) — called from PipelineExecutor's background thread via asyncio.run_coroutine_threadsafe pattern"
  - "broadcast_pipeline_event() is async wrapper over sync publish() — maintains async interface for PipelineExecutor._emit()"
  - "Subscriber queues have maxsize=200 to bound memory per connection; QueueFull drops oldest events (bus continues uninterrupted)"

requirements-completed: [PIPE-05]

# Metrics
duration: 5min
completed: 2026-04-12
---

# Phase 30 Plan 03: Pipeline WebSocket Event Bus Summary

**PipelineEventBus with 100-event ring buffer, monotonic sequence numbers, subscriber queues, and /ws/pipelines/{pipeline_id} endpoint with 30-second heartbeat + reconnect replay.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-12T06:03:15Z
- **Completed:** 2026-04-12T06:08:00Z
- **Tasks:** 2 (Task 1 TDD: 14 tests, Task 2: endpoint integration)
- **Files modified:** 3 files, +464 insertions

## Accomplishments

- Replaced Plan 01 stub with production `PipelineEventBus`:
  - Global monotonic sequence counter (1, 2, 3...) across all pipelines
  - Per-pipeline `collections.deque(maxlen=100)` ring buffer — oldest events dropped on overflow
  - `subscribe(pipeline_id)` / `unsubscribe(pipeline_id, queue)` for asyncio.Queue per WebSocket
  - `replay_from(pipeline_id, last_seq=N)` returns events with sequence > N for reconnect
  - `broadcast_pipeline_event()` async wrapper wired to singleton `get_event_bus()`
- Added `/ws/pipelines/{pipeline_id}` endpoint with full PIPE-05 protocol:
  - DB validation before accepting (closes 4004 if pipeline not found)
  - Missed-event replay via `replay_from(last_seq=N)` before streaming
  - 30-second heartbeat via `asyncio.wait_for(timeout=30)` + ping/pong
  - Subscriber queue unregistered on disconnect (no zombie queues)
- Existing `/ws/jobs/{job_id}` endpoint completely unchanged

## Task Commits

1. **Task 1 (TDD RED/GREEN): PipelineEventBus + tests** — `726f010` (feat)
2. **Task 2: /ws/pipelines/{pipeline_id} endpoint** — `a8a44a4` (feat)

**Plan metadata:** `726f010` and `a8a44a4`

## Files Created/Modified

- `api_server/services/pipeline_websocket.py` — Full `PipelineEventBus` class; `broadcast_pipeline_event()` wired to singleton; `PipelineEvent.to_dict()` for JSON serialization
- `tests/test_pipeline_websocket.py` (new) — 14 tests: sequence numbering, ring buffer enforcement, ascending order, replay filtering, singleton wiring, independent buffers, queue subscription, subscriber count/unsubscribe safety
- `api_server/routers/websocket.py` — Added `asyncio` import; appended `/ws/pipelines/{pipeline_id}` endpoint (83 lines)

## Decisions Made

- Used `asyncio.QueueFull` exception handling to drop events from slow subscribers rather than blocking the publisher — slow WebSocket clients cannot starve the bus
- Used `asyncio.wait_for(q.get(), timeout=HEARTBEAT_INTERVAL)` instead of bare `TimeoutError` — cleaner separation between event arrival and heartbeat timeout
- Replay is called BEFORE subscribe to prevent race condition: client gets all missed events (seq > last_seq) first, then new events flow through the queue from that point

## Deviations from Plan

None — plan executed exactly as written.

### Auto-fixed Issues

None — no issues encountered during execution.

---

**Total deviations:** 0
**Impact on plan:** N/A — clean execution

## Verification Results

| Check | Result |
|-------|--------|
| `python3 -m pytest tests/test_pipeline_websocket.py -x -q` | 14 passed |
| `from api_server.services.pipeline_websocket import PipelineEventBus, get_event_bus` | OK |
| `/ws/pipelines/{pipeline_id}` route registered | Present |
| `HEARTBEAT_INTERVAL = 30` grep | Found |
| `replay_from` in websocket.py grep | Found |
| `from api_server.routers.websocket import router` (existing /ws/jobs unchanged) | OK |
| SUMMARY.md file exists | FOUND |
| Task commits 726f010, a8a44a4 present | FOUND |

## Success Criteria Met

- [x] PipelineEventBus.publish() assigns global monotonic sequence numbers
- [x] Buffer holds exactly last 100 events per pipeline (older events dropped)
- [x] replay_from() returns events above last_seq for reconnecting clients
- [x] Two independent pipelines have separate buffers
- [x] /ws/pipelines/{pipeline_id} endpoint registered and importable
- [x] Heartbeat interval is 30 seconds (HEARTBEAT_INTERVAL = 30)
- [x] Endpoint closes with code 4004 if pipeline_id not found in DB
- [x] Existing /ws/jobs/{job_id} endpoint is not modified or broken

## Next Phase Readiness

- Plan 30-04 (cleanup handler + control endpoints) is ready — PipelineEventBus is installed; cleanup handler can broadcast `pipeline_cancelled` events; cancel_pipeline_executor() and get_active_executor() already exist in pipeline_executor.py

---
*Phase: 30-po-01-orchestration-engine plan 03*
*Completed: 2026-04-12*

## Self-Check: PASSED
