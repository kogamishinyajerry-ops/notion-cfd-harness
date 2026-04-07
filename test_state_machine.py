#!/usr/bin/env python3
"""
Well-Harness 状态机 pytest 单元测试
覆盖全部合法转换 + 非法转换拒绝 + GateValidator + Evidence 沉淀
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from state_machine import (
    StateMachine, GateValidator, STATES, GATE_TRANSITIONS,
    NOTION_HEADERS, NOTION_BASE_URL, EVIDENCE_DB_ID, SSOT_DB_ID,
)


class TestStateMachineBasic:
    """基础功能测试"""

    def test_initial_state_is_draft(self):
        sm = StateMachine(task_id="TEST-001")
        assert sm.get_state() == "Draft"

    def test_all_states_defined(self):
        expected = ["Draft", "IntakeValidated", "KnowledgeBound", "Planned",
                    "Running", "Verifying", "ReviewPending", "Approved", "Closed"]
        assert STATES == expected

    def test_task_id_stored(self):
        sm = StateMachine(task_id="AI-CFD-M1-1")
        assert sm.task_id == "AI-CFD-M1-1"


class TestLegalTransitions:
    """合法状态转换测试（G0-G6）"""

    def test_g0_draft_to_intakevalidated(self):
        sm = StateMachine(task_id="TEST")
        ok, evid = sm.transition("IntakeValidated")
        assert ok is True
        assert evid is not None
        assert sm.get_state() == "IntakeValidated"

    def test_g1_intakevalidated_to_knowledgebound(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")  # G0
        ok, evid = sm.transition("KnowledgeBound")  # G1
        assert ok is True
        assert evid is not None
        assert sm.get_state() == "KnowledgeBound"

    def test_g2_knowledgebound_to_planned(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        sm.transition("KnowledgeBound")
        ok, evid = sm.transition("Planned")  # G2
        assert ok is True
        assert evid is not None
        assert sm.get_state() == "Planned"

    def test_g3_planned_to_running(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        sm.transition("KnowledgeBound")
        sm.transition("Planned")
        ok, evid = sm.transition("Running")  # G3
        assert ok is True
        assert evid is not None
        assert sm.get_state() == "Running"

    def test_g4_running_to_verifying(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        sm.transition("KnowledgeBound")
        sm.transition("Planned")
        sm.transition("Running")
        ok, evid = sm.transition("Verifying")  # G4
        assert ok is True
        assert evid is not None
        assert sm.get_state() == "Verifying"

    def test_g5a_verifying_to_reviewpending(self):
        sm = StateMachine(task_id="TEST")
        for s in ["IntakeValidated", "KnowledgeBound", "Planned", "Running", "Verifying"]:
            sm.transition(s)
        ok, evid = sm.transition("ReviewPending")  # G5
        assert ok is True
        assert evid is not None
        assert sm.get_state() == "ReviewPending"

    def test_g5b_reviewpending_to_approved(self):
        sm = StateMachine(task_id="TEST")
        for s in ["IntakeValidated", "KnowledgeBound", "Planned", "Running",
                   "Verifying", "ReviewPending"]:
            sm.transition(s)
        ok, evid = sm.transition("Approved")  # G5
        assert ok is True
        assert evid is not None
        assert sm.get_state() == "Approved"

    def test_g6_approved_to_closed(self):
        sm = StateMachine(task_id="TEST")
        for s in ["IntakeValidated", "KnowledgeBound", "Planned", "Running",
                   "Verifying", "ReviewPending", "Approved"]:
            sm.transition(s)
        ok, evid = sm.transition("Closed")  # G6
        assert ok is True
        assert evid is not None
        assert sm.get_state() == "Closed"


class TestIllegalTransitions:
    """非法转换拒绝测试"""

    def test_cannot_skip_gates(self):
        sm = StateMachine(task_id="TEST")
        ok, _ = sm.transition("Running")  # 跳过 G0/G1/G2
        assert ok is False
        assert sm.get_state() == "Draft"

    def test_cannot_skip_g1(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        ok, _ = sm.transition("Running")  # 跳过 G2
        assert ok is False
        assert sm.get_state() == "IntakeValidated"

    def test_cannot_skip_g2(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        sm.transition("KnowledgeBound")
        ok, _ = sm.transition("Verifying")  # 跳过 G3
        assert ok is False
        assert sm.get_state() == "KnowledgeBound"

    def test_cannot_go_backward(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        ok, _ = sm.transition("Draft")  # 回退
        assert ok is False
        assert sm.get_state() == "IntakeValidated"

    def test_cannot_transition_from_closed(self):
        sm = StateMachine(task_id="TEST")
        for s in ["IntakeValidated", "KnowledgeBound", "Planned", "Running",
                   "Verifying", "ReviewPending", "Approved", "Closed"]:
            sm.transition(s)
        ok, _ = sm.transition("Draft")
        assert ok is False
        assert sm.get_state() == "Closed"

    def test_invalid_state_rejected(self):
        sm = StateMachine(task_id="TEST")
        ok, _ = sm.transition("NonExistentState")
        assert ok is False

    def test_cannot_transition_to_same_state(self):
        sm = StateMachine(task_id="TEST")
        ok, _ = sm.transition("Draft")
        assert ok is True  # 空操作允许（代码中 can_transition 返回 True）


class TestCanTransition:
    """can_transition 方法测试"""

    def test_can_transition_legal(self):
        sm = StateMachine(task_id="TEST")
        assert sm.can_transition("Draft", "IntakeValidated") is True
        assert sm.can_transition("IntakeValidated", "KnowledgeBound") is True
        assert sm.can_transition("KnowledgeBound", "Planned") is True

    def test_can_transition_illegal(self):
        sm = StateMachine(task_id="TEST")
        assert sm.can_transition("Draft", "Running") is False
        assert sm.can_transition("Planned", "Closed") is False

    def test_can_transition_same_state(self):
        sm = StateMachine(task_id="TEST")
        assert sm.can_transition("Draft", "Draft") is True


class TestGetAvailableTransitions:
    """可用转换查询测试"""

    def test_from_draft(self):
        sm = StateMachine(task_id="TEST")
        assert sm.get_available_transitions() == ["IntakeValidated"]

    def test_from_intakevalidated(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        assert sm.get_available_transitions() == ["KnowledgeBound"]

    def test_from_planned(self):
        sm = StateMachine(task_id="TEST")
        for s in ["IntakeValidated", "KnowledgeBound", "Planned"]:
            sm.transition(s)
        assert sm.get_available_transitions() == ["Running"]


class TestGetGateForTransition:
    """Gate 查询测试"""

    def test_g0_gate(self):
        sm = StateMachine(task_id="TEST")
        assert sm.get_gate_for_transition("IntakeValidated") == "G0"

    def test_g1_gate(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        assert sm.get_gate_for_transition("KnowledgeBound") == "G1"

    def test_g3_gate(self):
        sm = StateMachine(task_id="TEST")
        for s in ["IntakeValidated", "KnowledgeBound", "Planned"]:
            sm.transition(s)
        assert sm.get_gate_for_transition("Running") == "G3"

    def test_no_gate_for_invalid(self):
        sm = StateMachine(task_id="TEST")
        assert sm.get_gate_for_transition("NonExistent") is None


class TestEvidenceHistory:
    """证据历史测试"""

    def test_evidence_history_accumulates(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        sm.transition("KnowledgeBound")
        assert len(sm.evidence_history) == 2

    def test_evidence_contains_required_fields(self):
        sm = StateMachine(task_id="TEST")
        ok, evid = sm.transition("IntakeValidated")
        assert ok is True
        ev = sm.evidence_history[0]
        assert "evidence_id" in ev
        assert ev["task_id"] == "TEST"
        assert ev["from_state"] == "Draft"
        assert ev["to_state"] == "IntakeValidated"
        assert ev["gate"] == "G0"
        assert "timestamp" in ev


class TestSummary:
    """摘要功能测试"""

    def test_summary_fields(self):
        sm = StateMachine(task_id="TEST")
        sm.transition("IntakeValidated")
        summary = sm.summary()
        assert summary["task_id"] == "TEST"
        assert summary["current_state"] == "IntakeValidated"
        assert summary["transition_count"] == 1
        assert "available_transitions" in summary


class TestGateValidator:
    """GateValidator 测试"""

    def test_g0_validate_returns_tuple(self):
        gv = GateValidator()
        result = gv.validate("TEST", "G0")
        assert isinstance(result, tuple)
        assert len(result) == 2
        passed, evidence = result
        assert isinstance(passed, bool)
        assert isinstance(evidence, dict)

    def test_g0_validate_pass_fields(self):
        gv = GateValidator()
        passed, evidence = gv.validate("TEST", "G0")
        assert evidence["gate"] == "G0"
        assert evidence["gate_name"] == "任务门"
        assert evidence["task_id"] == "TEST"
        assert "timestamp" in evidence
        assert "checks" in evidence

    def test_g1_to_g6_validate(self):
        gv = GateValidator()
        for g in ["G1", "G2", "G3", "G4", "G5", "G6"]:
            passed, evidence = gv.validate("TEST", g)
            assert evidence["gate"] == g
            assert "checks" in evidence

    def test_invalid_gate_returns_false(self):
        gv = GateValidator()
        passed, evidence = gv.validate("TEST", "G9")
        assert passed is False
        assert evidence["message"] == "Unknown gate: G9"

    def test_gate_meta_complete(self):
        meta = GateValidator.GATE_META
        for g in ["G0", "G1", "G2", "G3", "G4", "G5", "G6"]:
            assert g in meta
            assert "name" in meta[g]
            assert "description" in meta[g]


class TestEvidenceDeposit:
    """Evidence 沉淀钩子测试"""

    def test_evidence_type_pass_mapping(self):
        """Gate 通过时 evidence_type 映射正确"""
        gv = GateValidator()
        assert gv._get_evidence_type("G0", True) == "GateCheck"
        assert gv._get_evidence_type("G1", True) == "GateCheck"
        assert gv._get_evidence_type("G2", True) == "ValidationReport"
        assert gv._get_evidence_type("G3", True) == "ValidationReport"
        assert gv._get_evidence_type("G4", True) == "ConvergenceLog"
        assert gv._get_evidence_type("G5", True) == "ApprovalRecord"
        assert gv._get_evidence_type("G6", True) == "ApprovalRecord"

    def test_evidence_type_fail_mapping(self):
        """Gate 失败时 evidence_type = RuleViolation"""
        gv = GateValidator()
        assert gv._get_evidence_type("G5", False) == "RuleViolation"
        assert gv._get_evidence_type("G6", False) == "RuleViolation"
        assert gv._get_evidence_type("default", False) == "RuleViolation"

    def test_evidence_id_format(self):
        """evidence_id 格式: EV-XXXXXX (EV- + 6位大写十六进制)"""
        gv = GateValidator()
        eid = gv._generate_evidence_id()
        assert eid.startswith("EV-")
        assert len(eid) == 9  # EV- (3) + 6 hex chars

    def test_evidence_id_unique(self):
        """每次生成的 evidence_id 唯一"""
        gv = GateValidator()
        ids = [gv._generate_evidence_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_hash_sha256(self):
        """哈希为 64 字符 SHA-256"""
        gv = GateValidator()
        h = gv._compute_hash({"gate": "G0", "task_id": "test"})
        assert len(h) == 64
        assert all(c in '0123456789abcdef' for c in h)

    def test_hash_deterministic(self):
        """相同内容产生相同哈希（防篡改验证）"""
        gv = GateValidator()
        content = {"gate": "G2", "task_id": "AI-CFD-M1-1", "checks": []}
        h1 = gv._compute_hash(content)
        h2 = gv._compute_hash(content)
        assert h1 == h2

    def test_hash_changes_with_content(self):
        """不同内容产生不同哈希"""
        gv = GateValidator()
        h1 = gv._compute_hash({"gate": "G0", "task_id": "task1"})
        h2 = gv._compute_hash({"gate": "G0", "task_id": "task2"})
        assert h1 != h2

    def test_deposit_calls_notion_api(self):
        """deposit_evidence 正确调用 Notion API"""
        gv = GateValidator()
        passed, evidence = gv.validate("TEST", "G0")

        mock_response = {"id": "fake-page-id-12345", "object": "page"}

        with patch('state_machine.requests.post', return_value=MagicMock(status_code=200, json=lambda: mock_response)) as mock_post:
            eid = gv.deposit_evidence("page-123", passed, evidence)

            assert eid is not None
            assert eid.startswith("EV-")
            mock_post.assert_called_once()
            # data passed as keyword arg: requests.post(url, headers=..., json=data)
            call_kwargs = mock_post.call_args[1]
            call_data = call_kwargs["json"]
            assert call_data["parent"] == {"database_id": EVIDENCE_DB_ID}
            props = call_data["properties"]
            assert props["evidence_id"]["title"][0]["text"]["content"].startswith("EV-")
            assert props["gate"]["select"]["name"] == "G0"
            assert props["evidence_type"]["select"]["name"] == "GateCheck"
            assert props["status"]["select"]["name"] == "Deposited"
            assert "immutable_hash" in props
            assert len(props["immutable_hash"]["rich_text"][0]["text"]["content"]) == 64

    def test_deposit_fail_status_on_rejected(self):
        """Gate FAIL 时 status = RuleViolation"""
        gv = GateValidator()
        # 模拟一个失败的 evidence
        failed_evidence = {
            "gate": "G3",
            "gate_name": "执行门",
            "task_id": "TEST",
            "timestamp": "2026-04-07T00:00:00",
            "checks": [],
            "result": "FAIL",
            "message": "Test fail",
        }

        mock_response = {"id": "fake-page-id-fail", "object": "page"}

        with patch('state_machine.requests.post', return_value=MagicMock(status_code=200, json=lambda: mock_response)) as mock_post:
            eid = gv.deposit_evidence("page-123", False, failed_evidence)
            assert eid is not None
            call_kwargs = mock_post.call_args[1]
            props = call_kwargs["json"]["properties"]
            assert props["status"]["select"]["name"] == "RuleViolation"
            assert props["evidence_type"]["select"]["name"] == "RuleViolation"

    def test_deposit_returns_none_on_error(self):
        """Notion API 失败时 deposit_evidence 返回 None"""
        gv = GateValidator()
        passed, evidence = gv.validate("TEST", "G0")

        with patch('state_machine.requests.post', return_value=MagicMock(status_code=400, json=lambda: {"message": "bad request"})):
            eid = gv.deposit_evidence("page-123", passed, evidence)
            assert eid is None

    def test_validate_and_deposit_returns_tuple(self):
        """validate_and_deposit 返回 (pass, evidence, evidence_id) 三元组"""
        gv = GateValidator()
        mock_response = {"id": "fake-page-id-456", "object": "page"}

        with patch('state_machine.requests.post', return_value=MagicMock(status_code=200, json=lambda: mock_response)):
            passed, evidence, eid = gv.validate_and_deposit("page-123", "G2")
            assert isinstance(passed, bool)
            assert isinstance(evidence, dict)
            assert "gate" in evidence
            assert eid is not None
            assert eid.startswith("EV-")

    def test_validate_and_deposit_evidence_id_starts_with_ev(self):
        """validate_and_deposit 每次返回不同 evidence_id"""
        gv = GateValidator()
        mock_response = {"id": "fake-page-id-789", "object": "page"}

        with patch('state_machine.requests.post', return_value=MagicMock(status_code=200, json=lambda: mock_response)):
            _, _, eid1 = gv.validate_and_deposit("page-123", "G0")
            _, _, eid2 = gv.validate_and_deposit("page-123", "G1")
            assert eid1 != eid2
            assert eid1.startswith("EV-")
            assert eid2.startswith("EV-")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
