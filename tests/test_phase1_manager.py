#!/usr/bin/env python3
"""
Phase 1 Module 4: ReportSpec Manager tests
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeLayer,
    KnowledgeStatus,
    PlotSpec,
    MetricSpec,
    ComparisonType,
)
from knowledge_compiler.phase1.manager import (
    ValidationResult,
    PromotionResult,
    ReportSpecManager,
    create_report_spec,
)


class TestReportSpecManager:
    def test_manager_creation(self):
        """ReportSpecManager should initialize"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            assert manager.storage_path == Path(tmpdir)
            assert len(manager._index) == 0

    def test_create_spec(self):
        """Manager should create ReportSpec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create(
                name="Test Spec",
                problem_type=ProblemType.INTERNAL_FLOW,
            )

            assert spec.name == "Test Spec"
            assert spec.problem_type == ProblemType.INTERNAL_FLOW
            assert spec.knowledge_layer == KnowledgeLayer.RAW
            assert spec.knowledge_status == KnowledgeStatus.DRAFT
            assert spec.report_spec_id in manager._index

    def test_create_spec_with_plots_metrics(self):
        """Manager should create ReportSpec with plots and metrics"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            plots = [
                PlotSpec(name="velocity", plane="xy", colormap="viridis", range="auto"),
            ]
            metrics = [
                MetricSpec(name="drag", unit="N", comparison=ComparisonType.DIRECT),
            ]

            spec = manager.create(
                name="Test Spec",
                problem_type=ProblemType.EXTERNAL_FLOW,
                required_plots=plots,
                required_metrics=metrics,
            )

            assert len(spec.required_plots) == 1
            assert len(spec.required_metrics) == 1
            assert spec.required_plots[0].name == "velocity"

    def test_get_spec(self):
        """Manager should retrieve ReportSpec by ID"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            created = manager.create(
                name="Test Spec",
                problem_type=ProblemType.INTERNAL_FLOW,
            )

            retrieved = manager.get(created.report_spec_id)

            assert retrieved is not None
            assert retrieved.report_spec_id == created.report_spec_id
            assert retrieved.name == "Test Spec"

    def test_get_nonexistent_spec(self):
        """Manager should return None for nonexistent spec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            retrieved = manager.get("NONEXISTENT")

            assert retrieved is None

    def test_list_specs(self):
        """Manager should list all specs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            manager.create("Spec 1", ProblemType.INTERNAL_FLOW)
            manager.create("Spec 2", ProblemType.EXTERNAL_FLOW)
            manager.create("Spec 3", ProblemType.HEAT_TRANSFER)

            all_specs = manager.list()

            assert len(all_specs) == 3

    def test_list_specs_filtered_by_problem_type(self):
        """Manager should filter by problem type"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            manager.create("Spec 1", ProblemType.INTERNAL_FLOW)
            manager.create("Spec 2", ProblemType.EXTERNAL_FLOW)
            manager.create("Spec 3", ProblemType.INTERNAL_FLOW)

            internal_specs = manager.list(problem_type=ProblemType.INTERNAL_FLOW)

            assert len(internal_specs) == 2

    def test_list_specs_filtered_by_status(self):
        """Manager should filter by status"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec1 = manager.create("Spec 1", ProblemType.INTERNAL_FLOW)
            spec2 = manager.create("Spec 2", ProblemType.INTERNAL_FLOW)

            # Promote one to candidate (without validation for this test)
            manager.promote(spec1.report_spec_id, KnowledgeStatus.CANDIDATE, validate=False)

            draft_specs = manager.list(knowledge_status=KnowledgeStatus.DRAFT)
            candidate_specs = manager.list(knowledge_status=KnowledgeStatus.CANDIDATE)

            assert len(draft_specs) == 1
            assert len(candidate_specs) == 1

    def test_update_spec(self):
        """Manager should update ReportSpec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create("Original Name", ProblemType.INTERNAL_FLOW)
            spec.name = "Updated Name"

            updated = manager.update(spec)

            assert updated.name == "Updated Name"
            retrieved = manager.get(spec.report_spec_id)
            assert retrieved.name == "Updated Name"

    def test_update_nonexistent_spec(self):
        """Manager should raise error for nonexistent spec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            from knowledge_compiler.phase1.schema import ReportSpec

            fake_spec = ReportSpec(
                report_spec_id="FAKE",
                name="Fake",
                problem_type=ProblemType.INTERNAL_FLOW,
            )

            try:
                manager.update(fake_spec)
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "not found" in str(e)

    def test_delete_spec(self):
        """Manager should delete ReportSpec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create("To Delete", ProblemType.INTERNAL_FLOW)

            assert manager.get(spec.report_spec_id) is not None

            result = manager.delete(spec.report_spec_id)

            assert result is True
            assert manager.get(spec.report_spec_id) is None

    def test_delete_nonexistent_spec(self):
        """Manager should return False for nonexistent spec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            result = manager.delete("NONEXISTENT")

            assert result is False

    def test_promote_to_candidate(self):
        """Manager should promote draft to candidate"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create(
                "Test Spec",
                ProblemType.INTERNAL_FLOW,
                required_plots=[PlotSpec(name="v", plane="xy", colormap="viridis", range="auto")],
            )

            result = manager.promote(spec.report_spec_id, KnowledgeStatus.CANDIDATE)

            assert result.success is True
            assert result.from_status == KnowledgeStatus.DRAFT
            assert result.to_status == KnowledgeStatus.CANDIDATE

            updated = manager.get(spec.report_spec_id)
            assert updated.knowledge_status == KnowledgeStatus.CANDIDATE

    def test_promote_without_validation(self):
        """Manager should promote without validation when requested"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create("Empty Spec", ProblemType.INTERNAL_FLOW)

            # Even empty spec can be promoted without validation
            result = manager.promote(
                spec.report_spec_id,
                KnowledgeStatus.CANDIDATE,
                validate=False,
            )

            assert result.success is True

    def test_promote_with_validation_failure(self):
        """Manager should reject promotion when validation fails"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            # Create empty spec (will fail validation for candidate)
            spec = manager.create("Empty Spec", ProblemType.INTERNAL_FLOW)

            result = manager.promote(
                spec.report_spec_id,
                KnowledgeStatus.CANDIDATE,
                validate=True,
            )

            assert result.success is False
            assert "Validation failed" in result.message
            assert result.validation_result is not None
            assert not result.validation_result.is_valid

    def test_promote_to_approved_requires_replay_rate(self):
        """Manager should require 70% replay rate for approval"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create(
                "Test Spec",
                ProblemType.INTERNAL_FLOW,
                required_plots=[PlotSpec(name="v", plane="xy", colormap="viridis", range="auto")],
            )
            # First promote to candidate
            manager.promote(spec.report_spec_id, KnowledgeStatus.CANDIDATE)

            # Try to approve without replay rate
            result = manager.promote(spec.report_spec_id, KnowledgeStatus.APPROVED)

            assert result.success is False
            assert "70%" in result.message

    def test_promote_to_approved_with_sufficient_replay(self):
        """Manager should approve with sufficient replay rate"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create(
                "Test Spec",
                ProblemType.INTERNAL_FLOW,
                required_plots=[PlotSpec(name="v", plane="xy", colormap="viridis", range="auto")],
            )
            manager.promote(spec.report_spec_id, KnowledgeStatus.CANDIDATE)

            # Set replay rate to 75%
            manager.update_replay_pass_rate(spec.report_spec_id, [True, True, True, False])

            # Now should approve
            result = manager.promote(spec.report_spec_id, KnowledgeStatus.APPROVED)

            assert result.success is True

    def test_find_best_match(self):
        """Manager should find best matching spec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            # Create specs at different layers
            raw_spec = manager.create("Raw", ProblemType.INTERNAL_FLOW)
            manager.promote(raw_spec.report_spec_id, KnowledgeStatus.CANDIDATE)

            parsed_spec = manager.create("Parsed", ProblemType.INTERNAL_FLOW)
            parsed_spec.knowledge_layer = KnowledgeLayer.PARSED
            manager.update(parsed_spec)

            # Find best match (should prefer Parsed over Raw)
            best = manager.find_best_match(ProblemType.INTERNAL_FLOW)

            assert best is not None
            assert best.report_spec_id == parsed_spec.report_spec_id

    def test_find_best_match_with_status_priority(self):
        """Manager should prefer Approved over Candidate"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec1 = manager.create("Candidate", ProblemType.INTERNAL_FLOW)
            manager.promote(spec1.report_spec_id, KnowledgeStatus.CANDIDATE)

            spec2 = manager.create("Approved", ProblemType.INTERNAL_FLOW)
            manager.promote(spec2.report_spec_id, KnowledgeStatus.CANDIDATE)
            manager.update_replay_pass_rate(spec2.report_spec_id, [True, True, True])
            manager.promote(spec2.report_spec_id, KnowledgeStatus.APPROVED)

            best = manager.find_best_match(ProblemType.INTERNAL_FLOW)

            assert best.report_spec_id == spec2.report_spec_id

    def test_update_replay_pass_rate(self):
        """Manager should update replay pass rate"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create("Test", ProblemType.INTERNAL_FLOW)

            updated = manager.update_replay_pass_rate(
                spec.report_spec_id,
                [True, True, False, True],
            )

            assert updated.replay_pass_rate == 75.0

    def test_add_teach_record(self):
        """Manager should link teach record to spec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create("Test", ProblemType.INTERNAL_FLOW)

            updated = manager.add_teach_record(spec.report_spec_id, "TEACH-001")

            assert "TEACH-001" in updated.teach_records

    def test_add_source_case(self):
        """Manager should link source case to spec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = manager.create("Test", ProblemType.INTERNAL_FLOW)

            updated = manager.add_source_case(spec.report_spec_id, "CASE-001")

            assert "CASE-001" in updated.source_cases

    def test_batch_promote_to_approved(self):
        """Manager should batch promote specs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec1 = manager.create("Spec 1", ProblemType.INTERNAL_FLOW)
            spec2 = manager.create("Spec 2", ProblemType.INTERNAL_FLOW)

            # Set up for approval
            for spec_id in [spec1.report_spec_id, spec2.report_spec_id]:
                manager.promote(spec_id, KnowledgeStatus.CANDIDATE)
                manager.update_replay_pass_rate(spec_id, [True, True, True])

            results = manager.promote_to_approved([spec1.report_spec_id, spec2.report_spec_id])

            assert len(results) == 2
            assert results[spec1.report_spec_id].success is True
            assert results[spec2.report_spec_id].success is True

    def test_validate_all(self):
        """Manager should validate all specs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            manager.create("Spec 1", ProblemType.INTERNAL_FLOW)
            manager.create("Spec 2", ProblemType.EXTERNAL_FLOW)

            results = manager.validate_all()

            assert len(results) == 2
            assert all(isinstance(r, ValidationResult) for r in results.values())


class TestConvenienceFunctions:
    def test_create_report_spec(self):
        """Convenience function should create ReportSpec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec = create_report_spec(
                name="Test",
                problem_type=ProblemType.INTERNAL_FLOW,
                plots=[
                    {"name": "velocity", "plane": "xy", "colormap": "viridis", "range": "auto"},
                ],
                metrics=[
                    {"name": "drag", "unit": "N", "comparison": "direct"},
                ],
                storage_path=Path(tmpdir),
            )

            assert spec.name == "Test"
            assert len(spec.required_plots) == 1
            assert len(spec.required_metrics) == 1

    def test_create_report_spec_with_manager(self):
        """Convenience function should use existing manager"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ReportSpecManager(storage_path=Path(tmpdir))

            spec = create_report_spec(
                name="Test",
                problem_type=ProblemType.INTERNAL_FLOW,
                manager=manager,
            )

            assert spec.report_spec_id in manager._index


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
