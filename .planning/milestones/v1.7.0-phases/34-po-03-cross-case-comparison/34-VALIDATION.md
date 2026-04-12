# Phase 34 Validation Plan

**Phase:** 34-po-03-cross-case-comparison
**Generated from:** RESEARCH.md Validation Architecture section
**Validator:** gsd-tools frontmatter check

---

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing project framework) |
| Config file | `pytest.ini` at project root |
| Quick run command | `pytest tests/test_comparison*.py -x -q` |
| Full suite command | `pytest tests/ -q --tb=short` |

---

## Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| PIPE-11 | Provenance mismatch warning shown when comparing cases with different openfoam_version | unit | `pytest tests/test_comparison_service.py::test_provenance_mismatch -x` | tests/test_comparison_service.py |
| PIPE-11 | Convergence overlay data structure built correctly (merged iteration-keyed dict) | unit | `pytest tests/test_comparison_service.py::test_convergence_merge -x` | tests/test_comparison_service.py |
| PIPE-11 | Delta field RPC computes CaseB.scalar - CaseA.scalar and saves VTU | unit/integration | `pytest tests/test_comparison_service.py::test_delta_field -x` | tests/test_comparison_service.py |
| PIPE-11 | ComparisonResult JSON matches expected schema | unit | `pytest tests/test_comparison_service.py::test_comparison_result_json -x` | tests/test_comparison_service.py |
| PIPE-12 | Case multi-select enables Compare button only when >= 2 cases selected | unit | `pytest tests/test_comparison_page.py::test_compare_button_enabled -x` | tests/test_comparison_page.py |
| PIPE-12 | Metrics table CSV export produces valid CSV with all rows | unit | `pytest tests/test_metrics_table.py::test_csv_export -x` | tests/test_metrics_table.py |
| PIPE-12 | Sortable metrics table sorts correctly by final_residual | unit | `pytest tests/test_metrics_table.py::test_sort -x` | tests/test_metrics_table.py |

---

## Wave 0 Test File Gaps

| File to Create | Purpose | Blocks |
|----------------|---------|--------|
| `tests/test_comparison_service.py` | ComparisonService unit tests: provenance mismatch, convergence merge, delta field, JSON schema | Plan 01 Task 3 |
| `tests/test_comparison_page.py` | React component unit tests for ComparisonPage: compare button enable logic | Plan 02 Task 3 |
| `tests/test_metrics_table.py` | MetricsTable CSV export and sort tests | Plan 02 Task 2 |
| `tests/conftest.py` | Shared fixtures: sample_sweep_case, sample_provenance_case, sample_comparison_result | All plans |

**Gap resolution:** Each gap has a corresponding Wave 0 task in the respective plan that creates the test scaffold before implementation tasks reference it.

---

## Open Risks and Mitigations

| Risk | Disposition | Mitigation |
|------|-------------|------------|
| Convergence history may not exist in case directories | Accepted | parse_convergence_log returns []; UI shows empty state |
| ParaView ProgrammableFilter delta pipeline untested | Accepted | Initial prototype with error-state fallback; confirmed via openfoam_docker.py investigation |
| Provenance fields may all be null | Accepted | Fields nullable; UI handles empty provenance with "—" display |
