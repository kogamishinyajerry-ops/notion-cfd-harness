#!/usr/bin/env python3
"""
P4-11: memory-network CLI tests.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from importlib.machinery import SourceFileLoader
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "memory-network"


def load_cli_module():
    loader = SourceFileLoader("memory_network_cli", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeEvent:
    def __init__(self, event_id: str, gate: str):
        self.event_id = event_id
        self.gate = gate

    def to_dict(self) -> dict[str, str]:
        return {"event_id": self.event_id, "gate": self.gate}


def test_script_exists_and_is_executable():
    assert SCRIPT_PATH.exists()
    assert os.access(SCRIPT_PATH, os.X_OK)


def test_gate_trigger_dispatches_to_requested_gate(monkeypatch, tmp_path):
    cli = load_cli_module()
    captured = {}

    def fake_trigger_gate(repo_root=None, record_path=None, pytest_args=None):
        captured["repo_root"] = repo_root
        captured["record_path"] = record_path
        captured["pytest_args"] = pytest_args
        return {
            "gate": "G4",
            "passed": True,
            "status": "PASS",
            "record_path": str(record_path),
            "next_action": "Ready",
            "report": "G4 ok",
        }

    monkeypatch.setitem(
        cli.GATE_MODULES,
        "G4",
        SimpleNamespace(trigger_gate=fake_trigger_gate),
    )

    record_path = tmp_path / "g4.json"
    result = cli.run_cli(
        [
            "gate",
            "trigger",
            "G4",
            "--repo-root",
            str(tmp_path),
            "--record-path",
            str(record_path),
            "--pytest-arg",
            "tests/test_p4_08_g4_g6_gates.py",
        ]
    )

    assert result["command"] == "gate trigger"
    assert result["gate"] == "G4"
    assert result["passed"] is True
    assert result["exit_code"] == 0
    assert captured["repo_root"] == tmp_path.resolve()
    assert captured["record_path"] == record_path.resolve()
    assert captured["pytest_args"] == ("tests/test_p4_08_g4_g6_gates.py",)


def test_status_reports_memory_network_statistics(monkeypatch, tmp_path):
    cli = load_cli_module()

    class FakeNetwork:
        def get_statistics(self):
            return {"total_memory_nodes": 16, "registered_changes": 3}

        def get_network_state(self):
            return {
                "memory_nodes": {"FORM-009": {}},
                "events": [{"event_id": "EVT-0001"}],
                "propagation_history": [{"action_type": "restart"}],
            }

    monkeypatch.setattr(
        cli,
        "create_memory_network",
        lambda args, mutable, network_cls=cli.MemoryNetwork: (FakeNetwork(), tmp_path / ".versions.json"),
    )

    result = cli.run_cli(["status", "--repo-root", str(tmp_path)])

    assert result["command"] == "status"
    assert result["statistics"]["total_memory_nodes"] == 16
    assert result["summary"] == {
        "memory_node_count": 1,
        "event_count": 1,
        "propagation_history_count": 1,
    }


def test_events_ingests_gate_results_and_syncs(monkeypatch, tmp_path):
    cli = load_cli_module()

    gate_result_path = tmp_path / "g4-gate.json"
    gate_result_path.write_text(
        json.dumps(
            {
                "gate": "G4",
                "passed": True,
                "status": "PASS",
                "timestamp": "2026-04-08T00:00:00+00:00",
                "checks": [],
                "blockers": [],
                "next_action": "Ready",
            }
        ),
        encoding="utf-8",
    )

    class FakeNetworkWithEvents:
        def __init__(self):
            self.memory_events = []
            self.event_tracker = SimpleNamespace(
                events_db_id="memory-events-db",
                prepare_event_sync_payload=lambda event, events_db_id=None, database_properties=None: {
                    "property_map": {"title": "Name"},
                    "payload": {
                        "parent": {"database_id": events_db_id},
                        "properties": {"Name": {"title": []}},
                        "children": [],
                    },
                },
            )

        def record_gate_trigger_event(self, gate_result, unit_id=None):
            event = FakeEvent(f"MEM-EVT-{len(self.memory_events) + 1:04d}", gate_result["gate"])
            self.memory_events.append(event)
            return {"event": event, "memory_events": [event]}

    monkeypatch.setattr(
        cli,
        "create_memory_network_with_events",
        lambda args, mutable: (FakeNetworkWithEvents(), tmp_path / ".versions.json"),
    )

    result = cli.run_cli(
        [
            "events",
            "--repo-root",
            str(tmp_path),
            "--gate-result",
            str(gate_result_path),
            "--events-db-id",
            "memory-events-db",
            "--mock",
        ]
    )

    assert result["command"] == "events"
    assert result["mock_mode"] is True
    assert result["event_count"] == 1
    assert result["source_files"] == [str(gate_result_path.resolve())]
    assert result["events"] == [{"event_id": "MEM-EVT-0001", "gate": "G4"}]
    assert result["sync_results"][0]["mock_mode"] is True


def test_sync_code_mappings_applies_mapping_payload(monkeypatch, tmp_path):
    cli = load_cli_module()

    mappings_file = tmp_path / "mappings.json"
    mappings_file.write_text(
        json.dumps(
            {
                "FORM-009": [
                    {
                        "file_path": "knowledge_compiler/executables/formula_validator.py",
                        "mapping_type": "validates",
                        "confidence": 0.97,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeRegistry:
        def get_statistics(self):
            return {"total_mappings": 1, "total_units": 1}

    class FakeNetwork:
        def __init__(self):
            self.code_mapping_registry = FakeRegistry()

        def sync_code_mappings(self, mappings=None):
            return {
                "FORM-009": [
                    {
                        "unit_id": "FORM-009",
                        "file_path": "knowledge_compiler/executables/formula_validator.py",
                        "mapping_type": "validates",
                        "confidence": 0.97,
                    }
                ]
            }

    monkeypatch.setattr(
        cli,
        "create_memory_network",
        lambda args, mutable, network_cls=cli.MemoryNetwork: (FakeNetwork(), tmp_path / "isolated.versions.json"),
    )

    result = cli.run_cli(
        [
            "sync-code-mappings",
            "--repo-root",
            str(tmp_path),
            "--mappings-file",
            str(mappings_file),
        ]
    )

    assert result["command"] == "sync-code-mappings"
    assert result["requested_units"] == ["FORM-009"]
    assert result["synced_units"] == ["FORM-009"]
    assert result["total_mappings"] == 1
    assert result["code_mappings"]["FORM-009"][0]["mapping_type"] == "validates"


def test_version_list_returns_version_history(monkeypatch, tmp_path):
    cli = load_cli_module()

    class FakeVersion:
        def __init__(self, unit_id: str, version: str):
            self.unit_id = unit_id
            self.version = version
            self.content_hash = "a" * 64
            self.short_hash = "aaaaaaaa"
            self.parent_hash = None
            self.created_at = cli.datetime.fromisoformat("2026-04-08T00:00:00+00:00")
            self.created_by = "test-suite"
            self.status = SimpleNamespace(value="active")
            self.change_summary = "Initial version"
            self.metadata = {"unit_type": "formula"}

    class FakeRegistry:
        history = {"FORM-009": [FakeVersion("FORM-009", "v1.0")]}

        def get_history(self, unit_id):
            return list(self.history.get(unit_id, []))

        def get_current(self, unit_id):
            history = self.get_history(unit_id)
            return history[0] if history else None

    monkeypatch.setattr(
        cli,
        "create_versioned_registry",
        lambda args, mutable: (FakeRegistry(), tmp_path / ".versions.json"),
    )

    result = cli.run_cli(
        [
            "version",
            "list",
            "--repo-root",
            str(tmp_path),
            "--unit-id",
            "FORM-009",
        ]
    )

    assert result["command"] == "version list"
    assert result["unit_count"] == 1
    assert result["versions"][0]["unit_id"] == "FORM-009"
    assert result["versions"][0]["current_version"] == "v1.0"
    assert result["versions"][0]["history"][0]["change_summary"] == "Initial version"


def test_main_prints_json_and_returns_gate_exit_code(monkeypatch, capsys):
    cli = load_cli_module()
    monkeypatch.setattr(
        cli,
        "run_cli",
        lambda argv=None: {
            "ok": True,
            "command": "gate trigger",
            "gate": "G6",
            "passed": False,
            "exit_code": 1,
        },
    )

    exit_code = cli.main(["gate", "trigger", "G6"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '"gate": "G6"' in captured.out
