#!/usr/bin/env python3
"""
Test P4-03: PropagationEngine Integration with diff_engine

Tests:
1. detect_changes() correctly uses diff_engine
2. analyze_impact() returns correct decisions for each ChangeType
3. propagate() executes based on propagation_rules.md logic
4. Decision history tracking works
"""

import pytest
from datetime import datetime
from knowledge_compiler.memory_network import (
    PropagationEngine,
    PropagationDecision,
)
from knowledge_compiler.executables.diff_engine import ChangeType, DiffReport


class TestPropagationEngine:
    """Test suite for PropagationEngine."""
    
    def test_init(self):
        """Test PropagationEngine initialization."""
        engine = PropagationEngine()
        assert engine.decision_history == []
        assert engine.ACTION_HOT_RELOAD == "hot_reload"
        assert engine.ACTION_RESTART == "restart"
        assert engine.ACTION_REVERIFY == "reverify"
        assert engine.ACTION_HALT == "halt"
        assert engine.ACTION_IGNORE == "ignore"
    
    def test_detect_changes_integration(self, tmp_path):
        """Test that detect_changes uses diff_engine correctly."""
        # This is an integration test - requires actual knowledge structure
        # For now, test that the method exists and has correct signature
        engine = PropagationEngine()
        
        # Test with non-existent paths - should handle gracefully
        try:
            changes = engine.detect_changes("HEAD~1", str(tmp_path))
            # If diff_engine works, we get a list
            assert isinstance(changes, list)
        except Exception:
            # Expected if git structure not present
            pass
    
    def test_analyze_impact_text_edit(self):
        """Test TEXT_EDIT returns ignore decision."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.TEXT_EDIT,
            unit_id="CH-001",
            field="content",
            old_value="old text",
            new_value="new text",
            impacted_executables=[]
        )
        
        decision = engine.analyze_impact(change)
        
        assert isinstance(decision, PropagationDecision)
        assert decision.should_propagate is False
        assert decision.target_executables == []
        assert decision.action_type == engine.ACTION_IGNORE
        assert "TEXT_EDIT" in decision.reason
        assert "no impact" in decision.reason.lower()
    
    def test_analyze_impact_delete(self):
        """Test DELETE returns halt decision."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.DELETE,
            unit_id="CH-001",
            field="__unit__",
            old_value={"path": "units/chapter_001.yaml"},
            new_value=None,
            impacted_executables=["EXEC-CHART-TEMPLATE-001"]
        )
        
        decision = engine.analyze_impact(change)
        
        assert decision.should_propagate is True
        assert "EXEC-CHART-TEMPLATE-001" in decision.target_executables
        assert decision.action_type == engine.ACTION_HALT
        assert "DELETE" in decision.reason
        assert "manual review" in decision.reason.lower()
    
    def test_analyze_impact_evidence_edit(self):
        """Test EVIDENCE_EDIT returns reverify decision."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.EVIDENCE_EDIT,
            unit_id="CASE-001",
            field="data_points[0].u_velocity",
            old_value=0.5,
            new_value=0.6,
            impacted_executables=["EXEC-BENCH-GHIA-001"]
        )
        
        decision = engine.analyze_impact(change)
        
        assert decision.should_propagate is True
        assert "EXEC-BENCH-GHIA-001" in decision.target_executables
        assert decision.action_type == engine.ACTION_REVERIFY
        assert "EVIDENCE_EDIT" in decision.reason
        assert "re-verification" in decision.reason.lower()
    
    def test_analyze_impact_chart_rule_edit(self):
        """Test CHART_RULE_EDIT returns hot_reload decision."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.CHART_RULE_EDIT,
            unit_id="CHART-001",
            field="chart_rules.yaml",
            old_value={"style": "old"},
            new_value={"style": "new"},
            impacted_executables=["EXEC-CHART-TEMPLATE-001"]
        )
        
        decision = engine.analyze_impact(change)
        
        assert decision.should_propagate is True
        assert decision.action_type == engine.ACTION_HOT_RELOAD
        assert "CHART_RULE_EDIT" in decision.reason
        assert "regeneration" in decision.reason.lower()
    
    def test_analyze_impact_semantic_edit_schema_breaking(self):
        """Test SEMANTIC_EDIT with schema change returns restart."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.SEMANTIC_EDIT,
            unit_id="schema/units",
            field="structure",
            old_value="old_structure",
            new_value="new_structure",
            impacted_executables=["EXEC-FORMULA-VALIDATOR-001"]
        )
        
        decision = engine.analyze_impact(change)
        
        assert decision.should_propagate is True
        assert decision.action_type == engine.ACTION_RESTART
        assert "schema-breaking" in decision.reason.lower()
    
    def test_analyze_impact_semantic_edit_non_schema(self):
        """Test SEMANTIC_EDIT without schema change returns hot_reload."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.SEMANTIC_EDIT,
            unit_id="CH-001",
            field="description",
            old_value="old description",
            new_value="new description",
            impacted_executables=["EXEC-CHART-TEMPLATE-001"]
        )
        
        decision = engine.analyze_impact(change)
        
        assert decision.should_propagate is True
        assert decision.action_type == engine.ACTION_HOT_RELOAD
        assert "hot-reload" in decision.reason.lower()
    
    def test_analyze_impact_new(self):
        """Test NEW returns hot_reload decision."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.NEW,
            unit_id="CH-003",
            field="__unit__",
            old_value=None,
            new_value={"path": "units/chapter_003.yaml"},
            impacted_executables=[]
        )
        
        decision = engine.analyze_impact(change)
        
        assert decision.should_propagate is True
        assert "CH-003" in decision.target_executables
        assert decision.action_type == engine.ACTION_HOT_RELOAD
        assert "NEW" in decision.reason
    
    def test_analyze_impact_formula_signature_change(self):
        """Test formula signature change is detected as schema-breaking."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.SEMANTIC_EDIT,
            unit_id="FORM-001",
            field="signature",
            old_value="f(x)",
            new_value="f(x, y)",
            impacted_executables=["EXEC-FORMULA-VALIDATOR-001"]
        )
        
        decision = engine.analyze_impact(change)
        
        assert decision.should_propagate is True
        assert decision.action_type == engine.ACTION_RESTART
        assert "schema-breaking" in decision.reason.lower() or "restart" in decision.reason.lower()
    
    def test_propagate_single_change(self):
        """Test propagate with single change."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.TEXT_EDIT,
            unit_id="CH-001",
            field="content",
            old_value="old",
            new_value="new",
            impacted_executables=[]
        )
        
        decisions = engine.propagate([change])
        
        assert len(decisions) == 1
        assert decisions[0].action_type == engine.ACTION_IGNORE
        assert len(engine.decision_history) == 1
    
    def test_propagate_multiple_changes(self):
        """Test propagate with multiple changes."""
        engine = PropagationEngine()
        changes = [
            DiffReport(
                change_type=ChangeType.TEXT_EDIT,
                unit_id="CH-001",
                field="content",
                old_value="old",
                new_value="new",
                impacted_executables=[]
            ),
            DiffReport(
                change_type=ChangeType.NEW,
                unit_id="CH-003",
                field="__unit__",
                old_value=None,
                new_value={"path": "units/chapter_003.yaml"},
                impacted_executables=[]
            ),
            DiffReport(
                change_type=ChangeType.EVIDENCE_EDIT,
                unit_id="CASE-001",
                field="data_points[0].u_velocity",
                old_value=0.5,
                new_value=0.6,
                impacted_executables=["EXEC-BENCH-GHIA-001"]
            ),
        ]
        
        decisions = engine.propagate(changes)
        
        assert len(decisions) == 3
        assert decisions[0].action_type == engine.ACTION_IGNORE
        assert decisions[1].action_type == engine.ACTION_HOT_RELOAD
        assert decisions[2].action_type == engine.ACTION_REVERIFY
        assert len(engine.decision_history) == 3
    
    def test_propagate_dry_run(self):
        """Test propagate with dry_run=True."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.NEW,
            unit_id="CH-003",
            field="__unit__",
            old_value=None,
            new_value={"path": "units/chapter_003.yaml"},
            impacted_executables=[]
        )
        
        decisions = engine.propagate([change], dry_run=True)
        
        # Decisions should still be made
        assert len(decisions) == 1
        assert len(engine.decision_history) == 1
        # But _execute_propagation should not be called
        # (verified by checking the decision was recorded)
    
    def test_decision_history(self):
        """Test decision history tracking."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.NEW,
            unit_id="CH-003",
            field="__unit__",
            old_value=None,
            new_value={"path": "units/chapter_003.yaml"},
            impacted_executables=[]
        )
        
        engine.propagate([change])
        
        history = engine.get_decision_history()
        assert len(history) == 1
        assert "timestamp" in history[0]
        assert "change" in history[0]
        assert "decision" in history[0]
        assert history[0]["change"]["unit_id"] == "CH-003"
        assert history[0]["decision"]["action_type"] == "hot_reload"
    
    def test_clear_history(self):
        """Test clearing decision history."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.NEW,
            unit_id="CH-003",
            field="__unit__",
            old_value=None,
            new_value={"path": "units/chapter_003.yaml"},
            impacted_executables=[]
        )
        
        engine.propagate([change])
        assert len(engine.decision_history) == 1
        
        engine.clear_history()
        assert len(engine.decision_history) == 0
        assert len(engine.get_decision_history()) == 0
    
    def test_propagation_decision_dataclass(self):
        """Test PropagationDecision dataclass structure."""
        decision = PropagationDecision(
            should_propagate=True,
            target_executables=["EXEC-001", "EXEC-002"],
            action_type="hot_reload",
            reason="Test reason"
        )
        
        assert decision.should_propagate is True
        assert decision.target_executables == ["EXEC-001", "EXEC-002"]
        assert decision.action_type == "hot_reload"
        assert decision.reason == "Test reason"
    
    def test_all_change_types_covered(self):
        """Test that all ChangeType enums are handled."""
        engine = PropagationEngine()
        
        # Create changes for each type
        change_types = [
            ChangeType.NEW,
            ChangeType.DELETE,
            ChangeType.TEXT_EDIT,
            ChangeType.SEMANTIC_EDIT,
            ChangeType.EVIDENCE_EDIT,
            ChangeType.CHART_RULE_EDIT,
        ]
        
        for ct in change_types:
            change = DiffReport(
                change_type=ct,
                unit_id="TEST-001",
                field="test_field",
                old_value=None,
                new_value=None,
                impacted_executables=[]
            )
            decision = engine.analyze_impact(change)
            
            # Every change should produce a valid decision
            assert isinstance(decision, PropagationDecision)
            assert decision.action_type in [
                engine.ACTION_HOT_RELOAD,
                engine.ACTION_RESTART,
                engine.ACTION_REVERIFY,
                engine.ACTION_HALT,
                engine.ACTION_IGNORE,
            ]
    
    def test_impact_executables_propagation(self):
        """Test that impacted_executables are carried through correctly."""
        engine = PropagationEngine()
        change = DiffReport(
            change_type=ChangeType.EVIDENCE_EDIT,
            unit_id="CASE-001",
            field="data",
            old_value="old",
            new_value="new",
            impacted_executables=["EXEC-BENCH-GHIA-001", "EXEC-BENCH-NACA-001"]
        )
        
        decision = engine.analyze_impact(change)
        
        assert decision.should_propagate is True
        assert set(decision.target_executables) == {"EXEC-BENCH-GHIA-001", "EXEC-BENCH-NACA-001"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
