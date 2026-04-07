# Knowledge Compiler: Diff Engine
**Version**: v1.0
**Purpose**: Detect and classify changes between versions of knowledge assets
**Layer**: Cross-layer (Raw ↔ Parsed ↔ Canonical ↔ Executable)

---

## 1. Change Granularity Classification

### 1.1 NEW
- New artifact created (file, unit, executable)
- Triggers: First-time capture of new source file
- Affected assets: Add to `new_assets` list

### 1.2 DELETE
- Artifact removed from newer version
- Triggers: Source file no longer exists, unit removed from spec
- Affected assets: Add to `deleted_assets` list

### 1.3 TEXT_EDIT
- Raw text content changed (whitespace, formatting)
- Detected by: SHA256 hash mismatch on raw_text
- Impact: Low — re-parse only, no semantic change
- Affected assets: Re-parse to update Parsed layer

### 1.4 SEMANTIC_EDIT
- Parsed content changed (data points, formula values)
- Detected by: Parsed layer field value diff
- Impact: Medium — update Canonical layer
- Affected assets: Canonical units affected by parsed change

### 1.5 EVIDENCE_EDIT
- Validation data changed (error percentages, vortex positions)
- Detected by: `data_points.yaml` values differ
- Impact: High — benchmarks invalidated, re-validation required
- Affected assets: All bench_validators referencing this evidence
- Required action: Re-run bench_validators, update error statistics

### 1.6 CHART_RULE_EDIT
- Rendering rules changed (marker styles, colormaps)
- Detected by: `chart_rules.yaml` diff
- Impact: High — chart templates must regenerate
- Affected assets: `chart_template.py` executable
- Required action: Re-run chart_template.py, verify output visually

---

## 2. Semantic Change Detection Rules

### 2.1 Version Change Detection
```
If spec_version changes (e.g. v1.0 → v1.1):
  → CHART_RULE_EDIT if chart rules section changed
  → EVIDENCE_EDIT if validation data section changed
  → SEMANTIC_EDIT otherwise
```

### 2.2 Formula Definition Change
```
If FORM-xxx.definition text differs:
  → SEMANTIC_EDIT
  → Re-compile formula_validator.py
  → Invalidate all test cases (must re-run)
```

### 2.3 Data Point Change
```
If CASE-xxx.data_points[].value differs by > 0.01%:
  → EVIDENCE_EDIT
  → Re-run bench_validator for this case
  → Update error statistics
```

### 2.4 Chapter Structure Change
```
If new chapter added:
  → NEW
If chapter removed:
  → DELETE
If chapter content edited:
  → SEMANTIC_EDIT
```

---

## 3. Affected Executable Asset Tracking

### 3.1 Dependency Graph
```
Source File (Raw)
  └── Parsed Unit
        └── Canonical Unit
              └── Executable Asset
                    └── Test Case
```

### 3.2 Impact Propagation Rules
| Change Type | Propagates To |
|-------------|--------------|
| TEXT_EDIT | Re-parse only, no downstream impact |
| SEMANTIC_EDIT | Canonical units, re-validate Executable |
| EVIDENCE_EDIT | Canonical + Executable, re-run bench validators |
| CHART_RULE_EDIT | Executable chart_template, visual re-verification |

### 3.3 Cascading Invalidation
When EVIDENCE_EDIT occurs:
1. Find all `bench_validator` executables referencing changed case_id
2. Set `status: INVALIDATED` on those executables
3. Re-run test cases
4. Update `pass_count` / `total_count`
5. If any fail: create `FAILED_BENCHMARK` issue

---

## 4. Diff Output Format

```json
{
  "diff_id": "DIFF-{timestamp}",
  "from_version": "v1.0",
  "to_version": "v1.1",
  "changes": [
    {
      "change_type": "EVIDENCE_EDIT",
      "unit_id": "CASE-001",
      "field": "centerline_velocity[3].error_pct",
      "old_value": "3.22",
      "new_value": "3.43",
      "impacted_executables": ["EXEC-BENCH-GHIA-001"]
    }
  ],
  "new_assets": [],
  "deleted_assets": [],
  "invalidated_executables": ["EXEC-BENCH-GHIA-001"],
  "requires_review": true
}
```

---

## 5. Review Triggers

### 5.1 Automatic Review Required
- Any `EVIDENCE_EDIT` → automatic review
- Any `CHART_RULE_EDIT` → automatic review
- `SEMANTIC_EDIT` with impact on >3 units → automatic review

### 5.2 Review Checkpoints
1. **Automated diff** → classify changes
2. **Impact analysis** → identify affected executables
3. **Re-run tests** → validate new state
4. **Human review** → if any FAIL or automatic review triggered
5. **Publish** → if all pass, propagate to next layer
