#!/usr/bin/env python3
"""
Phase 2 Execution Layer: Physics Planner Schema

物理规划器 - 根据问题特征自动选择物理模型和求解策略。

这是 Phase 2 Execution Layer 的核心组件，负责消费 Phase 1/2 编译的知识规范，
生成可执行的求解器配置。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# Enums (按照 Opus 4.6 审查意见：所有类型必须是 enum，不能用 str)
# ============================================================================

class FlowType(Enum):
    """流动类型"""
    LAMINAR = "laminar"
    TURBULENT = "turbulent"
    TRANSITIONAL = "transitional"


class TurbulenceModel(Enum):
    """湍流模型"""
    K_EPSILON = "kEpsilon"
    K_OMEGA_SST = "kOmegaSST"
    SPALART_ALLMARAS = "SpalartAllmaras"
    LES = "LES"
    DES = "DES"
    NONE = "none"


class TimeTreatment(Enum):
    """时间处理方式"""
    STEADY = "steady"
    TRANSIENT = "transient"


class Compressibility(Enum):
    """可压缩性"""
    INCOMPRESSIBLE = "incompressible"
    COMPRESSIBLE = "compressible"
    LOW_MACH = "low_mach"  # 低马赫数可压缩


class BCType(Enum):
    """边界条件类型（按 Opus 4.6 审查意见扩展）"""
    # 壁面
    WALL_NO_SLIP = "wall_no_slip"
    WALL_SLIP = "wall_slip"
    WALL_MOVING = "wall_moving"
    WALL_ROUGH = "wall_rough"
    WALL_ADIABATIC = "wall_adiabatic"
    WALL_ISOTHERMAL = "wall_isothermal"

    # 入口
    INLET_VELOCITY = "inlet_velocity"
    INLET_MASS_FLOW = "inlet_mass_flow"
    INLET_PRESSURE = "inlet_pressure"
    INLET_TOTAL_PRESSURE = "inlet_total_pressure"

    # 出口
    OUTLET_PRESSURE = "outlet_pressure"
    OUTLET_ZERO_GRADIENT = "outlet_zero_gradient"
    OUTLET_OUTFLOW = "outlet_outflow"

    # 对称/周期
    SYMMETRY = "symmetry"
    CYCLIC = "cyclic"
    WEDGE = "wedge"  # 轴对称
    EMPTY = "empty"

    # 远场
    FREESTREAM = "freestream"

    # 特殊
    INTERFACE = "interface"  # 多区域接口


class SolverType(Enum):
    """求解器类型"""
    SIMPLE_FOAM = "simpleFoam"
    PIMPLE_FOAM = "pimpleFoam"
    PISO_FOAM = "pisoFoam"
    RHO_SIMPLE_FOAM = "rhoSimpleFoam"
    RHO_PIMPLE_FOAM = "rhoPimpleFoam"
    BUOYANT_SIMPLE_FOAM = "buoyantSimpleFoam"
    BUOYANT_PIMPLE_FOAM = "buoyantPimpleFoam"
    INTER_FOAM = "interFoam"
    INTER_ISOFOAM = "interIsoFoam"
    SRF_SIMPLE_FOAM = "SRFSimpleFoam"
    SU2_CFD = "SU2_CFD"


class ProblemType(Enum):
    """问题类型（按 Opus 4.6 审查意见扩展）"""
    # 一级分类
    INTERNAL_FLOW = "internal_flow"
    EXTERNAL_FLOW = "external_flow"
    HEAT_TRANSFER = "heat_transfer"
    MULTIPHASE = "multiphase"
    FSI = "fsi"

    # 二级细分
    INTERNAL_FLOW_PIPE = "internal_flow_pipe"
    INTERNAL_FLOW_CAVITY = "internal_flow_cavity"
    INTERNAL_FLOW_STEP = "internal_flow_step"
    EXTERNAL_FLOW_BLUFF_BODY = "external_flow_bluff_body"
    EXTERNAL_FLOW_AIRFOIL = "external_flow_airfoil"
    HEAT_TRANSFER_FORCED = "heat_transfer_forced"
    HEAT_TRANSFER_NATURAL = "heat_transfer_natural"
    HEAT_TRANSFER_MIXED = "heat_transfer_mixed"


class ConvergenceType(Enum):
    """收敛类型"""
    RESIDUAL = "residual"
    FORCE = "force"
    INTEGRAL = "integral"
    MONITOR_POINT = "monitor_point"


# ============================================================================
# Core Data Classes
# ============================================================================

@dataclass
class PhysicsModel:
    """
    物理模型配置（按 Opus 4.6 审查意见扩展）

    包含所有必要的物理建模参数。
    """
    # --- 基础配置（原设计）---
    solver_type: SolverType
    flow_type: FlowType
    turbulence_model: Optional[TurbulenceModel]
    energy_model: bool = False
    species_model: bool = False
    multiphase_model: bool = False

    # --- 必须补充的字段（Opus 4.6 要求）---
    time_treatment: TimeTreatment = TimeTreatment.STEADY
    compressibility: Compressibility = Compressibility.INCOMPRESSIBLE
    gravity: bool = False  # 自然对流必须
    radiation_model: Optional[str] = None  # 高温问题必须

    # --- 建议补充的字段（Opus 4.6 建议）---
    reference_values: Dict[str, float] = field(default_factory=dict)
    wall_treatment: Optional[str] = None


@dataclass
class BoundaryCondition:
    """
    边界条件（按 Opus 4.6 审查意见改为 enum 类型）
    """
    name: str
    type: BCType
    values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConvergenceCriterion:
    """
    收敛标准（按 Opus 4.6 审查意见结构化）

    不再使用弱类型的 Dict[str, float]。
    """
    name: str
    type: ConvergenceType
    target_value: float
    comparison: str  # "below", "stable_within", "converged_to"
    window: int = 100
    tolerance: float = 0.01


@dataclass
class PhysicsPlan:
    """
    物理规划方案（按 Opus 4.6 审查意见完善）
    """
    plan_id: str = field(default_factory=lambda: f"PHYSICS-{uuid.uuid4().hex[:8]}")
    problem_type: ProblemType = ProblemType.INTERNAL_FLOW

    # 核心物理模型
    physics_model: Optional[PhysicsModel] = None

    # 求解器推荐（基于二维决策矩阵）
    recommended_solver: Optional[SolverType] = None

    # 边界条件
    boundary_conditions: List[BoundaryCondition] = field(default_factory=list)

    # 求解器设置
    solver_settings: Dict[str, Any] = field(default_factory=dict)

    # 收敛标准
    convergence_criteria: List[ConvergenceCriterion] = field(default_factory=list)

    # 元数据
    created_at: float = field(default_factory=time.time)
    confidence: float = 1.0  # 推理置信度


# ============================================================================
# 二维决策矩阵（按 Opus 4.6 审查意见实现）
# ============================================================================

@dataclass
class SolverSelectionMatrix:
    """
    求解器选择二维决策矩阵

    compressibility × time_treatment → solver
    """
    # 不可压缩 × 稳态
    incomp_steady: SolverType = SolverType.SIMPLE_FOAM
    # 不可压缩 × 瞬态
    incomp_transient: SolverType = SolverType.PIMPLE_FOAM
    # 可压缩 × 稳态
    comp_steady: SolverType = SolverType.RHO_SIMPLE_FOAM
    # 可压缩 × 瞬态
    comp_transient: SolverType = SolverType.RHO_PIMPLE_FOAM
    # 低马赫 × 稳态
    lowmach_steady: SolverType = SolverType.BUOYANT_SIMPLE_FOAM
    # 低马赫 × 瞬态
    lowmach_transient: SolverType = SolverType.BUOYANT_PIMPLE_FOAM
    # 多相流（通常瞬态）
    multiphase_vof: SolverType = SolverType.INTER_FOAM


def select_solver_by_matrix(
    compressibility: Compressibility,
    time_treatment: TimeTreatment,
    is_multiphase: bool = False,
    solver_type: Optional[SolverType] = None,
) -> SolverType:
    """
    按照二维决策矩阵选择求解器

    Args:
        compressibility: 可压缩性
        time_treatment: 时间处理
        is_multiphase: 是否多相流
        solver_type: 优先使用的求解器类型（如 SU2）

    Returns:
        推荐的求解器

    按照审查意见：Ma = 0.3 是分界线
    """
    matrix = SolverSelectionMatrix()

    # 多相流优先
    if is_multiphase:
        return SolverType.INTER_FOAM

    # SU2 优先（如果配置可用）
    if solver_type == SolverType.SU2_CFD:
        if compressibility in [Compressibility.COMPRESSIBLE, Compressibility.LOW_MACH]:
            return SolverType.SU2_CFD

    # 低马赫数可压缩流（Ma < 0.3）
    if compressibility == Compressibility.LOW_MACH:
        if time_treatment == TimeTreatment.STEADY:
            return matrix.lowmach_steady
        else:
            return matrix.lowmach_transient

    # 根据二维矩阵选择
    if compressibility == Compressibility.INCOMPRESSIBLE:
        if time_treatment == TimeTreatment.STEADY:
            return matrix.incomp_steady
        else:
            return matrix.incomp_transient

    elif compressibility == Compressibility.COMPRESSIBLE:
        if time_treatment == TimeTreatment.STEADY:
            return matrix.comp_steady
        else:
            return matrix.comp_transient

    else:  # LOW_MACH
        if time_treatment == TimeTreatment.STEADY:
            return matrix.lowmach_steady
        else:
            return matrix.lowmach_transient


# ============================================================================
# 边界条件验证器（按 Opus 4.6 审查意见实现）
# ============================================================================

@dataclass
class BCCombinationRule:
    """边界条件组合规则"""
    must_have: List[str] = field(default_factory=list)
    must_not: List[str] = field(default_factory=list)
    recommended: List[str] = field(default_factory=list)


# 问题类型 → BC 组合规则
BC_VALIDATION_RULES: Dict[ProblemType, BCCombinationRule] = {
    ProblemType.INTERNAL_FLOW: BCCombinationRule(
        must_have=["INLET_*", "OUTLET_*"],
        must_not=["FREESTREAM"],
    ),
    ProblemType.EXTERNAL_FLOW: BCCombinationRule(
        must_have=["FREESTREAM", "INLET_*"],
        recommended=["WALL_NO_SLIP"],
    ),
    ProblemType.HEAT_TRANSFER_NATURAL: BCCombinationRule(
        must_have=["WALL_*"],
        must_not=["INLET_VELOCITY"],  # 自然对流没有入口速度
    ),
}


def validate_boundary_conditions(
    problem_type: ProblemType,
    bcs: List[BoundaryCondition],
) -> Tuple[bool, List[str], List[str]]:
    """
    验证边界条件组合

    Args:
        problem_type: 问题类型
        bcs: 边界条件列表

    Returns:
        (是否有效, 错误列表, 警告列表)
    """
    errors = []
    warnings = []

    rule = BC_VALIDATION_RULES.get(problem_type)

    if not rule:
        # 没有规则的情况下，不做严格验证
        return True, [], []

    # 检查必须有的边界条件类型
    if rule.must_have:
        has_inlet = any(
            bc.type.value.startswith("inlet_") or
            bc.type == BCType.INLET_VELOCITY or
            bc.type == BCType.INLET_MASS_FLOW or
            bc.type == BCType.INLET_PRESSURE or
            bc.type == BCType.INLET_TOTAL_PRESSURE
            for bc in bcs
        )
        has_outlet = any(
            bc.type.value.startswith("outlet_") or
            bc.type == BCType.OUTLET_PRESSURE or
            bc.type == BCType.OUTLET_ZERO_GRADIENT or
            bc.type == BCType.OUTLET_OUTFLOW
            for bc in bcs
        )

        if "INLET_*" in rule.must_have and not has_inlet:
            errors.append("Missing inlet boundary condition")
        if "OUTLET_*" in rule.must_have and not has_outlet:
            errors.append("Missing outlet boundary condition")

    # 检查不允许的边界条件类型
    if rule.must_not:
        for bc in bcs:
            bc_type_str = bc.type.value.upper()
            for forbidden in rule.must_not:
                forbidden_upper = forbidden.upper()
                if bc_type_str == forbidden_upper or (
                    forbidden_upper.endswith("*") and
                    bc_type_str.startswith(forbidden_upper.rstrip("*"))
                ):
                    errors.append(f"Invalid BC type for {problem_type.value}: {bc_type_str}")

    # 检查推荐的配置
    if rule.recommended:
        for bc in bcs:
            if bc.type.value not in rule.recommended:
                warnings.append(f"BC type {bc.type.value} not recommended for {problem_type.value}")

    return len(errors) == 0, errors, warnings


# ============================================================================
# 收敛判断逻辑（按 Opus 4.6 审查意见实现）
# ============================================================================

def is_converged(
    criteria: List[ConvergenceCriterion],
    history: Dict[str, List[float]],
) -> Tuple[bool, str]:
    """
    判断是否收敛

    Args:
        criteria: 收敛标准列表
        history: 历史数据 {name: [values]}

    Returns:
        (是否收敛, 状态消息)
    """
    import numpy as np

    for c in criteria:
        if c.name not in history or len(history[c.name]) < c.window:
            return False, f"{c.name}: insufficient data (need {c.window} steps)"

        values = history[c.name][-c.window:]

        if c.comparison == "below":
            if values[-1] > c.target_value:
                return False, f"{c.name} = {values[-1]:.2e} > target {c.target_value:.2e}"

        elif c.comparison == "stable_within":
            if len(values) < 2:
                continue
            mean_val = np.mean(values)
            if mean_val == 0:
                # 避免除零
                variation = (max(values) - min(values)) / (max(abs(v) for v in values) or 1)
            else:
                variation = (max(values) - min(values)) / abs(mean_val)

            if variation > c.tolerance:
                return False, f"{c.name} variation {variation:.2%} > {c.tolerance:.2%}"

        elif c.comparison == "converged_to":
            if len(values) < 2:
                continue
            variation = abs(values[-1] - values[-2])
            if variation > c.tolerance * abs(values[-1]):
                return False, f"{c.name} change {variation:.2e} > {c.tolerance:.2%} of target"

    return True, "All criteria met"


def get_default_convergence_criteria(problem_type: ProblemType) -> List[ConvergenceCriterion]:
    """
    获取默认收敛标准（按 Opus 4.6 审查意见推荐）

    Args:
        problem_type: 问题类型

    Returns:
        收敛标准列表
    """
    if problem_type in [
        ProblemType.INTERNAL_FLOW,
        ProblemType.INTERNAL_FLOW_PIPE,
        ProblemType.INTERNAL_FLOW_CAVITY,
        ProblemType.INTERNAL_FLOW_STEP,
    ]:
        return [
            ConvergenceCriterion(
                name="p",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-5,
                comparison="below",
            ),
            ConvergenceCriterion(
                name="U",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-5,
                comparison="below",
            ),
        ]

    elif problem_type in [
        ProblemType.EXTERNAL_FLOW,
        ProblemType.EXTERNAL_FLOW_BLUFF_BODY,
        ProblemType.EXTERNAL_FLOW_AIRFOIL,
    ]:
        return [
            ConvergenceCriterion(
                name="p",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-6,
                comparison="below",
            ),
            ConvergenceCriterion(
                name="Cd",
                type=ConvergenceType.FORCE,
                target_value=0.005,  # 0.5%
                comparison="stable_within",
                window=200,
                tolerance=0.01,
            ),
            ConvergenceCriterion(
                name="Cl",
                type=ConvergenceType.FORCE,
                target_value=0.005,
                comparison="stable_within",
                window=200,
                tolerance=0.01,
            ),
        ]

    elif problem_type in [
        ProblemType.HEAT_TRANSFER,
        ProblemType.HEAT_TRANSFER_FORCED,
        ProblemType.HEAT_TRANSFER_NATURAL,
        ProblemType.HEAT_TRANSFER_MIXED,
    ]:
        return [
            ConvergenceCriterion(
                name="p",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-5,
                comparison="below",
            ),
            ConvergenceCriterion(
                name="T",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-7,
                comparison="below",
            ),
            ConvergenceCriterion(
                name="Nu_avg",
                type=ConvergenceType.INTEGRAL,
                target_value=0.01,
                comparison="stable_within",
                tolerance=0.01,
            ),
        ]

    # 默认
    return [
        ConvergenceCriterion(
            name="p",
            type=ConvergenceType.RESIDUAL,
            target_value=1e-5,
            comparison="below",
        ),
    ]


# ============================================================================
# Factory Functions
# ============================================================================

def create_physics_plan(
    problem_type: ProblemType,
    physics_model: Optional[PhysicsModel] = None,
) -> PhysicsPlan:
    """
    创建物理规划

    Args:
        problem_type: 问题类型
        physics_model: 物理模型

    Returns:
        物理规划
    """
    plan = PhysicsPlan(problem_type=problem_type)

    if physics_model:
        plan.physics_model = physics_model
        # 根据模型推荐求解器
        plan.recommended_solver = select_solver_by_matrix(
            physics_model.compressibility,
            physics_model.time_treatment,
            physics_model.multiphase_model,
            physics_model.solver_type,
        )
    else:
        # 使用默认值
        plan.recommended_solver = SolverType.SIMPLE_FOAM

    # 添加默认收敛标准
    plan.convergence_criteria = get_default_convergence_criteria(problem_type)

    return plan


def infer_physics_from_params(
    reynolds: float,
    mach: float = 0,
    has_gravity: bool = False,
    has_heat_transfer: bool = False,
) -> PhysicsModel:
    """
    从无量纲数推断物理模型

    Args:
        reynolds: 雷诺数
        mach: 马赫数
        has_gravity: 是否有重力
        has_heat_transfer: 是否有传热

    Returns:
        推断的物理模型
    """
    # 流动类型
    flow_type = FlowType.LAMINAR if reynolds < 4000 else FlowType.TURBULENT

    # 湍流模型
    if flow_type == FlowType.TURBULENT:
        turbulence_model = TurbulenceModel.K_EPSILON
    else:
        turbulence_model = None

    # 可压缩性
    # 按照 Opus 4.6 审查意见：Ma = 0.3 是分界线，边界包含在下区间
    if mach <= 0.01:
        compressibility = Compressibility.INCOMPRESSIBLE
    elif mach <= 0.3:
        compressibility = Compressibility.LOW_MACH
    else:
        compressibility = Compressibility.COMPRESSIBLE

    # 时间处理
    # 简化：假设低雷诺数或瞬态效应需要 transient
    time_treatment = TimeTreatment.STEADY

    # 构建参考值
    reference_values = {
        "Re": reynolds,
        "Ma": mach,
    }
    if mach > 0.01:
        reference_values["Ma"] = mach

    return PhysicsModel(
        solver_type=SolverType.SIMPLE_FOAM,  # 默认稳态不可压缩求解器
        flow_type=flow_type,
        turbulence_model=turbulence_model,
        energy_model=has_heat_transfer,
        time_treatment=time_treatment,
        compressibility=compressibility,
        gravity=has_gravity,
        reference_values=reference_values,
    )


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Enums
    "FlowType",
    "TurbulenceModel",
    "TimeTreatment",
    "Compressibility",
    "BCType",
    "SolverType",
    "ProblemType",
    "ConvergenceType",
    # Core classes
    "PhysicsModel",
    "BoundaryCondition",
    "ConvergenceCriterion",
    "PhysicsPlan",
    # Decision matrix
    "SolverSelectionMatrix",
    "select_solver_by_matrix",
    # Validation
    "BCCombinationRule",
    "BC_VALIDATION_RULES",
    "validate_boundary_conditions",
    # Convergence
    "is_converged",
    "get_default_convergence_criteria",
    # Factory
    "create_physics_plan",
    "infer_physics_from_params",
]
