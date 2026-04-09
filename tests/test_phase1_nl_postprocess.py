#!/usr/bin/env python3
"""
Tests for NL Postprocess Executor (F2)

Tests the natural language to action plan conversion.
"""

import pytest

from knowledge_compiler.phase1.nl_postprocess import (
    ActionType,
    Action,
    ActionPlan,
    ActionLog,
    NLPostprocessExecutor,
    create_action_plan,
    execute_action_plan,
)
from knowledge_compiler.phase1.schema import (
    ResultManifest,
    ResultAsset,
    ProblemType,
    PlotSpec,
    MetricSpec,
)


@pytest.fixture
def basic_manifest():
    """Create a basic ResultManifest for testing"""
    return ResultManifest(
        solver_type="openfoam",
        case_name="test_case",
        result_root="/path/to/results",
        assets=[
            ResultAsset(
                asset_type="field",
                path="postProcessing/velocity_cloud.obj",
                description="Velocity field data",
            ),
            ResultAsset(
                asset_type="contour_plot",
                path="postProcessing/pressure_contour.png",
                description="Pressure contour",
            ),
        ],
    )


class TestActionType:
    """Test ActionType enum"""

    def test_all_action_types_defined(self):
        """All required action types should be defined"""
        assert ActionType.GENERATE_PLOT
        assert ActionType.EXTRACT_SECTION
        assert ActionType.CALCULATE_METRIC
        assert ActionType.COMPARE_DATA
        assert ActionType.REORDER_CONTENT


class TestAction:
    """Test Action dataclass"""

    def test_create_action(self):
        """Test creating an Action"""
        action = Action(
            action_type=ActionType.GENERATE_PLOT,
            parameters={"field": "pressure", "plot_type": "contour"},
            confidence=0.8,
            requires_assets=["field_data"],
        )

        assert action.action_type == ActionType.GENERATE_PLOT
        assert action.parameters["field"] == "pressure"
        assert action.confidence == 0.8


class TestActionPlan:
    """Test ActionPlan dataclass"""

    def test_create_action_plan(self):
        """Test creating an ActionPlan"""
        actions = [
            Action(
                action_type=ActionType.GENERATE_PLOT,
                parameters={"field": "pressure"},
                confidence=0.9,
                requires_assets=["field_data"],
            ),
            Action(
                action_type=ActionType.EXTRACT_SECTION,
                parameters={"plane": "midplane"},
                confidence=0.7,
                requires_assets=["field_data"],
            ),
        ]

        plan = ActionPlan(
            actions=actions,
            detected_intent="mixed",
            missing_assets=[],
            confidence=0.8,
            raw_instruction="Generate pressure contour and midplane section",
        )

        assert len(plan.actions) == 2
        assert plan.is_executable()
        assert plan.detected_intent == "mixed"

    def test_action_plan_with_missing_assets(self):
        """Test ActionPlan with missing assets"""
        plan = ActionPlan(
            actions=[],
            detected_intent="plot",
            missing_assets=["field_data"],
            confidence=0.5,
            raw_instruction="Generate plot (no data available)",
        )

        assert not plan.is_executable()
        assert "field_data" in plan.missing_assets

    def test_action_plan_to_dict(self):
        """Test ActionPlan serialization"""
        action = Action(
            action_type=ActionType.GENERATE_PLOT,
            parameters={"field": "velocity"},
            confidence=0.7,
            requires_assets=[],
        )

        plan = ActionPlan(
            actions=[action],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.7,
            raw_instruction="Generate velocity plot",
        )

        result = plan.to_dict()

        assert result["actions"][0]["action_type"] == "generate_plot"
        assert result["confidence"] == 0.7
        assert result["raw_instruction"] == "Generate velocity plot"


class TestNLPostprocessExecutor:
    """Test NLPostprocessExecutor"""

    def test_executor_creation(self):
        """Test creating executor"""
        executor = NLPostprocessExecutor()
        assert executor is not None
        assert hasattr(executor, "_plot_keywords")
        assert hasattr(executor, "_section_keywords")

    def test_parse_plot_instruction_cloud(self):
        """Test parsing '生成压力云图'"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[
                ResultAsset(asset_type="field", path="U.obj"),
            ],
        )

        plan = executor.parse_instruction("生成压力云图", manifest)

        assert plan.detected_intent == "plot"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == ActionType.GENERATE_PLOT
        assert plan.actions[0].parameters["plot_type"] == "contour"
        assert plan.actions[0].parameters["field"] == "pressure"

    def test_parse_plot_instruction_line(self):
        """Test parsing '画速度等值线'"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="U.obj")],
        )

        plan = executor.parse_instruction("画速度等值线", manifest)

        assert plan.detected_intent == "plot"
        assert plan.actions[0].action_type == ActionType.GENERATE_PLOT
        assert plan.actions[0].parameters["plot_type"] == "line"

    def test_parse_section_instruction(self):
        """Test parsing '提取z=0.5平面的温度场'"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="T.obj")],
        )

        plan = executor.parse_instruction("提取z=0.5平面的温度场", manifest)

        assert plan.detected_intent == "section"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == ActionType.EXTRACT_SECTION
        assert plan.actions[0].parameters["plane"] == "z=0.5"
        assert plan.actions[0].parameters["field"] == "temperature"

    def test_parse_comparison_instruction(self):
        """Test parsing '对比inlet和outlet的压力'"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p.obj")],
        )

        plan = executor.parse_instruction("对比inlet和outlet的压力", manifest)

        assert plan.detected_intent == "compare"
        assert len(plan.actions) >= 1
        # Should find inlet and outlet in the comparison

    def test_parse_metric_instruction(self):
        """Test parsing '计算阻力系数'"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="U.obj")],
        )

        plan = executor.parse_instruction("计算阻力系数", manifest)

        assert plan.detected_intent == "metric"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == ActionType.CALCULATE_METRIC
        assert "coefficient" in plan.actions[0].parameters["metric_type"]

    def test_parse_reorder_instruction(self):
        """Test parsing '按报告顺序：总览→截面→图表'"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[],
        )

        plan = executor.parse_instruction("按报告顺序：总览→截面→图表", manifest)

        assert plan.detected_intent == "reorder"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == ActionType.REORDER_CONTENT
        assert "overview" in plan.actions[0].parameters["sequence"] or len(plan.actions[0].parameters["sequence"]) > 0

    def test_missing_assets_detection(self):
        """Test detection of missing assets"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[],  # No assets available
        )

        plan = executor.parse_instruction("生成压力云图", manifest)

        assert not plan.is_executable()
        assert "field_data" in plan.missing_assets
        assert plan.confidence < 0.6  # Lower confidence due to missing assets

    def test_unknown_intent_defaults_to_plot(self):
        """Test that unknown intent defaults to plot"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="U.obj")],
        )

        plan = executor.parse_instruction("处理这个结果", manifest)

        assert plan.detected_intent == "plot"  # Default


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_create_action_plan(self):
        """Test create_action_plan function"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="U.obj")],
        )

        plan = create_action_plan("生成压力云图", manifest)

        assert isinstance(plan, ActionPlan)
        assert len(plan.actions) > 0

    def test_execute_action_plan(self):
        """Test execute_action_plan function"""
        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={"field": "pressure"},
                    confidence=0.8,
                    requires_assets=[],
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

        log = execute_action_plan(plan, manifest)

        assert log.action_plan == plan
        assert len(log.execution_results) == 1


class TestFieldExtraction:
    """Test field name extraction from various instructions"""

    def test_extract_pressure_chinese(self):
        """Test extracting 'pressure' from Chinese instruction"""
        executor = NLPostprocessExecutor()

        field = executor._extract_field_name("生成压力图")
        assert field == "pressure"

    def test_extract_velocity_chinese(self):
        """Test extracting 'velocity' from Chinese instruction"""
        executor = NLPostprocessExecutor()

        field = executor._extract_field_name("速度分布")
        assert field == "velocity"

    def test_extract_temperature_chinese(self):
        """Test extracting 'temperature' from Chinese instruction"""
        executor = NLPostprocessExecutor()

        field = executor._extract_field_name("温度场")
        assert field == "temperature"

    def test_extract_pressure_english(self):
        """Test extracting 'pressure' from English instruction"""
        executor = NLPostprocessExecutor()

        field = executor._extract_field_name("pressure field")
        assert field == "pressure"

    def test_extract_velocity_english(self):
        """Test extracting 'velocity' from English instruction"""
        executor = NLPostprocessExecutor()

        field = executor._extract_field_name("velocity magnitude")
        assert field == "velocity"


class TestPlotTypeExtraction:
    """Test plot type extraction"""

    def test_contour_chinese(self):
        """Test extracting contour plot type"""
        executor = NLPostprocessExecutor()

        plot_type = executor._extract_plot_type("云图")
        assert plot_type == "contour"

    def test_contour_english(self):
        """Test extracting contour plot type from English"""
        executor = NLPostprocessExecutor()

        plot_type = executor._extract_plot_type("contour plot")
        assert plot_type == "contour"

    def test_line_chinese(self):
        """Test extracting line plot type"""
        executor = NLPostprocessExecutor()

        plot_type = executor._extract_plot_type("线图")
        assert plot_type == "line"

    def test_vector_chinese(self):
        """Test extracting vector plot type"""
        executor = NLPostprocessExecutor()

        plot_type = executor._extract_plot_type("矢量图")
        assert plot_type == "vector"


class TestPlaneExtraction:
    """Test plane/location extraction"""

    def test_z_plane(self):
        """Test extracting z=number pattern"""
        executor = NLPostprocessExecutor()

        plane = executor._extract_plane("z=0.5平面")
        assert plane == "z=0.5"

    def test_xy_plane(self):
        """Test extracting xy plane"""
        executor = NLPostprocessExecutor()

        plane = executor._extract_plane("xy平面")
        assert plane == "xy"

    def test_midplane_chinese(self):
        """Test extracting midplane"""
        executor = NLPostprocessExecutor()

        plane = executor._extract_plane("中平面")
        assert plane == "midplane"

    def test_wall_chinese(self):
        """Test extracting wall"""
        executor = NLPostprocessExecutor()

        plane = executor._extract_plane("壁面")
        assert plane == "wall"


class TestMetricTypeExtraction:
    """Test metric type extraction"""

    def test_drag_coefficient(self):
        """Test extracting drag coefficient"""
        executor = NLPostprocessExecutor()

        metric = executor._extract_metric_type("阻力系数")
        assert "coefficient" in metric.lower() or "drag" in metric.lower()

    def test_lift_coefficient(self):
        """Test extracting lift coefficient"""
        executor = NLPostprocessExecutor()

        metric = executor._extract_metric_type("升力系数")
        assert "coefficient" in metric.lower() or "lift" in metric.lower()

    def test_pressure_drop(self):
        """Test extracting pressure drop"""
        executor = NLPostprocessExecutor()

        metric = executor._extract_metric_type("压力降")
        assert "pressure" in metric.lower() or "drop" in metric.lower()


class TestComparisonItemExtraction:
    """Test comparison items extraction"""

    def test_vs_pattern(self):
        """Test extracting items with 'vs' separator"""
        executor = NLPostprocessExecutor()

        items = executor._extract_comparison_items("inlet vs outlet")
        assert "inlet" in items
        assert "outlet" in items

    def test_chinese_separator(self):
        """Test extracting items with Chinese separator"""
        executor = NLPostprocessExecutor()

        items = executor._extract_comparison_items("入口和出口")
        assert len(items) >= 2


class TestSequenceExtraction:
    """Test content sequence extraction"""

    def test_arrow_sequence(self):
        """Test extracting sequence with arrow separator"""
        executor = NLPostprocessExecutor()

        sequence = executor._extract_sequence("A -> B -> C")
        assert sequence == ["A", "B", "C"]

    def test_comma_sequence(self):
        """Test extracting sequence with comma separator"""
        executor = NLPostprocessExecutor()

        sequence = executor._extract_sequence("A, B, C")
        assert sequence == ["A", "B", "C"]

    def test_keyword_sequence(self):
        """Test extracting sequence from keywords"""
        executor = NLPostprocessExecutor()

        sequence = executor._extract_sequence("总览、截面、图表")
        assert "overview" in sequence or len(sequence) >= 3


class TestRealWorldInstructions:
    """Test with real-world-like instructions"""

    def test_complex_plot_instruction(self):
        """Test complex plot instruction with field and location"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="backward_step",
            result_root="/path",
            assets=[
                ResultAsset(asset_type="field", path="U.obj"),
                ResultAsset(asset_type="field", path="p.obj"),
            ],
        )

        instruction = "在z=0.5平面生成压力和速度的对比云图"
        plan = executor.parse_instruction(instruction, manifest)

        assert plan.detected_intent == "plot" or plan.detected_intent == "mixed"
        assert len(plan.actions) >= 2  # At least 2 actions for pressure and velocity

    def test_multi_section_extraction(self):
        """Test extracting multiple sections"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="cavity",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="T.obj")],
        )

        instruction = "提取三个截面：z=0.2, z=0.5, z=0.8"
        plan = executor.parse_instruction(instruction, manifest)

        assert plan.detected_intent == "section"
        # Should create multiple actions or one action with multiple sections

    def test_metric_with_location(self):
        """Test metric with location specification"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="airfoil",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="U.obj")],
        )

        plan = executor.parse_instruction("计算inlet处的阻力系数", manifest)

        assert plan.detected_intent == "metric"
        assert plan.actions[0].action_type == ActionType.CALCULATE_METRIC
        assert "inlet" in plan.actions[0].parameters.get("location", "")

    def test_report_structure(self):
        """Test report structure specification"""
        executor = NLPostprocessExecutor()
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="generic",
            result_root="/path",
            assets=[],
        )

        plan = executor.parse_instruction(
            "按报告顺序排列：先放总览，再放关键截面，最后放误差表",
            manifest
        )

        assert plan.detected_intent == "reorder"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == ActionType.REORDER_CONTENT


class TestActionLog:
    """Test ActionLog functionality"""

    def test_create_log(self):
        """Test creating an ActionLog"""
        plan = ActionPlan(
            actions=[],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.8,
            raw_instruction="Test",
        )

        log = ActionLog(timestamp=123456, action_plan=plan)

        assert log.action_plan == plan
        assert log.timestamp == 123456

    def test_log_execution_results(self):
        """Test adding execution results"""
        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={},
                    confidence=0.8,
                    requires_assets=[],
                ),
            ],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.8,
            raw_instruction="Test",
        )

        log = ActionLog(timestamp=123456, action_plan=plan)

        log.add_result(0, {"status": "completed", "file": "plot.png"})

        assert len(log.execution_results) == 1
        assert log.execution_results[0]["status"] == "completed"

    def test_log_with_missing_assets(self):
        """Test logging execution failure with missing assets"""
        plan = ActionPlan(
            actions=[],
            detected_intent="plot",
            missing_assets=["field_data"],
            confidence=0.5,
            raw_instruction="Test",
        )

        log = execute_action_plan(plan, ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[],
        ))

        assert len(log.errors) > 0
        assert "missing" in log.errors[0].lower()


class TestConfidenceCalculation:
    """Test confidence calculation"""

    def test_high_confidence(self):
        """Test high confidence scenario"""
        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={},
                    confidence=0.9,
                    requires_assets=[],
                ),
            ],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.0,  # Will be calculated
            raw_instruction="Test",
        )

        executor = NLPostprocessExecutor()
        confidence = executor._calculate_confidence(plan.actions, plan.missing_assets)

        assert confidence > 0.8

    def test_low_confidence_missing_assets(self):
        """Test low confidence due to missing assets"""
        plan = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={},
                    confidence=0.5,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=["field_data"],
            confidence=0.0,
            raw_instruction="Test",
        )

        executor = NLPostprocessExecutor()
        confidence = executor._calculate_confidence(plan.actions, plan.missing_assets)

        assert confidence < 0.4  # Should be penalized


class TestG1P1GatePreparation:
    """Test preparation for G1-P1 Gate (Action Executability)"""

    def test_gate_should_check_executability(self):
        """
        This test validates that ActionPlan.is_executable() can be used
        by G1-P1 Gate to check if an NL instruction can be executed.
        """
        # Executable case
        plan_executable = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={},
                    confidence=0.8,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=[],
            confidence=0.8,
            raw_instruction="Generate pressure plot",
        )

        assert plan_executable.is_executable() is True

        # Non-executable case
        plan_not_executable = ActionPlan(
            actions=[
                Action(
                    action_type=ActionType.GENERATE_PLOT,
                    parameters={},
                    confidence=0.5,
                    requires_assets=["field_data"],
                ),
            ],
            detected_intent="plot",
            missing_assets=["field_data"],
            confidence=0.5,
            raw_instruction="Generate pressure plot (no data)",
        )

        assert plan_not_executable.is_executable() is False


@pytest.mark.parametrize("instruction,intent,field", [
    ("生成压力云图", "plot", "pressure"),
    ("画速度等值线", "plot", "velocity"),
    ("提取z=0.5平面", "section", None),
    ("计算阻力系数", "metric", None),
    ("对比inlet和outlet", "compare", None),
    ("按顺序排列", "reorder", None),
])
def test_intent_detection_matrix(instruction, intent, field):
    """Test intent detection for various instructions"""
    executor = NLPostprocessExecutor()
    detected = executor._detect_intent(instruction.lower())

    assert detected == intent
