#!/usr/bin/env python3
"""
Tests for Correction Recorder Integration

Tests the integration between TeachModeEngine and CorrectionRecorder.
Ensures that corrections are automatically generated when appropriate.
"""

import tempfile
from pathlib import Path

import pytest

from knowledge_compiler.phase1.teach import (
    TeachModeEngine,
    CorrectionRecorder,
    CorrectionDetection,
    TeachContext,
    is_generalizable_correction,
    record_teach_operation,
)
from knowledge_compiler.phase1.schema import (
    ErrorType,
    ImpactScope,
    CorrectionSpec,
    create_correction_id,
)


class TestCorrectionDetection:
    """Test correction detection logic"""

    def test_generalizable_operation_triggers_correction(self):
        """Generalizable operations should always trigger correction"""
        recorder = CorrectionRecorder()

        detection = recorder.detect_correction(
            operation_type="add_plot",
            previous_state={"plots": ["velocity"]},
            reason="Change from contour to line for better comparison",
            is_generalizable=True,
        )

        assert detection.should_create_correction is True
        assert detection.error_type == ErrorType.WRONG_PLOT
        assert detection.impact_scope == ImpactScope.SIMILAR_CASES

    def test_error_keyword_triggers_correction(self):
        """Operations with error keywords should trigger correction"""
        recorder = CorrectionRecorder()

        detection = recorder.detect_correction(
            operation_type="modify_plot",
            previous_state={"colormap": "jet"},
            reason="Fix wrong colormap - should use viridis",
            is_generalizable=False,
        )

        assert detection.should_create_correction is True
        assert detection.error_type == ErrorType.WRONG_PLOT

    def test_structural_change_triggers_correction(self):
        """Structural changes should trigger correction"""
        recorder = CorrectionRecorder()

        detection = recorder.detect_correction(
            operation_type="modify_structure",
            previous_state={"order": ["a", "b", "c"]},
            reason="Reorder to put overview first",
            is_generalizable=False,
        )

        assert detection.should_create_correction is True

    def test_one_off_operation_no_correction(self):
        """One-off operations without fixes don't need correction"""
        recorder = CorrectionRecorder()

        detection = recorder.detect_correction(
            operation_type="add_plot",
            previous_state={"plots": ["velocity"]},
            reason="Just adding this one plot for this case",
            is_generalizable=False,
        )

        assert detection.should_create_correction is False


class TestCorrectionRecorder:
    """Test CorrectionRecorder functionality"""

    def test_create_correction(self):
        """Test creating a CorrectionSpec"""
        recorder = CorrectionRecorder()

        correction = recorder.create_correction(
            correction_id="CORRECT-TEST001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot_type": "contour"},
            correct_output={"plot_type": "line"},
            human_reason="Line plot is better for comparison",
            impact_scope=ImpactScope.SIMILAR_CASES,
            linked_teach_record_id="TEACH-001",
        )

        assert correction.correction_id == "CORRECT-TEST001"
        assert correction.error_type == ErrorType.WRONG_PLOT
        assert correction.linked_teach_record_id == "TEACH-001"

    def test_save_and_load_correction(self):
        """Test saving and loading CorrectionSpec"""
        recorder = CorrectionRecorder()

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            local_recorder = CorrectionRecorder(storage_path)

            correction = local_recorder.create_correction(
                correction_id="CORRECT-TEST002",
                error_type=ErrorType.MISSING_DATA,
                wrong_output={"metrics": ["drag"]},
                correct_output={"metrics": ["drag", "lift"]},
                human_reason="Lift coefficient is essential",
                impact_scope=ImpactScope.REPORT_SPEC,
                linked_teach_record_id="TEACH-002",
            )

            local_recorder.save_correction(correction)

            loaded = local_recorder.load_correction("CORRECT-TEST002")
            assert loaded is not None
            assert loaded.error_type == ErrorType.MISSING_DATA
            assert len(loaded.correct_output["metrics"]) == 2

    def test_list_corrections(self):
        """Test listing corrections with filters"""
        recorder = CorrectionRecorder()

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            local_recorder = CorrectionRecorder(storage_path)

            # Create multiple corrections
            for i in range(3):
                correction = local_recorder.create_correction(
                    correction_id=f"CORRECT-TEST{i:03d}",
                    error_type=ErrorType.WRONG_PLOT,
                    wrong_output={},
                    correct_output={},
                    human_reason=f"Test correction {i}",
                    impact_scope=ImpactScope.SINGLE_CASE,
                    linked_teach_record_id=f"TEACH-00{i}",
                )
                local_recorder.save_correction(correction)

            # List all
            all_corrections = local_recorder.list_corrections()
            assert len(all_corrections) == 3

            # Filter by teach_record_id
            filtered = local_recorder.list_corrections(teach_record_id="TEACH-001")
            assert len(filtered) == 1

    def test_infer_affected_components(self):
        """Test inference of affected components"""
        recorder = CorrectionRecorder()

        components = recorder._infer_affected_components(ErrorType.WRONG_PLOT)
        assert components == ["PlotSpec"]

        components = recorder._infer_affected_components(ErrorType.INVALID_ORDER)
        assert components == ["ReportSpec"]


class TestTeachModeEngineCorrectionIntegration:
    """Test TeachModeEngine integration with CorrectionRecorder"""

    def test_record_operation_creates_correction_for_generalizable(self):
        """Recording a generalizable operation should create a CorrectionSpec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            engine = TeachModeEngine(storage_path)

            context = TeachContext(
                draft_id="DRAFT-001",
                case_id="case_001",
                timestamp=1234567890.0,
                previous_state={"plots": ["velocity"]},
                operation_type="add_plot",
            )

            response = engine.record_operation(
                context=context,
                description="Add temperature field plot",
                reason="Heat transfer cases need temperature visualization",
                is_generalizable=True,  # This should trigger correction
            )

            assert response.success is True
            assert response.generalizable is True

            # Check that CorrectionSpec was created
            corrections = engine.list_corrections(
                teach_record_id=response.teach_record_id,
            )
            assert len(corrections) == 1

            correction = corrections[0]
            assert correction.impact_scope == ImpactScope.SIMILAR_CASES

    def test_record_operation_skips_correction_for_one_off(self):
        """Recording a one-off operation should not create a CorrectionSpec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            engine = TeachModeEngine(storage_path)

            context = TeachContext(
                draft_id="DRAFT-002",
                case_id="case_002",
                timestamp=1234567890.0,
                previous_state={},
                operation_type="add_plot",
            )

            response = engine.record_operation(
                context=context,
                description="Add this one plot for this specific case",
                reason="Just for this case",
                is_generalizable=False,  # Not generalizable, no error keywords
            )

            assert response.success is True

            # Check that no CorrectionSpec was created
            corrections = engine.list_corrections(
                teach_record_id=response.teach_record_id,
            )
            assert len(corrections) == 0

    def test_mark_correction_replay_passed(self):
        """Test marking correction as replay-passed"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            engine = TeachModeEngine(storage_path)

            # Create a correction directly
            correction = CorrectionSpec(
                correction_id="CORRECT-REPLAY001",
                error_type=ErrorType.WRONG_PLOT,
                wrong_output={},
                correct_output={},
                human_reason="Test",
                linked_teach_record_id="TEACH-001",
            )
            engine.correction_recorder.save_correction(correction)

            # Mark as passed
            result = engine.mark_correction_replay_passed("CORRECT-REPLAY001")
            assert result is True

            # Verify
            loaded = engine.get_correction("CORRECT-REPLAY001")
            assert loaded.replay_status == "passed"

    def test_mark_correction_replay_failed(self):
        """Test marking correction as replay-failed"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            engine = TeachModeEngine(storage_path)

            # Create a correction
            correction = CorrectionSpec(
                correction_id="CORRECT-REPLAY002",
                error_type=ErrorType.WRONG_METRIC,
                wrong_output={},
                correct_output={},
                human_reason="Test",
                linked_teach_record_id="TEACH-002",
            )
            engine.correction_recorder.save_correction(correction)

            # Mark as failed
            result = engine.mark_correction_replay_failed(
                "CORRECT-REPLAY002",
                "Replay still produces wrong output",
            )
            assert result is True

            # Verify
            loaded = engine.get_correction("CORRECT-REPLAY002")
            assert loaded.replay_status == "failed"
            assert "Replay still produces wrong output" in loaded.metadata["replay_failure_reason"]


class TestIsGeneralizableCorrection:
    """Test is_generalizable_correction function"""

    def test_similar_cases_requires_replay(self):
        """SIMILAR_CASES scope requires replay"""
        assert is_generalizable_correction(ImpactScope.SIMILAR_CASES) is True

    def test_all_cases_requires_replay(self):
        """ALL_CASES scope requires replay"""
        assert is_generalizable_correction(ImpactScope.ALL_CASES) is True

    def test_report_spec_requires_replay(self):
        """REPORT_SPEC scope requires replay"""
        assert is_generalizable_correction(ImpactScope.REPORT_SPEC) is True

    def test_gate_definition_requires_replay(self):
        """GATE_DEFINITION scope requires replay"""
        assert is_generalizable_correction(ImpactScope.GATE_DEFINITION) is True

    def test_single_case_skips_replay(self):
        """SINGLE_CASE scope does not require replay"""
        assert is_generalizable_correction(ImpactScope.SINGLE_CASE) is False


class TestCorrectionScenarios:
    """Test real-world correction scenarios"""

    def test_wrong_plot_type_scenario(self):
        """Scenario: System generated contour, engineer changed to line"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            engine = TeachModeEngine(storage_path)

            context = TeachContext(
                draft_id="DRAFT-001",
                case_id="backward_facing_step",
                timestamp=1234567890.0,
                previous_state={
                    "plot_name": "pressure_field",
                    "plot_type": "contour",
                },
                operation_type="modify_plot",
            )

            response = engine.record_operation(
                context=context,
                description="Change to line plot along centerline",
                reason="Contour doesn't show gradient clearly, line plot is better",
                is_generalizable=True,
            )

            corrections = engine.list_corrections(
                teach_record_id=response.teach_record_id,
            )

            assert len(corrections) == 1
            correction = corrections[0]
            assert correction.error_type == ErrorType.WRONG_PLOT
            assert "contour" in str(correction.wrong_output)
            assert correction.impact_scope == ImpactScope.SIMILAR_CASES

    def test_missing_metric_scenario(self):
        """Scenario: System forgot lift coefficient"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            engine = TeachModeEngine(storage_path)

            context = TeachContext(
                draft_id="DRAFT-002",
                case_id="airfoil_analysis",
                timestamp=1234567890.0,
                previous_state={"metrics": ["drag_coefficient"]},
                operation_type="add_metric",
            )

            response = engine.record_operation(
                context=context,
                description="Add lift coefficient",
                reason="Lift is essential for airfoil analysis - was missing",
                is_generalizable=True,
            )

            corrections = engine.list_corrections(
                teach_record_id=response.teach_record_id,
            )

            assert len(corrections) == 1
            correction = corrections[0]
            assert correction.error_type == ErrorType.MISSING_DATA
            # Verify the reason indicates missing data
            assert "missing" in correction.human_reason.lower() or "essential" in correction.human_reason.lower()

    def test_fix_order_scenario(self):
        """Scenario: Engineer reordered report sections"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir)
            engine = TeachModeEngine(storage_path)

            context = TeachContext(
                draft_id="DRAFT-003",
                case_id="generic_case",
                timestamp=1234567890.0,
                previous_state={"order": ["plots", "overview", "metrics"]},
                operation_type="modify_structure",
            )

            response = engine.record_operation(
                context=context,
                description="Move overview to beginning",
                reason="Fix the order - overview should come first, then plots",
                is_generalizable=True,
            )

            corrections = engine.list_corrections(
                teach_record_id=response.teach_record_id,
            )

            assert len(corrections) == 1
            correction = corrections[0]
            assert correction.error_type == ErrorType.INVALID_ORDER
            assert correction.impact_scope == ImpactScope.ALL_CASES


@pytest.mark.parametrize("operation_type,reason,is_generalizable,expected_correction", [
    ("add_plot", "Add for all similar cases", True, True),
    ("add_plot", "Just for this case", False, False),
    ("modify_plot", "Fix wrong plot type", False, True),
    ("add_metric", "Missing metric - add to template", True, True),
    ("modify_structure", "Fix order - standard for all", True, True),
    ("add_explanation", "Add explanation for this anomaly", False, False),
])
def test_correction_detection_matrix(
    operation_type, reason, is_generalizable, expected_correction
):
    """Test matrix of operation types and correction generation"""
    recorder = CorrectionRecorder()
    detection = recorder.detect_correction(
        operation_type=operation_type,
        previous_state={},
        reason=reason,
        is_generalizable=is_generalizable,
    )

    assert detection.should_create_correction == expected_correction
