"""
ReportGenerator - Core report generation for Phase 9

D-06: Fully automatic -- no human intervention required.
D-07: Errors logged but do NOT block pipeline.
D-08: Three formats: HTML (primary self-contained), PDF, JSON.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")  # Non-interactive backend, required for server environments

import base64
from io import BytesIO

from knowledge_compiler.phase2.execution_layer.postprocess_runner import (
    DerivedQuantity,
    FieldData,
    ResidualSummary,
    StandardPostprocessResult,
)
from knowledge_compiler.phase3.schema import SolverResult
from knowledge_compiler.phase9_report.gold_standard_loader import (
    GoldStandardLoader,
    LiteratureComparison,
)
from knowledge_compiler.phase9_report.report_configs import ReportConfig

logger = logging.getLogger(__name__)


def fig_to_base64_png(fig: plt.Figure, dpi: int = 150) -> str:
    """
    Convert matplotlib Figure to base64-encoded PNG string for HTML embedding.

    Args:
        fig: matplotlib Figure object
        dpi: dots-per-inch for the output PNG

    Returns:
        base64-encoded PNG string (utf-8 decoded)
    """
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    img_bytes = buf.getvalue()
    return base64.b64encode(img_bytes).decode("utf-8")


class ReportGenerator:
    """
    Generates multi-format CFD reports from StandardPostprocessResult.

    Primary output is self-contained HTML with embedded charts (base64 PNG).
    Per D-01: Two-tier structure -- Executive Summary first, then detailed breakdown.
    Per D-07: All errors caught and logged, never blocking the pipeline.
    """

    def __init__(self, config: Optional[ReportConfig] = None) -> None:
        self.config = config or ReportConfig()
        self.gold_loader = GoldStandardLoader()

    def generate(
        self,
        postprocess_result: StandardPostprocessResult,
        solver_result: SolverResult,
        case_type: str = "unknown",
        reynolds_number: Optional[float] = None,
    ) -> Dict[str, str]:
        """
        Generate HTML report from postprocess and solver results.

        Args:
            postprocess_result: StandardPostprocessResult from PostprocessRunner
            solver_result: SolverResult from solver execution
            case_type: Case type string for literature comparison lookup
            reynolds_number: Reynolds number for literature comparison

        Returns:
            Dict with "html" key pointing to generated HTML file path.
            Per D-07: errors are logged, not raised; returns {"html": "", "error": str}
        """
        try:
            # 1. Generate charts
            residual_chart_b64 = self._generate_residual_chart(postprocess_result.residuals)
            field_charts = self._generate_field_charts(postprocess_result.fields)

            # 2. Build executive summary data
            summary_data = self._build_executive_summary(
                postprocess_result, solver_result, case_type, reynolds_number
            )

            # 3. Render HTML
            html_path = self._render_html(
                postprocess_result,
                solver_result,
                summary_data,
                residual_chart_b64,
                field_charts,
            )

            return {"html": str(html_path)}

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return {"html": "", "error": str(e)}  # D-07: logged, not blocking

    def _generate_residual_chart(self, residuals: Optional[ResidualSummary]) -> str:
        """
        Generate residual convergence plot as base64 PNG.

        Creates a horizontal bar chart of final residuals per variable.
        """
        if not residuals or not residuals.variables:
            return ""

        fig, ax = plt.subplots(figsize=self.config.chart_figsize)
        var_names = list(residuals.variables.keys())
        final_residuals = list(residuals.variables.values())

        ax.barh(var_names, final_residuals, color="steelblue")
        ax.set_xlabel("Final Residual")
        ax.set_title("Residual Convergence")
        ax.set_xscale("log")
        ax.grid(True, alpha=0.3)

        chart_b64 = fig_to_base64_png(fig, dpi=self.config.dpi)
        plt.close(fig)
        return chart_b64

    def _generate_field_charts(self, fields: List[FieldData]) -> Dict[str, str]:
        """
        Generate field summary charts as base64 PNG dict keyed by field name.

        Currently a placeholder: actual field contour generation requires mesh data.
        Returns empty dict; field data is rendered as a table in the template.
        """
        # Placeholder: actual field contour generation would need mesh data
        # For now, include min/max table data in template
        return {}

    def _build_executive_summary(
        self,
        postprocess_result: StandardPostprocessResult,
        solver_result: SolverResult,
        case_type: str,
        reynolds_number: Optional[float],
    ) -> Dict[str, Any]:
        """Build executive summary data structure."""
        # Convergence status
        converged = (
            postprocess_result.residuals.converged if postprocess_result.residuals else False
        )
        status = "CONVERGED" if converged else "FAILED"

        # Precision gate status
        if postprocess_result.residuals and postprocess_result.residuals.variables:
            max_residual = max(postprocess_result.residuals.variables.values())
            precision_status = "PASS" if max_residual < self.config.precision_threshold else "WARN"
        else:
            precision_status = "UNKNOWN"

        # Literature comparisons
        literature_comparisons: List[LiteratureComparison] = []
        if case_type != "unknown" and reynolds_number is not None:
            ref_data = self.gold_loader.get_reference_data(case_type, reynolds_number)
            if ref_data:
                literature_comparisons = self._build_literature_comparisons(
                    postprocess_result, ref_data, reynolds_number
                )

        return {
            "status": status,
            "precision_status": precision_status,
            "result_id": postprocess_result.result_id,
            "case_path": postprocess_result.case_path,
            "solver_type": postprocess_result.solver_type,
            "processing_time": postprocess_result.processing_time,
            "runtime_seconds": solver_result.runtime_seconds,
            "literature_comparisons": literature_comparisons,
            "residuals": postprocess_result.residuals.variables if postprocess_result.residuals else {},
            "derived_quantities": [
                {"name": q.name, "value": q.value, "unit": q.unit}
                for q in postprocess_result.derived_quantities
            ],
            "mesh_info": postprocess_result.mesh_info,
        }

    def _build_literature_comparisons(
        self,
        postprocess_result: StandardPostprocessResult,
        ref_data: Dict[str, Any],
        reynolds_number: float,
    ) -> List[LiteratureComparison]:
        """Build literature comparison entries from reference data and derived quantities."""
        comparisons: List[LiteratureComparison] = []

        # For lid-driven cavity: compare max centerline velocity
        if "u_centerline" in ref_data and postprocess_result.derived_quantities:
            ref_max_u = max(ref_data.get("u_centerline", [0]))
            for q in postprocess_result.derived_quantities:
                if q.name == "max_u_centerline" and q.value:
                    comp = self.gold_loader.compare_with_reference(
                        simulated_value=q.value,
                        reference_value=ref_max_u,
                        metric_name="max_u_centerline",
                        unit="m/s",
                        reference_source="Ghia 1982",
                        reynolds_number=reynolds_number,
                        threshold_pct=self.config.precision_threshold,
                    )
                    comparisons.append(comp)

        return comparisons

    def _render_html(
        self,
        postprocess_result: StandardPostprocessResult,
        solver_result: SolverResult,
        summary_data: Dict[str, Any],
        residual_chart_b64: str,
        field_charts: Dict[str, str],
    ) -> Path:
        """Render HTML report using Jinja2 template."""
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        template_dir = Path(__file__).parent / "templates"
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        template = env.get_template(self.config.template_name)
        html_content = template.render(
            summary_data=summary_data,
            residual_chart_b64=residual_chart_b64,
            field_charts=field_charts,
            residuals=postprocess_result.residuals,
            fields=postprocess_result.fields,
            derived_quantities=postprocess_result.derived_quantities,
        )

        output_path = Path(self.config.output_dir) / f"report_{postprocess_result.result_id}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")

        return output_path
