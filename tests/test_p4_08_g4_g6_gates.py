#!/usr/bin/env python3
"""
P4-08: G4-G6 gate acceptance workflow tests.
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.gates import g4_gate, g5_gate, g6_gate


class TestGateConfigs:
    def test_g4_gate_configuration_targets_propagation_verification(self):
        assert g4_gate.DEFAULT_CONFIG.gate_name == "G4"
        assert g4_gate.DEFAULT_CONFIG.review_script is None
        assert g4_gate.DEFAULT_CONFIG.success_action == "Ready for G5 manual approval"
        assert "tests/test_p4_03_propagation_engine.py" in g4_gate.DEFAULT_CONFIG.default_pytest_args

    def test_g5_gate_configuration_targets_manual_approval(self):
        assert g5_gate.DEFAULT_CONFIG.gate_name == "G5"
        assert g5_gate.DEFAULT_CONFIG.review_script is None
        assert g5_gate.DEFAULT_CONFIG.success_action == "Ready for G6 final acceptance"
        assert "tests/test_p4_04_governance_engine.py" in g5_gate.DEFAULT_CONFIG.default_pytest_args

    def test_g6_gate_configuration_targets_final_acceptance(self):
        assert g6_gate.DEFAULT_CONFIG.gate_name == "G6"
        assert g6_gate.DEFAULT_CONFIG.review_script is None
        assert g6_gate.DEFAULT_CONFIG.success_action == "Phase 4 gate acceptance complete"
        assert len(g6_gate.DEFAULT_CONFIG.checks) == 5


class TestGateWrappers:
    def test_g4_trigger_gate_delegates_to_shared_runner(self, monkeypatch, tmp_path):
        captured = {}

        def fake_trigger_gate(gate_name, repo_root=None, record_path=None, pytest_args=None, config=None):
            captured["gate_name"] = gate_name
            captured["repo_root"] = repo_root
            captured["record_path"] = record_path
            captured["pytest_args"] = pytest_args
            captured["config"] = config
            return {"gate": gate_name, "passed": True, "status": "PASS", "report": "ok"}

        monkeypatch.setattr(g4_gate, "_trigger_gate", fake_trigger_gate)

        result = g4_gate.trigger_gate(repo_root=tmp_path, record_path=tmp_path / "g4.json")

        assert captured["gate_name"] == "G4"
        assert captured["repo_root"] == tmp_path
        assert captured["record_path"] == tmp_path / "g4.json"
        assert captured["config"] is g4_gate.DEFAULT_CONFIG
        assert result["gate"] == "G4"

    def test_g5_trigger_gate_delegates_to_shared_runner(self, monkeypatch, tmp_path):
        captured = {}

        def fake_trigger_gate(gate_name, repo_root=None, record_path=None, pytest_args=None, config=None):
            captured["gate_name"] = gate_name
            captured["config"] = config
            return {"gate": gate_name, "passed": True, "status": "PASS", "report": "ok"}

        monkeypatch.setattr(g5_gate, "_trigger_gate", fake_trigger_gate)

        result = g5_gate.trigger_gate(repo_root=tmp_path)

        assert captured["gate_name"] == "G5"
        assert captured["config"] is g5_gate.DEFAULT_CONFIG
        assert result["gate"] == "G5"

    def test_g6_trigger_gate_delegates_to_shared_runner(self, monkeypatch, tmp_path):
        captured = {}

        def fake_trigger_gate(gate_name, repo_root=None, record_path=None, pytest_args=None, config=None):
            captured["gate_name"] = gate_name
            captured["config"] = config
            return {"gate": gate_name, "passed": True, "status": "PASS", "report": "ok"}

        monkeypatch.setattr(g6_gate, "_trigger_gate", fake_trigger_gate)

        result = g6_gate.trigger_gate(repo_root=tmp_path)

        assert captured["gate_name"] == "G6"
        assert captured["config"] is g6_gate.DEFAULT_CONFIG
        assert result["gate"] == "G6"
