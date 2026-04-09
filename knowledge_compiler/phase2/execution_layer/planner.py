#!/usr/bin/env python3
"""
Phase 2 Execution Layer: Physics Planner

物理规划器实现 - 根据问题特征自动选择物理模型和求解策略。

这是 Phase 2 Execution Layer 的核心组件。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from knowledge_compiler.phase2.execution_layer.schema import (
    # Enums
    FlowType,
    TurbulenceModel,
    TimeTreatment,
    Compressibility,
    BCType,
    SolverType,
    ProblemType,
    ConvergenceType,
    # Core classes
    PhysicsModel,
    BoundaryCondition,
    ConvergenceCriterion,
    PhysicsPlan,
    # Decision matrix
    select_solver_by_matrix,
    # Validation
    validate_boundary_conditions,
    # Convergence
    is_converged,
    get_default_convergence_criteria,
    # Factory
    create_physics_plan,
    infer_physics_from_params,
)


class PhysicsPlanner:
    """
    物理规划器

    根据问题特征自动规划物理模型和求解策略。
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the physics planner

        Args:
            strict_mode: 是否启用严格模式（更严格的验证）
        """
        self.strict_mode = strict_mode

    def plan_from_spec(
        self,
        spec: Dict[str, Any],
    ) -> PhysicsPlan:
        """
        从规范（CanonicalSpec 内容）生成物理规划

        Args:
            spec: 规范字典（来自 CanonicalSpec.content）

        Returns:
            物理规划
        """
        # 推断问题类型
        problem_type = self._infer_problem_type(spec)
        if problem_type is None:
            problem_type = ProblemType.INTERNAL_FLOW

        # 推断物理参数
        physics_model = self._infer_physics_model(spec, problem_type)

        # 创建规划
        plan = create_physics_plan(problem_type, physics_model)

        # 添加边界条件
        plan.boundary_conditions = self._extract_boundary_conditions(spec)

        return plan

    def plan_from_case_params(
        self,
        reynolds: float,
        mach: float = 0,
        has_gravity: bool = False,
        has_heat_transfer: bool = False,
        geometry_type: str = "generic",
    ) -> PhysicsPlan:
        """
        从 case 参数生成物理规划

        Args:
            reynolds: 雷诺数
            mach: 马赫数
            has_gravity: 是否有重力
            has_heat_transfer: 是否有传热
            geometry_type: 几何类型

        Returns:
            物理规划
        """
        # 推断问题类型
        problem_type = self._classify_problem_type(
            reynolds, mach, has_gravity, has_heat_transfer, geometry_type
        )

        # 推断物理模型
        physics_model = infer_physics_from_params(
            reynolds, mach, has_gravity, has_heat_transfer
        )

        # 创建规划
        plan = create_physics_plan(problem_type, physics_model)

        # 推荐求解器
        plan.recommended_solver = select_solver_by_matrix(
            physics_model.compressibility,
            physics_model.time_treatment,
            physics_model.multiphase_model,
            physics_model.solver_type,
        )

        # 添加默认边界条件
        plan.boundary_conditions = self._get_default_bcs(problem_type)

        return plan

    def validate_plan(
        self,
        plan: PhysicsPlan,
    ) -> Tuple[bool, List[str], List[str]]:
        """
        验证物理规划

        Args:
            plan: 物理规划

        Returns:
            (是否有效, 错误列表, 警告列表)
        """
        errors = []
        warnings = []

        # 验证物理模型
        if plan.physics_model is None:
            errors.append("Physics model not specified")
        else:
            # 验证湍流模型选择
            if plan.physics_model.flow_type == FlowType.TURBULENT:
                if plan.physics_model.turbulence_model is None:
                    warnings.append("Turbulent flow without turbulence model")

            # 验证可压缩性处理
            if plan.physics_model.compressibility != Compressibility.INCOMPRESSIBLE:
                if plan.physics_model.time_treatment == TimeTreatment.STEADY:
                    # 可压缩稳态流需要特殊处理
                    if plan.physics_model.compressibility == Compressibility.LOW_MACH:
                        # 低马赫数可以用 buoyant 系列
                        pass
                    else:
                        warnings.append("Compressible steady-state may have convergence issues")

            # 验证重力
            if plan.physics_model.gravity and not plan.physics_model.energy_model:
                errors.append("Gravity requires energy model (buoyancy)")

        # 验证边界条件
        if plan.boundary_conditions:
            valid, bc_errors, bc_warnings = validate_boundary_conditions(
                plan.problem_type,
                plan.boundary_conditions,
            )
            errors.extend(bc_errors)
            warnings.extend(bc_warnings)

        # 验证收敛标准
        if not plan.convergence_criteria:
            warnings.append("No convergence criteria specified, using defaults")

        return len(errors) == 0, errors, warnings

    def _infer_problem_type(
        self,
        spec: Dict[str, Any],
    ) -> Optional[ProblemType]:
        """从规范推断问题类型"""
        # 检查规范中的关键信息
        content = spec.get("content", {})

        # 检查是否是外部流动
        if "freestream" in content.get("boundary_conditions", {}):
            return ProblemType.EXTERNAL_FLOW

        # 检查是否是传热问题
        if "temperature" in content or "T_" in content.get("fields", []):
            if "buoyancy" in content.get("physics", {}):
                return ProblemType.HEAT_TRANSFER_NATURAL
            else:
                return ProblemType.HEAT_TRANSFER_FORCED

        # 检查是否是多相
        if "VOF" in content or "multiphase" in content:
            return ProblemType.MULTIPHASE

        return ProblemType.INTERNAL_FLOW

    def _infer_physics_model(
        self,
        spec: Dict[str, Any],
        problem_type: ProblemType,
    ) -> Optional[PhysicsModel]:
        """从规范推断物理模型"""
        # 尝试从规范中提取物理参数
        physics = spec.get("physics", {})
        solver = spec.get("solver_settings", {})

        # 雷诺数
        reynolds = physics.get("Re", solver.get("Re", 4000))
        mach = physics.get("Ma", solver.get("Ma", 0))

        return infer_physics_from_params(
            reynolds=reynolds,
            mach=mach,
            has_gravity=physics.get("gravity", False),
            has_heat_transfer="T_" in solver.get("fields", []),
        )

    def _classify_problem_type(
        self,
        reynolds: float,
        mach: float,
        has_gravity: bool,
        has_heat_transfer: bool,
        geometry_type: str,
    ) -> ProblemType:
        """分类问题类型"""
        if has_heat_transfer:
            if has_gravity:
                return ProblemType.HEAT_TRANSFER_NATURAL
            else:
                return ProblemType.HEAT_TRANSFER_FORCED

        if geometry_type == "external":
            return ProblemType.EXTERNAL_FLOW

        if mach > 0.3:
            return ProblemType.EXTERNAL_FLOW

        return ProblemType.INTERNAL_FLOW

    def _get_default_bcs(
        self,
        problem_type: ProblemType,
    ) -> List[BoundaryCondition]:
        """获取默认边界条件"""
        bcs = []

        if problem_type == ProblemType.INTERNAL_FLOW:
            bcs = [
                BoundaryCondition(
                    name="inlet",
                    type=BCType.INLET_VELOCITY,
                    values={"U": "(10 0 0)", "p": 0},
                ),
                BoundaryCondition(
                    name="outlet",
                    type=BCType.OUTLET_PRESSURE,
                    values={"p": 0},
                ),
                BoundaryCondition(
                    name="walls",
                    type=BCType.WALL_NO_SLIP,
                ),
            ]

        elif problem_type == ProblemType.EXTERNAL_FLOW:
            bcs = [
                BoundaryCondition(
                    name="inlet",
                    type=BCType.INLET_VELOCITY,
                    values={"U": "(10 0 0)", "p": 0},
                ),
                BoundaryCondition(
                    name="freestream",
                    type=BCType.FREESTREAM,
                    values={"UInf": "(10 0 0)", "pInf": 0},
                ),
                BoundaryCondition(
                    name="walls",
                    type=BCType.WALL_NO_SLIP,
                ),
            ]

        elif problem_type == ProblemType.HEAT_TRANSFER_NATURAL:
            bcs = [
                BoundaryCondition(
                    name="walls",
                    type=BCType.WALL_NO_SLIP,
                    values={"T": "300", "q": 0},
                ),
                BoundaryCondition(
                    name="walls",
                    type=BCType.WALL_ADIABATIC,
                ),
            ]

        return bcs

    def _extract_boundary_conditions(
        self,
        spec: Dict[str, Any],
    ) -> List[BoundaryCondition]:
        """从规范提取边界条件"""
        bcs = []
        bc_data = spec.get("boundary_conditions", {})

        for name, bc_info in bc_data.items():
            # 推断 BC 类型
            bc_type = self._infer_bc_type(bc_info)
            if bc_type:
                bcs.append(BoundaryCondition(
                    name=name,
                    type=bc_type,
                    values=bc_info,
                ))

        return bcs

    def _infer_bc_type(self, bc_info: Dict[str, Any]) -> Optional[BCType]:
        """推断边界条件类型"""
        info_lower = str(bc_info).lower()

        if "velocity" in info_lower:
            return BCType.INLET_VELOCITY
        elif "pressure" in info_lower:
            if "inlet" in info_lower or "total" in info_lower:
                return BCType.INLET_TOTAL_PRESSURE
            else:
                return BCType.OUTLET_PRESSURE
        elif "wall" in info_lower:
            if "slip" in info_lower:
                return BCType.WALL_SLIP
            else:
                return BCType.WALL_NO_SLIP
        elif "symmetry" in info_lower:
            return BCType.SYMMETRY

        return None


# ============================================================================
# Convenience Functions
# ============================================================================

def plan_from_case(
    reynolds: float,
    mach: float = 0,
    has_gravity: bool = False,
    has_heat_transfer: bool = False,
) -> PhysicsPlan:
    """
    便捷函数：从 case 参数生成物理规划

    Args:
        reynolds: 雷诺数
        mach: 马赫数
        has_gravity: 是否有重力
        has_heat_transfer: 是否有传热

    Returns:
        物理规划
    """
    planner = PhysicsPlanner()
    return planner.plan_from_case_params(
        reynolds, mach, has_gravity, has_heat_transfer
    )


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "PhysicsPlanner",
    "plan_from_case",
]
