#!/usr/bin/env python3
"""
Phase 2 Gates Tests

测试 Phase 2 的所有 Gate 实现。
"""

import time

import pytest

from knowledge_compiler.phase2.schema import (
    SpecType,
    CanonicalSpec,
    KnowledgeStatus,
    KnowledgeLayer,
)
from knowledge_compiler.phase2.gates import (
    # Base
    GateStatus,
    # G1-P2
    KnowledgeCompletenessGate,
    G1_P2_GATE_ID,
    # G2-P2
    AuthorizationGate,
    G2_P2_GATE_ID,
    AuthStatus,
)


class TestKnowledgeCompletenessGate:
    """Test G1-P2: Knowledge Completeness Gate"""

    def test_gate_id(self):
        """Test gate ID is correct"""
        gate = KnowledgeCompletenessGate()
        assert gate.GATE_ID == G1_P2_GATE_ID
        assert gate.GATE_ID == "G1-P2"
        assert gate.GATE_NAME == "Knowledge Completeness Gate"

    def test_missing_spec_type(self):
        """Test spec without spec_type fails"""
        gate = KnowledgeCompletenessGate()

        # Create a mock spec without spec_type
        class MockSpec:
            pass

        spec = MockSpec()
        result = gate.check(spec)

        assert result.status == GateStatus.FAIL
        assert result.score == 0.0
        assert "spec_type is missing" in result.errors

    def test_report_spec_all_fields_present(self):
        """Test report_spec with all required fields passes"""
        gate = KnowledgeCompletenessGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={
                "name": "Internal Flow Report",
                "problem_type": "internal_flow",
                "required_plots": ["velocity_contour"],
                "required_metrics": ["pressure_drop"],
            },
        )

        result = gate.check(spec)

        assert result.is_pass()
        assert result.score == 100.0
        assert len(result.errors) == 0

    def test_report_spec_missing_fields(self):
        """Test report_spec with missing fields fails"""
        gate = KnowledgeCompletenessGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={
                "name": "Internal Flow Report",
                # Missing problem_type, required_plots, required_metrics
            },
        )

        result = gate.check(spec)

        assert result.status == GateStatus.FAIL
        # Score starts at 100, -12.5 for each of 3 missing fields = 62.5
        assert result.score < 75.0
        assert len(result.errors) == 3

    def test_plot_standard_validation(self):
        """Test plot_standard field validation"""
        gate = KnowledgeCompletenessGate()

        # Valid plot_standard
        spec = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={
                "plot_type": "contour",
                "field": "velocity",
                "colormap": "viridis",
                "plane": "xy",
            },
        )

        result = gate.check(spec)
        assert result.is_pass()

        # Missing required field
        spec2 = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={
                "plot_type": "contour",
                "field": "velocity",
                # Missing colormap, plane
            },
        )

        result2 = gate.check(spec2)
        assert result2.status == GateStatus.FAIL

    def test_metric_standard_validation(self):
        """Test metric_standard field validation"""
        gate = KnowledgeCompletenessGate()

        spec = CanonicalSpec(
            spec_type=SpecType.METRIC_STANDARD,
            content={
                "metric_name": "pressure_drop",
                "unit": "Pa",
                "calculation_method": "inlet_outlet_difference",
            },
        )

        result = gate.check(spec)
        assert result.is_pass()

    def test_section_rule_validation(self):
        """Test section_rule field validation"""
        gate = KnowledgeCompletenessGate()

        spec = CanonicalSpec(
            spec_type=SpecType.SECTION_RULE,
            content={
                "section_location": "introduction",
                "required_fields": ["case_description", "boundary_conditions"],
            },
        )

        result = gate.check(spec)
        assert result.is_pass()

    def test_workflow_validation(self):
        """Test workflow field validation"""
        gate = KnowledgeCompletenessGate()

        spec = CanonicalSpec(
            spec_type=SpecType.WORKFLOW_PATTERN,
            content={
                "workflow_name": "cfd_postprocessing",
                "steps": ["load_data", "generate_plots"],
                "inputs": ["openfoam_case"],
                "outputs": ["report_pdf"],
            },
        )

        result = gate.check(spec)
        assert result.is_pass()

    def test_empty_lists_warning(self):
        """Test empty list fields generate warnings"""
        gate = KnowledgeCompletenessGate()

        spec = CanonicalSpec(
            spec_type=SpecType.WORKFLOW_PATTERN,
            content={
                "workflow_name": "test",
                "steps": [],  # Empty - should warn
                "inputs": [],
                "outputs": [],
            },
        )

        result = gate.check(spec)
        # Empty lists should generate warnings, not errors
        assert len(result.warnings) > 0

    def test_non_strict_mode(self):
        """Test non-strict mode allows warnings"""
        gate = KnowledgeCompletenessGate(strict_mode=False)

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={
                "name": "Test",
                # Missing some fields
            },
        )

        result = gate.check(spec)
        # Non-strict mode: status is WARN if score >= 50 but < 75
        # Score: 100 - 3 * 12.5 = 62.5 -> WARN
        assert result.status == GateStatus.WARN

    def test_source_tracking_warning(self):
        """Test missing source tracking generates warning"""
        gate = KnowledgeCompletenessGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={
                "name": "Test",
                "problem_type": "test",
                "required_plots": ["plot1"],
                "required_metrics": ["metric1"],
            },
        )
        # No source_teach_ids or source_case_ids

        result = gate.check(spec)
        assert len(result.warnings) > 0
        assert "No source tracking" in str(result.warnings)

    def test_batch_check_all_pass(self):
        """Test batch check with all passing specs"""
        gate = KnowledgeCompletenessGate()

        specs = [
            CanonicalSpec(
                spec_type=SpecType.REPORT_SPEC,
                content={
                    "name": f"Report {i}",
                    "problem_type": "test",
                    "required_plots": ["plot1"],
                    "required_metrics": ["metric1"],
                },
            )
            for i in range(3)
        ]

        result = gate.check_batch(specs)
        assert result.is_pass()
        assert result.metadata["total_checked"] == 3
        assert result.metadata["pass_count"] == 3

    def test_batch_check_mixed(self):
        """Test batch check with mixed results"""
        gate = KnowledgeCompletenessGate()

        specs = [
            CanonicalSpec(
                spec_type=SpecType.REPORT_SPEC,
                content={
                    "name": "Valid Report",
                    "problem_type": "test",
                    "required_plots": ["plot1"],
                    "required_metrics": ["metric1"],
                },
            ),
            CanonicalSpec(
                spec_type=SpecType.REPORT_SPEC,
                content={
                    "name": "Invalid Report",
                    # Missing fields
                },
            ),
        ]

        result = gate.check_batch(specs)
        assert result.status == GateStatus.FAIL
        assert result.metadata["total_checked"] == 2
        assert result.metadata["pass_count"] == 1
        assert result.metadata["fail_count"] == 1

    def test_batch_check_empty(self):
        """Test batch check with empty list"""
        gate = KnowledgeCompletenessGate()

        result = gate.check_batch([])
        assert result.is_pass()
        assert result.score == 100.0


class TestAuthorizationGate:
    """Test G2-P2: Authorization Gate"""

    def test_gate_id(self):
        """Test gate ID is correct"""
        gate = AuthorizationGate()
        assert gate.GATE_ID == G2_P2_GATE_ID
        assert gate.GATE_ID == "G2-P2"
        assert gate.GATE_NAME == "Authorization Gate"

    def test_pending_authorization(self):
        """Test spec without authorization fails"""
        gate = AuthorizationGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )

        result = gate.check(spec)

        assert result.status == GateStatus.FAIL
        assert result.score < 50.0
        assert "Authorization pending" in result.errors

    def test_risk_level_assessment(self):
        """Test risk level assessment"""
        gate = AuthorizationGate()

        # Low risk (has sources)
        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )
        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "bench-04")
        spec.add_source("TEACH-003", "case-003")

        result = gate.check(spec)
        assert result.metadata["risk_level"] == "low"

        # High risk (no sources)
        spec2 = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test2"},
        )

        result2 = gate.check(spec2)
        assert result2.metadata["risk_level"] == "high"

    def test_create_auth_request(self):
        """Test creating authorization request"""
        gate = AuthorizationGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )

        request = gate.create_auth_request(
            spec=spec,
            requester="engineer-001",
            risk_level="medium",
            approvers=["senior-001"],
        )

        assert request.spec_id == spec.spec_id
        assert request.requester == "engineer-001"
        assert request.risk_level == "medium"
        assert request.status == AuthStatus.REQUESTED
        assert "senior-001" in request.approvers

    def test_approve_request(self):
        """Test approving authorization request"""
        gate = AuthorizationGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )
        # Add sources to reduce risk
        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "bench-04")
        spec.add_source("TEACH-003", "case-003")

        request = gate.create_auth_request(
            spec=spec,
            requester="engineer-001",
            risk_level="low",
        )

        # Approve the request
        success = gate.approve_request(
            request_id=request.request_id,
            approver="senior-001",
            comment="Looks good",
        )

        assert success is True

        # Now check should pass (with low risk and sources)
        result = gate.check(spec)
        assert result.is_pass()

    def test_reject_request(self):
        """Test rejecting authorization request"""
        gate = AuthorizationGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )

        request = gate.create_auth_request(
            spec=spec,
            requester="engineer-001",
            risk_level="high",
        )

        # Reject the request
        success = gate.reject_request(
            request_id=request.request_id,
            approver="senior-001",
            reason="Insufficient evidence",
        )

        assert success is True

        # Check should fail with rejected status
        result = gate.check(spec)
        assert result.status == GateStatus.FAIL
        assert "Authorization rejected" in result.errors

    def test_auto_approve_non_strict(self):
        """Test auto-approval in non-strict mode"""
        gate = AuthorizationGate(strict_mode=False)

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )
        # Add sources for has_teach_backup
        spec.add_source("TEACH-001", "case-001")
        spec.knowledge_status = KnowledgeStatus.APPROVED

        # Need all conditions: is_bug_fix, is_documentation_only, confidence >= 0.8, has_teach_backup
        result = gate.check(spec, context={
            "is_bug_fix": True,
            "is_documentation_only": True,
            "confidence": 0.9,
        })

        # With all conditions met, should auto-approve
        assert result.metadata.get("auth_status") == "auto_approved"

    def test_confidence_extraction(self):
        """Test confidence extraction"""
        gate = AuthorizationGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )

        # From context
        result = gate.check(spec, context={"confidence": 0.9})
        assert result.metadata["confidence"] == 0.9

        # From source count (default)
        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "bench-04")
        result2 = gate.check(spec)
        # 2 sources -> 2 * 0.3 + 0.1 = 0.7
        assert result2.metadata["confidence"] == 0.7

    def test_high_risk_warning(self):
        """Test high risk generates warning"""
        gate = AuthorizationGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )

        request = gate.create_auth_request(
            spec=spec,
            requester="engineer-001",
            risk_level="low",
        )
        gate.approve_request(request.request_id, "senior-001")

        result = gate.check(spec)
        # High risk (no sources) should generate warning
        if result.metadata["risk_level"] == "high":
            assert any("senior approval" in w for w in result.warnings)

    def test_source_tracking_exists(self):
        """Test source tracking check passes"""
        gate = AuthorizationGate()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )
        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "bench-04")

        # Create and approve request
        request = gate.create_auth_request(spec, "engineer-001", "low")
        gate.approve_request(request.request_id, "senior-001")

        result = gate.check(spec)
        # Should have source_tracking check item
        assert any(c.item == "source_tracking" for c in result.checklist)

    def test_auto_approve_conditions(self):
        """Test auto-approval conditions"""
        gate = AuthorizationGate(strict_mode=False)

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )
        spec.add_source("TEACH-001", "case-001")

        # Bug fix context should enable auto-approve
        result = gate.check(spec, context={
            "is_bug_fix": True,
            "is_documentation_only": True,
            "confidence": 0.9,
        })

        # Should have auto_approve check
        assert any(c.item == "auto_approve" for c in result.checklist)

    def test_strict_mode_disables_auto_approve(self):
        """Test strict mode disables auto-approval"""
        gate = AuthorizationGate(strict_mode=True)

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )
        spec.add_source("TEACH-001", "case-001")

        result = gate.check(spec, context={
            "is_bug_fix": True,
        })

        # Should warn about strict mode
        assert any("strict mode" in c.message.lower() for c in result.checklist)


class TestGateResult:
    """Test GateResult dataclass"""

    def test_to_dict(self):
        """Test GateResult to_dict conversion"""
        from knowledge_compiler.phase2.gates.gates import GateCheckItem, GateResult

        result = GateResult(
            gate_id="TEST-GATE",
            gate_name="Test Gate",
            status=GateStatus.PASS,
            timestamp=time.time(),
            score=100.0,
            checklist=[
                GateCheckItem(
                    item="test_item",
                    description="Test check",
                    result=GateStatus.PASS,
                    message="Passed",
                )
            ],
        )

        d = result.to_dict()
        assert d["gate_id"] == "TEST-GATE"
        assert d["status"] == "PASS"
        assert len(d["checklist"]) == 1
        assert d["checklist"][0]["item"] == "test_item"

    def test_is_pass(self):
        """Test is_pass method"""
        from knowledge_compiler.phase2.gates.gates import GateResult

        pass_result = GateResult(
            gate_id="TEST",
            gate_name="Test",
            status=GateStatus.PASS,
            timestamp=time.time(),
            score=100.0,
        )

        assert pass_result.is_pass() is True

        fail_result = GateResult(
            gate_id="TEST",
            gate_name="Test",
            status=GateStatus.FAIL,
            timestamp=time.time(),
            score=0.0,
        )

        assert fail_result.is_pass() is False

    def test_get_pass_rate(self):
        """Test get_pass_rate calculation"""
        from knowledge_compiler.phase2.gates.gates import GateResult, GateCheckItem

        result = GateResult(
            gate_id="TEST",
            gate_name="Test",
            status=GateStatus.PASS,
            timestamp=time.time(),
            score=75.0,
            checklist=[
                GateCheckItem(
                    item="item1",
                    description="Item 1",
                    result=GateStatus.PASS,
                    message="Passed",
                ),
                GateCheckItem(
                    item="item2",
                    description="Item 2",
                    result=GateStatus.FAIL,
                    message="Failed",
                ),
                GateCheckItem(
                    item="item3",
                    description="Item 3",
                    result=GateStatus.PASS,
                    message="Passed",
                ),
            ],
        )

        # 2 out of 3 passed = 66.67%
        pass_rate = result.get_pass_rate()
        assert 66.0 < pass_rate < 67.0
