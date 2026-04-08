#!/usr/bin/env python3
"""
Phase 3: Physics Planner

基于几何特征和问题描述，自动规划物理模型、求解器选择和边界条件。

复用策略:
- 求解器选择: 委托 Phase 2 的 select_solver_by_matrix()
- 收敛标准: 委托 Phase 2 的 get_default_convergence_criteria()
- Phase 3 特有: 关键词分类、BC 模板、BC 矛盾检测、批量规划

核心组件:
- PhysicsPlanner: 物理规划器
- BatchPhysicsPlanner: 批量规划器
- 便捷函数: create_physics_plan, plan_from_geometry
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from knowledge_compiler.phase2.execution_layer.schema import (
    select_solver_by_matrix as _p2_select_solver,
    get_default_convergence_criteria as _p2_get_convergence,
    SolverType as P2SolverType,
    Compressibility as P2Compressibility,
    TimeTreatment as P2TimeTreatment,
    ProblemType as P2ProblemType,
)
from knowledge_compiler.phase3.adapter import (
    compressibility_to_p2,
    convergence_to_p3,
    problem_type_to_p2,
    solver_type_to_p3,
    time_treatment_to_p2,
)
from knowledge_compiler.phase3.schema import (
    BoundaryCondition,
    PhysicsModel,
    PhysicsPlan,
    SolverType,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Phase 3 特有规则（Phase 2 没有的）
# ============================================================================

# 流动类型 → 默认湍流模型
_TURBULENCE_MODEL_MAP = {
    "turbulent": "kOmegaSST",
    "transitional": "kOmegaSST",
    "laminar": "none",
}

# 关键词 → 问题类型映射
_PROBLEM_TYPE_KEYWORDS = {
    "internal_flow": [
        "pipe", "duct", "channel", "nozzle", "diffuser",
        "valve", "internal", "内流", "管道", "通道",
    ],
    "external_flow": [
        "airfoil", "wing", "blade", "vehicle", "building",
        "external", "aerodynamic", "外流", "翼型", "翼",
    ],
    "heat_transfer": [
        "heat", "thermal", "conjugate", "cooling", "heating",
        "temperature", "传热", "热", "冷却", "加热",
    ],
    "multiphase": [
        "multiphase", "free surface", "cavitation", "boiling",
        "多相", "自由面", "空化",
    ],
    "compressible": [
        "compressible", "supersonic", "transonic", "shock",
        "mach", "可压", "超音速", "跨音速",
    ],
}


# ============================================================================
# PhysicsPlanner: 主规划器
# ============================================================================

class PhysicsPlanner:
    """物理模型规划器

    根据几何特征、问题描述和历史知识，
    推荐物理模型、求解器和边界条件。

    规划策略:
    1. 分析问题描述 → 推断问题类型（Phase 3 特有）
    2. 基于压缩性×时间 → 选择求解器（委托 Phase 2 矩阵）
    3. 基于流动特征 → 选择湍流模型（Phase 3）
    4. 生成默认边界条件（Phase 3 模板）
    5. 设置收敛标准（委托 Phase 2 + Phase 3 能量扩展）
    """

    def __init__(
        self,
        knowledge_store: Optional[Any] = None,
        custom_classifier: Optional[Callable[[str], str]] = None,
    ):
        self._store = knowledge_store
        self._classifier = custom_classifier

    def plan(
        self,
        problem_description: str = "",
        geometry_features: Optional[Dict[str, Any]] = None,
        flow_type: str = "turbulent",
        compressibility: str = "incompressible",
        steady_state: bool = True,
        energy: bool = False,
        custom_solver: Optional[SolverType] = None,
    ) -> PhysicsPlan:
        """生成物理规划方案

        Args:
            problem_description: 问题描述文本
            geometry_features: 几何特征字典
            flow_type: 流动类型 (laminar/turbulent/transitional)
            compressibility: 压缩性 (incompressible/compressible)
            steady_state: 是否稳态
            energy: 是否包含能量方程
            custom_solver: 指定求解器类型（覆盖推荐）

        Returns:
            PhysicsPlan 物理规划方案
        """
        # 1. 推断问题类型（Phase 3 特有逻辑）
        problem_type = self._classify_problem(
            problem_description, geometry_features
        )
        logger.info("推断问题类型: %s", problem_type)

        # 2. 推荐求解器（委托 Phase 2 二维决策矩阵）
        if custom_solver:
            solver_type = custom_solver
            solver_name = custom_solver.value
        else:
            p2_solver = _p2_select_solver(
                compressibility=compressibility_to_p2(compressibility),
                time_treatment=time_treatment_to_p2(steady_state),
                is_multiphase=(problem_type == "multiphase"),
            )
            solver_type = solver_type_to_p3(p2_solver)
            solver_name = p2_solver.value
        logger.info("推荐求解器: %s (%s)", solver_name, solver_type.value)

        # 3. 选择湍流模型
        turbulence_model = _TURBULENCE_MODEL_MAP.get(flow_type, "kOmegaSST")

        # 4. 构建物理模型
        physics_model = PhysicsModel(
            solver_type=solver_type,
            flow_type=flow_type,
            turbulence_model=turbulence_model,
            energy_model=energy,
            species_model=False,
            multiphase_model=problem_type == "multiphase",
        )

        # 5. 生成边界条件（Phase 3 特有模板）
        boundary_conditions = self._generate_boundary_conditions(
            problem_type, geometry_features
        )

        # 6. 设置收敛标准（委托 Phase 2 + Phase 3 能量扩展）
        p2_problem_type = problem_type_to_p2(problem_type)
        p2_criteria = _p2_get_convergence(p2_problem_type)
        convergence = convergence_to_p3(p2_criteria)
        if energy:
            convergence["residual_energy"] = 1e-6

        # 7. 求解器设置
        solver_settings = self._generate_solver_settings(
            problem_type, steady_state, turbulence_model
        )

        # 验证边界条件组合的物理合理性
        bc_warnings = validate_bc_compatibility(boundary_conditions)
        if bc_warnings:
            logger.warning("BC 矛盾检测: %s", "; ".join(bc_warnings))

        return PhysicsPlan(
            problem_type=problem_type,
            physics_model=physics_model,
            recommended_solver=solver_type,
            boundary_conditions=boundary_conditions,
            solver_settings=solver_settings,
            convergence_criteria=convergence,
        )

    def _classify_problem(
        self,
        description: str,
        geometry_features: Optional[Dict[str, Any]],
    ) -> str:
        """推断问题类型（Phase 3 特有：关键词+几何特征推断）"""
        if self._classifier:
            return self._classifier(description)

        # 基于关键词匹配
        desc_lower = description.lower()
        scores: Dict[str, int] = {}

        for ptype, keywords in _PROBLEM_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in desc_lower)
            if score > 0:
                scores[ptype] = score

        if scores:
            return max(scores, key=scores.get)  # type: ignore[arg-type]

        # 基于几何特征推断
        if geometry_features:
            geom_type = geometry_features.get("type", "")
            if geom_type in ("pipe", "duct", "channel"):
                return "internal_flow"
            if geom_type in ("airfoil", "wing", "blade"):
                return "external_flow"

        return "internal_flow"  # 默认

    def _generate_boundary_conditions(
        self,
        problem_type: str,
        geometry_features: Optional[Dict[str, Any]],
    ) -> List[BoundaryCondition]:
        """生成默认边界条件（Phase 3 特有模板）"""
        conditions = []

        if problem_type == "internal_flow":
            conditions = [
                BoundaryCondition(
                    name="inlet",
                    type="fixedValue",
                    values={"U": "uniform (1 0 0)"},
                ),
                BoundaryCondition(
                    name="outlet",
                    type="zeroGradient",
                    values={},
                ),
                BoundaryCondition(
                    name="walls",
                    type="noSlip",
                    values={},
                ),
            ]
        elif problem_type == "external_flow":
            conditions = [
                BoundaryCondition(
                    name="farfield",
                    type="freestream",
                    values={"U": "uniform (50 0 0)", "p": "uniform 0"},
                ),
                BoundaryCondition(
                    name="body",
                    type="noSlip",
                    values={},
                ),
            ]
        elif problem_type == "heat_transfer":
            conditions = [
                BoundaryCondition(
                    name="inlet",
                    type="fixedValue",
                    values={"U": "uniform (1 0 0)", "T": "uniform 300"},
                ),
                BoundaryCondition(
                    name="outlet",
                    type="zeroGradient",
                    values={},
                ),
                BoundaryCondition(
                    name="hot_wall",
                    type="fixedValue",
                    values={"T": "uniform 400"},
                ),
                BoundaryCondition(
                    name="adiabatic_walls",
                    type="zeroGradient",
                    values={"T": ""},
                ),
            ]
        else:
            # 通用默认
            conditions = [
                BoundaryCondition(
                    name="inlet",
                    type="fixedValue",
                    values={"U": "uniform (1 0 0)"},
                ),
                BoundaryCondition(
                    name="outlet",
                    type="zeroGradient",
                    values={},
                ),
            ]

        return conditions

    def _generate_solver_settings(
        self,
        problem_type: str,
        steady_state: bool,
        turbulence_model: str,
    ) -> Dict[str, Any]:
        """生成求解器设置"""
        settings: Dict[str, Any] = {
            "turbulence_model": turbulence_model,
            "steady_state": steady_state,
        }

        if steady_state:
            settings["n_correctors"] = 2
            settings["n_non_orthogonal_correctors"] = 1
            settings["relaxation_factors"] = {
                "U": 0.7,
                "p": 0.3,
                "k": 0.7,
                "omega": 0.7,
            }
        else:
            settings["delta_t"] = 0.001
            settings["max_co"] = 0.5
            settings["n_correctors"] = 3

        if problem_type == "multiphase":
            settings["n_alpha_correctors"] = 2
            settings["alpha_relax"] = 0.5

        return settings


# ============================================================================
# BatchPhysicsPlanner
# ============================================================================

class BatchPhysicsPlanner:
    """批量物理规划器

    对多组输入参数批量生成物理规划方案。
    """

    def __init__(self, knowledge_store: Optional[Any] = None):
        self._planner = PhysicsPlanner(knowledge_store=knowledge_store)

    def plan_batch(
        self,
        configs: List[Dict[str, Any]],
    ) -> List[PhysicsPlan]:
        """批量生成规划方案

        Args:
            configs: 配置字典列表，每个字典传递给 planner.plan()

        Returns:
            规划方案列表
        """
        plans = []
        for config in configs:
            plan = self._planner.plan(**config)
            plans.append(plan)
        return plans

    def get_summary(self, plans: List[PhysicsPlan]) -> Dict[str, Any]:
        """汇总统计"""
        problem_types = [p.problem_type for p in plans]
        solver_types = [
            p.recommended_solver.value
            for p in plans
            if p.recommended_solver
        ]
        turbulence_models = [
            p.physics_model.turbulence_model
            for p in plans
            if p.physics_model
        ]

        return {
            "total": len(plans),
            "problem_types": list(set(problem_types)),
            "solver_types": list(set(solver_types)),
            "turbulence_models": list(set(turbulence_models)),
            "avg_boundary_conditions": (
                sum(len(p.boundary_conditions) for p in plans) / len(plans)
                if plans else 0.0
            ),
        }


# ============================================================================
# BC Compatibility Validation
# ============================================================================

def validate_bc_compatibility(conditions: List[BoundaryCondition]) -> List[str]:
    """验证边界条件组合的物理合理性

    检查常见矛盾组合，返回警告列表（空=通过）。
    """
    warnings = []
    if not conditions:
        warnings.append("无边界条件")
        return warnings

    types = {bc.type for bc in conditions}
    names = {bc.name.lower() for bc in conditions}

    # 全 wall（无进出口）
    if types == {"noSlip", "wall"} or (len(conditions) > 0 and all(bc.type in ("noSlip", "wall") for bc in conditions)):
        warnings.append("所有边界都是 wall（无进出口），除非有源项否则无物理意义")

    # 无 outlet
    has_inlet = any(n in names for n in ("inlet", "farfield"))
    has_outlet = any(n in names for n in ("outlet", "farfield"))
    if has_inlet and not has_outlet:
        # farfield 同时是 inlet 和 outlet，所以不算
        if "farfield" not in names:
            warnings.append("有 inlet 但无 outlet，质量不守恒")

    # 全 symmetry
    if types == {"symmetry"}:
        warnings.append("全部 symmetry 边界，退化为无边界问题")

    return warnings


# ============================================================================
# Convenience Functions
# ============================================================================

def create_physics_plan(
    problem_type: str = "internal_flow",
    flow_type: str = "turbulent",
    solver_type: SolverType = SolverType.OPENFOAM,
    turbulence_model: str = "kOmegaSST",
    energy: bool = False,
) -> PhysicsPlan:
    """便捷函数：创建物理规划方案"""
    return PhysicsPlan(
        problem_type=problem_type,
        physics_model=PhysicsModel(
            solver_type=solver_type,
            flow_type=flow_type,
            turbulence_model=turbulence_model,
            energy_model=energy,
        ),
        recommended_solver=solver_type,
    )


def plan_from_geometry(
    geometry_info: Dict[str, Any],
    description: str = "",
) -> PhysicsPlan:
    """便捷函数：从几何信息生成规划"""
    planner = PhysicsPlanner()
    return planner.plan(
        problem_description=description,
        geometry_features=geometry_info,
    )
