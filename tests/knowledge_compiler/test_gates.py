#!/usr/bin/env python3
"""
Shared gate runner tests for P4-08.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.gates import g3_gate


class TestGateConfig:
    def test_gate_config_normalizes_gate_name_and_defaults(self):
        config = g3_gate.GateConfig(
            gate_name="g4",
            results_dir="custom/results",
            review_script="scripts/review.sh",
        )

        assert config.gate_name == "G4"
        assert config.report_title == "G4 Gate Report"
        assert config.results_dir == Path("custom/results")
        assert config.review_script == Path("scripts/review.sh")
        assert config.default_pytest_args == ()

    def test_record_gate_result_uses_gate_name_for_directory_output(self, tmp_path):
        payload = {
            "gate": "G5",
            "passed": True,
            "status": "PASS",
            "timestamp": "2026-04-07T12:00:00+00:00",
            "checks": [],
            "blockers": [],
            "next_action": "Ready for G6 final acceptance",
        }

        written_path = g3_gate.record_gate_result(
            payload,
            output_path=tmp_path / "reports",
            repo_root=tmp_path,
        )

        assert Path(written_path).name == "g5_gate_result_20260407T1200000000.json"
        saved_payload = json.loads(Path(written_path).read_text(encoding="utf-8"))
        assert saved_payload["gate"] == "G5"


class TestGateChecks:
    def test_check_core_components_handles_module_import_exception(self, monkeypatch):
        def raise_import_error(_module_name):
            raise RuntimeError("boom")

        monkeypatch.setattr(g3_gate, "import_module", raise_import_error)

        result = g3_gate.check_core_components(module_name="dummy.module")

        assert result["passed"] is False
        assert result["detail"] == "Unable to import dummy.module: boom"

    def test_check_dependency_propagation_handles_module_import_exception(self, monkeypatch):
        def raise_import_error(_module_name):
            raise RuntimeError("propagation import failed")

        monkeypatch.setattr(g3_gate, "import_module", raise_import_error)

        result = g3_gate.check_dependency_propagation(module_name="dummy.module")

        assert result["passed"] is False
        assert result["detail"] == "Unable to import dummy.module: propagation import failed"

    def test_check_manual_approval_points_handles_module_import_exception(self, monkeypatch):
        def raise_import_error(_module_name):
            raise RuntimeError("approval import failed")

        monkeypatch.setattr(g3_gate, "import_module", raise_import_error)

        result = g3_gate.check_manual_approval_points(module_name="dummy.module")

        assert result["passed"] is False
        assert "approval import failed" in result["detail"]

    def test_check_dependency_propagation_passes_for_memory_network_contract(self):
        result = g3_gate.check_dependency_propagation()

        assert result["passed"] is True
        assert "PropagationEngine.detect_changes" in result["verified_members"]
        assert "MemoryNetwork.propagate_change" in result["verified_members"]

    def test_check_manual_approval_points_passes_for_memory_network_contract(self):
        result = g3_gate.check_manual_approval_points()

        assert result["passed"] is True
        assert any("halt/manual review" in point for point in result["verified_points"])
        assert any("Gate Final Approval" in point for point in result["verified_points"])

    def test_check_gate_module_imports_passes_after_g4_g6_added(self):
        result = g3_gate.check_gate_module_imports()

        assert result["passed"] is True
        assert len(result["modules"]) == 4


class TestTriggerGateSharedRunner:
    def test_trigger_gate_collects_mixed_pass_fail_results(self, tmp_path):
        def passing_check(_repo_root, _pytest_args, _config):
            return {"check": "passing_check", "passed": True, "detail": "all good"}

        def failing_check(_repo_root, _pytest_args, _config):
            return {"check": "failing_check", "passed": False, "detail": "needs attention"}

        config = g3_gate.GateConfig(
            gate_name="G4",
            checks=(passing_check, failing_check, passing_check),
            success_action="unused",
            failure_action="Resolve blockers and re-run the G4 gate",
        )
        result = g3_gate.trigger_gate(
            gate_name="G4",
            repo_root=tmp_path,
            record_path=tmp_path / "reports",
            config=config,
        )

        assert result["gate"] == "G4"
        assert result["passed"] is False
        assert result["status"] == "FAIL"
        assert result["blockers"] == ["needs attention"]
        assert result["next_action"] == "Resolve blockers and re-run the G4 gate"
        assert Path(result["record_path"]).name.startswith("g4_gate_result_")
        assert "G4 Gate Report" in result["report"]

    def test_trigger_gate_accepts_legacy_repo_root_positional_argument(self, tmp_path):
        def passing_check(_repo_root, _pytest_args, _config):
            return {"check": "passing_check", "passed": True, "detail": "ok"}

        config = g3_gate.GateConfig(
            gate_name="G6",
            checks=(passing_check,),
            success_action="Phase 4 gate acceptance complete",
            failure_action="unused",
        )
        result = g3_gate.trigger_gate(
            tmp_path,
            record_path=tmp_path / "reports" / "g6.json",
            config=config,
        )

        assert result["gate"] == "G6"
        assert result["passed"] is True
        assert result["record_path"] == str((tmp_path / "reports" / "g6.json").resolve())
