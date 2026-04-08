#!/usr/bin/env python3
"""
Phase 3: Physics Planner

基于几何特征和问题描述，自动规划物理模型、求解器选择和边界条件。

核心组件:
- PhysicsPlanner: 物理规划器
- BatchPhysicsPlanner: 批量规划器
- 便捷函数: create_physics_plan, plan_from_geometry
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from knowledge_compiler.phase3.schema import (
    BoundaryCondition,
    MeshFormat,
    PhysicsModel,
    PhysicsPlan,
    SolverType,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 规则定义
# ============================================================================

# 流动类型 → 默认湍流模型
_TURBULENCE_MODEL_MAP = {
    "turbulent": "kOmegaSST",
    "transitional": "kOmegaSST",
    "laminar": "none",
}

# 问题类型 → 求解器推荐
_SOLVER_RECOMMENDATIONS = {
    "internal_flow": {
        "incompressible": ("simpleFoam", SolverType.OPENFOAM),
        "compressible": ("rhoSimpleFoam", SolverType.OPENFOAM),
        "transient": ("pimpleFoam", SolverType.OPENFOAM),
    },
    "external_flow": {
        "incompressible": ("simpleFoam", SolverType.OPENFOAM),
        "compressible": ("rhoSimpleFoam", SolverType.OPENFOAM),
        "transient": ("pimpleFoam", SolverType.OPENFOAM),
    },
    "heat_transfer": {
        "conjugate": ("chtMultiRegionFoam", SolverType.OPENFOAM),
        "single_region": ("buoyantSimpleFoam", SolverType.OPENFOAM),
    },
    "multiphase": {
        "voi": ("interFoam", SolverType.OPENFOAM),
        "eulerian": ("multiphaseEulerFoam", SolverType.OPENFOAM),
    },
    "compressible": {
        "steady": ("rhoSimpleFoam", SolverType.OPENFOAM),
        "transient": ("rhoPimpleFoam", SolverType.OPENFOAM),
    },
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

# 收敛标准默认值
_DEFAULT_CONVERGENCE = {
    "residual_u": 1e-5,
    "residual_p": 1e-5,
    "residual_k": 1e-5,
    "residual_omega": 1e-5,
    "residual_energy": 1e-6,
}


# ============================================================================
# PhysicsPlanner: 主规划器
# ============================================================================

class PhysicsPlanner:
    """物理模型规划器

    根据几何特征、问题描述和历史知识，
    推荐物理模型、求解器和边界条件。

    规划策略:
    1. 分析问题描述 → 推断问题类型
    2. 基于问题类型 → 选择求解器
    3. 基于流动特征 → 选择湍流模型
    4. 生成默认边界条件
    5. 设置收敛标准
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
        # 1. 推断问题类型
        problem_type = self._classify_problem(
            problem_description, geometry_features
        )
        logger.info("推断问题类型: %s", problem_type)

        # 2. 推荐求解器
        if custom_solver:
            solver_type = custom_solver
        else:
            solver_type = self._recommend_solver(
                problem_type, compressibility, steady_state
            )
        solver_name = self._get_solver_name(
            problem_type, compressibility, steady_state
        )
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

        # 5. 生成边界条件
        boundary_conditions = self._generate_boundary_conditions(
            problem_type, geometry_features
        )

        # 6. 设置收敛标准
        convergence = dict(_DEFAULT_CONVERGENCE)
        if not energy:
            convergence.pop("residual_energy", None)

        # 7. 求解器设置
        solver_settings = self._generate_solver_settings(
            problem_type, steady_state, turbulence_model
        )

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
        """推断问题类型"""
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

    def _recommend_solver(
        self,
        problem_type: str,
        compressibility: str,
        steady_state: bool,
    ) -> SolverType:
        """推荐求解器类型"""
        type_map = _SOLVER_RECOMMENDATIONS.get(problem_type, {})

        if compressibility == "compressible" and "compressible" in type_map:
            return type_map["compressible"][1]

        if not steady_state and "transient" in type_map:
            return type_map["transient"][1]

        key = compressibility if compressibility in type_map else "incompressible"
        return type_map.get(key, ("simpleFoam", SolverType.OPENFOAM))[1]

    def _get_solver_name(
        self,
        problem_type: str,
        compressibility: str,
        steady_state: bool,
    ) -> str:
        """获取求解器名称"""
        type_map = _SOLVER_RECOMMENDATIONS.get(problem_type, {})

        if not steady_state and "transient" in type_map:
            return type_map["transient"][0]
        if compressibility == "compressible" and "compressible" in type_map:
            return type_map["compressible"][0]

        key = compressibility if compressibility in type_map else "incompressible"
        return type_map.get(key, ("simpleFoam", SolverType.OPENFOAM))[0]

    def _generate_boundary_conditions(
        self,
        problem_type: str,
        geometry_features: Optional[Dict[str, Any]],
    ) -> List[BoundaryCondition]:
        """生成默认边界条件

        基于问题类型生成典型边界条件模板。
        """
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
