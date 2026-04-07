#!/usr/bin/env python3
"""
P4-06: MemoryNetwork orchestrator integration tests.

Covers:
1. Component initialization and shared state wiring
2. MemoryNode creation from registry + code mappings
3. Propagation orchestration
4. Governance against the post-change payload
5. Full register -> propagate -> govern -> sync lifecycle
"""

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.executables.diff_engine import ChangeType
from knowledge_compiler.memory_network import (
    GovernanceDecision,
    GovernanceEngine,
    MemoryNetwork,
    MemoryNode,
    PropagationEngine,
    PropagationEvent,
    PropagationDecision,
    VersionedKnowledgeRegistry,
)


KNOWLEDGE_COMPILER_PATH = REPO_ROOT / "knowledge_compiler"


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
    return MemoryNetwork(
        base_path=KNOWLEDGE_COMPILER_PATH,
        version_db_path=tmp_path / ".versions.json",
    )


class TestMemoryNetworkInitialization:
    def test_initialization_integrates_phase4_components(self, network):
        assert isinstance(network.versioned_registry, VersionedKnowledgeRegistry)
        assert isinstance(network.propagation_engine, PropagationEngine)
        assert isinstance(network.governance_engine, GovernanceEngine)
        assert network.code_mapping_registry is network.versioned_registry.code_mapping_registry
        assert network.governance_engine.propagation_engine is network.propagation_engine
        assert len(network.memory_nodes) == len(network.versioned_registry.versions)
        assert "FORM-009" in network.memory_nodes


class TestMemoryNodeIntegration:
    def test_create_memory_node_reflects_registry_and_mapping_state(self, network):
        synced = network.sync_code_mappings(
            {
                "FORM-009": [
                    {
                        "file_path": "knowledge_compiler/executables/formula_validator.py",
                        "mapping_type": "validates",
                        "confidence": 0.97,
                    },
                    {
                        "file_path": "tests/test_p4_06_memory_network.py",
                        "mapping_type": "references",
                        "confidence": 0.60,
                    },
                ]
            }
        )

        node = network.create_memory_node("FORM-009")

        assert isinstance(node, MemoryNode)
        assert node.version == network.versioned_registry.get_current("FORM-009").version
        assert node.code_mappings == [
            "knowledge_compiler/executables/formula_validator.py",
            "tests/test_p4_06_memory_network.py",
        ]
        assert len(synced["FORM-009"]) == 2


class TestChangeLifecycle:
    def test_propagate_change_uses_propagation_engine(self, network):
        decision = network.propagate_change(make_formula_change())

        assert isinstance(decision, PropagationDecision)
        assert decision.should_propagate is True
        assert decision.action_type == network.propagation_engine.ACTION_RESTART
        assert decision.target_executables == ["EXEC-FORMULA-VALIDATOR-001"]
        assert len(network.propagation_engine.get_decision_history()) == 1

    def test_govern_change_evaluates_post_change_payload(self, network):
        decision = network.govern_change(make_formula_change(new_value="TODO"))

        assert decision.status == GovernanceDecision.REJECTED
        assert any("Placeholder" in reason for reason in decision.reasons)

    def test_register_change_runs_full_lifecycle_and_updates_state(self, network):
        result = network.register_change(
            "FORM-009",
            make_formula_change(
                code_mappings=[
                    {
                        "file_path": "tests/test_p4_06_memory_network.py",
                        "mapping_type": "references",
                        "confidence": 0.55,
                    }
                ]
            ),
        )

        assert result["version"].version == "v1.1"
        assert result["memory_node"].version == "v1.1"
        assert result["propagation_decision"].action_type == network.propagation_engine.ACTION_RESTART
        assert result["governance_decision"].status == GovernanceDecision.APPROVED
        assert isinstance(result["event"], PropagationEvent)
        assert result["event"].source_unit == "FORM-009"

        mapped_files = network.code_mapping_registry.get_files_for_unit("FORM-009")
        assert mapped_files == [
            "knowledge_compiler/executables/formula_validator.py",
            "tests/test_p4_06_memory_network.py",
        ]
        assert network.versioned_registry.get_current("FORM-009").version == "v1.1"

        state = network.get_network_state()
        stats = network.get_statistics()

        assert state["memory_nodes"]["FORM-009"]["version"] == "v1.1"
        assert len(state["events"]) == 1
        assert state["events"][0]["governance_decision"] == GovernanceDecision.APPROVED
        assert stats["registered_changes"] == 1
        assert stats["propagation_events"] == 1
        assert stats["propagation_action_counts"] == {
            network.propagation_engine.ACTION_RESTART: 1
        }
        assert stats["governance_status_counts"] == {
            GovernanceDecision.APPROVED: 1
        }
        assert stats["code_mapping_registry"]["total_mappings"] == 2
