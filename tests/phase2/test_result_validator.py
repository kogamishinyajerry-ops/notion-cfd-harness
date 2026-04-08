#!/usr/bin/env python3
"""
Tests for Result Validator - 结果验证器测试
"""

import pytest
import time
from knowledge_compiler.phase2.execution_layer.result_validator import (
    Anomaly,
    AnomalyType,
    ValidationResult,
    ValidationStatus,
    ResidualChecker,
    ConvergenceChecker,
    NumericalAnomalyDetector,
    ResultValidator,
    validate_solver_result,
    validate_field_data,
    validate_mesh_quality,
)
from knowledge_compiler.phase2.execution_layer.schema import (
    ConvergenceCriterion,
    ConvergenceType,
)


class TestAnomaly:
    """测试异常类"""

    def test_anomaly_creation(self):
        """测试创建异常"""
        anomaly = Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="high",
            location="p",
            value=1.5,
            threshold=1.0,
            message="Residual spike detected"
        )
        assert anomaly.anomaly_type == AnomalyType.RESIDUAL_SPIKE
        assert anomaly.severity == "high"
        assert anomaly.location == "p"
        assert anomaly.value == 1.5


class TestValidationResult:
    """测试验证结果类"""

    def test_validation_result_creation(self):
        """测试创建验证结果"""
        result = ValidationResult()
        assert result.status == ValidationStatus.PENDING
        assert result.anomalies == []
        assert result.validation_id.startswith("VAL-")

    def test_add_anomaly_critical(self):
        """测试添加关键异常"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NaN_DETECTED,
            severity="critical",
            message="NaN detected"
        ))
        assert result.status == ValidationStatus.FAILED
        assert len(result.anomalies) == 1

    def test_add_anomaly_high(self):
        """测试添加高级异常"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="Divergence"
        ))
        assert result.status == ValidationStatus.FAILED

    def test_add_anomaly_medium(self):
        """测试添加中级异常"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NEGATIVE_PRESSURE,
            severity="medium",
            message="Negative pressure"
        ))
        assert result.status == ValidationStatus.WARNING

    def test_add_anomaly_low(self):
        """测试添加低级异常"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.HIGH_ASPECT_RATIO,
            severity="low",
            message="High aspect ratio"
        ))
        assert result.status == ValidationStatus.PENDING

    def test_multiple_anomalies(self):
        """测试多个异常"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.HIGH_ASPECT_RATIO,
            severity="low",
            message="High aspect ratio"
        ))
        assert result.status == ValidationStatus.PENDING

        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NEGATIVE_PRESSURE,
            severity="medium",
            message="Negative pressure"
        ))
        assert result.status == ValidationStatus.WARNING

    def test_is_valid(self):
        """测试验证检查"""
        result = ValidationResult(status=ValidationStatus.PASSED)
        assert result.is_valid() is True

        result.status = ValidationStatus.FAILED
        assert result.is_valid() is False

    def test_get_critical_anomalies(self):
        """测试获取关键异常"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NaN_DETECTED,
            severity="critical",
            message="NaN"
        ))
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NEGATIVE_PRESSURE,
            severity="medium",
            message="Negative pressure"
        ))

        critical = result.get_critical_anomalies()
        assert len(critical) == 1
        assert critical[0].severity == "critical"

    def test_get_summary(self):
        """测试获取摘要"""
        result = ValidationResult()
        result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NaN_DETECTED,
            severity="critical",
            message="NaN"
        ))
        result.warnings.append("Test warning")

        summary = result.get_summary()
        assert summary["n_anomalies"] == 1
        assert summary["n_critical"] == 1
        assert summary["n_warnings"] == 1
        assert "validation_id" in summary


class TestResidualChecker:
    """测试残差检查器"""

    def test_check_residuals_empty(self):
        """测试空残差"""
        checker = ResidualChecker()
        anomalies = checker.check_residuals({})
        assert anomalies == []

    def test_check_residuals_normal(self):
        """测试正常残差"""
        checker = ResidualChecker()
        residuals = {
            "p": [0.1, 0.01, 0.001, 1e-6],
            "U": [0.2, 0.02, 0.002, 1e-6]
        }
        anomalies = checker.check_residuals(residuals, tolerance=1e-5)
        # 最后的残差低于容差，应该没有异常
        assert len(anomalies) == 0

    def test_check_residuals_spike(self):
        """测试残差突然增大"""
        checker = ResidualChecker(spike_threshold=10.0)
        residuals = {
            "p": [0.001, 0.1]  # 100倍增长
        }
        anomalies = checker.check_residuals(residuals)
        # 应该检测到 spike 和 divergence（最终残差超过容差）
        assert len(anomalies) >= 1
        assert any(a.anomaly_type == AnomalyType.RESIDUAL_SPIKE for a in anomalies)
        spike = next(a for a in anomalies if a.anomaly_type == AnomalyType.RESIDUAL_SPIKE)
        assert spike.severity == "high"

    def test_check_residuals_divergence(self):
        """测试发散"""
        checker = ResidualChecker()
        residuals = {
            "p": [0.1, 0.5, 1.0]  # 最终残差很大
        }
        anomalies = checker.check_residuals(residuals, tolerance=1e-6)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.DIVERGENCE
        assert "超过容差" in anomalies[0].message


class TestConvergenceChecker:
    """测试收敛检查器"""

    def test_check_log_converged(self):
        """测试收敛日志"""
        checker = ConvergenceChecker()
        log = "Time = 1\nsolution converges\nEnd"
        converged, reason = checker.check_log(log)
        assert converged is True
        assert "Convergence pattern found" in reason

    def test_check_log_diverging(self):
        """测试发散日志"""
        checker = ConvergenceChecker()
        log = "Time = 1\nresiduals are increasing\nEnd"
        converged, reason = checker.check_log(log)
        assert converged is False
        assert "Divergence" in reason

    def test_check_log_final_residual(self):
        """测试最终残差模式"""
        checker = ConvergenceChecker()
        log = "Final residual < tolerance 1e-06\nEnd"
        converged, reason = checker.check_log(log)
        assert converged is True

    def test_check_log_empty(self):
        """测试空日志"""
        checker = ConvergenceChecker()
        converged, reason = checker.check_log("")
        assert converged is False
        assert "No clear" in reason

    def test_check_criteria_residual(self):
        """测试残差条件检查"""
        checker = ConvergenceChecker()
        criteria = [
            ConvergenceCriterion(
                name="p",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-6,
                comparison="below",
                tolerance=1e-6
            )
        ]
        current_values = {"p": 1e-7}
        converged, results = checker.check_criteria(criteria, current_values)
        assert converged is True
        assert results["p"] is True

    def test_check_criteria_not_converged(self):
        """测试未收敛条件"""
        checker = ConvergenceChecker()
        criteria = [
            ConvergenceCriterion(
                name="p",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-6,
                comparison="below",
                tolerance=1e-6
            )
        ]
        current_values = {"p": 1e-5}
        converged, results = checker.check_criteria(criteria, current_values)
        assert converged is False
        assert results["p"] is False


class TestNumericalAnomalyDetector:
    """测试数值异常检测器"""

    def test_detect_anomalies_nan(self):
        """测试 NaN 检测"""
        detector = NumericalAnomalyDetector()
        field_data = {"p": float('nan')}
        anomalies = detector.detect_anomalies(field_data)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.NaN_DETECTED
        assert anomalies[0].severity == "critical"

    def test_detect_anomalies_inf(self):
        """测试 Inf 检测"""
        detector = NumericalAnomalyDetector()
        field_data = {"U": float('inf')}
        anomalies = detector.detect_anomalies(field_data)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.INF_DETECTED

    def test_detect_anomalies_list(self):
        """测试列表中的异常"""
        detector = NumericalAnomalyDetector()
        field_data = {"p": [1.0, 2.0, float('nan'), 4.0]}
        anomalies = detector.detect_anomalies(field_data)
        assert len(anomalies) == 1
        assert "p[2]" in anomalies[0].location

    def test_check_pressure_anomalies_negative(self):
        """测试负压检测"""
        detector = NumericalAnomalyDetector()
        pressure_field = {"values": [100000, 50000, -1000, 80000]}
        anomalies = detector.check_pressure_anomalies(pressure_field)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.NEGATIVE_PRESSURE
        assert anomalies[0].value == -1000

    def test_check_mesh_quality_high_aspect_ratio(self):
        """测试高宽长比检测"""
        detector = NumericalAnomalyDetector()
        mesh_stats = {"max_aspect_ratio": 1500}
        anomalies = detector.check_mesh_quality(mesh_stats)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.HIGH_ASPECT_RATIO

    def test_check_mesh_quality_normal(self):
        """测试正常网格质量"""
        detector = NumericalAnomalyDetector()
        mesh_stats = {"max_aspect_ratio": 500}
        anomalies = detector.check_mesh_quality(mesh_stats)
        assert len(anomalies) == 0


class TestResultValidator:
    """测试结果验证器主类"""

    def test_validate_solver_result_converged(self):
        """测试验证收敛结果"""
        validator = ResultValidator()

        class MockSolverResult:
            stdout = "solution converges\nsolving for p, Final residual = 1e-07, No Iterations 45\nEnd"
            exit_code = 0
            error_message = ""

        result = validator.validate_solver_result(MockSolverResult())
        assert result.status == ValidationStatus.PASSED
        assert result.convergence_info["converged"] is True

    def test_validate_solver_result_diverged(self):
        """测试验证发散结果"""
        validator = ResultValidator()

        class MockSolverResult:
            stdout = "error: simulation failed"
            exit_code = 1
            error_message = "Simulation failed"

        result = validator.validate_solver_result(MockSolverResult())
        assert result.status == ValidationStatus.FAILED
        # 应该有错误相关异常
        assert len(result.anomalies) > 0

    def test_validate_field_data_normal(self):
        """测试验证正常场数据"""
        validator = ResultValidator()
        field_data = {"p": [100000, 101000, 99000], "U": [1.0, 2.0, 3.0]}
        result = validator.validate_field_data(field_data)
        assert result.status == ValidationStatus.PASSED

    def test_validate_field_data_with_nan(self):
        """测试验证含 NaN 场数据"""
        validator = ResultValidator()
        field_data = {"p": [100000, float('nan'), 99000]}
        result = validator.validate_field_data(field_data)
        assert result.status == ValidationStatus.FAILED
        assert any(a.anomaly_type == AnomalyType.NaN_DETECTED for a in result.anomalies)

    def test_validate_mesh_quality_good(self):
        """测试验证良好网格"""
        validator = ResultValidator()
        mesh_stats = {"max_aspect_ratio": 500, "max_non_orthogonality": 60}
        result = validator.validate_mesh_quality(mesh_stats)
        assert result.status == ValidationStatus.PASSED

    def test_validate_mesh_quality_poor(self):
        """测试验证差网格"""
        validator = ResultValidator()
        mesh_stats = {"max_aspect_ratio": 1500}
        result = validator.validate_mesh_quality(mesh_stats)
        assert result.status == ValidationStatus.WARNING


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_validate_solver_result_func(self):
        """测试验证求解器结果便捷函数"""
        class MockSolverResult:
            stdout = "solution converges"
            exit_code = 0
            error_message = ""

        result = validate_solver_result(MockSolverResult())
        assert result is not None
        assert hasattr(result, 'status')

    def test_validate_field_data_func(self):
        """测试验证场数据便捷函数"""
        result = validate_field_data({"p": [1.0, 2.0]})
        assert result is not None
        assert hasattr(result, 'status')

    def test_validate_mesh_quality_func(self):
        """测试验证网格质量便捷函数"""
        result = validate_mesh_quality({"max_aspect_ratio": 100})
        assert result is not None
        assert hasattr(result, 'status')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
