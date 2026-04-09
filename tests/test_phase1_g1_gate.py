#!/usr/bin/env python3
"""
Tests for G1-P1 Gate: ActionPlan Executability Gate

Tests the validation of ActionPlan executability before execution.
"""

import pytest

from knowledge_compiler.phase1.gates import (
    GateStatus,
    ActionPlanExecutabilityGate,
)
from knowledge_compiler.phase1.nl_postprocess import (
    ActionType,
    Action,
    ActionPlan,
)
from knowledge_compiler.phase1.schema import ResultManifest, ResultAsset


class TestActionPlanExecutabilityGate:
    """Test ActionPlanExecutabilityGate"""

    def test_gate_creation(self):
        """Test creating gate"""
        gate = ActionPlanExecutabilityGate()
        assert gate.GATE_ID == "G1-P1"
        assert gate.GATE_NAME == "ActionPlan Executability Gate"

    def test_executable_plan_passes(self):
        """Test that an executable plan passes the gate"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={"field": "pressure", "plot_type": "contour"},
                    confidence=0.9,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.9,
            raw_instruction="Generate pressure contour",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p.obj")],
        )

        result = gate.check_action_plan(plan, manifest)

        assert result.gate_id == "G1-P1"
        assert result.status == GateStatus.PASS
        assert result.score >= 70.0
        assert len(result.errors) == 0

    def test_missing_assets_fails(self):
        """Test that missing assets cause failure"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={"field": "pressure", "plot_type": "contour"},
                    confidence=0.5,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=["field_data"],  # Missing!
            confidence=0.5,
            raw_instruction="Generate pressure contour",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[],  # No assets available
        )

        result = gate.check_action_plan(plan, manifest)

        assert result.status == GateStatus.FAIL
        assert result.score < 60.0
        assert len(result.errors) > 0
        assert "missing" in str(result.errors).lower()

    def test_low_confidence_warns(self):
        """Test that low confidence generates warning"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={"field": "pressure", "plot_type": "contour"},
                    confidence=0.4,  # Low confidence
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.4,  # Below 0.5 threshold
            raw_instruction="Generate pressure contour",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p.obj")],
        )

        result = gate.check_action_plan(plan, manifest)

        # Should pass but with warning
        assert result.score < 90.0
        assert len(result.warnings) > 0
        assert any("confidence" in w.lower() for w in result.warnings)

    def test_parameter_completeness_checked(self):
        """Test that parameter completeness is validated"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={"field": "pressure"},  # Missing plot_type!
                    confidence=0.8,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.8,
            raw_instruction="Generate pressure plot",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p.obj")],
        )

        result = gate.check_action_plan(plan, manifest)

        # Should have warning about missing parameter
        assert len(result.warnings) > 0

    def test_duplicate_actions_detected(self):
        """Test that duplicate actions are detected"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={"field": "pressure", "plot_type": "contour"},
                    confidence=0.9,
                    requires_assets=["field_data"],
                ),
                Action(
                    action_type=ActionType.GENERATE_PLOT,  # Duplicate!
                    parameters={"field": "pressure", "plot_type": "contour"},
                    confidence=0.9,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.9,
            raw_instruction="Generate pressure contour twice",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p.obj")],
        )

        result = gate.check_action_plan(plan, manifest)

        # Should detect duplicates
        assert len(result.warnings) > 0
        assert any("duplicate" in w.lower() for w in result.warnings)

    def test_severity_is_block(self):
        """Test that G1 gate has BLOCK severity"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[],
            detected_intent="plot",
            missing_assets=[],
            confidence=1.0,
            raw_instruction="Test",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[],
        )

        result = gate.check_action_plan(plan, manifest)

        assert result.severity == "BLOCK"


class TestGateIntegration:
    """Test Gate integration with NL Postprocess"""

    def test_nl_to_gate_workflow(self):
        """Test full workflow: NL instruction -> ActionPlan -> Gate"""
        from knowledge_compiler.phase1.nl_postprocess import NLPostprocessExecutor

        executor = NLPostprocessExecutor()
        gate = ActionPlanExecutabilityGate()

        instruction = "生成压力云图"
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p.obj")],
        )

        # Parse instruction
        plan = executor.parse_instruction(instruction, manifest)

        # Check executability
        gate_result = gate.check_action_plan(plan, manifest)

        assert gate_result.status in [GateStatus.PASS, GateStatus.WARN]
        assert gate_result.metadata["intent"] == "plot"
        assert gate_result.metadata["num_actions"] >= 1

    def test_nl_instruction_with_missing_resources(self):
        """Test that missing resources are caught"""
        from knowledge_compiler.phase1.nl_postprocess import NLPostprocessExecutor

        executor = NLPostprocessExecutor()
        gate = ActionPlanExecutabilityGate()

        instruction = "生成速度矢量图"
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[],  # No assets!
        )

        plan = executor.parse_instruction(instruction, manifest)
        gate_result = gate.check_action_plan(plan, manifest)

        # Should fail due to missing assets
        assert gate_result.status == GateStatus.FAIL
        assert "missing" in str(gate_result.errors).lower()


class TestGateChecklist:
    """Test Gate checklist items"""

    def test_checklist_items_present(self):
        """Test that all checklist items are created"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={"field": "pressure", "plot_type": "contour"},
                    confidence=0.9,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.9,
            raw_instruction="Generate pressure contour",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p.obj")],
        )

        result = gate.check_action_plan(plan, manifest)

        # Check that all expected items are in checklist
        item_names = {item.item for item in result.checklist}
        expected_items = {
            "missing_assets",
            "parameter_completeness",
            "asset_mapping",
            "action_conflicts",
            "confidence_score",
        }

        assert expected_items.issubset(item_names)

    def test_checklist_pass_rate(self):
        """Test GateResult.get_pass_rate() method"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={"field": "pressure", "plot_type": "contour"},
                    confidence=0.9,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.9,
            raw_instruction="Generate pressure contour",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p.obj")],
        )

        result = gate.check_action_plan(plan, manifest)

        # All items should pass
        assert result.get_pass_rate() == 100.0


class TestGateWithMultipleActions:
    """Test gate with complex multi-action plans"""

    def test_multiple_actions_all_valid(self):
        """Test plan with multiple valid actions"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={"field": "pressure", "plot_type": "contour"},
                    confidence=0.9,
                    requires_assets=["field_data"],
                ),
                Action(
                    action_type=ActionType.EXTRACT_SECTION,
                    parameters={"plane": "z=0.5", "field": "velocity"},
                    confidence=0.85,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="mixed",
            missing_assets=[],
            confidence=0.875,
            raw_instruction="Generate plots and sections",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[
                ResultAsset(asset_type="field", path="p.obj"),
                ResultAsset(asset_type="field", path="U.obj"),
            ],
        )

        result = gate.check_action_plan(plan, manifest)

        assert result.status == GateStatus.PASS
        assert result.metadata["num_actions"] == 2

    def test_comparison_action_validation(self):
        """Test comparison action validation"""
        gate = ActionPlanExecutabilityGate()

        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.COMPARE_DATA,
                    parameters={
                        "items": ["inlet", "outlet"],
                        "field": "pressure",
                        "comparison_type": "side_by_side",
                    },
                    confidence=0.8,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="compare",
            missing_assets=[],
            confidence=0.8,
            raw_instruction="Compare inlet and outlet pressure",
        )

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p.obj")],
        )

        result = gate.check_action_plan(plan, manifest)

        # Comparison action should have required parameters
        param_items = [c for c in result.checklist if c.item == "parameter_completeness"]
        assert len(param_items) == 1
        assert param_items[0].result == GateStatus.PASS
