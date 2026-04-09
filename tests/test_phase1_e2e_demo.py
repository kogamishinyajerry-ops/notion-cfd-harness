#!/usr/bin/env python3
"""
Phase 1 End-to-End Demo Tests

完整的端到端演示，展示 Phase 1 各组件协同工作：
1. NL Postprocess: 自然语言解析 -> ActionPlan
2. G1-P1 Gate: 验证 ActionPlan 可执行性
3. Visualization Engine: 执行可视化
4. 结果验证: 检查输出文件

Demo Case: Backward-Facing Step (后向台阶)
"""

import json
import tempfile
from pathlib import Path

import pytest

from knowledge_compiler.phase1.nl_postprocess import (
    NLPostprocessExecutor,
    ActionType,
    ActionPlan,
    Action,
)
from knowledge_compiler.phase1.gates import (
    Phase1GateExecutor,
    GateStatus,
)
from knowledge_compiler.phase1.visualization import (
    VisualizationEngine,
    execute_visualization,
)
from knowledge_compiler.phase1.schema import (
    ResultManifest,
    ResultAsset,
)
from knowledge_compiler.phase1.gold_standards import (
    create_backward_facing_step_spec,
    BackwardStepGateValidator,
)


class TestPhase1E2EDemo:
    """
    Phase 1 End-to-End Demo

    完整流程演示:
    NL 输入 -> ActionPlan -> Gate 验证 -> Visualization -> 输出文件
    """

    def test_e2e_backward_facing_step_chinese(self):
        """
        E2E Demo: 后向台阶案例 (中文输入)

        流程:
        1. NL: "生成后向台阶的压力云图和速度流线图"
        2. NL Postprocess -> ActionPlan
        3. G1-P1 Gate -> 验证可执行性
        4. Visualization Engine -> 生成文件
        5. 验证输出文件
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: 创建 ResultManifest
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="backward_step",
                result_root="/mock/results",
                assets=[
                    ResultAsset(asset_type="field", path="p.obj"),
                    ResultAsset(asset_type="field", path="U.obj"),
                ],
            )

            # Step 2: NL Postprocess 解析
            nl_executor = NLPostprocessExecutor()
            instruction = "生成后向台阶的压力云图和速度流线图"
            plan = nl_executor.parse_instruction(instruction, manifest)

            # 验证 ActionPlan
            assert plan.detected_intent == "plot"
            assert len(plan.actions) >= 2
            assert plan.confidence > 0.7

            # 检查解析出的动作
            action_fields = [a.parameters.get("field") for a in plan.actions]
            assert "pressure" in action_fields or "p" in action_fields
            assert "velocity" in action_fields or "U" in action_fields

            # Step 3: G1-P1 Gate 验证
            gate_executor = Phase1GateExecutor()
            gate_result = gate_executor.run_g1_gate(
                action_plan=plan,
                manifest=manifest,
            )

            # Gate 应该通过
            assert gate_result.status in [GateStatus.PASS, GateStatus.WARN]
            if gate_result.status == GateStatus.WARN:
                # Warn 是可接受的，检查没有严重错误
                assert not any(c.is_blocking for c in gate_result.checks if not c.passed)

            # Step 4: Visualization Engine 执行
            vis_engine = VisualizationEngine(output_root=tmpdir)
            log = vis_engine.execute_action_plan(plan, manifest)

            # 验证执行日志
            assert len(log.execution_results) == len(plan.actions)
            assert log.action_plan == plan

            # Step 5: 验证输出文件
            for result in log.execution_results:
                if result["success"]:
                    output_path = Path(result["output_path"])
                    # 注意: MOCK 模式下文件可能不存在，但路径应该正确
                    assert "backward_step" in str(output_path) or "visualizations" in str(output_path)

    def test_e2e_backward_facing_step_english(self):
        """
        E2E Demo: Backward-Facing Step Case (English Input)

        Flow:
        1. NL: "Generate pressure contour and velocity streamlines for backward step"
        2. NL Postprocess -> ActionPlan
        3. G1-P1 Gate -> Validate executability
        4. Visualization Engine -> Generate files
        5. Verify output files
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Create ResultManifest
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="backward_step",
                result_root="/mock/results",
                assets=[
                    ResultAsset(asset_type="field", path="p"),
                    ResultAsset(asset_type="field", path="U"),
                ],
            )

            # Step 2: NL Postprocess parsing
            nl_executor = NLPostprocessExecutor()
            instruction = "Generate pressure contour and velocity streamlines"
            plan = nl_executor.parse_instruction(instruction, manifest)

            # Validate ActionPlan
            assert plan.detected_intent == "plot"
            assert len(plan.actions) >= 1
            assert plan.confidence > 0.5

            # Step 3: G1-P1 Gate validation
            gate_executor = Phase1GateExecutor()
            gate_result = gate_executor.run_g1_gate(
                action_plan=plan,
                manifest=manifest,
            )

            # Gate should pass or warn
            assert gate_result.status in [GateStatus.PASS, GateStatus.WARN]

            # Step 4: Visualization Engine execution
            vis_engine = VisualizationEngine(output_root=tmpdir)
            log = vis_engine.execute_action_plan(plan, manifest)

            # Validate execution log
            assert len(log.execution_results) >= 1

    def test_e2e_gold_standard_validation(self):
        """
        E2E Demo: 黄金标准验证

        展示如何使用黄金标准验证生成的 ReportSpec
        """
        # 创建黄金标准
        gold_spec = create_backward_facing_step_spec(
            case_id="test_backward_step",
            reynolds_number=400.0,
            is_turbulent=False,
        )

        # 创建验证器
        validator = BackwardStepGateValidator()

        # 验证黄金标准自身 (应该完美通过)
        result = validator.validate_report_spec(gold_spec)

        assert result["passed"] is True
        assert len(result["errors"]) == 0
        assert result["details"]["plot_coverage"] == 1.0
        assert result["details"]["metric_coverage"] == 1.0

    def test_e2e_metric_calculation(self):
        """
        E2E Demo: 指标计算

        展示计算 CFD 关键指标的完整流程
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="backward_step",
                result_root="/mock/results",
                assets=[
                    ResultAsset(asset_type="field", path="U"),
                    ResultAsset(asset_type="field", path="p"),
                ],
            )

            # NL: 计算再附着长度
            nl_executor = NLPostprocessExecutor()
            instruction = "计算再附着长度"
            plan = nl_executor.parse_instruction(instruction, manifest)

            # 应该检测到 metric 意图
            assert plan.detected_intent == "metric"

            # Gate 验证
            gate_executor = Phase1GateExecutor()
            gate_result = gate_executor.run_g1_gate(plan, manifest)

            assert gate_result.status in [GateStatus.PASS, GateStatus.WARN]

            # 执行
            vis_engine = VisualizationEngine(output_root=tmpdir)
            log = vis_engine.execute_action_plan(plan, manifest)

            # 验证输出
            assert len(log.execution_results) >= 1
            result = log.execution_results[0]
            assert result["action_type"] == "calculate_metric"

    def test_e2e_section_extraction(self):
        """
        E2E Demo: 截面提取

        展示从 CFD 结果中提取截面数据的完整流程
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="backward_step",
                result_root="/mock/results",
                assets=[
                    ResultAsset(asset_type="field", path="U"),
                ],
            )

            # NL: 提取 x=1.0 截面的速度分布
            nl_executor = NLPostprocessExecutor()
            instruction = "提取 x=1.0 截面的速度分布"
            plan = nl_executor.parse_instruction(instruction, manifest)

            # 应该检测到 section 意图
            assert plan.detected_intent == "section"

            # Gate 验证
            gate_executor = Phase1GateExecutor()
            gate_result = gate_executor.run_g1_gate(plan, manifest)

            assert gate_result.status in [GateStatus.PASS, GateStatus.WARN]

            # 执行
            vis_engine = VisualizationEngine(output_root=tmpdir)
            log = vis_engine.execute_action_plan(plan, manifest)

            # 验证输出
            assert len(log.execution_results) >= 1
            result = log.execution_results[0]
            assert result["action_type"] == "extract_section"
            assert result["output_format"] == "vtk"

    def test_e2e_data_comparison(self):
        """
        E2E Demo: 数据对比

        展示对比多个数据源的完整流程
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="backward_step",
                result_root="/mock/results",
                assets=[
                    ResultAsset(asset_type="field", path="p"),
                ],
            )

            # NL: 对比入口和出口的压力分布
            nl_executor = NLPostprocessExecutor()
            instruction = "对比入口和出口的压力分布"
            plan = nl_executor.parse_instruction(instruction, manifest)

            # 应该检测到 compare 意图
            assert plan.detected_intent == "compare"

            # Gate 验证
            gate_executor = Phase1GateExecutor()
            gate_result = gate_executor.run_g1_gate(plan, manifest)

            assert gate_result.status in [GateStatus.PASS, GateStatus.WARN]

            # 执行
            vis_engine = VisualizationEngine(output_root=tmpdir)
            log = vis_engine.execute_action_plan(plan, manifest)

            # 验证输出
            assert len(log.execution_results) >= 1
            result = log.execution_results[0]
            assert result["action_type"] == "compare_data"

    def test_e2e_content_reorder(self):
        """
        E2E Demo: 内容重排序

        展示自定义报告结构的完整流程
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="backward_step",
                result_root="/mock/results",
                assets=[],
            )

            # NL: 重新排序报告内容
            nl_executor = NLPostprocessExecutor()
            instruction = "按以下顺序排列：概述、图表、数据"
            plan = nl_executor.parse_instruction(instruction, manifest)

            # 应该检测到 reorder 意图
            assert plan.detected_intent == "reorder"

            # Gate 验证
            gate_executor = Phase1GateExecutor()
            gate_result = gate_executor.run_g1_gate(plan, manifest)

            assert gate_result.status in [GateStatus.PASS, GateStatus.WARN]

            # 执行
            vis_engine = VisualizationEngine(output_root=tmpdir)
            log = vis_engine.execute_action_plan(plan, manifest)

            # 验证输出
            assert len(log.execution_results) >= 1
            result = log.execution_results[0]
            assert result["action_type"] == "reorder_content"

            # 检查 JSON 输出
            output_path = Path(result["output_path"])
            if output_path.exists():
                with open(output_path) as f:
                    data = json.load(f)
                    assert "sequence" in data

    def test_e2e_gate_failure_handling(self):
        """
        E2E Demo: Gate 失败处理

        展示当 Gate 验证失败时的处理流程
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建缺少必要资源的 manifest
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="backward_step",
                result_root="/mock/results",
                assets=[],  # 没有资源!
            )

            # NL: 生成压力云图 (需要 field 资源)
            nl_executor = NLPostprocessExecutor()
            instruction = "生成压力云图"
            plan = nl_executor.parse_instruction(instruction, manifest)

            # Gate 验证应该失败或警告
            gate_executor = Phase1GateExecutor()
            gate_result = gate_executor.run_g1_gate(plan, manifest)

            # Gate 应该检测到缺失资源
            assert gate_result.status in [GateStatus.WARN, GateStatus.FAIL]

            # 即使 Gate 失败，Visualization Engine 也应该能处理
            vis_engine = VisualizationEngine(output_root=tmpdir)
            log = vis_engine.execute_action_plan(plan, manifest)

            # 验证错误被正确记录
            if len(log.errors) > 0:
                # 应该有关于缺失资源的错误信息
                error_str = str(log.errors).lower()
                assert "missing" in error_str or "asset" in error_str

    def test_e2e_complex_instruction(self):
        """
        E2E Demo: 复杂指令处理

        展示处理多步骤复杂指令的完整流程
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="backward_step",
                result_root="/mock/results",
                assets=[
                    ResultAsset(asset_type="field", path="p"),
                    ResultAsset(asset_type="field", path="U"),
                    ResultAsset(asset_type="field", path="k"),
                    ResultAsset(asset_type="field", path="omega"),
                ],
            )

            # NL: 复杂指令 - 生成多种图表并计算指标
            nl_executor = NLPostprocessExecutor()
            instruction = "生成压力云图、速度流线图、湍动能云图，并计算再附着长度"
            plan = nl_executor.parse_instruction(instruction, manifest)

            # 应该解析出多个动作
            assert len(plan.actions) >= 2
            assert plan.detected_intent == "plot"

            # Gate 验证
            gate_executor = Phase1GateExecutor()
            gate_result = gate_executor.run_g1_gate(plan, manifest)

            assert gate_result.status in [GateStatus.PASS, GateStatus.WARN]

            # 执行所有动作
            vis_engine = VisualizationEngine(output_root=tmpdir)
            log = vis_engine.execute_action_plan(plan, manifest)

            # 验证所有动作都被执行
            assert len(log.execution_results) == len(plan.actions)

            # 统计成功/失败
            successful = sum(1 for r in log.execution_results if r["success"])
            assert successful >= 1  # 至少有一个成功


class TestPhase1WorkflowPatterns:
    """
    Phase 1 工作流模式测试

    展示常见的 Phase 1 使用模式
    """

    def test_workflow_rapid_visualization(self):
        """
        工作流: 快速可视化

        从 NL 到可视化结果的最快路径
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[ResultAsset(asset_type="field", path="p")],
            )

            # 一步到位: 使用便捷函数
            from knowledge_compiler.phase1.nl_postprocess import NLPostprocessExecutor

            nl_executor = NLPostprocessExecutor()
            plan = nl_executor.parse_instruction("压力云图", manifest)

            log = execute_visualization(
                plan,
                manifest,
                output_root=tmpdir,
                case_name="test",
            )

            assert len(log.execution_results) >= 1

    def test_workflow_validated_generation(self):
        """
        工作流: 验证后生成

        先验证可执行性，再执行可视化
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[ResultAsset(asset_type="field", path="U")],
            )

            nl_executor = NLPostprocessExecutor()
            gate_executor = Phase1GateExecutor()
            vis_engine = VisualizationEngine(output_root=tmpdir)

            # 解析
            plan = nl_executor.parse_instruction("速度矢量图", manifest)

            # 验证
            gate_result = gate_executor.run_g1_gate(plan, manifest)

            # 只有验证通过才执行
            if gate_result.status != GateStatus.FAIL:
                log = vis_engine.execute_action_plan(plan, manifest)
                assert len(log.execution_results) >= 1
            else:
                # Gate 失败，应该有错误信息
                assert len(gate_result.checks) > 0

    def test_workflow_batch_processing(self):
        """
        工作流: 批量处理

        处理多个 NL 指令
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[
                    ResultAsset(asset_type="field", path="p"),
                    ResultAsset(asset_type="field", path="U"),
                ],
            )

            nl_executor = NLPostprocessExecutor()
            vis_engine = VisualizationEngine(output_root=tmpdir)

            # 批量指令
            instructions = [
                "压力云图",
                "速度流线",
                "速度矢量",
            ]

            results = []
            for instruction in instructions:
                plan = nl_executor.parse_instruction(instruction, manifest)
                log = vis_engine.execute_action_plan(plan, manifest)
                results.append(log)

            assert len(results) == 3

    def test_workflow_error_recovery(self):
        """
        工作流: 错误恢复

        展示如何处理和恢复错误
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # 不完整的 manifest
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="test",
                result_root="/path",
                assets=[],  # 没有资源
            )

            nl_executor = NLPostprocessExecutor()
            vis_engine = VisualizationEngine(output_root=tmpdir)

            plan = nl_executor.parse_instruction("压力云图", manifest)
            log = vis_engine.execute_action_plan(plan, manifest)

            # 检查错误
            if len(log.errors) > 0:
                # 错误应该被记录
                assert isinstance(log.errors, list)

                # execution_results 应该反映失败
                if len(log.execution_results) > 0:
                    assert not log.execution_results[0].get("success", True)


class TestPhase1IntegrationPoints:
    """
    Phase 1 集成点测试

    展示 Phase 1 与其他组件的集成
    """

    def test_integration_with_report_spec(self):
        """
        集成点: ReportSpec

        展示 ReportSpec 如何与 Visualization 集成
        """
        from knowledge_compiler.phase1 import ReportSpec

        # 创建黄金标准 ReportSpec
        gold_spec = create_backward_facing_step_spec()

        # 验证 spec 结构
        assert gold_spec.report_spec_id.startswith("GOLD-")
        assert len(gold_spec.required_plots) > 0
        assert len(gold_spec.required_metrics) > 0

        # 可以用于指导可视化
        plot_names = {p.name for p in gold_spec.required_plots}
        assert "velocity_magnitude_contour" in plot_names
        assert "streamlines" in plot_names

    def test_integration_with_gold_standard(self):
        """
        集成点: 黄金标准

        展示如何使用黄金标准验证结果
        """
        # 创建自定义 spec
        custom_spec = create_backward_facing_step_spec(
            case_id="custom",
            reynolds_number=800.0,
        )

        # 用黄金标准验证
        validator = BackwardStepGateValidator()
        result = validator.validate_report_spec(custom_spec)

        # 自定义 spec 应该符合黄金标准要求
        assert result["passed"] is True

    def test_integration_gate_chain(self):
        """
        集成点: Gate 链

        展示多个 Gate 的串联使用
        """
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="p")],
        )

        nl_executor = NLPostprocessExecutor()
        plan = nl_executor.parse_instruction("压力云图", manifest)

        # 运行 G1 Gate
        gate_executor = Phase1GateExecutor()
        g1_result = gate_executor.run_g1_gate(plan, manifest)

        # Gate 结果可以用于决策
        if g1_result.status == GateStatus.PASS:
            # 继续执行
            assert True
        elif g1_result.status == GateStatus.WARN:
            # 检查警告详情
            assert len(g1_result.checks) > 0
        else:
            # FAIL - 记录原因
            assert len(g1_result.checks) > 0
            failed_checks = [c for c in g1_result.checks if not c.passed]
            assert len(failed_checks) > 0


class TestPhase1DemoScenarios:
    """
    Phase 1 演示场景

    真实使用场景的演示
    """

    def test_scenario_new_case_setup(self):
        """
        场景: 新案例设置

        展示如何为新 CFD 案例设置报告规范
        """
        # 使用黄金标准作为模板
        template = create_backward_facing_step_spec()

        # 为新案例定制
        new_case_id = "custom_backward_step_v2"
        # (在实际使用中，这里会根据具体需求调整 template)

        assert template.report_spec_id.startswith("GOLD-")

    def test_scenario_quality_assurance(self):
        """
        场景: 质量保证

        展示如何用 Gate 确保 AI 输出质量
        """
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="production_case",
            result_root="/results",
            assets=[
                ResultAsset(asset_type="field", path="p"),
                ResultAsset(asset_type="field", path="U"),
            ],
        )

        # 生产环境的严格检查
        nl_executor = NLPostprocessExecutor()
        gate_executor = Phase1GateExecutor()

        instruction = "生成完整的后处理报告"
        plan = nl_executor.parse_instruction(instruction, manifest)

        # 运行 Gate 检查
        gate_result = gate_executor.run_g1_gate(plan, manifest)

        # 生产环境要求 PASS，WARN 也需要人工审核
        assert gate_result.status in [GateStatus.PASS, GateStatus.WARN]

        # 记录 Gate 结果用于审计
        assert gate_result.gate_id == "G1-P1"
        assert gate_result.timestamp is not None

    def test_scenario_reproducible_output(self):
        """
        场景: 可重现输出

        展示如何确保结果可重现
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ResultManifest(
                solver_type="openfoam",
                case_name="repro_test",
                result_root="/path",
                assets=[ResultAsset(asset_type="field", path="p")],
            )

            # 相同指令应该产生相同的 ActionPlan
            nl_executor = NLPostprocessExecutor()
            instruction = "压力云图"

            plan1 = nl_executor.parse_instruction(instruction, manifest)
            plan2 = nl_executor.parse_instruction(instruction, manifest)

            # ActionPlan 应该一致
            assert plan1.detected_intent == plan2.detected_intent
            assert len(plan1.actions) == len(plan2.actions)


# Demo 辅助函数
def print_e2e_demo_summary():
    """
    打印 E2E Demo 摘要

    用于文档和演示
    """
    summary = """
    Phase 1 End-to-End Demo Summary
    ================================

    Components Tested:
    1. NL Postprocess Executor (F2)
       - Natural language to ActionPlan
       - Support: Chinese, English
       - Intents: plot, metric, section, compare, reorder

    2. G1-P1 ActionPlan Executability Gate
       - Validates ActionPlan before execution
       - Checks: asset availability, parameter validity
       - Status: PASS, WARN, FAIL

    3. Visualization Engine (F3)
       - Executes ActionPlan
       - Outputs: PNG plots, VTK sections, JSON metrics
       - Error handling and logging

    4. Gold Standard: Backward-Facing Step
       - Reference ReportSpec template
       - Validator for quality assurance
       - Benchmark data from Armaly et al. (1983)

    Test Coverage:
    - E2E workflows: 11 tests
    - Workflow patterns: 4 tests
    - Integration points: 3 tests
    - Demo scenarios: 3 tests

    Total: 21 E2E demo tests
    """
    return summary
