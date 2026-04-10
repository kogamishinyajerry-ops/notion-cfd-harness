"""
Phase 9 Report Automation - ReportGenerator Core

Generates multi-format CFD reports from StandardPostprocessResult:
- HTML (primary, self-contained with embedded charts)
- PDF (archival)
- JSON (machine consumption)

D-01: Two-tier structure (Executive Summary first, then detailed breakdown)
D-02: Charts embedded as base64 PNG
D-07: Errors logged but do NOT block pipeline
"""

from knowledge_compiler.phase9_report.report_configs import ReportConfig
from knowledge_compiler.phase9_report.report_generator import (
    ReportGenerator,
    fig_to_base64_png,
)
from knowledge_compiler.phase9_report.gold_standard_loader import (
    GoldStandardLoader,
    LiteratureComparison,
)

__all__ = [
    "ReportConfig",
    "ReportGenerator",
    "fig_to_base64_png",
    "GoldStandardLoader",
    "LiteratureComparison",
]
