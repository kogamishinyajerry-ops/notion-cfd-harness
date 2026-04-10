"""
Phase 9 Report Automation - ReportGenerator Core

Generates multi-format CFD reports from StandardPostprocessResult:
- HTML (primary, self-contained with embedded charts)
- PDF (archival)
- JSON (machine consumption)

D-01: Two-tier structure (Executive Summary first, then detailed breakdown)
D-02: Charts embedded as base64 PNG
D-07: Errors logged but do NOT block pipeline
D-09: Inline correction via CorrectionCallback
D-10: Auto-apply corrections from teach store via ReportTeachMode
"""

from typing import Any, Dict, List, Optional

from knowledge_compiler.phase9_report.report_configs import ReportConfig
from knowledge_compiler.phase9_report.report_generator import (
    ReportGenerator,
    ReportTeachMode,
    fig_to_base64_png,
)
from knowledge_compiler.phase9_report.gold_standard_loader import (
    GoldStandardLoader,
    LiteratureComparison,
)
from knowledge_compiler.phase9_report.correction_endpoint import (
    CorrectionCallback,
    process_correction_request,
)

__all__ = [
    "ReportConfig",
    "ReportGenerator",
    "ReportTeachMode",
    "fig_to_base64_png",
    "GoldStandardLoader",
    "LiteratureComparison",
    "CorrectionCallback",
    "process_correction_request",
    "integrate_with_postprocess_pipeline",
]


def integrate_with_postprocess_pipeline(
    postprocess_result: "StandardPostprocessResult",
    solver_result: "SolverResult",
    case_type: str = "unknown",
    reynolds_number: Optional[float] = None,
    output_dir: str = "knowledge_compiler/reports",
    generate_pdf: bool = True,
) -> "StandardPostprocessResult":
    """
    Convenience function: run full pipeline with report generation.

    Integrates ReportGenerator into PostprocessPipeline after
    PostprocessRunner completes.

    Args:
        postprocess_result: StandardPostprocessResult from PostprocessRunner
        solver_result: SolverResult from SolverRunner
        case_type: Case type for literature comparison (e.g., "lid_driven_cavity")
        reynolds_number: Reynolds number for literature comparison
        output_dir: Output directory for reports
        generate_pdf: Whether to generate PDF (requires weasyprint)

    Returns:
        Modified StandardPostprocessResult with artifacts extended

    D-06: Fully automatic -- no human intervention required.
    D-07: Report generation errors logged but do NOT block pipeline.
    """
    from knowledge_compiler.phase9_report import ReportGenerator, ReportConfig

    # Don't let report errors block the pipeline
    try:
        config = ReportConfig(output_dir=output_dir)
        generator = ReportGenerator(config)

        artifacts = generator.generate_artifacts(
            postprocess_result,
            solver_result,
            case_type=case_type,
            reynolds_number=reynolds_number,
        )

        # Extend postprocess_result artifacts
        postprocess_result.artifacts.extend(artifacts)

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Report generation failed: {e}")

    return postprocess_result
