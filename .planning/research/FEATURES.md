# Feature Landscape: Pipeline Orchestration for AI-CFD

**Domain:** Scientific Computing / CFD Workflow Automation
**Project:** AI-CFD Knowledge Harness v1.7.0
**Researched:** 2026-04-12
**Confidence:** MEDIUM (Nextflow/Snakemake/Prefect/Cylc documentation verified via WebFetch)

---

## Introduction

The AI-CFD Knowledge Harness v1.6.0 has discrete components (case generation, solver execution, convergence monitoring, 3D visualization, report generation). v1.7.0 adds an **orchestration layer** that chains these into end-to-end automated pipelines.

Pipeline orchestration in this context means: the coordination layer that manages dependencies, execution order, state, and recovery for a sequence of CFD operations: `generate case parameters -> run solver -> monitor convergence -> visualize results -> generate report`.

---

## What Separates a Shell Script from a Production Pipeline Orchestrator?

| Dimension | Shell Script | Production Orchestrator |
|-----------|-------------|------------------------|
| **Dependency management** | Hardcoded order; runs all commands regardless | DAG-derived execution; runs only when inputs satisfy outputs |
| **Parallelism** | Sequential or manual `&`/wait | Automatic discovery of parallelizable tasks |
| **Failure handling** | Crashes, no resume | Retries, preserved logs, attempt-scaled resources |
| **Reproducibility** | Environment-specific | Containerized, version-tracked, checksum-validated |
| **Portability** | Machine-specific paths/commands | Abstract execution platform (local/cluster/cloud) |
| **State awareness** | Stateless | Tracks success/failure/cached state per step |
| **Resource constraints** | None | Tracks CPU, memory, GPU; scheduler enforces limits |
| **Parametric variations** | Copy-paste scripts | Wildcard/generation patterns; one definition -> N runs |

For CFD specifically:
- A parametric sweep of 20 mesh densities = 20 separate solver runs
- A shell script handles this as 20 hardcoded command blocks
- A production orchestrator treats each as a DAG node with wildcard expansion

**Sources:** Snakemake documentation (shell script vs orchestrator distinction) — WebFetch HIGH confidence

---

## Feature Categories

### Table Stakes (Expected -- missing feels incomplete)

#### PO-01: Pipeline Orchestration Engine
**What it does:** Chains existing components into a directed graph: `generate -> run -> monitor -> visualize -> report`.

**Why expected:** Without orchestration, users manually trigger each step. That is a CLI tool, not a product.

**Execution chain:**
```
Generate (blockMeshDict / case setup via CaseGenerator API)
  -> Run (OpenFOAM Docker solver via executor API)
    -> Monitor (WebSocket convergence, auto-abort on divergence)
      -> Visualize (Trame 3D viewer, auto-load result)
        -> Report (HTML/PDF with literature comparison)
```

**State machine:**
```
PENDING -> RUNNING -> MONITORING -> VISUALIZING -> REPORTING -> COMPLETED
                    -> FAILED (at any stage, with error context)
```

**Each stage must be idempotent:** if monitor fails mid-stream, pipeline resumes from last successful stage, not restart from scratch.

**Complexity:** Medium
- Build on existing FastAPI endpoints
- Define pipeline state machine
- Each stage produces a checkpoint artifact

**Existing system hooks:**
- `POST /cases/generate` (CaseGenerator)
- `POST /jobs/run` (Docker executor)
- WebSocket `/ws/convergence/{job_id}` (monitoring)
- `POST /trame/load` (visualization)
- `POST /reports/generate` (report generator)

---

#### PO-02: Batch Job Scheduling / Parametric Sweep
**What it is in CFD context:** Running the same solver configuration with systematically varied parameters (mesh refinement levels, boundary condition values, turbulence model constants, inlet velocities).

**Why expected:** The equivalent of "5-minute professional KT board design" for CFD is parameter exploration -- users need to sweep `meshSize: [0.1, 0.05, 0.02]` or `inletVelocity: [1, 5, 10]` without writing shell loops.

**Common CFD sweep parameters:**

| Parameter Type | Examples | CFD Implication |
|----------------|----------|-----------------|
| Mesh resolution | `cellSize: [0.1, 0.05, 0.02]` | Refinement study -- tests discretization sensitivity |
| Boundary condition | `inletVelocity: [1, 5, 10]` m/s | Flow regime sensitivity |
| Turbulence model | `model: [kEpsilon, kOmega, SST]` | Model uncertainty |
| Physical property | `viscosity: [1e-5, 1e-4]` | Fluid behavior sensitivity |
| Geometry | `angleOfAttack: [-5, 0, 5, 10]` deg | Performance polar |

**Sweep execution patterns:**
- **Full factorial:** All N1 x N2 x ... combinations (grows combinatorially)
- **One-at-a-time (OAT):** Fix all but one parameter, sweep one, repeat
- **Latin Hypercube:** Sparse sampling for high-dimensional parameter spaces

For v1.7.0, full factorial with concurrency control is the recommended starting point. OAT and Latin Hypercube are future phases.

**Patterns from established tools:**
- **Snakemake:** `expand("{dataset}/a.{ext}", dataset=DATASETS, ext=FORMATS)` -- Cartesian product of parameter lists
- **Prefect:** Task `.map()` spawning N task instances from a list of parameters

**Complexity:** Medium-High
- `ParametricSweep` schema: `{parameter_name: [value1, value2, ...], ...}`
- Sweep engine generates N pipeline instances
- Job queue with concurrency limits (do not run 100 Docker containers simultaneously)
- Individual job status tracking + aggregate sweep progress

**Dependency on existing:** Uses PO-01 as the per-parameter pipeline template.

---

#### PO-03: Cross-Case Comparison Engine
**What it does:** Compares convergence histories, field distributions (velocity/pressure), and key metrics across multiple cases.

**Why expected:** Users generate parametric sweeps to understand sensitivity. Raw job outputs are siloed. Comparison is the analytical layer on top of batch runs.

**Expected behaviors:**
1. **Convergence comparison:** Overlay residual curves (log-scale). X-axis = iteration number (aligned by iteration). Each case gets a distinct line color.
2. **Field comparison:** For a selected iteration (e.g., final), compute delta field = CaseA - CaseB. Display overlaid contours or side-by-side slice views.
3. **Key metrics table:** Per-case summary:
   - Final max velocity
   - Final max pressure
   - Total iterations to convergence
   - Execution time
   - Percentage difference from reference case
4. **Report embedding:** Comparison results embeddable in standard report generator output.

**Complexity:** Medium
- Convergence data: fetch from job history (already tracked via WebSocket)
- Field comparison: extract scalar fields from OpenFOAM results, compute delta
- Needs case metadata storage (already in Notion SSOT)

**Dependency on existing:** Uses Trame visualization (TRAME-01~06 shipped), report generator (Phase 19-22 shipped).

---

### Differentiators (Not expected, but valued)

#### PO-04: Pipeline State Persistence and Recovery
**What it is:** If a pipeline crashes (Docker OOM, WebSocket disconnect), it resumes from the last successful stage, not from scratch.

**Why differentiating:** Most research codebases restart from zero. Production systems (Nextflow, Snakemake, Prefect) treat state as first-class.

**Patterns from established tools:**
- **Nextflow:** `nxusDB` cache per task; `.resume()` reuses cached results
- **Prefect:** "Resuming interrupted runs from the last successful checkpoint"
- **Snakemake:** `--notemp` preserves intermediates; `--rerun-triggers mtime` forces re-execution on change

**How it works:**
- Each pipeline stage writes a checkpoint artifact (completed stage + output artifacts)
- On restart, loader reads checkpoint and skips completed stages
- Idempotency: each stage must be safe to re-run with same inputs

**Complexity:** High
- Requires checkpointing infrastructure (state store, artifact storage)
- Need to handle partial Docker container states
- Cross-stage artifacts must be addressable (case files, result files)

**Dependency on existing:** Uses existing Docker executor and file storage. Needs a new state store (SQLite or Notion page per pipeline run).

---

#### PO-05: Pipeline DAG Visualization
**What it is:** Dashboard display of the pipeline as a dependency graph, with live status indicators per node.

**Why differentiating:** Shell scripts have no graph. Even many "orchestrators" lack live DAG UIs.

**What it shows:**
- Nodes: generate, run, monitor, visualize, report
- Edges: data flow arrows with artifact names
- Node states: pending (gray), running (blue), completed (green), failed (red), skipped (yellow)
- For parametric sweeps: DAG expands to show sweep fan-out pattern

**Comparison with existing tools:**
- Snakemake: `--dag` produces a dot/graphviz representation
- Prefect: Real-time UI with task dependency graph
- Cylc: TUI (`cylc tui`) for terminal-based graph display

**Complexity:** Medium
- DAG can be pre-computed from pipeline definition (static graph)
- Live status requires WebSocket updates per stage
- React component for node rendering (existing dashboard infrastructure)
- For PO-02 sweeps: DAG shows the fan-out/fan-in pattern

---

## Anti-Features (What NOT to Build)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Custom DSL for pipeline definition** | Reinventing the wheel; Nextflow/Snakemake already solved this | Use existing FastAPI endpoints, compose them in Python |
| **HPC scheduler integration (SLURM/PBS)** | Over-scope for v1.7.0; local Docker is current execution target | Defer to future phase if HPC access is needed |
| **Real-time collaborative editing** | Complex multi-user state sync | Single-user pipeline control; collaboration via Notion SSOT |
| **Cloud deployment orchestration (K8s)** | Over-scope; current Docker executor is sufficient | Defer to future phase |
| **Full Nextflow/Snakemake engine port** | These are general-purpose; CFD-specific wrappers add value but complexity is high | Build lightweight CFD-specific orchestrator on top of existing FastAPI |
| **Native ParaView batch processing** | v1.4.0/1.5.0 shipped ParaView Web; batch CLI is separate | Expose existing `pvpython` CLI via Docker exec |
| **Automatic mesh refinement** | AI-driven mesh adaptation is a research problem | Accept mesh parameter as input; do not try to optimize it automatically |

---

## Feature Dependency Graph

```
PO-01 (Orchestration Engine)
  ├── PO-02 (Batch/Parametric Sweep) [depends on PO-01 as template]
  ├── PO-03 (Cross-Case Comparison) [depends on completed cases]
  ├── PO-04 (State Persistence) [spans all pipeline stages]
  └── PO-05 (DAG Visualization) [visualizes PO-01/02]

Existing System (v1.6.0):
  ├── CaseGenerator (CLI -> API)
  ├── Docker Executor (OpenFOAM)
  ├── WebSocket Convergence Monitor
  ├── Trame 3D Viewer
  └── Report Generator (HTML/PDF/JSON)
```

---

## MVP Recommendation

**Prioritize in order:**

1. **PO-01** -- Without orchestration engine, nothing else matters. Core value is chaining isolated components. Target: single-case end-to-end pipeline with manual trigger.

2. **PO-02** -- Batch scheduling is the natural extension of PO-01. The parametric sweep pattern is well-understood and directly serves parameter exploration. Target: parameter grid with N cases queued and executed sequentially with concurrency control.

3. **PO-05** -- DAG visualization builds on PO-01's pipeline definition. It is the clearest "wow" indicator for an orchestration system and directly answers "what separates this from a shell script."

**Defer:**
- **PO-03** (Cross-Case Comparison): Depends on having completed cases (PO-02 output). Build after PO-02 has runs to compare.
- **PO-04** (State Persistence): Highest complexity, lowest immediate value for demo. Defer to a maintenance phase after user feedback.

---

## Complexity Assessment Summary

| Feature | Complexity | Risk | Reason |
|---------|------------|------|--------|
| PO-01: Orchestration Engine | Medium | Low | Uses existing APIs; just needs state machine and orchestration layer |
| PO-02: Batch Scheduling | Medium-High | Medium | Concurrency control, sweep generation, queue management |
| PO-03: Cross-Case Comparison | Medium | Medium | Field extraction + comparison algorithms |
| PO-04: State Persistence | High | High | Checkpoint infrastructure, idempotency guarantees, partial failure handling |
| PO-05: DAG Visualization | Medium | Low | React component on existing dashboard; DAG derived from pipeline definition |

---

## Parametric Sweep Deep Dive (PO-02)

In CFD context, a parametric sweep means varying one or more parameters across a defined range and observing the effect on the solution.

**Execution requirements:**
- **Queue management:** N sweep cases queued, executed with concurrency limit (e.g., max 2 simultaneous Docker containers)
- **Case isolation:** Each sweep case gets its own Docker container, own working directory
- **Progress tracking:** Per-case status (pending/running/completed/failed) + aggregate progress
- **Cancellation:** Ability to abort entire sweep or individual cases

**Output organization:**
```
sweep_<id>/
  case_<param_set_hash>/
    case/           (OpenFOAM case files)
    results/        (solver output)
    residuals.csv   (convergence history)
    report/         (PDF/HTML report)
  summary.csv       (key metrics across all cases)
  comparison.pdf    (cross-case comparison report)
```

---

## Cross-Case Comparison Expected Behavior (PO-03)

Given N cases from a parametric sweep, the comparison engine produces:

1. **Convergence comparison:** Residual curves overlaid on log-scale, iteration-aligned across cases. Visual diff of how fast each case converged.

2. **Field comparison:** For a selected time step (e.g., final), delta field = CaseA - CaseB. Displays absolute difference magnitude as a scalar field.

3. **Metrics table:**

   | Case | Max Velocity | Max Pressure | Iterations | Exec Time | vs Ref |
   |------|-------------|-------------|------------|-----------|--------|
   | ref  | 12.34 m/s   | 101325 Pa   | 523        | 142s      | --     |
   | A    | 12.41 m/s   | 101340 Pa   | 489        | 138s      | +0.6%  |
   | B    | 11.98 m/s   | 101310 Pa   | 601        | 165s      | -2.9%  |

4. **Report embedding:** Comparison results as a section in the standard PDF/HTML report.

---

## Sources

- [Nextflow documentation](https://www.nextflow.io/docs/latest/index.html) -- dataflow model, channels, processes (WebFetch HIGH confidence)
- [Snakemake documentation](https://snakemake.readthedocs.io/en/stable/) -- wildcards, expand(), DAG phase, reporting, shell script vs orchestrator (WebFetch HIGH confidence)
- [Prefect documentation](https://docs.prefect.io/latest/) -- flows, tasks, state management, caching, retries (WebFetch HIGH confidence)
- [Cylc documentation](https://github.com/cylc/cylc-flow) -- HPC workflow engine, cycling systems (WebFetch MEDIUM confidence)
- [Dask documentation](https://docs.dask.org/en/stable/) -- parallel execution, futures, distributed computing (WebFetch HIGH confidence)

---

*Feature research for: Pipeline Orchestration & Automation (AI-CFD Knowledge Harness v1.7.0)*
*Researched: 2026-04-12*
