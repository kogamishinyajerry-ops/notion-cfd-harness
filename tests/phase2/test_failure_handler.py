#!/usr/bin/env python3
"""
Tests for Failure Handler - 失败路径处理器
"""

import pytest

from knowledge_compiler.phase2.execution_layer.failure_handler import (
    PermissionLevel,
    FailureAction,
    FailureAnalyzer,
    FailureCategory,
    FailureContext,
    FailureHandler,
    FailureHandlingResult,
    GateReporter,
    RetryHandler,
    CorrectionSpecGenerator,
    handle_failure,
    should_retry,
)
from knowledge_compiler.phase2.execution_layer.result_validator import (
    Anomaly,
    AnomalyType,
    ValidationStatus,
    ValidationResult,
)


class TestFailureAnalyzer:
    """测试失败分析器"""

    def test_analyze_residual_spike(self):
        """测试残差突然增大分析"""
        analyzer = FailureAnalyzer()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            location="p[10]",
            message="压力残差突然增大"
        ))

        context = FailureContext(validation_result=result)
        handling_result = analyzer.analyze(context)

        assert handling_result.category == FailureCategory.RECOVERABLE
        assert handling_result.action == FailureAction.RETRY
        assert handling_result.retry_with is not None
        assert handling_result.retry_with["strategy"] == "reduce_time_step"

    def test_analyze_nan_detected(self):
        """测试 NaN 检测分析"""
        analyzer = FailureAnalyzer()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NaN_DETECTED,
            severity="critical",
            location="U[100]",
            message="检测到 NaN"
        ))

        context = FailureContext(validation_result=result)
        handling_result = analyzer.analyze(context)

        assert handling_result.category == FailureCategory.NON_RECOVERABLE
        assert handling_result.action == FailureAction.ESCALATE

    def test_analyze_divergence_with_retry_limit(self):
        """测试发散达到重试上限时的分析"""
        analyzer = FailureAnalyzer()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="求解发散"
        ))

        context = FailureContext(
            validation_result=result,
            attempt_count=3,
            max_attempts=3
        )
        handling_result = analyzer.analyze(context)

        # 达到重试上限，应该升级到 ESCALATE
        assert handling_result.action == FailureAction.ESCALATE

    def test_analyze_high_aspect_ratio(self):
        """测试高宽长比分析"""
        analyzer = FailureAnalyzer()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.HIGH_ASPECT_RATIO,
            severity="medium",
            location="mesh",
            message="网格宽长比过高"
        ))

        context = FailureContext(validation_result=result)
        handling_result = analyzer.analyze(context)

        assert handling_result.category == FailureCategory.CONFIGURATION
        assert handling_result.action == FailureAction.GENERATE_CORRECTION
        assert handling_result.correction_spec is not None
        assert len(handling_result.correction_spec["suggested_actions"]) > 0


class TestFailureHandler:
    """测试失败处理器"""

    def test_handle_residual_spike(self):
        """测试处理残差突然增大"""
        handler = FailureHandler(max_attempts=3)

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            message="残差突然增大"
        ))

        context = FailureContext(validation_result=result)
        handling_result = handler.handle(context)

        assert handling_result.action == FailureAction.RETRY

    def test_handle_with_retry_disabled(self):
        """测试禁用重试时的处理"""
        handler = FailureHandler(max_attempts=3, enable_retry=False)

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            message="残差突然增大"
        ))

        context = FailureContext(validation_result=result)
        handling_result = handler.handle(context)

        # 重试被禁用，应该直接升级
        assert handling_result.action == FailureAction.ESCALATE

    def test_get_retry_params(self):
        """测试获取重试参数"""
        handler = FailureHandler()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            message="残差突然增大"
        ))

        context = FailureContext(validation_result=result)
        handling_result = handler.handle(context)

        if handling_result.action == FailureAction.RETRY:
            params = handler.get_retry_params(handling_result, context)
            assert params is not None
            assert "strategy" in params

    def test_generate_gate_report(self):
        """测试生成 Gate 报告"""
        handler = FailureHandler()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="critical",
            message="求解发散"
        ))

        context = FailureContext(validation_result=result, attempt_count=2)
        report = handler.generate_gate_report(context)

        assert report["gate_id"] == "G4-P2"
        assert report["status"] == "BLOCKED"
        assert report["attempt_count"] == 2

    def test_generate_correction_spec(self):
        """测试生成 CorrectionSpec"""
        handler = FailureHandler()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.HIGH_ASPECT_RATIO,
            severity="medium",
            message="网格宽长比过高"
        ))

        context = FailureContext(validation_result=result)
        spec = handler.generate_correction_spec(context)

        assert "spec_id" in spec
        assert spec["source"] == "G4-P2_FAILURE"
        assert "suggested_actions" in spec


class TestRetryHandler:
    """测试重试处理器"""

    def test_get_retry_params_residual_spike(self):
        """测试获取残差突然增大时的重试参数"""
        retry_handler = RetryHandler()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            message="残差突然增大"
        ))

        handling_result = FailureHandlingResult(
            action=FailureAction.RETRY,
            category=FailureCategory.RECOVERABLE,
            retry_with={"strategy": "reduce_time_step", "time_step_factor": 0.5}
        )

        context = FailureContext(validation_result=result)
        params = retry_handler.get_retry_params(handling_result, context)

        assert params["strategy"] == "reduce_time_step"

    def test_get_retry_params_divergence(self):
        """测试获取发散时的重试参数"""
        retry_handler = RetryHandler()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="求解发散"
        ))

        handling_result = FailureHandlingResult(
            action=FailureAction.RETRY,
            category=FailureCategory.RECOVERABLE,
            retry_with={"strategy": "increase_iterations"}
        )

        context = FailureContext(validation_result=result)
        params = retry_handler.get_retry_params(handling_result, context)

        assert params["strategy"] == "increase_iterations"
        assert params["max_iter"] >= 1000

    def test_permission_level_suggest_only(self):
        """测试 SUGGEST_ONLY 权限级别"""
        retry_handler = RetryHandler(permission_level=PermissionLevel.SUGGEST_ONLY)

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            message="残差突然增大"
        ))

        handling_result = FailureHandlingResult(
            action=FailureAction.RETRY,
            category=FailureCategory.RECOVERABLE,
            retry_with={"strategy": "reduce_time_step", "reason": "残差突然增大，降低时间步长"}
        )

        context = FailureContext(validation_result=result)
        params = retry_handler.get_retry_params(handling_result, context)

        # SUGGEST_ONLY 模式应返回建议而非实际参数
        assert "suggestion" in params
        assert params["strategy"] == "reduce_time_step"
        assert "note" in params
        assert "SUGGEST_ONLY" in params["note"]

    def test_permission_level_dry_run(self):
        """测试 DRY_RUN 权限级别"""
        retry_handler = RetryHandler(permission_level=PermissionLevel.DRY_RUN)

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="求解发散"
        ))

        handling_result = FailureHandlingResult(
            action=FailureAction.RETRY,
            category=FailureCategory.RECOVERABLE,
            retry_with={"strategy": "increase_iterations"}
        )

        context = FailureContext(validation_result=result)
        params = retry_handler.get_retry_params(handling_result, context)

        # DRY_RUN 模式应返回参数但添加 _dry_run 标记
        assert params["strategy"] == "increase_iterations"
        assert params.get("_dry_run") is True
        assert "_note" in params

    def test_permission_level_execute(self):
        """测试 EXECUTE 权限级别"""
        retry_handler = RetryHandler(permission_level=PermissionLevel.EXECUTE)

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            message="残差突然增大"
        ))

        handling_result = FailureHandlingResult(
            action=FailureAction.RETRY,
            category=FailureCategory.RECOVERABLE,
            retry_with={"strategy": "reduce_time_step", "time_step_factor": 0.5}
        )

        context = FailureContext(validation_result=result)
        params = retry_handler.get_retry_params(handling_result, context)

        # EXECUTE 模式应返回完整参数，无 _dry_run 标记
        assert params["strategy"] == "reduce_time_step"
        assert params.get("_dry_run") is None
        assert "delta_t" in params

    def test_failure_handler_with_permission_level(self):
        """测试 FailureHandler 传递 permission_level"""
        handler = FailureHandler(permission_level=PermissionLevel.SUGGEST_ONLY)

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            message="残差突然增大"
        ))

        context = FailureContext(validation_result=result)
        handling_result = handler.handle(context)

        assert handling_result.action == FailureAction.RETRY

        # 获取重试参数应使用 SUGGEST_ONLY 模式
        params = handler.get_retry_params(handling_result, context)
        assert "suggestion" in params or "_note" in params


class TestGateReporter:
    """测试 Gate 上报器"""

    def test_generate_report_basic(self):
        """测试生成基本报告"""
        reporter = GateReporter()

        result = ValidationResult(validation_id="VAL-123")
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="求解发散"
        ))

        context = FailureContext(validation_result=result, attempt_count=1)
        handling_result = FailureHandlingResult(
            action=FailureAction.ESCALATE,
            category=FailureCategory.NON_RECOVERABLE,
            message="求解发散"
        )

        report = reporter.generate_report(context, handling_result)

        assert report["gate_id"] == "G4-P2"
        assert report["status"] == "BLOCKED"
        assert report["validation_id"] == "VAL-123"
        assert report["primary_anomaly"]["type"] == "divergence"


class TestCorrectionSpecGenerator:
    """测试 CorrectionSpec 生成器"""

    def test_generate_basic_spec(self):
        """测试生成基本 CorrectionSpec"""
        generator = CorrectionSpecGenerator()

        result = ValidationResult(validation_id="VAL-456")
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.HIGH_ASPECT_RATIO,
            severity="medium",
            location="mesh",
            message="网格宽长比过高"
        ))

        context = FailureContext(validation_result=result)
        handling_result = FailureHandlingResult(
            action=FailureAction.GENERATE_CORRECTION,
            category=FailureCategory.CONFIGURATION,
            correction_spec={
                "suggested_actions": ["重新生成网格"]
            }
        )

        spec = generator.generate(context, handling_result)

        assert "spec_id" in spec
        assert spec["source"] == "G4-P2_FAILURE"
        assert spec["suggested_actions"] == ["重新生成网格"]

    def test_generate_without_precomputed_spec(self):
        """测试无预计算 spec 时的生成"""
        generator = CorrectionSpecGenerator()

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="求解发散"
        ))

        context = FailureContext(validation_result=result)
        spec = generator.generate(context, None)

        assert "suggested_actions" in spec
        assert len(spec["suggested_actions"]) > 0


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_handle_failure(self):
        """测试 handle_failure 函数"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="求解发散"
        ))

        handling_result = handle_failure(result)

        assert isinstance(handling_result, FailureHandlingResult)
        assert handling_result.action in [FailureAction.RETRY, FailureAction.ESCALATE]

    def test_should_retry_true(self):
        """测试 should_retry 返回 True"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            message="残差突然增大"
        ))

        assert should_retry(result) is True

    def test_should_retry_false(self):
        """测试 should_retry 返回 False"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NaN_DETECTED,
            severity="critical",
            message="检测到 NaN"
        ))

        assert should_retry(result) is False


class TestFailureWorkflow:
    """测试完整的失败处理工作流"""

    def test_retry_then_escalate_workflow(self):
        """测试重试后升级的工作流"""
        handler = FailureHandler(max_attempts=2)

        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="求解发散"
        ))

        # 第一次失败
        context = FailureContext(validation_result=result, attempt_count=0)
        handling_result = handler.handle(context)

        assert handling_result.action == FailureAction.RETRY
        params = handler.get_retry_params(handling_result, context)
        assert params is not None

        # 第二次失败（仍在重试上限内）
        context = FailureContext(validation_result=result, attempt_count=1)
        handling_result = handler.handle(context)

        # 根据实现，可能仍然 RETRY 或 ESCALATE
        assert handling_result.action in [FailureAction.RETRY, FailureAction.ESCALATE]

        # 第三次失败（超过重试上限）
        context = FailureContext(validation_result=result, attempt_count=2)
        handling_result = handler.handle(context)

        # 超过上限，必须升级
        assert handling_result.action == FailureAction.ESCALATE

        # 生成 Gate 报告
        report = handler.generate_gate_report(context, handling_result)
        assert report["attempt_count"] == 2
        assert report["status"] == "BLOCKED"
