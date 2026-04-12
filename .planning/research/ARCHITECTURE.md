# Research: Pipeline Orchestration Architecture

**Project:** AI-CFD Knowledge Harness v1.7.0
**Researched:** 2026-04-12
**Confidence:** MEDIUM-HIGH

Sources: Existing codebase analysis (api_server/, dashboard/src/, knowledge_compiler/), FastAPI/FastAPI-Worker patterns.

---

## Executive Summary

Pipeline orchestration (PO-01 to PO-05) integrates with the existing FastAPI + React architecture by extending the current job-based execution model into a hierarchical structure where Pipelines own Jobs. The existing `JobResponse` model, `WebSocketManager`, and `TrameSessionManager` provide the foundation -- new work is primarily additive.

**Recommendation: Integrate into `api_server` as a new `pipeline_service` module.** Do not create a separate microservice. The existing Docker-based deployment, in-process job execution, and absence of microservice infrastructure make an embedded approach correct for this project scale.

---

## 1. Integration Points with Existing Components

### 1.1 Data Layer -- Extend or Mirror Job Storage

**Current state:**
- `job_service.py` line 20: `_JOBS: Dict[str, JobResponse] = {}` -- in-memory only
- `JobResponse` (models.py lines 103-114): flat job model with `case_id`, `job_type`, `status`, `progress`, `result`

**Pipeline additions needed:**

| Model | File | Purpose | Relationship |
|-------|------|---------|--------------|
| `Pipeline` | `models.py` (new) | Pipeline metadata, config, status | Owns many `PipelineStep` |
| `PipelineStep` | `models.py` (new) | Per-step job reference | Belongs to one `Pipeline` |
| `Pipeline DAG` | `models.py` (new) | Step dependency graph (JSON field) | Embedded in `Pipeline.config` |

**Key design decision -- pipeline state storage:**

- **Option A (Recommended): SQLite in `data/` directory alongside existing job persistence**
  - Current `_JOBS` dict is ephemeral. Pipeline PO-04 (recovery) requires persistence.
  - SQLite is already appropriate for single-node deployment.
  - Migration path: later replace with PostgreSQL if needed.

- **Option B: Extend in-memory with JSON file dump**
  - Simpler but less robust for long-running pipelines.
  - Recovery from mid-pipeline crash is fragile.

- **Option C: Separate pipeline database**
  - Overkill at this project scale; adds deployment complexity.

### 1.2 API Layer -- New Router for Pipelines

**Current routers in `api_server/routers/`:**
- `cases.py`, `jobs.py`, `knowledge.py`, `status.py`, `auth.py`, `websocket.py`, `visualization.py`

**Pipeline router additions:**

```
POST   /pipelines              -- Create new pipeline
GET    /pipelines              -- List pipelines
GET    /pipelines/{id}         -- Get pipeline with steps
POST   /pipelines/{id}/start   -- Trigger pipeline execution
POST   /pipelines/{id}/pause   -- Pause pipeline
POST   /pipelines/{id}/resume  -- Resume pipeline
POST   /pipelines/{id}/cancel  -- Cancel pipeline
DELETE /pipelines/{id}         -- Delete pipeline

GET    /pipelines/{id}/steps   -- List pipeline steps
GET    /pipelines/{id}/dag     -- Get DAG structure for visualization
GET    /pipelines/{id}/compare -- Cross-case comparison data (PO-03)
```

**Existing job endpoints remain unchanged.** Pipeline execution creates child jobs via the existing `JobService.submit_job()` -- no duplication of job execution logic.

### 1.3 Service Layer -- New `pipeline_service.py`

**Current service structure:**
```
api_server/services/
  case_service.py       -- Case CRUD
  job_service.py        -- Job submission, execution, cancel
  knowledge_service.py  -- Knowledge registry
  websocket_manager.py  -- WebSocket connection registry
  trame_session_manager.py -- Trame Docker session lifecycle
  divergence_detector.py   -- Convergence detection
```

**New service:**
```
api_server/services/
  pipeline_service.py   -- Pipeline orchestration logic (NEW)
```

**Dependencies on existing services:**

```
pipeline_service.py
  --> JobService.submit_job()    -- Creates child jobs for each step
  --> WebSocketManager.broadcast() -- Pipeline-level progress events
  --> TrameSessionManager.launch_session() -- Auto-visualization after step=run
  --> knowledge_compiler/phase2/execution_layer/openfoam_docker.py -- Direct for step=run (bypasses JobService when pipeline manages lifecycle)
```

**Key insight:** `job_service.py` already has `_run_job()` that delegates to `_run_case`, `_verify_case`, `_generate_report`. Pipeline service should reuse these directly for `step_type=run/verify/report` rather than re-implementing Docker execution.

### 1.4 WebSocket Layer -- Extend Protocol for Pipeline Events

**Current WebSocket message types (dashboard/src/services/websocket.ts line 8):**
```typescript
type WebSocketMessageType = 'status' | 'progress' | 'completion' | 'error' | 'residual';
```

**Pipeline WebSocket events to add:**
```typescript
type PipelineMessageType = 'pipeline_status' | 'pipeline_progress' | 'pipeline_step_complete' | 'pipeline_complete' | 'pipeline_error' | 'pipeline_diverged';

interface PipelineStatusMessage {
  type: 'pipeline_status';
  pipeline_id: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  current_step: string | null;      // step_id of actively executing step
  completed_steps: number;
  total_steps: number;
  progress: number;                   // 0-100
}

interface PipelineStepCompleteMessage {
  type: 'pipeline_step_complete';
  pipeline_id: string;
  step_id: string;
  step_type: 'generate' | 'run' | 'verify' | 'visualize' | 'report';
  step_status: 'completed' | 'failed';
  output_dir?: string;                // Passed to next step
  trame_session_id?: string;         // If step_type=visualize
  error?: string;
}
```

**Existing per-job WebSocket remains unchanged** (`/ws/jobs/{job_id}`). Pipeline WebSocket at `/ws/pipelines/{pipeline_id}` aggregates child job events and emits pipeline-level events.

### 1.5 Knowledge Compiler Integration

**Current knowledge_compiler orchestrator (knowledge_compiler/orchestrator/):**
- `monitor.py` -- already handles residual streaming
- `verify_console.py` -- verification logic
- `solver_runner.py` -- solver execution

**Pipeline steps map to existing components:**

| Pipeline Step | Calls | Notes |
|---------------|-------|-------|
| `generate` | `knowledge_compiler/phase2/execution_layer/` case generation | Currently called via JobService._run_case which delegates to OpenFOAMDockerExecutor.execute_streaming |
| `run` | `OpenFOAMDockerExecutor.execute_streaming()` | Same executor, residual streaming already wired |
| `verify` | `knowledge_compiler/orchestrator/verify_console.py` | Already in JobService._verify_case |
| `visualize` | `TrameSessionManager.launch_session()` | Already auto-launches after job completion |
| `report` | `knowledge_compiler/phase9_report/ReportGenerator` | Already in JobService._generate_report |

**Conclusion:** Pipeline orchestration does not require new knowledge_compiler components. It orchestrates existing ones. The only potential new component is a `case_generator` invoker in `pipeline_service.py` to handle the `generate` step.

### 1.6 React Dashboard Integration

**Current dashboard services (dashboard/src/services/):**
- `api.ts` -- HTTP API client
- `websocket.ts` -- WebSocket subscription service
- `caseTypes.ts`, `types.ts` -- TypeScript interfaces

**Dashboard changes needed:**

| File | Change | Purpose |
|------|--------|---------|
| `services/types.ts` | Add `Pipeline`, `PipelineStep`, `PipelineDAG` interfaces | Type safety |
| `services/api.ts` | Add `getPipelines()`, `createPipeline()`, `startPipeline()`, etc. | API client methods |
| `services/pipelineWs.ts` (new) | Pipeline WebSocket subscription service | Real-time pipeline updates |
| `pages/PipelinesPage.tsx` (new) | Pipeline list and creation UI | Main pipeline view |
| `pages/PipelineDetailPage.tsx` (new) | Pipeline monitor with DAG visualization | Per-pipeline detail |
| `components/PipelineDAGViewer.tsx` (new) | DAG visualization component | PO-05 requirement |
| `components/PipelineStepCard.tsx` (new) | Individual step status card | Reusable step display |

---

## 2. New Components Needed

### 2.1 Backend (api_server/)

| Component | Path | Purpose |
|-----------|------|---------|
| Pipeline models | `models.py` (additions) | `Pipeline`, `PipelineStep`, `PipelineDAG` Pydantic models |
| Pipeline service | `services/pipeline_service.py` | Core orchestration logic: step sequencing, dependency resolution, error handling |
| Pipeline router | `routers/pipeline.py` | REST endpoints for pipeline CRUD and control |
| Pipeline DB | `data/pipelines.db` | SQLite persistence (auto-created) |

### 2.2 Frontend (dashboard/src/)

| Component | Path | Purpose |
|-----------|------|---------|
| Pipeline types | `services/types.ts` (additions) | TypeScript interfaces |
| Pipeline API client | `services/api.ts` (additions) | HTTP methods |
| Pipeline WS service | `services/pipelineWs.ts` | WebSocket subscription |
| Pipelines list page | `pages/PipelinesPage.tsx` | List + create + delete pipelines |
| Pipeline detail page | `pages/PipelineDetailPage.tsx` | Monitor + control pipeline |
| DAG viewer | `components/PipelineDAGViewer.tsx` | D3.js or React Flow DAG viz |
| Step card | `components/PipelineStepCard.tsx` | Step status display |

---

## 3. Data Flow Changes

### 3.1 Current Job Execution Flow

```
Dashboard                   api_server                    knowledge_compiler
    |                              |                                |
    |-- POST /jobs -------------->|                                |
    |                              |-- JobService.submit_job() -->|
    |                              |   Creates JobResponse         |
    |                              |   Stores in _JOBS dict         |
    |<-- 201 JobResponse ---------|                                |
    |                              |                                |
    | WebSocket /ws/jobs/{id}      |-- _execute_job_async() ------->|
    |<====== streaming ===========>|   (residual messages)          |
    |                              |                                |
    |                              |   Job completes                |
    |<====== completion ==========|                                |
```

### 3.2 Pipeline Execution Flow (New)

```
Dashboard                api_server                 knowledge_compiler / Docker
    |                         |                               |
    |-- POST /pipelines ---->|                               |
    |   { steps: [generate,   |                               |
    |    run, verify, report]}|                               |
    |<-- 201 Pipeline --------|                               |
    |                         |                               |
    |-- POST /pipelines/{id}/|                               |
    |   start                 |                               |
    |                         |-- PipelineService.start() --->|
    |                         |   Step 1: generate case ------>|
    | WebSocket /ws/pipelines/|       (case_generator)        |
    | {id}                    |<-- output_dir -----------------|
    |<==== pipeline_status ===|                               |
    |   current_step="gen_1" |   Step 2: run solver --------->|
    |                         |<-- residuals streaming --------|
    |<==== pipeline_step_    |<==== streaming ================|
    |   complete             |                               |
    |                         |   Step 3: verify ------------->|
    |<==== step_complete =====|       (verify_console)        |
    |                         |<-- verification report -------|
    |                         |                               |
    |                         |   Step 4: launch trame ------->|
    |<==== trame_session_id ==|       (TrameSessionManager)    |
    |                         |<-- session ready --------------|
    |                         |                               |
    |                         |   Step 5: report ------------->|
    |<==== pipeline_complete =|       (ReportGenerator)       |
    |   { result_urls: [...] }|                               |
```

### 3.3 Key Data Flow Changes

1. **Child job ownership:** Pipeline creates jobs with `pipeline_id` field set. Jobs retain full independence (queryable via existing `/jobs/{id}` endpoint) but pipeline tracks them.

2. **Output passing between steps:** Each step's `output_dir` is passed as input to the next step. This is stored in `PipelineStep.output_dir` and carried forward.

3. **WebSocket separation:**
   - `/ws/jobs/{job_id}` -- per-job events (unchanged)
   - `/ws/pipelines/{pipeline_id}` -- pipeline-level aggregation + step lifecycle

4. **Trame session lifecycle:** Currently auto-launched after job completion (job_service.py line 127-140). Pipeline should control this -- only launch after final `run` step completes, not after every child job.

---

## 4. Suggested Build Order

### Phase 1: Data Models + Persistence (Foundation)
**Purpose:** Establish the data layer before any orchestration logic.

1. Add `Pipeline`, `PipelineStep`, `PipelineDAG` Pydantic models to `models.py`
2. Add `PipelineStatus` enum (PENDING, RUNNING, PAUSED, COMPLETED, FAILED, CANCELLED)
3. Create SQLite database in `data/pipelines.db` via `pipeline_db.py`
4. Implement basic CRUD operations in `pipeline_db.py`
5. Write tests for models and database operations

**Dependencies:** None -- pure foundation.

### Phase 2: Pipeline Service Core (PO-01 engine)
**Purpose:** Build the orchestration engine that sequences steps.

1. Create `pipeline_service.py` with:
   - `create_pipeline(config)` -- validates DAG, stores in DB
   - `start_pipeline(pipeline_id)` -- begins sequential step execution
   - `_execute_step(step_id)` -- runs one step, captures output
   - `pause_pipeline(pipeline_id)`, `resume_pipeline(pipeline_id)`, `cancel_pipeline(pipeline_id)`
2. Implement step dependency resolution (DAG traversal)
3. Integrate with `JobService` for `run/verify/report` steps
4. Integrate with case generator for `generate` step
5. Error handling: step failure -> pipeline FAILED, propagate error
6. Write unit tests for orchestration logic

**Dependencies:** Phase 1 models.

### Phase 3: Pipeline REST API (PO-01 endpoint)
**Purpose:** Expose pipeline control to dashboard.

1. Create `routers/pipeline.py`
2. Implement all pipeline CRUD + control endpoints
3. Extend `WebSocketManager` with pipeline WebSocket support
4. Add pipeline WebSocket endpoint `/ws/pipelines/{pipeline_id}`
5. Write integration tests for API

**Dependencies:** Phase 2 service.

### Phase 4: React Dashboard Integration (PO-05 UI)
**Purpose:** Enable users to create and monitor pipelines.

1. Add `Pipeline`, `PipelineStep` to `dashboard/src/services/types.ts`
2. Add pipeline methods to `dashboard/src/services/api.ts`
3. Create `services/pipelineWs.ts` for WebSocket subscription
4. Create `PipelinesPage.tsx` -- list + create + delete
5. Create `PipelineDetailPage.tsx` -- monitor with step cards
6. Create `PipelineDAGViewer.tsx` -- D3.js DAG visualization

**Dependencies:** Phase 3 API.

### Phase 5: Cross-Case Comparison (PO-03)
**Purpose:** Enable PO-03 feature.

1. Add `GET /pipelines/{id}/compare` endpoint
2. Implement comparison engine: collect metrics from all child jobs' results
3. Dashboard: add comparison view to `PipelineDetailPage`

**Dependencies:** Phase 3.

### Phase 6: Batch/Parametric Sweep (PO-02)
**Purpose:** Enable parameterized batch runs.

1. Extend `PipelineStep` with `parameter_sweep` config (list of parameter values)
2. Pipeline service: expand sweep into parallel child jobs
3. Aggregate results for comparison
4. Dashboard: sweep configuration UI

**Dependencies:** Phase 2.

### Phase 7: Persistence Recovery (PO-04)
**Purpose:** Enable mid-crash recovery.

1. Pipeline service: on startup, scan DB for RUNNING pipelines
2. Implement recovery logic: re-attach to running steps or restart from last completed step
3. Add pipeline heartbeat to detect orphaned pipelines
4. Dashboard: "Resume interrupted pipeline" prompt

**Dependencies:** Phase 2 + Phase 3.

---

## 5. Architecture Options

### Option A: Embedded in api_server (RECOMMENDED)

**Description:** Add `pipeline_service.py` and `routers/pipeline.py` inside the existing `api_server/` module. SQLite in `data/`. Extend `models.py`.

**Tradeoffs:**

| Pros | Cons |
|------|------|
| Single deployment unit -- no new service to operate | Pipeline crashes can affect API availability |
| Shares existing auth, WebSocket, Docker infrastructure | Single-point scaling limitation (but appropriate for current scale) |
| Type sharing between pipeline and job models trivial | Larger api_server codebase |
| Existing CI/CD pipeline works unchanged | |

**When appropriate:** Current project scale (single-node Docker), no existing microservice infrastructure, team already familiar with api_server layout.

### Option B: Separate Pipeline Orchestrator Service

**Description:** New `pipeline-orchestrator/` service with its own FastAPI app, connects to `api_server` via HTTP for job submission.

**Tradeoffs:**

| Pros | Cons |
|------|------|
| Complete isolation -- pipeline crashes don't affect API | New deployment target, CI/CD pipeline, Docker Compose update |
| Independent scaling if needed later | Must maintain two auth systems or shared token validation |
| Clean separation of concerns | HTTP latency between orchestrator and job execution |
| | Requires defining inter-service protocol |

**When appropriate:** Multiple frontend clients, team scaling, operational independence requirements. Not yet justified for this project.

### Option C: Workflow Engine (Prefabricated)

**Description:** Use a workflow engine library (Prefect, Temporal, Airflow) instead of building orchestration from scratch.

**Tradeoffs:**

| Pros | Cons |
|------|------|
| Built-in retry, backfill, scheduling, UI | Heavy dependency -- introduces its own concepts and overhead |
| Battle-tested reliability | Overkill for 5-step linear pipeline |
| Distributed execution ready | Integration with existing job_service and trame_manager requires wrapper anyway |

**When appropriate:** Multi-team environment, complex branching DAGs, scheduled recurring pipelines, distributed execution requirements. None of these apply to the current 5-step pipeline.

---

## 6. Summary of Required Changes

### Modified Files

| File | Change |
|------|--------|
| `api_server/models.py` | Add `Pipeline`, `PipelineStep`, `PipelineDAG`, `PipelineStatus` models |
| `api_server/main.py` | Register new `pipeline.router` |
| `api_server/services/websocket_manager.py` | Add pipeline-level broadcast methods |
| `dashboard/src/services/api.ts` | Add pipeline API methods |
| `dashboard/src/services/types.ts` | Add TypeScript pipeline types |
| `dashboard/src/services/websocket.ts` | Extend message types for pipelines |

### New Files

| File | Purpose |
|------|---------|
| `api_server/services/pipeline_service.py` | Core orchestration engine |
| `api_server/routers/pipeline.py` | Pipeline REST endpoints |
| `api_server/services/pipeline_db.py` | SQLite persistence |
| `dashboard/src/services/pipelineWs.ts` | Pipeline WebSocket client |
| `dashboard/src/pages/PipelinesPage.tsx` | Pipeline list UI |
| `dashboard/src/pages/PipelineDetailPage.tsx` | Pipeline monitor UI |
| `dashboard/src/components/PipelineDAGViewer.tsx` | DAG visualization |
| `dashboard/src/components/PipelineStepCard.tsx` | Step status component |

### Components Left Unchanged

- `knowledge_compiler/` -- no changes required; pipeline orchestrates existing entry points
- `trame_server.py` -- no changes; lifecycle managed via existing `TrameSessionManager`
- `job_service.py` -- no changes; pipeline reuses `submit_job()` interface
- `Dockerfile` -- likely needs `pip install aiosqlite` for async SQLite

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Integration points | HIGH | All existing components clearly identified; job_service delegation pattern understood |
| Data model design | MEDIUM | Pipeline model structure clear; step dependency JSON format needs refinement during implementation |
| WebSocket extension | HIGH | Protocol extension is additive, no breaking changes |
| Build order | MEDIUM | Phases 1-3 are clearly sequential; Phases 4-7 have some parallelism |
| Option A recommendation | HIGH | Appropriate for current scale; no microservice infrastructure to protect |
