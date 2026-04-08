#!/usr/bin/env python3
"""
Phase 2 Postprocess Runner - 标准后处理执行器

D 层组件 - 负责从求解器结果中提取和处理数据，输出标准化的后处理结果。
不直接输出 NL Postprocess 格式，通过 Adapter 层与 B 层解耦。

架构:
    Solver Runner → Postprocess Runner → StandardPostprocessResult
                                               ↓
                                        PostprocessAdapter
                                               ↓
                                       NL Postprocess Executor (Phase 1 B层)
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
)


# ============================================================================
# Enums
# ============================================================================

class PostprocessStatus(Enum):
    """后处理状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FieldType(Enum):
    """场变量类型"""
    SCALAR = "scalar"  # 标量 (压力、温度等)
    VECTOR = "vector"  # 矢量 (速度、力等)
    TENSOR = "tensor"  # 张量 (应力、应变等)


# ============================================================================
# Standard Postprocess Result (D Layer Output Format)
# ============================================================================

@dataclass
class FieldData:
    """场数据

    支持稳态和瞬态数据:
    - 稳态: time_steps 为空或只包含一个时间点
    - 瞬态: time_steps 包含多个时间点，可按时间索引数据
    """
    name: str  # 场名称 (p, U, T, etc.)
    field_type: FieldType
    dimensions: int  # 维度 (1=标量, 3=矢量, 9=张量)
    unit: str = ""  # 单位
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    data_location: str = ""  # 数据位置 (文件路径或内存引用)
    time_steps: List[float] = field(default_factory=list)  # 可用的时间步 (瞬态支持)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_transient(self) -> bool:
        """检查是否为瞬态数据"""
        return len(self.time_steps) > 1

    @property
    def n_time_steps(self) -> int:
        """获取时间步数量"""
        return len(self.time_steps)


@dataclass
class ResidualSummary:
    """残差摘要"""
    variables: Dict[str, float] = field(default_factory=dict)  # 最终残差
    initial: Dict[str, float] = field(default_factory=dict)  # 初始残差
    iterations: Dict[str, int] = field(default_factory=dict)  # 迭代次数
    converged: bool = False
    convergence_reason: str = ""


@dataclass
class DerivedQuantity:
    """衍生量"""
    name: str  # 衍生量名称
    value: float
    unit: str = ""
    location: str = ""  # 位置信息
    formula: str = ""  # 计算公式


@dataclass
class StandardPostprocessResult:
    """
    标准后处理结果 - D 层输出格式

    这是 Postprocess Runner 的标准输出，不依赖任何特定的可视化或 NL 接口。
    Adapter 层负责将此格式转换为其他系统需要的格式。

    支持模式:
    - 单案例稳态: case_path 为单个路径，fields 的 time_steps 为空或单点
    - 单案例瞬态: case_path 为单个路径，fields 的 time_steps 包含多点
    - 多案例对比: 使用 related_case_paths 引用相关案例
    """
    result_id: str = field(default_factory=lambda: f"PP-{time.time():.0f}")
    status: PostprocessStatus = PostprocessStatus.PENDING
    created_at: float = field(default_factory=time.time)

    # 核心数据
    fields: List[FieldData] = field(default_factory=list)  # 提取的场数据
    residuals: Optional[ResidualSummary] = None  # 残差摘要
    derived_quantities: List[DerivedQuantity] = field(default_factory=list)  # 衍生量

    # 元数据
    case_path: str = ""  # 算例路径 (主案例)
    related_case_paths: List[str] = field(default_factory=list)  # 相关案例路径 (多案例对比)
    solver_type: str = ""  # 求解器类型
    solver_version: str = ""
    mesh_info: Dict[str, Any] = field(default_factory=dict)  # 网格信息

    # 处理信息
    processing_time: float = 0.0
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)

    def is_success(self) -> bool:
        """检查是否成功"""
        return self.status == PostprocessStatus.COMPLETED

    def get_field(self, name: str) -> Optional[FieldData]:
        """获取指定场数据"""
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def add_field(self, field: FieldData) -> None:
        """添加场数据"""
        self.fields.append(field)

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            "result_id": self.result_id,
            "status": self.status.value,
            "n_fields": len(self.fields),
            "converged": self.residuals.converged if self.residuals else False,
            "n_derivatives": len(self.derived_quantities),
            "processing_time": self.processing_time,
            "is_multi_case": len(self.related_case_paths) > 0,
            "is_transient": any(f.is_transient for f in self.fields),
        }

    def add_related_case(self, case_path: str) -> None:
        """添加相关案例（用于多案例对比）"""
        if case_path not in self.related_case_paths:
            self.related_case_paths.append(case_path)

    @property
    def is_multi_case(self) -> bool:
        """检查是否为多案例对比"""
        return len(self.related_case_paths) > 0

    @property
    def is_transient(self) -> bool:
        """检查是否包含瞬态数据"""
        return any(f.is_transient for f in self.fields)


# ============================================================================
# Postprocess Runner (D Layer)
# ============================================================================

class FieldDataExtractor:
    """场数据提取器"""

    def extract_from_openfoam(
        self,
        case_dir: str,
        time_step: str = "0",
    ) -> List[FieldData]:
        """从 OpenFOAM 算例提取场数据"""
        fields = []
        case_path = Path(case_dir)

        # 检查常见场文件
        field_names = ["p", "U", "T", "k", "epsilon", "omega", "nut"]
        field_types = {
            "p": FieldType.SCALAR,
            "T": FieldType.SCALAR,
            "k": FieldType.SCALAR,
            "epsilon": FieldType.SCALAR,
            "omega": FieldType.SCALAR,
            "nut": FieldType.SCALAR,
            "U": FieldType.VECTOR,
        }

        for field_name in field_names:
            # 检查场文件是否存在
            field_file = case_path / time_step / f"{field_name}"
            if not field_file.exists():
                # 尝试其他时间步
                continue

            # 读取场文件头获取基本信息
            try:
                with open(field_file, "r") as f:
                    lines = [f.readline().strip() for _ in range(5)]

                # 解析维度
                dimensions = 1  # 默认标量
                for line in lines:
                    if "dimensions" in line.lower():
                        match = re.search(r"(\d+)", line)
                        if match:
                            dimensions = int(match.group(1))
                        break

                field_type = field_types.get(field_name, FieldType.SCALAR)

                fields.append(FieldData(
                    name=field_name,
                    field_type=field_type,
                    dimensions=dimensions,
                    data_location=str(field_file),
                ))
            except Exception as e:
                # 记录警告但继续处理其他场
                pass

        return fields


class ResidualParser:
    """残差解析器"""

    def parse_from_log(self, log_content: str) -> ResidualSummary:
        """从日志解析残差信息"""
        summary = ResidualSummary()

        # 解析最终残差
        for match in re.finditer(
            r"solving for (\w+),\s*Final\s*residual\s*=\s*([\d.e-]+),\s*No\s*Iterations\s*(\d+)",
            log_content,
            re.IGNORECASE
        ):
            var_name = match.group(1)
            final_residual = float(match.group(2))
            iterations = int(match.group(3))

            summary.variables[var_name] = final_residual
            summary.iterations[var_name] = iterations

        # 解析初始残差
        for match in re.finditer(
            r"solving for (\w+),\s*initial\s*residual\s*=\s*([\d.e-]+)",
            log_content,
            re.IGNORECASE
        ):
            var_name = match.group(1)
            initial_residual = float(match.group(2))
            summary.initial[var_name] = initial_residual

        # 检查收敛状态 - 先检查失败模式
        divergence_patterns = [
            r"Maximum iterations reached",
            r"diverging",
            r"stabilising",
        ]

        for pattern in divergence_patterns:
            if re.search(pattern, log_content, re.IGNORECASE):
                summary.converged = False
                summary.convergence_reason = "Divergence pattern found"
                return summary

        # 再检查收敛模式
        convergence_patterns = [
            r"solution\s+converges?",
            r"Final\s+residuals*.*<.*tolerance",
            r"End\s*=\s*\d+\.\d+.*s.*cumulative",  # OpenFOAM 结束模式
        ]

        for pattern in convergence_patterns:
            if re.search(pattern, log_content, re.IGNORECASE):
                summary.converged = True
                summary.convergence_reason = "Convergence pattern found"
                break

        return summary


class DerivedQuantityCalculator:
    """衍生量计算器"""

    def compute_pressure_drop(
        self,
        field_data: List[FieldData],
        inlet_location: str = "inlet",
        outlet_location: str = "outlet",
    ) -> Optional[DerivedQuantity]:
        """计算压降"""
        # 简化版本 - 实际实现需要读取具体的场数据
        return DerivedQuantity(
            name="pressure_drop",
            value=0.0,
            unit="Pa",
            location=f"{inlet_location} → {outlet_location}",
            formula="p_inlet - p_outlet",
        )

    def compute_velocity_magnitude(
        self,
        velocity_field: FieldData,
    ) -> Optional[DerivedQuantity]:
        """计算速度幅值"""
        if velocity_field.field_type != FieldType.VECTOR:
            return None

        return DerivedQuantity(
            name="velocity_magnitude",
            value=0.0,
            unit="m/s",
            location="domain_average",
            formula="sqrt(U_x^2 + U_y^2 + U_z^2)",
        )

    def compute_reynolds_number(
        self,
        velocity: float,
        length: float,
        kinematic_viscosity: float = 1.5e-5,  # 空气运动粘度
    ) -> DerivedQuantity:
        """计算雷诺数"""
        re = (velocity * length) / kinematic_viscosity
        return DerivedQuantity(
            name="reynolds_number",
            value=re,
            unit="",
            formula="velocity * length / nu",
        )


class PostprocessRunner:
    """
    后处理运行器 - D 层核心组件

    职责:
    1. 从求解器结果中提取场数据
    2. 解析残差和收敛信息
    3. 计算衍生量
    4. 输出标准化的 StandardPostprocessResult

    不负责:
    - 自然语言解析 (由 Phase 1 B 层负责)
    - 可视化 (由专门的可视化组件负责)
    """

    def __init__(
        self,
        extractor: Optional[FieldDataExtractor] = None,
        residual_parser: Optional[ResidualParser] = None,
        calculator: Optional[DerivedQuantityCalculator] = None,
    ):
        self.extractor = extractor or FieldDataExtractor()
        self.residual_parser = residual_parser or ResidualParser()
        self.calculator = calculator or DerivedQuantityCalculator()

    def run(
        self,
        case_dir: str,
        solver_output: str = "",
        options: Optional[Dict[str, Any]] = None,
    ) -> StandardPostprocessResult:
        """
        执行后处理

        Args:
            case_dir: 算例目录
            solver_output: 求解器输出 (日志)
            options: 后处理选项

        Returns:
            StandardPostprocessResult: 标准化的后处理结果
        """
        start_time = time.time()
        options = options or {}

        result = StandardPostprocessResult(
            case_path=case_dir,
            status=PostprocessStatus.RUNNING,
        )

        try:
            # 1. 解析残差
            if solver_output:
                result.residuals = self.residual_parser.parse_from_log(solver_output)

            # 2. 提取场数据
            time_step = options.get("time_step", "0")
            fields = self.extractor.extract_from_openfoam(case_dir, time_step)
            result.fields = fields

            # 3. 计算衍生量
            if options.get("compute_derivatives", True):
                if options.get("pressure_drop", True):
                    dp = self.calculator.compute_pressure_drop(fields)
                    if dp:
                        result.derived_quantities.append(dp)

                if options.get("reynolds_number", False):
                    velocity = options.get("velocity", 1.0)
                    length = options.get("characteristic_length", 1.0)
                    re = self.calculator.compute_reynolds_number(velocity, length)
                    result.derived_quantities.append(re)

            # 4. 完成处理
            result.status = PostprocessStatus.COMPLETED
            result.processing_time = time.time() - start_time

        except Exception as e:
            result.status = PostprocessStatus.FAILED
            result.error_message = str(e)
            result.processing_time = time.time() - start_time

        return result

    def run_from_solver_result(
        self,
        solver_result: Any,
        options: Optional[Dict[str, Any]] = None,
    ) -> StandardPostprocessResult:
        """
        从求解器结果运行后处理

        Args:
            solver_result: SolverResult 对象
            options: 后处理选项

        Returns:
            StandardPostprocessResult
        """
        case_dir = getattr(solver_result, "case_dir", "")
        solver_output = getattr(solver_result, "stdout", "")

        return self.run(case_dir, solver_output, options)


# ============================================================================
# Convenience Functions
# ============================================================================

def run_postprocess(
    case_dir: str,
    solver_output: str = "",
    options: Optional[Dict[str, Any]] = None,
) -> StandardPostprocessResult:
    """便捷函数：运行后处理"""
    runner = PostprocessRunner()
    return runner.run(case_dir, solver_output, options)


def extract_field_data(
    case_dir: str,
    fields: Optional[List[str]] = None,
    time_step: str = "0",
) -> List[FieldData]:
    """便捷函数：提取场数据"""
    extractor = FieldDataExtractor()
    all_fields = extractor.extract_from_openfoam(case_dir, time_step)

    if fields is None:
        return all_fields

    # 过滤指定场
    return [f for f in all_fields if f.name in fields]
