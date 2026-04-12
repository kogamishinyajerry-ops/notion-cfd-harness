# STACK.md — v1.8.0 GoldStandard Expansion + System Integration

**Project:** AI-CFD Knowledge Harness v1.8.0
**Domain:** CFD knowledge compilation + workflow orchestration integration
**Researched:** 2026-04-12
**Confidence:** MEDIUM (existing patterns well-understood from codebase; external library verification unavailable)

---

## Context: What Exists vs. What Is Needed

### Current GoldStandard State (v1.7.0)

| Item | Status |
|------|--------|
| `cold_start_whitelist.yaml` | 30 cases defined (OF-01~06, SU2-01~24) |
| `phase1/gold_standards/cold_start.py` | ColdStartCase/ColdStartWhitelist loader (YAML only, no GoldStandard data) |
| `phase1/gold_standards/` implementations | **5 exist**: lid_driven_cavity, backward_facing_step, inviscid_bump, inviscid_wedge, laminar_flat_plate |
| SU2-02, SU2-04, SU2-09, SU2-10, SU2-19, OF-04 | **MISSING** — high-value cases from whitelist with no GoldStandard module |
| GoldStandardLoader | Does not exist as a separate abstraction — each case is standalone |
| knowledge_compiler ↔ api_server bridge | **MISSING** — no integration between GoldStandardRegistry and PipelineExecutor/ComparisonService |

### What v1.8.0 Must Add

1. **24 missing GoldStandard case modules** (SU2 + OF cases from whitelist)
2. **GoldStandardRegistry** — unified loader that aggregates all gold_standards/
3. **Bridge service** — exposes GoldStandardRegistry to api_server PipelineExecutor/ComparisonService

---

## GoldStandard Case Architecture (Existing Pattern)

Each GoldStandard module in `phase1/gold_standards/` follows this dataclass pattern:

```python
# Constants class — literature reference data
class {Case}Constants:
    # Physical/geometry parameters
    # Benchmark data (e.g., Ghia 1982 velocity profiles)

# ReportSpec factory — defines required plots, metrics, sections
def create_{case}_spec(...) -> ReportSpec

# GateValidator — validates new results against gold standard
class {Case}GateValidator:
    def validate_report_spec(self, spec: ReportSpec) -> Dict[str, Any]

# Optional: reference data accessors
def get_expected_{quantity}(...) -> Any
```

**No new libraries needed for GoldStandard implementations** — all use existing `knowledge_compiler.phase1.schema` (dataclasses: ReportSpec, PlotSpec, MetricSpec, SectionSpec, ComparisonType, KnowledgeLayer, KnowledgeStatus).

---

## Recommended Stack Additions

### 1. GoldStandardRegistry — New Python Module (knowledge_compiler/phase1/gold_standards/registry.py)

**Purpose:** Unified entry point that aggregates all individual GoldStandard modules and the ColdStartWhitelist YAML.

**Why a registry instead of importing all modules directly:**
- Avoids circular import risk as case count grows
- Provides a stable API for api_server bridge
- Supports lazy loading (only import actual module when case is requested)

**Design:**

```python
# knowledge_compiler/phase1/gold_standards/registry.py

from typing import Dict, List, Optional, Callable

class GoldStandardRegistry:
    """Registry mapping case_id -> (spec_factory, validator_factory, reference_data_fn)."""

    def __init__(self):
        self._spec_factories: Dict[str, Callable] = {}
        self._validators: Dict[str, type] = {}
        self._reference_data: Dict[str, Callable] = {}
        self._whitelist = load_cold_start_whitelist()

    def register(self, case_id: str,
                 spec_factory: Callable,
                 validator_class: type,
                 reference_fn: Optional[Callable] = None):
        self._spec_factories[case_id] = spec_factory
        self._validators[case_id] = validator_class
        self._reference_data[case_id] = reference_fn

    def get_whitelist_case(self, case_id: str) -> Optional[ColdStartCase]:
        """Get ColdStartCase metadata from whitelist YAML."""
        return self._whitelist.get_by_id(case_id)

    def list_available(self) -> List[str]:
        """Return case_ids that have GoldStandard modules registered."""
        return list(self._spec_factories.keys())

    def get_spec(self, case_id: str, **kwargs) -> ReportSpec:
        """Create ReportSpec for case_id."""
        factory = self._spec_factories.get(case_id)
        if not factory:
            raise KeyError(f"No GoldStandard spec factory for {case_id}")
        return factory(**kwargs)

    def get_validator(self, case_id: str):
        """Instantiate validator for case_id."""
        validator_class = self._validators.get(case_id)
        if not validator_class:
            return None
        return validator_class()

    def get_reference_data(self, case_id: str, **kwargs):
        """Get literature reference data (e.g., Ghia benchmark values)."""
        fn = self._reference_data.get(case_id)
        if not fn:
            return None
        return fn(**kwargs)
```

**Registration at module init** (auto-registers existing + new cases):

```python
# Auto-discover and register all gold_standard modules
from importlib import import_module, walk_packages
import knowledge_compiler.phase1.gold_standards as pkg

for _, module_name, _ in walk_packages(pkg.__path__, pkg.__name__ + "."):
    if module_name.endswith("_registry"):
        continue
    mod = import_module(module_name)
    # Convention: module exposes register(registry) function
    if hasattr(mod, "register"):
        mod.register(registry)
```

**Installation:** No new dependencies — pure Python with `importlib`.

---

### 2. Bridge Service — api_server/services/gold_standard_service.py

**Purpose:** Exposes GoldStandardRegistry to FastAPI endpoints, PipelineExecutor, and ComparisonService.

**No new libraries needed.** Uses existing FastAPI + Pydantic patterns from `api_server/models.py`.

```python
# api_server/services/gold_standard_service.py

from typing import List, Optional, Dict, Any
from knowledge_compiler.phase1.gold_standards.registry import GoldStandardRegistry
from knowledge_compiler.phase1.gold_standards import (
    load_cold_start_whitelist,
)
from api_server.models import ColdStartCaseResponse  # Pydantic model

_registry: Optional[GoldStandardRegistry] = None

def get_gold_standard_registry() -> GoldStandardRegistry:
    global _registry
    if _registry is None:
        _registry = GoldStandardRegistry()
        _register_all_cases(_registry)
    return _registry

def _register_all_cases(registry: GoldStandardRegistry):
    """Import all gold_standard modules to trigger auto-registration."""
    from knowledge_compiler.phase1.gold_standards import (
        lid_driven_cavity,
        backward_facing_step,
        inviscid_bump,
        inviscid_wedge,
        laminar_flat_plate,
    )
    # Register each — each module has register(registry) function
    lid_driven_cavity.register(registry)
    backward_facing_step.register(registry)
    inviscid_bump.register(registry)
    inviscid_wedge.register(registry)
    laminar_flat_plate.register(registry)
    # New cases added in v1.8.0 will auto-register via same pattern

class GoldStandardService:
    """API-facing service wrapping GoldStandardRegistry."""

    def __init__(self):
        self._registry = get_gold_standard_registry()

    def list_cases(self, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all GoldStandard case IDs, optionally filtered by platform."""
        whitelist = load_cold_start_whitelist()
        cases = whitelist.by_platform(platform) if platform else whitelist.cases
        return [
            {
                "id": c.id,
                "case_name": c.case_name,
                "platform": c.platform,
                "tier": c.tier,
                "difficulty": c.difficulty,
                "has_gold_standard": c.id in self._registry.list_available(),
            }
            for c in cases
        ]

    def get_case_spec(self, case_id: str, **kwargs) -> Dict[str, Any]:
        """Get ReportSpec dict for a case."""
        spec = self._registry.get_spec(case_id, **kwargs)
        return spec.to_dict()

    def get_reference_data(self, case_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Get literature reference data for validation."""
        return self._registry.get_reference_data(case_id, **kwargs)

    def validate_result(self, case_id: str, result_spec: Dict) -> Dict[str, Any]:
        """Validate a result ReportSpec against gold standard."""
        validator = self._registry.get_validator(case_id)
        if not validator:
            return {"passed": False, "error": f"No validator for {case_id}"}
        from knowledge_compiler.phase1.schema import ReportSpec
        spec = ReportSpec.from_dict(result_spec)
        return validator.validate_report_spec(spec)
```

**Pydantic models** for API responses (extend `api_server/models.py`):

```python
class GoldStandardCaseResponse(BaseModel):
    id: str
    case_name: str
    platform: str
    tier: str
    difficulty: str
    has_gold_standard: bool

class GoldStandardListResponse(BaseModel):
    cases: List[GoldStandardCaseResponse]
    total: int
```

---

### 3. REST API Router — api_server/routers/gold_standards.py

**No new dependencies** — follows existing router pattern from `api_server/routers/cases.py`, `knowledge.py`.

```python
# api_server/routers/gold_standards.py
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/gold-standards", tags=["gold-standards"])

@router.get("/")
async def list_gold_standard_cases(
    platform: Optional[str] = Query(None, description="Filter by platform (OpenFOAM/SU2)")
):
    service = GoldStandardService()
    cases = service.list_cases(platform=platform)
    return {"cases": cases, "total": len(cases)}

@router.get("/{case_id}/spec")
async def get_case_spec(case_id: str):
    service = GoldStandardService()
    return service.get_case_spec(case_id)

@router.get("/{case_id}/reference")
async def get_reference_data(case_id: str):
    service = GoldStandardService()
    data = service.get_reference_data(case_id)
    if data is None:
        raise HTTPException(404, f"No reference data for {case_id}")
    return data

@router.post("/{case_id}/validate")
async def validate_result(case_id: str, result: Dict[str, Any]):
    service = GoldStandardService()
    return service.validate_result(case_id, result)
```

**Register in `api_server/main.py`:**
```python
from api_server.routers import gold_standards
app.include_router(gold_standards.router, prefix=API_PREFIX, tags=["gold-standards"])
```

---

### 4. Integration: PipelineExecutor StepType — GOLDSTANDARD (optional v1.8.0)

**No new library** — extend existing `StepType` enum and `step_wrappers.py`.

When a pipeline step has `step_type=GOLDSTANDARD`, the wrapper fetches the GoldStandard spec and uses it as the template for case generation:

```python
# In api_server/services/step_wrappers.py (extend)

async def gold_standard_wrapper(step, cancel_event: threading.Event) -> StepResult:
    """
    Load GoldStandard case from registry and generate a pipeline-ready case.
    This is a pipeline SEED step — produces case_dir for downstream run steps.
    """
    from api_server.services.gold_standard_service import get_gold_standard_registry

    params = step.params
    case_id = params.get("gold_standard_case_id")  # e.g., "SU2-02"

    registry = get_gold_standard_registry()
    spec_dict = registry.get_spec(case_id)
    whitelist_case = registry.get_whitelist_case(case_id)

    def _generate_blocking():
        # Use whitelist_case.source_location to set up the case directory
        # Use spec_dict to configure the ReportSpec for this pipeline
        case_dir = setup_case_from_whitelist(whitelist_case)
        return {"case_dir": str(case_dir), "spec": spec_dict, "case_id": case_id}

    output = await asyncio.to_thread(_generate_blocking)

    return StepResult(
        status=StepResultStatus.SUCCESS,
        exit_code=0,
        validation_checks={"gold_standard_loaded": True},
        diagnostics={
            "case_id": case_id,
            "case_dir": output["case_dir"],
            "spec": output["spec"],
        }
    )
```

**In `execute_step` dispatch table** (add GOLDSTANDARD to existing 5 types):
```python
dispatch = {
    StepType.GENERATE: generate_wrapper,
    StepType.RUN: run_wrapper,
    StepType.MONITOR: monitor_wrapper,
    StepType.VISUALIZE: visualize_wrapper,
    StepType.REPORT: report_wrapper,
    StepType.GOLDSTANDARD: gold_standard_wrapper,  # NEW
}
```

---

### 5. Integration: ComparisonService GoldStandard Validation

**No new library** — extend `ComparisonService` to validate results against GoldStandard reference data:

```python
# In api_server/services/comparison_service.py (extend)

def validate_against_gold_standard(
    self,
    case_id: str,
    result_dir: Path,
    gold_standard_case_id: str,
) -> Tuple[bool, str, Optional[Dict]]:
    """
    Compare a completed case result against its GoldStandard reference data.
    Returns (passed, error_message, validation_details).
    """
    from api_server.services.gold_standard_service import get_gold_standard_registry

    registry = get_gold_standard_registry()

    # Get reference data (e.g., Ghia 1982 centerline velocities)
    ref_data = registry.get_reference_data(gold_standard_case_id)
    if not ref_data:
        return False, f"No reference data for {gold_standard_case_id}", None

    # Parse solver result from result_dir
    result_data = self._parse_result_fields(result_dir)

    # Compare against reference
    validator = registry.get_validator(gold_standard_case_id)
    if not validator:
        return False, f"No validator for {gold_standard_case_id}", None

    validation_result = validator.validate_result(result_data, ref_data)
    return (
        validation_result["passed"],
        validation_result.get("error", ""),
        validation_result,
    )
```

---

## New GoldStandard Case Implementation Pattern

Each of the 24 missing cases follows this zero-dependency pattern:

```python
# knowledge_compiler/phase1/gold_standards/supersonic_wedge.py (SU2-02)

from knowledge_compiler.phase1.schema import (
    ProblemType, ReportSpec, PlotSpec, MetricSpec, SectionSpec,
    ComparisonType, KnowledgeLayer, KnowledgeStatus,
)

class SupersonicWedgeConstants:
    """SU2-02: Inviscid supersonic wedge, M=2.0, 15-degree wedge."""
    MACH = 2.0
    WEDGE_ANGLE = 15.0
    SHOCK_ANGLE = 45.34  # degrees — from theta-beta-M relation
    PRESSURE_JUMP = 2.19  # p2/p1

def create_supersonic_wedge_spec(...) -> ReportSpec:
    """Create ReportSpec following the established pattern."""
    ...

class SupersonicWedgeGateValidator:
    """Validate wedge results against analytical shock relations."""
    ...

def get_expected_shock_angle(mach: float, wedge_angle: float) -> float:
    """Analytical shock angle from theta-beta-M relation."""
    ...

def register(registry: GoldStandardRegistry):
    """Module-level auto-registration hook."""
    registry.register(
        case_id="SU2-02",
        spec_factory=create_supersonic_wedge_spec,
        validator_class=SupersonicWedgeGateValidator,
        reference_fn=get_expected_shock_angle,
    )
```

**Pattern rationale:**
- `register(registry)` hook enables auto-discovery without import-time side effects
- Constants + analytical formulas (no external data files needed)
- SU2 cases use analytical reference data (oblique shock relations) — no external libraries
- OF cases use OpenFOAM tutorial case directories as reference

---

## Version Specifications

| Component | Version/Constraint | Notes |
|-----------|-------------------|-------|
| Python | >=3.10 | Type hints, dataclass field defaults |
| PyYAML | >=6.0 | Already in cold_start.py import |
| FastAPI | >=0.109.0 | Already in api_server/requirements.txt |
| Pydantic | >=2.5.0 | Already in api_server/requirements.txt |
| `importlib` | stdlib | No installation needed |
| SU2 | System dependency | Already expected in Docker container |

**No new pip packages required** for v1.8.0 GoldStandard expansion and system integration. All additions are pure Python modules using existing infrastructure.

---

## What NOT to Add

| Avoid | Reason | Instead |
|-------|--------|---------|
| New ORM (SQLAlchemy, Alembic) | Pipeline state already in SQLite via pipeline_db.py | Reuse pipeline_db |
| New task queue | PipelineExecutor handles async step execution | Not needed |
| External validation service | GoldStandard validators are pure Python | Inline validators |
| Benchmark database | Literature data (Ghia, etc.) is embedded as Python constants | Keep as-is |
| Celery / Dramatiq / RQ | Task queue, not workflow engine; PipelineExecutor handles this | Not needed |
| Prefect / Dagster | Already rejected in v1.7.0 planning — PipelineExecutor IS the orchestrator | Not needed |

---

## Integration Architecture

```
knowledge_compiler/phase1/gold_standards/
    cold_start.py              # YAML loader (EXISTING)
    registry.py                # NEW — GoldStandardRegistry
    lid_driven_cavity.py       # EXISTING (add register() hook)
    backward_facing_step.py     # EXISTING (add register() hook)
    inviscid_bump.py           # EXISTING (add register() hook)
    inviscid_wedge.py          # EXISTING (add register() hook)
    laminar_flat_plate.py     # EXISTING (add register() hook)
    supersonic_wedge.py        # NEW — SU2-02
    cylinder_compressible.py   # NEW — SU2-04
    turbulent_flat_plate.py    # NEW — SU2-09
    von_karman_vortex.py       # NEW — SU2-10
    onera_m6.py               # NEW — SU2-19
    dam_break_vof.py          # NEW — OF-04
    ... (24 total new)

api_server/
    main.py                    # Register gold_standards router
    models.py                  # Add GoldStandardCaseResponse, GoldStandardListResponse
    routers/
        gold_standards.py       # NEW — REST endpoints
    services/
        gold_standard_service.py # NEW — GoldStandardRegistry bridge
        step_wrappers.py        # EXTEND — add gold_standard_wrapper
        comparison_service.py   # EXTEND — add GoldStandard validation
```

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Registry pattern | MEDIUM | Follows existing Python plugin patterns; no external verification |
| API router design | HIGH | Directly follows existing patterns from cases.py, knowledge.py |
| GoldStandard case pattern | HIGH | 5 existing implementations to copy from |
| StepType.GOLDSTANDARD | MEDIUM | Logical extension; existing dispatch table pattern is solid |
| No new libraries | HIGH | Confirmed by analyzing existing implementations |
| Bridge to ComparisonService | MEDIUM | Extension of existing comparison patterns |

---

## Sources

- Existing GoldStandard implementations: `knowledge_compiler/phase1/gold_standards/{lid_driven_cavity,backward_facing_step,inviscid_bump,inviscid_wedge,laminar_flat_plate}.py`
- ColdStartWhitelist: `data/cold_start_whitelist.yaml`
- Existing API patterns: `api_server/routers/{cases,knowledge,pipelines}.py`
- Existing step wrappers: `api_server/services/step_wrappers.py`
- Existing pipeline executor: `api_server/services/pipeline_executor.py`
- Existing comparison service: `api_server/services/comparison_service.py`
