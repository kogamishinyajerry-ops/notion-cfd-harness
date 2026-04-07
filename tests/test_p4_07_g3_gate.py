#!/usr/bin/env python3
"""
P4-07: G3 Gate automation tests.
"""

import json
from pathlib import Path
import sys
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.gates import g3_gate


class TestCheckCoreComponents:
    def test_check_core_components_passes_when_all_phase4_exports_exist(self, monkeypatch):
        dummy_module = SimpleNamespace(
            VersionedKnowledgeRegistry=type("VersionedKnowledgeRegistry", (), {}),
            MemoryNode=type("MemoryNode", (), {}),
            PropagationEngine=type("PropagationEngine", (), {}),
            GovernanceEngine=type("GovernanceEngine", (), {}),
            CodeMappingRegistry=type("CodeMappingRegistry", (), {}),
            MemoryNetwork=type("MemoryNetwork", (), {}),
        )

        monkeypatch.setattr(g3_gate, "import_module", lambda _: dummy_module)

        result = g3_gate.check_core_components(module_name="dummy.phase4")

        assert result["passed"] is True
        assert result["check"] == "check_core_components"
        assert len(result["components"]) == 6
        assert all(component["passed"] is True for component in result["components"])
        assert "Verified 6/6" in result["detail"]

    def test_check_core_components_reports_missing_component(self, monkeypatch):
        dummy_module = SimpleNamespace(
            VersionedKnowledgeRegistry=type("VersionedKnowledgeRegistry", (), {}),
            MemoryNode=type("MemoryNode", (), {}),
            PropagationEngine=type("PropagationEngine", (), {}),
            GovernanceEngine=type("GovernanceEngine", (), {}),
            CodeMappingRegistry=type("CodeMappingRegistry", (), {}),
        )

        monkeypatch.setattr(g3_gate, "import_module", lambda _: dummy_module)

        result = g3_gate.check_core_components(module_name="dummy.phase4")

        assert result["passed"] is False
        assert "P4-06 MemoryNetwork" in result["detail"]
        assert result["components"][-1]["passed"] is False


class TestRunAllTests:
    def test_run_all_tests_passes_when_pytest_succeeds(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run(command, cwd, check, capture_output, text):
            captured["command"] = command
            captured["cwd"] = cwd
            captured["check"] = check
            captured["capture_output"] = capture_output
            captured["text"] = text
            return SimpleNamespace(
                returncode=0,
                stdout="============================= 201 passed in 0.84s =============================\n",
                stderr="",
            )

        monkeypatch.setattr(g3_gate.subprocess, "run", fake_run)

        result = g3_gate.run_all_tests(repo_root=tmp_path)

        assert result["passed"] is True
        assert result["detail"] == "201 passed in 0.84s"
        assert captured["command"][:3] == [g3_gate.sys.executable, "-m", "pytest"]
        assert captured["cwd"] == str(tmp_path.resolve())
        assert captured["check"] is False
        assert captured["capture_output"] is True
        assert captured["text"] is True

    def test_run_all_tests_fails_when_pytest_fails(self, monkeypatch, tmp_path):
        def fake_run(command, cwd, check, capture_output, text):
            return SimpleNamespace(
                returncode=1,
                stdout="FAILED tests/test_p4_07_g3_gate.py::test_example - AssertionError\n",
                stderr="============================= 1 failed, 200 passed in 0.90s =============================\n",
            )

        monkeypatch.setattr(g3_gate.subprocess, "run", fake_run)

        result = g3_gate.run_all_tests(repo_root=tmp_path)

        assert result["passed"] is False
        assert result["detail"] == "1 failed, 200 passed in 0.90s"
        assert result["returncode"] == 1


class TestCodeReviewIntegration:
    def test_check_code_review_integration_passes_when_script_exists(self, tmp_path):
        script_path = tmp_path / "scripts" / "trigger_code_review.sh"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        script_path.chmod(0o755)

        result = g3_gate.check_code_review_integration(repo_root=tmp_path)

        assert result["passed"] is True
        assert result["script_path"] == str(script_path.resolve())
        assert result["executable"] is True
        assert "Found code review trigger" in result["detail"]

    def test_check_code_review_integration_fails_when_script_missing(self, tmp_path):
        result = g3_gate.check_code_review_integration(repo_root=tmp_path)

        assert result["passed"] is False
        assert result["executable"] is False
        assert "Missing code review trigger" in result["detail"]


class TestRecordGateResult:
    def test_record_gate_result_writes_json_payload(self, tmp_path):
        output_path = tmp_path / "reports" / "g3-result.json"
        payload = {
            "gate": "G3",
            "passed": True,
            "status": "PASS",
            "timestamp": "2026-04-07T12:00:00+00:00",
            "checks": [],
            "blockers": [],
            "next_action": "Ready for G4 gate validation",
        }

        written_path = g3_gate.record_gate_result(payload, output_path=output_path)

        assert written_path == str(output_path.resolve())
        saved_payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved_payload["gate"] == "G3"
        assert saved_payload["status"] == "PASS"
        assert saved_payload["record_path"] == str(output_path.resolve())


class TestTriggerGate:
    def test_trigger_gate_runs_full_flow_and_records_report(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            g3_gate,
            "check_core_components",
            lambda: {
                "check": "check_core_components",
                "passed": True,
                "detail": "Verified 6/6 Phase 4 core components",
                "components": [],
            },
        )
        monkeypatch.setattr(
            g3_gate,
            "run_all_tests",
            lambda repo_root, pytest_args=None: {
                "check": "run_all_tests",
                "passed": True,
                "detail": "201 passed in 0.84s",
                "summary": "201 passed in 0.84s",
                "command": [g3_gate.sys.executable, "-m", "pytest"],
                "working_directory": str(repo_root),
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            },
        )
        monkeypatch.setattr(
            g3_gate,
            "check_code_review_integration",
            lambda repo_root: {
                "check": "check_code_review_integration",
                "passed": True,
                "detail": "Found code review trigger: scripts/trigger_code_review.sh",
                "script_path": str(tmp_path / "scripts" / "trigger_code_review.sh"),
                "executable": True,
            },
        )

        output_path = tmp_path / "reports" / "g3-gate.json"
        result = g3_gate.trigger_gate(repo_root=tmp_path, record_path=output_path)

        assert result["passed"] is True
        assert result["status"] == "PASS"
        assert result["blockers"] == []
        assert result["record_path"] == str(output_path.resolve())
        assert "G3 Gate Report" in result["report"]
        assert "run_all_tests: PASS - 201 passed in 0.84s" in result["report"]

        recorded = json.loads(output_path.read_text(encoding="utf-8"))
        assert recorded["passed"] is True
        assert recorded["status"] == "PASS"
        assert recorded["record_path"] == str(output_path.resolve())

    def test_trigger_gate_reports_failures_as_blockers(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            g3_gate,
            "check_core_components",
            lambda: {
                "check": "check_core_components",
                "passed": False,
                "detail": "Missing core components: P4-06 MemoryNetwork",
                "components": [],
            },
        )
        monkeypatch.setattr(
            g3_gate,
            "run_all_tests",
            lambda repo_root, pytest_args=None: {
                "check": "run_all_tests",
                "passed": True,
                "detail": "201 passed in 0.84s",
                "summary": "201 passed in 0.84s",
                "command": [g3_gate.sys.executable, "-m", "pytest"],
                "working_directory": str(repo_root),
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            },
        )
        monkeypatch.setattr(
            g3_gate,
            "check_code_review_integration",
            lambda repo_root: {
                "check": "check_code_review_integration",
                "passed": False,
                "detail": "Missing code review trigger: scripts/trigger_code_review.sh",
                "script_path": str(tmp_path / "scripts" / "trigger_code_review.sh"),
                "executable": False,
            },
        )

        result = g3_gate.trigger_gate(
            repo_root=tmp_path,
            record_path=tmp_path / "reports" / "g3-gate-failed.json",
        )

        assert result["passed"] is False
        assert result["status"] == "FAIL"
        assert result["blockers"] == [
            "Missing core components: P4-06 MemoryNetwork",
            "Missing code review trigger: scripts/trigger_code_review.sh",
        ]
        assert result["next_action"] == "Resolve blockers and re-run the G3 gate"
        assert "Blockers: Missing core components: P4-06 MemoryNetwork, Missing code review trigger: scripts/trigger_code_review.sh" in result["report"]
