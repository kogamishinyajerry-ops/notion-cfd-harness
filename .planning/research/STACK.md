# STACK.md — Pipeline Orchestration & Automation

**Project:** AI-CFD Knowledge Harness v1.7.0
**Domain:** Workflow orchestration for chained CFD components
**Researched:** 2026-04-12
**Confidence:** LOW (no external verification — Context7/WebSearch unavailable; ecosystem knowledge from training data ~June 2025)

---

## Introduction

v1.7.0 adds an **orchestration layer** to chain existing components:

```
case generation (Python) → Docker solver exec → WebSocket monitoring → trame 3D viz → report generation
```

The stack additions must:
1. **Integrate with existing FastAPI backend** (Python-native preferred)
2. **Persist pipeline state** (survive restarts, track long-running CFD jobs)
3. **Support parametric sweeps** (N cases, N results, cross-case comparison)
4. **Expose DAG to React dashboard** (real-time status + visualization)
5. **NOT over-engineer** — existing FastAPI + DockerExec + WebSocket infra is solid

---

## Existing Stack

| Component | Technology | Role |
|-----------|-----------|------|
| API Server | FastAPI | REST + WebSocket server |
| Dashboard | React + TypeScript | UI |
| Solver Exec | Docker (bash) | OpenFOAM runs |
| Monitoring | WebSocket (FastAPI) | Real-time residuals |
| Visualization | trame (VTK) | 3D field viewer |
| Report Gen | Python (HTML/PDF/JSON) | Literature comparison |
| Case Gen | `knowledge_compiler/` | blockMeshDict generation |

**Key constraint:** Everything lives in a single Docker/FastAPI ecosystem — no distributed cluster.

---

## Recommended Stack Additions

### 1. Pipeline Orchestration Engine — Prefect (recommended)

**Why Prefect over alternatives (Python-native workflow engines):**

| Criteria | Prefect | Luigi | Airflow | Dagster |
|----------|---------|-------|---------|---------|
| Python-native | YES | YES | NO (DAG = YAML+Python) | YES |
| FastAPI integration | Natural (both async Python) | Manual | Manual | Manual |
| State persistence | Built-in (SQLite/Postgres) | Manual | Manual | Built-in |
| Dynamic DAG (parametric sweep) | YES (dynamic task generation) | YES | YES (XCom + loops) | YES |
| Dashboard (native) | Excellent (Prefect UI) | Basic | Excellent (Airflow UI) | Excellent (Dagster UI) |
| Docker-native | YES | YES | YES | YES |
| Weight | Light | Medium | Heavy | Medium |
| Learning curve | Low | Medium | High | Medium |

**Why NOT the others:**
- **Luigi**: No native state persistence, no modern async API, harder to embed in FastAPI, less active development
- **Airflow**: Overkill (requires scheduler + webserver + worker + Redis/Postgres), too heavy for single-app ecosystem, DAGs defined in YAML + Python operator boilerplate
- **Dagster**: Excellent but more ML-pipeline focused; steeper learning curve; heavier initial setup; assets model is powerful but adds conceptual overhead for this use case
- **Celery**: Task queue, not a workflow engine — no DAG awareness, no state visualization, no pipeline-level retry

**Why Prefect:**
1. Python-native `async` support matches FastAPI patterns
2. Dynamic task generation handles parametric sweeps cleanly without XCom gymnastics
3. State persistence with SQLite (no external DB required for single-node) — **critical for this project**
4. REST API + WebSocket for embedding pipeline status in React dashboard
5. `@flow` / `@task` decorators are minimal boilerplate
6. Subprocess/Docker task runner built in — maps directly to existing `docker_executor` module

**Version caveat:** Prefect was at ~3.x as of mid-2025. Current version should be verified with `pip show prefect` or PyPI before installing. LOW confidence on exact version.

**Installation:**
```bash
pip install prefect
# Prefect uses SQLite by default for local/Single-Node deployments
# No Redis, Postgres, or external services needed for MVP
```

**Integration pattern with FastAPI:**
```python
# pipeline_engine.py
from prefect import flow, task

@task
def generate_case(params: dict):
    # knowledge_compiler/ case generation
    ...

@task
def run_solver(case_id: str):
    # Docker exec — existing docker_executor module
    ...

@task
def generate_report(result: dict):
    # Existing report generator
    ...

@flow
def cfd_pipeline(case_params: dict):
    case = generate_case(case_params)
    result = run_solver(case.id)
    report = generate_report(result)
    return report
```

```python
# FastAPI route — embeds Prefect in FastAPI async context
@app.post("/pipelines/run")
async def run_pipeline(params: CaseParams):
    from pipeline_engine import cfd_pipeline
    result = await cfd_pipeline.aio(params.dict())
    return {"pipeline_run_id": result.id, "status": "completed"}
```

---

### 2. State Persistence & Recovery — Prefect (built-in) + SQLite

**Why NOT add a separate state machine library (PyTransitions, python-statemachine, FSA):**
- CFD pipelines have complex DAGs with branching, retry, and partial failure — a full workflow engine handles this better than a bare FSM
- Prefect's built-in state backend handles persistence, retry, and resume out of the box
- Adding a separate FSM + task queue layer creates two sources of truth and integration friction

**Recovery mechanism:**
- Prefect automatically retries failed tasks with configurable retry policies
- Pipeline state (running/waiting/completed/failed) persisted in SQLite
- `prefect deployment build` + `prefect agent start` for long-running pipeline deployment
- Task-level checkpointing via Prefect's result storage

---

### 3. Batch Job Scheduling (Parametric Sweeps) — Prefect (native)

**Pattern:** Dynamic task generation inside a Prefect flow:

```python
from prefect import flow, task
from itertools import product

@flow
def parametric_sweep(param_ranges: dict):
    # param_ranges e.g., {"velocity": [1.0, 2.0, 5.0], "viscosity": [1e-5, 1e-6]}
    # Generate N cases = len(velocity) * len(viscosity)
    param_combinations = list(product(
        param_ranges["velocity"],
        param_ranges["viscosity"]
    ))

    # Create a case for each parameter combination
    cases = [
        generate_case({"velocity": v, "viscosity": mu})
        for v, mu in param_combinations
    ]

    # Sequential execution (CFD jobs are compute-bound, Docker-limited)
    results = [run_case(case) for case in cases]

    # Cross-case comparison
    return compare_all_results(results)
```

**Why NOT Celery + Redis for this:**
- Adds Redis as a dependency (operational overhead for single-node)
- Celery is task-level, not workflow-level — parametric sweep needs DAG-level awareness (cases, dependencies, retry, result aggregation)
- Prefect handles both task execution and workflow orchestration in one layer

---

### 4. Cross-Case Comparison Engine — Python-native (new module)

Not a library — a new `comparison_engine.py` module leveraging existing infrastructure:

| Comparison Type | Data Source | Output |
|-----------------|-------------|--------|
| Convergence curves | WebSocket residual logs (existing) | JSON/CSV of residual history per case |
| Field distribution | trame/VTK snapshots | PNG diff + scalar metrics |
| Key metrics | solver log (residuals, Y+, exec time) | JSON comparison table |
| Literature validation | existing report gen module | comparison HTML with literature bounds |

**Existing components to reuse:**
- `DivergenceDetector` (v1.3.0) — for convergence comparison
- Report generator (v1.3.0+) — for HTML comparison output
- `ResultSummaryPanel` data structures

**New module:** `comparison_engine.py` in `knowledge_compiler/` or `api_server/`
- Accepts list of case result IDs
- Fetches residual histories from pipeline run metadata (stored by Prefect)
- Computes comparative metrics (best convergence, fastest, lowest residual)
- Generates comparison report (reuses existing HTML template)

---

### 5. Pipeline DAG Visualization in React — @xyflow/react

**Why @xyflow/react (React Flow) over alternatives:**

| Library | Pros | Cons |
|---------|------|------|
| @xyflow/react | Purpose-built for React DAGs, drag-drop editor, minimap, multiple node types, zoom/pan built-in | No physics layout (manual positioning required) |
| react-force-graph | 3D rendering, physics-based layout | Force-directed layouts are slow for >50 nodes; not DAG-first UX; heavy |
| dagre + @types/dagre | Layout engine for DAGs | Requires manual React rendering; basic node/edge drawing |
| cytoscape.js | Feature-rich graph library | Heavy; steep learning curve; not React-native |

**Why NOT native SVG/D3:**
- Too much boilerplate for interactive node graphs with zoom/pan/select
- @xyflow/react has native support for workflow/node styling — maps well to pipeline step states

**Version caveat:** @xyflow/react was at ~12.x as of early 2025. Verify current version with `npm show @xyflow/react`. LOW confidence.

**Installation:**
```bash
npm install @xyflow/react
```

**Integration with Prefect:**
- Prefect exposes pipeline run metadata via REST API (`GET /api/run/{id}/graph` returns DAG structure)
- React dashboard fetches DAG structure + node states (PENDING/RUNNING/COMPLETED/FAILED)
- Map Prefect task states to @xyflow/react node styles (colors, icons)

**Integration point — new React component:**
```tsx
// PipelineDAG.tsx
import { ReactFlow } from '@xyflow/react';

function PipelineDAG({ pipelineRunId }: { pipelineRunId: string }) {
  // Fetch DAG from Prefect API or backend proxy
  const { nodes, edges } = usePipelineDAG(pipelineRunId);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
      minimap
      nodeTypes={pipelineNodeTypes}  // custom: CaseGen, RunSolver, Visualize, Report
    />
  );
}
```

---

## What NOT to Add

| Avoid | Reason | Instead |
|-------|--------|---------|
| Apache Airflow | Overkill for single-node app; requires Redis + Postgres + scheduler + workers; too heavy | Prefect (local/SQLite mode) |
| Celery (standalone) | Task queue only, not a workflow engine; adds Redis dependency; no DAG awareness | Prefect handles task queuing internally |
| Luigi | Older design; no native state persistence; harder FastAPI integration; less active development | Prefect |
| Dagster | More ML-pipeline focused; steeper learning curve; heavier initial setup | Prefect (lighter, simpler) |
| Dramatiq | Task queue only; no workflow orchestration; no DAG visualization | Prefect |
| BPMN engine (Camunda, etc.) | Enterprise-grade; massive overhead; overkill for Python-centric project | Prefect |
| Temporal | Go-based; requires separate server deployment; too heavy for this ecosystem | Prefect (pure Python) |
| Redisson / distributed task queues | Requires Redis cluster; over-engineered for single-node | Prefect SQLite |
| Celery + separate FSM library | Two sources of truth; complex integration; double the operational burden | Prefect alone |
| RQ (Redis Queue) | Task queue, not workflow engine; no DAG awareness | Prefect |

---

## Integration Points

### With existing FastAPI server

**Option A — Embed Prefect in FastAPI (embedded runner, recommended for MVP):**
- Prefect flow runs in the same Python process as FastAPI
- Simpler deployment — no separate Prefect server/agent processes
- FastAPI `async` endpoints can `await` Prefect flow completion

**Option B — Prefect as sidecar (separate process):**
- FastAPI `POST /pipelines/run` → calls Prefect REST API → Prefect agent picks up job
- More decoupled but requires Prefect server running as separate process
- Better if pipeline complexity grows beyond single-node

**Recommendation for v1.7.0:** Option A (embedded) — simpler deployment, sufficient for single-node CFD pipeline.

### With WebSocket monitoring

- Prefect tasks emit state change events via `prefect.events`
- React dashboard subscribes to WebSocket for real-time task state updates
- Reuse existing `divergence_alert` WebSocket message pattern
- Prefect's `get_run_logger()` can feed into existing logging infrastructure

### With trame visualization

- After `run_solver` task completes → Prefect triggers `TrameSessionManager` launch
- Pipeline state update → React dashboard auto-loads result in trame iframe viewer
- Reuse existing iframe bridge (`CFDViewerBridge.ts`)

### With Docker solver execution

- `run_solver` Prefect task calls existing `docker_executor` module (already exists)
- Prefect handles Docker container lifecycle, logging, and retry policies
- No new Docker integration needed — wrap existing `docker_executor.run()` in a `@task`

---

## Recommended Additions Summary

| Category | Library/Package | Version Caveat | Why |
|----------|----------------|----------------|-----|
| Pipeline engine | `prefect` | ~3.x as of mid-2025 (verify via `pip show prefect`) | Python-native, async FastAPI integration, SQLite state, dynamic DAGs, Docker-native |
| React DAG viz | `@xyflow/react` | ~12.x as of early 2025 (verify via `npm show @xyflow/react`) | React-native DAG library, zoom/pan/minimap, multiple node types |
| State persistence | Prefect built-in (SQLite) | No new dependency | Already part of Prefect |
| Batch scheduling | Prefect dynamic tasks | Part of Prefect | Native parametric sweep support via `itertools.product` |
| Comparison engine | New `comparison_engine.py` | No new dependency | Python module reusing existing infra (report gen, DivergenceDetector) |
| No new task queue | — | — | Prefect handles task queuing internally |
| No new database | — | — | SQLite via Prefect; localStorage via browser |

---

## Anti-Patterns to Avoid

| Anti-pattern | Why | Correct approach |
|-------------|-----|-----------------|
| Adding Celery for "just the task queue" + FSM for state | Two sources of truth; complex integration wiring | Prefect alone |
| Building custom DAG executor | Rewrites battle-tested logic; no dashboard; no persistence | Prefect |
| Using Airflow "because everyone uses it" | Requires Redis + Postgres + multiple processes; massive overhead for single-node | Prefect |
| Adding Temporal (Go-based) | Requires separate server; Go runtime; over-engineered | Prefect |
| Bypassing Prefect and using FastAPI BackgroundTasks for pipeline | No DAG awareness; no state persistence; no retry logic; no visualization | Prefect |

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Prefect recommendation | LOW | Training data ~June 2025; versions and ecosystem may have shifted; no Context7/WebSearch verification |
| Luigi/Airflow/Dagster alternatives | LOW | Same — ecosystem may have evolved significantly |
| @xyflow/react | LOW | Training data ~early 2025; verify current version |
| Integration patterns | MEDIUM | Python-async patterns are well-established; FastAPI + Prefect embedded mode is documented |
| Anti-patterns | MEDIUM | Based on established Python/FastAPI patterns |

---

## Sources

- Prefect docs: https://docs.prefect.io/
- Prefect PyPI: https://pypi.org/pypi/prefect/
- @xyflow/react (React Flow): https://reactflow.dev/
- Luigi (Spotify): https://github.com/spotify/luigi
- Apache Airflow: https://airflow.apache.org/
- Dagster: https://docs.dagster.io/

**Critical note:** No external verification tools (Context7, WebSearch, Exa, Brave) were available at time of writing. All ecosystem assessments are from training data (~June 2025). **Verify current versions and feature availability against live PyPI/npm before implementation.**
