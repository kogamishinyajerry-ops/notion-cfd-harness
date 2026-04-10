# Phase 9: Report Automation & Postprocess Intelligence - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliverable: A `ReportGenerator` that consumes `SolverResult` (from Phase 7) and produces structured, human-readable CFD reports. The report must include an executive summary, detailed validation data, and literature comparison. Human corrections via inline HTML interaction feed into `ReportTeachMode` for continuous improvement.

Scope: Report generation, comparison engine (case-vs-literature via Gold Standards), teach mode feedback loop.

Out of scope: New solver functionality, mesh generation, case setup.

</domain>

<decisions>
## Implementation Decisions

### Report Content & Structure
- **D-01:** Two-tier structure: Executive Summary first (conclusion, key metrics, pass/fail), then detailed breakdown
- **D-02:** Include data visualizations: residual convergence plot (from solver log) + key field contour summaries (p, U fields)

### Comparison Scope
- **D-03:** Primary mode: Case vs Literature — compare results against published reference data
- **D-04:** Reference data source: Gold Standards library (e.g., `knowledge_compiler/phase1/gold_standards/lid_driven_cavity.py`, `backward_facing_step.py`)
- **D-05:** Gold Standards provide canonical reference values (e.g., Re, U_max, etc.) for comparison

### Automation Level
- **D-06:** Fully automatic — report generates as part of postprocess pipeline after solver completes
- **D-07:** Report generation errors are logged but do NOT block pipeline continuation

### Output Formats
- **D-08:** Output three formats: HTML (primary, self-contained with embedded CSS/charts), PDF (archival), JSON (machine consumption / programmatic integration)

### ReportTeachMode
- **D-09:** Inline HTML correction: user clicks on a reported value → flags it as incorrect → correction recorded to `correction_recorder` (Phase 2c component)
- **D-10:** Future reports auto-apply corrections from the teach store — no manual re-entry needed

### Claude's Discretion
- Exact chart rendering library (matplotlib vs plotly) — researcher/planner to determine based on existing dependencies
- Specific HTML template structure — researcher/planner to design
- PDF generation approach (weasyprint, pdfkit, etc.) — researcher/planner to determine

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Gold Standards (Reference Data)
- `knowledge_compiler/phase1/gold_standards/lid_driven_cavity.py` — Cavity reference data
- `knowledge_compiler/phase1/gold_standards/backward_facing_step.py` — BFS reference data
- `knowledge_compiler/phase1/gold_standards/laminar_flat_plate.py` — Flat plate reference data

### Existing Postprocess Infrastructure
- `knowledge_compiler/phase2/execution_layer/postprocess_runner.py` — StandardPostprocessResult dataclass, FieldData, ResidualSummary, DerivedQuantity
- `knowledge_compiler/phase3/postprocess_runner/runner.py` — PostprocessRunner, PostprocessArtifact, PostprocessFormat (HTML_REPORT already defined)
- `knowledge_compiler/phase3/schema.py` — SolverResult, PostprocessFormat, PostprocessArtifact
- `knowledge_compiler/phase2/execution_layer/result_validator.py` — ValidationResult, convergence checking

### Existing Report/Output Artifacts
- `knowledge_compiler/phase2/execution_layer/postprocess_runner.py:_create_report_artifact` — Existing plain-text report generation (placeholder for Phase 9)

### Correction/Teach Infrastructure
- `knowledge_compiler/phase2c/correction_recorder.py` — CorrectionRecorder for teach mode
- `knowledge_compiler/phase2c/benchmark_replay.py` — May serve as reference for replay/correction flow

### Phase 7 Real Solver (Context for Report Input)
- `knowledge_compiler/phase2/execution_layer/openfoam_docker.py` — SolverResult structure and execution context

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PostprocessArtifact` with `HTML_REPORT` format already defined in schema — extend, don't re-create
- `StandardPostprocessResult` (FieldData, ResidualSummary, DerivedQuantity) — primary input types for report content
- `ResultValidator` — provides convergence and anomaly data to include in reports
- Gold Standards in `phase1/gold_standards/` — contain canonical reference values for literature comparison
- `correction_recorder.py` — existing correction loop infrastructure to reuse for ReportTeachMode

### Established Patterns
- Pipeline pattern: `SolverRunner → PostprocessRunner → ReportGenerator` (Phase 9 new terminal)
- Artifact pattern: `PostprocessArtifact(format=HTML_REPORT, file_path=...)` already used in Phase 3
- Two-layer output: `StandardPostprocessResult` (internal) → various `PostprocessArtifact` formats (external)

### Integration Points
- `ReportGenerator` plugs into `PostprocessPipeline` after `PostprocessRunner` completes
- `ReportGenerator` reads from Gold Standards library for literature comparison data
- `ReportGenerator` reads from `correction_recorder` for teach mode corrections
- Output goes to `knowledge_compiler/reports/` directory
- Notion integration (Phase 4) could be used to push report metadata to Cases DB

</code_context>

<specifics>
## Specific Ideas

- Literature comparison table in report: columns = [Metric, Simulated Value, Literature Value, Error %]
- Executive Summary box at top: color-coded PASS (green) / WARN (yellow) / FAIL (red) based on precision gate thresholds
- Charts generated via matplotlib embedded as base64 PNG in HTML (no external dependencies at runtime)

</specifics>

<deferred>
## Deferred Ideas

None — all ideas discussed are within Phase 9 scope.

</deferred>

---

*Phase: 09-report-automation*
*Context gathered: 2026-04-10*
