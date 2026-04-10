# Phase 12: Residual Streaming Backend - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 12-residual-streaming-backend
**Areas discussed:** Residual Parser, Job Abort, WebSocket Message Format

---

## Residual Parser

| Option | Description | Selected |
|--------|-------------|----------|
| New ResidualParser class | Parse 'Initial/Final residual: X' lines — isolated, testable, reusable | |
| Extend existing Monitor class | Extend existing Monitor class — couples to Monitor's other responsibilities | ✓ |
| Inline in JobService | Parse residuals directly in JobService — mixes concerns | |
| Add stream method | Add stream_residuals() generator to Monitor — batch + streaming | |

**User's choice:** Extend existing Monitor class
**Notes:** Keep related logic together. Monitor in knowledge_compiler/orchestrator/monitor.py is the canonical location.

---

## Job Abort

| Option | Description | Selected |
|--------|-------------|----------|
| Container ID + docker kill | Track container ID, remove --rm, call 'docker kill' — persistent container | ✓ |
| Direct subprocess | Run solver via asyncio subprocess (not Docker) — simpler but loses isolation | |
| SIGTERM to container PID | Send SIGTERM to container PID — may not clean up fully | |

**User's choice:** Container ID + docker kill
**Notes:** Remove --rm flag from Docker run command. Track container ID in _ACTIVE_JOBS dict. On abort, call `docker kill <container_id>`. Clean container after completion.

---

## WebSocket Message Format

| Option | Description | Selected |
|--------|-------------|----------|
| Separate residual message | Separate 'residual' message type — clean, explicit, frontend subscribes to 'residual' | ✓ |
| Piggyback on progress | Add residuals to existing 'progress' messages — fewer types, auto-forwarded | |
| On-demand polling | Only send residuals when queried (polling) — simpler but less real-time | |

**User's choice:** Separate residual message
**Notes:** New ConvergenceMessage Pydantic model with `type: "residual"`. Clean, explicit, frontend subscribes to `residual` events.

---

## Deferred Ideas

- Multi-metric overlay (MON-07) — Phase 13 or later
- 3D visualization (MON-08) — Phase 14+
- Divergence detection alert (MON-06) — Phase 14
- Simulation mid-run parameter adjustment — Out of scope
