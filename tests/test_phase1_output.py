#!/usr/bin/env python3
"""
Tests for Phase1Output Interface
Phase 1 → Phase 2 Aggregation Contract
"""

import json
import tempfile
from pathlib import Path

import pytest

from knowledge_compiler.phase1 import (
    Phase1Output,
    ReportSpec,
    CorrectionSpec,
    TeachRecord,
    TeachOperation,
    create_phase1_output_id,
    create_report_spec_id,
    create_correction_id,
    create_teach_record_id,
)
from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeLayer,
    KnowledgeStatus,
    ErrorType,
    ImpactScope,
    PlotSpec,
    MetricSpec,
    ComparisonType,
)


class TestPhase1OutputCreation:
    """Test Phase1Output creation"""

    def test_create_with_factory(self):
        """Test creating with factory function"""
        output_id = create_phase1_output_id()

        assert output_id.startswith("P1OUT-")
        assert len(output_id) == len("P1OUT-") + 12

    def test_create_output(self):
        """Test creating Phase1Output"""
        output = Phase1Output(
            output_id="P1OUT-TEST001",
            version="1.0",
        )

        assert output.output_id == "P1OUT-TEST001"
        assert output.version == "1.0"
        assert output.report_specs == []
        assert output.correction_specs == []
        assert output.teach_records == []


class TestPhase1OutputReportSpecs:
    """Test Phase1Output ReportSpec management"""

    def test_add_report_spec(self):
        """Test adding a ReportSpec"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        output.add_report_spec(spec)

        assert len(output.report_specs) == 1
        assert output.report_specs[0].report_spec_id == "RSPEC-001"

    def test_get_candidate_specs(self):
        """Test getting candidate specs"""
        output = Phase1Output(output_id="P1OUT-TEST001")

        # Add specs with different statuses
        draft_spec = ReportSpec(
            report_spec_id="RSPEC-DRAFT",
            name="Draft Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            knowledge_status=KnowledgeStatus.DRAFT,
        )
        candidate_spec = ReportSpec(
            report_spec_id="RSPEC-CANDIDATE",
            name="Candidate Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            knowledge_status=KnowledgeStatus.CANDIDATE,
        )
        approved_spec = ReportSpec(
            report_spec_id="RSPEC-APPROVED",
            name="Approved Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            knowledge_status=KnowledgeStatus.APPROVED,
        )

        output.add_report_spec(draft_spec)
        output.add_report_spec(candidate_spec)
        output.add_report_spec(approved_spec)

        # Get candidates - should return CANDIDATE and APPROVED
        candidates = output.get_candidate_specs()

        assert len(candidates) == 2
        assert any(s.report_spec_id == "RSPEC-CANDIDATE" for s in candidates)
        assert any(s.report_spec_id == "RSPEC-APPROVED" for s in candidates)


class TestPhase1OutputCorrectionSpecs:
    """Test Phase1Output CorrectionSpec management"""

    def test_add_correction_spec(self):
        """Test adding a CorrectionSpec"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        correction = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot_type": "contour"},
            correct_output={"plot_type": "vector"},
            human_reason="Vector plot is more appropriate",
        )

        output.add_correction_spec(correction)

        assert len(output.correction_specs) == 1
        assert output.correction_specs[0].correction_id == "CORRECT-001"

    def test_get_pending_corrections(self):
        """Test getting pending corrections"""
        output = Phase1Output(output_id="P1OUT-TEST001")

        # Add corrections with different statuses
        pending_correction = CorrectionSpec(
            correction_id="CORRECT-PENDING",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={},
            correct_output={},
            human_reason="Test",
            replay_status="pending",
        )
        passed_correction = CorrectionSpec(
            correction_id="CORRECT-PASSED",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={},
            correct_output={},
            human_reason="Test",
            replay_status="passed",
        )

        output.add_correction_spec(pending_correction)
        output.add_correction_spec(passed_correction)

        # Get pending - should only return pending
        pending = output.get_pending_corrections()

        assert len(pending) == 1
        assert pending[0].correction_id == "CORRECT-PENDING"


class TestPhase1OutputTeachRecords:
    """Test Phase1Output TeachRecord management"""

    def test_add_teach_record(self):
        """Test adding a TeachRecord"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        record = TeachRecord(
            teach_record_id="TEACH-001",
            case_id="case-001",
            timestamp=1234567890.0,
            operations=[],
        )

        output.add_teach_record(record)

        assert len(output.teach_records) == 1
        assert output.teach_records[0].teach_record_id == "TEACH-001"


class TestPhase1OutputGoldStandards:
    """Test Phase1Output Gold Standards management"""

    def test_add_gold_standard(self):
        """Test adding a gold standard"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        spec = ReportSpec(
            report_spec_id="GOLD-BACKWARD-STEP",
            name="Backward Facing Step",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        output.add_gold_standard("backward_facing_step", spec)

        assert "backward_facing_step" in output.gold_standards
        assert output.gold_standards["backward_facing_step"].report_spec_id == "GOLD-BACKWARD-STEP"


class TestPhase1OutputReplayResults:
    """Test Phase1Output Replay Results management"""

    def test_add_replay_result(self):
        """Test adding a replay result"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        result = {
            "case_id": "case-001",
            "passed": True,
            "details": "All checks passed",
        }

        output.add_replay_result(result)

        assert len(output.replay_results) == 1
        assert output.replay_results[0]["passed"] is True

    def test_calculate_replay_pass_rate(self):
        """Test calculating replay pass rate"""
        output = Phase1Output(output_id="P1OUT-TEST001")

        # Add results: 3 passed, 1 failed
        for i in range(3):
            output.add_replay_result({"case_id": f"case-{i}", "passed": True})
        output.add_replay_result({"case_id": "case-3", "passed": False})

        output.calculate_stats()

        assert output.stats["replay_pass_rate"] == 75.0


class TestPhase1OutputStatistics:
    """Test Phase1Output statistics calculation"""

    def test_calculate_stats_empty(self):
        """Test stats calculation with empty output"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        output.calculate_stats()

        assert output.stats["total_report_specs"] == 0
        assert output.stats["candidate_specs"] == 0
        assert output.stats["total_corrections"] == 0
        assert output.stats["replay_pass_rate"] == 0.0

    def test_calculate_stats_with_data(self):
        """Test stats calculation with data"""
        output = Phase1Output(output_id="P1OUT-TEST001")

        # Add a candidate spec
        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test",
            problem_type=ProblemType.INTERNAL_FLOW,
            knowledge_status=KnowledgeStatus.CANDIDATE,
        )
        output.add_report_spec(spec)

        # Add a pending correction
        correction = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={},
            correct_output={},
            human_reason="Test",
            replay_status="pending",
        )
        output.add_correction_spec(correction)

        # Add a teach record
        record = TeachRecord(
            teach_record_id="TEACH-001",
            case_id="case-001",
            timestamp=1234567890.0,
            operations=[],
        )
        output.add_teach_record(record)

        # Add a gold standard
        gold = ReportSpec(
            report_spec_id="GOLD-001",
            name="Gold",
            problem_type=ProblemType.INTERNAL_FLOW,
        )
        output.add_gold_standard("test_gold", gold)

        # Add replay results
        output.add_replay_result({"passed": True})
        output.add_replay_result({"passed": True})

        # Calculate stats
        output.calculate_stats()

        assert output.stats["total_report_specs"] == 1
        assert output.stats["candidate_specs"] == 1
        assert output.stats["total_corrections"] == 1
        assert output.stats["pending_corrections"] == 1
        assert output.stats["total_teach_records"] == 1
        assert output.stats["gold_standards"] == 1
        assert output.stats["replay_pass_rate"] == 100.0


class TestPhase1OutputSerialization:
    """Test Phase1Output serialization for Phase 2"""

    def test_to_dict(self):
        """Test converting to dictionary"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test",
            problem_type=ProblemType.INTERNAL_FLOW,
        )
        output.add_report_spec(spec)
        output.calculate_stats()

        data = output.to_dict()

        assert data["output_id"] == "P1OUT-TEST001"
        assert data["version"] == "1.0"
        assert "generated_at_iso" in data
        assert data["report_specs"][0]["spec_id"] == "RSPEC-001"
        assert data["stats"]["total_report_specs"] == 1

    def test_to_json(self):
        """Test converting to JSON"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        output.calculate_stats()

        json_str = output.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert data["output_id"] == "P1OUT-TEST001"

    def test_save_and_load(self):
        """Test saving to file and loading back"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Phase1Output(output_id="P1OUT-TEST001")
            spec = ReportSpec(
                report_spec_id="RSPEC-001",
                name="Test",
                problem_type=ProblemType.INTERNAL_FLOW,
            )
            output.add_report_spec(spec)
            output.calculate_stats()

            # Save
            file_path = Path(tmpdir) / "phase1_output.json"
            output.save(file_path)

            # Load
            loaded = Phase1Output.load(file_path)

            assert loaded.output_id == "P1OUT-TEST001"
            assert loaded.version == "1.0"
            assert loaded.stats["total_report_specs"] == 1

    def test_from_dict(self):
        """Test loading from dictionary"""
        data = {
            "output_id": "P1OUT-TEST001",
            "version": "1.0",
            "generated_at": 1234567890.0,
            "stats": {"total_report_specs": 5},
        }

        output = Phase1Output.from_dict(data)

        assert output.output_id == "P1OUT-TEST001"
        assert output.version == "1.0"
        assert output.stats["total_report_specs"] == 5


class TestPhase1OutputVisualization:
    """Test Phase1Output visualization outputs"""

    def test_add_visualization_output(self):
        """Test adding visualization output"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        vis_output = {
            "action_type": "generate_plot",
            "output_path": "/outputs/plot_001.png",
            "success": True,
        }

        output.add_visualization_output(vis_output)

        assert len(output.visualization_outputs) == 1
        assert output.visualization_outputs[0]["success"] is True


class TestPhase1OutputGateSummary:
    """Test Phase1Output gate summary"""

    def test_gate_summary(self):
        """Test gate summary tracking"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        output.gate_summary = {
            "G1-P1": {"status": "PASS", "checks": 5},
            "G3-P1": {"status": "WARN", "checks": 3},
            "G4-P1": {"status": "PASS", "checks": 4},
        }

        assert output.gate_summary["G1-P1"]["status"] == "PASS"
        assert len(output.gate_summary) == 3


class TestPhase1OutputContract:
    """Test Phase 1 → Phase 2 contract compliance"""

    def test_contract_contains_all_required_fields(self):
        """Test that Phase1Output contains all required fields for Phase 2"""
        output = Phase1Output(output_id="P1OUT-TEST001")

        # Required fields according to contract
        required_fields = [
            "output_id",
            "version",
            "generated_at",
            "report_specs",
            "correction_specs",
            "teach_records",
            "gold_standards",
            "replay_results",
            "visualization_outputs",
            "gate_summary",
            "stats",
        ]

        for field in required_fields:
            assert hasattr(output, field), f"Missing required field: {field}"

    def test_dict_format_for_phase2(self):
        """Test that to_dict() produces Phase 2 compatible format"""
        output = Phase1Output(output_id="P1OUT-TEST001")
        output.calculate_stats()

        data = output.to_dict()

        # Phase 2 requires these top-level fields
        required_phase2_fields = [
            "output_id",
            "version",
            "generated_at_iso",
            "report_specs",
            "correction_specs",
            "teach_records",
            "gold_standards",
            "stats",
        ]

        for field in required_phase2_fields:
            assert field in data, f"Missing Phase 2 field: {field}"

    def test_version_compatibility(self):
        """Test version format for backward compatibility"""
        output = Phase1Output(output_id="P1OUT-TEST001", version="1.0")

        # Version should follow semver-like format
        assert "." in output.version
        parts = output.version.split(".")
        assert len(parts) >= 2
        assert parts[0].isdigit()


class TestAnalogySpec:
    """Test AnalogySpec Phase 3 placeholder"""

    def test_create_analogy_spec(self):
        """Test creating AnalogySpec placeholder"""
        from knowledge_compiler.phase1.schema import AnalogySpec

        analogy = AnalogySpec(
            analogy_id="ANALOGY-001",
            source_case_id="case-001",
            target_case_id="case-002",
            similarity_score=0.85,
        )

        assert analogy.analogy_id == "ANALOGY-001"
        assert analogy.source_case_id == "case-001"
        assert analogy.target_case_id == "case-002"
        assert analogy.similarity_score == 0.85
        assert analogy.analogy_type is None  # Phase 3 placeholder

    def test_analogy_spec_to_dict(self):
        """Test AnalogySpec serialization"""
        from knowledge_compiler.phase1.schema import AnalogySpec

        analogy = AnalogySpec(
            analogy_id="ANALOGY-001",
            source_case_id="case-001",
            target_case_id="case-002",
            similarity_score=0.85,
        )

        data = analogy.to_dict()

        assert data["analogy_id"] == "ANALOGY-001"
        assert "source_case_id" in data
        assert "target_case_id" in data


class TestPhase1OutputIntegration:
    """Integration tests for Phase1Output"""

    def test_full_phase1_output_workflow(self):
        """Test creating a complete Phase1Output"""
        output = Phase1Output(
            output_id=create_phase1_output_id(),
            version="1.0",
        )

        # Add a ReportSpec
        spec = ReportSpec(
            report_spec_id=create_report_spec_id(),
            name="Backward Facing Step",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[
                PlotSpec(name="velocity_contour", plane="domain", colormap="viridis", range="auto")
            ],
            required_metrics=[
                MetricSpec(name="reattachment_length", unit="-", comparison=ComparisonType.DIRECT)
            ],
            knowledge_layer=KnowledgeLayer.CANONICAL,
            knowledge_status=KnowledgeStatus.CANDIDATE,
        )
        output.add_report_spec(spec)
        output.add_gold_standard("backward_facing_step", spec)

        # Add a TeachRecord
        record = TeachRecord(
            teach_record_id=create_teach_record_id(),
            case_id="backward-step-001",
            timestamp=1234567890.0,
            operations=[
                TeachOperation(
                    operation_type="add_plot",
                    description="Add vorticity contour plot",
                    reason="Better visualize rotation",
                    is_generalizable=True,
                )
            ],
        )
        output.add_teach_record(record)

        # Add a CorrectionSpec
        correction = CorrectionSpec(
            correction_id=create_correction_id(),
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot": "velocity_contour"},
            correct_output={"plot": "vorticity_contour"},
            human_reason="Vorticity is more important for this case",
            impact_scope=ImpactScope.SIMILAR_CASES,
            replay_status="passed",
        )
        output.add_correction_spec(correction)

        # Add replay results
        output.add_replay_result({"case_id": "case-001", "passed": True})
        output.add_replay_result({"case_id": "case-002", "passed": True})

        # Add visualization output
        output.add_visualization_output({
            "action": "generate_plot",
            "file": "/outputs/plot.png",
        })

        # Add gate summary
        output.gate_summary = {
            "G1-P1": {"status": "PASS"},
            "G3-P1": {"status": "PASS"},
            "G4-P1": {"status": "PASS"},
        }

        # Calculate stats
        output.calculate_stats()

        # Verify
        assert output.stats["total_report_specs"] == 1
        assert output.stats["candidate_specs"] == 1
        assert output.stats["total_corrections"] == 1
        assert output.stats["pending_corrections"] == 0  # replay_status=passed
        assert output.stats["total_teach_records"] == 1
        assert output.stats["gold_standards"] == 1
        assert output.stats["replay_pass_rate"] == 100.0

        # Test serialization
        json_str = output.to_json()
        data = json.loads(json_str)

        assert data["stats"]["candidate_specs"] == 1
        assert data["gate_summary"]["G1-P1"]["status"] == "PASS"
