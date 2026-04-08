#!/usr/bin/env python3
"""
Result Validator - 结果验证器

实现残差检查、收敛判定、数值异常检测。
对应 G4-P2 运行 Gate 的技术基础。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from knowledge_compiler.phase2.execution_layer.schema import (
    ConvergenceCriterion,
    ConvergenceType,
)


class ValidationStatus(Enum):
    """验证状态"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    PENDING = "pending"


class AnomalyType(Enum):
    """异常类型"""
    RESIDUAL_SPIKE = "residual_spike"  # 残差突然增大
    DIVERGENCE = "divergence"  # 发散
    NaN_DETECTED = "nan_detected"  # 检测到 NaN
    INF_DETECTED = "inf_detected"  # 检测到 Inf
    NEGATIVE_PRESSURE = "negative_pressure"  # 负压
    HIGH_ASPECT_RATIO = "high_aspect_ratio"  # 高宽长比
    BLOW_UP_STAGNATION = "blow_up_stagnation"  # 射吹停滞


@dataclass
class Anomaly:
    """异常事件"""
    anomaly_type: AnomalyType
    severity: str  # "low", "medium", "high", "critical"
    location: str = ""  # 在哪个场/位置
    value: float = 0.0
    threshold: float = 0.0
    message: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class ValidationResult:
    """验证结果"""
    validation_id: str = field(default_factory=lambda: f"VAL-{time.time():.0f}")
    status: ValidationStatus = ValidationStatus.PENDING
    anomalies: List[Anomaly] = field(default_factory=list)
    convergence_info: Dict[str, Any] = field(default_factory=dict)
    residual_info: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_anomaly(self, anomaly: Anomaly) -> None:
        """添加异常"""
        self.anomalies.append(anomaly)
        if anomaly.severity in ["high", "critical"]:
            self.status = ValidationStatus.FAILED
        elif anomaly.severity == "medium" and self.status != ValidationStatus.FAILED:
            self.status = ValidationStatus.WARNING

    def is_valid(self) -> bool:
        """检查是否通过验证"""
        return self.status == ValidationStatus.PASSED

    def get_critical_anomalies(self) -> List[Anomaly]:
        """获取关键异常"""
        return [a for a in self.anomalies if a.severity == "critical"]

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            "validation_id": self.validation_id,
            "status": self.status.value,
            "n_anomalies": len(self.anomalies),
            "n_critical": len(self.get_critical_anomalies()),
            "n_warnings": len(self.warnings),
        }


class ResidualChecker:
    """残差检查器"""

    def __init__(self, spike_threshold: float = 100.0):
        self.spike_threshold = spike_threshold

    def check_residuals(
        self,
        residuals: Dict[str, List[float]],
        tolerance: float = 1e-6,
    ) -> List[Anomaly]:
        """检查残差序列"""
        anomalies = []

        for var_name, values in residuals.items():
            if not values:
                continue

            # 检查突然增大
            for i in range(1, len(values)):
                if values[i] > self.spike_threshold * values[i-1]:
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.RESIDUAL_SPIKE,
                        severity="high",
                        location=f"{var_name}[{i}]",
                        value=values[i],
                        threshold=self.spike_threshold * values[i-1],
                        message=f"{var_name} 残差在步骤 {i} 突然增大 {values[i]/values[i-1]:.1f} 倍"
                    ))
                    break

            # 检查是否达到容差
            final_residual = values[-1]
            if final_residual > tolerance:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.DIVERGENCE,
                    severity="high",
                    location=var_name,
                    value=final_residual,
                    threshold=tolerance,
                    message=f"{var_name} 最终残差 {final_residual:.2e} 超过容差 {tolerance:.2e}"
                ))

        return anomalies


class ConvergenceChecker:
    """收敛检查器"""

    def __init__(self):
        self.convergence_patterns = [
            re.compile(r"solution\s+converges?", re.IGNORECASE),
            re.compile(r"Final\s+residual\s*<.*tolerance", re.IGNORECASE),
            re.compile(r"No\s+Iterations\s+\d+", re.IGNORECASE),
        ]

    def check_log(self, log_content: str) -> Tuple[bool, str]:
        """检查日志中的收敛信息"""
        for pattern in self.convergence_patterns:
            if pattern.search(log_content):
                return True, "Convergence pattern found"

        # 检查发散模式
        divergence_patterns = [
            re.compile(r"diverging", re.IGNORECASE),
            re.compile(f"residuals.*increas(?:ing|es)", re.IGNORECASE),
        ]
        for pattern in divergence_patterns:
            if pattern.search(log_content):
                return False, "Divergence pattern found"

        # 默认: 假设未收敛但也没有发散
        return False, "No clear convergence/divergence pattern"

    def check_criteria(
        self,
        criteria: List[ConvergenceCriterion],
        current_values: Dict[str, float],
    ) -> Tuple[bool, Dict[str, bool]]:
        """检查收敛条件"""
        results = {}

        for criterion in criteria:
            if criterion.type == ConvergenceType.RESIDUAL:
                field = criterion.name  # ConvergenceCriterion uses 'name' for field name
                target = criterion.target_value
                value = current_values.get(field, float('inf'))
                results[field] = value <= target

            elif criterion.type == ConvergenceType.FORCE:
                # 力收敛检查比较复杂，这里简化处理
                pass

        converged = all(results.values()) if results else False
        return converged, results


class NumericalAnomalyDetector:
    """数值异常检测器"""

    def __init__(self):
        self.anomaly_patterns = {
            AnomalyType.NaN_DETECTED: re.compile(r"\bNaN\b|-?nan", re.IGNORECASE),
            AnomalyType.INF_DETECTED: re.compile(r"\bInf\b|-?inf", re.IGNORECASE),
        }

    def detect_anomalies(
        self,
        field_data: Dict[str, Any],
    ) -> List[Anomaly]:
        """检测数值异常"""
        anomalies = []

        for field_name, data in field_data.items():
            if isinstance(data, (int, float)):
                if str(data).lower() in ['nan', '-nan', 'inf', '-inf']:
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.NaN_DETECTED if 'nan' in str(data).lower() else AnomalyType.INF_DETECTED,
                        severity="critical",
                        location=field_name,
                        value=float(data),
                        message=f"{field_name} 包含非数值 {data}"
                    ))
            elif isinstance(data, list):
                for i, val in enumerate(data):
                    if isinstance(val, (int, float)) and (str(val).lower() in ['nan', '-nan', 'inf', '-inf']):
                        anomalies.append(Anomaly(
                            anomaly_type=AnomalyType.NaN_DETECTED if 'nan' in str(val).lower() else AnomalyType.INF_DETECTED,
                            severity="critical",
                            location=f"{field_name}[{i}]",
                            value=float(val),
                            message=f"{field_name}[{i}] 包含非数值 {val}"
                        ))

        return anomalies

    def check_pressure_anomalies(
        self,
        pressure_field: Dict[str, Any],
    ) -> List[Anomaly]:
        """检查压力场异常（负压）"""
        anomalies = []

        if "values" in pressure_field:
            for i, value in enumerate(pressure_field["values"]):
                if isinstance(value, (int, float)) and value < 0:
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.NEGATIVE_PRESSURE,
                        severity="medium",
                        location=f"pressure[{i}]",
                        value=value,
                        message=f"检测到负压 {value} 在位置 {i}"
                    ))

        return anomalies

    def check_mesh_quality(
        self,
        mesh_stats: Dict[str, Any],
        thresholds: Optional[Dict[str, float]] = None,
    ) -> List[Anomaly]:
        """检查网格质量异常"""
        anomalies = []

        if thresholds is None:
            thresholds = {
                "max_aspect_ratio": 1000.0,
                "max_non_orthogonality": 70.0,
            }

        # 检查高宽长比
        if "max_aspect_ratio" in mesh_stats:
            ar = mesh_stats["max_aspect_ratio"]
            if ar > thresholds.get("max_aspect_ratio", 1000):
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.HIGH_ASPECT_RATIO,
                    severity="medium",
                    location="mesh",
                    value=ar,
                    threshold=thresholds["max_aspect_ratio"],
                    message=f"网格最大宽长比 {ar} 超过阈值 {thresholds['max_aspect_ratio']}"
                ))

        return anomalies


class ResultValidator:
    """结果验证器主类"""

    def __init__(
        self,
        residual_spike_threshold: float = 100.0,
        default_tolerance: float = 1e-6,
    ):
        self.residual_checker = ResidualChecker(spike_threshold=residual_spike_threshold)
        self.convergence_checker = ConvergenceChecker()
        self.anomaly_detector = NumericalAnomalyDetector()
        self.default_tolerance = default_tolerance

    def validate_solver_result(
        self,
        solver_result: Any,  # SolverResult
        criteria: Optional[List[ConvergenceCriterion]] = None,
    ) -> ValidationResult:
        """验证求解器结果"""
        result = ValidationResult()

        try:
            # 1. 检查日志中的收敛信息
            if hasattr(solver_result, 'stdout'):
                log_content = solver_result.stdout
                converged, message = self.convergence_checker.check_log(log_content)
                result.convergence_info = {
                    "converged": converged,
                    "reason": message,
                }

                if not converged:
                    result.add_anomaly(Anomaly(
                        anomaly_type=AnomalyType.DIVERGENCE,
                        severity="high",
                        message=f"求解未收敛: {message}"
                    ))

                # 2. 解析残差信息（简单版本）
                import re
                residuals = {"initial": {}, "final": {}, "iterations": []}
                for match in re.finditer(r'solving for (\w+), Final residual = ([\d.e-]+)', log_content):
                    var_name = match.group(1)
                    final_residual = float(match.group(2))
                    residuals["final"][var_name] = final_residual
                    residuals["iterations"].append({
                        "variable": var_name,
                        "final_residual": final_residual,
                    })
                result.residual_info = residuals

                # 3. 检查残差异常
                if residuals.get("iterations"):
                    for iter_info in residuals["iterations"]:
                        var_name = iter_info.get("variable", "")
                        final_residual = iter_info.get("final_residual", 0)

                        if final_residual > self.default_tolerance:
                            result.add_anomaly(Anomaly(
                                anomaly_type=AnomalyType.DIVERGENCE,
                                severity="medium",
                                location=var_name,
                                value=final_residual,
                                threshold=self.default_tolerance,
                                message=f"{var_name} 最终残差 {final_residual:.2e} 未收敛"
                            ))

            # 2. 检查数值异常
            if hasattr(solver_result, 'error_message') and solver_result.error_message:
                result.add_anomaly(Anomaly(
                    anomaly_type=AnomalyType.DIVERGENCE,
                    severity="critical",
                    message=f"求解器错误: {solver_result.error_message}"
                ))

            # 3. 检查退出码
            if hasattr(solver_result, 'exit_code') and solver_result.exit_code != 0:
                result.add_anomaly(Anomaly(
                    anomaly_type=AnomalyType.DIVERGENCE,
                    severity="high",
                    message=f"求解器非零退出码: {solver_result.exit_code}"
                ))

            # 4. 设置最终状态
            if result.status == ValidationStatus.PENDING:
                result.status = ValidationStatus.PASSED

        except Exception as e:
            result.status = ValidationStatus.FAILED
            result.add_anomaly(Anomaly(
                anomaly_type=AnomalyType.DIVERGENCE,
                severity="critical",
                message=f"验证过程出错: {str(e)}"
            ))

        return result

    def validate_field_data(
        self,
        field_data: Dict[str, Any],
    ) -> ValidationResult:
        """验证场数据"""
        result = ValidationResult()

        # 1. 检测数值异常
        anomalies = self.anomaly_detector.detect_anomalies(field_data)
        for anomaly in anomalies:
            result.add_anomaly(anomaly)

        # 2. 检查压力场
        for field_name, data in field_data.items():
            if "pressure" in field_name.lower() or "p" == field_name:
                anomalies = self.anomaly_detector.check_pressure_anomalies(data)
                for anomaly in anomalies:
                    result.add_anomaly(anomaly)

        # 3. 设置最终状态
        if result.status == ValidationStatus.PENDING:
            result.status = ValidationStatus.PASSED

        return result

    def validate_mesh_quality(
        self,
        mesh_stats: Dict[str, Any],
        thresholds: Optional[Dict[str, float]] = None,
    ) -> ValidationResult:
        """验证网格质量"""
        result = ValidationResult()

        anomalies = self.anomaly_detector.check_mesh_quality(mesh_stats, thresholds)
        for anomaly in anomalies:
            result.add_anomaly(anomaly)

        if result.status == ValidationStatus.PENDING:
            result.status = ValidationStatus.PASSED

        return result


# 便捷函数
def validate_solver_result(
    solver_result: Any,
    criteria: Optional[List[ConvergenceCriterion]] = None,
) -> ValidationResult:
    """便捷函数：验证求解器结果"""
    validator = ResultValidator()
    return validator.validate_solver_result(solver_result, criteria)


def validate_field_data(field_data: Dict[str, Any]) -> ValidationResult:
    """便捷函数：验证场数据"""
    validator = ResultValidator()
    return validator.validate_field_data(field_data)


def validate_mesh_quality(
    mesh_stats: Dict[str, Any],
    thresholds: Optional[Dict[str, float]] = None,
) -> ValidationResult:
    """便捷函数：验证网格质量"""
    validator = ResultValidator()
    return validator.validate_mesh_quality(mesh_stats, thresholds)
