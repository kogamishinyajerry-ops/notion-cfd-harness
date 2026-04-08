#!/usr/bin/env python3
"""
Phase 3 ↔ Phase 2 Type Adapter

桥接 Phase 3 简化类型（string/bool/dict）和 Phase 2 强类型（enum/dataclass），
让 Phase 3 组件可以复用 Phase 2 执行层逻辑。

转换方向:
- P3 → P2: Phase 3 参数传入 Phase 2 函数前转换
- P2 → P3: Phase 2 结果返回 Phase 3 调用方时转换
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

# Phase 2 imports (强类型)
from knowledge_compiler.phase2.execution_layer.schema import (
    BCType,
    Compressibility,
    ConvergenceCriterion,
    ConvergenceType,
    FlowType,
    PhysicsModel as P2PhysicsModel,
    PhysicsPlan as P2PhysicsPlan,
    ProblemType as P2ProblemType,
    SolverType as P2SolverType,
    TimeTreatment,
    TurbulenceModel,
    BoundaryCondition as P2BoundaryCondition,
    select_solver_by_matrix,
    get_default_convergence_criteria,
)

# Phase 2 CAD parser imports
from knowledge_compiler.phase2.execution_layer.cad_parser import (
    BoundingBox as P2CadBoundingBox,
    GeometryFeature as P2GeometryFeature,
    GeometryFormat as P2GeometryFormat,
    ParsedGeometry as P2ParsedGeometry,
)

# Phase 3 imports (简化类型)
from knowledge_compiler.phase3.schema import (
    BoundaryCondition as P3BoundaryCondition,
    GeometryFeature as P3GeometryFeature,
    MeshFormat,
    ParsedGeometry as P3ParsedGeometry,
    PhysicsModel as P3PhysicsModel,
    PhysicsPlan as P3PhysicsPlan,
    SolverType as P3SolverType,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Phase 3 → Phase 2 转换
# ============================================================================

# --- 映射表 ---

_FLOW_TYPE_MAP: Dict[str, FlowType] = {
    "laminar": FlowType.LAMINAR,
    "turbulent": FlowType.TURBULENT,
    "transitional": FlowType.TRANSITIONAL,
}

_TURBULENCE_MODEL_MAP: Dict[str, TurbulenceModel] = {
    "kEpsilon": TurbulenceModel.K_EPSILON,
    "kOmegaSST": TurbulenceModel.K_OMEGA_SST,
    "SpalartAllmaras": TurbulenceModel.SPALART_ALLMARAS,
    "LES": TurbulenceModel.LES,
    "DES": TurbulenceModel.DES,
    "none": TurbulenceModel.NONE,
}

_COMPRESSIBILITY_MAP: Dict[str, Compressibility] = {
    "incompressible": Compressibility.INCOMPRESSIBLE,
    "compressible": Compressibility.COMPRESSIBLE,
    "low_mach": Compressibility.LOW_MACH,
}

_BC_TYPE_MAP: Dict[str, BCType] = {
    "noSlip": BCType.WALL_NO_SLIP,
    "slip": BCType.WALL_SLIP,
    "movingWall": BCType.WALL_MOVING,
    "fixedValue": BCType.INLET_VELOCITY,
    "zeroGradient": BCType.OUTLET_ZERO_GRADIENT,
    "freestream": BCType.FREESTREAM,
    "symmetry": BCType.SYMMETRY,
    "cyclic": BCType.CYCLIC,
    "empty": BCType.EMPTY,
    "wall": BCType.WALL_NO_SLIP,
    "inlet": BCType.INLET_VELOCITY,
    "outlet": BCType.OUTLET_PRESSURE,
}

_PROBLEM_TYPE_MAP: Dict[str, P2ProblemType] = {
    "internal_flow": P2ProblemType.INTERNAL_FLOW,
    "external_flow": P2ProblemType.EXTERNAL_FLOW,
    "heat_transfer": P2ProblemType.HEAT_TRANSFER,
    "multiphase": P2ProblemType.MULTIPHASE,
    "fsi": P2ProblemType.FSI,
    "compressible": P2ProblemType.INTERNAL_FLOW,  # closest match
}

_SOLVER_TYPE_P3_TO_P2: Dict[P3SolverType, P2SolverType] = {
    P3SolverType.OPENFOAM: P2SolverType.SIMPLE_FOAM,
    P3SolverType.SU2: P2SolverType.SU2_CFD,
    P3SolverType.STARCCM: P2SolverType.SIMPLE_FOAM,  # fallback
    P3SolverType.FLUENT: P2SolverType.SIMPLE_FOAM,  # fallback
}

# --- 转换函数 ---

def flow_type_to_p2(flow_type: str) -> FlowType:
    """Phase 3 flow_type string → Phase 2 FlowType enum"""
    result = _FLOW_TYPE_MAP.get(flow_type)
    if result is None:
        logger.warning("未知 flow_type: %s, 默认 TURBULENT", flow_type)
        return FlowType.TURBULENT
    return result


def turbulence_model_to_p2(model: str) -> TurbulenceModel:
    """Phase 3 turbulence_model string → Phase 2 TurbulenceModel enum"""
    result = _TURBULENCE_MODEL_MAP.get(model)
    if result is None:
        logger.warning("未知 turbulence_model: %s, 默认 K_OMEGA_SST", model)
        return TurbulenceModel.K_OMEGA_SST
    return result


def time_treatment_to_p2(steady_state: bool) -> TimeTreatment:
    """Phase 3 steady_state bool → Phase 2 TimeTreatment enum"""
    return TimeTreatment.STEADY if steady_state else TimeTreatment.TRANSIENT


def compressibility_to_p2(comp: str) -> Compressibility:
    """Phase 3 compressibility string → Phase 2 Compressibility enum"""
    result = _COMPRESSIBILITY_MAP.get(comp)
    if result is None:
        return Compressibility.INCOMPRESSIBLE
    return result


def problem_type_to_p2(ptype: str) -> P2ProblemType:
    """Phase 3 problem_type string → Phase 2 ProblemType enum"""
    result = _PROBLEM_TYPE_MAP.get(ptype)
    if result is None:
        return P2ProblemType.INTERNAL_FLOW
    return result


def bc_type_to_p2(bc_type: str) -> BCType:
    """Phase 3 BC type string → Phase 2 BCType enum"""
    result = _BC_TYPE_MAP.get(bc_type)
    if result is None:
        return BCType.WALL_NO_SLIP
    return result


def solver_type_p3_to_p2(st: P3SolverType) -> P2SolverType:
    """Phase 3 SolverType (category) → Phase 2 SolverType (specific)"""
    return _SOLVER_TYPE_P3_TO_P2.get(st, P2SolverType.SIMPLE_FOAM)


# ============================================================================
# Phase 2 → Phase 3 转换
# ============================================================================

_FLOW_TYPE_TO_P3: Dict[FlowType, str] = {v: k for k, v in _FLOW_TYPE_MAP.items()}
_TURBULENCE_MODEL_TO_P3: Dict[TurbulenceModel, str] = {v: k for k, v in _TURBULENCE_MODEL_MAP.items()}
_COMPRESSIBILITY_TO_P3: Dict[Compressibility, str] = {v: k for k, v in _COMPRESSIBILITY_MAP.items()}

# Phase 2 具体求解器 → Phase 3 求解器类别
_SOLVER_TYPE_P2_TO_P3: Dict[P2SolverType, P3SolverType] = {}
for p2_st in P2SolverType:
    if p2_st == P2SolverType.SU2_CFD:
        _SOLVER_TYPE_P2_TO_P3[p2_st] = P3SolverType.SU2
    else:
        _SOLVER_TYPE_P2_TO_P3[p2_st] = P3SolverType.OPENFOAM

_BC_TYPE_TO_P3: Dict[BCType, str] = {
    BCType.WALL_NO_SLIP: "noSlip",
    BCType.WALL_SLIP: "slip",
    BCType.WALL_MOVING: "movingWall",
    BCType.WALL_ROUGH: "noSlip",
    BCType.WALL_ADIABATIC: "zeroGradient",
    BCType.WALL_ISOTHERMAL: "fixedValue",
    BCType.INLET_VELOCITY: "fixedValue",
    BCType.INLET_MASS_FLOW: "fixedValue",
    BCType.INLET_PRESSURE: "fixedValue",
    BCType.INLET_TOTAL_PRESSURE: "fixedValue",
    BCType.OUTLET_PRESSURE: "fixedValue",
    BCType.OUTLET_ZERO_GRADIENT: "zeroGradient",
    BCType.OUTLET_OUTFLOW: "zeroGradient",
    BCType.SYMMETRY: "symmetry",
    BCType.CYCLIC: "cyclic",
    BCType.WEDGE: "wedge",
    BCType.EMPTY: "empty",
    BCType.FREESTREAM: "freestream",
    BCType.INTERFACE: "interface",
}

_PROBLEM_TYPE_TO_P3: Dict[P2ProblemType, str] = {}
for p2_pt in P2ProblemType:
    # 二级细分映射到一级
    val = p2_pt.value
    if val.startswith("internal_flow"):
        _PROBLEM_TYPE_TO_P3[p2_pt] = "internal_flow"
    elif val.startswith("external_flow"):
        _PROBLEM_TYPE_TO_P3[p2_pt] = "external_flow"
    elif val.startswith("heat_transfer"):
        _PROBLEM_TYPE_TO_P3[p2_pt] = "heat_transfer"
    elif val == "multiphase":
        _PROBLEM_TYPE_TO_P3[p2_pt] = "multiphase"
    elif val == "fsi":
        _PROBLEM_TYPE_TO_P3[p2_pt] = "fsi"
    else:
        _PROBLEM_TYPE_TO_P3[p2_pt] = "internal_flow"


def flow_type_to_p3(ft: FlowType) -> str:
    """Phase 2 FlowType enum → Phase 3 string"""
    return _FLOW_TYPE_TO_P3.get(ft, "turbulent")


def turbulence_model_to_p3(tm: TurbulenceModel) -> str:
    """Phase 2 TurbulenceModel enum → Phase 3 string"""
    return _TURBULENCE_MODEL_TO_P3.get(tm, "kOmegaSST")


def solver_type_to_p3(st: P2SolverType) -> P3SolverType:
    """Phase 2 SolverType (specific) → Phase 3 SolverType (category)"""
    return _SOLVER_TYPE_P2_TO_P3.get(st, P3SolverType.OPENFOAM)


def bc_type_to_p3(bc: BCType) -> str:
    """Phase 2 BCType enum → Phase 3 string"""
    return _BC_TYPE_TO_P3.get(bc, "noSlip")


def problem_type_to_p3(pt: P2ProblemType) -> str:
    """Phase 2 ProblemType enum → Phase 3 string"""
    return _PROBLEM_TYPE_TO_P3.get(pt, "internal_flow")


def bounding_box_to_p3(bb: P2CadBoundingBox) -> Dict[str, float]:
    """Phase 2 BoundingBox dataclass → Phase 3 Dict"""
    return {
        "x_min": bb.min_x,
        "x_max": bb.max_x,
        "y_min": bb.min_y,
        "y_max": bb.max_y,
        "z_min": bb.min_z,
        "z_max": bb.max_z,
        "size_x": bb.length,
        "size_y": bb.width,
        "size_z": bb.height,
    }


def convergence_to_p3(criteria: List[ConvergenceCriterion]) -> Dict[str, float]:
    """Phase 2 ConvergenceCriterion list → Phase 3 Dict[str, float]

    Phase 3 使用 "residual_u", "residual_p" 等键名。
    """
    result: Dict[str, float] = {}
    for c in criteria:
        # Phase 2 的 "p" → Phase 3 的 "residual_p"
        name = c.name
        if name in ("p", "U", "k", "omega", "T", "epsilon", "nut"):
            result[f"residual_{name.lower()}"] = c.target_value
        else:
            result[name] = c.target_value
    return result


def p2_bc_to_p3(bc: P2BoundaryCondition) -> P3BoundaryCondition:
    """Phase 2 BoundaryCondition → Phase 3 BoundaryCondition"""
    return P3BoundaryCondition(
        name=bc.name,
        type=bc_type_to_p3(bc.type),
        values=bc.values,
    )


def p3_bc_to_p2(bc: P3BoundaryCondition) -> P2BoundaryCondition:
    """Phase 3 BoundaryCondition → Phase 2 BoundaryCondition"""
    return P2BoundaryCondition(
        name=bc.name,
        type=bc_type_to_p2(bc.type),
        values=bc.values,
    )


def p2_physics_model_to_p3(model: P2PhysicsModel) -> P3PhysicsModel:
    """Phase 2 PhysicsModel → Phase 3 PhysicsModel"""
    return P3PhysicsModel(
        solver_type=solver_type_to_p3(model.solver_type),
        flow_type=flow_type_to_p3(model.flow_type),
        turbulence_model=turbulence_model_to_p3(model.turbulence_model) if model.turbulence_model else "none",
        energy_model=model.energy_model,
        species_model=model.species_model,
        multiphase_model=model.multiphase_model,
    )


def p2_physics_plan_to_p3(plan: P2PhysicsPlan) -> P3PhysicsPlan:
    """Phase 2 PhysicsPlan → Phase 3 PhysicsPlan"""
    return P3PhysicsPlan(
        plan_id=plan.plan_id,
        problem_type=problem_type_to_p3(plan.problem_type) if isinstance(plan.problem_type, P2ProblemType) else str(plan.problem_type),
        physics_model=p2_physics_model_to_p3(plan.physics_model) if plan.physics_model else None,
        recommended_solver=solver_type_to_p3(plan.recommended_solver) if plan.recommended_solver else None,
        boundary_conditions=[p2_bc_to_p3(bc) for bc in plan.boundary_conditions],
        solver_settings=plan.solver_settings,
        convergence_criteria=convergence_to_p3(plan.convergence_criteria),
    )


# Phase 2 GeometryFormat → Phase 3 MeshFormat
_GEO_FORMAT_TO_MESH_FORMAT = {
    P2GeometryFormat.STL: MeshFormat.STL,
    P2GeometryFormat.OBJ: MeshFormat.OBJ,
    P2GeometryFormat.STEP: MeshFormat.STEP,
    P2GeometryFormat.STP: MeshFormat.STEP,
    P2GeometryFormat.UNKNOWN: MeshFormat.STL,
}


def p2_parsed_geometry_to_p3(geom: P2ParsedGeometry) -> P3ParsedGeometry:
    """Phase 2 ParsedGeometry → Phase 3 ParsedGeometry"""
    # 转换格式
    mesh_fmt = _GEO_FORMAT_TO_MESH_FORMAT.get(geom.format, MeshFormat.STL)

    # 转换边界盒
    bbox = bounding_box_to_p3(geom.bounding_box) if geom.bounding_box else None

    # 转换特征
    features = []
    for f in geom.features:
        features.append(P3GeometryFeature(
            type=f.feature_type,
            name=f.name,
            properties=f.properties,
        ))

    return P3ParsedGeometry(
        source_file=geom.source_file,
        format=mesh_fmt,
        features=features,
        bounding_box=bbox,
        surface_area=geom.surface_area,
        volume=geom.volume,
        is_watertight=geom.is_valid,
        repair_needed=[geom.error_message] if geom.error_message else [],
    )


# ============================================================================
# 便捷函数：直接委托 Phase 2 逻辑
# ============================================================================

def select_solver_p2(
    compressibility: str = "incompressible",
    steady_state: bool = True,
    is_multiphase: bool = False,
    custom_solver: Optional[P3SolverType] = None,
) -> P3SolverType:
    """使用 Phase 2 的求解器选择矩阵，返回 Phase 3 SolverType"""
    p2_solver = select_solver_by_matrix(
        compressibility=compressibility_to_p2(compressibility),
        time_treatment=time_treatment_to_p2(steady_state),
        is_multiphase=is_multiphase,
        solver_type=solver_type_p3_to_p2(custom_solver) if custom_solver else None,
    )
    return solver_type_to_p3(p2_solver)


def get_convergence_criteria_p2(problem_type: str) -> Dict[str, float]:
    """使用 Phase 2 的默认收敛标准，返回 Phase 3 Dict"""
    p2_type = problem_type_to_p2(problem_type)
    criteria = get_default_convergence_criteria(p2_type)
    return convergence_to_p3(criteria)
