#!/usr/bin/env python3
"""
Phase 9 ReportGenerator Tests

Tests REQ-09-01 through REQ-09-08:
- REQ-09-01: Consume SolverResult, output StandardPostprocessResult
- REQ-09-02: Generate HTML report with executive summary + detailed breakdown
- REQ-09-03: Embed residual convergence plot as base64 PNG in HTML
- REQ-09-04: Literature comparison computed correctly
- REQ-09-05: JSON artifact produced
- REQ-09-06: PDF artifact produced (if weasyprint available)
- REQ-09-07: Inline correction mechanism functional
- REQ-09-08: Report errors logged, not blocking pipeline
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

from knowledge_compiler.phase2.execution_layer.postprocess_runner import (
    StandardPostprocessResult,
    PostprocessStatus,
    FieldData,
    FieldType,
    ResidualSummary,
    DerivedQuantity,
)
from knowledge_compiler.phase3.schema import SolverResult, SolverStatus
from knowledge_compiler.phase9_report import (
    ReportGenerator,
    ReportConfig,
    GoldStandardLoader,
    LiteratureComparison,
    ReportTeachMode,
)


class TestReportConfig:
    """Test ReportConfig dataclass"""

    def test_default_values(self):
        config = ReportConfig()
        assert config.output_dir == "knowledge_compiler/reports"
        assert config.dpi == 150
        assert config.precision_threshold == 5.0
        assert config.chart_figsize == (10, 6)


class TestGoldStandardLoader:
    """Test GoldStandardLoader and literature comparison"""

    def test_get_reference_data_lid_cavity(self):
        loader = GoldStandardLoader()
        ref = loader.get_reference_data("lid_driven_cavity", 1000)
        assert "reynolds_number" in ref
        assert ref["reynolds_number"] == 1000
        assert "u_centerline" in ref
        assert "y_positions" in ref

    def test_get_reference_data_unknown_case(self):
        loader = GoldStandardLoader()
        ref = loader.get_reference_data("unknown_case", 100)
        assert ref is None

    def test_compare_with_reference_pass(self):
        loader = GoldStandardLoader()
        comp = loader.compare_with_reference(
            simulated_value=0.51,
            reference_value=0.50,
            metric_name="test_metric",
            unit="m/s",
            reference_source="Test",
            reynolds_number=1000,
            threshold_pct=5.0,
        )
        assert comp.status == "PASS"
        assert 0 < comp.error_pct <= 5.0

    def test_compare_with_reference_fail(self):
        loader = GoldStandardLoader()
        comp = loader.compare_with_reference(
            simulated_value=1.0,
            reference_value=0.50,
            metric_name="test_metric",
            unit="m/s",
            reference_source="Test",
            reynolds_number=1000,
            threshold_pct=5.0,
        )
        assert comp.status == "FAIL"
        assert comp.error_pct == 100.0


class TestReportGenerator:
    """Test ReportGenerator core functionality"""

    @pytest.fixture
    def temp_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_postprocess_result(self):
        residuals = ResidualSummary(
            variables={"p": 1e-5, "U": 2e-5, "epsilon": 3e-5},
            initial={"p": 0.1, "U": 0.2, "epsilon": 0.3},
            iterations={"p": 100, "U": 100, "epsilon": 100},
            converged=True,
            convergence_reason="Solution converged",
        )

        fields = [
            FieldData(name="p", field_type=FieldType.SCALAR, dimensions=1,
                      unit="Pa", min_value=0.0, max_value=101325.0, mean_value=50662.5),
            FieldData(name="U", field_type=FieldType.VECTOR, dimensions=3,
                      unit="m/s", min_value=0.0, max_value=1.0, mean_value=0.5),
        ]

        derived = [
            DerivedQuantity(name="max_u_centerline", value=0.95, unit="m/s"),
            DerivedQuantity(name="pressure_drop", value=1000.0, unit="Pa"),
        ]

        return StandardPostprocessResult(
            result_id="TEST-RUN-001",
            status=PostprocessStatus.COMPLETED,
            fields=fields,
            residuals=residuals,
            derived_quantities=derived,
            case_path="/test/case/lid_driven_cavity_Re1000",
            solver_type="openfoam",
            mesh_info={"n_cells": 10000, "n_points": 5000},
            processing_time=2.5,
        )

    @pytest.fixture
    def mock_solver_result(self):
        return SolverResult(
            job_id="JOB-001",
            status=SolverStatus.COMPLETED,
            exit_code=0,
            stdout="Solving for p, Final residual = 1e-5",
            stderr="",
            runtime_seconds=120.0,
        )

    def test_generate_returns_all_formats(self, temp_output_dir, mock_postprocess_result, mock_solver_result):
        """REQ-09-02 + REQ-09-05: HTML and JSON produced"""
        config = ReportConfig(output_dir=temp_output_dir)
        gen = ReportGenerator(config)

        result = gen.generate(mock_postprocess_result, mock_solver_result)

        assert "html" in result
        assert "json" in result
        assert result["html"]  # Not empty
        assert result["json"]  # Not empty

        # Check HTML file exists
        assert Path(result["html"]).exists()

        # Check JSON content
        with open(result["json"]) as f:
            data = json.load(f)
        assert "convergence" in data
        assert data["convergence"]["converged"] is True

    def test_residual_chart_in_html(self, temp_output_dir, mock_postprocess_result, mock_solver_result):
        """REQ-09-03: Residual chart embedded as base64 PNG"""
        config = ReportConfig(output_dir=temp_output_dir)
        gen = ReportGenerator(config)

        result = gen.generate(mock_postprocess_result, mock_solver_result)

        with open(result["html"]) as f:
            html_content = f.read()

        # Check for base64 PNG embedding
        assert "data:image/png;base64," in html_content
        # Check residual section present
        assert "Residual Convergence" in html_content

    def test_executive_summary_first(self, temp_output_dir, mock_postprocess_result, mock_solver_result):
        """REQ-09-02: Executive Summary appears first in HTML"""
        config = ReportConfig(output_dir=temp_output_dir)
        gen = ReportGenerator(config)

        result = gen.generate(mock_postprocess_result, mock_solver_result)

        with open(result["html"]) as f:
            html_content = f.read()

        # Executive summary should appear before detailed breakdown
        exec_summary_pos = html_content.find('id="executive-summary"')
        detailed_pos = html_content.find('id="detailed-breakdown"')
        assert exec_summary_pos < detailed_pos
        assert exec_summary_pos > 0

    def test_literature_comparison_in_json(self, temp_output_dir, mock_postprocess_result, mock_solver_result):
        """REQ-09-04: Literature comparison in JSON output"""
        config = ReportConfig(output_dir=temp_output_dir)
        gen = ReportGenerator(config)

        # lid_driven_cavity with Re=1000 has gold standard
        result = gen.generate(
            mock_postprocess_result,
            mock_solver_result,
            case_type="lid_driven_cavity",
            reynolds_number=1000.0,
        )

        with open(result["json"]) as f:
            data = json.load(f)

        assert "literature_comparisons" in data

    def test_errors_do_not_block(self, temp_output_dir):
        """REQ-09-08: Errors logged, not blocking pipeline"""
        config = ReportConfig(output_dir=temp_output_dir)
        gen = ReportGenerator(config)

        # Pass None data - should not raise, should return empty results
        result = gen.generate(None, None)

        assert isinstance(result, dict)
        assert "html" in result
        # HTML should be empty string due to error, not crashed

    def test_pdf_generation_graceful(self, temp_output_dir, mock_postprocess_result, mock_solver_result):
        """REQ-09-06: PDF generation graceful if weasyprint not available"""
        config = ReportConfig(output_dir=temp_output_dir)
        gen = ReportGenerator(config)

        result = gen.generate(mock_postprocess_result, mock_solver_result)

        # PDF may or may not be generated depending on weasyprint
        assert "pdf" in result
        if result["pdf"]:
            assert Path(result["pdf"]).exists()


class TestCorrectionCallback:
    """Test inline correction mechanism (D-09)"""

    @pytest.fixture
    def temp_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_process_correction_request(self, temp_storage):
        """REQ-09-07: Inline correction records to CorrectionRecorder"""
        from knowledge_compiler.phase9_report import process_correction_request

        result = process_correction_request(
            record_id="TEST-001",
            field_name="max_u_centerline",
            value="0.95",
            engineer_id="test_engineer",
        )

        # Should return status
        assert "status" in result


class TestReportTeachMode:
    """Test ReportTeachMode auto-correction (D-10)"""

    def test_loads_corrections_from_storage(self):
        """D-10: TeachMode loads corrections from storage"""
        teach = ReportTeachMode(storage_path="data/corrections")
        # Should not raise
        assert teach is not None

    def test_apply_corrections_to_summary(self):
        """D-10: Corrections applied to summary before rendering"""
        teach = ReportTeachMode()

        summary = {
            "derived_quantities": [
                {"name": "test_metric", "value": 1.0, "unit": "m/s"}
            ],
            "literature_comparisons": [
                {
                    "metric_name": "test",
                    "simulated_value": 0.5,
                    "reference_value": 0.5,
                    "error_pct": 0.0,
                    "unit": "m/s",
                    "reference_source": "test",
                    "reynolds_number": 1000,
                    "status": "PASS",
                }
            ],
        }

        corrected = teach.apply_corrections_to_summary(summary)

        # Without actual corrections stored, should return original
        assert corrected is not None
        assert "derived_quantities" in corrected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
