# Domain Pitfalls: Adding Pipeline Orchestration to AI-CFD Harness

**Project:** AI-CFD Knowledge Harness v1.7.0
**Researched:** 2026-04-12
**Domain:** Pipeline Orchestration for Scientific Computing (CFD/Simulation)
**Confidence:** MEDIUM-HIGH

> This document covers pitfalls specific to **adding** pipeline orchestration to an existing CFD/scientific visualization system. It assumes FastAPI + WebSocket server, React dashboard, trame VTK viewer in Docker, Python knowledge_compiler, and OpenFOAM Docker solver are already operational.

---

## 1. Introduction

Adding pipeline orchestration to an existing system carries distinct risks from building one from scratch. The existing components have established behaviors, communication patterns, and failure modes. Disrupting these while adding orchestration introduces specific integration pitfalls that are not obvious from workflow engine documentation alone.

This document assumes **existing components are working** and focuses on pitfalls that arise when wrapping them in an orchestration layer.

---

## 2. Critical Pitfalls

Mistakes that cause pipeline failures, data loss, or integration breakage.

### 2.1: Pipeline State Hides Individual Component Failures

**What goes wrong:** When orchestration wraps existing components, failures in underlying components get absorbed by the pipeline's retry/continuation logic, making the actual failure hard to diagnose.

**Why it happens:** Existing components (knowledge_compiler, OpenFOAM solver, trame viewer) have their own error handling. When wrapped in pipeline tasks, exceptions may be caught at multiple layers, creating ambiguous stack traces. The orchestrator retries or marks a step "completed" based on exit codes, but the component's internal state (diverged mesh, corrupted output) is not visible.

**Consequences:**
- Pipeline reports "success" but downstream steps fail with cryptic errors
- OpenFOAM divergence is detected but the pipeline continues because the Docker container exited cleanly
- Residual data is partial but treated as valid by the comparison engine

**Prevention:**
- Instrument each wrapped component with structured result objects that include: exit code, validation checks passed/failed, and a machine-readable status enum
- Never rely solely on process exit codes to determine component success
- Propagate component-level diagnostic data (residual history, mesh quality metrics) through the pipeline state

**Detection:**
- Pipeline execution logs show "completed" but downstream WebSocket messages contain stale data
- Dashboard DAG shows all nodes green but case comparison yields NaN values

---

### 2.2: Docker Container Lifecycle Ownership Conflicts

**What goes wrong:** The existing system launches Docker containers (OpenFOAM solver, trame viewer) independently. Adding an orchestrator that also manages containers creates lifecycle conflicts -- two processes trying to start/stop the same container.

**Why it happens:**
- Trame viewer has its own Docker lifecycle manager (`TrameSessionManager`) with idle timeout and auto-launch
- Pipeline orchestrator may independently launch Docker containers for the same purpose
- `docker kill` from pipeline abort overwrites graceful shutdown in `TrameSessionManager`

**Consequences:**
- Orphaned containers accumulate (memory leak of Docker processes)
- Race condition: pipeline thinks container is ready but `TrameSessionManager` has not yet started it
- Double-termination of containers causes port conflicts on restart

**Prevention:**
- Designate exactly **one** component as the Docker lifecycle owner. Options:
  - **Option A:** Pipeline orchestrator owns all container lifecycle; disable `TrameSessionManager`'s auto-launch
  - **Option B:** `TrameSessionManager` continues owning viewer containers; pipeline only manages solver containers
- Use container labels to identify ownership: `pipeline.owned=true` vs `trame.managed=true`
- Never issue `docker kill` directly; always go through the owning component's shutdown method

**Detection:**
- `docker ps` shows multiple orphaned containers after pipeline runs
- `TrameViewer.tsx` logs show "session already exists" errors during pipeline execution
- Port 8080 (trame) conflicts after pipeline restarts a crashed job

---

### 2.3: WebSocket Connection Loss During Long-Running Simulation

**What goes wrong:** CFD simulations can run for hours. WebSocket connections to the dashboard drop due to timeouts, network interruptions, or browser tab suspension. The pipeline continues running but the client has no visibility.

**Why it happens:**
- FastAPI/WebSocket default timeout behavior may close idle connections
- Browser tabs suspend WebSocket connections after inactivity (especially mobile)
- Dashboard `ConnectionManager` (in-memory) loses track of reconnecting clients
- Pipeline progress events queue but have nowhere to send when no client is connected

**Consequences:**
- User loses real-time convergence monitoring during a critical divergence event
- DivergenceDetector sends `divergence_alert` WebSocket message but no client receives it
- User cannot abort a diverging job because the abort button is disconnected

**Prevention:**
- Implement **connection resilience** in `ConnectionManager`:
  - Server-side message buffering with `missed_message` query on reconnect
  - Client sends last-received sequence number on reconnect
  - Server replays buffered messages above sequence number
- Add a **persistence layer** for critical pipeline events:
  - Write `divergence_alert`, `job_complete`, `job_failed` to a Redis/persistent queue
  - Dashboard polls or receives these on reconnect
- Use `WebSocket.ping()` heartbeats at 30-second intervals to keep connection alive
- Never assume a connected client will stay connected for the duration of a pipeline run

**Detection:**
- Dashboard shows frozen residual chart mid-simulation with no error message
- `divergence_alert` is logged server-side but user never sees it
- User reports "pipeline was running but dashboard showed nothing"

---

### 2.4: Stale Cache Returning Invalid Results After Solver Divergence

**What goes wrong:** Pipeline or component-level caching returns a previous successful result when the current run diverged but cache has not been invalidated.

**Why it happens:**
- Prefect documentation explicitly warns: "Cached states never expire unless `cache_expiration` is explicitly provided"
- If a pipeline step uses a cached solver result but the case parameters changed slightly, the cached (potentially diverged) result is returned without re-running
- Cross-case comparison uses cached mesh/field data that may be from a failed run

**Consequences:**
- Pipeline reports "completed" using stale data from a previous successful run
- Cross-case comparison produces misleading results because some cases are from cache, others fresh
- User exports results thinking they correspond to current parameters when they do not

**Prevention:**
- Always invalidate cache when: case parameters change, mesh topology changes, solver settings change
- Use content-addressable caching: hash case parameters + solver config + mesh seed -> cache key
- Distinguish between "result not yet computed" and "result computed with different parameters"
- For cross-case comparison, explicitly validate that all compared cases used the same solver version and settings

**Detection:**
- Pipeline completes instantly (no actual computation) for a case that should have run
- Cross-case comparison shows suspiciously identical results for different parameter sets
- Export shows results that do not match the case parameters selected

---

### 2.5: Pipeline State Persistence Gap Between Steps

**What goes wrong:** Pipeline state is not persisted at the right granularity. If the pipeline crashes or is manually stopped between steps, all state from completed steps is lost and must be recomputed.

**Why it happens:**
- Pipeline orchestration typically serializes state at the **run level** but not at the **step level**
- OpenFOAM solver produces intermediate results at each iteration, but pipeline only saves final state
- If pipeline stops after `generate` but before `run`, the generated case must be recreated
- If pipeline stops after `run` but before `visualize`, the solver output is available but not linked to the pipeline context

**Consequences:**
- Long-running parametric sweeps must restart from scratch after interruption
- Intermediate data (checkpoint files, residuals at each iteration) is lost
- Pipeline resume produces a **new** case ID rather than continuing the original run, breaking traceability

**Prevention:**
- Implement **step-level checkpointing**: after each pipeline step completes, write a checkpoint that includes:
  - Step completed, outputs produced, input hashes consumed
  - Docker container state (paused, not terminated)
  - Intermediate data paths (not just final results)
- Designate a **pipeline state directory** per run: `pipelines/{pipeline_id}/{step_id}/`
- On resume: detect existing checkpoint, validate outputs exist, skip to first incomplete step
- Use **deterministic case IDs**: `pipeline_id + step_index + parameter_hash` not random UUID

**Detection:**
- After pipeline restart, case list shows duplicate entries for the same parameters
- Parametric sweep resume recalculates all previously completed cases
- Pipeline logs show different case IDs for what user believes is one continuous run

---

## 3. Moderate Pitfalls

Issues that cause incorrect behavior or degraded UX, but do not cause complete pipeline failure.

### 3.1: Blocking Sync Operations in Async Pipeline Callbacks

**What goes wrong:** Using `def` (sync) route handlers that call blocking OpenFOAM I/O operations inside async pipeline callbacks, freezing the event loop.

**Why it happens:**
- FastAPI runs sync route handlers in a threadpool but pipeline orchestrator callbacks may be async contexts
- OpenFOAM I/O operations (reading log files, writing mesh files) are blocking and can take seconds
- If orchestrator callback uses `async def` but calls blocking I/O without `await`, the event loop stalls

**Prevention:**
- When calling blocking I/O from async contexts, use `asyncio.to_thread()` or offload to a worker process
- Explicitly separate: async coordination (WebSocket, scheduling) vs blocking computation (solver I/O, mesh generation)
- Do not wrap blocking operations in `await` unless they are truly async-compatible

---

### 3.2: Parametric Sweep Resource Contention

**What goes wrong:** Batch scheduling launches multiple OpenFOAM containers simultaneously, causing resource contention that degrades all simulations or causes OOM kills.

**Why it happens:**
- Each OpenFOAM Docker container consumes significant memory (2-8 GB depending on mesh size)
- Default Docker resource limits may not be set; containers compete for host resources
- Trame viewer containers also consume GPU/memory when active
- No **resource pool manager** coordinates concurrent simulation capacity

**Prevention:**
- Implement a **resource pool** that tracks available host memory/GPU and limits concurrent solver runs
- Set explicit Docker resource limits per container: `--memory`, `--cpus`, `--gpus`
- For parametric sweeps, use a **staggered launch** pattern: start next case when previous reaches `runStartTime` rather than waiting for full completion
- Monitor host resource usage and scale down concurrency when memory pressure is detected

---

### 3.3: Cross-Case Comparison Version Mismatch

**What goes wrong:** Comparing cases that used different OpenFOAM versions, solver settings, or mesh generation configs produces misleading comparative results.

**Why it happens:**
- Cases created at different times may have been generated with different `knowledge_compiler` versions
- OpenFOAM Docker image may have been updated between case runs
- Mesh refinement levels or boundary condition defaults may have changed
- Comparison engine does not automatically detect or flag these differences

**Prevention:**
- Store **provenance metadata** with every case: `openfoam_version`, `compiler_version`, `mesh_seed_hash`, `solver_config_hash`
- Before comparison, run a **compatibility check**: compare provenance metadata of all selected cases
- Flag mismatches explicitly in UI rather than silently proceeding
- Store comparison results with the provenance of the cases compared

---

### 3.4: Pipeline DAG Visualization Stale State

**What goes wrong:** Dashboard DAG visualization shows pipeline as "running" when individual steps have actually completed or failed, because DAG updates are driven by WebSocket push without polling fallback.

**Why it happens:**
- DAG state is driven by WebSocket messages from orchestrator to dashboard
- If WebSocket disconnects (see 2.3), DAG stops updating
- Client-side DAG may show a step as "running" because it received `step_started` but no `step_completed`
- No polling fallback to sync actual pipeline state

**Prevention:**
- Implement **optimistic UI with reconciliation**: dashboard shows expected state based on last event, but periodically polls `/api/pipelines/{id}/status` to reconcile
- DAG nodes should have explicit **staleness indicators**: if node has been "running" for > expected_duration, show warning
- Store pipeline state in a persistent backend (not just in-memory) so any dashboard instance can retrieve current state

---

### 3.5: DAG Cycle Detection False Positives

**What goes wrong:** Complex parametric sweep pipelines with dynamic branching create apparent cycles that trigger DAG validation errors, even when the graph is actually a DAG.

**Why it happens:**
- Cross-case comparison may create a virtual edge between cases that is not a real dependency but a logical relationship
- Parametric sweep with conditional branching (`if mesh_quality < threshold, refine_mesh`) creates dynamic edges
- DAG validation libraries may flag these as cycles

**Prevention:**
- Clearly separate **data dependency edges** (real execution order) from **metadata edges** (comparison relationships)
- Store comparison relationships in a separate graph structure, not in the pipeline DAG
- For conditional branching, use explicit `Condition` nodes with deterministic predicate evaluation, not implicit control flow

---

## 4. Minor Pitfalls

Cosmetic or UX issues that are annoying but do not cause incorrect results.

### 4.1: Pipeline Abort Does Not Clean Up Child Processes

**What goes wrong:** Clicking "abort" on a running pipeline kills the orchestrator's view of the pipeline but orphaned Docker containers and background processes continue running.

**Prevention:** Implement a **cleanup handler** that on pipeline abort: stops all Docker containers started by that pipeline, kills background Python processes spawned by that pipeline, removes temporary case directories not yet persisted.

### 4.2: Scheduler DST and Timezone Mismatch

**What goes wrong:** Batch jobs scheduled with cron-like expressions fire at wrong times due to DST transitions, or scheduled times appear incorrect because server uses UTC but dashboard shows local time.

**Prevention:** Always store and transmit pipeline scheduled times in UTC. Display in user's local timezone only at UI layer. Never use interval schedules < 24 hours for time-sensitive triggers (see Prefect scheduling docs).

### 4.3: WebSocket Message Ordering Not Guaranteed

**What goes wrong:** Pipeline events arrive at dashboard in non-chronological order (e.g., `step_complete` arrives before `step_started`), causing DAG to show incorrect state transitions.

**Prevention:** Attach monotonic sequence numbers to all pipeline events. On client, maintain a **sequence log** and apply events in order. Discard late-arriving events with lower sequence numbers than already processed.

---

## 5. Integration Pitfalls

Pitfalls at the boundary between existing components and the new orchestration layer.

### 5.1: FastAPI Background Tasks vs. Dedicated Orchestrator

**What goes wrong:** Adding pipeline orchestration inside the existing FastAPI server using `BackgroundTasks` creates coupling between HTTP request lifecycle and pipeline lifecycle.

**Why it happens:**
- FastAPI `BackgroundTasks` are tied to the request lifecycle; if the server restarts, background tasks are lost
- Long-running pipelines outlive HTTP requests; `BackgroundTasks` are not designed for multi-hour runs
- The existing FastAPI server was designed for request-response, not pipeline orchestration

**Prevention:**
- Use a **dedicated orchestrator process** (separate from FastAPI) that communicates via:
  - Redis queue or PostgreSQL for job dispatch
  - FastAPI for status polling and WebSocket subscription
  - File system or object storage for large result payloads
- FastAPI acts as the **API facade** and WebSocket hub; the actual pipeline execution runs in an independent process or worker pool

---

### 5.2: knowledge_compiler Integration Without Idempotency

**What goes wrong:** Pipeline triggers `knowledge_compiler` multiple times with same parameters, producing duplicate or conflicting case definitions.

**Why it happens:**
- `knowledge_compiler` was designed for one-off case generation, not pipeline reuse
- If pipeline retries a `generate` step, it creates a new case with different ID but same parameters
- Downstream `run` step may pick up the wrong case file if multiple versions exist

**Prevention:**
- Implement **idempotent generation**: if a case with matching parameters already exists, return its ID instead of creating new
- Add a **generation lock**: prevent concurrent generation of the same parameter set
- Store `knowledge_compiler` outputs in a versioned case directory: `cases/{param_hash}/{version}/`

---

### 5.3: Trame Viewer Session Pool Collision

**What goes wrong:** Pipeline visualization steps compete with interactive dashboard users for the trame session pool.

**Why it happens:**
- `TrameSessionManager` has an idle timeout (30 min) and max session limit
- Pipeline automated visualization requests consume a session slot
- When a user later tries to open an interactive viewer, all sessions are occupied by pipeline runs
- Or vice versa: user holds sessions open, pipeline cannot get a slot for automated screenshots

**Prevention:**
- Separate **interactive** and **pipeline** trame session pools with different priority queues
- Pipeline visualization sessions should be **ephemeral**: acquire session, render, release, without waiting for user interaction
- Set shorter idle timeout (e.g., 5 min) for pipeline sessions vs. 30 min for interactive
- Use a **session lease** system: pipeline holds lease for the minimum time needed

---

## 6. Phase-Specific Warnings

Which phase should address each pitfall.

| Pitfall | Severity | Phase Recommendation | Notes |
|---------|----------|----------------------|-------|
| 2.1 State hides failures | Critical | PO-01 (Orchestration Engine) | Must be addressed in engine design, not deferred |
| 2.2 Docker lifecycle conflicts | Critical | PO-01 (Orchestration Engine) | Requires deciding ownership model early |
| 2.3 WebSocket disconnection | Critical | PO-01 (Orchestration Engine) | Connection resilience is foundational |
| 2.4 Stale cache invalidation | High | PO-02 (Batch Scheduling) | Caching strategy must be designed with batch in mind |
| 2.5 Step-level persistence gap | High | PO-04 (Pipeline Persistence) | Explicit phase for state persistence |
| 3.1 Blocking async | Medium | PO-01 (Orchestration Engine) | FastAPI integration pattern |
| 3.2 Resource contention | Medium | PO-02 (Batch Scheduling) | Resource pool design |
| 3.3 Version mismatch | Medium | PO-03 (Cross-Case Comparison) | Provenance tracking |
| 3.4 DAG stale state | Medium | PO-05 (DAG Visualization) | Polling fallback |
| 3.5 DAG cycle false positive | Low | PO-05 (DAG Visualization) | Graph structure design |
| 4.1 Abort cleanup | Low | PO-01 (Orchestration Engine) | Cleanup handler |
| 4.2 DST/timezone | Low | Any scheduling phase | Simple if caught early |
| 4.3 Message ordering | Low | PO-01 (Orchestration Engine) | Sequence numbering |
| 5.1 FastAPI vs orchestrator | Critical | PO-01 (Orchestration Engine) | Architectural decision |
| 5.2 Compiler idempotency | High | PO-01 (Orchestration Engine) | Generation locking |
| 5.3 Session pool collision | Medium | PO-01 (Orchestration Engine) | Pool separation |

---

## 7. Prevention Summary

### Critical Path Checklist for PO-01 (Orchestration Engine)

Before PO-01 is complete, these must be resolved:

- [ ] **Docker ownership model** decided: orchestrator owns all containers OR TrameSessionManager continues owning viewer containers exclusively
- [ ] **Structured result objects** defined for each wrapped component (not just exit codes)
- [ ] **Connection resilience** designed: message buffering + sequence numbering + polling fallback
- [ ] **Orchestrator process** is separate from FastAPI HTTP lifecycle
- [ ] **Cleanup handler** registered for abort signal
- [ ] **Resource pool** designed (even if not implemented yet) to prevent unbounded concurrent runs

### Later Phase Items

- PO-02: Add cache invalidation strategy + resource pool implementation
- PO-03: Provenance metadata schema for cross-case comparison
- PO-04: Step-level checkpointing + deterministic case ID scheme
- PO-05: DAG staleness indicators + polling fallback

---

## 8. Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Docker lifecycle pitfalls | HIGH | Well-documented, multiple sources agree |
| WebSocket disconnection | HIGH | Standard real-time systems issue, documented in FastAPI docs |
| State persistence | MEDIUM | General workflow engine patterns verified; CFD-specific checkpoint granularity needs validation |
| Cross-case comparison | MEDIUM | Version mismatch is a known scientific workflow issue; specific OpenFOAM provenance schema not confirmed |
| Resource contention | HIGH | Noisy neighbor problem documented across all workflow engines |
| Integration anti-patterns | MEDIUM | FastAPI BackgroundTasks vs dedicated orchestrator is an architectural pattern, not CFD-specific |

---

## 9. Sources

| Source | URL | Confidence | What it verifies |
|--------|-----|------------|------------------|
| Prefect Documentation: Task timeouts | https://docs.prefect.io/latest/concepts/tasks/ | HIGH | ThreadPoolTaskRunner timeout limitations with blocking operations |
| Prefect Documentation: Caching | https://docs.prefect.io/latest/concepts/tasks/ | HIGH | Cache expiration never expires by default |
| Prefect Documentation: State management | https://docs.prefect.io/latest/concepts/states/ | HIGH | State manipulation can hide failures; `AwaitingRetry` behavior |
| Prefect Documentation: Schedules | https://docs.prefect.io/latest/concepts/schedules/ | HIGH | Cron limitations, DST handling, scheduler constraints |
| Apache Airflow Documentation: Executor pitfalls | https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/index.html | HIGH | Noisy neighbor, container startup latency, hybrid executor issues |
| Apache Airflow Documentation: DAGs | https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html | HIGH | Trigger rule cascade, DAG state management, `depends_on_past` behavior |
| Apache Airflow Documentation: Tasks | https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html | HIGH | Task dependencies, XCom fundamentals, zombie task detection |
| Apache Airflow Documentation: Sensors | https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html | MEDIUM | Poke vs reschedule mode, soft_fail, timeout configuration |
| Snakemake Documentation | https://snakemake.readthedocs.io/en/stable/snakefiles/deployment.html | MEDIUM | Deployment reproducibility, conda environment issues |
| FastAPI Documentation: WebSocket | https://fastapi.tiangolo.com/advanced/websockets/ | HIGH | WebSocket connection lifecycle, disconnect handling, ConnectionManager pattern |
| FastAPI Documentation: Async | https://fastapi.tiangolo.com/async/ | HIGH | async/await patterns, blocking event loop, background tasks |
| Docker Documentation: Dockerfile best practices | https://docs.docker.com/develop/develop-images/dockerfile_best-practices/ | HIGH | Ephemeral containers, graceful shutdown with exec, volume mounting |
| pytest Documentation: Flaky tests | https://docs.pytest.org/en/latest/explanation/flaky.html | MEDIUM | Flaky test root causes, timing issues, test isolation |

---

## RESEARCH COMPLETE

**Project:** AI-CFD Knowledge Harness v1.7.0
**Mode:** Ecosystem (Pitfalls Research)
**Confidence:** MEDIUM-HIGH

### Key Findings

- **Critical integration risk (2.2):** Docker lifecycle ownership conflict between `TrameSessionManager` and new pipeline orchestrator must be resolved before PO-01 begins
- **WebSocket resilience (2.3):** Long-running CFD simulations require connection resilience with message buffering and polling fallback -- the existing in-memory `ConnectionManager` will lose events on disconnect
- **State visibility (2.1):** Pipeline abstraction must instrument components with structured result objects, not just rely on exit codes, to prevent silent failures propagating through the pipeline
- **Architectural decision (5.1):** FastAPI `BackgroundTasks` must NOT be used for pipeline orchestration -- requires dedicated independent process
- **Provenance tracking (3.3):** Cross-case comparison needs explicit version metadata to prevent comparing results from different OpenFOAM/compiler versions

### Files Created

| File | Purpose |
|------|---------|
| `/Users/Zhuanz/Desktop/notion-cfd-harness/.planning/research/PITFALLS.md` | Domain pitfalls for pipeline orchestration v1.7.0 |

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Docker lifecycle | HIGH | Well-documented across workflow engines; applies to existing TrameSessionManager |
| WebSocket disconnection | HIGH | FastAPI docs confirm; standard real-time systems problem |
| State persistence | MEDIUM | General patterns verified; CFD-specific checkpoint granularity needs PO-04 validation |
| Cross-case comparison | MEDIUM | Provenance mismatch is known in scientific workflows; specific schema needs design |
| Integration anti-patterns | MEDIUM | FastAPI BackgroundTasks vs dedicated orchestrator is architectural, not CFD-specific |

### Roadmap Implications

- **PO-01 must resolve:** Docker ownership model, orchestrator/FastAPI separation, connection resilience, cleanup handler, structured result objects
- **PO-02 must implement:** Resource pool + cache invalidation (deferring these to batch phase risks resource exhaustion)
- **PO-03 must track:** Provenance metadata schema design
- **PO-04 must implement:** Step-level checkpointing with deterministic case IDs

### Open Questions

- Does `TrameSessionManager` currently support labeling containers for ownership tracking?
- Is there an existing Redis or PostgreSQL queue available for job dispatch, or will one need to be introduced?
- What is the expected maximum parametric sweep size? (Affects resource pool sizing)
- Should pipeline abort attempt to pause Docker containers for later resume, or terminate completely?

---

*Research conducted: 2026-04-12*
*Next step: Review with architecture team before PO-01 phase begins*
