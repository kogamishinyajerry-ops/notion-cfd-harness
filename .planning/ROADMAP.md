# AI-CFD Knowledge Harness — Roadmap

## Milestones

- [x] **M1** — Well-Harness AI-CFD OS (Phases 1-7, shipped 2026-04-07)
- [x] **v1.1.0** — Report Automation & CaseGenerator v2 (Phases 8-9, shipped 2026-04-10)
- [x] **v1.2.0** — API & Web Interface (Phases 10-11, shipped 2026-04-10)
- [x] **v1.3.0** — Real-time Convergence Monitoring (shipped 2026-04-11)
- [x] **v1.4.0** — ParaView Web 3D Visualization (shipped 2026-04-11)
- [x] **v1.5.0** — Advanced Visualization (Phases 19-22, shipped 2026-04-11)
- [x] **v1.6.0** — ParaView Web to Trame Migration (Phases 23-28, shipped 2026-04-12)
- [ ] **v1.7.0** — Pipeline Orchestration & Automation (Phases 29-34, planning)

## v1.7.0 — Pipeline Orchestration & Automation

### Phases

- [x] **Phase 29: Foundation — Data Models + SQLite Persistence** — Pipeline and PipelineStep models with SQLite persistence (completed 2026-04-12)
- [x] **Phase 30: PO-01 Orchestration Engine** — State machine, DAG traversal, component wrapping, WebSocket events, cleanup handler, async separation (completed 2026-04-12)
- [x] **Phase 31: Pipeline REST API + React Dashboard** — Full CRUD and control endpoints, PipelinesPage and PipelineDetailPage (completed 2026-04-12)
- [ ] **Phase 32: PO-02 Parametric Sweep** — SweepRunner, concurrency control, aggregate progress, output organization
- [ ] **Phase 33: PO-05 DAG Visualization** — @xyflow/react DAG viewer with live status updates
- [ ] **Phase 34: PO-03 Cross-Case Comparison** — Comparison engine and dashboard UI

---

## Phase Details

### Phase 29: Foundation — Data Models + SQLite Persistence

**Goal:** Pipeline definitions persist across server restarts; all orchestration logic has a stable data model to build on.

**Depends on:** Nothing

**Requirements:** PIPE-01

**Success Criteria** (what must be TRUE):
1. User can create a pipeline with N steps and branching dependencies via `POST /pipelines`, and the pipeline definition is stored in `data/pipelines.db`
2. User can retrieve a pipeline by ID via `GET /pipelines/{id}` and see its DAG adjacency list and step definitions
3. User can update a PENDING pipeline name/description/config via `PUT /pipelines/{id}`
4. User can delete a pipeline via `DELETE /pipelines/{id}`, removing all persisted state
5. Server restart does not lose any pipeline definitions — SQLite persistence verified

**Plans:** 2/2 plans complete

Plans:
- [x] 29-01-PLAN.md — Pydantic models (Pipeline/Step/DAG) + SQLite schema init
- [x] 29-02-PLAN.md — CRUD service, REST router, main.py wiring

---

### Phase 30: PO-01 Orchestration Engine

**Goal:** Pipelines execute autonomously from start to completion, chaining generate -> run -> monitor -> visualize -> report with proper error propagation and resource cleanup.

**Depends on:** Phase 29

**Requirements:** PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07

**Success Criteria** (what must be TRUE):
1. When a pipeline starts, steps execute in DAG topological order; a step begins only when all its `depends_on` predecessors report `COMPLETED`
2. Each step produces a structured result object with `status` (success/diverged/validation_failed/error), `exit_code`, `validation_checks`, and `diagnostics`; pipeline uses `status` — not `exit_code` — to determine step success
3. The `diverged` status from a monitor step does NOT halt the pipeline by default; configurable per step type
4. WebSocket events (`pipeline_started`, `step_started`, `step_completed`, `step_failed`, `pipeline_completed`, `pipeline_failed`, `pipeline_cancelled`) are emitted with monotonic sequence numbers; last 100 events are buffered per pipeline; reconnecting client receives events above its last-received sequence
5. `WebSocket.ping()` heartbeats fire every 30 seconds during long-running pipelines
6. On `CANCELLED` or `FAILED`: Docker containers started by pipeline steps are stopped, background processes are killed, but COMPLETED step outputs are preserved; abort gives running steps 10 seconds to finish before force-kill
7. Blocking I/O (OpenFOAM file I/O, mesh generation) runs in a dedicated background thread/process — NOT in FastAPI BackgroundTasks — so the event loop remains responsive; `asyncio.to_thread()` used for any blocking calls inside async handlers

**Plans:** 4/4 plans complete

**UI hint:** no

---

### Phase 31: Pipeline REST API + React Dashboard

**Goal:** Users can create pipelines, trigger execution, monitor real-time progress, and control pipelines (pause/resume/cancel) from a browser UI.

**Depends on:** Phase 30

**Requirements:** PIPE-08, PIPE-09

**Success Criteria** (what must be TRUE):
1. User can navigate to a Pipelines list page showing all pipelines with status badges (PENDING/RUNNING/COMPLETED/FAILED) and create/delete pipelines
2. User can open a PipelineDetailPage showing the pipeline name, description, step list with current statuses, and control buttons (Start/Pause/Resume/Cancel)
3. User can create a new pipeline using a DAG builder form: add steps, select step type, set `depends_on` relationships, configure params
4. Dashboard receives real-time WebSocket updates on PipelineDetailPage — step statuses change without page refresh
5. If WebSocket disconnects, dashboard falls back to polling and auto-reconnects; no manual refresh required

**Plans:** 4/4 plans complete

Plans:
- [ ] 31-pipeline-rest-api-react-dashboard/31-01-PLAN.md — Backend: PipelineStatus PAUSED enum, pause/resume threading, steps/events/pause/resume REST endpoints
- [ ] 31-pipeline-rest-api-react-dashboard/31-02-PLAN.md — Frontend types, API client methods, WebSocket service
- [ ] 31-pipeline-rest-api-react-dashboard/31-03-PLAN.md — PipelinesPage, PipelineDetailPage, PipelineCreatePage
- [ ] 31-pipeline-rest-api-react-dashboard/31-04-PLAN.md — Routes, nav, theme CSS variables, exports + human verify

**UI hint:** yes

---

### Phase 32: PO-02 Parametric Sweep

**Goal:** User defines a parameter grid once; system runs the full factorial of all parameter combinations as separate pipeline instances, with concurrency control.

**Depends on:** Phase 30

**Requirements:** PIPE-10

**Success Criteria** (what must be TRUE):
1. User can define a sweep: select a base pipeline template and specify a parameter grid (e.g., `{velocity: [1, 2, 5], resolution: [50, 100]}`); system expands to all combinations via `itertools.product`
2. User can set max concurrent Docker containers (default 2) and the sweep runner respects this limit across combination pipelines
3. Sweep progress shows aggregate completion percentage (% of combinations finished) and per-combination status
4. Each combination's outputs are stored under `sweep_{id}/{combination_hash}/` with deterministic naming
5. After sweep completes, user sees a summary table: case_id, params, final_residual, status for all combinations

**Plans:** 2/2 plans created

Plans:
- [ ] 32-01-PLAN.md — Backend: Sweep Pydantic models, SQLite schema, SweepDBService, SweepRunner
- [ ] 32-02-PLAN.md — Backend REST API + Frontend: SweepsPage, SweepCreatePage, SweepDetailPage, routes, nav

**UI hint:** yes

---

### Phase 33: PO-05 DAG Visualization

**Goal:** Dashboard displays each pipeline as an interactive DAG with live node colors reflecting step statuses.

**Depends on:** Phase 31

**Requirements:** PIPE-13

**Success Criteria** (what must be TRUE):
1. User viewing PipelineDetailPage sees a DAG rendered with `@xyflow/react` where nodes represent steps and edges represent `depends_on` relationships
2. Node background colors reflect live status: gray (PENDING), blue (RUNNING), green (COMPLETED), red (FAILED), yellow (SKIPPED); colors update in real time via WebSocket
3. Clicking a node opens a detail panel showing step params, result summary, and diagnostics
4. DAG supports zoom, pan, and minimap navigation
5. If a RUNNING step exceeds its expected duration, a warning icon appears on the node

**Plans:** 2/2 plans created

Plans:
- [ ] 32-01-PLAN.md — Backend: Sweep Pydantic models, SQLite schema, SweepDBService, SweepRunner
- [ ] 32-02-PLAN.md — Backend REST API + Frontend: SweepsPage, SweepCreatePage, SweepDetailPage, routes, nav

**UI hint:** yes

---

### Phase 34: PO-03 Cross-Case Comparison

**Goal:** User can select multiple completed cases and compare them across convergence history, scalar field differences, and key metrics.

**Depends on:** Phase 32

**Requirements:** PIPE-11, PIPE-12

**Success Criteria** (what must be TRUE):
1. User can multi-select cases from a list; each case shows provenance metadata (OpenFOAM version, compiler version, mesh seed hash, solver config hash)
2. When comparing cases with mismatched provenance, a warning is displayed before rendering results
3. Convergence overlay shows residual vs iteration curves for all selected cases on a single log-scale Recharts LineChart
4. Delta field tab displays `CaseB.scalar - CaseA.scalar` as a separate source in the trame viewer
5. Metrics table tab shows per-case columns (case_id, params, final_residual, execution_time) with percentage difference vs reference case; sortable and exportable to CSV
6. Comparison result is saved as `ComparisonResult` JSON and downloadable

**Plans:** 2/2 plans created

Plans:
- [ ] 32-01-PLAN.md — Backend: Sweep Pydantic models, SQLite schema, SweepDBService, SweepRunner
- [ ] 32-02-PLAN.md — Backend REST API + Frontend: SweepsPage, SweepCreatePage, SweepDetailPage, routes, nav

**UI hint:** yes

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 29. Foundation — Data Models + SQLite | 2/2 | Complete    | 2026-04-12 |
| 30. PO-01 Orchestration Engine | 4/4 | Complete    | 2026-04-12 |
| 31. Pipeline REST API + React Dashboard | 4/4 | Complete    | 2026-04-12 |
| 32. PO-02 Parametric Sweep | 0/2 | Planning | — |
| 33. PO-05 DAG Visualization | 0/TBD | Not started | — |
| 34. PO-03 Cross-Case Comparison | 0/TBD | Not started | — |

---

## Coverage

**v1.7.0 Requirements: 13/13 mapped**

| Phase | Requirement | Description |
|-------|-------------|-------------|
| 29 | PIPE-01 | Pipeline Data Model |
| 30 | PIPE-02 | Pipeline State Machine |
| 30 | PIPE-03 | Structured Result Objects |
| 30 | PIPE-04 | Component Wrapping |
| 30 | PIPE-05 | WebSocket Pipeline Events |
| 30 | PIPE-06 | Cleanup Handler |
| 30 | PIPE-07 | Async/Sync Separation |
| 31 | PIPE-08 | Pipeline REST API |
| 31 | PIPE-09 | Dashboard Pipeline Pages |
| 32 | PIPE-10 | Parametric Sweep |
| 33 | PIPE-13 | Pipeline DAG Visualization |
| 34 | PIPE-11 | Cross-Case Comparison Engine |
| 34 | PIPE-12 | Cross-Case Comparison UI |

All v1.7.0 requirements mapped. No orphans.

---

*Full milestone history: `.planning/MILESTONES.md`*
