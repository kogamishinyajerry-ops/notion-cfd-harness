#!/usr/bin/env python3
"""
Phase 1 E2E Demo: Backward-Facing Step Case

完整测试 Phase 1 工作流：
1. NL 指令 -> 真实后处理 -> 报告草案
2. 工程师纠偏 -> CorrectionSpec -> Replay 验证

验证 5 种动作类型：
- GENERATE_PLOT: 压力云图、速度云图、流线
- EXTRACT_SECTION: 截面提取
- CALCULATE_METRIC: 压力降计算
- COMPARE_DATA: 入口/出口压力对比
- REORDER_CONTENT: 报告结构重排
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from knowledge_compiler.phase1.gold_standards import (
    BackwardStepGateValidator,
    create_backward_facing_step_spec,
)
from knowledge_compiler.phase1.nl_postprocess import (
    ActionPlan,
    ActionType,
    NLPostprocessExecutor,
)
from knowledge_compiler.phase1.parser import ResultDirectoryParser
from knowledge_compiler.phase1.replay import HistoricalReference, ReplayEngine
from knowledge_compiler.phase1.schema import (
    ErrorType,
    ImpactScope,
    KnowledgeStatus,
    ProblemType,
    ReportDraft,
    ResultAsset,
)
from knowledge_compiler.phase1.skeleton import ReportSkeletonGenerator
from knowledge_compiler.phase1.teach import TeachContext, TeachModeEngine
from knowledge_compiler.phase1.visualization import VisualizationEngine


# 五种必须验证的动作类型
REQUIRED_ACTION_TYPES = {
    ActionType.GENERATE_PLOT,
    ActionType.EXTRACT_SECTION,
    ActionType.CALCULATE_METRIC,
    ActionType.COMPARE_DATA,
    ActionType.REORDER_CONTENT,
}


def _write(path: Path, content: str) -> None:
    """Helper to write file with parent directory creation"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_mock_openfoam_case(case_dir: Path) -> None:
    """
    创建最小化的 OpenFOAM 后向台阶案例目录结构

    目录结构：
    case_dir/
    ├── 0/                    # 初始条件
    │   ├── U
    │   └── p
    ├── 100/                  # 最终时间步
    │   ├── U
    │   └── p
    ├── system/
    │   └── controlDict
    ├── constant/
    │   └── polyMesh/
    │       └── points
    └── postProcessing/
        ├── forceCoeffs/0/coefficient.dat
        └── probes/0/U
    """
    # Initial conditions
    _write(case_dir / "0" / "U", "FoamFile { version 2.0; format ascii; }\ninternalField uniform (1 0 0);\n")
    _write(case_dir / "0" / "p", "FoamFile { version 2.0; format ascii; }\ninternalField uniform 0;\n")

    # Final time step
    _write(case_dir / "100" / "U", "FoamFile { version 2.0; format ascii; }\ninternalField uniform (0.8 0.1 0);\n")
    _write(case_dir / "100" / "p", "FoamFile { version 2.0; format ascii; }\ninternalField uniform -25;\n")

    # System files
    _write(case_dir / "system" / "controlDict", "application simpleFoam;\nstartFrom latestTime;\n")

    # Mesh marker (minimal)
    _write(case_dir / "constant" / "polyMesh" / "points", "FoamFile { version 2.0; format ascii; }\n4\n((0 0 0) (1 0 0) (1 1 0) (0 1 0))\n")

    # Post-processing outputs
    _write(
        case_dir / "postProcessing" / "forceCoeffs" / "0" / "coefficient.dat",
        "# Time Cd Cl Cm\n0 0.020 0.001 0.0\n100 0.018 0.002 0.0\n",
    )
    _write(
        case_dir / "postProcessing" / "probes" / "0" / "U",
        "# Probe velocity\n0 (1 0 0)\n100 (0.8 0.1 0)\n",
    )

    # Add OpenFOAM marker for solver detection (0.org/U/p style)
    # This is the marker that SolverType.detect looks for
    _write(case_dir / "0.org" / "U" / "p", "# OpenFOAM marker\n")


def _build_action_plan(manifest) -> ActionPlan:
    """
    从多条 NL 指令构建完整的 ActionPlan

    指令覆盖 5 种动作类型：
    1. "生成后向台阶压力云图和速度云图" -> GENERATE_PLOT (contour)
    2. "生成速度流线" -> GENERATE_PLOT (streamline)
    3. "提取 z=0.5 截面的速度分布" -> EXTRACT_SECTION
    4. "计算压力降" -> CALCULATE_METRIC
    5. "对比入口和出口的压力" -> COMPARE_DATA
    6. "按报告顺序：总览 截面 图表 数据表" -> REORDER_CONTENT
    """
    executor = NLPostprocessExecutor()

    instructions = [
        "生成后向台阶压力云图和速度云图",
        "生成速度流线",
        "提取 z=0.5 截面的速度分布",
        "计算压力降",
        "对比入口和出口的压力",
        "按报告顺序：总览 截面 图表 数据表",
    ]

    plans = [executor.parse_instruction(text, manifest) for text in instructions]

    # 验证所有 plan 都是可执行的
    assert all(plan.is_executable() for plan in plans), "Some action plans are not executable"

    # 合并所有 actions
    return ActionPlan(
        actions=[action for plan in plans for action in plan.actions],
        detected_intent="mixed",
        missing_assets=sorted({asset for plan in plans for asset in plan.missing_assets}),
        confidence=sum(plan.confidence for plan in plans) / len(plans),
        raw_instruction=" | ".join(plan.raw_instruction for plan in plans),
    )


def test_phase1_e2e_backward_step_real_postprocess_and_replay(tmp_path: Path) -> None:
    """
    完整 Phase 1 E2E 测试：后向台阶案例

    测试流程：
    1. 创建模拟 OpenFOAM 案例
    2. 解析结果目录生成 ResultManifest
    3. 从 NL 指令构建 ActionPlan
    4. 使用真实 Visualization Engine 生成图表
    5. 生成 ReportDraft
    6. 创建后向台阶黄金样板 ReportSpec
    7. 记录 Teach 操作和 CorrectionSpec
    8. 执行 Replay 验证
    """
    # 跳过条件：matplotlib 和 numpy 必须可用
    pytest.importorskip("matplotlib")
    pytest.importorskip("numpy")

    # ============================================================
    # Step 1: 创建模拟 OpenFOAM 后向台阶案例
    # ============================================================
    case_dir = tmp_path / "openfoam_backward_step"
    _create_mock_openfoam_case(case_dir)

    # ============================================================
    # Step 2: 解析结果目录
    # ============================================================
    parser = ResultDirectoryParser()
    manifest = parser.parse(case_dir, case_name="backward_step")

    # 添加 monitor point asset
    manifest.assets.append(
        ResultAsset(
            asset_type="monitor_point",
            path="postProcessing/probes/0/U",
            description="Probe velocity history",
        )
    )

    # 验证 manifest
    assert manifest.solver_type == "openfoam"
    assert manifest.case_name == "backward_step"
    assert any(asset.asset_type == "field" for asset in manifest.assets)

    # ============================================================
    # Step 3: 从 NL 指令构建 ActionPlan
    # ============================================================
    action_plan = _build_action_plan(manifest)

    # 验证覆盖了所有必需的动作类型
    executed_types = {a.action_type for a in action_plan.actions}
    assert REQUIRED_ACTION_TYPES.issubset(executed_types), \
        f"Missing action types: {REQUIRED_ACTION_TYPES - executed_types}"

    # ============================================================
    # Step 4: 使用真实 Visualization Engine 执行
    # ============================================================
    vis_engine = VisualizationEngine(
        output_root=str(tmp_path / "phase1_outputs"),
        is_mock=False,  # 使用真实 matplotlib 后端
    )

    action_log = vis_engine.execute_action_plan(action_plan, manifest)

    # 验证执行结果
    assert not action_log.errors, f"Execution errors: {action_log.errors}"
    assert len(action_log.execution_results) == len(action_plan.actions)

    # 验证所有 action 成功
    for result in action_log.execution_results:
        assert result["success"] is True, f"Action failed: {result}"

    # ============================================================
    # Step 5: 验证生成的输出文件
    # ============================================================
    # 验证 PNG 文件（真实图表）
    png_results = [
        result for result in action_log.execution_results
        if result["output_format"] == "png"
    ]
    assert len(png_results) >= 3, "Should have at least 3 PNG outputs"

    for result in png_results:
        output_path = Path(result["output_path"])
        assert output_path.exists(), f"PNG file not created: {output_path}"
        # 真实图表大小应 > 1000 bytes（非空占位符）
        assert output_path.stat().st_size > 1000, \
            f"PNG file too small (possibly placeholder): {output_path}"
        # 验证是真实模式生成的
        assert result["metadata"]["mode"] == "real", "Should use real visualization mode"

    # 验证 METRIC JSON 文件
    metric_result = next(
        (r for r in action_log.execution_results
         if r["action_type"] == ActionType.CALCULATE_METRIC.value),
        None
    )
    assert metric_result is not None, "No metric calculation result found"

    metric_path = Path(metric_result["output_path"])
    assert metric_path.exists()
    metric_data = json.loads(metric_path.read_text())
    assert metric_data["metric_type"] == "pressure_drop"
    assert metric_data["value"] > 0.0, "Pressure drop should be positive"

    # 验证 REORDER JSON 文件
    reorder_result = next(
        (r for r in action_log.execution_results
         if r["action_type"] == ActionType.REORDER_CONTENT.value),
        None
    )
    assert reorder_result is not None
    reorder_data = json.loads(Path(reorder_result["output_path"]).read_text())
    assert "sequence" in reorder_data
    assert len(reorder_data["sequence"]) > 0

    # ============================================================
    # Step 6: 生成 ReportDraft
    # ============================================================
    task_spec = {
        "task_spec_id": "TASK-BFS-E2E",
        "case_id": "backward_step",
        "problem_type": ProblemType.INTERNAL_FLOW.value,
        "geometry": {
            "step_height": 0.1,
            "expansion_ratio": 2.0,
        },
    }

    skeleton_gen = ReportSkeletonGenerator()
    draft = skeleton_gen.generate(task_spec, manifest, case_id=manifest.case_name)

    # 添加可视化输出到 draft
    draft.structure["visualization_outputs"] = action_log.execution_results

    # 验证 ReportDraft
    assert isinstance(draft, ReportDraft)
    assert draft.case_id == "backward_step"
    assert draft.plots, "Draft should have plots"
    assert draft.metrics, "Draft should have metrics"

    # ============================================================
    # Step 7: 创建后向台阶黄金样板 ReportSpec
    # ============================================================
    corrected_spec = create_backward_facing_step_spec(
        case_id="backward_step_e2e",
        reynolds_number=400.0,
        is_turbulent=False,
    )
    corrected_spec.knowledge_status = KnowledgeStatus.DRAFT

    # 验证黄金样板
    gold_validation = BackwardStepGateValidator().validate_report_spec(corrected_spec)
    assert gold_validation["passed"], f"Gold validation failed: {gold_validation['errors']}"

    # ============================================================
    # Step 8: 记录 Teach 操作和 CorrectionSpec
    # ============================================================
    teach_engine = TeachModeEngine(tmp_path / "teach_records")

    teach_response = teach_engine.record_operation(
        context=TeachContext(
            draft_id=draft.draft_id,
            case_id=draft.case_id,
            timestamp=time.time(),
            previous_state={
                "plots": [plot["name"] for plot in draft.plots],
                "metrics": [metric["name"] for metric in draft.metrics],
            },
            operation_type="add_plot",
        ),
        description="Add backward-step velocity profiles and reattachment metric",
        reason="Missing required backward-step plots and metrics for separated-flow validation",
        is_generalizable=True,
        metadata={"corrected_report_spec_id": corrected_spec.report_spec_id},
    )

    # 验证 Teach 记录
    corrections = teach_engine.list_corrections(
        teach_record_id=teach_response.teach_record_id
    )
    assert len(corrections) == 1

    correction = corrections[0]
    assert correction.error_type == ErrorType.MISSING_COMPONENT
    assert correction.impact_scope == ImpactScope.SIMILAR_CASES
    assert correction.needs_replay is True
    assert correction.replay_status == "pending"

    # 链接到 ReportSpec
    correction.link_to_report_spec(corrected_spec.report_spec_id)
    correction.replay_case_ids = [manifest.case_name]
    teach_engine.correction_recorder.save_correction(correction)

    # ============================================================
    # Step 9: 执行 Replay 验证
    # ============================================================
    historical = HistoricalReference(
        case_id=manifest.case_name,
        task_spec=task_spec,
        result_manifest=manifest,
        final_report_plans=[plot.name for plot in corrected_spec.required_plots],
        final_report_metrics=[metric.name for metric in corrected_spec.required_metrics],
        problem_type=ProblemType.INTERNAL_FLOW,
    )

    replay_engine = ReplayEngine(
        skeleton_generator=ReportSkeletonGenerator([corrected_spec]),
    )

    replay_batch = replay_engine.promote_to_candidate(
        corrected_spec,
        [historical],
        min_pass_rate=100.0,
    )

    # 验证 Replay 结果
    assert replay_batch.pass_rate == 100.0, \
        f"Replay pass rate: {replay_batch.pass_rate}%"

    replay_case = replay_batch.case_results[0]
    assert replay_case.success is True
    assert replay_case.overall_pass is True
    assert replay_case.plot_coverage == 1.0, "Plot coverage should be 100%"
    assert replay_case.metric_coverage == 1.0, "Metric coverage should be 100%"

    # 验证 ReportSpec 被提升为 CANDIDATE
    assert corrected_spec.knowledge_status == KnowledgeStatus.CANDIDATE

    # ============================================================
    # Step 10: 验证 Correction 标记为 passed
    # ============================================================
    assert teach_engine.mark_correction_replay_passed(correction.correction_id) is True

    verified_correction = teach_engine.get_correction(correction.correction_id)
    assert verified_correction is not None
    assert verified_correction.linked_report_spec_id == corrected_spec.report_spec_id
    assert verified_correction.replay_status == "passed"


def test_phase1_e2e_backward_step_nl_parsing_only(tmp_path: Path) -> None:
    """
    轻量级测试：仅验证 NL 解析和 ActionPlan 构建

    不依赖 matplotlib，适合快速验证 NL Postprocess 功能
    """
    # 创建最小案例
    case_dir = tmp_path / "minimal_case"
    _create_mock_openfoam_case(case_dir)

    # 解析
    parser = ResultDirectoryParser()
    manifest = parser.parse(case_dir, case_name="backward_step")

    # 构建多个 NL 指令的 ActionPlan
    action_plan = _build_action_plan(manifest)

    # 验证动作类型覆盖
    action_types = {a.action_type for a in action_plan.actions}
    assert REQUIRED_ACTION_TYPES.issubset(action_types)

    # 验证所有 action 都有必需参数
    for action in action_plan.actions:
        assert action.action_type in ActionType
        assert action.confidence > 0.0
        assert isinstance(action.parameters, dict)


def test_phase1_e2e_backward_step_mock_mode(tmp_path: Path) -> None:
    """
    MOCK 模式 E2E 测试：不生成真实图表

    适合在没有 matplotlib 的环境中运行
    """
    # 创建案例
    case_dir = tmp_path / "mock_case"
    _create_mock_openfoam_case(case_dir)

    # 解析
    parser = ResultDirectoryParser()
    manifest = parser.parse(case_dir, case_name="backward_step")

    # 构建 ActionPlan
    action_plan = _build_action_plan(manifest)

    # 使用 MOCK 模式
    vis_engine = VisualizationEngine(
        output_root=str(tmp_path / "mock_outputs"),
        is_mock=True,  # MOCK 模式
    )

    action_log = vis_engine.execute_action_plan(action_plan, manifest)

    # MOCK 模式应该成功但文件是占位符
    assert not action_log.errors
    assert len(action_log.execution_results) > 0

    # MOCK 模式的 PNG 文件应该是空占位符
    png_results = [
        r for r in action_log.execution_results
        if r["output_format"] == "png"
    ]
    for result in png_results:
        output_path = Path(result["output_path"])
        assert output_path.exists()
        # MOCK 模式文件可能很小或为空
        assert result["metadata"]["mode"] == "mock"
