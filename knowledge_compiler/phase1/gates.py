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
    ResultManifest,
    ResultAsset,
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
# P1-G1: ActionPlan Executability Gate
# ============================================================================

from knowledge_compiler.phase1.nl_postprocess import ActionPlan, Action


class ActionPlanExecutabilityGate:
    """
    P1-G1: 动作可执行性 Gate

    验证 ActionPlan 是否可以执行：
    1. 所需资源是否都存在
    2. 动作参数是否完整
    3. 是否有冲突或错误配置

    这是 NL 指令转换为动作后的第一道检查，确保系统不会尝试
    执行无法完成的后处理操作。
    """

    GATE_ID = "G1-P1"
    GATE_NAME = "ActionPlan Executability Gate"

    def __init__(self):
        # 资源类型到逻辑名称的映射
        self._asset_type_requirements = {
            "field_data": ["field"],
            "plot_data": ["contour_plot", "line_plot", "vector_plot"],
            "line_data": ["line_plot", "field"],
            "vector_data": ["vector_plot", "field"],
            "metric_data": ["metric"],
        }

    def check_action_plan(
        self,
        action_plan: ActionPlan,
        manifest: ResultManifest,
    ) -> GateResult:
        """
        检查 ActionPlan 是否可执行

        Args:
            action_plan: 从 NL 指令解析得到的 ActionPlan
            manifest: 结果目录的 ResultManifest

        Returns:
            Gate 检查结果
        """
        checklist = []
        errors = []
        warnings = []
        score = 100.0

        # Check 1: 使用 ActionPlan.is_executable() 做基础检查
        if not action_plan.is_executable():
            errors.append(
                f"ActionPlan has missing assets: {action_plan.missing_assets}"
            )
            score -= 40.0

            checklist.append(GateCheckItem(
                item="missing_assets",
                description="All required assets are available",
                result=GateStatus.FAIL,
                message=f"Missing: {action_plan.missing_assets}",
            ))
        else:
            checklist.append(GateCheckItem(
                item="missing_assets",
                description="All required assets are available",
                result=GateStatus.PASS,
                message="No missing assets",
            ))

        # Check 2: 验证每个 action 的参数完整性
        param_issues = self._validate_action_parameters(action_plan)
        if param_issues:
            warnings.extend(param_issues)
            score -= 10.0 * len(param_issues)

            checklist.append(GateCheckItem(
                item="parameter_completeness",
                description="Action parameters are complete",
                result=GateStatus.WARN,
                message=f"Parameter issues: {param_issues}",
            ))
        else:
            checklist.append(GateCheckItem(
                item="parameter_completeness",
                description="Action parameters are complete",
                result=GateStatus.PASS,
                message="All action parameters complete",
            ))

        # Check 3: 验证资源映射（逻辑名称 -> 实际 asset）
        mapping_issues = self._validate_asset_mapping(action_plan, manifest)
        if mapping_issues:
            errors.extend(mapping_issues)
            score -= 20.0 * len(mapping_issues)

            checklist.append(GateCheckItem(
                item="asset_mapping",
                description="Asset references map to actual files",
                result=GateStatus.FAIL,
                message=f"Mapping issues: {mapping_issues}",
            ))
        else:
            checklist.append(GateCheckItem(
                item="asset_mapping",
                description="Asset references map to actual files",
                result=GateStatus.PASS,
                message="All assets properly mapped",
            ))

        # Check 4: 检测动作冲突
        conflicts = self._detect_action_conflicts(action_plan)
        if conflicts:
            warnings.extend(conflicts)
            score -= 10.0 * len(conflicts)

            checklist.append(GateCheckItem(
                item="action_conflicts",
                description="No conflicting actions in plan",
                result=GateStatus.WARN,
                message=f"Conflicts detected: {conflicts}",
            ))
        else:
            checklist.append(GateCheckItem(
                item="action_conflicts",
                description="No conflicting actions in plan",
                result=GateStatus.PASS,
                message="No action conflicts",
            ))

        # Check 5: 检查置信度
        if action_plan.confidence < 0.5:
            warnings.append(
                f"Low confidence score: {action_plan.confidence:.2f} < 0.5"
            )
            score -= 15.0

            checklist.append(GateCheckItem(
                item="confidence_score",
                description="ActionPlan has sufficient confidence",
                result=GateStatus.WARN,
                message=f"Low confidence: {action_plan.confidence:.2f}",
            ))
        else:
            checklist.append(GateCheckItem(
                item="confidence_score",
                description="ActionPlan has sufficient confidence",
                result=GateStatus.PASS,
                message=f"Confidence: {action_plan.confidence:.2f}",
            ))

        # 确定最终状态
        status = GateStatus.PASS
        if score < 50.0 or errors:
            status = GateStatus.FAIL
        elif score < 70.0 or warnings:
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
                "intent": action_plan.detected_intent,
                "num_actions": len(action_plan.actions),
                "raw_instruction": action_plan.raw_instruction,
            },
            severity="BLOCK",  # P1-G1 是 BLOCK 级别
        )

    def _validate_action_parameters(self, action_plan: ActionPlan) -> List[str]:
        """验证每个 action 的参数完整性"""
        issues = []

        for i, action in enumerate(action_plan.actions):
            # 每个 action_type 有必需的参数
            required_params = {
                "generate_plot": ["field", "plot_type"],
                "extract_section": ["plane", "field"],
                "calculate_metric": ["metric_type"],
                "compare_data": ["items", "field"],
                "reorder_content": ["sequence"],
            }

            action_type = action.action_type.value
            required = required_params.get(action_type, [])

            missing = [p for p in required if p not in action.parameters]
            if missing:
                issues.append(
                    f"Action {i}: Missing required parameters: {missing}"
                )

        return issues

    def _validate_asset_mapping(
        self,
        action_plan: ActionPlan,
        manifest: ResultManifest,
    ) -> List[str]:
        """验证资源引用是否映射到实际文件"""
        issues = []

        # 获取所有实际可用的 asset_type
        available_types = {asset.asset_type for asset in manifest.assets}

        # 检查每个 action 的 requires_assets
        for i, action in enumerate(action_plan.actions):
            for required in action.requires_assets:
                # 检查是否有对应的实际 asset
                # 例如：requires="field_data" 对应 asset_type="field"
                mapped = False
                if required == "field_data" and "field" in available_types:
                    mapped = True
                elif required in available_types:
                    mapped = True

                if not mapped:
                    issues.append(
                        f"Action {i}: Required asset '{required}' not found in manifest"
                    )

        return issues

    def _detect_action_conflicts(self, action_plan: ActionPlan) -> List[str]:
        """检测动作冲突"""
        conflicts = []

        # 检测重复的动作（例如：多次生成同一个 plot）
        seen_actions = {}  # (action_type, key_params) -> count

        for i, action in enumerate(action_plan.actions):
            action_type = action.action_type.value

            # 为每个 action 生成一个 key
            if action_type == "generate_plot":
                key = (
                    action_type,
                    action.parameters.get("field"),
                    action.parameters.get("plot_type"),
                    action.parameters.get("plane"),
                )
            elif action_type == "extract_section":
                key = (
                    action_type,
                    action.parameters.get("plane"),
                    action.parameters.get("field"),
                )
            else:
                key = (action_type, str(sorted(action.parameters.items())))

            count = seen_actions.get(key, 0) + 1
            seen_actions[key] = count

            if count > 1:
                conflicts.append(
                    f"Duplicate action {i}: {action_type} with {action.parameters}"
                )

        return conflicts


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

    GATE_ID = "G3-P1"
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

    GATE_ID = "G4-P1"
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
        # 一致性：检查TeachRecord是否指向相同类型的操作
        operation_types = set()
        for record in teach_records:
            for op in record.operations:
                operation_types.add(op.operation_type)

        # 基于 TeachRecord 操作类型多样性和数值范围覆盖度
        if teach_records:
            # 操作多样性：不同操作类型的占比
            operation_diversity = min(1.0, len(operation_types) / 5.0)
            # 案例覆盖：不同 source_case_id 的数量
            case_ids = {r.case_id for r in teach_records if r.case_id}
            case_diversity = min(1.0, len(case_ids) / 3.0)
            diversity_score = 0.6 * operation_diversity + 0.4 * case_diversity
        else:
            diversity_score = 0.0

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
# P1-2: CorrectionSpec Completeness Gate
# ============================================================================

from knowledge_compiler.phase1.schema import ErrorType, ImpactScope


class CorrectionSpecCompletenessGate:
    """
    P1-2: CorrectionSpec 完整性 Gate

    验证 CorrectionSpec 的 9 个必填字段，确保学习主通道的数据质量。

    根据 Opus 4.6 审查建议（P1-2）：
    - 检查 9 个必填字段是否完整
    - BLOCK 级别：任一必填字段缺失或无效即 FAIL
    - 支持单个检查和批量检查
    """
    GATE_ID = "G2-P1"
    GATE_NAME = "CorrectionSpec Completeness Gate"

    # 9 个必填字段定义
    REQUIRED_FIELDS = [
        "correction_id",
        "error_type",
        "wrong_output",
        "correct_output",
        "human_reason",
        "impact_scope",
        "source_case_id",
        "timestamp",
        "replay_status",
    ]

    # 有效的 replay_status 值
    VALID_REPLAY_STATUSES = {"pending", "in_progress", "passed", "failed", "skipped"}

    # 有效的 error_type 值（同时支持 enum name 和 value）
    VALID_ERROR_TYPES = {et.value for et in ErrorType} | {et.name for et in ErrorType}

    # 有效的 impact_scope 值（同时支持 enum name 和 value）
    VALID_IMPACT_SCOPES = {scope.value for scope in ImpactScope} | {scope.name for scope in ImpactScope}

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the gate

        Args:
            strict_mode: 如果为 True，所有字段必须完整；False 则允许警告模式
        """
        self.strict_mode = strict_mode

    def check(self, correction_spec) -> GateResult:
        """
        检查单个 CorrectionSpec

        Args:
            correction_spec: CorrectionSpec 实例或字典

        Returns:
            GateResult 检查结果
        """
        checklist = []
        errors = []
        warnings = []
        score = 100.0

        # 提取数据为字典格式
        if isinstance(correction_spec, dict):
            data = correction_spec
            spec_id = data.get("correction_id", "unknown")
        else:
            data = self._spec_to_dict(correction_spec)
            spec_id = getattr(correction_spec, "correction_id", "unknown")

        # 检查 9 个必填字段
        for field in self.REQUIRED_FIELDS:
            result, message = self._check_field(data, field)
            checklist.append(GateCheckItem(
                item=field,
                description=f"Required field: {field}",
                result=result,
                message=message,
            ))

            if result == GateStatus.FAIL:
                errors.append(message)
                score -= 10.0
            elif result == GateStatus.WARN:
                warnings.append(message)
                score -= 5.0

        # 验证字段值的合法性
        validation_result, validation_errors, validation_warnings = self._validate_values(data)
        checklist.extend(validation_result)

        for error in validation_errors:
            errors.append(error)
            score -= 10.0

        for warning in validation_warnings:
            warnings.append(warning)
            score -= 5.0

        # 确定最终状态
        status = GateStatus.PASS
        if score < 50.0 or (self.strict_mode and errors):
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
                "correction_id": spec_id,
                "strict_mode": self.strict_mode,
                "fields_checked": len(self.REQUIRED_FIELDS),
            },
            severity="BLOCK",  # BLOCK 级别：阻止低质量学习数据进入系统
        )

    def check_batch(self, correction_specs: List) -> GateResult:
        """
        批量检查多个 CorrectionSpec

        Args:
            correction_specs: CorrectionSpec 列表

        Returns:
            汇总的 GateResult
        """
        # 空列表视为通过（100% pass rate）
        if not correction_specs:
            return GateResult(
                gate_id=self.GATE_ID,
                gate_name=f"{self.GATE_NAME} (Batch)",
                status=GateStatus.PASS,
                timestamp=time.time(),
                score=100.0,
                checklist=[],
                errors=[],
                warnings=[],
                metadata={
                    "total_checked": 0,
                    "pass_count": 0,
                    "fail_count": 0,
                    "pass_rate": 100.0,
                },
                severity="BLOCK",
            )

        all_checklist = []
        all_errors = []
        all_warnings = []
        total_score = 0.0

        pass_count = 0
        fail_count = 0

        for spec in correction_specs:
            result = self.check(spec)
            all_checklist.extend(result.checklist)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            total_score += result.score

            if result.is_pass():
                pass_count += 1
            else:
                fail_count += 1

        # 计算平均分数
        avg_score = total_score / len(correction_specs)

        # 确定整体状态
        status = GateStatus.PASS
        if fail_count > 0:
            status = GateStatus.FAIL
        elif avg_score < 70.0:
            status = GateStatus.WARN

        return GateResult(
            gate_id=self.GATE_ID,
            gate_name=f"{self.GATE_NAME} (Batch)",
            status=status,
            timestamp=time.time(),
            score=avg_score,
            checklist=all_checklist,
            errors=all_errors,
            warnings=all_warnings,
            metadata={
                "total_checked": len(correction_specs),
                "pass_count": pass_count,
                "fail_count": fail_count,
                "pass_rate": (pass_count / len(correction_specs) * 100),
            },
            severity="BLOCK",
        )

    def _check_field(self, data: Dict, field: str) -> Tuple[GateStatus, str]:
        """检查单个字段"""
        value = data.get(field)

        # 检查字段是否存在
        if value is None:
            if field == "source_case_id":
                # source_case_id 可能在 metadata 中
                if data.get("metadata", {}).get("source_case_id"):
                    return GateStatus.PASS, "Found in metadata"
                # 或在动态属性中（如 correction_spec.source_case_id）
                if hasattr(data, "__dict__") and "source_case_id" in data.__dict__:
                    return GateStatus.PASS, "Found as attribute"
            return GateStatus.FAIL, f"Missing required field: {field}"

        # 检查字段值是否有效
        if field == "correction_id":
            if not value or not isinstance(value, str):
                return GateStatus.FAIL, f"Invalid correction_id: {value}"

        elif field == "error_type":
            if isinstance(value, ErrorType):
                value = value.value
            if value not in self.VALID_ERROR_TYPES:
                return GateStatus.FAIL, f"Invalid error_type: {value}"

        elif field == "wrong_output":
            if not isinstance(value, dict) or not value:
                return GateStatus.FAIL, "wrong_output must be a non-empty dict"

        elif field == "correct_output":
            if not isinstance(value, dict) or not value:
                return GateStatus.FAIL, "correct_output must be a non-empty dict"

        elif field == "human_reason":
            if not value or not isinstance(value, str):
                return GateStatus.WARN, "human_reason should be a non-empty string"

        elif field == "impact_scope":
            if isinstance(value, ImpactScope):
                value = value.value
            if value not in self.VALID_IMPACT_SCOPES:
                return GateStatus.WARN, f"Unusual impact_scope: {value}"

        elif field == "timestamp":
            if not isinstance(value, (int, float)):
                return GateStatus.WARN, f"timestamp should be numeric: {type(value).__name__}"

        elif field == "replay_status":
            if value not in self.VALID_REPLAY_STATUSES:
                return GateStatus.WARN, f"Invalid replay_status: {value}"

        return GateStatus.PASS, f"Field {field} is valid"

    def _validate_values(self, data: Dict) -> Tuple[List[GateCheckItem], List[str], List[str]]:
        """验证字段值的合法性"""
        checklist = []
        errors = []
        warnings = []

        # 检查 wrong_output 和 correct_output 是否真的不同
        wrong = data.get("wrong_output", {})
        correct = data.get("correct_output", {})

        if isinstance(wrong, dict) and isinstance(correct, dict):
            if wrong == correct:
                msg = "wrong_output and correct_output are identical"
                checklist.append(GateCheckItem(
                    item="output_difference",
                    description="wrong_output differs from correct_output",
                    result=GateStatus.WARN,
                    message=msg,
                ))
                warnings.append(msg)
            elif wrong.keys() == correct.keys():
                # 检查值是否真的不同
                same_values = sum(1 for k in wrong if wrong.get(k) == correct.get(k))
                if same_values == len(wrong):
                    msg = "wrong_output and correct_output have identical values"
                    errors.append(msg)

        return checklist, errors, warnings

    def _spec_to_dict(self, spec) -> Dict:
        """将 CorrectionSpec 转换为字典"""
        if hasattr(spec, "to_dict"):
            return spec.to_dict()
        elif hasattr(spec, "__dict__"):
            return spec.__dict__
        else:
            return dict(spec)


# ============================================================================
# Combined Gate Executor
# ============================================================================

class Phase1GateExecutor:
    """
    Phase 1 Gate执行器

    统一执行P1-G1/G2/G3/G4四个Gate（聚焦版：G1-P1 ~ G4-P1）
    """

    def __init__(self):
        self.g1_gate = ActionPlanExecutabilityGate()
        self.g2_gate = CorrectionSpecCompletenessGate()
        self.g3_gate = EvidenceBindingGate()
        self.g4_gate = TemplateGeneralizationGate()

    def run_g1_gate(
        self,
        action_plan: ActionPlan,
        manifest: ResultManifest,
    ) -> GateResult:
        """执行G1-P1 Gate (ActionPlan Executability)"""
        return self.g1_gate.check_action_plan(action_plan, manifest)

    def run_g2_gate(
        self,
        correction_spec,
    ) -> GateResult:
        """执行G2-P1 Gate (CorrectionSpec Completeness)"""
        return self.g2_gate.check(correction_spec)

    def run_g2_gate_batch(
        self,
        correction_specs: List,
    ) -> GateResult:
        """执行G2-P1 Gate (批量检查)"""
        return self.g2_gate.check_batch(correction_specs)

    def run_g3_gate(
        self,
        teach_records: List[TeachRecord],
        available_assets: Optional[List[str]] = None,
    ) -> GateResult:
        """执行G3-P1 Gate (Evidence Binding)"""
        if not teach_records:
            return GateResult(
                gate_id="G3-P1",
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
        """执行G4-P1 Gate (Template Generalization)"""
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
        action_plan: Optional[ActionPlan] = None,
        manifest: Optional[ResultManifest] = None,
    ) -> Dict[str, GateResult]:
        """
        执行所有Phase 1 Gates

        Args:
            report_spec: ReportSpec候选
            source_cases: 源case列表
            teach_records: TeachRecord列表
            available_assets: 可用资产列表
            action_plan: 可选的 ActionPlan（用于 P1-G1）
            manifest: 可选的 ResultManifest（用于 P1-G1）

        Returns:
            各Gate的结果字典
        """
        results = {}

        # G1-P1: ActionPlan Executability (如果提供)
        if action_plan and manifest:
            results["G1-P1"] = self.run_g1_gate(action_plan, manifest)

        # G3-P1: Evidence Binding
        results["G3-P1"] = self.run_g3_gate(teach_records, available_assets)

        # G4-P1: Template Generalization
        results["G4-P1"] = self.run_g4_gate(
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
    # P1-G1
    "ActionPlanExecutabilityGate",
    # P1-G2
    "CorrectionSpecCompletenessGate",
    # P1-G3
    "ExplanationBinding",
    "EvidenceBindingGate",
    # P1-G4
    "GeneralizationMetrics",
    "TemplateGeneralizationGate",
    # Executor
    "Phase1GateExecutor",
]
