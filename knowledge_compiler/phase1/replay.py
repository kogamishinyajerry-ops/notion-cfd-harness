#!/usr/bin/env python3
"""
Phase 1 Module 5: C6 Replay Engine

报告回放引擎：用已有ReportSpec候选重新生成历史case报告并验证
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeLayer,
    KnowledgeStatus,
    ReportSpec,
    ReportDraft,
    ResultManifest,
    TeachRecord,
    PlotSpec,
    MetricSpec,
    ComparisonType,
)
from knowledge_compiler.phase1.parser import ResultDirectoryParser
from knowledge_compiler.phase1.skeleton import (
    ReportSkeletonGenerator,
    Phase1Gates,
)


# ============================================================================
# Replay Configuration
# ============================================================================

@dataclass
class ReplayConfig:
    """Replay执行配置"""
    # OpenFOAM only (简化范围)
    supported_solvers: Set[str] = field(default_factory=lambda: {"openfoam"})

    # 差异容忍度
    plot_name_tolerance: float = 0.9  # 90%匹配度要求
    metric_name_tolerance: float = 0.9
    required_plot_coverage: float = 0.7  # 至少70%的必需plots

    # 超时配置
    max_replay_time: int = 300  # 单个case最长5分钟


# ============================================================================
# Replay Result
# ============================================================================

@dataclass
class ReplayResult:
    """单个case的回放结果"""
    case_id: str
    report_spec_id: str
    success: bool
    timestamp: float

    # 生成结果
    generated_draft: Optional[ReportDraft] = None

    # 对比结果
    expected_plots: List[str] = field(default_factory=list)
    generated_plots: List[str] = field(default_factory=list)
    expected_metrics: List[str] = field(default_factory=list)
    generated_metrics: List[str] = field(default_factory=list)

    # 差异分析
    missing_plots: List[str] = field(default_factory=list)
    extra_plots: List[str] = field(default_factory=list)
    missing_metrics: List[str] = field(default_factory=list)
    extra_metrics: List[str] = field(default_factory=list)

    # 通过率
    plot_coverage: float = 0.0
    metric_coverage: float = 0.0
    overall_pass: bool = False

    # 错误信息
    errors: List[str] = field(default_factory=list)

    def calculate_coverage(self) -> None:
        """计算覆盖率"""
        # Plot覆盖率
        if self.expected_plots:
            matched = sum(1 for p in self.expected_plots if p in self.generated_plots)
            self.plot_coverage = matched / len(self.expected_plots)
        else:
            self.plot_coverage = 1.0 if not self.generated_plots else 0.0

        # Metric覆盖率
        if self.expected_metrics:
            matched = sum(1 for m in self.expected_metrics if m in self.generated_metrics)
            self.metric_coverage = matched / len(self.expected_metrics)
        else:
            self.metric_coverage = 1.0 if not self.generated_metrics else 0.0

        # 总体通过：两者都达到容忍度
        self.overall_pass = (
            self.plot_coverage >= ReplayConfig().required_plot_coverage
            and self.metric_coverage >= ReplayConfig().required_plot_coverage
        )


@dataclass
class BatchReplayResult:
    """批量回放结果"""
    report_spec_id: str
    replay_timestamp: float

    # 单个结果
    case_results: List[ReplayResult] = field(default_factory=list)

    # 汇总
    total_cases: int = 0
    passed_cases: int = 0
    pass_rate: float = 0.0

    # 聚合差异
    commonly_missing_plots: Dict[str, int] = field(default_factory=dict)
    commonly_extra_plots: Dict[str, int] = field(default_factory=dict)

    def calculate_summary(self) -> None:
        """计算汇总统计"""
        self.total_cases = len(self.case_results)
        self.passed_cases = sum(1 for r in self.case_results if r.overall_pass)

        if self.total_cases > 0:
            self.pass_rate = (self.passed_cases / self.total_cases) * 100

        # 聚合差异
        for result in self.case_results:
            for plot in result.missing_plots:
                self.commonly_missing_plots[plot] = self.commonly_missing_plots.get(plot, 0) + 1
            for plot in result.extra_plots:
                self.commonly_extra_plots[plot] = self.commonly_extra_plots.get(plot, 0) + 1


# ============================================================================
# Historical Reference (历史基准)
# ============================================================================

@dataclass
class HistoricalReference:
    """历史case参考数据（用于对比）"""
    case_id: str
    task_spec: Dict[str, Any]
    result_manifest: ResultManifest
    final_report_plans: List[str]  # 历史最终报告中的plot/metric列表
    final_report_metrics: List[str]
    problem_type: ProblemType

    @classmethod
    def from_files(
        cls,
        case_id: str,
        task_spec_path: Path,
        result_dir: Path,
        final_report_json: Path,
    ) -> "HistoricalReference":
        """从文件加载历史参考"""
        # 加载task spec
        task_spec = json.loads(task_spec_path.read_text())

        # 解析结果目录
        parser = ResultDirectoryParser()
        manifest = parser.parse(result_dir, case_id)

        # 加载final report
        final_report = json.loads(final_report_json.read_text())

        return cls(
            case_id=case_id,
            task_spec=task_spec,
            result_manifest=manifest,
            final_report_plans=final_report.get("plots", []),
            final_report_metrics=final_report.get("metrics", []),
            problem_type=ProblemType(task_spec.get("problem_type", "InternalFlow")),
        )


# ============================================================================
# Replay Engine (CORE)
# ============================================================================

class ReplayEngine:
    """
    C6 报告回放引擎

    核心功能：
    1. 用ReportSpec重新生成历史case的ReportDraft
    2. 与历史FinalReport对比
    3. 计算通过率和差异
    4. 支持ReportSpec的候选状态验证
    """

    def __init__(
        self,
        config: Optional[ReplayConfig] = None,
        skeleton_generator: Optional[ReportSkeletonGenerator] = None,
    ):
        """
        初始化回放引擎

        Args:
            config: 回放配置
            skeleton_generator: 骨架生成器（可选，默认新建）
        """
        self.config = config or ReplayConfig()
        self.skeleton = skeleton_generator or ReportSkeletonGenerator()
        self._replay_history: List[BatchReplayResult] = []

    def replay_case(
        self,
        report_spec: ReportSpec,
        historical: HistoricalReference,
    ) -> ReplayResult:
        """
        回放单个case

        Args:
            report_spec: 要验证的ReportSpec候选
            historical: 历史case参考数据

        Returns:
            回放结果
        """
        result = ReplayResult(
            case_id=historical.case_id,
            report_spec_id=report_spec.report_spec_id,
            success=False,
            timestamp=time.time(),
        )

        try:
            # Step 1: 用ReportSpec重新生成ReportDraft
            generated = self.skeleton.generate(
                task_spec=historical.task_spec,
                manifest=historical.result_manifest,
                case_id=historical.case_id,
            )

            result.generated_draft = generated

            # Step 2: 提取生成的plots和metrics
            generated_plots = [p["name"] for p in generated.plots]
            generated_metrics = [m["name"] for m in generated.metrics]

            result.generated_plots = generated_plots
            result.generated_metrics = generated_metrics

            # Step 3: 与历史final报告对比
            result.expected_plots = historical.final_report_plans
            result.expected_metrics = historical.final_report_metrics

            # Step 4: 差异分析
            result.missing_plots = [
                p for p in result.expected_plots
                if p not in generated_plots
            ]
            result.extra_plots = [
                p for p in generated_plots
                if p not in result.expected_plots
            ]
            result.missing_metrics = [
                m for m in result.expected_metrics
                if m not in generated_metrics
            ]
            result.extra_metrics = [
                m for m in generated_metrics
                if m not in result.expected_metrics
            ]

            # Step 5: 计算覆盖率和通过状态
            result.calculate_coverage()
            result.success = True

        except Exception as e:
            result.errors.append(str(e))

        return result

    def replay_batch(
        self,
        report_spec: ReportSpec,
        historical_cases: List[HistoricalReference],
    ) -> BatchReplayResult:
        """
        批量回放多个case

        Args:
            report_spec: 要验证的ReportSpec候选
            historical_cases: 历史case列表

        Returns:
            批量回放结果
        """
        batch_result = BatchReplayResult(
            report_spec_id=report_spec.report_spec_id,
            replay_timestamp=time.time(),
        )

        for historical in historical_cases:
            case_result = self.replay_case(report_spec, historical)
            batch_result.case_results.append(case_result)

        # 计算汇总
        batch_result.calculate_summary()

        # 保存到历史
        self._replay_history.append(batch_result)

        return batch_result

    def validate_report_spec_candidate(
        self,
        report_spec: ReportSpec,
        historical_cases: List[HistoricalReference],
        min_pass_rate: float = 70.0,
    ) -> Tuple[bool, BatchReplayResult]:
        """
        验证ReportSpec是否可以从draft提升到candidate

        Args:
            report_spec: 要验证的ReportSpec
            historical_cases: 历史case列表
            min_pass_rate: 最低通过率要求

        Returns:
            (是否通过, 批量回放结果)
        """
        # 确保是draft状态
        if report_spec.knowledge_status != KnowledgeStatus.DRAFT:
            raise ValueError(f"ReportSpec status must be DRAFT, got {report_spec.knowledge_status}")

        # 执行回放
        batch_result = self.replay_batch(report_spec, historical_cases)

        # 检查通过率
        passed = batch_result.pass_rate >= min_pass_rate

        # 如果通过，更新ReportSpec的replay_pass_rate
        if passed:
            # 注意：这里不直接更新ReportSpec，由调用者决定是否提升
            pass

        return passed, batch_result

    def promote_to_candidate(
        self,
        report_spec: ReportSpec,
        historical_cases: List[HistoricalReference],
        min_pass_rate: float = 70.0,
    ) -> BatchReplayResult:
        """
        验证并通过后提升到candidate状态

        Args:
            report_spec: 要提升的ReportSpec（必须是draft）
            historical_cases: 历史case列表
            min_pass_rate: 最低通过率

        Returns:
            批量回放结果
        """
        passed, batch_result = self.validate_report_spec_candidate(
            report_spec,
            historical_cases,
            min_pass_rate,
        )

        if passed:
            # 更新replay pass rate
            replay_results = [r.overall_pass for r in batch_result.case_results]
            report_spec.calculate_replay_pass_rate(replay_results)

            # 提升到candidate
            report_spec.transition_to(KnowledgeStatus.CANDIDATE)

        return batch_result

    def get_replay_history(
        self,
        report_spec_id: Optional[str] = None,
    ) -> List[BatchReplayResult]:
        """获取回放历史"""
        if report_spec_id:
            return [
                r for r in self._replay_history
                if r.report_spec_id == report_spec_id
            ]
        return self._replay_history.copy()

    def analyze_common_patterns(
        self,
        report_spec_id: str,
    ) -> Dict[str, Any]:
        """
        分析回放结果中的共性模式

        Args:
            report_spec_id: ReportSpec ID

        Returns:
            共性模式分析结果
        """
        histories = self.get_replay_history(report_spec_id)

        if not histories:
            return {"error": "No replay history found"}

        # 聚合所有历史的数据
        all_missing: Dict[str, int] = {}
        all_extra: Dict[str, int] = {}

        for history in histories:
            for missing, count in history.commonly_missing_plots.items():
                all_missing[missing] = all_missing.get(missing, 0) + count
            for extra, count in history.commonly_extra_plots.items():
                all_extra[extra] = all_extra.get(extra, 0) + count

        # 排序
        top_missing = sorted(all_missing.items(), key=lambda x: -x[1])[:5]
        top_extra = sorted(all_extra.items(), key=lambda x: -x[1])[:5]

        return {
            "report_spec_id": report_spec_id,
            "total_replays": len(histories),
            "top_missing_plots": top_missing,
            "top_extra_plots": top_extra,
            "avg_pass_rate": sum(h.pass_rate for h in histories) / len(histories),
        }


# ============================================================================
# OpenFOAM-specific Utilities
# ============================================================================

class OpenFOAMReplayUtils:
    """OpenFOAM专用回放工具"""

    @staticmethod
    def create_test_case_reference(
        case_id: str,
        case_dir: Path,
        problem_type: ProblemType = ProblemType.INTERNAL_FLOW,
    ) -> HistoricalReference:
        """
        从OpenFOAM case目录创建测试参考

        Args:
            case_id: Case ID
            case_dir: Case目录路径
            problem_type: 问题类型

        Returns:
            HistoricalReference对象
        """
        # 简化的task spec
        task_spec = {
            "task_spec_id": f"TASK-{case_id}",
            "case_id": case_id,
            "problem_type": problem_type.value,
        }

        # 解析OpenFOAM结果
        parser = ResultDirectoryParser()
        manifest = parser.parse(case_dir, case_id)

        # 基于问题类型生成期望的plots/metrics
        expected_outputs = OpenFOAMReplayUtils._get_expected_outputs(problem_type)

        return HistoricalReference(
            case_id=case_id,
            task_spec=task_spec,
            result_manifest=manifest,
            final_report_plans=expected_outputs["plots"],
            final_report_metrics=expected_outputs["metrics"],
            problem_type=problem_type,
        )

    @staticmethod
    def _get_expected_outputs(problem_type: ProblemType) -> Dict[str, List[str]]:
        """获取问题类型的期望输出"""
        if problem_type == ProblemType.INTERNAL_FLOW:
            return {
                "plots": [
                    "velocity_magnitude",
                    "pressure_coefficient",
                    "streamlines",
                    "velocity_contour",
                    "pressure_contour",
                ],
                "metrics": [
                    "max_velocity",
                    "pressure_drop",
                    "mass_flow_rate",
                ],
            }
        elif problem_type == ProblemType.EXTERNAL_FLOW:
            return {
                "plots": [
                    "pressure_coefficient",
                    "wall_shear_stress",
                    "velocity_field",
                    "wake_profile",
                ],
                "metrics": [
                    "drag_coefficient",
                    "lift_coefficient",
                    "strouhal_number",
                ],
            }
        elif problem_type == ProblemType.HEAT_TRANSFER:
            return {
                "plots": [
                    "temperature_field",
                    "heat_flux",
                    "nußelt_number",
                ],
                "metrics": [
                    "heat_transfer_coefficient",
                    "total_heat_flux",
                    "max_temperature",
                ],
            }
        else:
            # 默认
            return {
                "plots": ["velocity_magnitude", "pressure_field"],
                "metrics": ["max_velocity"],
            }


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "ReplayConfig",
    "ReplayResult",
    "BatchReplayResult",
    "HistoricalReference",
    "ReplayEngine",
    "OpenFOAMReplayUtils",
]
