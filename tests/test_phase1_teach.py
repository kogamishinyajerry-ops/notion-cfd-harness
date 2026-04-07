#!/usr/bin/env python3
"""
Phase 1 Module 3: Teach Mode Engine tests
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeLayer,
    KnowledgeStatus,
    ComparisonType,
    ReportDraft,
    TeachRecord,
    ReportSpec,
)
from knowledge_compiler.phase1.teach import (
    OperationType,
    TeachContext,
    TeachResponse,
    EvidenceReference,
    TeachModeEngine,
    record_teach_operation,
)


class TestTeachModeEngine:
    def test_engine_creation(self):
        """TeachModeEngine should initialize"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            assert engine.storage_path == Path(tmpdir)
            assert engine._active_session is None
            assert engine._session_records == []

    def test_start_session(self):
        """Engine should start a new session"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            session_id = engine.start_session()

            assert session_id.startswith("SESSION-")
            assert engine._active_session == session_id
            assert engine._session_records == []

    def test_start_session_with_custom_id(self):
        """Engine should support custom session IDs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            session_id = engine.start_session("CUSTOM-SESSION")

            assert session_id == "CUSTOM-SESSION"

    def test_end_session(self):
        """Engine should end session and return records"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))
            engine.start_session("TEST-SESSION")

            # Record something
            context = TeachContext(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                timestamp=time.time(),
                previous_state={},
                operation_type="add_plot",
            )

            response = engine.record_operation(
                context=context,
                description="Add velocity plot",
                reason="Shows vortex formation",
                is_generalizable=True,
            )

            records = engine.end_session()

            assert len(records) == 1
            assert response.teach_record_id in records
            assert engine._active_session is None

    def test_record_operation(self):
        """Engine should record teach operation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            context = TeachContext(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                timestamp=time.time(),
                previous_state={},
                operation_type="add_plot",
            )

            response = engine.record_operation(
                context=context,
                description="Add velocity plot",
                reason="Shows vortex formation",
                is_generalizable=True,
            )

            assert response.success is True
            assert response.teach_record_id.startswith("TEACH-")
            assert response.generalizable is True

            # Check file was created
            file_path = engine.storage_path / f"{response.teach_record_id}.json"
            assert file_path.exists()

    def test_record_invalid_operation(self):
        """Engine should reject invalid operation types"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            context = TeachContext(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                timestamp=time.time(),
                previous_state={},
                operation_type="invalid_op",  # Invalid
            )

            response = engine.record_operation(
                context=context,
                description="Test",
                reason="Test",
                is_generalizable=False,
            )

            assert response.success is False
            assert "Invalid operation type" in response.message

    def test_load_record(self):
        """Engine should load saved record"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            context = TeachContext(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                timestamp=time.time(),
                previous_state={},
                operation_type="add_plot",
            )

            response = engine.record_operation(
                context=context,
                description="Add velocity plot",
                reason="Shows vortex formation",
                is_generalizable=True,
            )

            # Load the record
            loaded = engine.load_record(response.teach_record_id)

            assert loaded is not None
            assert loaded.teach_record_id == response.teach_record_id
            assert loaded.case_id == "CASE-001"
            assert len(loaded.operations) == 1

    def test_load_nonexistent_record(self):
        """Engine should return None for nonexistent record"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            loaded = engine.load_record("TEACH-NONEXISTENT")

            assert loaded is None

    def test_list_records(self):
        """Engine should list all records"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            # Create multiple records
            for i in range(3):
                context = TeachContext(
                    draft_id=f"DRAFT-{i:03d}",
                    case_id="CASE-001",
                    timestamp=time.time(),
                    previous_state={},
                    operation_type="add_plot",
                )

                engine.record_operation(
                    context=context,
                    description=f"Plot {i}",
                    reason="Test",
                    is_generalizable=True,
                )

            records = engine.list_records()

            assert len(records) == 3

    def test_list_records_filtered_by_case(self):
        """Engine should filter records by case ID"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            # Create records for different cases
            for case_id in ["CASE-001", "CASE-002"]:
                context = TeachContext(
                    draft_id="DRAFT-001",
                    case_id=case_id,
                    timestamp=time.time(),
                    previous_state={},
                    operation_type="add_plot",
                )

                engine.record_operation(
                    context=context,
                    description="Test plot",
                    reason="Test",
                    is_generalizable=True,
                )

            # Filter by case
            records = engine.list_records(case_id="CASE-001")

            assert len(records) == 1
            assert records[0].case_id == "CASE-001"

    def test_list_records_filtered_by_session(self):
        """Engine should filter records by session ID"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            # Record in session 1
            engine.start_session("SESSION-1")
            context1 = TeachContext(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                timestamp=time.time(),
                previous_state={},
                operation_type="add_plot",
                session_id="SESSION-1",
            )
            engine.record_operation(
                context=context1,
                description="Plot 1",
                reason="Test",
                is_generalizable=True,
            )
            engine.end_session()

            # Record in session 2
            engine.start_session("SESSION-2")
            context2 = TeachContext(
                draft_id="DRAFT-002",
                case_id="CASE-001",
                timestamp=time.time(),
                previous_state={},
                operation_type="add_metric",
                session_id="SESSION-2",
            )
            engine.record_operation(
                context=context2,
                description="Metric 1",
                reason="Test",
                is_generalizable=True,
            )
            engine.end_session()

            # Filter by session
            records = engine.list_records(session_id="SESSION-1")

            assert len(records) == 1
            assert records[0].operations[0].operation_type == "add_plot"


class TestApplyOperations:
    def test_apply_add_plot(self):
        """Engine should apply add_plot to draft"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            draft = ReportDraft(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                task_spec_id="TASK-001",
                plots=[],
            )

            from knowledge_compiler.phase1.schema import TeachOperation

            operation = TeachOperation(
                operation_type="add_plot",
                description="Add velocity plot",
                reason="Shows vortex",
                is_generalizable=True,
                metadata={
                    "plot_spec": {
                        "name": "velocity_magnitude",
                        "plane": "xy",
                        "colormap": "viridis",
                        "range": "auto",
                    }
                },
            )

            modified = engine.apply_to_draft(draft, operation)

            assert len(modified.plots) == 1
            assert modified.plots[0]["name"] == "velocity_magnitude"

    def test_apply_remove_plot(self):
        """Engine should apply remove_plot to draft"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            draft = ReportDraft(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                task_spec_id="TASK-001",
                plots=[
                    {"name": "velocity", "plane": "xy", "colormap": "viridis", "range": "auto"},
                    {"name": "pressure", "plane": "xy", "colormap": "coolwarm", "range": "auto"},
                ],
            )

            from knowledge_compiler.phase1.schema import TeachOperation

            operation = TeachOperation(
                operation_type="remove_plot",
                description="Remove pressure plot",
                reason="Not needed",
                is_generalizable=False,
                metadata={"plot_name": "pressure"},
            )

            modified = engine.apply_to_draft(draft, operation)

            assert len(modified.plots) == 1
            assert modified.plots[0]["name"] == "velocity"

    def test_apply_modify_plot(self):
        """Engine should apply modify_plot to draft"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            draft = ReportDraft(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                task_spec_id="TASK-001",
                plots=[
                    {"name": "velocity", "plane": "xy", "colormap": "viridis", "range": "auto"},
                ],
            )

            from knowledge_compiler.phase1.schema import TeachOperation

            operation = TeachOperation(
                operation_type="modify_plot",
                description="Change colormap",
                reason="Better contrast",
                is_generalizable=True,
                metadata={
                    "plot_name": "velocity",
                    "modifications": {"colormap": "coolwarm"},
                },
            )

            modified = engine.apply_to_draft(draft, operation)

            assert modified.plots[0]["colormap"] == "coolwarm"

    def test_apply_add_metric(self):
        """Engine should apply add_metric to draft"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            draft = ReportDraft(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                task_spec_id="TASK-001",
                metrics=[],
            )

            from knowledge_compiler.phase1.schema import TeachOperation

            operation = TeachOperation(
                operation_type="add_metric",
                description="Add drag coefficient",
                reason="Required for validation",
                is_generalizable=True,
                metadata={
                    "metric_spec": {
                        "name": "drag_coefficient",
                        "unit": "-",
                        "comparison": "ratio",
                    }
                },
            )

            modified = engine.apply_to_draft(draft, operation)

            assert len(modified.metrics) == 1
            assert modified.metrics[0]["name"] == "drag_coefficient"

    def test_apply_remove_metric(self):
        """Engine should apply remove_metric to draft"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            draft = ReportDraft(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                task_spec_id="TASK-001",
                metrics=[
                    {"name": "drag", "unit": "N", "comparison": "direct"},
                    {"name": "lift", "unit": "N", "comparison": "direct"},
                ],
            )

            from knowledge_compiler.phase1.schema import TeachOperation

            operation = TeachOperation(
                operation_type="remove_metric",
                description="Remove lift metric",
                reason="Not needed",
                is_generalizable=False,
                metadata={"metric_name": "lift"},
            )

            modified = engine.apply_to_draft(draft, operation)

            assert len(modified.metrics) == 1
            assert modified.metrics[0]["name"] == "drag"

    def test_apply_modify_metric(self):
        """Engine should apply modify_metric to draft"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            draft = ReportDraft(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                task_spec_id="TASK-001",
                metrics=[
                    {"name": "drag", "unit": "N", "comparison": "direct"},
                ],
            )

            from knowledge_compiler.phase1.schema import TeachOperation

            operation = TeachOperation(
                operation_type="modify_metric",
                description="Change to coefficient",
                reason="Dimensionless is better",
                is_generalizable=True,
                metadata={
                    "metric_name": "drag",
                    "modifications": {"unit": "-", "comparison": "ratio"},
                },
            )

            modified = engine.apply_to_draft(draft, operation)

            assert modified.metrics[0]["unit"] == "-"

    def test_apply_add_explanation(self):
        """Engine should apply add_explanation to draft"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            draft = ReportDraft(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                task_spec_id="TASK-001",
                structure={},
            )

            from knowledge_compiler.phase1.schema import TeachOperation

            operation = TeachOperation(
                operation_type="add_explanation",
                description="Explain vortex formation",
                reason="Helps reader understand physics",
                is_generalizable=True,
            )

            modified = engine.apply_to_draft(draft, operation)

            assert "explanations" in modified.structure
            assert len(modified.structure["explanations"]) == 1

    def test_apply_modify_structure(self):
        """Engine should apply modify_structure to draft"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            draft = ReportDraft(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                task_spec_id="TASK-001",
                structure={"title": "Test Report"},
            )

            from knowledge_compiler.phase1.schema import TeachOperation

            operation = TeachOperation(
                operation_type="modify_structure",
                description="Update title",
                reason="Better description",
                is_generalizable=False,
                metadata={
                    "structure_changes": {"title": "Updated Test Report"},
                },
            )

            modified = engine.apply_to_draft(draft, operation)

            assert modified.structure["title"] == "Updated Test Report"


class TestPromotion:
    def test_promote_to_report_spec(self):
        """Engine should promote generalizable operations to ReportSpec"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TeachModeEngine(storage_path=Path(tmpdir))

            # Create teach records
            records = []

            for i in range(2):
                context = TeachContext(
                    draft_id="DRAFT-001",
                    case_id="CASE-001",
                    timestamp=time.time(),
                    previous_state={},
                    operation_type="add_plot",
                )

                response = engine.record_operation(
                    context=context,
                    description=f"Add plot {i}",
                    reason="Test",
                    is_generalizable=True,
                    metadata={
                        "plot_spec": {
                            "name": f"plot_{i}",
                            "plane": "xy",
                            "colormap": "viridis",
                            "range": "auto",
                        }
                    },
                )

                record = engine.load_record(response.teach_record_id)
                records.append(record)

            # Add a non-generalizable record (should be ignored)
            context = TeachContext(
                draft_id="DRAFT-001",
                case_id="CASE-001",
                timestamp=time.time(),
                previous_state={},
                operation_type="add_plot",
            )

            response = engine.record_operation(
                context=context,
                description="Non-generalizable plot",
                reason="Case-specific",
                is_generalizable=False,
            )
            records.append(engine.load_record(response.teach_record_id))

            # Promote
            spec = engine.promote_to_report_spec(
                teach_records=records,
                name="Test Spec",
                problem_type=ProblemType.INTERNAL_FLOW,
            )

            assert spec.name == "Test Spec"
            assert spec.problem_type == ProblemType.INTERNAL_FLOW
            assert spec.knowledge_layer == KnowledgeLayer.PARSED
            assert spec.knowledge_status == KnowledgeStatus.CANDIDATE
            # Only 2 generalizable plots should be included
            assert len(spec.required_plots) == 2
            # All 3 records should be tracked
            assert len(spec.teach_records) == 3


class TestConvenienceFunctions:
    def test_record_teach_operation(self):
        """Convenience function should record operation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            response = record_teach_operation(
                case_id="CASE-001",
                draft_id="DRAFT-001",
                operation_type="add_plot",
                description="Test plot",
                reason="Testing",
                is_generalizable=False,
                storage_path=Path(tmpdir),
            )

            assert response.success is True
            assert response.teach_record_id.startswith("TEACH-")


class TestEvidenceReference:
    def test_evidence_reference_creation(self):
        """EvidenceReference should initialize"""
        evidence = EvidenceReference(
            evidence_type="experimental",
            source_id="doi:10.1234/test",
            description="Experimental validation",
            confidence=0.95,
        )

        assert evidence.evidence_type == "experimental"
        assert evidence.confidence == 0.95


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
