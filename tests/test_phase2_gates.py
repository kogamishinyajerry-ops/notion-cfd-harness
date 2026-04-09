#!/usr/bin/env python3
"""
Tests for Phase 2 Gate modules: G1-P2 (Knowledge Completeness) and G2-P2 (Authorization).
"""

import pytest
from knowledge_compiler.phase2.gates.g1_p2 import (
    KnowledgeCompletenessGate,
    G1_P2_GATE_ID,
)
from knowledge_compiler.phase2.gates.g2_p2 import (
    AuthorizationGate,
    AuthStatus,
    AuthRequest,
    G2_P2_GATE_ID,
)
from knowledge_compiler.phase2.gates.gates import GateStatus
from knowledge_compiler.phase2.schema import CanonicalSpec, SpecType


# ============================================================================
# G1-P2: Knowledge Completeness Gate Tests
# ============================================================================

class TestKnowledgeCompletenessGate:
    """Tests for KnowledgeCompletenessGate (G1-P2)"""

    def test_gate_id(self):
        """Gate has correct ID"""
        gate = KnowledgeCompletenessGate()
        assert gate.GATE_ID == G1_P2_GATE_ID
        assert gate.GATE_ID == "G1-P2"

    def test_strict_mode_default(self):
        """Gate defaults to strict mode"""
        gate = KnowledgeCompletenessGate()
        assert gate.strict_mode is True

    def test_strict_mode_configurable(self):
        """Strict mode can be disabled"""
        gate = KnowledgeCompletenessGate(strict_mode=False)
        assert gate.strict_mode is False

    def test_complete_report_spec_passes(self):
        """Complete report_spec passes gate"""
        gate = KnowledgeCompletenessGate(strict_mode=True)
        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={
                "name": "Test Spec",
                "problem_type": "fluid_flow",
                "required_plots": [{"name": "velocity"}],
                "required_metrics": [{"name": "Cd"}],
            },
            spec_id="SPEC-001",
            source_teach_ids=["TEACH-001"],
        )
        result = gate.check(spec)
        assert result.status == GateStatus.PASS
        assert result.score >= 75.0

    def test_missing_spec_type_fails(self):
        """Spec without spec_type fails"""
        gate = KnowledgeCompletenessGate()
        spec = CanonicalSpec(
            spec_type=None,
            content={"name": "Test"},
        )
        result = gate.check(spec)
        assert result.status == GateStatus.FAIL
        assert result.metadata.get("error") == "no_spec_type"

    def test_missing_required_fields_fails_strict(self):
        """Missing required fields in strict mode fails"""
        gate = KnowledgeCompletenessGate(strict_mode=True)
        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={
                "name": "Test Spec",
                # missing problem_type, required_plots, required_metrics
            },
            spec_id="SPEC-002",
        )
        result = gate.check(spec)
        assert result.status == GateStatus.FAIL
        assert len(result.errors) > 0

    def test_batch_check_aggregates(self):
        """Batch check aggregates results"""
        gate = KnowledgeCompletenessGate(strict_mode=False)
        specs = [
            CanonicalSpec(
                spec_type=SpecType.REPORT_SPEC,
                content={
                    "name": "Spec 1",
                    "problem_type": "fluid_flow",
                    "required_plots": [],
                    "required_metrics": [],
                },
                spec_id="SPEC-A",
            ),
            CanonicalSpec(
                spec_type=SpecType.PLOT_STANDARD,
                content={
                    "plot_type": "contour",
                    "field": "velocity",
                    "colormap": "viridis",
                    "plane": "z=0",
                },
                spec_id="SPEC-B",
            ),
        ]
        result = gate.check_batch(specs)
        assert result.metadata["total_checked"] == 2
        assert result.metadata["pass_count"] >= 0

    def test_plot_standard_fields(self):
        """Plot standard has correct required fields"""
        gate = KnowledgeCompletenessGate(strict_mode=False)
        spec = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={
                "plot_type": "contour",
                "field": "velocity",
                "colormap": "viridis",
                "plane": "z=0",
            },
            spec_id="SPEC-PLOT",
        )
        result = gate.check(spec)
        assert result.status == GateStatus.PASS

    def test_missing_source_tracking_warns(self):
        """Missing source tracking generates warning but not error"""
        gate = KnowledgeCompletenessGate(strict_mode=False)
        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={
                "name": "Test",
                "problem_type": "fluid_flow",
                "required_plots": [],
                "required_metrics": [],
            },
            spec_id="SPEC-NO-SOURCE",
        )
        result = gate.check(spec)
        assert len(result.warnings) > 0  # No source tracking warning

    def test_metric_standard_fields(self):
        """Metric standard validates correctly"""
        gate = KnowledgeCompletenessGate(strict_mode=False)
        spec = CanonicalSpec(
            spec_type=SpecType.METRIC_STANDARD,
            content={
                "metric_name": "Cd",
                "unit": "N/A",
                "calculation_method": "area-weighted average",
            },
            spec_id="SPEC-METRIC",
        )
        result = gate.check(spec)
        assert result.status == GateStatus.PASS


# ============================================================================
# G2-P2: Authorization Gate Tests
# ============================================================================

class TestAuthorizationGate:
    """Tests for AuthorizationGate (G2-P2)"""

    def test_gate_id(self):
        """Gate has correct ID"""
        gate = AuthorizationGate()
        assert gate.GATE_ID == G2_P2_GATE_ID
        assert gate.GATE_ID == "G2-P2"

    def test_strict_mode_default(self):
        """Gate defaults to strict mode"""
        gate = AuthorizationGate()
        assert gate.strict_mode is True

    def test_approved_spec_passes(self):
        """Approved spec passes gate via auto-approval"""
        gate = AuthorizationGate(strict_mode=False)  # non-strict allows auto-approve

        class MockSpec:
            spec_id = "SPEC-AUTH-001"
            source_teach_ids = ["TEACH-001", "TEACH-002", "TEACH-003"]  # 3+ sources = low risk
            source_case_ids = ["CASE-001"]

        spec = MockSpec()
        context = {
            "confidence": 0.85,  # >= 0.7 threshold
        }
        result = gate.check(spec, context)
        assert result.status == GateStatus.PASS
        assert result.score >= 75.0

    def test_pending_auth_fails_strict(self):
        """Pending authorization fails in strict mode"""
        gate = AuthorizationGate(strict_mode=True)

        class MockSpec:
            spec_id = "SPEC-PEND"
            source_teach_ids = []
            source_case_ids = []

        spec = MockSpec()
        context = {
            "auth_status": AuthStatus.PENDING,
            "risk_level": "high",
            "confidence": 0.3,
        }
        result = gate.check(spec, context)
        assert result.status == GateStatus.FAIL

    def test_rejected_auth_fails(self):
        """Rejected authorization fails"""
        gate = AuthorizationGate(strict_mode=False)

        class MockSpec:
            spec_id = "SPEC-REJ"
            source_teach_ids = []
            source_case_ids = []

        spec = MockSpec()
        context = {
            "auth_status": AuthStatus.REJECTED,
            "risk_level": "low",
            "confidence": 0.5,
        }
        result = gate.check(spec, context)
        assert result.status == GateStatus.FAIL

    def test_high_risk_warns(self):
        """High risk knowledge generates warning"""
        gate = AuthorizationGate(strict_mode=True)  # strict mode required for high-risk detection

        class MockSpec:
            spec_id = "SPEC-HIGH-RISK"
            source_teach_ids = []  # No sources = high risk
            source_case_ids = []

        spec = MockSpec()
        context = {
            "confidence": 0.9,  # High confidence but no sources
        }
        result = gate.check(spec, context)
        # High risk (no sources) in strict mode should WARN
        risk_items = [c for c in result.checklist if c.item == "risk_assessment"]
        assert len(risk_items) == 1
        assert risk_items[0].result == GateStatus.WARN

    def test_auto_approve_conditions(self):
        """Auto-approve conditions are defined"""
        gate = AuthorizationGate(strict_mode=False)
        assert gate.AUTO_APPROVE_CONDITIONS["is_bug_fix"] is True
        assert gate.AUTO_APPROVE_CONDITIONS["is_documentation_only"] is True
        assert gate.AUTO_APPROVE_CONDITIONS["confidence"] == 0.8

    def test_low_confidence_warns(self):
        """Low confidence generates warning"""
        gate = AuthorizationGate(strict_mode=False)

        class MockSpec:
            spec_id = "SPEC-LOW-CONF"
            source_teach_ids = ["TEACH-001"]
            source_case_ids = ["CASE-001"]

        spec = MockSpec()
        context = {
            "auth_status": AuthStatus.APPROVED,
            "risk_level": "medium",
            "confidence": 0.3,
        }
        result = gate.check(spec, context)
        assert len(result.warnings) > 0  # Low confidence warning

    def test_strict_mode_blocks_auto_approve(self):
        """Strict mode blocks auto-approval"""
        gate = AuthorizationGate(strict_mode=True)

        class MockSpec:
            spec_id = "SPEC-STRICT"
            source_teach_ids = ["TEACH-001"]
            source_case_ids = ["CASE-001"]

        spec = MockSpec()
        context = {
            "auth_status": AuthStatus.APPROVED,
            "risk_level": "low",
            "confidence": 0.9,
        }
        result = gate.check(spec, context)
        # In strict mode, auto-approve should WARN (disabled)
        auto_approve_items = [c for c in result.checklist if c.item == "auto_approve"]
        assert len(auto_approve_items) == 1
        assert auto_approve_items[0].result == GateStatus.WARN


class TestAuthRequest:
    """Tests for AuthRequest dataclass"""

    def test_is_approved_true(self):
        """is_approved returns True for APPROVED status"""
        req = AuthRequest(
            request_id="AUTH-001",
            spec_id="SPEC-001",
            requester="engineer_1",
            risk_level="low",
            timestamp=1234567890.0,
            status=AuthStatus.APPROVED,
            approvers=["manager_1"],
        )
        assert req.is_approved() is True

    def test_is_approved_false_pending(self):
        """is_approved returns False for PENDING status"""
        req = AuthRequest(
            request_id="AUTH-002",
            spec_id="SPEC-002",
            requester="engineer_1",
            risk_level="low",
            timestamp=1234567890.0,
            status=AuthStatus.PENDING,
            approvers=["manager_1"],
        )
        assert req.is_approved() is False

    def test_comments_default_none(self):
        """Comments defaults to None"""
        req = AuthRequest(
            request_id="AUTH-003",
            spec_id="SPEC-003",
            requester="engineer_1",
            risk_level="medium",
            timestamp=1234567890.0,
            status=AuthStatus.REQUESTED,
            approvers=["manager_1"],
        )
        assert req.comments is None  # field default is None

    def test_comments_can_be_set(self):
        """Comments can be populated"""
        req = AuthRequest(
            request_id="AUTH-004",
            spec_id="SPEC-004",
            requester="engineer_1",
            risk_level="high",
            timestamp=1234567890.0,
            status=AuthStatus.REJECTED,
            approvers=["senior_manager"],
            comments=["Risk too high for auto-approval"],
        )
        assert len(req.comments) == 1


class TestAuthStatus:
    """Tests for AuthStatus enum"""

    def test_all_auth_statuses_exist(self):
        """All expected auth statuses are defined"""
        assert AuthStatus.PENDING.value == "pending"
        assert AuthStatus.REQUESTED.value == "requested"
        assert AuthStatus.APPROVED.value == "approved"
        assert AuthStatus.REJECTED.value == "rejected"
        assert AuthStatus.AUTO_APPROVED.value == "auto_approved"

    def test_status_count(self):
        """All 5 auth statuses exist"""
        assert len(AuthStatus) == 5
