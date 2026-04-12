# AI-CFD Knowledge Harness — Requirements

**Milestone:** v1.7.0 — Pipeline Orchestration & Automation
**Version:** 1
**Status:** Active
**Last updated:** 2026-04-12

## Requirement Quality Criteria

Good requirements are:
- **Specific and testable:** "User can X" (not "System does Y")
- **User-centric:** "User can X" (not "System does Y")
- **Atomic:** One capability per requirement (not "User can login and manage profile")
- **Independent:** Minimal dependencies on other requirements

---

## v1.7.0 Requirements

### PIPE-01: Pipeline Data Model

**Category:** PIPE (Pipeline Orchestration)

**Requirement:**
User can create, read, update, and delete pipeline definitions via REST API.

**Details:**
- `Pipeline` model: id, name, description, created_at, updated_at, status, config (JSON)
- `PipelineStep` model: id, pipeline_id, step_type (generate/run/monitor/visualize/report), step_order, depends_on (list of step IDs), params (JSON), status
- `PipelineDAG`: DAG stored as adjacency list in `pipeline.config`; supports branching (one step can depend on multiple preceding steps)
- SQLite persistence in `data/pipelines.db` — survives server restart
- API: `POST /pipelines`, `GET /pipelines`, `GET /pipelines/{id}`, `PUT /pipelines/{id}`, `DELETE /pipelines/{id}`

**Traceability:** PO-01b (DAG with branches)
**Priority:** Must have
**Phase:** 29

---

### PIPE-02: Pipeline State Machine

**Category:** PIPE (Pipeline Orchestration)

**Requirement:**
Pipeline executes steps according to DAG dependency order, with a defined state machine.

**Details:**
- States: `PENDING` → `RUNNING` → `MONITORING` → `VISUALIZING` → `REPORTING` → `COMPLETED` | `FAILED` | `CANCELLED`
- Step states: `PENDING` → `RUNNING` → `COMPLETED` | `FAILED` | `SKIPPED`
- DAG traversal: topological sort; step starts only when all `depends_on` steps are `COMPLETED`
- On `COMPLETED`: auto-advance to next step(s)
- On `FAILED`: propagate to dependent steps → `SKIPPED`; pipeline enters `FAILED` state
- On `CANCELLED`: stop all `RUNNING` steps; already `COMPLETED` steps stay completed

**Traceability:** PO-01b (DAG with branches)
**Priority:** Must have
**Phase:** 30

---

### PIPE-03: Structured Result Objects

**Category:** PIPE (Pipeline Orchestration)

**Requirement:**
Each wrapped component returns a structured result object — not just an exit code.

**Details:**
- Each step produces a result object with:
  - `status`: enum (`success`, `diverged`, `validation_failed`, `error`)
  - `exit_code`: integer
  - `validation_checks`: dict of check_name → bool
  - `diagnostics`: dict of component-specific data (residual_history, mesh_quality, etc.)
- Pipeline uses `status` field (not `exit_code`) to determine step success
- `diverged` status from monitor step does NOT halt pipeline — configurable per step type
- Result objects stored as JSON in `pipeline.config` per step

**Traceability:** PO-01b + PITFALL 2.1
**Priority:** Must have
**Phase:** 30

---

### PIPE-04: Component Wrapping

**Category:** PIPE (Pipeline Orchestration)

**Requirement:**
Pipeline orchestrates existing components by calling their existing APIs.

**Details:**
- `generate` step → calls `GenericOpenFOAMCaseGenerator` Python API
- `run` step → calls `JobService.submit_job()` with generated case
- `monitor` step → subscribes to WebSocket residuals; emits `converged` or `diverged` result
- `visualize` step → launches trame session via `TrameSessionManager` (or pipeline-managed session)
- `report` step → calls `ReportGenerator` Python API
- Each step is idempotent: re-running a completed step with same params returns cached result
- Docker lifecycle ownership: configurable — either pipeline owns all containers, or `TrameSessionManager` retains viewer containers

**Traceability:** PO-01b + PITFALL 2.2
**Priority:** Must have
**Phase:** 30

---

### PIPE-05: WebSocket Pipeline Events

**Category:** PIPE (Pipeline Orchestration)

**Requirement:**
Dashboard receives real-time pipeline events via WebSocket.

**Details:**
- New WebSocket endpoint: `/ws/pipelines/{pipeline_id}`
- Events: `pipeline_started`, `step_started`, `step_completed`, `step_failed`, `pipeline_completed`, `pipeline_failed`, `pipeline_cancelled`
- Sequence numbers on all events (monotonic integer)
- Server-side message buffering: last 100 events stored per pipeline
- Client reconnect: sends last-received sequence number; server replays events above that sequence
- Heartbeat: `WebSocket.ping()` every 30 seconds to prevent connection timeout during long runs

**Traceability:** PO-01b + PITFALL 2.3
**Priority:** Must have
**Phase:** 30

---

### PIPE-06: Cleanup Handler

**Category:** PIPE (Pipeline Orchestration)

**Requirement:**
Pipeline abort/cancel cleans up all resources started by that pipeline.

**Details:**
- On `CANCELLED` or `FAILED`:
  - Stop all Docker containers started by pipeline steps
  - Kill any background processes spawned by pipeline
  - Do NOT clean up `COMPLETED` step outputs (保留用于后续分析)
- Abort button in Dashboard calls `DELETE /pipelines/{pipeline_id}` with `cancel=true`
- Graceful shutdown: give running steps 10 seconds to finish before force-killing

**Traceability:** PO-01b + PITFALL 4.1
**Priority:** Must have
**Phase:** 30

---

### PIPE-07: Async/Sync Separation

**Category:** PIPE (Pipeline Orchestration)

**Requirement:**
Blocking I/O (OpenFOAM file I/O, mesh generation) does not block the FastAPI event loop.

**Details:**
- Pipeline orchestrator runs in a dedicated background thread/process, NOT in FastAPI `BackgroundTasks`
- FastAPI acts as API facade; actual execution happens in `PipelineExecutor` (separate from HTTP request lifecycle)
- Use `asyncio.to_thread()` for blocking calls inside async handlers
- Solver execution (Docker) is inherently non-blocking — already correct

**Traceability:** PO-01b + PITFALL 3.1, 5.1
**Priority:** Must have
**Phase:** 30

---

### PIPE-08: Pipeline REST API

**Category:** PIPE (Pipeline Orchestration)

**Requirement:**
REST API exposes pipeline CRUD and control operations.

**Details:**
- `POST /pipelines` — create pipeline from DAG definition
- `GET /pipelines` — list all pipelines (with status filter)
- `GET /pipelines/{id}` — get pipeline detail with step statuses
- `PUT /pipelines/{id}` — update pipeline definition (only when `PENDING`)
- `DELETE /pipelines/{id}` — cancel and delete pipeline
- `POST /pipelines/{id}/start` — start pipeline execution
- `POST /pipelines/{id}/pause` — pause pipeline (pause RUNNING steps)
- `POST /pipelines/{id}/resume` — resume paused pipeline
- `POST /pipelines/{id}/cancel` — cancel pipeline
- `GET /pipelines/{id}/steps` — get all steps with statuses
- `GET /pipelines/{id}/events` — get buffered pipeline events

**Traceability:** PO-01b
**Priority:** Must have
**Phase:** 31

---

### PIPE-09: Dashboard Pipeline Pages

**Category:** PIPE (Pipeline Orchestration)

**Requirement:**
Dashboard exposes pipeline management and monitoring UI.

**Details:**
- `PipelinesPage.tsx` — list view of all pipelines with status badges, create button, delete button
- `PipelineDetailPage.tsx` — detail view: DAG visualization, step list with statuses, real-time WebSocket updates, control buttons (start/pause/resume/cancel)
- Pipeline creation wizard/form: DAG builder (add steps, set dependencies)
- Auto-refresh on tab focus (polling fallback if WebSocket disconnected)

**Traceability:** PO-01b
**Priority:** Must have
**Phase:** 31

---

### PIPE-10: Parametric Sweep

**Category:** SWEEP (Batch Scheduling)

**Requirement:**
User can define and execute a parametric sweep: one pipeline template, N parameter combinations.

**Details:**
- Sweep definition: base pipeline template + parameter grid
  - Parameter grid expressed as dict: `{param_name: [val1, val2, ...]}`
  - Full factorial expansion: `itertools.product` over all param values
- Sweep execution: one pipeline per combination, managed by `SweepRunner`
- Concurrency control: max N simultaneous Docker containers (configurable, default 2)
- Sweep progress: aggregate progress (% of combinations completed)
- Output organization: `sweep_{id}/{combination_hash}/` per combination
- Results aggregation: summary table of all combination results (case_id, params, final_residual, status)

**Traceability:** PO-02a
**Priority:** Must have
**Phase:** 32

---

### PIPE-11: Cross-Case Comparison Engine

**Category:** COMP (Cross-Case Comparison)

**Requirement:**
User can compare multiple completed cases: convergence curves overlay, delta fields, key metrics table.

**Details:**
- Convergence overlay: residual vs iteration curves for selected cases on same plot (Recharts)
- Delta scalar fields: `CaseB.scalar - CaseA.scalar` field data; visualized in trame as separate source
- Key metrics table: per-case table (final residuals, execution time, case_id, params); percentage difference vs reference case
- Provenance metadata: each case stores (openfoam_version, compiler_version, mesh_seed_hash, solver_config_hash)
- Comparison validity check: warn if provenance mismatches across compared cases
- Comparison result saved as `ComparisonResult` JSON; downloadable

**Traceability:** PO-03
**Priority:** Should have
**Phase:** 34

---

### PIPE-12: Cross-Case Comparison UI

**Category:** COMP (Cross-Case Comparison)

**Requirement:**
Dashboard provides UI for selecting cases, running comparison, and viewing results.

**Details:**
- Case selector: multi-select from job/case list; show provenance metadata for each
- "Compare" button → opens `ComparisonView.tsx`
- Convergence overlay tab: Recharts LineChart with one line per selected case
- Delta field tab: trame viewer showing delta scalar field
- Metrics table tab: HTML table with sort, export to CSV
- Comparison history: list of past comparisons

**Traceability:** PO-03
**Priority:** Should have
**Phase:** 34

---

### PIPE-13: Pipeline DAG Visualization

**Category:** DAGVIZ (DAG Visualization)

**Requirement:**
Dashboard displays pipeline as an interactive DAG with live status updates.

**Details:**
- Uses `@xyflow/react` (React Flow) for DAG rendering
- Nodes represent steps; edges represent `depends_on` relationships
- Node colors by status: gray (PENDING), blue (RUNNING), green (COMPLETED), red (FAILED), yellow (SKIPPED)
- Click node → show step detail panel (params, result, diagnostics)
- Zoom, pan, minimap enabled
- DAG is pre-computed from pipeline definition (static graph); only node colors update via WebSocket
- Staleness indicator: if node has been "RUNNING" for > expected_duration, show warning icon

**Traceability:** PO-05 + PITFALL 3.4
**Priority:** Should have
**Phase:** 33

---

## Future Requirements (Deferred)

These requirements are out of scope for v1.7.0 but noted for future milestones.

| ID | Requirement | Reason Deferred |
|----|-------------|----------------|
| PO-04-Future | State Persistence and Recovery — mid-crash resume from last completed step | Highest complexity; lowest immediate demo value |
| OAT-Future | OAT/Latin Hypercube sampling — advanced DOE for parameter space exploration | Full factorial sufficient for v1.7.0 |
| HPC-Future | SLURM/PBS scheduler integration — run on HPC clusters | Single-node Docker is current target |
| ShareLink-Future | Shareable pipeline links — serialize pipeline state to URL | Nice-to-have; not core value |
| MultiViz-Future | Multi-viewport side-by-side case comparison | Defer until comparison engine stable |

---

## Out of Scope

| Item | Reason |
|------|--------|
| Airflow / Celery / Dagster / Temporal | Overkill for 5-step linear pipeline; Prefect sufficient |
| Redis / PostgreSQL for pipeline state | SQLite sufficient for single-node; add complexity |
| Multi-node / distributed execution | Single-node Docker is current target |
| Native Prefect UI | Custom React dashboard provides better UX integration |

---

## Traceability Matrix

| Phase | Requirements |
|-------|-------------|
| 29 | PIPE-01 |
| 30 | PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07 |
| 31 | PIPE-08, PIPE-09 |
| 32 | PIPE-10 |
| 33 | PIPE-13 |
| 34 | PIPE-11, PIPE-12 |

---

*Generated: 2026-04-12*
