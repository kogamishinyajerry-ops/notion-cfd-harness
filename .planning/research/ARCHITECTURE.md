# Architecture Research: knowledge_compiler / api_server Integration

**Project:** AI-CFD Knowledge Harness v1.8.0
**Researched:** 2026-04-12
**Confidence:** MEDIUM-HIGH
**Mode:** Ecosystem (integration architecture)

---

## Executive Summary

The `knowledge_compiler/` and `api_server/` systems are currently **parallel, independent stacks** that share only one integration point: `step_wrappers.py`'s `generate_wrapper` calls `GenericOpenFOAMCaseGenerator`. The v1.8.0 goal is to bridge them so that GoldStandard case metadata (ColdStartCase, BenchmarkSuite) can drive Pipeline creation, and solver results can be validated against BenchmarkSuite expected outputs.

The core integration challenge: **knowledge_compiler uses rich domain dataclasses** (RunContext, TaskIntent, PhysicsPlan, BenchmarkCase) while **api_server uses flat Pydantic request/response models** (PipelineCreate, StepResult, SweepCaseResponse). Bridging requires a translation/adapter layer (`GoldStandardLoader`) that maps domain objects to pipeline step parameters.

---

## Current Architecture Map

```
knowledge_compiler/
├── phase1/gold_standards/cold_start.py
│   ├── ColdStartCase       — YAML-loaded CFD case metadata (id, rank, platform,
│   │                         tier, mesh_strategy, solver_command, ...)
│   └── ColdStartWhitelist  — Container with filter methods (by_platform, core_seeds, ...)
│
├── phase2c/benchmark_replay.py
│   ├── BenchmarkCase       — Gold standard case (input_data, expected_output,
│   │                         tolerance, constraints, category, ...)
│   ├── BenchmarkReplayResult — Per-replay validation result
│   ├── BenchmarkReplayEngine — Replay orchestration
│   └── BenchmarkSuite      — Case registry + JSON file storage
│
├── phase2c/knowledge_compiler.py
│   ├── KnowledgeManager    — PatternKnowledge/RuleKnowledge CRUD
│   ├── PatternKnowledge    — Extracted anomaly/fix patterns (L2)
│   └── KnowledgeValidator  — Confidence + success rate validation
│
├── orchestrator/
│   ├── contract.py         — RunContext, TaskIntent, PhysicsPlan, MeshPlan,
│   │                         SolverPlan, MonitorReport, VerificationReport
│   └── interfaces.py       — ISolverRunner, IVerifyConsole protocols
│
└── executables/
    └── bench_*.py          — Per-benchmark validator scripts

api_server/
├── services/
│   ├── pipeline_executor.py
│   │   └── PipelineExecutor — threading.Thread, DAG topological sort,
│   │                         StepResult.status (SUCCESS/DIVERGED/ERROR)
│   ├── sweep_runner.py
│   │   └── SweepRunner     — Full-factorial, asyncio.Semaphore concurrency,
│   │                         per-combination pipeline creation
│   ├── comparison_service.py
│   │   ├── parse_convergence_log() — OpenFOAM log → residual time series
│   │   ├── compute_delta_field()   — pvpython delta field
│   │   └── ComparisonService       — cross-case provenance + metrics
│   ├── pipeline_db.py
│   │   ├── PipelineDBService — pipelines + pipeline_steps CRUD
│   │   └── SweepDBService   — sweeps + sweep_cases + comparisons CRUD
│   └── step_wrappers.py
│       ├── generate_wrapper — GenericOpenFOAMCaseGenerator (knowledge_compiler)
│       ├── run_wrapper     — JobService.submit_job + poll
│       ├── monitor_wrapper — convergence polling → DIVERGED/SUCCESS
│       ├── visualize_wrapper — TrameSessionManager
│       └── report_wrapper  — ReportGenerator (knowledge_compiler)
│
└── models.py
    └── PipelineCreate, PipelineStep, StepType, StepResult,
        SweepCaseResponse, ComparisonResponse, ProvenanceMetadata, ...
```

---

## Existing Integration Points

### 1. `generate_wrapper` calls `GenericOpenFOAMCaseGenerator`

```python
# step_wrappers.py → generate_wrapper
from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
    GenericOpenFOAMCaseGenerator,
)
generator = GenericOpenFOAMCaseGenerator(**params)
output = generator.generate()
```

This is the **only** existing bridge. It works because `generate_wrapper` passes `step.params` as kwargs to the generator. The interface is: dict-in, dict-out with `case_dir` key.

### 2. `ComparisonService` convergence log parser

```python
# comparison_service.py
time_pattern = re.compile(r"Time = ([\d.]+)")
residual_pattern = re.compile(r"(Ux|Uy|Uz|p)\s*=\s*([\d.e+-]+)")
```

This mirrors the regex patterns in `knowledge_compiler/orchestrator/monitor.py` (confirmed in comparison_service.py comment). This is **convergent duplication** — not a real integration point, but evidence both systems parse the same log format.

---

## Gap Analysis

### Gap 1: No ColdStartCase to Pipeline mapping

`ColdStartWhitelist` contains rich metadata, but there is no path from a `ColdStartCase` to a `PipelineCreate` spec. The `solver_command` field (e.g., `"icoFoam"`) contains the solver name, but the pipeline system has no concept of "this case should use solver X with mesh_strategy Y."

| ColdStartCase field | PipelineStep mapping |
|---------------------|---------------------|
| `solver_command` | `run_wrapper` params: `solver_name` |
| `mesh_strategy: "A"` | No generate step (use existing mesh) |
| `mesh_strategy: "B"` | Add `generate_wrapper` step with mesh script |
| `case_name` | Pipeline `name` field |
| `platform: "OpenFOAM"` | Default; `"SU2"` needs separate step type |
| `source_location.local_case_path` | Pass as `case_dir` param to run step |

### Gap 2: BenchmarkSuite not integrated with ComparisonService

`BenchmarkSuite` validates outputs against `expected_output`. `ComparisonService` computes convergence metrics. **These are complementary**: ComparisonService handles quantitative metrics, BenchmarkSuite handles threshold validation.

### Gap 3: SweepRunner provenance metadata gap

`SweepCaseResponse` has 4 provenance columns (openfoam_version, compiler_version, mesh_seed_hash, solver_config_hash), but no code populates them. ColdStartWhitelist has no hash fields.

### Gap 4: No GoldStandardLoader service in api_server

`ColdStartWhitelist` is only accessible via `load_cold_start_whitelist()`. The api_server has no API endpoint to list or query it.

---

## Proposed Integration Architecture

### New Component: GoldStandardLoader Service

```
api_server/services/gold_standard_loader.py   (NEW)
```

**Responsibility:** Load and serve ColdStartCase metadata as API-selectable items, translate cases into PipelineCreate specs.

```python
class ColdStartCaseDTO(BaseModel):
    """API-facing GoldStandard case metadata."""
    id: str
    rank: int
    platform: str
    tier: str
    dimension: str
    difficulty: str
    case_name: str
    mesh_strategy: str  # "A" = ready mesh, "B" = script-built
    has_ready_mesh: bool
    solver_command: str
    success_criteria: str
    source_provenance: str


class GoldStandardLoader:
    def list_cases(
        platform: Optional[str] = None,
        tier: Optional[str] = None,
        difficulty: Optional[str] = None,
        has_ready_mesh: bool = False,
    ) -> List[ColdStartCaseDTO]: ...

    def get_case(self, case_id: str) -> Optional[ColdStartCaseDTO]: ...

    def build_pipeline_spec(
        self,
        case_id: str,
        output_dir: str,
    ) -> PipelineCreate: ...
```

**`build_pipeline_spec` translation logic:**

```python
def build_pipeline_spec(self, case_id: str, output_dir: str) -> PipelineCreate:
    case = self.get_case(case_id)
    steps = []

    if not case.has_ready_mesh:
        steps.append(PipelineStep(
            step_id="generate_mesh",
            step_type=StepType.GENERATE,
            step_order=0,
            depends_on=[],
            params={"case_name": case.case_name},
        ))

    steps.append(PipelineStep(
        step_id="run_solver",
        step_type=StepType.RUN,
        step_order=1,
        depends_on=["generate_mesh"] if not case.has_ready_mesh else [],
        params={
            "solver_name": self._parse_solver(case.solver_command),
            "case_dir": case.source_location.get("local_case_path", ""),
            "output_dir": output_dir,
        },
    ))

    steps.append(PipelineStep(
        step_id="monitor_convergence",
        step_type=StepType.MONITOR,
        step_order=2,
        depends_on=["run_solver"],
        params={"job_id": "{{ run_solver.job_id }}"},
    ))

    return PipelineCreate(
        name=f"GoldStandard: {case.case_name}",
        description=f"Auto-generated from {case.id}",
        steps=steps,
        config={"gold_standard_case_id": case.id},
    )
```

### Pipeline Template Registry

Pre-stored `PipelineCreate` specs keyed by ColdStartCase ID. This avoids repeated translation logic and makes templates inspectable before creation.

```python
class PipelineTemplateRegistry:
    TEMPLATES: Dict[str, PipelineCreate] = {
        "OF-01": PipelineCreate(name="OF-01 Lid-Driven Cavity", steps=[...]),
        "OF-02": PipelineCreate(name="OF-02", steps=[...]),
        ...
    }
```

Templates are populated by a build step that translates all 30 ColdStartCases. The `gold_standard_case_id` in `config` provides provenance.

### BenchmarkVerificationService (NEW)

```
api_server/services/benchmark_verification.py   (NEW)
```

```python
class BenchmarkVerificationService:
    def __init__(self, benchmark_suite: BenchmarkSuite):
        self._suite = benchmark_suite

    def verify_case(
        self,
        case_id: str,
        completed_case_dir: Path,
    ) -> VerificationReportDTO:
        benchmark = self._suite.get_case(case_id)
        if not benchmark:
            raise ValueError(f"No benchmark for case {case_id}")

        actual_output = self._parse_solver_output(completed_case_dir)
        passed, result = benchmark.validate_output(actual_output)

        return VerificationReportDTO(
            case_id=case_id,
            benchmark_id=benchmark.case_id,
            passed=passed,
            field_results=result["field_results"],
            errors=result["errors"],
        )
```

### ComparisonService Extension

`ComparisonService` stays as-is for convergence + provenance. Add `verify_against_benchmark()` that delegates to `BenchmarkVerificationService`:

```python
# In ComparisonService
def verify_against_benchmark(
    self,
    case_id: str,
    benchmark_case_id: str,
    case_output_dir: Path,
) -> VerificationReportDTO:
    verifier = BenchmarkVerificationService()
    return verifier.verify_case(benchmark_case_id, case_output_dir)
```

This keeps ComparisonService as the facade while delegating domain logic to knowledge_compiler's BenchmarkSuite.

---

## Data Flow

```
[User selects ColdStartCase via GET /gold-standard-cases]
         │
         ▼
[POST /pipelines/from-gold-standard/{case_id}]
         │
         ▼
GoldStandardLoader.build_pipeline_spec(case_id)
         │
         ├─→ Template lookup (TEMPLATE registry)
         │
         └─→ PipelineCreate(spec)
                   │
                   ▼
         PipelineDBService.create_pipeline()
                   │
                   ▼
         PipelineExecutor (threading.Thread)
                   │
                   ├─→ generate_wrapper (mesh generation)
                   │
                   ├─→ run_wrapper (solver execution)
                   │
                   ├─→ monitor_wrapper (convergence)
                   │
                   ├─→ visualize_wrapper (trame)
                   │
                   └─→ report_wrapper (HTML report)
                            │
                            ▼
              [SweepCaseResponse stored in SQLite with provenance]
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
    [GET /comparisons]            [POST /verifications]
              │                           │
              ▼                           ▼
    ComparisonService           BenchmarkVerificationService
    - convergence_data          - BenchmarkSuite.validate_output()
    - provenance_mismatch       - field-by-field pass/fail
    - delta_field
```

---

## Shared Models (Proposed)

### New Pydantic models in api_server/models.py

```python
class GoldStandardCase(BaseModel):
    """API-facing GoldStandard case metadata."""
    id: str
    rank: int
    platform: str
    tier: str
    dimension: str
    difficulty: str
    case_name: str
    mesh_strategy: str
    has_ready_mesh: bool
    solver_command: str
    success_criteria: str
    source_provenance: str


class VerificationReportDTO(BaseModel):
    """Result of BenchmarkSuite validation on a completed case."""
    case_id: str
    benchmark_id: str
    passed: bool
    field_results: Dict[str, str]
    errors: List[str]
    timestamp: datetime
```

### Schema Extension: sweep_cases benchmark columns

```sql
-- Schema v5: Add to sweep_cases table
ALTER TABLE sweep_cases ADD COLUMN benchmark_id TEXT;
ALTER TABLE sweep_cases ADD COLUMN verification_passed BOOLEAN;
ALTER TABLE sweep_cases ADD COLUMN verification_errors TEXT;  -- JSON
```

---

## API Contract Additions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/gold-standard-cases` | List ColdStartWhitelist cases (filterable) |
| `GET` | `/gold-standard-cases/{case_id}` | Single case metadata |
| `POST` | `/pipelines/from-gold-standard/{case_id}` | Create pipeline from GoldStandard template |
| `POST` | `/verifications` | Run BenchmarkSuite validation on completed case |
| `GET` | `/verifications/{case_id}` | Get verification report for a case |

**Request/Response examples:**

```python
# POST /pipelines/from-gold-standard/OF-01
# Request: {"output_dir": "data/gold_standard/OF-01"}
# Response: 201 PipelineResponse with config.gold_standard_case_id = "OF-01"
```

```python
# POST /verifications
# Request: {
#   "case_id": "CASE-XXXXXXXX",
#   "benchmark_case_id": "BENCH-002",
#   "case_output_dir": "data/sweep_SWEEP-XX/ABC123/"
# }
# Response: VerificationReportDTO(passed, field_results, errors)
```

---

## Build Order

### Phase 1: GoldStandardLoader + Template Registry
1. Create `GoldStandardLoader` in `api_server/services/`
2. Create `ColdStartCaseDTO` Pydantic model in `api_server/models.py`
3. Implement `GoldStandardLoader.list_cases()` using existing `load_cold_start_whitelist()`
4. Implement `GoldStandardLoader.build_pipeline_spec()` with template lookup
5. Create pre-built template registry for all 30 ColdStartCases
6. Add `GET /gold-standard-cases` and `POST /pipelines/from-gold-standard/{case_id}` endpoints
7. Add unit tests

**Dependency:** None — uses only existing `cold_start.py`.

### Phase 2: BenchmarkVerificationService
1. Create `BenchmarkVerificationService` in `api_server/services/`
2. Implement `verify_case()` delegating to `BenchmarkSuite` from knowledge_compiler
3. Implement output parser for OpenFOAM results
4. Add schema v5 migration to `pipeline_db.py`
5. Add `POST /verifications` and `GET /verifications/{case_id}` endpoints
6. Add unit tests with mock BenchmarkSuite

**Dependency:** Phase 1 (GoldStandardLoader provides case metadata for verification).

### Phase 3: ComparisonService + BenchmarkSuite Bridge
1. Add `verify_against_benchmark()` to `ComparisonService`
2. Add provenance hash computation functions
3. Wire provenance population into `run_wrapper` diagnostics
4. Update `update_case_result()` to compute + store provenance fields
5. Add integration tests: full pipeline -> verification -> comparison

**Dependency:** Phase 2 complete.

---

## Anti-Patterns to Avoid

### Don't convert domain dataclasses to Pydantic in knowledge_compiler
Rich domain dataclasses (`ColdStartCase`, `BenchmarkCase`, `PhysicsPlan`) live in knowledge_compiler and must NOT be converted to Pydantic there. The bridge layer translates them to Pydantic DTOs at the API boundary. This keeps knowledge_compiler decoupled from api_server's HTTP layer.

### Don't make SweepRunner aware of GoldStandardLoader
SweepRunner creates pipelines from a base pipeline template + param_grid. The base pipeline for a sweep is pre-created via `POST /pipelines/from-gold-standard/{case_id}`, and SweepRunner operates on it unchanged.

### Don't duplicate BenchmarkSuite storage
BenchmarkSuite already manages JSON file storage at `.benchmarks/`. `BenchmarkVerificationService` uses an in-process BenchmarkSuite instance. Comparison results are stored in SQLite via the `comparisons` table extension.

---

## Open Questions

1. **SU2 platform support**: ColdStartWhitelist has `platform: "SU2"` cases. Will SU2 cases use a separate step type, or will they be handled via generic Docker runner?

2. **Parametric sweep with GoldStandard cases**: Can a SweepRunner base pipeline come from a GoldStandard template? The current ColdStartCase has a single `solver_command` string — param-grid overrides (e.g., varying Reynolds number) need a design.

3. **mesh_seed_hash / solver_config_hash computation**: These provenance fields are defined in schema v4 but not populated. Should they be computed by `run_wrapper` from the actual case directory post-execution, or should they come from the ColdStartWhitelist YAML?

4. **BenchmarkSuite storage path**: The `.benchmarks/` default path must be configurable for api_server deployment. Should use `DATA_DIR / ".benchmarks"` to match where `pipelines.db` lives.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Integration points identified | MEDIUM-HIGH | Single existing bridge confirmed; rest inferred from parallel system analysis |
| Build order | HIGH | Clear dependency chain; Phase 1 has no external deps |
| Data flow | MEDIUM | Template registry approach is sound; SU2/sweep questions unresolved |
| Anti-patterns | HIGH | No-conversion and no-duplication rules are unambiguous |

---

## Sources

- Code analysis: `cold_start.py`, `benchmark_replay.py`, `comparison_service.py`, `pipeline_db.py`, `pipeline_executor.py`, `sweep_runner.py`, `step_wrappers.py`, `orchestrator/contract.py`, `orchestrator/interfaces.py`, `phase2c/knowledge_compiler.py`
- Project definition: `.planning/PROJECT.md` v1.8.0 goals
