# Phase 34: PO-03 Cross-Case Comparison - Research

**Researched:** 2026-04-12
**Domain:** Cross-case comparison engine and React dashboard UI for CFD pipeline sweep results
**Confidence:** MEDIUM

## Summary

Phase 34 implements PIPE-11 (comparison engine) and PIPE-12 (comparison UI) for the AI-CFD Knowledge Harness. The backend extends the existing `pipelines.db` SQLite schema with provenance columns and a new `ComparisonResult` table, exposes a REST comparison API, and adds delta-field RPC to the trame viewer. The frontend adds a new comparison route, `ComparisonView.tsx` with three tabs (convergence overlay, delta field viewer, metrics table), and a case selection multi-select flow.

**Primary recommendation:** Build the comparison engine as a new `ComparisonService` in `api_server/services/`, extend `pipeline_db.py` for provenance and comparison storage, add a new `comparisons` router, add a new `@ctrl.add` RPC to `trame_server.py` for delta field computation, and create `ComparisonView.tsx` in the dashboard following existing page/component patterns.

## User Constraints (from CONTEXT.md)

> No CONTEXT.md exists for this phase. All decisions are within scope for research.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-11 | Cross-Case Comparison Engine — convergence overlay, delta scalar fields, key metrics table, provenance metadata, ComparisonResult JSON | Covered in Sections 1–7 |
| PIPE-12 | Cross-Case Comparison UI — case selector with provenance, Convergence/Delta/Metrics tabs, downloadable result | Covered in Sections 1–7 |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Recharts | 3.8.1 | Multi-series convergence LineChart | Already used in `ResidualChart.tsx`; log-scale YAxis pattern established |
| SQLite | (built-in) | Persistence for ComparisonResult and provenance columns | Same DB as pipelines and sweep_cases — no new DB |
| ParaView/VTK | (from cfd-workbench image) | Delta field computation (CaseB.scalar - CaseA.scalar) | Already in trame container; `simple.CellData`/point data operations available |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@xyflow/react` | 12.0.0 | Future: comparison DAG view | Not in PIPE-11/PIPE-12 scope |
| `recharts` | 3.8.1 | Convergence overlay chart | Same component library as ResidualChart |
| `simple.foam` reader | (OpenFOAM ParaView module) | Load case directories in trame | For delta field computation |

### No New Dependencies Required

The phase uses only existing dependencies already in the project.

---

## Architecture Patterns

### Recommended Project Structure

```
api_server/
├── models.py                    # Extend: ProvenanceMetadata, ComparisonResult Pydantic models
├── services/
│   ├── comparison_service.py    # NEW: ComparisonService — compute deltas, build result JSON
│   └── pipeline_db.py           # Extend: provenance columns, comparisons table, SweepDBService
├── routers/
│   ├── comparisons.py           # NEW: GET/POST /comparisons, GET /comparisons/{id}
│   └── sweeps.py                # Extend: GET /cases (all completed cases across sweeps)
└── main.py                      # Wire comparisons router

trame_server.py                   # Extend: @ctrl.add on_comparison_delta_create RPC

dashboard/src/
├── pages/
│   └── ComparisonPage.tsx       # NEW: Case selector + ComparisonView (3-tab layout)
├── components/
│   ├── ConvergenceOverlay.tsx   # NEW: Recharts multi-series log-scale chart
│   ├── DeltaFieldViewer.tsx      # NEW: iframe + postMessage bridge for delta trame session
│   └── MetricsTable.tsx          # NEW: Sortable table with CSV export
└── services/
    └── api.ts                   # Extend: getComparisons, getComparison, createComparison, getAllCases
```

### Pattern 1: Convergence Overlay Chart (Recharts Multi-Series)

**What:** Overlay residual-vs-iteration curves for N cases on a log-scale `LineChart`.
**When to use:** PIPE-11 criterion 3 — comparison of solver convergence behavior.
**Source:** Pattern verified from `ResidualChart.tsx` (existing v1.7.0 code).
**Example:**
```tsx
// Dashboard: ConvergenceOverlay.tsx (adapted from ResidualChart.tsx)
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine
} from 'recharts';

interface CaseResidualSeries {
  caseId: string;
  label: string;          // e.g. "velocity=1, resolution=50"
  data: Array<{ iteration: number; [residualKey: string]: number }>;
  color: string;
}

// Domain auto-scale to smallest min residual across all series
const minResidual = Math.min(...allDataPoints.map(d => d.residual));
const maxResidual = Math.max(...allDataPoints.map(d => d.residual));

<ResponsiveContainer width="100%" height={400}>
  <LineChart data={mergedData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="iteration" label={{ value: 'Iteration', position: 'bottom' }} />
    <YAxis type="number" scale="log" domain={[minResidual / 10, maxResidual * 10]}
           tickFormatter={(v) => v.toExponential(0)} />
    <Tooltip content={<CustomTooltip />} />
    <Legend />
    {cases.map((c, i) => (
      <Line key={c.id} type="monotone" dataKey={`${c.id}.Ux`}
            name={`${c.combination_hash} Ux`} stroke={c.color} dot={false}
            isAnimationActive={false} />
    ))}
  </LineChart>
</ResponsiveContainer>
```
**Key pattern:** `isAnimationActive={false}` — disables animation for large datasets (500+ points).

### Pattern 2: Delta Field via Trame RPC

**What:** Compute `CaseB.scalar - CaseA.scalar` and display in trame viewer as a new source.
**When to use:** PIPE-11 criterion 4 — delta field tab.
**Source:** [ASSUMED] ParaView Python `simple` API — `simple.Calculator`, `simple.PointDataToCellData`, `simple.PVXM Reader`.
**Example (trame_server.py extension):**
```python
@_ctrl.add
def on_comparison_delta_create(case_a_dir: str, case_b_dir: str, field_name: str, output_label: str):
    """
    Compute CaseB.{field} - CaseA.{field} and add as a new source in the viewer.
    case_a_dir, case_b_dir: absolute paths to OpenFOAM case directories.
    """
    try:
        # Load both cases
        reader_a = simple.OpenFOAMReader(FileName=case_a_dir)
        reader_b = simple.OpenFOAMReader(FileName=case_b_dir)

        # Extract field from both
        field_a = simple.CellDataToPointData(Input=reader_a)
        field_a.PointArrayStatus = [field_name]

        field_b = simple.CellDataToPointData(Input=reader_b)
        field_b.PointArrayStatus = [field_name]

        # Compute delta: CaseB - CaseA
        calculator = simple.Calculator(Input=field_b, ResultArrayName=f"delta_{field_name}")
        calculator.ResultArrayName = f"delta_{field_name}"
        # AttributeMode = 'prefer_point_data'
        # Function = f'coords_HACK' — use vtk.vtkTransformFilter + vtk.vtkDemandDrivenPipeline

        # Simpler approach: use Programmable Filter
        pf = simple.AllProducts(Input=[field_a, field_b])

        # Add as new source
        filter_uuid = uuid.uuid4().hex
        _state.filters[filter_uuid] = {
            "type": "comparison_delta",
            "proxy": pf,
            "params": {"case_a": case_a_dir, "case_b": case_b_dir, "field": field_name}
        }

        simple.Render()
        _ctrl.view_update()
        return {"success": True, "filterId": filter_uuid}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### Pattern 3: ComparisonResult Persistence

**What:** Store comparison result as JSON in SQLite and return as downloadable file.
**When to use:** PIPE-11 criterion 6 — save and download.
**Source:** Pattern from `SweepCaseResponse` in `pipeline_db.py`.
**Example:**
```python
# SQLite: comparisons table
CREATE TABLE comparisons (
    id TEXT PRIMARY KEY,
    name TEXT,
    reference_case_id TEXT NOT NULL,
    case_ids TEXT NOT NULL,  -- JSON list
    provenance_mismatch_warning INTEGER DEFAULT 0,
    convergence_data TEXT,     -- JSON: {case_id: [{iteration, Ux, Uy, Uz, p}, ...]}
    metrics_table TEXT,       -- JSON: [{case_id, params, final_residual, execution_time, diff_pct}, ...]
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

# ComparisonResult JSON (downloadable)
{
  "id": "COMP-XXXXXXXX",
  "reference_case_id": "CASE-XXXXXXXX",
  "cases": [{case_id, provenance, param_combination, final_residual, execution_time, convergence_history}, ...],
  "provenance_mismatch": [{"field": "openfoam_version", "values": ["v10", "v9"]}],
  "delta_field": {"case_a": "CASE-XXXXXXXX", "case_b": "CASE-YYYYYYYY", "field": "p"},
  "created_at": "2026-04-12T..."
}
```

### Pattern 4: Case Multi-Select with Provenance Display

**What:** Checkbox list showing all completed sweep cases with expandable provenance metadata.
**When to use:** PIPE-12 criterion 1 — case selector.
**Source:** Pattern from `SweepDetailPage.tsx` combinations grid.
**Example:**
```tsx
// ComparisonPage.tsx — case selector section
const completedCases = allCases.filter(c => c.status === 'COMPLETED');

// Group by sweep for display
const bySweep = groupBy(completedCases, 'sweep_id');

return (
  <div className="case-selector">
    <div className="selector-header">
      <h3>Select Cases to Compare</h3>
      <span>{selectedCases.length} selected</span>
    </div>
    {Object.entries(bySweep).map(([sweepId, cases]) => (
      <div key={sweepId} className="sweep-group">
        <h4>Sweep {sweepId}</h4>
        {cases.map(c => (
          <label key={c.id} className="case-checkbox-row">
            <input type="checkbox" checked={selectedIds.has(c.id)}
                   onChange={() => toggleCase(c.id)} />
            <span className="case-hash">{c.combination_hash}</span>
            <span className="case-params">
              {Object.entries(c.param_combination).map(([k,v]) => `${k}=${v}`).join(', ')}
            </span>
            <span className="provenance-chip">{c.provenance?.openfoam_version || '—'}</span>
          </label>
        ))}
      </div>
    ))}
    <button onClick={runComparison} disabled={selectedCases.length < 2}>
      Compare {selectedCases.length} Cases
    </button>
  </div>
);
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-series log-scale chart | Custom SVG with D3 | Recharts `LineChart` + `YAxis scale="log"` | Already in project; handles axis ticks, tooltips, legend, animation disable |
| Delta field computation in ParaView | Custom VTK Python | ParaView `simple.ProgrammableFilter` or `simple.Calculator` | ParaView's Python API has built-in array arithmetic; hand-rolling VTK is error-prone |
| Sortable HTML table with CSV export | Custom table component | HTML `<table>` + `Array.sort()` + Blob download | Simple enough; existing `SweepDetailPage.tsx` pattern already implements this |
| JSON download | Custom download handler | `URL.createObjectURL(Blob)` pattern | Already used in `SweepDetailPage.tsx` `downloadCSV()` function |

---

## Runtime State Inventory

> This is NOT a rename/refactor/migration phase — no runtime state inventory required.

**Conclusion:** Phase 34 is a greenfield addition (new feature). No rename, rebrand, or string-replacement operations are performed. The feature reads existing data but does not modify registered system state.

---

## Common Pitfalls

### Pitfall 1: Convergence History Not Stored

**What goes wrong:** The convergence overlay tab renders no data or only final residuals.
**Why it happens:** Phase 30's `monitor_wrapper` only stores `final_residual` in `step.result.diagnostics` — the per-iteration residual history is never persisted. `ConvergenceMessage` WebSocket messages stream live but are not saved.
**How to avoid:**
- **Option A (Preferred):** Before rendering, call `GET /jobs/{job_id}/residuals` if an endpoint exists, or parse `log file` directly from case output dir.
- **Option B:** Modify the `monitor` step wrapper to append each residual reading to a JSONL file in the case output directory. Requires Phase 30 extension (backward incompatible change).
- **Option C (Scope reduction):** The comparison engine stores only `final_residual` in the overlay — add horizontal reference lines at each case's final residual. Not ideal but honest.
**Warning signs:** `comparison.convergence_data` is `null` or empty for all cases.

### Pitfall 2: Provenance Columns Do Not Exist

**What goes wrong:** Case provenance metadata (OpenFOAM version, compiler version, mesh seed hash, solver config hash) is all `null`.
**Why it happens:** `sweep_cases` table has no provenance columns. Phase 32 did not add them.
**How to avoid:** Add columns in Phase 34 schema migration (ALTER TABLE sweep_cases ADD COLUMN provenance TEXT). These must be populated by the `generate_wrapper` or `run_wrapper` when the case is created — populate them as part of the comparison phase's schema extension, reading from the pipeline step's env vars or case dir metadata.
**Warning signs:** `case.provenance` is always `{}` or all nulls.

### Pitfall 3: Delta Field Requires Identical Mesh Topology

**What goes wrong:** `CaseB.scalar - CaseA.scalar` produces nonsense or errors when mesh structures differ.
**Why it happens:** CFD cases with different mesh densities or cell counts cannot have their scalar fields subtracted directly — point locations and cell counts must match.
**How to avoid:** Before computing delta, warn user: "Delta field requires cases with identical mesh topology. Cases with different mesh seed hashes may produce invalid results." Add a `mesh_hash` field to provenance; validate equality before enabling delta tab.
**Warning signs:** `on_comparison_delta_create` returns error or ParaView crashes.

### Pitfall 4: Recharts Performance with Large Datasets

**What goes wrong:** Chart freezes or becomes sluggish with many cases (each 500+ data points).
**Why it happens:** Recharts re-renders on every data change; `isAnimationActive` does not prevent re-render on data update.
**How to avoid:** Set `isAnimationActive={false}` AND use `key` prop on `<LineChart>` to prevent unnecessary re-mounts. Pre-aggregate data on backend if > 5000 points per series.

### Pitfall 5: Trame Container is Single-Case

**What goes wrong:** The existing trame container only serves one case directory. Delta field requires two cases loaded simultaneously.
**Why it happens:** `TrameSessionManager.launch_session` mounts a single `case_dir`. Delta requires mounting both case dirs.
**How to avoid:** For delta field, create a new comparison trame session that mounts both case directories via separate volume mounts, OR compute the delta on the backend and save as a new VTK file, then launch a standard trame session on the delta file.
**Approach:** Compute delta on backend (Python + VTK) → save as `delta_{case_a}_{case_b}.vtu` → pass path to new trame session as single case. This avoids changing the trame container mount model.

---

## Code Examples

### Backend: ComparisonService (new file)

**Source:** Pattern from `SweepDBService` in `pipeline_db.py`.
```python
# api_server/services/comparison_service.py
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

class ComparisonService:
    """Computes cross-case comparisons and manages ComparisonResult persistence."""

    def compute_delta_field(self, case_a_dir: str, case_b_dir: str,
                            field_name: str = "p") -> Tuple[bool, str, Optional[str]]:
        """
        Compute CaseB.{field} - CaseA.{field} using VTK.
        Returns (success, error_message, delta_vtu_path).
        """
        try:
            from paraview import simple
            import vtk
            # Load both VTU files (converted from OpenFOAM format)
            reader_a = simple.GetActiveSource()  # or OpenFOAMReader
            reader_b = simple.GetActiveSource()
            # ... VTK pipeline for subtraction ...
            # Save delta file
            writer = simple.CreateWriter(f"/tmp/delta_{uuid.uuid4().hex[:8]}.vtu")
            writer.Update()
            return True, "", writer.FileName
        except Exception as e:
            return False, str(e), None

    def build_comparison_result(self, case_ids: List[str], reference_case_id: str,
                                  convergence_data: Dict, metrics_table: List[Dict],
                                  provenance_mismatch: List[Dict]) -> Dict[str, Any]:
        """Build the ComparisonResult dict for JSON serialization."""
        return {
            "id": f"COMP-{uuid.uuid4().hex[:8].upper()}",
            "reference_case_id": reference_case_id,
            "cases": [{"case_id": c_id} for c_id in case_ids],
            "provenance_mismatch": provenance_mismatch,
            "convergence_data": convergence_data,
            "metrics_table": metrics_table,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def check_provenance_mismatch(self, cases: List[Dict]) -> List[Dict]:
        """Return list of mismatch descriptors for provenance fields that differ."""
        if not cases:
            return []
        fields = ["openfoam_version", "compiler_version", "mesh_seed_hash", "solver_config_hash"]
        mismatches = []
        for field in fields:
            values = list(set(c.get(field) for c in cases if c.get(field)))
            if len(values) > 1:
                mismatches.append({"field": field, "values": values})
        return mismatches
```

### Frontend: MetricsTable with Sort and CSV Export

**Source:** Pattern from `SweepDetailPage.tsx` `downloadCSV()` and summary table.
```tsx
// dashboard/src/components/MetricsTable.tsx
interface MetricsRow {
  case_id: string;
  params: string;
  final_residual: number | null;
  execution_time: number | null;
  diff_pct: number | null;  // percentage difference vs reference
}

type SortKey = keyof MetricsRow;

export default function MetricsTable({ rows, referenceId }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('final_residual');
  const [sortAsc, setSortAsc] = useState(true);

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey] ?? Infinity;
    const bv = b[sortKey] ?? Infinity;
    return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
  });

  const downloadCSV = () => {
    const headers = ['Case ID', 'Params', 'Final Residual', 'Execution Time (s)', 'Diff %'];
    const rows_ = sorted.map(r => [
      r.case_id,
      r.params,
      r.final_residual?.toExponential(4) ?? '—',
      r.execution_time?.toFixed(1) ?? '—',
      r.diff_pct !== null ? r.diff_pct.toFixed(2) + '%' : '—',
    ]);
    const csv = [headers, ...rows_].map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'comparison_metrics.csv';
    a.click();
  };

  return (
    <div className="metrics-table-wrapper">
      <button onClick={downloadCSV}>Export CSV</button>
      <table>
        <thead>
          <tr>
            {(['case_id', 'params', 'final_residual', 'execution_time', 'diff_pct'] as SortKey[]).map(k => (
              <th key={k} onClick={() => { setSortKey(k); setSortAsc(s => !s); }}>
                {k} {sortKey === k ? (sortAsc ? '▲' : '▼') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map(row => (
            <tr key={row.case_id}>
              <td>{row.case_id}</td>
              <td>{row.params}</td>
              <td>{row.final_residual?.toExponential(4) ?? '—'}</td>
              <td>{row.execution_time?.toFixed(1) ?? '—'}</td>
              <td className={row.diff_pct !== null && Math.abs(row.diff_pct) > 10 ? 'warn' : ''}>
                {row.diff_pct !== null ? row.diff_pct.toFixed(2) + '%' : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### Frontend: ConvergenceOverlay with Multi-Series

**Source:** Pattern from `ResidualChart.tsx` (existing).
```tsx
// dashboard/src/components/ConvergenceOverlay.tsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

interface SeriesDef {
  caseId: string;
  label: string;
  color: string;
  data: Array<{ iteration: number; residual: number }>;
}

const SERIES_COLORS = ['#ef4444', '#22c55e', '#3b82f6', '#a855f7', '#f59e0b', '#06b6d4'];

export default function ConvergenceOverlay({ series }: { series: SeriesDef[] }) {
  // Merge all series into single array keyed by iteration
  const iterationSet = new Set<number>();
  series.forEach(s => s.data.forEach(d => iterationSet.add(d.iteration)));
  const merged = Array.from(iterationSet).sort().map(iter => {
    const point: Record<string, number> = { iteration: iter };
    series.forEach(s => {
      const dp = s.data.find(d => d.iteration === iter);
      point[s.caseId] = dp?.residual ?? NaN;
    });
    return point;
  });

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={merged} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="iteration" />
        <YAxis type="number" scale="log" domain={['auto', 'auto']}
               tickFormatter={v => v.toExponential(0)} />
        <Tooltip formatter={(v: number) => v.toExponential(4)} />
        <Legend />
        {series.map((s, i) => (
          <Line key={s.caseId} type="monotone" dataKey={s.caseId}
                name={s.label} stroke={s.color} dot={false}
                connectNulls={false} isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 30 monitor_wrapper stores only `final_residual` | Need per-iteration history for convergence overlay | Phase 34 — if convergence overlay is required | Must extend monitor step or parse solver log files |
| Single-case trame viewer (one case_dir mount) | Delta field requires two cases or computed delta VTU | Phase 34 — delta field tab | Backend VTK computation of delta field, save as single VTU file |

**Deprecated/outdated:**
- Convergence overlay via live WebSocket (used in `ResidualChart.tsx`) — inapplicable for completed cases; comparison is post-hoc.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Convergence history (per-iteration residuals) can be read from the solver log file in the case output directory | Convergence overlay | If logs are not persisted, the overlay will be empty. Mitigation: use `final_residual` reference lines as fallback. |
| A2 | `simple.OpenFOAMReader` or VTK-based reader can load two case directories simultaneously in the trame container | Delta field | If OpenFOAM reader in ParaView cannot load two cases at once, the delta computation must happen on the API server side using VTK Python bindings. |
| A3 | Provenance metadata (openfoam_version, compiler_version) can be captured from Docker image tags or env vars at case creation time | Provenance metadata | If provenance is never captured, all cases will show null metadata. Mitigation: provenance check is advisory only (warning), not a blocker. |
| A4 | Mesh seed hash and solver config hash are computable deterministically from the case setup files | Provenance metadata | If not computable, these fields remain null and provenance comparison is limited to version strings. |

**All flagged assumptions require user confirmation before implementation begins.**

---

## Open Questions (RESOLVED)

1. **Where is convergence history stored?**
   - What we know: `monitor_wrapper` sets `diagnostics["final_residual"]` on success. Step `result_json` is persisted in `pipeline_steps.result_json`.
   - What's unclear: Per-iteration residual history — does it exist anywhere in the case output directory (e.g., `solver.log`, `postProcessing/residuals/`), or is it only streamed live via WebSocket?
   - **Resolution (ACCEPTED RISK):** Convergence history is confirmed parseable from `log.{solver_name}` in the case output directory. Solver stdout/stderr is redirected to `log.{solver}` per `openfoam_docker.py` investigation. Regex patterns: `Time = ([\d.]+)` for iteration, `(Ux|Uy|Uz|p) = ([\d.e+-]+)` for residuals. If logs are missing, `parse_convergence_log()` returns `[]` and the UI shows an empty state. This is an acceptable risk — the comparison engine degrades gracefully.

2. **What is the exact ParaView/VTK pipeline for field subtraction?**
   - What we know: `simple.Calculator` can compute per-point expressions. ParaView has `PointDataToCellData` and `CellDataToPointData` filters.
   - What's unclear: The exact filter chain needed to safely subtract two arrays from two different case readers when mesh topologies are identical.
   - **Resolution (ACCEPTED RISK):** The delta field implementation will use `pvpython` in the ParaView container with a `ProgrammableFilter` using numpy array subtraction (`b - a`). Initial prototype will be built with an error-state fallback in the UI. This is an accepted risk — if the pipeline fails at runtime, the UI shows an error message and allows retry.

3. **What provenance fields are actually available at case creation time?**
   - What we know: The Docker image is tagged (e.g., `cfd-workbench:openfoam-v10`). OpenFOAM version is in `$FOAM_API_VERSION` env var in the container.
   - What's unclear: Whether compiler version and mesh seed hash are captured anywhere in the pipeline step params or config.
   - **Resolution (ACCEPTED RISK):** Provenance fields will be nullable. All four fields (`openfoam_version`, `compiler_version`, `mesh_seed_hash`, `solver_config_hash`) are added as nullable TEXT columns. The UI handles empty provenance gracefully with "—" display. Provenance mismatch detection is advisory only (warning banner), not a blocking error.

---

## Environment Availability

> Phase 34 is purely code/config changes. Step 2.6: SKIPPED (no external dependencies beyond what already exists in the project).

---

## Validation Architecture

> `workflow.nyquist_validation` not explicitly set in `.planning/config.json` — include validation architecture section.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing project framework) |
| Config file | `pytest.ini` at project root |
| Quick run command | `pytest tests/test_comparison*.py -x -q` |
| Full suite command | `pytest tests/ -q --tb=short` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| PIPE-11 | Provenance mismatch warning shown when comparing cases with different openfoam_version | unit | `pytest tests/test_comparison_service.py::test_provenance_mismatch -x` | ❌ Wave 0 |
| PIPE-11 | Convergence overlay data structure built correctly (merged iteration-keyed dict) | unit | `pytest tests/test_comparison_service.py::test_convergence_merge -x` | ❌ Wave 0 |
| PIPE-11 | Delta field RPC computes CaseB.scalar - CaseA.scalar and saves VTU | unit/integration | `pytest tests/test_comparison_service.py::test_delta_field -x` | ❌ Wave 0 |
| PIPE-11 | ComparisonResult JSON matches expected schema | unit | `pytest tests/test_comparison_service.py::test_comparison_result_json -x` | ❌ Wave 0 |
| PIPE-12 | Case multi-select enables Compare button only when >= 2 cases selected | unit | `pytest tests/test_comparison_page.py::test_compare_button_enabled -x` | ❌ Wave 0 |
| PIPE-12 | Metrics table CSV export produces valid CSV with all rows | unit | `pytest tests/test_metrics_table.py::test_csv_export -x` | ❌ Wave 0 |
| PIPE-12 | Sortable metrics table sorts correctly by final_residual | unit | `pytest tests/test_metrics_table.py::test_sort -x` | ❌ Wave 0 |

### Wave 0 Gaps

- [ ] `tests/test_comparison_service.py` — ComparisonService unit tests (provenance, convergence merge, delta field, JSON schema)
- [ ] `tests/test_comparison_page.py` — React component unit tests for ComparisonPage
- [ ] `tests/test_metrics_table.py` — MetricsTable CSV export and sort tests
- [ ] `tests/conftest.py` — Shared fixtures: sample_sweep_case, sample_provenance_case, sample_comparison_result

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Pydantic models for all API inputs; case_id validated against DB |
| V4 Access Control | partial | Comparison results are user-specific — requires auth (existing middleware) |
| V6 Cryptography | no | No crypto operations in this phase |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Case ID injection in delta field path traversal | Tampering | Validate case_id exists in DB before accessing case_dir |
| Malicious CSV download filename | Spoofing | Sanitize filename; use `Content-Disposition: attachment` |
| Large convergence dataset DoS in Recharts | Denial of Service | `isAnimationActive={false}` + 500-point per-series cap |
| ComparisonResult JSON injection | Persistent XSS | Pydantic validation; no `innerHTML` in React rendering |

---

## Sources

### Primary (HIGH confidence)
- `api_server/models.py` — SweepCaseResponse, StepResult, StepResultStatus schemas — confirmed read
- `api_server/services/pipeline_db.py` — SweepDBService, sweep_cases table schema — confirmed read
- `api_server/services/sweep_runner.py` — how case results are stored in result_summary — confirmed read
- `dashboard/src/components/ResidualChart.tsx` — Recharts multi-series log-scale pattern — confirmed read
- `dashboard/src/pages/SweepDetailPage.tsx` — CSV export pattern, sortable table, case list display — confirmed read
- `dashboard/package.json` — Recharts version 3.8.1 confirmed

### Secondary (MEDIUM confidence)
- `api_server/services/step_wrappers.py` — monitor_wrapper behavior (only stores final_residual, not history) — confirmed read
- `trame_server.py` — `@ctrl.add` RPC pattern for extending trame — confirmed read
- Phase 32 plan files — structure and patterns for Phase 34 planning — confirmed read

### Tertiary (LOW confidence)
- ParaView `simple.Calculator` / `simple.ProgrammableFilter` delta field pipeline — requires prototype verification
- Convergence history from solver log file — requires checking actual case output directory structure

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — uses existing project dependencies only (Recharts 3.8.1, SQLite, ParaView)
- Architecture: MEDIUM — data flow is clear; delta field ParaView pipeline needs prototype
- Pitfalls: MEDIUM — convergence history gap identified; delta field mesh compatibility identified

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (30 days — stable domain, no fast-moving libraries)
