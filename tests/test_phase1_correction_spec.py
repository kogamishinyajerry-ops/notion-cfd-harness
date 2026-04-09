#!/usr/bin/env python3
"""
Tests for CorrectionSpec Schema

CorrectionSpec is the primary learning channel in Phase 1.
When an engineer modifies system output, a CorrectionSpec MUST be generated.
"""

import json
import tempfile
from pathlib import Path

import pytest

from knowledge_compiler.phase1.schema import (
    CorrectionSpec,
    ErrorType,
    ImpactScope,
    create_correction_id,
)


class TestErrorType:
    """Test ErrorType enum"""

    def test_data_errors_exist(self):
        """Data error types should be defined"""
        assert ErrorType.MISSING_DATA
        assert ErrorType.INCORRECT_DATA
        assert ErrorType.INCONSISTENT_DATA

    def test_process_errors_exist(self):
        """Process error types should be defined"""
        assert ErrorType.WRONG_PLOT
        assert ErrorType.WRONG_METRIC
        assert ErrorType.WRONG_SECTION

    def test_logic_errors_exist(self):
        """Logic error types should be defined"""
        assert ErrorType.MISINTERPRETATION
        assert ErrorType.MISSING_EXPLANATION
        assert ErrorType.INCORRECT_INFERENCE

    def test_structural_errors_exist(self):
        """Structural error types should be defined"""
        assert ErrorType.INVALID_ORDER
        assert ErrorType.MISSING_COMPONENT
        assert ErrorType.DUPLICATE_CONTENT


class TestImpactScope:
    """Test ImpactScope enum"""

    def test_scopes_exist(self):
        """All impact scopes should be defined"""
        assert ImpactScope.SINGLE_CASE
        assert ImpactScope.SIMILAR_CASES
        assert ImpactScope.ALL_CASES
        assert ImpactScope.REPORT_SPEC
        assert ImpactScope.GATE_DEFINITION


class TestCorrectionSpecCreation:
    """Test CorrectionSpec creation"""

    def test_minimal_creation(self):
        """Create CorrectionSpec with minimal required fields"""
        correction = CorrectionSpec(
            correction_id="CORRECT-TEST001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot_type": "contour", "field": "pressure"},
            correct_output={"plot_type": "line", "field": "pressure"},
            human_reason="Line plot is more appropriate for this comparison",
        )

        assert correction.correction_id == "CORRECT-TEST001"
        assert correction.error_type == ErrorType.WRONG_PLOT
        assert correction.wrong_output["plot_type"] == "contour"
        assert correction.correct_output["plot_type"] == "line"
        assert correction.impact_scope == ImpactScope.SINGLE_CASE  # default
        assert correction.needs_replay is True  # default
        assert correction.replay_status == "pending"  # default

    def test_full_creation(self):
        """Create CorrectionSpec with all fields"""
        correction = CorrectionSpec(
            correction_id="CORRECT-TEST002",
            error_type=ErrorType.MISSING_COMPONENT,
            wrong_output={"plots": ["velocity", "pressure"]},
            correct_output={"plots": ["velocity", "pressure", "temperature"]},
            human_reason="Temperature field is required for heat transfer analysis",
            evidence=["EVID-001", "EVID-002"],
            linked_teach_record_id="TEACH-001",
            linked_report_spec_id="RSPEC-001",
            impact_scope=ImpactScope.REPORT_SPEC,
            affected_components=["PlotSpec", "ReportSpec"],
            root_cause="Heat transfer problem type template was incomplete",
            fix_action="Add temperature to required_plots for HEAT_TRANSFER type",
            needs_replay=True,
            replay_case_ids=["case_001", "case_002"],
            author="engineer_alice",
            metadata={"priority": "high", "category": "template_fix"},
        )

        assert correction.correction_id == "CORRECT-TEST002"
        assert len(correction.evidence) == 2
        assert correction.impact_scope == ImpactScope.REPORT_SPEC
        assert len(correction.affected_components) == 2
        assert correction.root_cause is not None
        assert correction.fix_action is not None
        assert correction.author == "engineer_alice"


class TestCorrectionSpecMethods:
    """Test CorrectionSpec methods"""

    def test_to_dict(self):
        """Test conversion to dictionary"""
        correction = CorrectionSpec(
            correction_id="CORRECT-TEST003",
            error_type=ErrorType.WRONG_METRIC,
            wrong_output={"metric": "velocity", "unit": "m/s"},
            correct_output={"metric": "velocity", "unit": "m/s", "location": "inlet"},
            human_reason="Need location specification for velocity metrics",
        )

        result = correction.to_dict()

        assert result["correction_id"] == "CORRECT-TEST003"
        assert result["error_type"] == "wrong_metric"
        assert "timestamp_iso" in result
        assert result["wrong_output"]["metric"] == "velocity"

    def test_to_json(self):
        """Test conversion to JSON"""
        correction = CorrectionSpec(
            correction_id="CORRECT-TEST004",
            error_type=ErrorType.INVALID_ORDER,
            wrong_output={"order": ["overview", "details", "appendix"]},
            correct_output={"order": ["overview", "appendix", "details"]},
            human_reason="Details should come after appendix",
        )

        json_str = correction.to_json()
        data = json.loads(json_str)

        assert data["correction_id"] == "CORRECT-TEST004"
        assert data["error_type"] == "invalid_order"

    def test_mark_replay_passed(self):
        """Test marking replay as passed"""
        correction = CorrectionSpec(
            correction_id="CORRECT-TEST005",
            error_type=ErrorType.WRONG_SECTION,
            wrong_output={"section": "midplane"},
            correct_output={"section": "wall"},
            human_reason="Wall section is more relevant",
        )

        assert correction.replay_status == "pending"
        correction.mark_replay_passed()
        assert correction.replay_status == "passed"

    def test_mark_replay_failed(self):
        """Test marking replay as failed"""
        correction = CorrectionSpec(
            correction_id="CORRECT-TEST006",
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={"value": 1.5},
            correct_output={"value": 2.0},
            human_reason="Correct value is 2.0",
        )

        correction.mark_replay_failed("Replay produced 1.5 instead of 2.0")

        assert correction.replay_status == "failed"
        assert correction.metadata["replay_failure_reason"] == "Replay produced 1.5 instead of 2.0"

    def test_link_to_teach_record(self):
        """Test linking to TeachRecord"""
        correction = CorrectionSpec(
            correction_id="CORRECT-TEST007",
            error_type=ErrorType.MISINTERPRETATION,
            wrong_output={"interpretation": "steady_state"},
            correct_output={"interpretation": "transient"},
            human_reason="This is a transient simulation",
        )

        correction.link_to_teach_record("TEACH-123")
        assert correction.linked_teach_record_id == "TEACH-123"

    def test_link_to_report_spec(self):
        """Test linking to ReportSpec"""
        correction = CorrectionSpec(
            correction_id="CORRECT-TEST008",
            error_type=ErrorType.DUPLICATE_CONTENT,
            wrong_output={"plots": ["p1", "p1", "p2"]},
            correct_output={"plots": ["p1", "p2"]},
            human_reason="Duplicate plot removed",
        )

        correction.link_to_report_spec("RSPEC-456")
        assert correction.linked_report_spec_id == "RSPEC-456"


class TestCorrectionSpecSerialization:
    """Test CorrectionSpec save/load"""

    def test_save_and_load(self):
        """Test saving to file and loading back"""
        original = CorrectionSpec(
            correction_id="CORRECT-TEST009",
            error_type=ErrorType.MISSING_EXPLANATION,
            wrong_output={"has_explanation": False},
            correct_output={"has_explanation": True, "text": "..."},
            human_reason="Anomaly requires explanation",
            metadata={"test": "serialization"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "correction.json"
            original.save(file_path)

            loaded = CorrectionSpec.load(file_path)

            assert loaded.correction_id == original.correction_id
            assert loaded.error_type == original.error_type
            assert loaded.wrong_output == original.wrong_output
            assert loaded.correct_output == original.correct_output
            assert loaded.human_reason == original.human_reason
            assert loaded.metadata["test"] == "serialization"

    def test_from_dict_roundtrip(self):
        """Test from_dict -> to_dict roundtrip"""
        original = CorrectionSpec(
            correction_id="CORRECT-TEST010",
            error_type=ErrorType.INCONSISTENT_DATA,
            wrong_output={"source1": 1.0, "source2": 2.0},
            correct_output={"source1": 1.5, "source2": 1.5},
            human_reason="Values should be consistent",
            evidence=["EVID-1"],
            impact_scope=ImpactScope.SIMILAR_CASES,
        )

        data = original.to_dict()
        restored = CorrectionSpec.from_dict(data)

        assert restored.correction_id == original.correction_id
        assert restored.error_type == original.error_type
        assert restored.impact_scope == original.impact_scope

    def test_from_json_roundtrip(self):
        """Test from_json -> to_json roundtrip"""
        original = CorrectionSpec(
            correction_id="CORRECT-TEST011",
            error_type=ErrorType.OTHER,
            wrong_output={"unknown": "issue"},
            correct_output={"unknown": "fixed"},
            human_reason="Custom fix",
        )

        json_str = original.to_json()
        restored = CorrectionSpec.from_json(json_str)

        assert restored.correction_id == original.correction_id
        assert restored.human_reason == original.human_reason


class TestCorrectionSpecIdGeneration:
    """Test CorrectionSpec ID generation"""

    def test_create_correction_id_format(self):
        """Generated IDs should follow CORRECT-XXX format"""
        id1 = create_correction_id()
        id2 = create_correction_id()

        assert id1.startswith("CORRECT-")
        assert id2.startswith("CORRECT-")
        assert id1 != id2  # Should be unique
        assert len(id1) == len("CORRECT-") + 12  # 12 hex chars


class TestCorrectionSpecScenarios:
    """Test real-world CorrectionSpec scenarios"""

    def test_wrong_plot_type_correction(self):
        """Scenario: Engineer changes plot type"""
        correction = CorrectionSpec(
            correction_id="CORRECT-SCENARIO001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={
                "plot_name": "pressure_field",
                "plot_type": "contour",
                "colormap": "jet",
            },
            correct_output={
                "plot_name": "pressure_field",
                "plot_type": "line",
                "location": "centerline",
            },
            human_reason="Line plot along centerline better shows pressure gradient",
            affected_components=["PlotSpec"],
            impact_scope=ImpactScope.SIMILAR_CASES,
            root_cause="Default plot type for pressure fields is contour",
            fix_action="For internal flow cases with centerline, default to line plot",
        )

        assert correction.error_type == ErrorType.WRONG_PLOT
        assert correction.affected_components == ["PlotSpec"]
        assert correction.impact_scope == ImpactScope.SIMILAR_CASES

    def test_missing_metric_correction(self):
        """Scenario: Engineer adds missing metric"""
        correction = CorrectionSpec(
            correction_id="CORRECT-SCENARIO002",
            error_type=ErrorType.MISSING_DATA,
            wrong_output={"metrics": ["drag_coefficient"]},
            correct_output={"metrics": ["drag_coefficient", "lift_coefficient"]},
            human_reason="Lift coefficient is essential for airfoil analysis",
            evidence=["EVID-AIRFOIL-001"],
            affected_components=["MetricSpec", "ReportSpec"],
            impact_scope=ImpactScope.REPORT_SPEC,
            root_cause="External flow template only included drag by default",
            fix_action="Add lift_coefficient to required_metrics for EXTERNAL_FLOW",
        )

        assert "lift_coefficient" in correction.correct_output["metrics"]
        assert correction.impact_scope == ImpactScope.REPORT_SPEC

    def test_invalid_order_correction(self):
        """Scenario: Engineer reorders report sections"""
        correction = CorrectionSpec(
            correction_id="CORRECT-SCENARIO003",
            error_type=ErrorType.INVALID_ORDER,
            wrong_output={"sections": ["plots", "metrics", "overview", "appendix"]},
            correct_output={"sections": ["overview", "plots", "metrics", "appendix"]},
            human_reason="Overview should come first to provide context",
            affected_components=["ReportSpec"],
            impact_scope=ImpactScope.ALL_CASES,
            fix_action="Standardize report order: overview -> plots -> metrics -> appendix",
        )

        assert correction.correct_output["sections"][0] == "overview"
        assert correction.impact_scope == ImpactScope.ALL_CASES


class TestCorrectionSpecReplayWorkflow:
    """Test CorrectionSpec replay validation workflow"""

    def test_pending_to_passed_workflow(self):
        """Test workflow from pending to passed"""
        correction = CorrectionSpec(
            correction_id="CORRECT-REPLAY001",
            error_type=ErrorType.WRONG_METRIC,
            wrong_output={"unit": "Pa"},
            correct_output={"unit": "mPa"},
            human_reason="Millipascal is more appropriate for this scale",
            needs_replay=True,
            replay_case_ids=["case_001", "case_002"],
        )

        assert correction.replay_status == "pending"
        assert correction.needs_replay is True

        # After successful replay
        correction.mark_replay_passed()
        assert correction.replay_status == "passed"

    def test_pending_to_failed_workflow(self):
        """Test workflow from pending to failed"""
        correction = CorrectionSpec(
            correction_id="CORRECT-REPLAY002",
            error_type=ErrorType.WRONG_SECTION,
            wrong_output={"z": 0.5},
            correct_output={"z": 0.1},
            human_reason="Section should be near wall",
            needs_replay=True,
            replay_case_ids=["case_003"],
        )

        # After failed replay
        correction.mark_replay_failed("Replay section still at z=0.5")
        assert correction.replay_status == "failed"
        assert "Replay section still at z=0.5" in correction.metadata["replay_failure_reason"]

    def test_skip_replay(self):
        """Test corrections that don't need replay"""
        correction = CorrectionSpec(
            correction_id="CORRECT-REPLAY003",
            error_type=ErrorType.DUPLICATE_CONTENT,
            wrong_output={"items": ["a", "a", "b"]},
            correct_output={"items": ["a", "b"]},
            human_reason="Duplicate removal",
            needs_replay=False,  # Simple duplicate fix, no replay needed
        )

        assert correction.needs_replay is False
        assert correction.replay_status == "pending"  # Still has default status


@pytest.mark.parametrize("error_type,expected_scope", [
    (ErrorType.WRONG_PLOT, ImpactScope.SIMILAR_CASES),
    (ErrorType.MISSING_COMPONENT, ImpactScope.REPORT_SPEC),
    (ErrorType.INVALID_ORDER, ImpactScope.ALL_CASES),
    (ErrorType.DUPLICATE_CONTENT, ImpactScope.SINGLE_CASE),
])
def test_error_type_to_impact_scope_mapping(error_type, expected_scope):
    """Test that certain error types map to expected impact scopes"""
    correction = CorrectionSpec(
        correction_id="CORRECT-MAP001",
        error_type=error_type,
        wrong_output={},
        correct_output={},
        human_reason="Test",
        impact_scope=expected_scope,
    )
    assert correction.impact_scope == expected_scope
