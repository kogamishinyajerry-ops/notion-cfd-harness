---
phase: 09
slug: report-automation-postprocess-intelligence-goal-solverresult
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini or pyproject.toml [pytest] section |
| **Quick run command** | `pytest tests/test_phase9_report_generator.py -v --tb=short` |
| **Full suite command** | `pytest tests/test_phase9_report_generator.py tests/test_phase9_literature_comparison.py -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | REQ-09-01 | T-09-01 | N/A | unit | `pytest tests/test_phase9_report_generator.py::TestReportConfig -v` | ✅ | ⬜ pending |
| 09-01-02 | 01 | 1 | REQ-09-04 | T-09-02 | N/A | unit | `pytest tests/test_phase9_report_generator.py::TestGoldStandardLoader -v` | ✅ | ⬜ pending |
| 09-01-03 | 01 | 1 | REQ-09-03 | T-09-03 | N/A | unit | `pytest tests/test_phase9_report_generator.py::TestReportGenerator::test_residual_chart_in_html -v` | ✅ | ⬜ pending |
| 09-01-04 | 01 | 1 | REQ-09-02 | T-09-04 | N/A | unit | `pytest tests/test_phase9_report_generator.py::TestReportGenerator::test_executive_summary_first -v` | ✅ | ⬜ pending |
| 09-02-01 | 02 | 2 | REQ-09-05 | T-09-05 | N/A | unit | `pytest tests/test_phase9_report_generator.py -k "json" -v` | ✅ | ⬜ pending |
| 09-02-02 | 02 | 2 | REQ-09-06 | T-09-06 | N/A | unit | `pytest tests/test_phase9_report_generator.py::TestReportGenerator::test_pdf_generation_graceful -v` | ✅ | ⬜ pending |
| 09-03-01 | 03 | 3 | REQ-09-07 | T-09-07 | Input sanitization on field_name/value | unit | `pytest tests/test_phase9_report_generator.py::TestCorrectionCallback -v` | ✅ | ⬜ pending |
| 09-03-02 | 03 | 3 | REQ-09-08 | T-09-08 | N/A | unit | `pytest tests/test_phase9_report_generator.py::TestReportGenerator::test_errors_do_not_block -v` | ✅ | ⬜ pending |
| 09-03-03 | 03 | 3 | REQ-09-07 | T-09-07 | Only approved corrections applied | unit | `pytest tests/test_phase9_report_generator.py::TestReportTeachMode -v` | ✅ | ⬜ pending |
| 09-03-04 | 03 | 3 | REQ-09-08 | T-09-08 | N/A | integration | `pytest tests/test_phase9_report_generator.py -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase9_report_generator.py` — stubs for REQ-09-01 through REQ-09-08 (created by Plan 09-03 Task 3)
- [ ] `tests/conftest.py` — shared fixtures if needed (existing pytest infrastructure)
- [ ] `weasyprint` added to dependencies if PDF generation needed

*Phase 9 uses existing pytest infrastructure. Wave 0 is the test file created by Plan 09-03.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HTML report visual layout | REQ-09-02 | Requires human inspection of rendered HTML | Open generated HTML file, verify Executive Summary appears before Detailed Breakdown |
| Chart legibility | REQ-09-03 | Visual quality of embedded PNG charts | Open HTML, verify residual chart and field contours are visible and readable |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
