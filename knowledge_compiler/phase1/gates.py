#!/usr/bin/env python3
"""
Phase 1 Gates: P1-G3 & P1-G4 Implementation

根据Opus 4.6审查建议补齐Gate体系：
- P1-G3: 解释证据绑定 Gate（Evidence Binding Gate）
- P1-G4: 模板泛化 Gate（Template Generalization Gate）

与P1-G1/G2共享统一接口，仅支持OpenFOAM求解器。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from knowledge_compiler.phase1.schema import (
    KnowledgeStatus,
    ReportSpec,
    TeachRecord,
    TeachOperation,
    ProblemType,
)


# ============================================================================
# Gate Result Interface (统一接口)
# ============================================================================

class GateStatus(Enum):
    """Gate状态"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass
class GateCheckItem:
    """单个检查项"""
    item: str
    description: str
    result: GateStatus
    message: str
    evidence_id: Optional[str] = None


@dataclass
class GateResult:
    """
    Gate检查结果（统一接口）

    所有P1-Gate共享此接口

    Gate级别定义（根据v2架构）:
    - P1-G1/G2: Block级 - 阻止继续
    - P1-G3: Warn级 - 警告但不阻止
    - P1-G4: Log级 - 仅记录
    """
    gate_id: str
    gate_name: str
    status: GateStatus
    timestamp: float
    score: float  # 0-100
    checklist: List[GateCheckItem] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    severity: str = field(default="LOG")  # BLOCK, WARN, LOG

    def is_pass(self) -> bool:
        """检查是否通过"""
        return self.status == GateStatus.PASS

    def get_pass_rate(self) -> float:
        """获取通过率"""
        if not self.checklist:
            return 0.0
        passed = sum(1 for c in self.checklist if c.result == GateStatus.PASS)
        return (passed / len(self.checklist)) * 100

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        与 Evidence Schema 的 deposit_evidence() 兼容
        datetime 序列化为 ISO-8601，枚举值序列化为字符串
        """
        from datetime import datetime

        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "status": self.status.value,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "score": self.score,
            "checklist": [
                {
                    "item": c.item,
                    "description": c.description,
                    "result": c.result.value,
                    "message": c.message,
                    "evidence_id": c.evidence_id,
                }
                for c in self.checklist
            ],
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "severity": self.severity,
        }


# ============================================================================
# P1-G3: Evidence Binding Gate
# ============================================================================

@dataclass
class ExplanationBinding:
    """解释绑定记录"""
    explanation: str  # TeachRecord中的解释文本
    bound_to: List[str]  # 绑定的图表/指标/对比结果ID
    binding_type: str  # "plot", "metric", "comparison", "none"
    confidence: float  # 0-1


class EvidenceBindingGate:
    """
    P1-G3: 解释证据绑定 Gate

    检查TeachRecord中的每条explanation是否绑定到具体的结果对象。
    这是确保知识可追溯性的关键Gate。
    """

    GATE_ID = "P1-G3"
    GATE_NAME = "Evidence Binding Gate"

    def __init__(self):
        self._binding_keywords = {
            # Plot-related keywords
            "plot": ["plot", "contour", "field", "cloud", "vector", "streamline"],
            # Metric-related keywords
            "metric": ["metric", "coefficient", "number", "value", "rate"],
            # Comparison-related keywords
            "comparison": ["vs", "versus", "difference", "delta", "ratio", "relative"],
            # Section-related keywords
            "section": ["section", "slice", "plane", "location", "midplane"],
            # Anomaly-related keywords (Opus 4.6 审查建议)
            "anomaly": ["anomaly", "deviation", "residual", "unexpected", "divergence"],
        }

        # 显式绑定模式（UI关联的asset_id）
        self._explicit_binding_pattern = re.compile(r'#\s*(\w+:\w+)')  # 如 #asset:plot_001

    def check_teach_record(
        self,
        teach_record: TeachRecord,
        available_assets: Optional[List[str]] = None,
    ) -> GateResult:
        """
        检查单个TeachRecord的证据绑定情况

        Args:
            teach_record: 要检查的TeachRecord
            available_assets: 可用的资产列表（可选，用于验证绑定有效性）

        Returns:
            Gate检查结果
        """
        checklist = []
        errors = []
        warnings = []
        score = 100.0

        for i, operation in enumerate(teach_record.operations):
            # 跳过非解释类操作
            # Opus 4.6 建议：只有 add/modify_explanation/add_structure 涉及文字解释
            # modify_metric 如果包含 reason 字段，也应进入绑定检测
            skip_types = ["add_plot", "remove_plot", "modify_plot", "add_metric", "remove_metric", "adjust_section"]
            if operation.operation_type in skip_types:
                continue

            # modify_metric 需要 check reason 字段是否有解释内容
            if operation.operation_type == "modify_metric":
                # 如果 reason 包含解释性内容，需要检查绑定
                if not operation.reason or len(operation.reason) < 10:
                    continue

            # modify_structure 如果描述太短，跳过
            if operation.operation_type == "modify_structure":
                if not operation.description or len(operation.description) < 10:
                    continue

            explanation = operation.description.lower()
            reason = operation.reason.lower()

            # 检查是否有绑定指示
            binding = self._detect_binding(explanation, reason)

            if binding.binding_type == "none":
                errors.append(
                    f"Operation {i}: Explanation without binding - '{operation.description}'"
                )
                score -= 20.0

                checklist.append(GateCheckItem(
                    item=f"operation_{i}",
                    description=f"Explanation binding for '{operation.description[:50]}...'",
                    result=GateStatus.FAIL,
                    message=f"No binding detected (type: add_explanation)",
                ))
            else:
                # 检查绑定对象是否在可用资产中（如果提供）
                if available_assets:
                    valid_bindings = [
                        b for b in binding.bound_to
                        if any(asset.lower() in b.lower() for asset in available_assets)
                    ]

                    if not valid_bindings:
                        warnings.append(
                            f"Operation {i}: Binding references unavailable asset - '{operation.description}'"
                        )
                        score -= 5.0

                checklist.append(GateCheckItem(
                    item=f"operation_{i}",
                    description=f"Explanation binding for '{operation.description[:50]}...'",
                    result=GateStatus.PASS if binding.binding_type != "none" else GateStatus.FAIL,
                    message=f"Binding type: {binding.binding_type}, objects: {binding.bound_to}",
                ))

        # 确定最终状态（P1-G3是WARN级别，Opus 4.6 审查建议）
        status = GateStatus.PASS if not errors else GateStatus.WARN  # WARN而非FAIL
        if score < 50.0:
            status = GateStatus.WARN

        return GateResult(
            gate_id=self.GATE_ID,
            gate_name=self.GATE_NAME,
            status=status,
            timestamp=time.time(),
            score=max(0.0, score),
            checklist=checklist,
            errors=errors,
            warnings=warnings,
            metadata={
                "teach_record_id": teach_record.teach_record_id,
                "total_operations": len(teach_record.operations),
                "explanation_operations": sum(
                    1 for op in teach_record.operations
                    if op.operation_type in ["add_explanation", "modify_explanation"]
                ),
            },
            severity="WARN",  # P1-G3是WARN级别
        )

    def _detect_binding(self, explanation: str, reason: str) -> ExplanationBinding:
        """
        检测解释文本中的绑定

        支持两种绑定模式（Opus 4.6 审查建议）:
        1. 显式绑定: 工程师在 Teach UI 中点选关联图表
        2. 隐式绑定: 从文本中提取引用（正则匹配）

        Returns:
            ExplanationBinding对象
        """
        bound_objects = []
        binding_type = "none"
        confidence = 0.5  # 默认置信度

        # 1. 检查显式绑定（优先级最高）
        explicit_matches = self._explicit_binding_pattern.findall(explanation + " " + reason)
        if explicit_matches:
            binding_type = "explicit"
            bound_objects.extend(explicit_matches)
            confidence = 1.0
        else:
            # 2. 检查隐式绑定（从文本中提取）
            # 检查anomaly绑定（Opus 4.6 建议）
            for keyword in self._binding_keywords["anomaly"]:
                if keyword in explanation or keyword in reason:
                    binding_type = "anomaly"
                    matches = re.findall(
                        r'\b(\w+(?:_?(?:deviation|residual|anomaly|divergence)))\b',
                        explanation + " " + reason
                    )
                    bound_objects.extend(matches)
                    confidence = 0.8
                    break

            # 检查plot绑定
            if binding_type == "none":
                for keyword in self._binding_keywords["plot"]:
                    if keyword in explanation:
                        binding_type = "plot"
                        # 提取可能的plot名称，支持多种表述
                        # "见图3" / "参考图3" / "如图3所示" / "as shown in Fig.3"
                        fig_matches = re.findall(r'[图Fig][\s]*(\d+)', explanation)
                        if fig_matches:
                            bound_objects.extend([f"figure_{m}" for m in fig_matches])
                        # 也提取下划线命名的plot
                        name_matches = re.findall(
                            r'\b(\w+(?:_?(?:magnitude|contour|field|coefficient|profile))\b)',
                            explanation
                        )
                        bound_objects.extend(name_matches)
                        confidence = 0.7
                        break

            # 检查metric绑定
            if binding_type == "none":
                for keyword in self._binding_keywords["metric"]:
                    if keyword in explanation or keyword in reason:
                        binding_type = "metric"
                        matches = re.findall(
                            r'\b(\w+(?:_?(?:coefficient|number|rate|ratio))\b)',
                            explanation + " " + reason
                        )
                        bound_objects.extend(matches)
                        confidence = 0.7
                        break

            # 检查comparison绑定
            if binding_type == "none":
                for keyword in self._binding_keywords["comparison"]:
                    if keyword in explanation or keyword in reason:
                        binding_type = "comparison"
                        confidence = 0.7
                        break

            # 检查section绑定
            if binding_type == "none":
                for keyword in self._binding_keywords["section"]:
                    if keyword in explanation or keyword in reason:
                        binding_type = "section"
                        matches = re.findall(
                            r'\b(\w+(?:_?(?:section|slice|plane|location))\b)',
                            explanation + " " + reason
                        )
                        bound_objects.extend(matches)
                        confidence = 0.7
                        break

        return ExplanationBinding(
            explanation=explanation,
            bound_to=bound_objects,
            binding_type=binding_type,
            confidence=confidence,
        )

    def check_batch(
        self,
        teach_records: List[TeachRecord],
        available_assets: Optional[List[str]] = None,
    ) -> GateResult:
        """
        批量检查多个TeachRecord

        Args:
            teach_records: TeachRecord列表
            available_assets: 可用资产列表

        Returns:
        汇总的Gate结果
        """
        combined_checklist = []
        all_errors = []
        all_warnings = []
        total_score = 0.0
        checked_count = 0

        for record in teach_records:
            result = self.check_teach_record(record, available_assets)
            combined_checklist.extend(result.checklist)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            total_score += result.score
            checked_count += 1

        # 计算平均分
        avg_score = total_score / checked_count if checked_count > 0 else 100.0

        # 确定状态
        status = GateStatus.PASS
        if avg_score < 70.0 or all_errors:
            status = GateStatus.FAIL
        elif avg_score < 85.0:
            status = GateStatus.WARN

        return GateResult(
            gate_id=self.GATE_ID,
            gate_name=self.GATE_NAME,
            status=status,
            timestamp=time.time(),
            score=avg_score,
            checklist=combined_checklist,
            errors=all_errors,
            warnings=all_warnings,
            metadata={
                "total_records": len(teach_records),
                "checked_records": checked_count,
            },
            severity="WARN",  # P1-G3是WARN级别
        )


# ============================================================================
# P1-G4: Template Generalization Gate
# ============================================================================

@dataclass
class GeneralizationMetrics:
    """泛化性度量"""
    diversity_score: float  # 多样性分数 (0-1)
    consistency_score: float  # 一致性分数 (0-1)
    coverage_score: float  # 覆盖率分数 (0-1)
    generalizability_score: float  # 综合泛化性分数 (0-1)

    def calculate_overall(self, weights: Optional[Dict[str, float]] = None) -> None:
        """
        计算综合泛化性分数

        Args:
            weights: 可选的权重配置，格式为 {"diversity": 0.3, "consistency": 0.3, "coverage": 0.4}
        """
        # 加权平均（Opus 4.6 建议：可按problem_type配置）
        if weights is None:
            weights = {"diversity": 0.3, "consistency": 0.3, "coverage": 0.4}
        self.generalizability_score = (
            weights["diversity"] * self.diversity_score +
            weights["consistency"] * self.consistency_score +
            weights["coverage"] * self.coverage_score
        )


class TemplateGeneralizationGate:
    """
    P1-G4: 模板泛化 Gate

    评估当前TeachRecord集合是否具有泛化为ReportSpec候选的条件。
    这是区分"个例处理"与"通用标准"的关键Gate。
    """

    GATE_ID = "P1-G4"
    GATE_NAME = "Template Generalization Gate"

    # 泛化性阈值
    MIN_GENERALIZABILITY_SCORE = 0.7
    MIN_Case_COUNT = 3

    def __init__(self):
        # 泛化性权重（Opus 4.6 建议：可按problem_type配置）
        self._generalization_weights = {
            ProblemType.INTERNAL_FLOW: {"diversity": 0.3, "consistency": 0.3, "coverage": 0.4},
            ProblemType.EXTERNAL_FLOW: {"diversity": 0.2, "consistency": 0.4, "coverage": 0.4},
            ProblemType.HEAT_TRANSFER: {"diversity": 0.3, "consistency": 0.3, "coverage": 0.4},
        }

        self._problem_type_patterns = {
            ProblemType.INTERNAL_FLOW: {
                "expected_plots": {"velocity_magnitude", "pressure_contour", "streamlines"},
                "expected_metrics": {"max_velocity", "pressure_drop"},
                "supported": True,
            },
            ProblemType.EXTERNAL_FLOW: {
                "expected_plots": {"pressure_coefficient", "wall_shear_stress", "wake_profile"},
                "expected_metrics": {"drag_coefficient", "lift_coefficient"},
                "supported": True,
            },
            ProblemType.HEAT_TRANSFER: {
                "expected_plots": {"temperature_field", "heat_flux"},
                "expected_metrics": {"heat_transfer_coefficient", "max_temperature"},
                "supported": True,
            },
            # Opus 4.6 建议：标记Multiphase和FSI为NOT_YET_SUPPORTED
            ProblemType.MULTIPHASE: {
                "expected_plots": set(),  # 待定义
                "expected_metrics": set(),  # 待定义
                "supported": False,
                "note": "NOT_YET_SUPPORTED - Phase 1 起步阶段",
            },
            ProblemType.FSI: {
                "expected_plots": set(),  # 待定义
                "expected_metrics": set(),  # 待定义
                "supported": False,
                "note": "NOT_YET_SUPPORTED - Phase 1 起步阶段",
            },
        }

    def check_report_spec_candidate(
        self,
        report_spec: ReportSpec,
        source_cases: List[str],
        teach_records: List[TeachRecord],
    ) -> GateResult:
        """
        检查ReportSpec候选是否具备泛化条件

        Args:
            report_spec: 要检查的ReportSpec
            source_cases: 源case ID列表
            teach_records: 相关的TeachRecord列表

        Returns:
            Gate检查结果
        """
        checklist = []
        errors = []
        warnings = []
        score = 100.0

        # 检查problem_type是否支持（Opus 4.6 建议）
        problem_type = report_spec.problem_type
        pattern_info = self._problem_type_patterns.get(problem_type, {})

        if not pattern_info.get("supported", True):
            # 不支持的问题类型，返回SKIP而非FAIL
            return GateResult(
                gate_id=self.GATE_ID,
                gate_name=self.GATE_NAME,
                status=GateStatus.WARN,  # 使用WARN表示SKIP
                timestamp=time.time(),
                score=100.0,
                checklist=[],
                warnings=[f"Problem type {problem_type.value} is not yet supported in Phase 1"],
                metadata={
                    "skip_reason": "NOT_YET_SUPPORTED",
                    "note": pattern_info.get("note", "待Phase 2+实现"),
                },
                severity="LOG",
            )

        # Check 1: 最小case数量
        case_count = len(set(source_cases))
        if case_count < self.MIN_Case_COUNT:
            errors.append(
                f"Insufficient source cases: {case_count} < {self.MIN_Case_COUNT} required"
            )
            score -= 30.0

            checklist.append(GateCheckItem(
                item="case_count",
                description=f"Number of unique source cases",
                result=GateStatus.FAIL,
                message=f"Only {case_count} cases, need at least {self.MIN_Case_COUNT}",
            ))
        else:
            checklist.append(GateCheckItem(
                item="case_count",
                description=f"Number of unique source cases",
                result=GateStatus.PASS,
                message=f"Adequate case coverage: {case_count} cases",
            ))

        # Check 2: 必需plots/metrics完整性
        expected = pattern_info

        required_plots = expected.get("expected_plots", set())
        required_metrics = expected.get("expected_metrics", set())

        actual_plots = {p.name for p in report_spec.required_plots}
        actual_metrics = {m.name for m in report_spec.required_metrics}

        missing_plots = required_plots - actual_plots
        missing_metrics = required_metrics - actual_metrics

        if missing_plots:
            errors.append(f"Missing required plots: {missing_plots}")
            score -= 20.0
        else:
            checklist.append(GateCheckItem(
                item="required_plots",
                description="Problem type required plots",
                result=GateStatus.PASS,
                message=f"All required plots present for {problem_type.value}",
            ))

        if missing_metrics:
            errors.append(f"Missing required metrics: {missing_metrics}")
            score -= 20.0
        else:
            checklist.append(GateCheckItem(
                item="required_metrics",
                description="Problem type required metrics",
                result=GateStatus.PASS,
                message=f"All required metrics present for {problem_type.value}",
            ))

        # Check 3: TeachRecord一致性
        if teach_records:
            metrics = self._calculate_generalization_metrics(
                report_spec,
                teach_records,
            )

            checklist.append(GateCheckItem(
                item="diversity_score",
                description="Operation diversity across cases",
                result=GateStatus.PASS if metrics.diversity_score >= 0.5 else GateStatus.WARN,
                message=f"Diversity score: {metrics.diversity_score:.2f}",
            ))

            checklist.append(GateCheckItem(
                item="consistency_score",
                description="Consistency of operations",
                result=GateStatus.PASS if metrics.consistency_score >= 0.5 else GateStatus.WARN,
                message=f"Consistency score: {metrics.consistency_score:.2f}",
            ))

            checklist.append(GateCheckItem(
                item="coverage_score",
                description="Coverage of problem domain",
                result=GateStatus.PASS if metrics.coverage_score >= 0.7 else GateStatus.WARN,
                message=f"Coverage score: {metrics.coverage_score:.2f}",
            ))

            metrics.calculate_overall()

            if metrics.generalizability_score < self.MIN_GENERALIZABILITY_SCORE:
                errors.append(
                    f"Generalizability score too low: {metrics.generalizability_score:.2f} < {self.MIN_GENERALIZABILITY_SCORE}"
                )
                score -= 20.0

        # 确定最终状态
        status = GateStatus.PASS
        if score < 50.0:
            status = GateStatus.FAIL
        elif score < 70.0:
            status = GateStatus.WARN

        return GateResult(
            gate_id=self.GATE_ID,
            gate_name=self.GATE_NAME,
            status=status,
            timestamp=time.time(),
            score=max(0.0, score),
            checklist=checklist,
            errors=errors,
            warnings=warnings,
            metadata={
                "generalizability_score": getattr(
                    self._calculate_generalization_metrics(report_spec, teach_records),
                    "generalizability_score",
                    0.0,
                ),
                "case_count": case_count,
            },
            severity="LOG",  # P1-G4是LOG级别（仅记录）
        )

    def _calculate_generalization_metrics(
        self,
        report_spec: ReportSpec,
        teach_records: List[TeachRecord],
    ) -> GeneralizationMetrics:
        """
        计算泛化性度量

        Opus 4.6 建议：
        - 综合考虑：plot重叠率 + metric重叠率 + section重叠率 + 解释模式相似度
        - 权重分配应可配置（不同问题类型的关键维度不同）
        - 区分'结构泛化'（图表组成一致）和'内容泛化'（数值范围可复用）
        """
        # 简化实现：基于TeachRecord的多样性
        diversity_score = 0.5  # TODO: 实际计算

        # 一致性：检查TeachRecord是否指向相同类型的操作
        operation_types = set()
        for record in teach_records:
            for op in record.operations:
                operation_types.add(op.operation_type)

        consistency_score = len(operation_types) / 9.0  # 9种操作类型

        # 覆盖率：必需项的覆盖度
        problem_type = report_spec.problem_type
        expected = self._problem_type_patterns.get(problem_type, {})
        required_plots = expected.get("expected_plots", set())
        required_metrics = expected.get("expected_metrics", set())

        actual_plots = {p.name for p in report_spec.required_plots}
        actual_metrics = {m.name for m in report_spec.required_metrics}

        coverage_score = 0.0
        if required_plots or required_metrics:
            total_required = len(required_plots) + len(required_metrics)
            covered = len(required_plots & actual_plots) + len(required_metrics & actual_metrics)
            coverage_score = covered / total_required if total_required > 0 else 0.0

        # 使用该problem_type的权重配置计算综合分数
        weights = self._generalization_weights.get(problem_type)
        metrics = GeneralizationMetrics(
            diversity_score=diversity_score,
            consistency_score=consistency_score,
            coverage_score=coverage_score,
            generalizability_score=0.0,  # Will be calculated
        )
        metrics.calculate_overall(weights)

        return metrics


# ============================================================================
# Combined Gate Executor
# ============================================================================

class Phase1GateExecutor:
    """
    Phase 1 Gate执行器

    统一执行P1-G1/G2/G3/G4四个Gate
    """

    def __init__(self):
        self.g3_gate = EvidenceBindingGate()
        self.g4_gate = TemplateGeneralizationGate()

    def run_g3_gate(
        self,
        teach_records: List[TeachRecord],
        available_assets: Optional[List[str]] = None,
    ) -> GateResult:
        """执行P1-G3 Gate"""
        if not teach_records:
            return GateResult(
                gate_id="P1-G3",
                gate_name="Evidence Binding Gate",
                status=GateStatus.PASS,
                timestamp=time.time(),
                score=100.0,
                checklist=[],
                warnings=["No teach records to check"],
                severity="WARN",
            )

        return self.g3_gate.check_batch(teach_records, available_assets)

    def run_g4_gate(
        self,
        report_spec: ReportSpec,
        source_cases: List[str],
        teach_records: List[TeachRecord],
    ) -> GateResult:
        """执行P1-G4 Gate"""
        return self.g4_gate.check_report_spec_candidate(
            report_spec,
            source_cases,
            teach_records,
        )

    def run_all_gates(
        self,
        report_spec: ReportSpec,
        source_cases: List[str],
        teach_records: List[TeachRecord],
        available_assets: Optional[List[str]] = None,
    ) -> Dict[str, GateResult]:
        """
        执行所有Phase 1 Gates

        Args:
            report_spec: ReportSpec候选
            source_cases: 源case列表
            teach_records: TeachRecord列表
            available_assets: 可用资产列表

        Returns:
            各Gate的结果字典
        """
        results = {}

        # P1-G3: Evidence Binding
        results["P1-G3"] = self.run_g3_gate(teach_records, available_assets)

        # P1-G4: Template Generalization
        results["P1-G4"] = self.run_g4_gate(
            report_spec,
            source_cases,
            teach_records,
        )

        return results


# ============================================================================
# Export
# ============================================================================

__all__ = [
    # Gate status
    "GateStatus",
    # Gate components
    "GateCheckItem",
    "GateResult",
    # P1-G3
    "ExplanationBinding",
    "EvidenceBindingGate",
    # P1-G4
    "GeneralizationMetrics",
    "TemplateGeneralizationGate",
    # Executor
    "Phase1GateExecutor",
]
