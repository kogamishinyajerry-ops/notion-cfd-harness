# Knowledge Compiler BASELINE v1.0
**Status**: Phase2 Initial Baseline
**Generated**: 2026-04-07
**Source**: Phase1 ReportSpec v1.1 + Phase1 Evidence

---

## 1. Baseline Overview

This document establishes the initial compilation baseline for Phase2 (Knowledge Compiler).
All downstream Phase2 tasks should inherit from this baseline.

### 1.1 Input Assets

| Asset ID | Name | Version | Status |
|----------|------|---------|--------|
| SPEC-001 | Phase1-ReportSpec | v1.1 | Active |
| CHART-001 | CFD图表标准化规则 | v1.0 | Active |
| EVID-001 | Procedure Evidence | v1.0 | Active |

### 1.2 Knowledge Units Produced

| Unit Type | Count | Unit IDs |
|-----------|-------|----------|
| chapters | 6 | CH-001 → CH-005, CH-003-1 |
| formulas | 10 | FORM-001 → FORM-010 |
| data_points | 2 | CASE-001, BENCH-04 |
| chart_rules | 3 | CHART-001, CHART-002, CHART-003 |
| evidence | 2 | EVID-CHAIN-001, EVID-CHAIN-002 |

---

## 2. Four-Layer Architecture

```
Layer         | Artifacts
--------------|--------------------------------------------------
Raw           | Phase1-ReportSpec-Candidate.md, chart_standards.md, procedure_evidence.md
Parsed        | knowledge_compiler/units/*.yaml
Canonical     | knowledge_compiler/schema/*_schema.json
Executable    | knowledge_compiler/executables/*.py
```

---

## 3. Executable Assets Baseline

### 3.1 formula_validator.py
- **Language**: Python
- **Functions**: `L1()`, `L2()`, `relative_error()`, `GCI()`
- **Tests**: 5 test cases
- **Status**: ✅ All pass (baseline verification)

### 3.2 chart_template.py
- **Language**: Python (matplotlib)
- **Functions**: `plot_velocity_profile()`, `plot_pressure_contour()`, `plot_gci_convergence()`
- **Tests**: 3 test cases
- **Status**: ✅ All pass (baseline verification)

### 3.3 bench_ghia1982.py
- **Language**: Python
- **Benchmark**: Ghia et al. 1982 Lid Cavity Re=1000
- **Acceptance**: max error < 5%
- **Status**: ✅ Pass (canonical data)

### 3.4 bench_cylinder_wake.py
- **Language**: Python
- **Benchmark**: Williamson 1996 Circular Cylinder Wake Re=100
- **Acceptance**: Strouhal error <= 8%, drag error <= 5%
- **Honesty Check**: BENCH-04 seeds only St and mean Cd
- **Status**: ✅ Pass (canonical data)

---

## 4. Key Baseline Decisions

### 4.1 Zero Reference Handling
- **Decision**: Strategy A — switch to absolute error when |u_exp| < 0.01 * u_max
- **No** `max()` denominator trick
- **Source**: ReportSpec v1.1 §2.2

### 4.2 Data Honesty Constraint
- **Decision**: BENCH-04 seeds only Strouhal number, mean drag coefficient, and wake visualization
- **Action**: Must NOT fabricate richer wake traces without provenance
- **Source**: EVID-001 §B.6 Honesty Declaration

### 4.3 Canonical Unsteady Wake Target
- **Decision**: Re=100 cylinder wake must show a Karman vortex street with St≈0.164
- **Action**: Validate both St and mean drag against Williamson 1996
- **Source**: ReportSpec v1.1 §4 BENCH-04 note

### 4.4 Chapter Extraction (F-001 Fix)
- Boundary Conditions extracted as §1.3.1 (not merged into §1.3)
- Source: Opus R-SPEC-001 fix

---

## 5. Phase2继承指引

### 5.1 What Phase2 Can Assume (Trusted Baseline)
- All units above are verified against source
- Formula definitions are correct per ReportSpec v1.1
- Benchmark data is honest (no fabrication)
- Chart rendering rules are standardized

### 5.2 What Phase2 Must Not Assume
- Phase2 may NOT override baseline formula definitions without major version bump
- Phase2 may NOT add new benchmark data without source provenance
- Phase2 may NOT skip bench validation for "convenience"

### 5.3 Phase2 Extension Points
Phase2 can extend:
- New executable assets (e.g., mesh_quality_validator.py)
- New chart types beyond §1-§3
- New case types beyond Case1/Case2
- Automation of capture/parse/normalize pipeline

---

## 6. Baseline Integrity Verification

Run to verify baseline integrity:
```bash
cd /Users/Zhuanz/Desktop/notion-cfd-harness/knowledge_compiler/executables
python3 formula_validator.py        # Must show "✅ All tests passed"
python3 chart_template.py          # Must show "✅ All tests passed"
python3 bench_ghia1982.py           # Must show "✅ OVERALL PASS"
python3 bench_cylinder_wake.py      # Must show "✅ OVERALL PASS"
```

---

*This baseline is immutable once published. Any change requires version upgrade per publish_contract.md §3.*
