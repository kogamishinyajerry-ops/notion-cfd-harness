#!/usr/bin/env python3
"""
Tests for Phase 1 Visualization Engine
"""

import json
import tempfile
from pathlib import Path

import pytest

from knowledge_compiler.phase1.visualization import (
    OutputFormat,
    VisualizationResult,
    VisualizationEngine,
    execute_visualization,
)
from knowledge_compiler.phase1.nl_postprocess import (
    ActionType,
    Action,
    ActionPlan,
)
from knowledge_compiler.phase1.schema import ResultManifest, ResultAsset


class TestVisualizationResult:
    """Test VisualizationResult dataclass"""

    def test_create_result(self):
        """Test creating a VisualizationResult"""
        result = VisualizationResult(
            action_index=0,
            action_type=ActionType.GENERATE_PLOT,
            output_path="/outputs/plot_001.png",
            output_format=OutputFormat.PNG,
            success=True,
            metadata={"field": "pressure"},
        )

        assert result.action_index == 0
        assert result.action_type == ActionType.GENERATE_PLOT
        assert result.success is True
        assert result.metadata["field"] == "pressure"

    def test_result_to_dict(self):
        """Test VisualizationResult serialization"""
        result = VisualizationResult(
            action_index=0,
            action_type=ActionType.GENERATE_PLOT,
            output_path="/outputs/plot_001.png",
            output_format=OutputFormat.PNG,
            success=True,
        )

        data = result.to_dict()

        assert data["action_index"] == 0
        assert data["action_type"] == "generate_plot"
        assert data["output_format"] == "png"
        assert data["success"] is True


class TestVisualizationEngine:
    """Test VisualizationEngine"""

    def test_engine_creation(self):
        """Test creating VisualizationEngine"""
        engine = VisualizationEngine()

        assert engine.output_root == Path("outputs")

    def test_engine_with_output_root(self):
        """Test creating engine with custom output root"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VisualizationEngine(output_root=tmpdir)

            assert engine.output_root == Path(tmpdir)

    def test_execute_generate_plot(self):
        """Test executing GENERATE_PLOT action"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VisualizationEngine(output_root=tmpdir)

            plan = ActionPlan(
                actions=[
                    Action(
                        action_type=ActionType.GENERATE_PLOT,
                        parameters={
                            "field": "pressure",
                            "plot_type": "contour",
                        },
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

            log = engine.execute_action_plan(plan, manifest)

            assert len(log.execution_results) == 1
            assert log.action_plan == plan

            result = log.execution_results[0]
            assert result["success"] is True
            assert result["action_type"] == "generate_plot"
            assert ".png" in result["output_path"]

    def test_execute_extract_section(self):
        """Test executing EXTRACT_SECTION action"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VisualizationEngine(output_root=tmpdir)

            plan = ActionPlan(
                actions=[
                    Action(
                        action_type=ActionType.EXTRACT_SECTION,
                        parameters={
                            "plane": "z=0.5",
                            "field": "velocity",
                        },
                        confidence=0.9,
                        requires_assets=["field_data"],
                    ),
                ],
                detected_intent="section",
                missing_assets=[],
                confidence=0.9,
                raw_instruction="Extract z=0.5 plane",
            )

            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[ResultAsset(asset_type="field", path="U.obj")],
            )

            log = engine.execute_action_plan(plan, manifest)

            assert len(log.execution_results) == 1

            result = log.execution_results[0]
            assert result["success"] is True
            assert result["output_format"] == "vtk"

    def test_execute_calculate_metric(self):
        """Test executing CALCULATE_METRIC action"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VisualizationEngine(output_root=tmpdir)

            plan = ActionPlan(
                actions=[
                    Action(
                        action_type=ActionType.CALCULATE_METRIC,
                        parameters={
                            "metric_type": "drag_coefficient",
                            "location": "inlet",
                        },
                        confidence=0.9,
                        requires_assets=["field_data"],
                    ),
                ],
                detected_intent="metric",
                missing_assets=[],
                confidence=0.9,
                raw_instruction="Calculate drag coefficient",
            )

            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[ResultAsset(asset_type="field", path="U.obj")],
            )

            log = engine.execute_action_plan(plan, manifest)

            assert len(log.execution_results) == 1

            result = log.execution_results[0]
            assert result["success"] is True
            assert result["output_format"] == "json"
            assert "metric_drag_coefficient" in result["output_path"]

            # Check JSON file was created
            output_path = Path(result["output_path"])
            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)
                assert "coefficient_type" in data

    def test_execute_compare_data(self):
        """Test executing COMPARE_DATA action"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VisualizationEngine(output_root=tmpdir)

            plan = ActionPlan(
                actions=[
                    Action(
                        action_type=ActionType.COMPARE_DATA,
                        parameters={
                            "items": ["inlet", "outlet"],
                            "field": "pressure",
                            "comparison_type": "side_by_side",
                        },
                        confidence=0.9,
                        requires_assets=["field_data"],
                    ),
                ],
                detected_intent="compare",
                missing_assets=[],
                confidence=0.9,
                raw_instruction="Compare inlet and outlet pressure",
            )

            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[ResultAsset(asset_type="field", path="p.obj")],
            )

            log = engine.execute_action_plan(plan, manifest)

            assert len(log.execution_results) == 1

            result = log.execution_results[0]
            assert result["success"] is True
            assert "comparison" in result["output_path"]

    def test_execute_reorder_content(self):
        """Test executing REORDER_CONTENT action"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VisualizationEngine(output_root=tmpdir)

            plan = ActionPlan(
                actions=[
                    Action(
                        action_type=ActionType.REORDER_CONTENT,
                        parameters={
                            "sequence": ["overview", "sections", "plots"],
                        },
                        confidence=0.9,
                        requires_assets=[],
                    ),
                ],
                detected_intent="reorder",
                missing_assets=[],
                confidence=0.9,
                raw_instruction="Reorder content",
            )

            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[],
            )

            log = engine.execute_action_plan(plan, manifest)

            assert len(log.execution_results) == 1

            result = log.execution_results[0]
            assert result["success"] is True

            # Check JSON file
            output_path = Path(result["output_path"])
            with open(output_path) as f:
                data = json.load(f)
                assert data["sequence"] == ["overview", "sections", "plots"]

    def test_non_executable_plan_fails(self):
        """Test that non-executable plan fails"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VisualizationEngine(output_root=tmpdir)

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
                missing_assets=["field_data"],  # Missing!
                confidence=0.5,
                raw_instruction="Generate plot (no data)",
            )

            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[],  # No assets
            )

            log = engine.execute_action_plan(plan, manifest)

            assert len(log.errors) > 0
            assert "missing" in str(log.errors).lower()

    def test_multiple_actions(self):
        """Test executing plan with multiple actions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VisualizationEngine(output_root=tmpdir)

            plan = ActionPlan(
                actions=[
                    Action(
                        action_type=ActionType.GENERATE_PLOT,
                        parameters={"field": "pressure", "plot_type": "contour"},
                        confidence=0.9,
                        requires_assets=["field_data"],
                    ),
                    Action(
                        action_type=ActionType.GENERATE_PLOT,
                        parameters={"field": "velocity", "plot_type": "vector"},
                        confidence=0.9,
                        requires_assets=["field_data"],
                    ),
                ],
                detected_intent="plot",
                missing_assets=[],
                confidence=0.9,
                raw_instruction="Generate pressure and velocity plots",
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

            log = engine.execute_action_plan(plan, manifest)

            assert len(log.execution_results) == 2
            assert all(r["success"] for r in log.execution_results)

    def test_output_directory_creation(self):
        """Test that output directories are created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "outputs"
            engine = VisualizationEngine(output_root=str(output_root))

            plan = ActionPlan(
                actions=[
                    Action(
                        action_type=ActionType.GENERATE_PLOT,
                        parameters={"field": "pressure"},
                        confidence=0.9,
                        requires_assets=["field_data"],
                    ),
                ],
                detected_intent="plot",
                missing_assets=[],
                confidence=0.9,
                raw_instruction="Generate plot",
            )

            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test_case",
                result_root="/path",
                assets=[ResultAsset(asset_type="field", path="p.obj")],
            )

            log = engine.execute_action_plan(plan, manifest)

            # Check that output directory was created
            expected_dir = output_root / "test_case" / "visualizations"
            assert expected_dir.exists()
            assert expected_dir.is_dir()


class TestConvenienceFunction:
    """Test convenience functions"""

    def test_execute_visualization(self):
        """Test execute_visualization function"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = ActionPlan(
                actions=[
                    Action(
                        action_type=ActionType.GENERATE_PLOT,
                        parameters={"field": "pressure"},
                        confidence=0.9,
                        requires_assets=["field_data"],
                    ),
                ],
                detected_intent="plot",
                missing_assets=[],
                confidence=0.9,
                raw_instruction="Generate plot",
            )

            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[ResultAsset(asset_type="field", path="p.obj")],
            )

            log = execute_visualization(
                plan,
                manifest,
                output_root=tmpdir,
                case_name="my_case",
            )

            assert len(log.execution_results) == 1
            assert log.execution_results[0]["success"] is True


class TestMetricCalculators:
    """Test metric calculator methods"""

    def test_drag_coefficient_calculator(self):
        """Test drag coefficient calculator"""
        engine = VisualizationEngine()

        result = engine._calc_drag_coefficient({}, None)

        assert "value" in result
        assert result["coefficient_type"] == "drag"

    def test_lift_coefficient_calculator(self):
        """Test lift coefficient calculator"""
        engine = VisualizationEngine()

        result = engine._calc_lift_coefficient({}, None)

        assert "value" in result
        assert result["coefficient_type"] == "lift"

    def test_pressure_drop_calculator(self):
        """Test pressure drop calculator"""
        engine = VisualizationEngine()

        result = engine._calc_pressure_drop({}, None)

        assert "value" in result
        assert result["metric_type"] == "pressure_drop"
        assert result["unit"] == "Pa"


class TestIntegrationWithNLPostprocess:
    """Test integration with NL Postprocess Executor"""

    def test_nl_to_visualization_workflow(self):
        """Test full workflow: NL -> ActionPlan -> Visualization"""
        from knowledge_compiler.phase1.nl_postprocess import NLPostprocessExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            nl_executor = NLPostprocessExecutor()
            vis_engine = VisualizationEngine(output_root=tmpdir)

            instruction = "生成压力云图"
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[ResultAsset(asset_type="field", path="p.obj")],
            )

            # Parse NL
            plan = nl_executor.parse_instruction(instruction, manifest)

            # Execute visualization
            log = vis_engine.execute_action_plan(plan, manifest)

            assert len(log.execution_results) >= 1
            assert log.execution_results[0]["success"] is True


class TestRealVisualizationMode:
    """Test VisualizationEngine with real matplotlib backend (is_mock=False)"""

    def test_engine_creation_real_mode(self):
        """Test creating engine with real mode"""
        try:
            engine = VisualizationEngine(is_mock=False)
            assert engine.is_mock is False
            assert hasattr(engine, '_plt')
            assert hasattr(engine, '_np')
        except ImportError:
            pytest.skip("matplotlib not available")

    def test_execute_generate_plot_real_mode(self):
        """Test GENERATE_PLOT with real matplotlib"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                engine = VisualizationEngine(output_root=tmpdir, is_mock=False)

                plan = ActionPlan(
                    actions=[
                        Action(
                            action_type=ActionType.GENERATE_PLOT,
                            parameters={
                                "field": "pressure",
                                "plot_type": "contour",
                                "colormap": "viridis",
                            },
                            confidence=0.9,
                            requires_assets=[],
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
                    assets=[],
                )

                log = engine.execute_action_plan(plan, manifest)

                assert len(log.execution_results) == 1
                result = log.execution_results[0]
                assert result["success"] is True
                assert result["metadata"]["mode"] == "real"

                # Verify PNG file was created
                output_path = Path(result["output_path"])
                assert output_path.exists()
                assert output_path.stat().st_size > 1000  # Real image, not empty

        except ImportError:
            pytest.skip("matplotlib not available")

    def test_execute_generate_plot_vector_real_mode(self):
        """Test vector plot with real matplotlib"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                engine = VisualizationEngine(output_root=tmpdir, is_mock=False)

                plan = ActionPlan(
                    actions=[
                        Action(
                            action_type=ActionType.GENERATE_PLOT,
                            parameters={
                                "field": "velocity",
                                "plot_type": "vector",
                            },
                            confidence=0.9,
                            requires_assets=[],
                        ),
                    ],
                    detected_intent="plot",
                    missing_assets=[],
                    confidence=0.9,
                    raw_instruction="Generate velocity vector plot",
                )

                manifest = ResultManifest(
                    solver_type="openfoam",
                    case_name="test",
                    result_root="/path",
                    assets=[],
                )

                log = engine.execute_action_plan(plan, manifest)

                result = log.execution_results[0]
                assert result["success"] is True
                assert result["metadata"]["plot_type"] == "vector"

                output_path = Path(result["output_path"])
                assert output_path.exists()
                assert output_path.stat().st_size > 1000

        except ImportError:
            pytest.skip("matplotlib not available")

    def test_execute_generate_plot_streamline_real_mode(self):
        """Test streamline plot with real matplotlib"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                engine = VisualizationEngine(output_root=tmpdir, is_mock=False)

                plan = ActionPlan(
                    actions=[
                        Action(
                            action_type=ActionType.GENERATE_PLOT,
                            parameters={
                                "field": "velocity",
                                "plot_type": "streamline",
                            },
                            confidence=0.9,
                            requires_assets=[],
                        ),
                    ],
                    detected_intent="plot",
                    missing_assets=[],
                    confidence=0.9,
                    raw_instruction="Generate velocity streamline plot",
                )

                manifest = ResultManifest(
                    solver_type="openfoam",
                    case_name="test",
                    result_root="/path",
                    assets=[],
                )

                log = engine.execute_action_plan(plan, manifest)

                result = log.execution_results[0]
                assert result["success"] is True
                assert result["metadata"]["plot_type"] == "streamline"

        except ImportError:
            pytest.skip("matplotlib not available")

    def test_execute_calculate_metric_real_mode(self):
        """Test CALCULATE_METRIC with real calculations"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                engine = VisualizationEngine(output_root=tmpdir, is_mock=False)

                plan = ActionPlan(
                    actions=[
                        Action(
                            action_type=ActionType.CALCULATE_METRIC,
                            parameters={
                                "metric_type": "max_value",
                            },
                            confidence=0.9,
                            requires_assets=[],
                        ),
                    ],
                    detected_intent="metric",
                    missing_assets=[],
                    confidence=0.9,
                    raw_instruction="Calculate max value",
                )

                manifest = ResultManifest(
                    solver_type="openfoam",
                    case_name="test",
                    result_root="/path",
                    assets=[],
                )

                log = engine.execute_action_plan(plan, manifest)

                result = log.execution_results[0]
                assert result["success"] is True

                # Check JSON file
                output_path = Path(result["output_path"])
                assert output_path.exists()
                with open(output_path) as f:
                    data = json.load(f)
                    assert "value" in data
                    # Real mode should have non-zero value
                    assert data["value"] != 0.0

        except ImportError:
            pytest.skip("matplotlib not available")

    def test_execute_compare_data_real_mode(self):
        """Test COMPARE_DATA with real matplotlib bar chart"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                engine = VisualizationEngine(output_root=tmpdir, is_mock=False)

                plan = ActionPlan(
                    actions=[
                        Action(
                            action_type=ActionType.COMPARE_DATA,
                            parameters={
                                "items": ["inlet", "outlet", "middle"],
                                "field": "pressure",
                            },
                            confidence=0.9,
                            requires_assets=[],
                        ),
                    ],
                    detected_intent="compare",
                    missing_assets=[],
                    confidence=0.9,
                    raw_instruction="Compare inlet and outlet pressure",
                )

                manifest = ResultManifest(
                    solver_type="openfoam",
                    case_name="test",
                    result_root="/path",
                    assets=[],
                )

                log = engine.execute_action_plan(plan, manifest)

                result = log.execution_results[0]
                assert result["success"] is True
                assert result["metadata"]["mode"] == "real"

                output_path = Path(result["output_path"])
                assert output_path.exists()
                assert output_path.stat().st_size > 1000

        except ImportError:
            pytest.skip("matplotlib not available")

    def test_convenience_function_real_mode(self):
        """Test execute_visualization with is_mock=False"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                plan = ActionPlan(
                    actions=[
                        Action(
                            action_type=ActionType.GENERATE_PLOT,
                            parameters={"field": "temperature", "plot_type": "contour"},
                            confidence=0.9,
                            requires_assets=[],
                        ),
                    ],
                    detected_intent="plot",
                    missing_assets=[],
                    confidence=0.9,
                    raw_instruction="Generate temperature contour",
                )

                manifest = ResultManifest(
                    solver_type="openfoam",
                    case_name="test",
                    result_root="/path",
                    assets=[],
                )

                log = execute_visualization(
                    plan,
                    manifest,
                    output_root=tmpdir,
                    is_mock=False,
                )

                assert len(log.execution_results) == 1
                assert log.execution_results[0]["success"] is True
                assert log.execution_results[0]["metadata"]["mode"] == "real"

        except ImportError:
            pytest.skip("matplotlib not available")

    def test_metric_calculators_real_mode(self):
        """Test metric calculators produce real values"""
        try:
            engine = VisualizationEngine(is_mock=False)

            # Test max value
            result = engine._calc_max_value({}, None)
            assert result["value"] != 0.0  # Real mode should have actual value
            assert result["metric_type"] == "max"

            # Test min value
            result = engine._calc_min_value({}, None)
            assert result["metric_type"] == "min"

            # Test average
            result = engine._calc_average({}, None)
            assert result["metric_type"] == "average"

            # Test drag coefficient
            result = engine._calc_drag_coefficient({}, None)
            assert "coefficient_type" in result
            assert result["coefficient_type"] == "drag"

        except ImportError:
            pytest.skip("matplotlib not available")
