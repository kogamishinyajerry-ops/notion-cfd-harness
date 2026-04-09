# Knowledge Compiler: Review / Publish / Propagate Contract
**Version**: v1.0
**Layer**: Canonical → Executable
**Purpose**: Define conditions for advancing knowledge assets through the pipeline

---

## 1. Review Checklist

Before publishing any knowledge asset, all items must pass:

### 1.1 Completeness Check
- [ ] All required fields present in schema (Raw/Parsed/Canonical/Executable)
- [ ] No `null` values in required fields without documented reason
- [ ] Source line ranges populated for all source-mapped units
- [ ] Version tags assigned to all units

### 1.2 Data Honesty Check
- [ ] All `data_gaps` declared (no hidden missing data)
- [ ] No fabricated benchmark data points (e.g. richer cylinder-wake traces beyond BENCH-04 seed data)
- [ ] Zero-reference values correctly flagged

### 1.3 Schema Compliance Check
- [ ] Raw layer: all `required_fields` present
- [ ] Parsed layer: `structured_data.unit_type` matches schema enum
- [ ] Canonical layer: `spec_version` = "v1.1" hardcoded
- [ ] Executable layer: `test_cases` non-empty array

### 1.4 Executable Validation Check
- [ ] All `formula_validator.py` tests pass
- [ ] All `chart_template.py` rendering tests pass
- [ ] `bench_ghia1982.py` — OVERALL PASS
- [ ] `bench_cylinder_wake.py` — OVERALL PASS
- [ ] All bench validator errors within acceptance thresholds

### 1.5 Semantic Correctness Check
- [ ] Formula definitions match ReportSpec v1.1 §2.2
- [ ] Zero-reference handling follows §2.2 strategy (no `max()` denominator)
- [ ] Chapter structure matches ReportSpec v1.1 §1
- [ ] GCI formula follows chart_standards.md §3.2

---

## 2. Publish Trigger Conditions

ALL of the following must be true before publishing:

```
✅ All review checklist items pass
✅ bench_ghia1982.py: overall_pass == True
✅ bench_cylinder_wake.py: overall_pass == True
✅ Benchmark metrics remain within BENCH-04 tolerances
✅ No undeclared data gaps
✅ No conflict_flags in any canonical unit
✅ Human reviewer has signed off (for Phase1 → Phase2 transition)
```

---

## 3. Version Upgrade Rules

### 3.1 When to Increment Version
| Change Type | Version Action |
|-------------|---------------|
| New unit added | Patch version: v1.0 → v1.1 |
| Schema field added (backward compatible) | Patch version |
| Schema field removed or renamed (breaking) | Major version: v1.x → v2.0 |
| Formula definition changed | Major version: v1.x → v2.0 |
| Benchmark data changed (EVIDENCE_EDIT) | Major version: v1.x → v2.0 |

### 3.2 Version Tagging
- Format: `{artifact_id}-v{major}.{minor}`
- Examples: `SPEC-001-v1.1`, `CHART-001-v1.0`, `EVID-001-v1.0`
- Tags are immutable once assigned

---

## 4. Rollback Principles

### 4.1 Rollback Triggers
- Any published version found to have fabrication (data not in source)
- Any published version with undeclared data gaps
- Benchmark test found to be falsely passing

### 4.2 Rollback Procedure
1. Mark version as `DEPRECATED` in Artifacts DB
2. Revert to previous known-good version
3. Log rollback event with reason
4. Notify consumers of downstream assets

### 4.3 No Rollback When
- Minor rendering improvements (chart aesthetics)
- New optional fields added
- Documentation clarifications (not affecting executable behavior)

---

## 5. Propagation Rules

### 5.1 Phase1 → Phase2 Propagation
- Phase1 output (Canonical layer) becomes Phase2 input
- All 5 unit types must be present: chapters, formulas, data_points, chart_rules, evidence
- Any missing unit type → block propagation, report gap

### 5.2 Phase2 → Phase3 Propagation
- Knowledge Compiler output becomes Orchestrator input
- Executable assets (formula_validator, chart_template, benches) must all pass
- Diff engine must show no untracked changes

### 5.3 Propagation Blockers
```
BLOCK if:
  - Any required unit type missing
  - bench tests failing
  - undeclared data gaps found
  - human review not signed off
```
