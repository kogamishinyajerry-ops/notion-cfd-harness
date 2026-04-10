# Phase 9: Report Automation & Postprocess Intelligence - Research

**Researched:** 2026-04-10
**Domain:** CFD report generation, literature comparison, automated postprocessing
**Confidence:** HIGH (based on verified codebase patterns + established library knowledge)

## Summary

Phase 9 implements automatic report generation from `SolverResult`. The existing `PostprocessRunner` produces `StandardPostprocessResult` (fields, residuals, derived quantities), which becomes the primary input to `ReportGenerator`. The output is a three-format deliverable: HTML (primary, self-contained), PDF (archival), JSON (machine consumption). Literature comparison uses Gold Standards reference data via `get_expected_*` functions. Inline HTML corrections feed into `CorrectionRecorder` for teach mode.

**Primary recommendation:** Use matplotlib (already in use) for charts, embed as base64 PNG in self-contained HTML. Use Jinja2 for HTML templating (not hand-crafted string concatenation). Use weasyprint for PDF (pure Python, fewer macOS issues than pdfkit/wkhtmltopdf).

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Two-tier structure: Executive Summary first (conclusion, key metrics, pass/fail), then detailed breakdown
- **D-02:** Include data visualizations: residual convergence plot + key field contour summaries
- **D-03:** Primary comparison mode: Case vs Literature
- **D-04:** Reference data source: Gold Standards library
- **D-06:** Fully automatic -- report generates as part of postprocess pipeline after solver completes
- **D-07:** Report generation errors logged but do NOT block pipeline
- **D-08:** Output three formats: HTML (primary), PDF (archival), JSON (machine consumption)
- **D-09:** Inline HTML correction: user clicks value -> flags incorrect -> correction recorded to `correction_recorder`

### Claude's Discretion (Research To Determine)
- Chart rendering library (matplotlib vs plotly) -- researcher to determine based on existing dependencies
- PDF generation approach (weasyprint, pdfkit, etc.) -- researcher to determine
- HTML template structure -- researcher to design
- Inline correction mechanism detail -- researcher to determine

### Deferred Ideas (OUT OF SCOPE)
None.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REQ-09-01 | Consume SolverResult, output StandardPostprocessResult | Phase 2 `PostprocessRunner.run_from_solver_result()` already does this |
| REQ-09-02 | Generate HTML report with executive summary + detailed breakdown | Jinja2 template approach identified |
| REQ-09-03 | Embed residual convergence plot as base64 PNG in HTML | matplotlib + base64 encoding confirmed |
| REQ-09-04 | Literature comparison: case vs Gold Standards | Gold Standards `get_expected_*` functions identified |
| REQ-09-05 | Output JSON machine-consumable format | Schema already defined in `PostprocessResult` |
| REQ-09-06 | Output PDF archival format | weasyprint recommended |
| REQ-09-07 | Inline correction mechanism in HTML | CorrectionRecorder integration point identified |
| REQ-09-08 | Report errors logged, not blocking pipeline | D-07 constraint |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| matplotlib | 3.x (existing) | Chart generation | Already used in project (`chart_template.py`, `visualization.py`) with `Agg` backend |
| Jinja2 | 3.x | HTML templating | Python standard for template-based report generation |
| weasyprint | 55.x+ | PDF generation | Pure Python, no system deps (vs pdfkit's wkhtmltopdf requirement) |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| base64 | Encode PNG to embed in HTML | Charts embedded as base64 data URIs |
| json | Machine-readable output | JSON format artifact |
| pathlib | Path handling | Output directory management |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| matplotlib | plotly | Plotly is interactive-only (HTML/JS), harder to embed as static PNG in HTML reports |
| Jinja2 | hand-crafted HTML strings | Jinja2 is cleaner, separates presentation from logic, testable |
| weasyprint | pdfkit | pdfkit requires wkhtmltopdf (system dep, macOS issues); weasyprint is pure Python |
| weasyprint | reportlab | reportlab is lower-level (canvas API), weasyprint uses CSS which aligns with HTML template |

**Installation:**
```bash
pip install weasyprint jinja2
```
Note: matplotlib and numpy are already present (verified by codebase usage in `chart_template.py`).

---

## Architecture Patterns

### Recommended Project Structure
```
knowledge_compiler/
├── phase9_report/
│   ├── __init__.py
│   ├── report_generator.py      # ReportGenerator class
│   ├── report_configs.py         # ReportConfig dataclass
│   ├── gold_standard_loader.py   # Gold Standards integration
│   ├── templates/
│   │   └── report_template.html  # Jinja2 HTML template
│   └── static/
│       └── report.css           # Report styles
└── reports/                     # Generated reports output
```

### Pattern 1: ReportGenerator as Postprocess Pipeline Terminal

**What:** ReportGenerator is the final stage of `PostprocessPipeline`, consuming `StandardPostprocessResult` and producing `PostprocessArtifact` in multiple formats.

**When to use:** After `PostprocessRunner` completes successfully.

**Integration point:**
```python
# In postprocess pipeline (conceptual)
solver_result = solver_runner.run(case_input)
postprocess_result = postprocess_runner.run_from_solver_result(solver_result)
# Phase 9: Report generation (errors logged, not blocking)
try:
    report_artifacts = report_generator.generate(postprocess_result, solver_result)
    postprocess_result.artifacts.extend(report_artifacts)
except ReportGenerationError as e:
    logger.error(f"Report generation failed: {e}")  # D-07: logged, not blocking
```

**Source:** Verified from `phase3/postprocess_runner/runner.py` and `phase3/schema.py` (PostprocessFormat.HTML_REPORT already defined).

### Pattern 2: Two-Tier Report Structure

**What:** Executive Summary (conclusion, pass/fail, key metrics) followed by detailed breakdown.

**Structure:**
```
HTML Report
├── Executive Summary Box (color-coded: green/yellow/red)
│   ├── Status: CONVERGED / FAILED / WARNING
│   ├── Key Metrics Table
│   └── Literature Comparison Summary
├── Residual Convergence Chart (base64 PNG)
├── Field Contour Summaries (base64 PNG)
├── Detailed Breakdown
│   ├── Mesh Information
│   ├── Boundary Conditions
│   ├── Field Statistics
│   └── Anomaly Details
└── Footer (correction mechanism)
```

### Pattern 3: Gold Standards Query Pattern

**What:** ReportGenerator queries Gold Standards by case type and Reynolds number.

**Example:**
```python
# From lid_driven_cavity.py
from knowledge_compiler.phase1.gold_standards.lid_driven_cavity import get_expected_ghia_data

# Query reference data for Re=1000
ref_data = get_expected_ghia_data(1000)
# Returns: {"reynolds_number": 1000, "y_positions": [...], "u_centerline": [...], ...}

# Compare with simulated values
simulated_u = extract_centerline_velocity(postprocess_result, "x=0.5")
error_pct = compute_error(ref_data["u_centerline"], simulated_u)
```

**Source:** Verified from `knowledge_compiler/phase1/gold_standards/lid_driven_cavity.py:318-349`.

### Pattern 4: Inline Correction via Query Param

**What:** HTML report contains clickable values that set query params, processed by a correction endpoint.

**Mechanism:**
1. HTML generated with clickable spans: `<span class="correctable" data-field="max_u" data-value="0.342">0.342</span>`
2. Click triggers: `window.location.href = '/correct?record=<report_id>&field=max_u&value=0.342'`
3. Server endpoint receives, calls `CorrectionRecorder.record_from_generator()`
4. Future reports auto-apply corrections from teach store

**Source:** CorrectionRecorder structure verified from `knowledge_compiler/phase2c/correction_recorder.py`.

### Anti-Patterns to Avoid
- **Hand-crafted HTML strings:** Use Jinja2 templates instead -- easier to test, modify, and maintain
- **External image files in HTML:** Embed as base64 data URIs for self-contained HTML (D-08: "self-contained")
- **Blocking report errors:** Wrap in try/except, log and continue (D-07 constraint)
- **Single format output:** Must output all three formats (HTML, PDF, JSON)

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chart generation | Custom canvas drawing | matplotlib + base64 encoding | Already in project, proven, stable |
| HTML templating | String concatenation | Jinja2 | Separates concerns, testable, industry standard |
| PDF from HTML | wkhtmltopdf (pdfkit) | weasyprint | Pure Python, no system deps, CSS support |
| Literature reference lookup | Custom parsing | Gold Standards `get_expected_*()` functions | Already implemented, validated |
| Correction recording | New storage format | CorrectionRecorder | Already exists, Phase 2c approved |

---

## Common Pitfalls

### Pitfall 1: Chart Axes Not Readable in Small Size
**What goes wrong:** Contour/velocity plots have tiny labels when embedded at small display size in HTML.
**Why it happens:** Default matplotlib figsize (8x6) produces labels optimized for print, not inline HTML display.
**How to avoid:** Use `figsize=(10, 8)` minimum, increase fontsize to 14pt for labels, 18pt for titles. Test at actual HTML display size.
**Warning signs:** Labels appear as illegible dots in generated HTML preview.

### Pitfall 2: Gold Standards Version Mismatch
**What goes wrong:** Report compares against wrong reference data (e.g., Re=100 data when Re=400 was simulated).
**Why it happens:** `get_expected_ghia_data()` raises `ValueError` if Re not in tabulated data; but silently returns empty if wrong case type used.
**How to avoid:** Explicit case type detection before querying. Log warning if no reference data found.
**Warning signs:** Literature comparison shows 0% error (no reference data loaded).

### Pitfall 3: weasyprint CSS Limitations
**What goes wrong:** Complex CSS (flexbox, grid) renders differently in PDF vs HTML browser.
**Why it happens:** weasyprint has partial CSS support, some properties behave differently.
**How to avoid:** Use simple CSS (block layout, basic colors, standard fonts). Test PDF output explicitly.
**Warning signs:** PDF output has broken layout, missing sections, or overlapped text.

### Pitfall 4: Large Base64 Payloads
**What goes wrong:** Reports with multiple high-DPI charts produce 10MB+ HTML files, slow to load.
**Why it happens:** Charts saved at dpi=300 produce large PNGs; base64 encoding adds ~33% overhead.
**How to avoid:** Use dpi=150 for HTML embedding (sufficient for screen viewing), dpi=300 only for PDF if needed. Consider SVG for simple line charts.

---

## Code Examples

### Chart to Base64 PNG (verified pattern)
```python
# Source: Based on chart_template.py (knowledge_compiler/executables/chart_template.py)
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import base64
from io import BytesIO

def fig_to_base64_png(fig: plt.Figure) -> str:
    """Convert matplotlib Figure to base64-encoded PNG string for HTML embedding."""
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    img_bytes = buf.getvalue()
    return base64.b64encode(img_bytes).decode('utf-8')

# Usage in ReportGenerator
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(iterations, residual_values)
ax.set_xlabel('Iteration')
ax.set_ylabel('Residual')
ax.set_yscale('log')
chart_b64 = fig_to_base64_png(fig)
plt.close(fig)
# Embed in HTML: <img src="data:image/png;base64,{chart_b64}">
```

### Residual Convergence Plot (verified from PostprocessRunner)
```python
# Source: phase2/execution_layer/postprocess_runner.py:ResidualParser
# Parse residuals from solver log
residuals = {"initial": {}, "final": {}, "iterations": []}
for match in re.finditer(r'solving for (.+), Final residual = ([\d.e-]+), No Iterations (\d+)', log_content):
    var_name = match.group(1)
    residuals["final"][var_name] = float(match.group(2))
    residuals["iterations"].append({"variable": var_name, "final_residual": float(match.group(2))})
```

### Gold Standards Query (verified from lid_driven_cavity.py)
```python
# Source: knowledge_compiler/phase1/gold_standards/lid_driven_cavity.py
from knowledge_compiler.phase1.gold_standards.lid_driven_cavity import get_expected_ghia_data

def compare_with_literature(simulated_u, reynolds_number):
    try:
        ref_data = get_expected_ghia_data(reynolds_number)
    except ValueError as e:
        return {"error": str(e), "available_Re": [100, 400, 1000]}

    # Compute error at each position
    errors = [abs(ref - sim) / abs(ref) * 100 for ref, sim in zip(ref_data["u_centerline"], simulated_u)]
    max_error = max(errors)
    return {"max_error_pct": max_error, "reference_source": "Ghia 1982"}
```

### ReportGenerator Skeleton
```python
# Source: Derived from phase3/postprocess_runner/runner.py pattern
from knowledge_compiler.phase3.schema import PostprocessArtifact, PostprocessFormat

class ReportGenerator:
    def __init__(self, output_dir: str = "knowledge_compiler/reports"):
        self.output_dir = Path(output_dir)
        self.template_env = Jinja2.Environment(loader=FileSystemLoader("templates/"))

    def generate(
        self,
        postprocess_result: StandardPostprocessResult,
        solver_result: SolverResult,
    ) -> List[PostprocessArtifact]:
        """Generate all report formats. Errors logged per D-07."""
        artifacts = []
        try:
            # 1. Generate charts (matplotlib -> base64)
            charts = self._generate_charts(postprocess_result)

            # 2. Render HTML from template
            html_path = self._render_html(postprocess_result, solver_result, charts)

            # 3. Generate PDF from HTML
            pdf_path = self._render_pdf(html_path)

            # 4. Generate JSON machine-readable
            json_path = self._render_json(postprocess_result)

            artifacts.extend([
                PostprocessArtifact(format=PostprocessFormat.HTML_REPORT, file_path=html_path),
                PostprocessArtifact(format=PostprocessFormat.PDF, file_path=pdf_path),
                PostprocessArtifact(format=PostprocessFormat.JSON, file_path=json_path),
            ])
        except ReportGenerationError as e:
            logger.error(f"Report generation failed: {e}")  # D-07: logged, not blocking
        return artifacts
```

### Jinja2 Template Snippet
```html
<!-- Source: Derived from report structure requirements -->
<div id="executive-summary" class="{{ 'PASS' if converged else 'FAIL' }}">
  <h2>Executive Summary</h2>
  <div class="status-badge {{ status_class }}">{{ status }}</div>
  <table class="metrics-table">
    {% for metric in key_metrics %}
    <tr>
      <td>{{ metric.name }}</td>
      <td>{{ "%.4f"|format(metric.value) }} {{ metric.unit }}</td>
      <td class="{{ 'error-high' if metric.error_pct > 5 else 'error-ok' }}">
        {{ "%.2f"|format(metric.error_pct) }}% vs ref
      </td>
    </tr>
    {% endfor %}
  </table>
</div>

<div id="residual-chart">
  <h2>Residual Convergence</h2>
  <img src="data:image/png;base64,{{ residual_chart_b64 }}" />
</div>
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Plain-text reports (postprocess_report.txt) | Structured HTML reports with embedded charts | Phase 9 | Engineer readability + self-contained distribution |
| Manual literature comparison | Automated Gold Standards query | Phase 9 | Consistent, auditable comparison |
| No correction loop | Inline HTML correction -> CorrectionRecorder | Phase 9 | Continuous learning from human feedback |

**Deprecated/outdated:**
- `_create_report_artifact` in `runner.py` (lines 254-301): produces plain-text, placeholder for Phase 9 replacement

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | weasyprint has no major macOS-specific issues | PDF Generation | pdfkit/wkhtmltopdf is known problematic on macOS; weasyprint preferred |
| A2 | Gold Standards `get_expected_*` functions cover all needed reference data | Gold Standards Integration | If new case types are added, reference data may not exist |
| A3 | matplotlib is available (not just numpy) | Chart Generation | VisualizationEngine checks for matplotlib; likely present |

---

## Open Questions (RESOLVED)

1. **Correction endpoint location** — RESOLVED
   - Decision: Standalone script (`correction_endpoint.py`) with `process_correction_request()` function. HTTP endpoint optional for Phase 9. Notion Phase 4 push deferred.
   - Resolution: Plan 09-03 creates `correction_endpoint.py` with `CorrectionCallback` and `process_correction_request()` — no new HTTP server required.

2. **PDF archival location** — RESOLVED
   - Decision: Local files in `knowledge_compiler/reports/` only for Phase 9.
   - Resolution: Notion Cases DB push (Phase 4 integration) is a future enhancement, not Phase 9 scope.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| matplotlib | Chart generation | YES | 3.x (existing) | — |
| numpy | Chart calculations | YES | (existing) | — |
| Jinja2 | HTML templating | UNKNOWN | — | Hand-crafted strings (not recommended) |
| weasyprint | PDF generation | UNKNOWN | — | pdfkit (if weasyprint unavailable) |

**Missing dependencies with fallback:**
- Jinja2: If not installed, use string-based templates (less maintainable but functional)
- weasyprint: If not installed, skip PDF generation with warning; prioritize HTML

**Missing dependencies with no fallback:**
- None identified for Phase 9 core functionality

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing project standard) |
| Config file | pytest.ini or conftest.py (root level exists) |
| Quick run command | `pytest tests/test_phase9* -x -v` |
| Full suite command | `pytest tests/ -x --ignore=tests/test_phase1*` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| REQ-09-01 | SolverResult -> StandardPostprocessResult consumed | unit | `pytest tests/test_phase9_report_generator.py::test_input_consumption -x` | NO |
| REQ-09-02 | HTML report with executive summary generated | unit | `pytest tests/test_phase9_report_generator.py::test_html_structure -x` | NO |
| REQ-09-03 | Residual chart embedded as base64 PNG | unit | `pytest tests/test_phase9_report_generator.py::test_chart_embedding -x` | NO |
| REQ-09-04 | Literature comparison computed correctly | unit | `pytest tests/test_phase9_report_generator.py::test_literature_comparison -x` | NO |
| REQ-09-05 | JSON artifact produced | unit | `pytest tests/test_phase9_report_generator.py::test_json_output -x` | NO |
| REQ-09-06 | PDF artifact produced | integration | `pytest tests/test_phase9_report_generator.py::test_pdf_output -x` | NO |
| REQ-09-07 | Inline correction mechanism functional | manual | Browser click test | NO |

### Sampling Rate
- **Per task commit:** `pytest tests/test_phase9_report_generator.py -x`
- **Per wave merge:** Full suite (excluding Phase 1 tests)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase9_report_generator.py` — covers REQ-09-01 through REQ-09-06
- [ ] `knowledge_compiler/phase9_report/` — Phase 9 module directory
- [ ] Framework install: Jinja2 + weasyprint (if not already in environment)

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | NO | N/A — reports are read-only artifacts |
| V3 Session Management | NO | N/A — no user sessions in report generation |
| V4 Access Control | NO | N/A — reports generated from controlled pipeline |
| V5 Input Validation | YES | ReportGenerator validates file paths, chart data ranges |
| V6 Cryptography | NO | N/A — no encryption in report pipeline |

### Known Threat Patterns for Report Generation

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal in report output | Tampering | Use `Path.resolve()` and sandbox output to `knowledge_compiler/reports/` |
| Malicious template input | Information Disclosure | Jinja2 auto-escapes by default; validate template parameters |
| Large base64 payload DoS | Denial of Service | Limit chart resolution (dpi=150 max), warn if HTML > 5MB |

---

## Sources

### Primary (HIGH confidence)
- `knowledge_compiler/phase2/execution_layer/postprocess_runner.py` — StandardPostprocessResult, FieldData, ResidualSummary (VERIFIED)
- `knowledge_compiler/phase3/postprocess_runner/runner.py` — PostprocessRunner, PostprocessArtifact, PostprocessFormat (VERIFIED)
- `knowledge_compiler/phase3/schema.py` — SolverResult, PostprocessFormat.HTML_REPORT (VERIFIED)
- `knowledge_compiler/phase2c/correction_recorder.py` — CorrectionRecorder structure (VERIFIED)
- `knowledge_compiler/phase1/gold_standards/lid_driven_cavity.py` — get_expected_ghia_data(), CavityConstants (VERIFIED)
- `knowledge_compiler/phase1/gold_standards/backward_facing_step.py` — get_expected_reattachment_length() (VERIFIED)
- `knowledge_compiler/executables/chart_template.py` — matplotlib Agg backend usage (VERIFIED)
- `knowledge_compiler/phase1/visualization.py` — VisualizationEngine with matplotlib (VERIFIED)

### Secondary (MEDIUM confidence)
- weasyprint vs pdfkit comparison: [ASSUMED] based on general Python ecosystem knowledge — weasyprint is pure Python, pdfkit requires wkhtmltopdf system dependency
- Jinja2 best practices: [ASSUMED] standard Python templating pattern

### Tertiary (LOW confidence)
- Chart embedding DPI recommendations: [ASSUMED] based on general visualization experience — dpi=150 for screen, dpi=300 for print

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified existing dependencies in codebase
- Architecture: HIGH — patterns from existing Phase 2/3 code
- Pitfalls: MEDIUM — based on general experience, not verified with Phase 9 specifically

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (30 days — stable domain)
