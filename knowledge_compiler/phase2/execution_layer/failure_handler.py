#!/usr/bin/env python3
"""
Failure Handler - 失败路径处理器

定义 Result Validator 失败后的处理路径：
1. 自动重试（换网格密度 / 换求解策略）
2. 上报 Gate Engine（G4-P2 阻断）
3. 生成 CorrectionSpec 候选（学习闭环）

架构设计：
    Result Validator → FAIL
                    ↓
            FailureHandler (路由)
            ↓       ↓           ↓
        RetryHandler  GateReporter  CorrectionSpecGenerator
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from knowledge_compiler.phase2.execution_layer.result_validator import (
    Anomaly,
    AnomalyType,
    ValidationResult,
    ValidationStatus,
)


class PermissionLevel(Enum):
    """权限级别 - 控制自动化行为的安全性"""
    SUGGEST_ONLY = "suggest_only"  # L0: 仅建议，不修改参数
    DRY_RUN = "dry_run"  # L1: 演练模式，返回参数但不执行
    EXECUTE = "execute"  # L2: 完全执行自动化
    EXPLORE = "explore"  # L3: 允许低成本试探，禁止正式高成本执行


class FailureAction(Enum):
    """失败处理动作"""
    RETRY = "retry"  # 自动重试
    ESCALATE = "escalate"  # 上报 Gate Engine
    GENERATE_CORRECTION = "generate_correction"  # 生成 CorrectionSpec
    TERMINATE = "terminate"  # 终止执行
    FALLBACK = "fallback"  # 降级策略


class FailureCategory(Enum):
    """失败类别"""
    RECOVERABLE = "recoverable"  # 可恢复（通过重试或参数调整）
    NON_RECOVERABLE = "non_recoverable"  # 不可恢复（需要人工干预）
    CONFIGURATION = "configuration"  # 配置问题
    RESOURCE = "resource"  # 资源问题
    NUMERICAL = "numerical"  # 数值问题


@dataclass
class FailureContext:
    """失败上下文"""
    validation_result: ValidationResult
    solver_result: Any = None
    attempt_count: int = 0
    max_attempts: int = 3
    elapsed_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_first_attempt(self) -> bool:
        return self.attempt_count == 0

    @property
    def can_retry(self) -> bool:
        return self.attempt_count < self.max_attempts


@dataclass
class FailureHandlingResult:
    """失败处理结果"""
    action: FailureAction
    category: FailureCategory
    retry_with: Optional[Dict[str, Any]] = None  # 重试时的参数调整
    message: str = ""
    correction_spec: Optional[Dict[str, Any]] = None
    gate_report: Optional[Dict[str, Any]] = None


class FailureAnalyzer:
    """失败分析器 - 决定失败类别和处理策略"""

    # 失败类型到类别的映射
    ANOMALY_CATEGORIES = {
        AnomalyType.RESIDUAL_SPIKE: FailureCategory.RECOVERABLE,
        AnomalyType.DIVERGENCE: FailureCategory.RECOVERABLE,
        AnomalyType.NaN_DETECTED: FailureCategory.NON_RECOVERABLE,
        AnomalyType.INF_DETECTED: FailureCategory.NON_RECOVERABLE,
        AnomalyType.NEGATIVE_PRESSURE: FailureCategory.NUMERICAL,
        AnomalyType.HIGH_ASPECT_RATIO: FailureCategory.CONFIGURATION,
        AnomalyType.BLOW_UP_STAGNATION: FailureCategory.NON_RECOVERABLE,
    }

    # 失败类型到处理动作的映射
    ANOMALY_ACTIONS = {
        AnomalyType.RESIDUAL_SPIKE: FailureAction.RETRY,
        AnomalyType.DIVERGENCE: FailureAction.RETRY,
        AnomalyType.NaN_DETECTED: FailureAction.ESCALATE,
        AnomalyType.INF_DETECTED: FailureAction.ESCALATE,
        AnomalyType.NEGATIVE_PRESSURE: FailureAction.GENERATE_CORRECTION,
        AnomalyType.HIGH_ASPECT_RATIO: FailureAction.GENERATE_CORRECTION,
        AnomalyType.BLOW_UP_STAGNATION: FailureAction.TERMINATE,
    }

    def analyze(self, context: FailureContext) -> FailureHandlingResult:
        """分析失败并决定处理策略"""
        result = context.validation_result

        # 获取最严重的异常
        critical_anomalies = result.get_critical_anomalies()
        if critical_anomalies:
            primary_anomaly = critical_anomalies[0]
        elif result.anomalies:
            primary_anomaly = result.anomalies[0]
        else:
            # 没有异常但状态是 FAILED - 可能是退出码问题
            return FailureHandlingResult(
                action=FailureAction.ESCALATE,
                category=FailureCategory.NON_RECOVERABLE,
                message="验证失败但无具体异常，需要人工审查"
            )

        # 根据异常类型决定处理策略
        anomaly_type = primary_anomaly.anomaly_type
        category = self.ANOMALY_CATEGORIES.get(anomaly_type, FailureCategory.NON_RECOVERABLE)
        action = self.ANOMALY_ACTIONS.get(anomaly_type, FailureAction.ESCALATE)

        # 根据严重度和重试次数调整策略
        if not context.can_retry and action == FailureAction.RETRY:
            action = FailureAction.ESCALATE

        # 生成重试参数或 CorrectionSpec
        retry_with = None
        correction_spec = None

        if action == FailureAction.RETRY:
            retry_with = self._generate_retry_params(primary_anomaly, context)
        elif action == FailureAction.GENERATE_CORRECTION:
            correction_spec = self._generate_correction_spec(primary_anomaly, context)

        return FailureHandlingResult(
            action=action,
            category=category,
            retry_with=retry_with,
            message=primary_anomaly.message,
            correction_spec=correction_spec
        )

    def _generate_retry_params(
        self, anomaly: Anomaly, context: FailureContext
    ) -> Dict[str, Any]:
        """生成重试参数"""
        params = {"attempt": context.attempt_count + 1}

        if anomaly.anomaly_type == AnomalyType.RESIDUAL_SPIKE:
            # 残差突然增大 - 降低时间步长
            params.update({
                "strategy": "reduce_time_step",
                "time_step_factor": 0.5,
                "reason": "残差突然增大，降低时间步长以稳定计算"
            })

        elif anomaly.anomaly_type == AnomalyType.DIVERGENCE:
            # 发散 - 尝试多种策略
            strategies = [
                "increase_iterations",  # 增加迭代次数
                "relax_tolerance",  # 放宽松弛因子
                "refine_mesh",  # 细化网格
            ]
            strategy_index = min(context.attempt_count, len(strategies) - 1)
            params.update({
                "strategy": strategies[strategy_index],
                "reason": f"求解发散，尝试策略: {strategies[strategy_index]}"
            })

        return params

    def _generate_correction_spec(
        self, anomaly: Anomaly, context: FailureContext
    ) -> Dict[str, Any]:
        """生成 CorrectionSpec 候选"""
        return {
            "spec_id": f"CORR-{time.time():.0f}",
            "anomaly_type": anomaly.anomaly_type.value,
            "location": anomaly.location,
            "suggested_actions": self._get_correction_actions(anomaly),
            "severity": anomaly.severity,
            "timestamp": time.time(),
            "context": {
                "attempt_count": context.attempt_count,
                "original_message": anomaly.message,
            }
        }

    def _get_correction_actions(self, anomaly: Anomaly) -> List[str]:
        """获取修正建议"""
        actions = []

        if anomaly.anomaly_type == AnomalyType.HIGH_ASPECT_RATIO:
            actions = [
                "重新生成网格，降低最大宽长比",
                "使用边界层网格加密",
                "检查几何清理是否充分"
            ]

        elif anomaly.anomaly_type == AnomalyType.NEGATIVE_PRESSURE:
            actions = [
                "检查边界条件设置",
                "调整松弛因子",
                "验证初始条件"
            ]

        return actions


class RetryStrategy(ABC):
    """重试策略抽象基类"""

    @abstractmethod
    def can_apply(self, context: FailureContext) -> bool:
        """判断是否可以应用此策略"""

    @abstractmethod
    def get_params(self, context: FailureContext) -> Dict[str, Any]:
        """获取新的运行参数"""


class ReduceTimeStepStrategy(RetryStrategy):
    """降低时间步长策略"""

    def can_apply(self, context: FailureContext) -> bool:
        # 检查是否有时间步参数
        return any(
            a.anomaly_type in [AnomalyType.RESIDUAL_SPIKE, AnomalyType.DIVERGENCE]
            for a in context.validation_result.anomalies
        )

    def get_params(self, context: FailureContext) -> Dict[str, Any]:
        factor = 0.5 ** (context.attempt_count + 1)
        return {
            "time_step": f"original * {factor}",
            "max_co_time_step_factor": factor,
            "adjustable_time_step": "yes",
        }


class IncreaseIterationsStrategy(RetryStrategy):
    """增加迭代次数策略"""

    def can_apply(self, context: FailureContext) -> bool:
        return any(
            a.anomaly_type == AnomalyType.DIVERGENCE
            for a in context.validation_result.anomalies
        )

    def get_params(self, context: FailureContext) -> Dict[str, Any]:
        base = 1000
        increase = 500 * (context.attempt_count + 1)
        return {
            "max_iter": base + increase,
            "n_correctors": 2 + context.attempt_count,
        }


class RetryHandler:
    """重试处理器

    支持权限级别控制自动化安全性：
    - suggest_only: 仅返回建议，不修改参数
    - dry_run: 返回完整参数但标记为演练
    - execute: 完全执行自动化
    """

    def __init__(self, permission_level: PermissionLevel = PermissionLevel.DRY_RUN):
        self.permission_level = permission_level
        self.strategies: List[RetryStrategy] = [
            ReduceTimeStepStrategy(),
            IncreaseIterationsStrategy(),
        ]

    def get_retry_params(
        self, handling_result: FailureHandlingResult, context: FailureContext
    ) -> Dict[str, Any]:
        """
        获取重试参数

        根据 permission_level 返回不同级别的内容：
        - suggest_only: 仅返回建议描述
        - dry_run: 返回完整参数但添加 _dry_run 标记
        - execute: 返回可执行的完整参数
        """
        # 先使用分析器生成的参数
        if handling_result.retry_with:
            strategy = handling_result.retry_with.get("strategy", "")
            reason = handling_result.retry_with.get("reason", "")

            # suggest_only 模式：仅返回建议
            if self.permission_level == PermissionLevel.SUGGEST_ONLY:
                return {
                    "suggestion": reason,
                    "strategy": strategy,
                    "note": "SUGGEST_ONLY mode: No parameters modified",
                }

            base_params = {"strategy": strategy}

            if strategy == "reduce_time_step":
                factor = handling_result.retry_with.get("time_step_factor", 0.5)
                base_params.update({
                    "delta_t": f"original * {factor ** (context.attempt_count + 1)}",
                })

            elif strategy == "increase_iterations":
                base_params.update({
                    "max_iter": 1000 + 500 * (context.attempt_count + 1),
                })

            elif strategy == "relax_tolerance":
                base_params.update({
                    "relaxation_factor": 0.7 + 0.1 * context.attempt_count,
                })

            # dry_run 模式：添加标记
            if self.permission_level == PermissionLevel.DRY_RUN:
                base_params["_dry_run"] = True
                base_params["_note"] = "DRY_RUN mode: Review before executing"

            return base_params

        # 尝试应用预定义策略
        for strategy in self.strategies:
            if strategy.can_apply(context):
                params = strategy.get_params(context)

                if self.permission_level == PermissionLevel.SUGGEST_ONLY:
                    return {
                        "suggestion": f"Apply {strategy.__class__.__name__}",
                        "note": "SUGGEST_ONLY mode: No parameters modified",
                    }

                if self.permission_level == PermissionLevel.DRY_RUN:
                    params["_dry_run"] = True
                    params["_note"] = "DRY_RUN mode: Review before executing"

                return params

        return {}


class GateReporter:
    """Gate 上报器 - 向 Gate Engine 报告失败"""

    def generate_report(
        self,
        context: FailureContext,
        handling_result: FailureHandlingResult
    ) -> Dict[str, Any]:
        """生成 Gate 报告"""
        return {
            "gate_id": "G4-P2",  # 运行 Gate
            "status": "BLOCKED",
            "validation_id": context.validation_result.validation_id,
            "failure_category": handling_result.category.value,
            "action_taken": handling_result.action.value,
            "primary_anomaly": self._serialize_anomaly(
                context.validation_result.anomalies[0]
                if context.validation_result.anomalies else None
            ),
            "attempt_count": context.attempt_count,
            "message": handling_result.message,
            "timestamp": time.time(),
        }

    def _serialize_anomaly(self, anomaly: Optional[Anomaly]) -> Optional[Dict[str, Any]]:
        """序列化异常"""
        if anomaly is None:
            return None
        return {
            "type": anomaly.anomaly_type.value,
            "severity": anomaly.severity,
            "location": anomaly.location,
            "message": anomaly.message,
        }


class CorrectionSpecGenerator:
    """CorrectionSpec 生成器 - 为学习闭环提供输入"""

    def __init__(self):
        self.spec_count = 0

    def generate(
        self,
        context: FailureContext,
        handling_result: FailureHandlingResult
    ) -> Dict[str, Any]:
        """生成 CorrectionSpec"""
        self.spec_count += 1

        base_spec = {
            "spec_id": f"CORR-{self.spec_count}-{int(time.time())}",
            "source": "G4-P2_FAILURE",
            "timestamp": time.time(),
            "validation_result": {
                "validation_id": context.validation_result.validation_id,
                "status": context.validation_result.status.value,
                "n_anomalies": len(context.validation_result.anomalies),
                "anomalies": [
                    self._serialize_anomaly(a)
                    for a in context.validation_result.anomalies
                ],
            },
        }

        # 使用分析器生成的 spec 或自行生成
        if handling_result and handling_result.correction_spec:
            base_spec.update(handling_result.correction_spec)
        else:
            base_spec["suggested_actions"] = self._infer_actions(context)

        return base_spec

    def _serialize_anomaly(self, anomaly: Anomaly) -> Dict[str, Any]:
        """序列化异常"""
        return {
            "type": anomaly.anomaly_type.value,
            "severity": anomaly.severity,
            "location": anomaly.location,
            "message": anomaly.message,
        }

    def _infer_actions(self, context: FailureContext) -> List[str]:
        """推断修正动作"""
        actions = []

        for anomaly in context.validation_result.anomalies:
            if anomaly.anomaly_type == AnomalyType.DIVERGENCE:
                actions.append("检查边界条件完整性")
                actions.append("验证网格质量")
                actions.append("尝试降低松弛因子")

            elif anomaly.anomaly_type == AnomalyType.HIGH_ASPECT_RATIO:
                actions.append("重新生成网格，降低宽长比")

            elif anomaly.anomaly_type == AnomalyType.NEGATIVE_PRESSURE:
                actions.append("检查压力边界条件")
                actions.append("验证初始压力场")

        return actions or ["人工审查"]


class FailureHandler:
    """
    失败处理器主类

    路由 ValidationResult 到适当的处理路径。

    用法:
        handler = FailureHandler()

        # 验证失败后调用
        if not validation_result.is_valid():
            context = FailureContext(
                validation_result=validation_result,
                solver_result=solver_result
            )
            handling_result = handler.handle(context)

            if handling_result.action == FailureAction.RETRY:
                params = handler.get_retry_params(handling_result, context)
                # 使用新参数重试
            elif handling_result.action == FailureAction.ESCALATE:
                report = handler.generate_gate_report(context, handling_result)
                # 上报到 Gate Engine
    """

    def __init__(
        self,
        max_attempts: int = 3,
        enable_retry: bool = True,
        enable_correction: bool = True,
        permission_level: PermissionLevel = PermissionLevel.DRY_RUN,
    ):
        self.max_attempts = max_attempts
        self.enable_retry = enable_retry
        self.enable_correction = enable_correction
        self.permission_level = permission_level

        self.analyzer = FailureAnalyzer()
        self.retry_handler = RetryHandler(permission_level=permission_level)
        self.gate_reporter = GateReporter()
        self.correction_generator = CorrectionSpecGenerator()

    def handle(
        self,
        context: FailureContext
    ) -> FailureHandlingResult:
        """处理失败"""
        # 确保 attempt_count 在合理范围内
        context.attempt_count = min(context.attempt_count, self.max_attempts)
        context.max_attempts = self.max_attempts

        # 分析失败并决定处理策略
        handling_result = self.analyzer.analyze(context)

        # 根据配置调整策略
        if handling_result.action == FailureAction.RETRY and not self.enable_retry:
            handling_result.action = FailureAction.ESCALATE

        return handling_result

    def get_retry_params(
        self,
        handling_result: FailureHandlingResult,
        context: FailureContext
    ) -> Dict[str, Any]:
        """获取重试参数"""
        return self.retry_handler.get_retry_params(handling_result, context)

    def generate_gate_report(
        self,
        context: FailureContext,
        handling_result: Optional[FailureHandlingResult] = None
    ) -> Dict[str, Any]:
        """生成 Gate 报告"""
        if handling_result is None:
            handling_result = self.analyzer.analyze(context)

        return self.gate_reporter.generate_report(context, handling_result)

    def generate_correction_spec(
        self,
        context: FailureContext,
        handling_result: Optional[FailureHandlingResult] = None
    ) -> Dict[str, Any]:
        """生成 CorrectionSpec"""
        if handling_result is None:
            handling_result = self.analyzer.analyze(context)

        if not self.enable_correction:
            return {}

        return self.correction_generator.generate(context, handling_result)


# 便捷函数
def handle_failure(
    validation_result: ValidationResult,
    solver_result: Any = None,
    attempt_count: int = 0,
) -> FailureHandlingResult:
    """便捷函数：处理验证失败"""
    handler = FailureHandler()
    context = FailureContext(
        validation_result=validation_result,
        solver_result=solver_result,
        attempt_count=attempt_count,
    )
    return handler.handle(context)


def should_retry(validation_result: ValidationResult, attempt_count: int = 0) -> bool:
    """便捷函数：判断是否应该重试"""
    handler = FailureHandler()
    context = FailureContext(
        validation_result=validation_result,
        attempt_count=attempt_count,
    )
    result = handler.handle(context)
    return result.action == FailureAction.RETRY
