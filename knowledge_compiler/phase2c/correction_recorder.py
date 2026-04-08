#!/usr/bin/env python3
"""
Correction Recorder - Phase 2c Governance & Learning

结构化记录和持久化 CorrectionSpec，提供 impact_scope 判定和 Specs/Constraints 验证。

集成点:
- 输入: FailureHandler.CorrectionSpecGenerator
- 验证: Specs/Constraints 表
- 输出: 持久化的 CorrectionSpec 记录
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_compiler.phase1.schema import (
    CorrectionSpec,
    ErrorType,
    ImpactScope,
)
from knowledge_compiler.phase2.execution_layer.result_validator import (
    Anomaly,
    AnomalyType,
    ValidationResult,
)
from knowledge_compiler.phase2.execution_layer.failure_handler import (
    FailureContext,
    FailureHandlingResult,
)


class CorrectionSeverity(Enum):
    """修正严重程度"""
    CRITICAL = "critical"  # 系统无法继续运行
    HIGH = "high"  # 功能受损但可降级
    MEDIUM = "medium"  # 轻微影响
    LOW = "low"  # 建议性改进


class ReplayStatus(Enum):
    """回放状态"""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CorrectionRecord:
    """
    完整的修正记录（9 字段扩展版）

    扩展 CorrectionSpecGenerator 的输出，添加完整的学习闭环所需字段。
    """
    # 基础 ID
    record_id: str
    created_at: float

    # 9 个必填字段
    error_type: ErrorType
    wrong_output: Dict[str, Any]
    correct_output: Dict[str, Any]
    human_reason: str
    evidence: List[str]
    impact_scope: ImpactScope
    root_cause: str
    fix_action: str
    needs_replay: bool

    # 元数据
    severity: CorrectionSeverity = CorrectionSeverity.MEDIUM
    replay_status: ReplayStatus = ReplayStatus.PENDING
    linked_spec_ids: List[str] = field(default_factory=list)  # 关联的 Specs
    linked_constraint_ids: List[str] = field(default_factory=list)  # 关联的 Constraints

    # 源信息
    source_case_id: Optional[str] = None
    source_validation_id: Optional[str] = None
    source_anomaly: Optional[Dict[str, Any]] = None

    # 审批状态
    approved: bool = False
    approved_by: Optional[str] = None  # Engineer ID
    approved_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "record_id": self.record_id,
            "created_at": self.created_at,
            "error_type": self.error_type.value,
            "wrong_output": self.wrong_output,
            "correct_output": self.correct_output,
            "human_reason": self.human_reason,
            "evidence": self.evidence,
            "impact_scope": self.impact_scope.value,
            "root_cause": self.root_cause,
            "fix_action": self.fix_action,
            "needs_replay": self.needs_replay,
            "severity": self.severity.value,
            "replay_status": self.replay_status.value,
            "linked_spec_ids": self.linked_spec_ids,
            "linked_constraint_ids": self.linked_constraint_ids,
            "source_case_id": self.source_case_id,
            "source_validation_id": self.source_validation_id,
            "approved": self.approved,
        }


class ImpactScopeAnalyzer:
    """
    Impact Scope 分析器

    根据失败类型、位置、上下文自动判定修正的影响范围。
    """

    # 异常类型到影响范围的映射规则
    ANOMALY_SCOPE_MAP = {
        AnomalyType.RESIDUAL_SPIKE: ImpactScope.SINGLE_CASE,
        AnomalyType.DIVERGENCE: ImpactScope.SIMILAR_CASES,
        AnomalyType.NaN_DETECTED: ImpactScope.ALL_CASES,
        AnomalyType.INF_DETECTED: ImpactScope.ALL_CASES,
        AnomalyType.NEGATIVE_PRESSURE: ImpactScope.SIMILAR_CASES,
        AnomalyType.HIGH_ASPECT_RATIO: ImpactScope.SINGLE_CASE,
        AnomalyType.BLOW_UP_STAGNATION: ImpactScope.ALL_CASES,
    }

    # 位置关键词影响范围判定
    LOCATION_KEYWORDS = {
        "gate": ImpactScope.GATE_DEFINITION,
        "report": ImpactScope.REPORT_SPEC,
        "template": ImpactScope.REPORT_SPEC,
        "sampler": ImpactScope.SIMILAR_CASES,
        "postprocessor": ImpactScope.SIMILAR_CASES,
    }

    def analyze(
        self,
        anomaly: Anomaly,
        context: FailureContext
    ) -> ImpactScope:
        """分析异常的影响范围"""
        # 首先检查位置关键词
        location_lower = anomaly.location.lower() if anomaly.location else ""
        for keyword, scope in self.LOCATION_KEYWORDS.items():
            if keyword in location_lower:
                return scope

        # 然后根据异常类型映射
        return self.ANOMALY_SCOPE_MAP.get(
            anomaly.anomaly_type,
            ImpactScope.SINGLE_CASE  # 默认单案例
        )

    def analyze_from_context(
        self,
        spec_generator_output: Dict[str, Any],
        context: FailureContext
    ) -> ImpactScope:
        """从 CorrectionSpecGenerator 输出分析影响范围"""
        # 检查 validation_result 中的异常
        if context.validation_result.anomalies:
            return self.analyze(context.validation_result.anomalies[0], context)

        return ImpactScope.SINGLE_CASE


class SpecsValidator:
    """
    Specs 验证器

    验证修正是否符合项目规范要求。
    """

    def __init__(self, specs: List[Dict[str, Any]]):
        """
        Args:
            specs: Specs 列表（从 Notion Specs 表加载）
        """
        self.specs = specs
        self._build_index()

    def _build_index(self):
        """构建规范索引"""
        self._by_type = {}
        self._by_scope = {}

        for spec in self.specs:
            scope_type = spec.get("scope_type", "")
            spec_type = spec.get("title", "")

            if scope_type not in self._by_scope:
                self._by_scope[scope_type] = []
            self._by_scope[scope_type].append(spec)

            if spec_type not in self._by_type:
                self._by_type[spec_type] = []
            self._by_type[spec_type].append(spec)

    def validate(
        self,
        record: CorrectionRecord
    ) -> List[str]:
        """
        验证修正记录是否符合规范

        Returns:
            违规信息列表，空列表表示合规
        """
        violations = []

        # 1. 验证枚举使用（约束：无字符串类型）
        if isinstance(record.error_type, str):
            violations.append("error_type 必须使用 ErrorType 枚举")

        if isinstance(record.impact_scope, str):
            violations.append("impact_scope 必须使用 ImpactScope 枚举")

        # 2. 验证 Phase 1 接口稳定性（约束：Phase 1 接口不能破坏）
        if "Gate" in record.root_cause or "gate" in record.fix_action.lower():
            # Gate 修改需要特殊审查
            gate_specs = self._by_scope.get("Architecture", [])
            if gate_specs:
                violations.append("Gate 修改需要 Opus 4.6 审查")

        # 3. 验证数据伪造约束（约束：无数据伪造）
        if "fabricat" in record.fix_action.lower() or "fake" in record.fix_action.lower():
            violations.append("CRITICAL: 禁止数据伪造")

        # 4. 验证模型路由约束（约束：核心逻辑用 Codex）
        if "model" in record.fix_action.lower() or "routing" in record.fix_action.lower():
            model_specs = [s for s in self.specs if "MODEL-ROUTING" in s.get("title", "")]
            if model_specs:
                violations.append("模型路由修改需要更新 MODEL_ROUTING-001")

        return violations


class ConstraintsChecker:
    """
    Constraints 检查器

    检查修正是否违反项目约束。
    """

    def __init__(self, constraints: List[Dict[str, Any]]):
        """
        Args:
            constraints: Constraints 列表（从 Notion Constraints 表加载）
        """
        self.constraints = constraints
        self._build_index()

    def _build_index(self):
        """构建约束索引"""
        self._by_type = {}
        self._by_severity = {}

        for constraint in self.constraints:
            ctype = constraint.get("constraint_type", "")
            severity = constraint.get("severity", "")

            if ctype not in self._by_type:
                self._by_type[ctype] = []
            self._by_type[ctype].append(constraint)

            if severity not in self._by_severity:
                self._by_severity[severity] = []
            self._by_severity[severity].append(constraint)

    def check(
        self,
        record: CorrectionRecord
    ) -> List[str]:
        """
        检查约束违规

        Returns:
            违规信息列表
        """
        violations = []

        # 1. 检查接口约束
        interface_constraints = self._by_type.get("Interface", [])
        for constraint in interface_constraints:
            if not constraint.get("enabled", True):
                continue

            validation = constraint.get("validation_rule", "")
            if "enum" in validation.lower() and isinstance(record.error_type, str):
                violations.append(f"接口约束: {constraint['constraint_name']}")

        # 2. 检查安全约束
        security_constraints = self._by_type.get("Security", [])
        for constraint in security_constraints:
            if not constraint.get("enabled", True):
                continue

            validation = constraint.get("validation_rule", "")
            if "fabricat" in validation.lower() and "fabricat" in record.fix_action.lower():
                violations.append(f"安全约束: {constraint['constraint_name']}")

        # 3. 检查架构约束
        architecture_constraints = self._by_type.get("Architecture", [])
        for constraint in architecture_constraints:
            if not constraint.get("enabled", True):
                continue

            validation = constraint.get("validation_rule", "")
            if "dataclass" in validation.lower() and "dataclass" not in record.fix_action.lower():
                # 如果修正涉及数据结构，必须使用 dataclass
                if "structure" in record.fix_action.lower() or "class" in record.fix_action.lower():
                    violations.append(f"架构约束: {constraint['constraint_name']}")

        return violations


class CorrectionRecorder:
    """
    修正记录器 - Phase 2c 核心组件

    消费 FailureHandler.CorrectionSpecGenerator 输出，生成结构化 CorrectionRecord，
    提供 impact_scope 自动判定、Specs/Constraints 验证和持久化存储。

    用法:
        recorder = CorrectionRecorder(specs, constraints)

        # 从 FailureHandler 获取原始 spec
        spec_dict = failure_handler.generate_correction_spec(context, handling_result)

        # 转换为完整记录
        record = recorder.record_from_generator(spec_dict, context, handling_result)

        # 验证
        violations = recorder.validate(record)
        if violations:
            print(f"Validation failed: {violations}")
            return None

        # 持久化
        recorder.save(record)
    """

    def __init__(
        self,
        specs: Optional[List[Dict[str, Any]]] = None,
        constraints: Optional[List[Dict[str, Any]]] = None,
        storage_path: Optional[str] = None,
    ):
        """
        Args:
            specs: Specs 列表（从 Notion 加载）
            constraints: Constraints 列表（从 Notion 加载）
            storage_path: 持久化存储路径
        """
        self.specs = specs or []
        self.constraints = constraints or []
        self.storage_path = storage_path or "data/corrections"

        # 初始化子组件
        self.scope_analyzer = ImpactScopeAnalyzer()
        self.specs_validator = SpecsValidator(self.specs) if self.specs else None
        self.constraints_checker = ConstraintsChecker(self.constraints) if self.constraints else None

        # 记录计数
        self._record_count = 0

        # 确保存储目录存在
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)

    def record_from_generator(
        self,
        spec_generator_output: Dict[str, Any],
        context: FailureContext,
        handling_result: Optional[FailureHandlingResult] = None,
        human_reason: Optional[str] = None,
        engineer_id: Optional[str] = None,
    ) -> CorrectionRecord:
        """
        从 CorrectionSpecGenerator 输出生成完整记录

        Args:
            spec_generator_output: CorrectionSpecGenerator.generate() 的输出
            context: FailureContext
            handling_result: FailureHandlingResult
            human_reason: 人工原因说明（如果有的话）
            engineer_id: 工程师 ID

        Returns:
            CorrectionRecord 完整记录
        """
        self._record_count += 1
        now = time.time()

        # 1. 提取异常信息
        anomaly = None
        if context.validation_result.anomalies:
            anomaly = context.validation_result.anomalies[0]

        # 2. 映射 AnomalyType 到 ErrorType
        error_type = self._map_anomaly_to_error_type(anomaly)

        # 3. 构建 wrong_output 和 correct_output
        wrong_output = {
            "anomaly": {
                "type": anomaly.anomaly_type.value if anomaly else None,
                "message": anomaly.message if anomaly else None,
                "location": anomaly.location if anomaly else None,
                "severity": anomaly.severity if anomaly else None,
            } if anomaly else None,
            "solver_result": handling_result.message if handling_result else None,
            "action_taken": handling_result.action.value if handling_result else None,
        }

        correct_output = {
            "suggested_actions": spec_generator_output.get("suggested_actions", []),
            "retry_strategy": spec_generator_output.get("retry_with", {}),
        }

        # 4. 分析 impact_scope
        impact_scope = self.scope_analyzer.analyze_from_context(
            spec_generator_output, context
        )

        # 5. 推断 root_cause
        root_cause = self._infer_root_cause(anomaly, context)

        # 6. 生成 fix_action
        fix_action = self._generate_fix_action(anomaly, handling_result)

        # 7. 收集 evidence
        evidence = self._collect_evidence(spec_generator_output, context)

        # 8. 判断是否需要回放
        needs_replay = self._determine_replay_need(impact_scope, error_type)

        # 9. 构建记录
        record = CorrectionRecord(
            record_id=f"CREC-{self._record_count}-{int(now)}",
            created_at=now,
            error_type=error_type,
            wrong_output=wrong_output,
            correct_output=correct_output,
            human_reason=human_reason or self._generate_default_reason(anomaly),
            evidence=evidence,
            impact_scope=impact_scope,
            root_cause=root_cause,
            fix_action=fix_action,
            needs_replay=needs_replay,
            source_case_id=context.metadata.get("case_id"),
            source_validation_id=context.validation_result.validation_id,
            source_anomaly=spec_generator_output.get("validation_result", {}),
        )

        return record

    def _map_anomaly_to_error_type(
        self,
        anomaly: Optional[Anomaly]
    ) -> ErrorType:
        """映射 AnomalyType 到 ErrorType"""
        if anomaly is None:
            return ErrorType.MISSING_DATA

        mapping = {
            AnomalyType.NaN_DETECTED: ErrorType.INCORRECT_DATA,
            AnomalyType.INF_DETECTED: ErrorType.INCORRECT_DATA,
            AnomalyType.NEGATIVE_PRESSURE: ErrorType.INCORRECT_DATA,
            AnomalyType.HIGH_ASPECT_RATIO: ErrorType.MISSING_COMPONENT,
            AnomalyType.RESIDUAL_SPIKE: ErrorType.INCORRECT_INFERENCE,
            AnomalyType.DIVERGENCE: ErrorType.INCORRECT_INFERENCE,
            AnomalyType.BLOW_UP_STAGNATION: ErrorType.MISSING_EXPLANATION,
        }

        return mapping.get(
            anomaly.anomaly_type,
            ErrorType.MISINTERPRETATION
        )

    def _infer_root_cause(
        self,
        anomaly: Optional[Anomaly],
        context: FailureContext
    ) -> str:
        """推断根因"""
        if anomaly is None:
            return "未知异常"

        if anomaly.anomaly_type == AnomalyType.HIGH_ASPECT_RATIO:
            return "网格质量问题：宽长比过高导致数值不稳定"

        elif anomaly.anomaly_type == AnomalyType.NaN_DETECTED:
            return "数值爆炸：可能是边界条件或时间步长设置不当"

        elif anomaly.anomaly_type == AnomalyType.DIVERGENCE:
            return f"求解发散：尝试 {context.attempt_count} 次后仍未收敛"

        elif anomaly.anomaly_type == AnomalyType.RESIDUAL_SPIKE:
            return "残差突增：可能是边界条件变化或物理解释错误"

        elif anomaly.anomaly_type == AnomalyType.BLOW_UP_STAGNATION:
            return "停滞现象：求解器进入数值停滞状态"

        return f"异常类型: {anomaly.anomaly_type.value}"

    def _generate_fix_action(
        self,
        anomaly: Optional[Anomaly],
        handling_result: Optional[FailureHandlingResult]
    ) -> str:
        """生成修正动作"""
        if handling_result and handling_result.retry_with:
            strategy = handling_result.retry_with.get("strategy", "")
            reason = handling_result.retry_with.get("reason", "")
            return f"建议重试策略: {strategy}. {reason}"

        if anomaly:
            return f"建议修正措施: {anomaly.message}"

        return "需要人工审查和修正"

    def _collect_evidence(
        self,
        spec_output: Dict[str, Any],
        context: FailureContext
    ) -> List[str]:
        """收集证据"""
        evidence = []

        # 添加验证 ID
        if context.validation_result.validation_id:
            evidence.append(f"validation_id: {context.validation_result.validation_id}")

        # 添加时间戳 (使用当前时间)
        evidence.append(f"timestamp: {datetime.now().isoformat()}")

        # 添加尝试次数
        evidence.append(f"attempt_count: {context.attempt_count}")

        # 添加异常详情
        if context.validation_result.anomalies:
            for a in context.validation_result.anomalies:
                evidence.append(f"anomaly: {a.anomaly_type.value} at {a.location}")

        return evidence

    def _determine_replay_need(
        self,
        impact_scope: ImpactScope,
        error_type: ErrorType
    ) -> bool:
        """判定是否需要回放"""
        # 全局修改必须回放
        if impact_scope in [
            ImpactScope.ALL_CASES,
            ImpactScope.REPORT_SPEC,
            ImpactScope.GATE_DEFINITION
        ]:
            return True

        # 关键错误类型需要回放
        if error_type in [
            ErrorType.MISSING_COMPONENT,
            ErrorType.DUPLICATE_CONTENT,
        ]:
            return True

        # 其他情况根据策略判定
        return False

    def _generate_default_reason(
        self,
        anomaly: Optional[Anomaly]
    ) -> str:
        """生成默认原因说明"""
        if anomaly:
            return f"检测到 {anomaly.anomaly_type.value} 类型的异常，位置: {anomaly.location}"
        return "验证失败，需要修正"

    def validate(self, record: CorrectionRecord) -> List[str]:
        """验证记录是否符合 Specs 和 Constraints"""
        all_violations = []

        if self.specs_validator:
            violations = self.specs_validator.validate(record)
            all_violations.extend(violations)

        if self.constraints_checker:
            violations = self.constraints_checker.check(record)
            all_violations.extend(violations)

        return all_violations

    def save(self, record: CorrectionRecord) -> str:
        """
        持久化保存记录

        Returns:
            保存的文件路径
        """
        timestamp = datetime.fromtimestamp(record.created_at).strftime("%Y%m%d")
        # 文件名包含 case_id（如果有）以便识别
        if record.source_case_id:
            filename = f"{record.source_case_id}_{record.record_id}.json"
        else:
            filename = f"{record.record_id}.json"
        filepath = Path(self.storage_path) / timestamp / filename

        # 创建日期目录
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 保存为 JSON
        with open(filepath, "w") as f:
            json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)

        return str(filepath)

    def load(self, record_id: str) -> Optional[CorrectionRecord]:
        """加载记录"""
        # 搜索文件
        for json_file in Path(self.storage_path).rglob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    if data.get("record_id") == record_id:
                        # 重建 CorrectionRecord
                        return CorrectionRecord(
                            record_id=data["record_id"],
                            created_at=data["created_at"],
                            error_type=ErrorType(data["error_type"]),
                            wrong_output=data["wrong_output"],
                            correct_output=data["correct_output"],
                            human_reason=data["human_reason"],
                            evidence=data["evidence"],
                            impact_scope=ImpactScope(data["impact_scope"]),
                            root_cause=data["root_cause"],
                            fix_action=data["fix_action"],
                            needs_replay=data["needs_replay"],
                            severity=CorrectionSeverity(data.get("severity", "medium")),
                            replay_status=ReplayStatus(data.get("replay_status", "pending")),
                            linked_spec_ids=data.get("linked_spec_ids", []),
                            linked_constraint_ids=data.get("linked_constraint_ids", []),
                            source_case_id=data.get("source_case_id"),
                            source_validation_id=data.get("source_validation_id"),
                            approved=data.get("approved", False),
                        )
            except (json.JSONDecodeError, KeyError):
                continue

        return None

    def list_records(
        self,
        limit: int = 100
    ) -> List[CorrectionRecord]:
        """列出所有记录"""
        records = []

        for json_file in list(Path(self.storage_path).rglob("*.json"))[:limit]:
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    records.append(CorrectionRecord(
                        record_id=data["record_id"],
                        created_at=data["created_at"],
                        error_type=ErrorType(data["error_type"]),
                        wrong_output=data["wrong_output"],
                        correct_output=data["correct_output"],
                        human_reason=data["human_reason"],
                        evidence=data["evidence"],
                        impact_scope=ImpactScope(data["impact_scope"]),
                        root_cause=data["root_cause"],
                        fix_action=data["fix_action"],
                        needs_replay=data["needs_replay"],
                        severity=CorrectionSeverity(data.get("severity", "medium")),
                        replay_status=ReplayStatus(data.get("replay_status", "pending")),
                        linked_spec_ids=data.get("linked_spec_ids", []),
                        linked_constraint_ids=data.get("linked_constraint_ids", []),
                        source_case_id=data.get("source_case_id"),
                        source_validation_id=data.get("source_validation_id"),
                        approved=data.get("approved", False),
                    ))
            except (json.JSONDecodeError, KeyError):
                continue

        # 按创建时间排序
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records


# ============================================================================
# 便捷函数
# ============================================================================

def record_from_failure(
    spec_generator_output: Dict[str, Any],
    context: FailureContext,
    handling_result: Optional[FailureHandlingResult] = None,
    specs: Optional[List[Dict[str, Any]]] = None,
    constraints: Optional[List[Dict[str, Any]]] = None,
) -> Optional[CorrectionRecord]:
    """便捷函数：从失败记录修正"""
    recorder = CorrectionRecorder(specs, constraints)
    record = recorder.record_from_generator(
        spec_generator_output, context, handling_result
    )

    # 验证
    violations = recorder.validate(record)
    if violations:
        print(f"⚠️  Validation violations: {violations}")

    # 保存
    filepath = recorder.save(record)
    print(f"✅ Saved correction record to: {filepath}")

    return record
