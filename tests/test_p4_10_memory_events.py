#!/usr/bin/env python3
"""
P4-10: Memory Events Notion sync tests.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import notion_cfd_loop

from knowledge_compiler.executables.diff_engine import ChangeType, DiffReport
from knowledge_compiler.memory_network import (
    GovernanceDecision,
    PropagationDecision,
    PropagationEvent,
    UnitVersion,
    VersionStatus,
)
from knowledge_compiler.memory_network.notion_memory_events import (
    MemoryEventTracker,
    MemoryEventType,
    MemoryNetworkWithEvents,
)


KNOWLEDGE_COMPILER_PATH = REPO_ROOT / "knowledge_compiler"


def _memory_events_db_schema() -> dict:
    return {
        "properties": {
            "Name": {"title": {}},
            "Event Type": {"select": {}},
            "Unit ID": {"rich_text": {}},
            "Timestamp": {"date": {}},
            "Details": {"rich_text": {}},
        }
    }


def _rich_text_content(prop: dict) -> str:
    return "".join(item["text"]["content"] for item in prop.get("rich_text", []))


def _children_text(children: list[dict]) -> str:
    lines = []
    for block in children:
        block_type = block["type"]
        for item in block[block_type]["rich_text"]:
            lines.append(item["text"]["content"])
    return "\n".join(lines)


def _gate_result(
    gate: str = "G4",
    passed: bool = True,
    status: str = "PASS",
    detail: str = "Gate execution recorded",
) -> dict:
    return {
        "gate": gate,
        "passed": passed,
        "status": status,
        "timestamp": "2026-04-08T00:00:00+00:00",
        "checks": [
            {
                "check": "gate_execution",
                "passed": passed,
                "detail": detail,
            }
        ],
        "blockers": [] if passed else [detail],
        "next_action": "Continue" if passed else "Investigate",
    }


def make_formula_change(
    new_value: str = "GCI_12 = abs(e_12) / (r^p - 1) * 100%",
    code_mappings=None,
):
    return {
        "unit_id": "FORM-009",
        "change_type": ChangeType.SEMANTIC_EDIT,
        "field": "definition",
        "old_value": "GCI_{12} = |epsilon_{12}| / (r^p - 1) * 100%",
        "new_value": new_value,
        "impacted_executables": ["EXEC-FORMULA-VALIDATOR-001"],
        "created_by": "test-suite",
        "change_summary": "Clarify GCI formula wording",
        "code_mappings": code_mappings or [],
    }


@pytest.fixture
def network(tmp_path, monkeypatch):
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mplconfig"))
    return MemoryNetworkWithEvents(
        base_path=KNOWLEDGE_COMPILER_PATH,
        version_db_path=tmp_path / ".versions.json",
    )


def test_record_change_result_builds_unit_created_version_and_propagation_events():
    tracker = MemoryEventTracker(events_db_id="memory-events-db")
    created_at = datetime.fromisoformat("2026-04-08T00:00:00+00:00")

    previous_version = UnitVersion(
        unit_id="FORM-NEW-001",
        version="v1.0",
        content_hash="a" * 64,
        parent_hash=None,
        created_at=created_at,
        created_by="system",
        status=VersionStatus.ACTIVE,
        change_summary="Initial version",
        metadata={"source_file": "units/formulas.yaml", "unit_type": "formula"},
    )
    new_version = UnitVersion(
        unit_id="FORM-NEW-001",
        version="v1.1",
        content_hash="b" * 64,
        parent_hash=previous_version.content_hash,
        created_at=created_at,
        created_by="test-suite",
        status=VersionStatus.ACTIVE,
        change_summary="New unit published",
        metadata={"source_file": "units/formulas.yaml", "unit_type": "formula"},
    )
    diff_report = DiffReport(
        change_type=ChangeType.NEW,
        unit_id="FORM-NEW-001",
        field="definition",
        old_value=None,
        new_value="New formula definition",
        impacted_executables=["EXEC-FORMULA-VALIDATOR-001"],
    )
    propagation_decision = PropagationDecision(
        should_propagate=True,
        target_executables=["EXEC-FORMULA-VALIDATOR-001"],
        action_type="hot_reload",
        reason="NEW unit FORM-NEW-001 - hot-reload new knowledge",
    )
    governance_decision = GovernanceDecision(
        status=GovernanceDecision.APPROVED,
        reasons=["All governance checks passed"],
        warnings=[],
    )
    propagation_event = PropagationEvent(
        event_id="EVT-0001",
        change_type=ChangeType.NEW,
        source_unit="FORM-NEW-001",
        impact_targets=["EXEC-FORMULA-VALIDATOR-001"],
        governance_decision=GovernanceDecision.APPROVED,
        reason="hot_reload: All governance checks passed",
        timestamp=created_at,
    )

    events = tracker.record_change_result(
        {
            "unit_id": "FORM-NEW-001",
            "version": new_version,
            "previous_version": previous_version,
            "propagation_decision": propagation_decision,
            "governance_decision": governance_decision,
            "event": propagation_event,
        },
        diff_report=diff_report,
        context={"created_by": "test-suite"},
        unit_existed_before=False,
    )

    assert [event.event_type for event in events] == [
        MemoryEventType.UNIT_CREATED,
        MemoryEventType.VERSION_CREATED,
        MemoryEventType.PROPAGATION_EXECUTED,
    ]
    assert events[0].details["diff_report"]["change_type"] == "NEW"
    assert events[1].details["version"]["version"] == "v1.1"
    assert events[2].details["propagation_chain"] == [
        "FORM-NEW-001",
        "EXEC-FORMULA-VALIDATOR-001",
    ]


def test_memory_network_with_events_register_change_records_update_propagation_and_mapping_events(
    network,
):
    result = network.register_change(
        "FORM-009",
        make_formula_change(
            code_mappings=[
                {
                    "file_path": "tests/test_p4_10_memory_events.py",
                    "mapping_type": "references",
                    "confidence": 0.61,
                }
            ]
        ),
    )

    event_types = [event.event_type for event in result["memory_events"]]

    assert MemoryEventType.CODE_MAPPING_CHANGED in event_types
    assert MemoryEventType.UNIT_UPDATED in event_types
    assert MemoryEventType.VERSION_CREATED in event_types
    assert MemoryEventType.PROPAGATION_EXECUTED in event_types

    mapping_event = next(
        event
        for event in result["memory_events"]
        if event.event_type == MemoryEventType.CODE_MAPPING_CHANGED
    )
    added_paths = {
        mapping["file_path"]
        for mapping in mapping_event.details["added_mappings"]
    }
    assert added_paths == {
        "knowledge_compiler/executables/formula_validator.py",
        "tests/test_p4_10_memory_events.py",
    }

    propagation_event = next(
        event
        for event in result["memory_events"]
        if event.event_type == MemoryEventType.PROPAGATION_EXECUTED
    )
    assert propagation_event.unit_id == "FORM-009"
    assert propagation_event.details["propagation_chain"][0] == "FORM-009"
    assert "EXEC-FORMULA-VALIDATOR-001" in propagation_event.details["impact_targets"]


def test_record_gate_trigger_uses_gate_namespace_and_status():
    tracker = MemoryEventTracker(events_db_id="memory-events-db")

    event = tracker.record_gate_trigger(
        _gate_result(gate="G6", passed=False, status="FAIL", detail="Manual review required")
    )

    assert event.event_type == MemoryEventType.GATE_TRIGGERED
    assert event.unit_id == "GATE:G6"
    assert event.details["gate"] == "G6"
    assert event.details["status"] == "FAIL"
    assert event.details["blockers"] == ["Manual review required"]


def test_sync_event_to_notion_queries_schema_and_builds_payload(monkeypatch):
    tracker = MemoryEventTracker(events_db_id="memory-events-db")
    event = tracker.record_gate_trigger(_gate_result(gate="G4"))

    get_calls: list[str] = []
    post_call: dict = {}

    def fake_get(endpoint: str) -> dict:
        get_calls.append(endpoint)
        return _memory_events_db_schema()

    def fake_post(endpoint: str, data: dict) -> dict:
        post_call["endpoint"] = endpoint
        post_call["data"] = data
        return {"id": "memory-event-page-123"}

    monkeypatch.setattr(notion_cfd_loop, "notion_get", fake_get)
    monkeypatch.setattr(notion_cfd_loop, "notion_post", fake_post)

    sync_result = tracker.sync_event_to_notion(event)

    assert sync_result["success"] is True
    assert sync_result["page_id"] == "memory-event-page-123"
    assert get_calls == ["databases/memory-events-db"]
    assert post_call["endpoint"] == "pages"

    payload = post_call["data"]
    props = payload["properties"]
    assert payload["parent"] == {"database_id": "memory-events-db"}
    assert props["Event Type"]["select"]["name"] == "GateTriggered"
    assert _rich_text_content(props["Unit ID"]) == "GATE:G4"
    assert props["Timestamp"]["date"]["start"] == "2026-04-08T00:00:00+00:00"
    assert "gate_execution" in _rich_text_content(props["Details"])

    children_text = _children_text(payload["children"])
    assert "Memory Event Summary" in children_text
    assert "Details" in children_text
    assert "GATE:G4" in children_text
