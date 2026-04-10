# Phase 9: Report Automation & Postprocess Intelligence - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 09-Report Automation
**Areas discussed:** Report content & structure, Comparison scope, Automation level, Output formats, ReportTeachMode

---

## Report content & structure

| Option | Description | Selected |
|--------|-------------|----------|
| Executive Summary + Details (Recommended) | Brief conclusion first (converged/failed, key metrics), then detailed breakdown of residuals, fields, derived quantities | ✓ |
| Full Detail Only | Comprehensive technical data dump — residuals, all field min/max, mesh quality, no executive summary | |
| Narrative-driven | Story format: 'The case was set up for X geometry. After Y iterations, Z was observed...' | |

**User's choice:** Executive Summary + Details (Recommended)

**Notes:** User wants two-tier structure — quick结论 first, then technical details

---

## Charts

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — residual convergence plot + key field contours (Recommended) | Generate matplotlib charts: residual history, velocity/pressure distributions. Increases report size but much more readable | ✓ |
| Text only | No charts — keep it lightweight and fast. Tables and numbers only | |
| Optional / flag-controlled | Chart generation controlled by a flag/option | |

**User's choice:** Yes — residual convergence plot + key field contours (Recommended)

**Notes:** Charts for residual convergence + field contours

---

## Comparison scope

| Option | Description | Selected |
|--------|-------------|----------|
| Case vs Literature (Recommended) | Compare solver results against published reference data (Ghia 1982, etc.) | ✓ |
| Case vs Case | Compare multiple simulation runs (e.g., different mesh densities, boundary conditions) | |
| Both case-vs-literature and case-vs-case | Support both modes | |

**User's choice:** Case vs Literature (Recommended)

**Notes:** Primary use case is validating simulation accuracy against literature

---

## Ref data

| Option | Description | Selected |
|--------|-------------|----------|
| From Gold Standards / teaching records (Recommended) | Use the existing Gold Standards library (lid_driven_cavity.py, backward_facing_step.py etc.) which contain reference data | ✓ |
| From user-provided reference files | User uploads CSV/JSON files with reference data per case type | |
| Both Gold Standards + user files | Gold Standards as default, user can override/add reference data | |

**User's choice:** From Gold Standards / teaching records (Recommended)

---

## Automation level

| Option | Description | Selected |
|--------|-------------|----------|
| Fully automatic after solver completes (Recommended) | Report generates automatically as part of postprocess pipeline. No human gate needed. Errors logged but don't block pipeline | ✓ |
| Human review gate | Report generates but requires human acknowledgment before being marked complete | |
| On-demand only | Report only generated when explicitly requested via CLI/API | |

**User's choice:** Fully automatic after solver completes (Recommended)

---

## Output formats

| Option | Description | Selected |
|--------|-------------|----------|
| HTML (Recommended) | Self-contained HTML with embedded CSS and charts | |
| HTML + Notion page | HTML for web + auto-create Notion page in Cases DB | |
| Multiple: HTML + PDF + JSON (Recommended) | Full suite: HTML for viewing, PDF for archival, JSON for machine consumption | ✓ |

**User's choice:** Multiple: HTML + PDF + JSON

---

## Teach mode

| Option | Description | Selected |
|--------|-------------|----------|
| Inline correction (Recommended) | User clicks on value in HTML → flags incorrect → correction recorded to correction_recorder | ✓ |
| Post-run CLI review | After report generates, CLI prompts user: 'Do you accept this report? [y/n]' | |
| Separate Notion review | Report pushed to Notion. Human edits Notion page directly. System syncs corrections back | |

**User's choice:** Inline correction (Recommended)

---

## Claude's Discretion

The following were left to researcher/planner discretion:
- Exact chart rendering library (matplotlib vs plotly)
- Specific HTML template structure
- PDF generation approach (weasyprint, pdfkit, etc.)

## Deferred Ideas

None — all discussion stayed within Phase 9 scope.
