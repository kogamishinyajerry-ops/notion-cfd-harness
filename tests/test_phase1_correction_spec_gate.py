#!/usr/bin/env python3
"""
Tests for Phase 1 G2-P1: CorrectionSpec Completeness Gate

验证 CorrectionSpec 完整性 Gate 的功能：
- 9 个必填字段检查
- 字段值合法性验证
- 批量检查功能
- 边界情况处理
"""

import time

import pytest

from knowledge_compiler.phase1 import (
    CorrectionSpec,
    CorrectionSpecCompletenessGate,
    ErrorType,
    ImpactScope,
)
from knowledge_compiler.phase1.gates import GateStatus


class TestCorrectionSpecCompletenessGate:
    """Test CorrectionSpecCompletenessGate basic functionality"""

    def test_gate_creation(self):
        """Test creating the gate"""
        gate = CorrectionSpecCompletenessGate()
        assert gate.GATE_ID == "G2-P1"
        assert gate.GATE_NAME == "CorrectionSpec Completeness Gate"
        assert gate.strict_mode is True

    def test_gate_creation_non_strict(self):
        """Test creating gate in non-strict mode"""
        gate = CorrectionSpecCompletenessGate(strict_mode=False)
        assert gate.strict_mode is False


class TestCorrectionSpecValidation:
    """Test CorrectionSpec validation"""

    def test_valid_correction_spec_passes(self):
        """Test that a valid CorrectionSpec passes the gate"""
        gate = CorrectionSpecCompletenessGate()

        spec = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot_type": "contour"},
            correct_output={"plot_type": "vector"},
            human_reason="Vector plot is more appropriate",
            impact_scope=ImpactScope.SIMILAR_CASES,
            timestamp=time.time(),
            replay_status="pending",
        )

        # Add source_case_id via metadata (common pattern)
        spec_dict = spec.to_dict()
        spec_dict["source_case_id"] = "case-001"

        result = gate.check(spec_dict)

        assert result.is_pass()
        assert result.status == GateStatus.PASS
        assert result.severity == "BLOCK"
        assert len(result.errors) == 0

    def test_missing_required_field_fails(self):
        """Test that missing required fields cause failure"""
        gate = CorrectionSpecCompletenessGate()

        spec = {
            "correction_id": "CORRECT-001",
            # Missing error_type
            "wrong_output": {"plot": "contour"},
            "correct_output": {"plot": "vector"},
            "human_reason": "Test",
            "impact_scope": "SIMILAR_CASES",
            "timestamp": time.time(),
            "replay_status": "pending",
        }

        result = gate.check(spec)

        assert not result.is_pass()
        assert result.status == GateStatus.FAIL
        assert any("error_type" in e for e in result.errors)

    def test_missing_source_case_id_fails(self):
        """Test that missing source_case_id causes failure"""
        gate = CorrectionSpecCompletenessGate()

        spec = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot": "contour"},
            correct_output={"plot": "vector"},
            human_reason="Test",
            impact_scope=ImpactScope.SIMILAR_CASES,
            timestamp=time.time(),
            replay_status="pending",
        )

        result = gate.check(spec)

        assert not result.is_pass()
        assert any("source_case_id" in e for e in result.errors)

    def test_source_case_id_in_metadata_passes(self):
        """Test that source_case_id in metadata passes"""
        gate = CorrectionSpecCompletenessGate()

        spec = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot": "contour"},
            correct_output={"plot": "vector"},
            human_reason="Test",
            impact_scope=ImpactScope.SIMILAR_CASES,
            timestamp=time.time(),
            replay_status="pending",
        )

        # Add source_case_id to metadata
        spec_dict = spec.to_dict()
        spec_dict["source_case_id"] = "case-001"

        result = gate.check(spec_dict)

        assert result.is_pass()

    def test_invalid_replay_status_warns(self):
        """Test that invalid replay_status generates warning"""
        gate = CorrectionSpecCompletenessGate()

        spec = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot": "contour"},
            correct_output={"plot": "vector"},
            human_reason="Test",
            impact_scope=ImpactScope.SIMILAR_CASES,
            timestamp=time.time(),
            replay_status="invalid_status",  # Invalid
        )

        spec_dict = spec.to_dict()
        spec_dict["source_case_id"] = "case-001"

        result = gate.check(spec_dict)

        # Should pass or warn depending on implementation
        assert any("replay_status" in w for w in result.warnings)

    def test_identical_outputs_detected(self):
        """Test that identical wrong_output and correct_output is detected"""
        gate = CorrectionSpecCompletenessGate()

        same_output = {"plot": "contour", "field": "pressure"}

        spec = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output=same_output,
            correct_output=same_output,  # Identical!
            human_reason="Test",
            impact_scope=ImpactScope.SIMILAR_CASES,
            timestamp=time.time(),
            replay_status="pending",
        )

        spec_dict = spec.to_dict()
        spec_dict["source_case_id"] = "case-001"

        result = gate.check(spec_dict)

        # Should have a warning about identical outputs
        assert any("identical" in w.lower() or "same" in w.lower()
                   for w in result.warnings + result.errors)


class TestBatchValidation:
    """Test batch validation functionality"""

    def test_batch_all_pass(self):
        """Test batch validation with all valid specs"""
        gate = CorrectionSpecCompletenessGate()

        specs = []
        for i in range(5):
            spec = CorrectionSpec(
                correction_id=f"CORRECT-{i:03d}",
                error_type=ErrorType.WRONG_PLOT,
                wrong_output={"plot": "contour"},
                correct_output={"plot": "vector"},
                human_reason=f"Reason {i}",
                impact_scope=ImpactScope.SIMILAR_CASES,
                timestamp=time.time(),
                replay_status="pending",
            )
            spec_dict = spec.to_dict()
            spec_dict["source_case_id"] = f"case-{i:03d}"
            specs.append(spec_dict)

        result = gate.check_batch(specs)

        assert result.is_pass()
        assert result.metadata["total_checked"] == 5
        assert result.metadata["pass_count"] == 5
        assert result.metadata["fail_count"] == 0
        assert result.metadata["pass_rate"] == 100.0

    def test_batch_mixed_results(self):
        """Test batch validation with mixed pass/fail"""
        gate = CorrectionSpecCompletenessGate()

        specs = []

        # Valid spec
        valid_spec = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot": "contour"},
            correct_output={"plot": "vector"},
            human_reason="Test",
            impact_scope=ImpactScope.SIMILAR_CASES,
            timestamp=time.time(),
            replay_status="pending",
        )
        valid_dict = valid_spec.to_dict()
        valid_dict["source_case_id"] = "case-001"
        specs.append(valid_dict)

        # Invalid spec (missing error_type)
        invalid_spec = {
            "correction_id": "CORRECT-002",
            # Missing error_type
            "wrong_output": {"plot": "contour"},
            "correct_output": {"plot": "vector"},
            "human_reason": "Test",
            "impact_scope": "SIMILAR_CASES",
            "timestamp": time.time(),
            "replay_status": "pending",
        }
        specs.append(invalid_spec)

        result = gate.check_batch(specs)

        assert result.metadata["total_checked"] == 2
        assert result.metadata["pass_count"] == 1
        assert result.metadata["fail_count"] == 1
        assert result.metadata["pass_rate"] == 50.0

    def test_batch_empty_list(self):
        """Test batch validation with empty list"""
        gate = CorrectionSpecCompletenessGate()

        result = gate.check_batch([])

        # Empty batch should pass with 100% pass rate
        assert result.is_pass()
        assert result.metadata["total_checked"] == 0


class TestRequiredFields:
    """Test the 9 required fields validation"""

    def test_all_9_fields_checked(self):
        """Test that all 9 required fields are checked"""
        gate = CorrectionSpecCompletenessGate()

        assert len(gate.REQUIRED_FIELDS) == 9
        assert set(gate.REQUIRED_FIELDS) == {
            "correction_id",
            "error_type",
            "wrong_output",
            "correct_output",
            "human_reason",
            "impact_scope",
            "source_case_id",
            "timestamp",
            "replay_status",
        }

    def test_each_missing_field_causes_failure(self):
        """Test that each missing field causes appropriate failure"""
        gate = CorrectionSpecCompletenessGate()

        # Base valid spec
        base_spec_dict = {
            "correction_id": "CORRECT-001",
            "error_type": "WRONG_PLOT",
            "wrong_output": {"plot": "contour"},
            "correct_output": {"plot": "vector"},
            "human_reason": "Test",
            "impact_scope": "SIMILAR_CASES",
            "source_case_id": "case-001",
            "timestamp": time.time(),
            "replay_status": "pending",
        }

        # Test each field missing individually
        for field in gate.REQUIRED_FIELDS:
            spec_copy = base_spec_dict.copy()
            del spec_copy[field]

            result = gate.check(spec_copy)

            assert not result.is_pass(), f"Missing {field} should fail"
            assert any(field in e for e in result.errors)


class TestFieldValidation:
    """Test individual field validation"""

    def test_invalid_error_type_fails(self):
        """Test invalid error_type causes failure"""
        gate = CorrectionSpecCompletenessGate()

        spec = {
            "correction_id": "CORRECT-001",
            "error_type": "INVALID_ERROR_TYPE",  # Invalid
            "wrong_output": {"plot": "contour"},
            "correct_output": {"plot": "vector"},
            "human_reason": "Test",
            "impact_scope": "SIMILAR_CASES",
            "source_case_id": "case-001",
            "timestamp": time.time(),
            "replay_status": "pending",
        }

        result = gate.check(spec)

        assert not result.is_pass()
        assert any("error_type" in e for e in result.errors)

    def test_empty_output_fails(self):
        """Test empty wrong_output causes failure"""
        gate = CorrectionSpecCompletenessGate()

        spec = {
            "correction_id": "CORRECT-001",
            "error_type": "WRONG_PLOT",
            "wrong_output": {},  # Empty
            "correct_output": {"plot": "vector"},
            "human_reason": "Test",
            "impact_scope": "SIMILAR_CASES",
            "source_case_id": "case-001",
            "timestamp": time.time(),
            "replay_status": "pending",
        }

        result = gate.check(spec)

        assert not result.is_pass()
        assert any("wrong_output" in e for e in result.errors)

    def test_weak_human_reason_warns(self):
        """Test weak human_reason generates warning"""
        gate = CorrectionSpecCompletenessGate(strict_mode=False)

        spec = {
            "correction_id": "CORRECT-001",
            "error_type": "WRONG_PLOT",
            "wrong_output": {"plot": "contour"},
            "correct_output": {"plot": "vector"},
            "human_reason": "",  # Empty string
            "impact_scope": "SIMILAR_CASES",
            "source_case_id": "case-001",
            "timestamp": time.time(),
            "replay_status": "pending",
        }

        result = gate.check(spec)

        # Should pass with warning (non-strict mode)
        assert result.is_pass() or result.status == GateStatus.WARN
        assert any("human_reason" in w for w in result.warnings)


class TestGateMetadata:
    """Test gate result metadata"""

    def test_metadata_contains_correction_id(self):
        """Test that metadata includes correction_id"""
        gate = CorrectionSpecCompletenessGate()

        spec = CorrectionSpec(
            correction_id="TEST-123",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot": "contour"},
            correct_output={"plot": "vector"},
            human_reason="Test",
            impact_scope=ImpactScope.SIMILAR_CASES,
            timestamp=time.time(),
            replay_status="pending",
        )

        spec_dict = spec.to_dict()
        spec_dict["source_case_id"] = "case-001"

        result = gate.check(spec_dict)

        assert result.metadata["correction_id"] == "TEST-123"
        assert result.metadata["fields_checked"] == 9

    def test_severity_is_block(self):
        """Test that gate severity is BLOCK"""
        gate = CorrectionSpecCompletenessGate()

        spec = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot": "contour"},
            correct_output={"plot": "vector"},
            human_reason="Test",
            impact_scope=ImpactScope.SIMILAR_CASES,
            timestamp=time.time(),
            replay_status="pending",
        )

        spec_dict = spec.to_dict()
        spec_dict["source_case_id"] = "case-001"

        result = gate.check(spec_dict)

        assert result.severity == "BLOCK"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_spec_with_extra_fields_passes(self):
        """Test that spec with extra fields still passes"""
        gate = CorrectionSpecCompletenessGate()

        spec = {
            # Required fields
            "correction_id": "CORRECT-001",
            "error_type": "WRONG_PLOT",
            "wrong_output": {"plot": "contour"},
            "correct_output": {"plot": "vector"},
            "human_reason": "Test",
            "impact_scope": "SIMILAR_CASES",
            "source_case_id": "case-001",
            "timestamp": time.time(),
            "replay_status": "pending",
            # Extra fields
            "extra_field": "some value",
            "another_field": 12345,
        }

        result = gate.check(spec)

        assert result.is_pass()

    def test_non_dict_spec_handling(self):
        """Test handling of non-dict input"""
        gate = CorrectionSpecCompletenessGate()

        # Test with CorrectionSpec object
        spec = CorrectionSpec(
            correction_id="CORRECT-001",
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={"plot": "contour"},
            correct_output={"plot": "vector"},
            human_reason="Test",
            impact_scope=ImpactScope.SIMILAR_CASES,
            timestamp=time.time(),
            replay_status="pending",
        )

        # The gate should handle object or dict
        # For now, we convert to dict internally
        spec_dict = spec.to_dict()
        spec_dict["source_case_id"] = "case-001"

        result = gate.check(spec_dict)

        assert result.is_pass()

    def test_zero_timestamp(self):
        """Test handling of zero timestamp"""
        gate = CorrectionSpecCompletenessGate()

        spec = {
            "correction_id": "CORRECT-001",
            "error_type": "WRONG_PLOT",
            "wrong_output": {"plot": "contour"},
            "correct_output": {"plot": "vector"},
            "human_reason": "Test",
            "impact_scope": "SIMILAR_CASES",
            "source_case_id": "case-001",
            "timestamp": 0.0,  # Zero timestamp
            "replay_status": "pending",
        }

        result = gate.check(spec)

        # Zero timestamp is valid (edge case)
        assert result.is_pass()

    def test_all_valid_replay_statuses(self):
        """Test all valid replay_status values"""
        gate = CorrectionSpecCompletenessGate()

        valid_statuses = ["pending", "in_progress", "passed", "failed", "skipped"]

        for status in valid_statuses:
            spec = {
                "correction_id": f"CORRECT-{status}",
                "error_type": "WRONG_PLOT",
                "wrong_output": {"plot": "contour"},
                "correct_output": {"plot": "vector"},
                "human_reason": "Test",
                "impact_scope": "SIMILAR_CASES",
                "source_case_id": "case-001",
                "timestamp": time.time(),
                "replay_status": status,
            }

            result = gate.check(spec)
            assert result.is_pass(), f"Failed for status: {status}"
