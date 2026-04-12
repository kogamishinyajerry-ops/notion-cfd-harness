# Project Research Summary

**Project:** AI-CFD Knowledge Harness v1.7.0 — Pipeline Orchestration & Automation
**Domain:** Scientific Computing / CFD Workflow Automation
**Researched:** 2026-04-12
**Confidence:** MEDIUM

## Executive Summary

v1.7.0 adds an orchestration layer that chains existing components (case generation, Docker solver execution, convergence monitoring, Trame 3D visualization, report generation) into automated end-to-end pipelines. The core value is enabling parametric sweeps and batch job scheduling without users manually triggering each step. Experts build CFD orchestration on top of existing workflow engines (Prefect, Snakemake, Nextflow) rather than building from scratch, leveraging their battle-tested state persistence, retry logic, and DAG scheduling.

The recommended approach is **embedded orchestration** inside the existing FastAPI server (Option A from architecture research), adding a `pipeline_service` module and new REST/WebSocket endpoints. This is NOT a microservice -- it extends the existing single-node Docker/FastAPI ecosystem. For stack additions: Prefect for the orchestration engine (Python-native, SQLite state backend, async FastAPI integration, dynamic task generation for parametric sweeps) and @xyflow/react for React DAG visualization. No external services (Redis, Postgres) required for MVP.

The critical risks are Docker lifecycle ownership conflicts between the new pipeline orchestrator and the existing TrameSessionManager, WebSocket connection loss during multi-hour CFD runs, and the architectural mistake of using FastAPI BackgroundTasks for long-running pipeline coordination instead of a dedicated process. These must be resolved in PO-01 (Phase 2 of the roadmap) before any orchestration logic is written.

## Key Findings

### Recommended Stack

Python-native orchestration with minimal new dependencies. The existing FastAPI + Docker + WebSocket + Trame stack remains unchanged; only new Python and npm packages are added.

**Core technologies:**
- `prefect` (~3.x, verify via PyPI before installing) -- pipeline orchestration engine. Python-native, async FastAPI integration, SQLite state backend, dynamic task generation for parametric sweeps, built-in Docker/Subprocess task runner. Rejected alternatives: Airflow (overkill, requires Redis+Postgres), Celery (task queue not workflow engine), Luigi (no native state persistence), Dagster (heavier, ML-focused).
- `@xyflow/react` (~12.x, verify via npm) -- React-native DAG visualization library. Built-in zoom/pan/minimap, multiple node types, well-suited for pipeline step states. Rejected alternatives: react-force-graph (force-directed, slow for >50 nodes), dagre (layout engine only, no React rendering), cytoscape.js (heavy, not React-native).
- `comparison_engine.py` (new Python module) -- cross-case comparison engine. Reuses existing report generator templates, DivergenceDetector, and WebSocket residual logs. No new dependencies.
- Prefect built-in SQLite -- state persistence for pipeline runs. No new dependency, no external services required for MVP.

### Expected Features

**Must have (table stakes):**
- PO-01: Pipeline Orchestration Engine -- chains the 5-step sequence (generate -> run -> monitor -> visualize -> report) with a state machine (PENDING -> RUNNING -> MONITORING -> VISUALIZING -> REPORTING -> COMPLETED/FAILED). Each stage must be idempotent; failures produce structured result objects, not just exit codes.
- PO-02: Batch Job Scheduling / Parametric Sweep -- runs the same pipeline with systematically varied parameters (mesh resolution, inlet velocity, turbulence model constants). Full factorial with concurrency control (max N simultaneous Docker containers) is the starting pattern.

**Should have (differentiators):**
- PO-03: Cross-Case Comparison Engine -- overlays convergence curves, computes delta scalar fields, produces key metrics table with percentage difference from reference. Depends on PO-02 having completed cases to compare.
- PO-05: Pipeline DAG Visualization -- live dashboard display of pipeline as dependency graph with node states (pending/running/completed/failed/skipped). Clearest "this is not a shell script" indicator.

**Defer (v2+):**
- PO-04: State Persistence and Recovery -- highest complexity (High), lowest immediate value. Enables mid-crash resume from last successful stage. Defer until after user feedback.
- OAT/Latin Hypercube sweep patterns -- full factorial is sufficient for v1.7.0.
- HPC scheduler integration (SLURM/PBS) -- single-node Docker executor is current target.

### Architecture Approach

Extend the existing FastAPI + React architecture by adding a pipeline ownership layer above the existing job layer. **Option A (recommended):** embed `pipeline_service` inside `api_server/` as a new module, not a separate microservice. The existing `JobResponse` model, `WebSocketManager`, `TrameSessionManager`, and Docker executor are foundation -- pipeline orchestrates them, not replaces them.

**Major components:**
1. `api_server/models.py` additions -- `Pipeline`, `PipelineStep`, `PipelineDAG` Pydantic models with status enums. SQLite persistence in `data/pipelines.db` via `pipeline_db.py`.
2. `api_server/services/pipeline_service.py` -- core orchestration engine: step sequencing, DAG traversal, error propagation, cleanup handler. Delegates to existing `JobService`, `TrameSessionManager`, and case generator.
3. `api_server/routers/pipeline.py` + `dashboard/src/pages/PipelineDetailPage.tsx` -- REST API facade + React UI for pipeline CRUD, control (start/pause/resume/cancel), and real-time monitoring.

**Key architectural decision:** Pipeline orchestrator runs as a dedicated background process (not FastAPI BackgroundTasks), communicating via SQLite and the existing WebSocket hub. This avoids tying pipeline lifecycle to HTTP request lifecycle.

### Critical Pitfalls

1. **Docker lifecycle ownership conflicts (2.2, Critical)** -- Both `TrameSessionManager` and the new pipeline orchestrator launch Docker containers. Without clear ownership designation, `docker kill` from pipeline abort can corrupt `TrameSessionManager`'s graceful shutdown. **Fix:** Designate exactly one owner; use container labels (`pipeline.owned=true` vs `trame.managed=true`); never issue `docker kill` directly.
2. **WebSocket connection loss during multi-hour runs (2.3, Critical)** -- The existing in-memory `ConnectionManager` loses events on disconnect. CFD runs can be hours long; tabs suspend, networks interrupt. **Fix:** Implement server-side message buffering with sequence numbers; client sends last-received sequence on reconnect; add `WebSocket.ping()` heartbeats at 30-second intervals.
3. **FastAPI BackgroundTasks for pipeline orchestration (5.1, Critical)** -- BackgroundTasks are tied to HTTP request lifecycle; server restart kills them. **Fix:** Dedicated orchestrator process separate from FastAPI; FastAPI acts as API facade and WebSocket hub only.
4. **State hiding individual component failures (2.1, Critical)** -- Pipeline retry logic absorbs underlying component failures. OpenFOAM divergence may produce clean Docker exit while residual data is invalid. **Fix:** Instrument each wrapped component with structured result objects (exit code + validation checks + machine-readable status enum). Never rely solely on exit codes.
5. **Blocking sync operations in async pipeline callbacks (3.1, Medium)** -- OpenFOAM I/O is blocking. Calling it from `async def` without `asyncio.to_thread()` stalls the event loop. **Fix:** Explicitly separate async coordination (WebSocket, scheduling) from blocking computation (solver I/O); use `asyncio.to_thread()` for blocking calls.

## Implications for Roadmap

### Phase 1: Foundation -- Data Models + SQLite Persistence
**Rationale:** All orchestration logic depends on having a stable data model. Build the persistence layer first so subsequent phases can iterate on service logic without re-engineering storage.
**Delivers:** `Pipeline`, `PipelineStep`, `PipelineDAG` Pydantic models; SQLite database in `data/pipelines.db`; basic CRUD operations.
**Addresses:** PO-01 (data layer only), PITFALL 2.5 (step-level checkpointing design), PITFALL 5.2 (idempotent generation schema).
**Avoids:** Building orchestration on top of in-memory-only state.

### Phase 2: PO-01 Orchestration Engine
**Rationale:** This is the core product. Before this phase completes, no pipeline chaining exists. Also resolves all Critical pitfalls before any orchestration logic is written.
**Delivers:** Sequential step execution (generate -> run -> monitor -> visualize -> report), error propagation, pipeline-level WebSocket events, cleanup handler on abort.
**Implements:** `pipeline_service.py` with state machine. Reuses existing `JobService.submit_job()` for run/verify/report steps.
**Avoids:** PITFALL 2.1 (structured result objects), PITFALL 2.2 (Docker ownership model decision), PITFALL 2.3 (connection resilience), PITFALL 5.1 (FastAPI BackgroundTasks), PITFALL 3.1 (blocking async).
**Research flag:** Docker ownership model decision must be made at phase start -- does pipeline own all containers, or does TrameSessionManager retain viewer containers?

### Phase 3: Pipeline REST API + React Dashboard
**Rationale:** Exposes PO-01 to users. Builds on Phase 2 service; must be sequenced after orchestration logic is stable.
**Delivers:** `POST/GET /pipelines/{id}` endpoints, `POST /pipelines/{id}/start/pause/resume/cancel`, WebSocket `/ws/pipelines/{id}`, `PipelinesPage.tsx`, `PipelineDetailPage.tsx`.
**Implements:** Pipeline router + new React pages and WebSocket client service.
**Avoids:** PITFALL 4.3 (sequence numbering on WebSocket messages).

### Phase 4: PO-02 Batch Scheduling / Parametric Sweep
**Rationale:** Natural extension of PO-01. Uses PO-01 as per-parameter pipeline template. Enables the core CFD value proposition of parameter exploration.
**Delivers:** Parametric sweep configuration UI, concurrency-limited job queue, aggregate sweep progress, output organization by sweep ID.
**Implements:** Sweep expansion in `pipeline_service.py` using `itertools.product`.
**Avoids:** PITFALL 3.2 (resource contention -- implement resource pool here), PITFALL 2.4 (cache invalidation strategy).
**Research flag:** Confirm max concurrent Docker containers for resource pool sizing.

### Phase 5: PO-05 DAG Visualization
**Rationale:** Builds on PO-01 pipeline definition and Phase 3 WebSocket infrastructure. Clear UX differentiator; DAG is pre-computed from pipeline definition (static graph) with live status updates.
**Delivers:** `PipelineDAGViewer.tsx` using @xyflow/react, node states with WebSocket-driven color changes, minimap and zoom/pan.
**Avoids:** PITFALL 3.4 (DAG stale state -- implement polling fallback), PITFALL 3.5 (DAG cycle false positives -- separate data dependency edges from comparison metadata edges).

### Phase 6: PO-03 Cross-Case Comparison
**Rationale:** Depends on PO-02 producing cases to compare. The comparison engine is a new Python module but reuses existing infrastructure (report generator, DivergenceDetector, residual logs).
**Delivers:** Convergence curve overlay, delta scalar field computation, key metrics table with provenance metadata.
**Implements:** `comparison_engine.py`. Stores provenance metadata (OpenFOAM version, compiler version, mesh seed hash, solver config hash) for each case.
**Avoids:** PITFALL 3.3 (version mismatch -- provenance tracking schema).

### Phase 7: PO-04 State Persistence and Recovery (v2)
**Rationale:** Deferred highest-complexity feature. User feedback will clarify whether step-level checkpointing adds sufficient value to justify complexity.
**Delivers:** Mid-crash pipeline resume from last completed stage, deterministic case IDs, pipeline heartbeat for orphaned detection.
**Depends on:** Phase 1 (persistence infrastructure), Phase 2 (orchestration engine).

### Phase Ordering Rationale

- **Phases 1 -> 2 -> 3 are strictly sequential:** Data models before service before API/UI.
- **Phase 4 (batch) depends on Phase 2 (orchestration):** Sweep is PO-01 applied N times.
- **Phase 5 (DAG) depends on Phase 3 (API):** UI requires API endpoints; DAG data comes from pipeline definition + WebSocket state.
- **Phase 6 (comparison) depends on Phase 4 (batch):** No cases to compare until sweep runs complete.
- **Phase 7 (persistence) is deferred:** Highest risk, lowest immediate value.
- **PITFALL resolution order:** All Critical pitfalls resolved in Phase 2 (orchestration engine) before any orchestration code runs. PO-01 IS the pitfall resolution phase.

### Research Flags

Needs research during planning:
- **Phase 2 (PO-01):** Docker ownership model -- requires reading existing `TrameSessionManager` implementation to determine if it supports container labeling or if its auto-launch needs to be disabled.
- **Phase 4 (PO-02):** Resource pool sizing -- need to know available host memory/GPU and OpenFOAM container footprint to set concurrency limits.
- **Phase 7 (PO-04):** Step-level checkpoint granularity -- needs validation against actual OpenFOAM intermediate data structure to determine what to persist per step.

Standard patterns (skip deep research):
- **Phase 3 (API + React):** REST CRUD + WebSocket subscription is well-established in existing codebase.
- **Phase 5 (DAG viz):** @xyflow/react patterns are standard; DAG is pre-computed (static), only live status is dynamic.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | LOW | Prefect ~3.x and @xyflow/react ~12.x from training data (~June 2025). No Context7/WebSearch verification available. Verify against live PyPI/npm before implementation. |
| Features | MEDIUM | Well-documented across Snakemake/Prefect/Nextflow/Airflow. PO-01/02/05 priorities are clear from domain logic. PO-03/04 complexity assessments are based on community consensus. |
| Architecture | MEDIUM-HIGH | Integration points verified from existing codebase analysis. Option A (embedded) is clearly appropriate for single-node deployment. Phase sequencing is dependency-driven. |
| Pitfalls | MEDIUM-HIGH | Critical pitfalls (Docker lifecycle, WebSocket disconnection, BackgroundTasks) are well-documented across FastAPI/Prefect/Airflow documentation. Mitigation strategies are specific to existing components. |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Prefect version:** STACK.md explicitly notes training data ~June 2025. Current Prefect version MUST be verified via `pip show prefect` before any implementation. API surface may have changed.
- **@xyflow/react version:** Same -- verify via `npm show @xyflow/react` before `npm install`.
- **Docker ownership model:** Requires reading `TrameSessionManager` source to determine how to implement container labeling without breaking existing interactive workflow.
- **Max sweep size:** Resource pool sizing for PO-02 depends on expected parametric sweep cardinality. No data in research files.
- **Step-level checkpoint granularity:** PO-04 deferred but design cannot be finalized until OpenFOAM intermediate data format is examined.
- **Prefect vs. custom orchestrator conflict:** ARCHITECTURE.md Option C recommends against Prefect for 5-step linear pipeline as overkill. STACK.md recommends Prefect. These conflict -- a design decision is needed: build lightweight custom orchestrator (ARCHITECTURE.md position) or adopt Prefect (STACK.md position). The ARCHITECTURE.md note that Prefect adds "its own concepts and overhead" for a 5-step linear pipeline is a valid concern worth reconsidering before committing to the Prefect dependency.

## Sources

### Primary (HIGH confidence)
- Prefect Documentation (docs.prefect.io) -- caching, state management, task generation, scheduling patterns (WebFetch)
- Snakemake Documentation (snakemake.readthedocs.io) -- shell script vs orchestrator distinction, wildcards, DAG phase (WebFetch)
- FastAPI Documentation (fastapi.tiangolo.com) -- WebSocket lifecycle, async patterns, BackgroundTasks limitations (WebFetch)
- Apache Airflow Documentation (airflow.apache.org) -- executor pitfalls, DAG state, task dependencies, sensor patterns (WebFetch)

### Secondary (MEDIUM confidence)
- Prefect PyPI (pypi.org/pypi/prefect) -- version and dependency info (WebFetch)
- @xyflow/react (reactflow.dev) -- React-native DAG library (WebFetch)
- Cylc documentation -- HPC workflow engine cycling systems (WebFetch)
- Dask documentation -- parallel execution patterns (WebFetch)

### Tertiary (LOW confidence)
- Prefect version (~3.x) -- training data ~June 2025; verify before use
- @xyflow/react version (~12.x) -- training data ~early 2025; verify before use
- Luigi, Dagster, Temporal alternative assessments -- from training data; ecosystem may have shifted

---

*Research completed: 2026-04-12*
*Ready for roadmap: yes (with caveats on Prefect version verification and Docker ownership decision)*
