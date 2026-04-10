"""
ReportGenerator - Core report generation for Phase 9

D-06: Fully automatic -- no human intervention required.
D-07: Errors logged but do NOT block pipeline.
D-08: Three formats: HTML (primary self-contained), PDF, JSON.
"""

import json
import logging
import time
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


class ReportTeachMode:
    """
    D-10: Future reports auto-apply corrections from the teach store.

    Loads corrections from CorrectionRecorder storage and applies
    corrected values to report data before rendering.
    """

    def __init__(self, storage_path: str = "data/corrections"):
        self.storage_path = storage_path
        self._corrections: Dict[str, Dict[str, Any]] = {}
        self._load_corrections()

    def _load_corrections(self):
        """Load all corrections from storage."""
        try:
            from knowledge_compiler.phase2c.correction_recorder import CorrectionRecorder
            recorder = CorrectionRecorder(storage_path=self.storage_path)
            records = recorder.list_records(limit=1000)

            for record in records:
                if record.approved:
                    # Only apply approved corrections
                    self._apply_correction_record(record)

        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to load corrections: {e}")

    def _apply_correction_record(self, record):
        """Extract field corrections from a CorrectionRecord."""
        # Extract field corrections from correct_output
        correct_output = record.correct_output

        # The validation_result contains field_name and corrected_value
        if isinstance(correct_output, dict):
            validation_result = correct_output.get("validation_result", {})
            if isinstance(validation_result, dict):
                field_name = validation_result.get("field_name")
                corrected_value = validation_result.get("corrected_value")
                if field_name and corrected_value is not None:
                    self._corrections[field_name] = {
                        "value": corrected_value,
                        "source": record.record_id,
                    }

    def get_corrected_value(self, field_name: str, original_value: Any) -> Any:
        """
        Get corrected value for a field, or original if no correction exists.

        D-10: Future reports auto-apply corrections from the teach store.
        """
        correction = self._corrections.get(field_name)
        if correction:
            logging.getLogger(__name__).debug(
                f"Applying correction for {field_name}: {original_value} -> {correction['value']}"
            )
            return correction["value"]
        return original_value

    def apply_corrections_to_summary(self, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply corrections to executive summary data before rendering."""
        corrected = summary_data.copy()

        # Apply corrections to derived_quantities
        if "derived_quantities" in corrected:
            corrected["derived_quantities"] = [
                {
                    **q,
                    "value": self.get_corrected_value(q["name"], q["value"]),
                }
                for q in corrected["derived_quantities"]
            ]

        # Apply corrections to literature_comparisons (literature_comparisons are dataclass LiteratureComparison)
        if "literature_comparisons" in corrected:
            corrected["literature_comparisons"] = [
                type(comp)(
                    metric_name=comp.metric_name,
                    simulated_value=self.get_corrected_value(
                        f"{comp.metric_name}_sim", comp.simulated_value
                    ),
                    reference_value=comp.reference_value,
                    error_pct=comp.error_pct,
                    unit=comp.unit,
                    reference_source=comp.reference_source,
                    reynolds_number=comp.reynolds_number,
                    status=comp.status,
                )
                if hasattr(comp, 'metric_name')  # LiteratureComparison dataclass
                else comp
                for comp in corrected["literature_comparisons"]
            ]

        return corrected


class ReportGenerator:
    """
    Generates multi-format CFD reports from StandardPostprocessResult.

    Primary output is self-contained HTML with embedded charts (base64 PNG).
    Per D-01: Two-tier structure -- Executive Summary first, then detailed breakdown.
    Per D-07: All errors caught and logged, never blocking the pipeline.
    """

    def __init__(self, config: Optional[ReportConfig] = None, teach_mode: bool = True) -> None:
        self.config = config or ReportConfig()
        self.gold_loader = GoldStandardLoader()
        # D-10: Auto-apply corrections from teach store
        self.teach_mode = ReportTeachMode() if teach_mode else None

    def generate(
        self,
        postprocess_result: StandardPostprocessResult,
        solver_result: SolverResult,
        case_type: str = "unknown",
        reynolds_number: Optional[float] = None,
    ) -> Dict[str, str]:
        """
        Generate all report formats (HTML, PDF, JSON).

        D-06: Fully automatic -- no human intervention required.
        D-07: Errors logged but do NOT block pipeline -- each format fails gracefully.
        D-08: Three formats: HTML (primary self-contained), PDF, JSON.

        Returns:
            Dict with keys: html, pdf, json (empty string if format failed)
        """
        result = {"html": "", "pdf": "", "json": ""}

        try:
            # 1. Generate charts
            residual_chart_b64 = self._generate_residual_chart(postprocess_result.residuals)
            field_charts = self._generate_field_charts(postprocess_result.fields)

            # 2. Build executive summary data
            summary_data = self._build_executive_summary(
                postprocess_result, solver_result, case_type, reynolds_number
            )

            # 3. Render HTML (primary format)
            html_path = self._render_html(
                postprocess_result,
                solver_result,
                summary_data,
                residual_chart_b64,
                field_charts,
            )
            result["html"] = str(html_path)

            # 4. Render PDF from HTML (archival format)
            # D-07: PDF errors are logged, not blocking
            try:
                pdf_path = self._render_pdf(html_path)
                result["pdf"] = str(pdf_path)
            except Exception as e:
                logger.warning(f"PDF generation failed: {e}")

            # 5. Render JSON (machine consumption)
            # D-07: JSON errors are logged, not blocking
            try:
                json_path = self._render_json(postprocess_result, solver_result, summary_data)
                result["json"] = str(json_path)
            except Exception as e:
                logger.warning(f"JSON generation failed: {e}")

        except Exception as e:
            # D-07: Top-level errors logged, not blocking
            logger.error(f"Report generation failed: {e}")

        return result

    def generate_artifacts(
        self,
        postprocess_result: StandardPostprocessResult,
        solver_result: SolverResult,
        case_type: str = "unknown",
        reynolds_number: Optional[float] = None,
    ) -> List["PostprocessArtifact"]:
        """
        Generate all formats and return PostprocessArtifact list for pipeline integration.

        Returns list of PostprocessArtifact with format, file_path, metadata.
        Empty file_path indicates format failed (per D-07).
        """
        from knowledge_compiler.phase3.schema import PostprocessArtifact, PostprocessFormat

        paths = self.generate(postprocess_result, solver_result, case_type, reynolds_number)

        artifacts = []

        if paths.get("html"):
            artifacts.append(PostprocessArtifact(
                format=PostprocessFormat.HTML_REPORT,
                file_path=paths["html"],
                metadata={"case_type": case_type, "reynolds_number": reynolds_number},
            ))

        if paths.get("pdf") and paths["pdf"] not in ("", "."):
            artifacts.append(PostprocessArtifact(
                format=PostprocessFormat.PDF,
                file_path=paths["pdf"],
                metadata={"case_type": case_type, "reynolds_number": reynolds_number},
            ))

        if paths.get("json"):
            artifacts.append(PostprocessArtifact(
                format=PostprocessFormat.JSON,
                file_path=paths["json"],
                metadata={"case_type": case_type, "reynolds_number": reynolds_number},
            ))

        return artifacts

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

        summary_data = {
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

        # D-10: Apply corrections from teach store
        if self.teach_mode:
            summary_data = self.teach_mode.apply_corrections_to_summary(summary_data)

        return summary_data

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

    def _render_json(
        self,
        postprocess_result: StandardPostprocessResult,
        solver_result: SolverResult,
        summary_data: Dict[str, Any],
    ) -> Path:
        """Generate JSON machine-consumable format (D-08)."""
        output_data = {
            "report_metadata": {
                "result_id": postprocess_result.result_id,
                "generated_at": time.time(),
                "case_path": postprocess_result.case_path,
                "solver_type": postprocess_result.solver_type,
            },
            "convergence": {
                "converged": postprocess_result.residuals.converged if postprocess_result.residuals else False,
                "convergence_reason": postprocess_result.residuals.convergence_reason if postprocess_result.residuals else "",
                "final_residuals": postprocess_result.residuals.variables if postprocess_result.residuals else {},
                "initial_residuals": postprocess_result.residuals.initial if postprocess_result.residuals else {},
                "iterations": postprocess_result.residuals.iterations if postprocess_result.residuals else {},
            },
            "performance": {
                "processing_time": postprocess_result.processing_time,
                "runtime_seconds": solver_result.runtime_seconds,
            },
            "mesh_info": postprocess_result.mesh_info,
            "derived_quantities": [
                {
                    "name": q.name,
                    "value": q.value,
                    "unit": q.unit,
                    "location": q.location,
                    "formula": q.formula,
                }
                for q in postprocess_result.derived_quantities
            ],
            "literature_comparisons": [
                {
                    "metric_name": comp.metric_name,
                    "simulated_value": comp.simulated_value,
                    "reference_value": comp.reference_value,
                    "error_pct": comp.error_pct,
                    "unit": comp.unit,
                    "reference_source": comp.reference_source,
                    "reynolds_number": comp.reynolds_number,
                    "status": comp.status,
                }
                for comp in summary_data.get("literature_comparisons", [])
            ],
        }

        output_path = Path(self.config.output_dir) / f"report_{postprocess_result.result_id}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"JSON generated: {output_path}")
        return output_path

    def _render_pdf(self, html_path: Path) -> Path:
        """
        Generate PDF archival format from HTML using weasyprint (D-08).

        weasyprint chosen over pdfkit because:
        - Pure Python, no system dependencies (wkhtmltopdf)
        - Better macOS compatibility
        - CSS support aligns with HTML template
        """
        try:
            from weasyprint import HTML
        except ImportError:
            logger.warning("weasyprint not installed, skipping PDF generation")
            return Path("")

        pdf_path = html_path.with_suffix(".pdf")

        try:
            HTML(filename=str(html_path)).write_pdf(str(pdf_path))
            logger.info(f"PDF generated: {pdf_path}")
        except Exception as e:
            logger.warning(f"PDF generation failed: {e}")
            return Path("")

        return pdf_path
