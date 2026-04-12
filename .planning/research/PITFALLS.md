# Domain Pitfalls: GoldStandard Implementation + System Integration

**Project:** AI-CFD Knowledge Harness v1.8.0
**Researched:** 2026-04-12
**Domain:** GoldStandard CFD case implementation + knowledge_compiler / api_server integration
**Confidence:** MEDIUM-HIGH

> This document covers pitfalls specific to (1) implementing 24 new GoldStandard CFD cases and (2) bridging `knowledge_compiler/` GoldStandardLoader with `api_server/` pipeline/services. It assumes existing v1.7.0 infrastructure is operational.

---

## 1. GoldStandard Implementation Pitfalls

Mistakes that cause GoldStandard cases to produce wrong reference data, fail validation, or generate misleading literature comparisons.

### 1.1: Literature Data Extracted Incorrectly

**What goes wrong:** Reference values in `get_expected_*` functions do not match the primary source paper.

**Why it happens:**
- Rounding errors when transcribing tabulated data from PDFs or websites
- Unit conversion errors (Pa vs kPa, dimensionless vs scaled)
- Wrong row/column mapping in table lookup (y/L position vs value)
- Interpolation between tabulated Reynolds numbers without documenting the method
- Re values in the paper differ from the tutorial case parameters (e.g., Ghia 1982 uses Re based on lid velocity and cavity size, but the tutorial may specify a different definition)

**Consequences:**
- GoldStandard returns incorrect reference values
- LiteratureComparison reports PASS when simulation is actually off
- Or worse: reports FAIL for a correct simulation
- Analogy engine propagates wrong reference data through the knowledge chain

**Prevention:**
- Always cite the specific table/equation number from the primary source (not a secondary source)
- For interpolated Re values, use linear interpolation and document the method explicitly
- Verify unit consistency between the paper's definition and the tutorial case's parameterization
- For each `get_expected_*` function: add a `__docstring__` that references the exact paper, table, and column
- Add assertions that sanity-check reference values against known physical bounds (e.g., shock angle must be between Mach angle and 90 deg)

**Detection:**
- Cross-reference the tabulated values against the primary paper
- Add a unit test that verifies reference values against known analytic solutions (e.g., for inviscid wedge, the shock angle computed from theta-beta-M relation must match the tabulated reference value to within 0.01 deg)

---

### 1.2: Mesh Strategy Mismatch in GoldStandard

**What goes wrong:** A GoldStandard is implemented for a case that the whitelist marks as "mesh_strategy: A" (ready mesh), but the implementation uses a programmatic mesh generator (mesh_strategy: B), or vice versa.

**Why it happens:**
- The 6 existing GoldStandards (`cold_start.py`, `backward_facing_step.py`, `inviscid_bump.py`, `inviscid_wedge.py`, `laminar_flat_plate.py`, `lid_driven_cavity.py`) are not yet validated against the mesh_strategy declared in `cold_start_whitelist.yaml`
- For example, `inviscid_wedge.py` declares it uses CGNS mesh (ready mesh, mesh_strategy A), but the GoldStandard `ReportSpec` does not encode the mesh file path or validate its presence
- The `GoldStandardLoader` in `phase9_report/gold_standard_loader.py` uses `_case_type_loaders` that import from `knowledge_compiler.phase1.gold_standards.*`, but those modules do not expose a `get_mesh_strategy()` function

**Consequences:**
- The analogy engine (E1-E6) may select a GoldStandard for a case that requires a different mesh setup than what the target case provides
- Pipeline tries to run a GoldStandard case without the expected mesh file, producing a silent failure
- `GoldStandardLoader.get_reference_data()` returns data but the corresponding simulation cannot be reproduced

**Prevention:**
- Each GoldStandard module must expose a `get_mesh_info()` function returning: `{mesh_strategy: "A"|"B", mesh_file_path: str|None, mesh_hash: str|None}`
- The `GoldStandardLoader` must check mesh_strategy compatibility before returning reference data
- For mesh_strategy A (ready mesh): validate that the mesh file exists and matches the declared hash before returning reference values
- Encode `mesh_strategy` explicitly in the `ReportSpec` produced by each GoldStandard's `create_*_spec()` function

**Detection:**
- GoldStandard test suite runs each case with both mesh strategies and verifies that the appropriate error is raised for mismatched strategies
- Integration test: run `GoldStandardLoader.get_reference_data()` and verify the returned dict includes `mesh_strategy`

---

### 1.3: Solver Config Not Captured in GoldStandard

**What goes wrong:** The GoldStandard's `ReportSpec` does not encode the solver configuration that was used to generate the reference data. Different solver settings (turbulence model, discretization schemes, convergence criteria) produce different results.

**Why it happens:**
- `lid_driven_cavity.py`'s `CavityGateValidator` checks `required_plots` and `required_metrics` but does not validate solver configuration
- The whitelist entries declare `solver_command` (e.g., "blockMesh && icoFoam") but the GoldStandard modules do not store or expose this
- Reference data from Ghia 1982 was computed with a specific solver and mesh density; using a different solver or mesh may legitimately produce different numbers

**Consequences:**
- A case runs with k-epsilon turbulence but the GoldStandard reference data was produced with DNS -- the comparison is meaningless
- Pipeline generates a case with different solver settings and reports misleading PASS/WARN/FAIL
- The analogy engine transfers a GoldStandard to a case with incompatible physics

**Prevention:**
- Each GoldStandard module must expose a `get_solver_config()` function returning: `{solver_name: str, turbulence_model: str|None, discretization_schemes: Dict[str,str], convergence_criteria: Dict[str,float]}`
- The `LiteratureComparison` result must include a `solver_config_compatible: bool` field
- Before comparing, `GoldStandardLoader.compare_with_reference()` must verify that the simulated case's solver config is compatible with the GoldStandard's solver config

**Detection:**
- `GoldStandardLoader.get_reference_data()` returns a dict that includes `solver_config` -- if a case's solver config is absent or incompatible, the comparison returns `status: INCOMPATIBLE` instead of PASS/WARN/FAIL

---

### 1.4: Validation Threshold Too Tight or Too Loose

**What goes wrong:** The `LiteratureComparison` uses hardcoded `threshold_pct` (default 5.0%) that is inappropriate for the metric and the physics.

**Why it happens:**
- Different metrics have fundamentally different error characteristics: centerline velocity profiles can be compared point-by-point (error < 1% is achievable for well-resolved cases), but pressure jump ratios may have 10-15% uncertainty due to scheme differences
- Using the same threshold for all metrics produces false FAILs or false PASSes
- The threshold is not documented in the `LiteratureComparison` result

**Consequences:**
- High-quality simulations fail validation for metrics where 5% is excellent
- Low-quality simulations pass validation for metrics where 20% error is still "reasonable"
- Users cannot understand why a given threshold was chosen

**Prevention:**
- Each `get_expected_*` function must return a dict that includes `metric_thresholds: Dict[str, float]` -- per-metric thresholds instead of a global default
- For new GoldStandards, research the typical error range for each metric in the literature (e.g., Ghia 1982 notes that centerline velocities are accurate to within 1-2% for well-resolved simulations)
- Document the threshold rationale in the metric specification

**Detection:**
- Cross-validation: run the GoldStandard case with the reference solver and mesh; the resulting error should be well within the declared threshold
- If the GoldStandard itself fails its own validation test, the threshold is wrong

---

### 1.5: Analytic Reference Values Computed Incorrectly

**What goes wrong:** For compressible flow GoldStandards, analytic relations (e.g., theta-beta-M for oblique shocks, Blasius solution for flat plate) are implemented with numerical errors.

**Why it happens:**
- The `get_expected_shock_angle()` in `inviscid_wedge.py` uses a bisection loop. If the convergence tolerance (`abs(theta_calc - theta) < 1e-10`) is too tight for the numeric type, the loop may exit with an inaccurate result
- The Mach angle computation (`asin(1.0 / M1)`) returns NaN if M1 < 1 (supersonic check missing)
- No test verifies that `get_expected_shock_angle()` produces the expected result to within a documented tolerance

**Consequences:**
- The GoldStandard returns a wrong shock angle reference value
- All SU2-02 cases validated against this reference will be systematically wrong
- The error may be small (e.g., 0.1 deg) but still exceeds the validation threshold

**Prevention:**
- For each analytic function: add a test that verifies the output against a known analytic solution or a high-precision reference (e.g., `get_expected_shock_angle(M=2.0, theta=15.0)` should return 45.34 deg -- verify to 0.01 deg)
- Add explicit preconditions: raise `ValueError` if `mach_number <= 1.0` (not supersonic)
- Document the expected precision of each analytic function in its docstring
- Use `math.fsum` for accumulated sums to minimize floating-point error

**Detection:**
- Unit test: for `get_expected_shock_angle`, test at known solutions (e.g., M=2.0, theta=10/15/20 deg) against published theta-beta-M tables
- For `get_expected_ghia_data`, verify that the returned profile arrays have the correct length (41 positions) and are symmetric where expected

---

### 1.6: ReportSpec Schema Version Drift

**What goes wrong:** New GoldStandards are implemented with updated `ReportSpec` schema fields that are incompatible with the schema version used by the existing pipeline.

**Why it happens:**
- The 6 existing GoldStandards use `create_*_spec()` functions that return `ReportSpec` objects
- If a new GoldStandard adds fields to `ReportSpec` (e.g., new fields in `PlotSpec` or `MetricSpec`), the existing `CavityGateValidator.validate_report_spec()` may break or silently skip validation
- The `GoldStandardLoader` in `phase9_report/gold_standard_loader.py` only handles 3 case types (`lid_driven_cavity`, `backward_facing_step`, `laminar_flat_plate`) -- adding 24 more without a scalable registration pattern causes code sprawl

**Consequences:**
- New GoldStandards cannot be loaded via `GoldStandardLoader` because they are not registered
- Pipeline fails when trying to validate a new case against an unregistered GoldStandard
- Gate validation silently passes because it only checks a subset of fields

**Prevention:**
- Implement a **registration decorator** for GoldStandards: `@register_gold_standard("su2_cylinder")` that registers the module's `get_expected_*` and `create_*_spec` functions in a central registry
- `GoldStandardLoader` should iterate over registered GoldStandards instead of hardcoding case type mappings
- Before implementing new GoldStandards, verify the current `ReportSpec` schema version and ensure new fields have backward-compatible defaults
- Add a schema version field to `ReportSpec` and validate it in `CavityGateValidator`

**Detection:**
- `GoldStandardLoader.get_reference_data()` is called with a case type and returns `None` -- this should be a loud error, not a silent empty dict
- `GoldStandardLoader` integration test: call `get_reference_data()` for every registered GoldStandard and verify non-empty return

---

## 2. System Integration Pitfalls

Mistakes that arise when bridging `knowledge_compiler/` GoldStandardLoader with `api_server/` PipelineExecutor/ComparisonService.

### 2.1: Circular Import Between knowledge_compiler and api_server

**What goes wrong:** `api_server/services/knowledge_service.py` imports `from knowledge_compiler.runtime import KnowledgeRegistry`, and `knowledge_compiler` modules may transitively import from `api_server`, creating a circular dependency.

**Why it happens:**
- `KnowledgeService._get_registry()` does a lazy import inside a method: `from knowledge_compiler.runtime import KnowledgeRegistry`
- This is a deferred import pattern that avoids startup circular imports
- However, if any `knowledge_compiler` module (e.g., in `phase3/orchestrator/`) imports from `api_server.models`, and `api_server.models` imports something that eventually imports `knowledge_compiler`, the deferred import in `knowledge_service.py` will also fail at runtime

**Consequences:**
- FastAPI server fails to start with `ImportError: cannot import name 'X' from 'knowledge_compiler'`
- The error is intermittent and depends on import order, making it hard to reproduce
- Tests that import both modules fail

**Prevention:**
- Enforce a strict **layering rule**: `api_server/` may import from `knowledge_compiler/`, but `knowledge_compiler/` may NOT import from `api_server/`
- Use an **interface pattern**: `api_server/services/knowledge_service.py` defines an abstract interface, and `knowledge_compiler/` provides an implementation via a plugin registration (not a direct import)
- All cross-boundary imports must go through an abstract base class or Protocol, not a concrete module
- Add a `conftest.py` test that imports both modules in isolation and verifies no circular import

**Detection:**
- CI test: `python -c "from api_server.services.knowledge_service import KnowledgeService; from knowledge_compiler.phase1.gold_standards.lid_driven_cavity import get_expected_ghia_data"` -- must succeed
- Add a top-level `__init__.py` assertion that verifies no `api_server` imports exist in `knowledge_compiler/` tree

---

### 2.2: GoldStandardLoader Not Thread-Safe Under PipelineExecutor

**What goes wrong:** `GoldStandardLoader` uses instance state (`_case_type_loaders` dict) and lazy-loaded imports, which are not safe under concurrent access from multiple pipeline threads.

**Why it happens:**
- `GoldStandardLoader.__init__()` sets `self._case_type_loaders: Dict[str, Callable[..., Optional[Dict[str, Any]]]]`
- `self._registry` in `KnowledgeService` is a shared mutable reference across requests
- `PipelineExecutor` runs in a dedicated `threading.Thread` (not async), and multiple steps may call `GoldStandardLoader` concurrently
- Python's GIL protects individual bytecode operations but not complex state transitions

**Consequences:**
- Race condition: one thread is iterating over `_case_type_loaders` while another modifies it (adds a new GoldStandard registration)
- `KnowledgeService._get_registry()` may initialize `_registry` twice, with the second overwriting the first
- In production with concurrent pipeline runs, sporadic `KeyError` or `AttributeError` occurs

**Prevention:**
- `GoldStandardLoader` should be **stateless**: all registration happens at module load time via a module-level registry dict, not in `__init__`
- If state is needed, use a `threading.Lock` around all state mutations
- `KnowledgeService` should be instantiated **once per FastAPI request** (not singleton) to avoid shared mutable state across requests
- For concurrent pipeline access, create a new `GoldStandardLoader` instance per pipeline run

**Detection:**
- Load test: create 10 concurrent pipeline runs that all call `GoldStandardLoader.get_reference_data()` simultaneously -- should produce identical results with no errors
- Stress test with pytest-xdist: run the full pipeline test suite with 4 workers, verify no intermittent import or state errors

---

### 2.3: API Contract Mismatch Between GoldStandardLoader and ComparisonService

**What goes wrong:** `ComparisonService` expects certain fields from `GoldStandardLoader.get_reference_data()`, but new GoldStandards return different field names or structures.

**Why it happens:**
- `GoldStandardLoader.get_reference_data()` returns `Dict[str, Any]` -- the caller must know the exact field names
- `ComparisonService.build_metrics_table()` in `comparison_service.py` reads `case.result_summary.get("final_residual")` -- this field name must match what the pipeline's run step produces
- `LiteratureComparison` (in `gold_standard_loader.py`) has fields: `metric_name, simulated_value, reference_value, error_pct, unit, reference_source, reynolds_number, status`
- But `ComparisonService` produces `MetricsRow` with fields: `case_id, params, final_residual, execution_time, diff_pct`
- These two models are **incompatible**: `LiteratureComparison` is about literature comparison, `MetricsRow` is about case-vs-case comparison

**Consequences:**
- `ComparisonService.create_comparison()` calls `GoldStandardLoader.compare_with_reference()` but the result cannot be stored in the `ComparisonResponse` model because `LiteratureComparison` fields are not in `ComparisonResponse`
- The cross-case comparison (PO-03) and literature comparison (D-03/D-04) are two different operations with incompatible data models
- The `delta_field` computation in `ComparisonService` produces `.vtu` files but the GoldStandard reference does not have a field-level delta -- the comparison is scalar-only

**Prevention:**
- Define a unified `ReferenceComparison` model that encompasses both literature comparison and case-vs-case comparison: `{metric_name, simulated_value, reference_value, error_pct, unit, reference_source, reference_type: "literature"|"case", reynolds_number, status}`
- `ComparisonResponse` should contain a `literature_comparisons: List[ReferenceComparison]` field alongside `metrics_table`
- `GoldStandardLoader` should be injectable into `ComparisonService` (not hardcoded import), so the comparison logic can be unit-tested independently

**Detection:**
- Integration test: create a GoldStandard case, run it through the pipeline, then call `ComparisonService.create_comparison()` with a `ComparisonCreate` that includes literature reference -- verify the result includes literature comparison data

---

### 2.4: Provenance Metadata Gap for GoldStandard Cases

**What goes wrong:** GoldStandard cases in the pipeline do not carry provenance metadata, causing `ComparisonService.check_provenance_mismatch()` to flag GoldStandard cases as mismatched against each other or against user cases.

**Why it happens:**
- `check_provenance_mismatch()` compares `openfoam_version`, `compiler_version`, `mesh_seed_hash`, `solver_config_hash` across cases
- GoldStandard cases may have been run with different mesh files or solver versions than user cases
- The `GoldStandardLoader` does not return provenance metadata, so there is no way to know what provenance the reference data was generated under
- `ComparisonResponse` has `provenance_mismatch: List[ProvenanceMismatchItem]` -- if all compared cases have no provenance data, the list is empty (false negative)

**Consequences:**
- Comparing a user case against a GoldStandard case always produces a provenance mismatch warning, even when the settings are equivalent
- The provenance mismatch is informational but not actionable: the user does not know what specific setting differs
- Analogy engine transfers a GoldStandard to a case with different turbulence model, and this is not flagged

**Prevention:**
- `GoldStandardLoader.get_reference_data()` must return a `provenance` dict alongside the reference values: `{openfoam_version: str|None, compiler_version: str|None, mesh_seed_hash: str|None, solver_config_hash: str|None, mesh_strategy: str}`
- `LiteratureComparison` result must include the provenance of the reference data so consumers can see whether comparison is apples-to-apples
- `ComparisonService.check_provenance_mismatch()` should accept an optional `reference_provenance` parameter and compare cases against the GoldStandard's provenance, not just against each other

**Detection:**
- Test: create a comparison with 3 user cases and 1 GoldStandard case -- `provenance_mismatch` should include items for each field that differs between the user cases and the GoldStandard reference

---

### 2.5: Path Assumptions in ComparisonService Break in Docker

**What goes wrong:** `ComparisonService.get_convergence_data()` and `compute_delta()` hardcode filesystem paths (`data/sweeps/{sweep_id}/{combination_hash}/`) that may not resolve correctly when the pipeline runs inside Docker containers.

**Why it happens:**
- `get_convergence_data()` constructs `case_dir = Path(f"data/sweeps/{case.sweep_id}/{case.combination_hash}")` with a relative path
- When running in Docker, the working directory may be different, or the `data/` directory may be volume-mounted at a different location
- `compute_delta_field()` writes `delta_script_{script_id}.py` to `output_dir` and then executes it via `docker exec`, but the script path inside the container may not match the path on the host

**Consequences:**
- Convergence data parsing returns empty list because the log file is not found
- Delta field computation fails with "Case directory not found"
- The comparison completes but with no data, producing an empty `metrics_table`

**Prevention:**
- Use **absolute paths** derived from environment variables: `case_dir = Path(os.environ.get("DATA_DIR", "/app/data")) / f"sweeps/{case.sweep_id}/{case.combination_hash}"`
- `compute_delta_field()` should volume-mount the output directory into the ParaView container and use container-absolute paths in the pvpython script
- Add a path resolution step: if the case directory does not exist at the expected path, search parent directories or raise a descriptive error

**Detection:**
- Integration test: run a pipeline inside Docker and verify that `ComparisonService.get_convergence_data()` returns non-empty convergence history
- Verify that `delta_vtu_url` in `ComparisonResponse` resolves to a downloadable file

---

## 3. Moderate Pitfalls

### 3.1: GoldStandard Registration Is Ad-Hoc

**What goes wrong:** Each new GoldStandard is added by editing `GoldStandardLoader._case_type_loaders` dict directly, creating a growing list of if/elif imports that is hard to maintain.

**Prevention:** Use a module-level `GOLD_STANDARD_REGISTRY` dict populated via import-time side effects. Each GoldStandard module registers itself on import.

### 3.2: Error swallowed in GoldStandardLoader._load_* functions

**What goes wrong:** The `_load_lid_cavity`, `_load_backward_step`, and `_load_flat_plate` functions in `GoldStandardLoader` catch all exceptions and return empty dicts. This silently hides import errors, ValueError from wrong Re, and AttributeError from API changes.

**Prevention:** Return a result that includes an `error` field. Callers should check `if not result or result.get("error")` and propagate or log appropriately. Never catch all exceptions silently.

### 3.3: LiteratureComparison status thresholds are undocumented

**What goes wrong:** `compare_with_reference()` uses hardcoded threshold logic (PASS <= threshold, WARN <= 2*threshold, FAIL > 2*threshold) without documenting the rationale.

**Prevention:** Document the threshold logic in the docstring and make the multiplier configurable via a `warn_multiplier` parameter with default 2.0.

---

## 4. Phase-Specific Warnings

| Pitfall | Severity | Phase | Mitigation |
|---------|----------|-------|-----------|
| 1.1 Literature data extraction | Critical | GoldStandard implementation | Unit tests against primary sources |
| 1.2 Mesh strategy mismatch | Critical | GoldStandard implementation | `get_mesh_info()` function + schema encoding |
| 1.3 Solver config not captured | High | GoldStandard implementation | `get_solver_config()` function + compatibility check |
| 1.4 Validation threshold inappropriate | High | GoldStandard implementation | Per-metric thresholds in `get_expected_*` return |
| 1.5 Analytic values computed incorrectly | High | GoldStandard implementation | Analytic function unit tests against published tables |
| 1.6 ReportSpec schema drift | High | GoldStandard implementation | Registration decorator + schema versioning |
| 2.1 Circular import | Critical | System integration | Layering rule enforcement + import isolation test |
| 2.2 GoldStandardLoader thread safety | High | System integration | Stateless design + per-run instance |
| 2.3 API contract mismatch | High | System integration | Unified `ReferenceComparison` model |
| 2.4 Provenance metadata gap | Medium | System integration | Provenance in `get_reference_data()` return |
| 2.5 Path assumptions in Docker | Medium | System integration | Absolute paths from env vars + volume mount validation |
| 3.1 Ad-hoc registration | Low | GoldStandard implementation | Module-level registry |
| 3.2 Swallowed errors in _load_* | Medium | GoldStandard implementation | Explicit error field in return dict |
| 3.3 Undocumented threshold rationale | Low | GoldStandard implementation | Docstring + configurable multiplier |

---

## 5. Priority Checklist

Before implementing any new GoldStandard, these must be resolved:

- [ ] `get_mesh_info()` function defined and implemented in all 6 existing GoldStandards
- [ ] `get_solver_config()` function defined and implemented in all 6 existing GoldStandards
- [ ] `LiteratureComparison` extended to include `solver_config_compatible` and `reference_type`
- [ ] `ComparisonResponse` updated to include `literature_comparisons` field
- [ ] `GoldStandardLoader` registration decorator implemented (not hardcoded dict)
- [ ] Import isolation test passes: no circular import between `api_server/` and `knowledge_compiler/`
- [ ] Path resolution uses environment-derived absolute paths, not relative paths
- [ ] Per-metric thresholds defined for each existing GoldStandard metric

---

## 6. Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| GoldStandard implementation pitfalls | MEDIUM | Based on existing code patterns in `lid_driven_cavity.py` and `inviscid_wedge.py`; analytic function risks verified by code inspection |
| Literature data extraction | MEDIUM | Cross-reference risk is standard in scientific computing; specific error modes inferred from code structure |
| System integration pitfalls | MEDIUM-HIGH | Based on code inspection of `knowledge_service.py`, `comparison_service.py`, and `gold_standard_loader.py`; thread safety risk is architectural |
| Circular import risk | HIGH | Lazy import pattern in `knowledge_service.py` is a known risk; layering rule is a standard mitigation |
| Path assumption risk | MEDIUM | Docker volume mount patterns are documented in project; specific paths are verified from code |

---

## 7. Sources

| Source | URL | Confidence | What it verifies |
|--------|-----|------------|-----------------|
| Ghia 1982 paper | Journal of Computational Physics 48(3) | HIGH | Primary reference data for lid-driven cavity |
| Armaly 1983 paper | J. Fluid Mech. 127 | HIGH | Backward-facing step reattachment lengths |
| SU2 Tutorials official docs | https://su2code.github.io/tutorials/ | HIGH | Case parameters, mesh files, solver configs |
| OpenFOAM Tutorial Guide | https://www.openfoam.com/documentation/tutorial-guide/ | HIGH | OF case setup and solver commands |
| Python threading docs | https://docs.python.org/3/library/threading.html | HIGH | Thread safety and GIL limitations |
| FastAPI import patterns | https://fastapi.tiangolo.com/ | MEDIUM | Best practices for service layer isolation |

---

*Research conducted: 2026-04-12*
*Files read: PROJECT.md, cold_start.py, comparison_service.py, 34-REVIEW.md, gold_standard_loader.py, knowledge_service.py, pipeline_executor.py (partial), lid_driven_cavity.py, inviscid_wedge.py, cold_start_whitelist.yaml, existing PITFALLS.md*
