#!/usr/bin/env python3
"""
Phase 2 Execution Layer Tests: Physics Planner

按照 Opus 4.6 审查要求的测试策略：
- Gold standard case tests（经典验证案例）
- Boundary case tests（边界值测试）
- BC validation tests（边界条件验证）
- Convergence criteria tests（收敛标准测试）
- Default convergence criteria by problem type tests
"""

import pytest

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
    SolverSelectionMatrix,
    select_solver_by_matrix,
    # Validation
    BCCombinationRule,
    BC_VALIDATION_RULES,
    validate_boundary_conditions,
    # Convergence
    is_converged,
    get_default_convergence_criteria,
    # Factory
    create_physics_plan,
    infer_physics_from_params,
)
from knowledge_compiler.phase2.execution_layer.planner import (
    PhysicsPlanner,
    plan_from_case,
)


# ============================================================================
# Test Enums
# ============================================================================

class TestEnums:
    """测试所有枚举类型的完整性"""

    def test_flow_type_values(self):
        """测试 FlowType 枚举值"""
        assert FlowType.LAMINAR.value == "laminar"
        assert FlowType.TURBULENT.value == "turbulent"
        assert FlowType.TRANSITIONAL.value == "transitional"

    def test_turbulence_model_values(self):
        """测试 TurbulenceModel 枚举值"""
        assert TurbulenceModel.K_EPSILON.value == "kEpsilon"
        assert TurbulenceModel.K_OMEGA_SST.value == "kOmegaSST"
        assert TurbulenceModel.SPALART_ALLMARAS.value == "SpalartAllmaras"
        assert TurbulenceModel.LES.value == "LES"
        assert TurbulenceModel.DES.value == "DES"
        assert TurbulenceModel.NONE.value == "none"

    def test_time_treatment_values(self):
        """测试 TimeTreatment 枚举值"""
        assert TimeTreatment.STEADY.value == "steady"
        assert TimeTreatment.TRANSIENT.value == "transient"

    def test_compressibility_values(self):
        """测试 Compressibility 枚举值"""
        assert Compressibility.INCOMPRESSIBLE.value == "incompressible"
        assert Compressibility.COMPRESSIBLE.value == "compressible"
        assert Compressibility.LOW_MACH.value == "low_mach"

    def test_bc_type_comprehensive(self):
        """测试 BCType 枚举完整性（按 Opus 4.6 审查意见扩展）"""
        # 壁面
        assert BCType.WALL_NO_SLIP.value == "wall_no_slip"
        assert BCType.WALL_SLIP.value == "wall_slip"
        assert BCType.WALL_MOVING.value == "wall_moving"
        assert BCType.WALL_ROUGH.value == "wall_rough"
        assert BCType.WALL_ADIABATIC.value == "wall_adiabatic"
        assert BCType.WALL_ISOTHERMAL.value == "wall_isothermal"

        # 入口
        assert BCType.INLET_VELOCITY.value == "inlet_velocity"
        assert BCType.INLET_MASS_FLOW.value == "inlet_mass_flow"
        assert BCType.INLET_PRESSURE.value == "inlet_pressure"
        assert BCType.INLET_TOTAL_PRESSURE.value == "inlet_total_pressure"

        # 出口
        assert BCType.OUTLET_PRESSURE.value == "outlet_pressure"
        assert BCType.OUTLET_ZERO_GRADIENT.value == "outlet_zero_gradient"
        assert BCType.OUTLET_OUTFLOW.value == "outlet_outflow"

        # 对称/周期
        assert BCType.SYMMETRY.value == "symmetry"
        assert BCType.CYCLIC.value == "cyclic"
        assert BCType.WEDGE.value == "wedge"
        assert BCType.EMPTY.value == "empty"

        # 远场
        assert BCType.FREESTREAM.value == "freestream"

        # 特殊
        assert BCType.INTERFACE.value == "interface"

    def test_solver_type_comprehensive(self):
        """测试 SolverType 枚举完整性"""
        assert SolverType.SIMPLE_FOAM.value == "simpleFoam"
        assert SolverType.PIMPLE_FOAM.value == "pimpleFoam"
        assert SolverType.PISO_FOAM.value == "pisoFoam"
        assert SolverType.RHO_SIMPLE_FOAM.value == "rhoSimpleFoam"
        assert SolverType.RHO_PIMPLE_FOAM.value == "rhoPimpleFoam"
        assert SolverType.BUOYANT_SIMPLE_FOAM.value == "buoyantSimpleFoam"
        assert SolverType.BUOYANT_PIMPLE_FOAM.value == "buoyantPimpleFoam"
        assert SolverType.INTER_FOAM.value == "interFoam"
        assert SolverType.INTER_ISOFOAM.value == "interIsoFoam"
        assert SolverType.SRF_SIMPLE_FOAM.value == "SRFSimpleFoam"
        assert SolverType.SU2_CFD.value == "SU2_CFD"

    def test_problem_type_comprehensive(self):
        """测试 ProblemType 枚举完整性（一级+二级分类）"""
        # 一级分类
        assert ProblemType.INTERNAL_FLOW.value == "internal_flow"
        assert ProblemType.EXTERNAL_FLOW.value == "external_flow"
        assert ProblemType.HEAT_TRANSFER.value == "heat_transfer"
        assert ProblemType.MULTIPHASE.value == "multiphase"
        assert ProblemType.FSI.value == "fsi"

        # 二级细分
        assert ProblemType.INTERNAL_FLOW_PIPE.value == "internal_flow_pipe"
        assert ProblemType.INTERNAL_FLOW_CAVITY.value == "internal_flow_cavity"
        assert ProblemType.INTERNAL_FLOW_STEP.value == "internal_flow_step"
        assert ProblemType.EXTERNAL_FLOW_BLUFF_BODY.value == "external_flow_bluff_body"
        assert ProblemType.EXTERNAL_FLOW_AIRFOIL.value == "external_flow_airfoil"
        assert ProblemType.HEAT_TRANSFER_FORCED.value == "heat_transfer_forced"
        assert ProblemType.HEAT_TRANSFER_NATURAL.value == "heat_transfer_natural"
        assert ProblemType.HEAT_TRANSFER_MIXED.value == "heat_transfer_mixed"

    def test_convergence_type_values(self):
        """测试 ConvergenceType 枚举值"""
        assert ConvergenceType.RESIDUAL.value == "residual"
        assert ConvergenceType.FORCE.value == "force"
        assert ConvergenceType.INTEGRAL.value == "integral"
        assert ConvergenceType.MONITOR_POINT.value == "monitor_point"


# ============================================================================
# Test Solver Decision Matrix (2D Matrix: compressibility × time_treatment)
# ============================================================================

class TestSolverDecisionMatrix:
    """测试二维决策矩阵：compressibility × time_treatment → solver"""

    def test_incomp_steady(self):
        """测试不可压缩稳态 → simpleFoam"""
        result = select_solver_by_matrix(
            Compressibility.INCOMPRESSIBLE,
            TimeTreatment.STEADY,
            is_multiphase=False,
        )
        assert result == SolverType.SIMPLE_FOAM

    def test_incomp_transient(self):
        """测试不可压缩瞬态 → pimpleFoam"""
        result = select_solver_by_matrix(
            Compressibility.INCOMPRESSIBLE,
            TimeTreatment.TRANSIENT,
            is_multiphase=False,
        )
        assert result == SolverType.PIMPLE_FOAM

    def test_comp_steady(self):
        """测试可压缩稳态 → rhoSimpleFoam"""
        result = select_solver_by_matrix(
            Compressibility.COMPRESSIBLE,
            TimeTreatment.STEADY,
            is_multiphase=False,
        )
        assert result == SolverType.RHO_SIMPLE_FOAM

    def test_comp_transient(self):
        """测试可压缩瞬态 → rhoPimpleFoam"""
        result = select_solver_by_matrix(
            Compressibility.COMPRESSIBLE,
            TimeTreatment.TRANSIENT,
            is_multiphase=False,
        )
        assert result == SolverType.RHO_PIMPLE_FOAM

    def test_lowmach_steady(self):
        """测试低马赫数稳态 → buoyantSimpleFoam（Ma < 0.3）"""
        result = select_solver_by_matrix(
            Compressibility.LOW_MACH,
            TimeTreatment.STEADY,
            is_multiphase=False,
        )
        assert result == SolverType.BUOYANT_SIMPLE_FOAM

    def test_lowmach_transient(self):
        """测试低马赫数瞬态 → buoyantPimpleFoam"""
        result = select_solver_by_matrix(
            Compressibility.LOW_MACH,
            TimeTreatment.TRANSIENT,
            is_multiphase=False,
        )
        assert result == SolverType.BUOYANT_PIMPLE_FOAM

    def test_multiphase_override(self):
        """测试多相流优先 → interFoam"""
        result = select_solver_by_matrix(
            Compressibility.INCOMPRESSIBLE,
            TimeTreatment.STEADY,
            is_multiphase=True,
        )
        assert result == SolverType.INTER_FOAM

    def test_su2_priority(self):
        """测试 SU2 优先（可压缩流）"""
        result = select_solver_by_matrix(
            Compressibility.COMPRESSIBLE,
            TimeTreatment.STEADY,
            is_multiphase=False,
            solver_type=SolverType.SU2_CFD,
        )
        assert result == SolverType.SU2_CFD


# ============================================================================
# Test Gold Standard Cases（经典验证案例）
# ============================================================================

class TestGoldStandardCases:
    """测试经典 CFD 验证案例的物理规划"""

    def test_backward_facing_step(self):
        """测试后向台阶流（经典湍流分离案例）"""
        # Re = 44,000 → 湍流
        physics = infer_physics_from_params(reynolds=44000, mach=0)

        assert physics.flow_type == FlowType.TURBULENT
        assert physics.turbulence_model == TurbulenceModel.K_EPSILON
        assert physics.compressibility == Compressibility.INCOMPRESSIBLE
        assert physics.time_treatment == TimeTreatment.STEADY

    def test_cylinder_flow(self):
        """测试圆柱绕流（经典外流案例）"""
        # Re = 100 → 层流
        physics = infer_physics_from_params(reynolds=100, mach=0)

        assert physics.flow_type == FlowType.LAMINAR
        assert physics.turbulence_model is None
        assert physics.compressibility == Compressibility.INCOMPRESSIBLE

    def test_cavity_natural_convection(self):
        """测试方腔自然对流（经典传热案例）"""
        physics = infer_physics_from_params(
            reynolds=1000,
            mach=0,
            has_gravity=True,
            has_heat_transfer=True,
        )

        assert physics.gravity is True
        assert physics.energy_model is True
        # Mach=0 属于 INCOMPRESSIBLE，LOW_MACH 是 0.01 < Mach <= 0.3
        assert physics.compressibility == Compressibility.INCOMPRESSIBLE


# ============================================================================
# Test Boundary Cases（边界值测试）
# ============================================================================

class TestBoundaryCases:
    """测试边界值：Ma = 0.3, Re = 4000"""

    def test_mach_0_3_boundary(self):
        """测试 Ma = 0.3 边界（可压缩性分界线）"""
        # Ma < 0.3 → LOW_MACH
        physics_low = infer_physics_from_params(reynolds=10000, mach=0.29)
        assert physics_low.compressibility == Compressibility.LOW_MACH

        # Ma = 0.3 → LOW_MACH（边界包含在下区间）
        physics_boundary = infer_physics_from_params(reynolds=10000, mach=0.3)
        assert physics_boundary.compressibility == Compressibility.LOW_MACH

        # Ma > 0.3 → COMPRESSIBLE
        physics_high = infer_physics_from_params(reynolds=10000, mach=0.31)
        assert physics_high.compressibility == Compressibility.COMPRESSIBLE

    def test_reynolds_4000_boundary(self):
        """测试 Re = 4000 边界（层流/湍流分界线）"""
        # Re < 4000 → 层流
        physics_laminar = infer_physics_from_params(reynolds=3999)
        assert physics_laminar.flow_type == FlowType.LAMINAR
        assert physics_laminar.turbulence_model is None

        # Re = 4000 → 湍流（边界包含在上区间）
        physics_turbulent = infer_physics_from_params(reynolds=4000)
        assert physics_turbulent.flow_type == FlowType.TURBULENT
        assert physics_turbulent.turbulence_model == TurbulenceModel.K_EPSILON


# ============================================================================
# Test BC Validation（边界条件验证）
# ============================================================================

class TestBCValidation:
    """测试边界条件组合验证"""

    def test_internal_flow_valid_bcs(self):
        """测试内流有效边界条件"""
        bcs = [
            BoundaryCondition(name="inlet", type=BCType.INLET_VELOCITY),
            BoundaryCondition(name="outlet", type=BCType.OUTLET_PRESSURE),
            BoundaryCondition(name="walls", type=BCType.WALL_NO_SLIP),
        ]

        valid, errors, warnings = validate_boundary_conditions(
            ProblemType.INTERNAL_FLOW,
            bcs,
        )

        assert valid is True
        assert len(errors) == 0

    def test_internal_flow_missing_inlet(self):
        """测试内流缺少入口边界条件"""
        bcs = [
            BoundaryCondition(name="outlet", type=BCType.OUTLET_PRESSURE),
        ]

        valid, errors, _ = validate_boundary_conditions(
            ProblemType.INTERNAL_FLOW,
            bcs,
        )

        assert valid is False
        assert any("Missing inlet" in e for e in errors)

    def test_external_flow_with_freestream(self):
        """测试外流必须包含 FREESTREAM"""
        bcs = [
            BoundaryCondition(name="inlet", type=BCType.INLET_VELOCITY),
            BoundaryCondition(name="freestream", type=BCType.FREESTREAM),
        ]

        valid, errors, _ = validate_boundary_conditions(
            ProblemType.EXTERNAL_FLOW,
            bcs,
        )

        assert valid is True

    def test_natural_convection_no_velocity_inlet(self):
        """测试自然对流不允许入口速度"""
        bcs = [
            BoundaryCondition(name="walls", type=BCType.WALL_NO_SLIP),
            BoundaryCondition(name="inlet", type=BCType.INLET_VELOCITY),
        ]

        valid, errors, _ = validate_boundary_conditions(
            ProblemType.HEAT_TRANSFER_NATURAL,
            bcs,
        )

        assert valid is False
        assert any("Invalid BC" in e for e in errors)


# ============================================================================
# Test Convergence Criteria（收敛标准测试）
# ============================================================================

class TestConvergenceCriteria:
    """测试收敛判断逻辑"""

    def test_converged_below_threshold(self):
        """测试收敛：残差低于阈值"""
        criteria = [
            ConvergenceCriterion(
                name="p",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-5,
                comparison="below",
                window=10,
            ),
        ]

        history = {"p": [1e-3, 1e-4, 1e-5, 1e-6] * 3}

        converged, msg = is_converged(criteria, history)
        assert converged is True
        assert "All criteria met" in msg

    def test_not_converged_above_threshold(self):
        """测试未收敛：残差高于阈值"""
        criteria = [
            ConvergenceCriterion(
                name="p",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-5,
                comparison="below",
                window=10,
            ),
        ]

        history = {"p": [1e-3, 1e-2, 1e-1] * 4}

        converged, msg = is_converged(criteria, history)
        assert converged is False
        assert "p =" in msg

    def test_stable_within_tolerance(self):
        """测试稳定性：变化在容差内"""
        criteria = [
            ConvergenceCriterion(
                name="Cd",
                type=ConvergenceType.FORCE,
                target_value=0.005,
                comparison="stable_within",
                window=10,
                tolerance=0.01,
            ),
        ]

        # 稳定的值（变化 < 1%）
        history = {"Cd": [1.0, 1.005, 0.998, 1.002, 1.001] * 2}

        converged, msg = is_converged(criteria, history)
        assert converged is True

    def test_insufficient_data(self):
        """测试数据不足"""
        criteria = [
            ConvergenceCriterion(
                name="p",
                type=ConvergenceType.RESIDUAL,
                target_value=1e-5,
                comparison="below",
                window=100,
            ),
        ]

        history = {"p": [1e-3, 1e-4, 1e-5]}  # 只有 3 个数据点

        converged, msg = is_converged(criteria, history)
        assert converged is False
        assert "insufficient data" in msg


# ============================================================================
# Test Default Convergence Criteria by Problem Type
# ============================================================================

class TestDefaultConvergenceCriteria:
    """测试按问题类型的默认收敛标准"""

    def test_internal_flow_defaults(self):
        """测试内流默认收敛标准"""
        criteria = get_default_convergence_criteria(ProblemType.INTERNAL_FLOW)

        assert len(criteria) >= 2
        assert any(c.name == "p" for c in criteria)
        assert any(c.name == "U" for c in criteria)

        # 检查目标值
        p_criterion = next(c for c in criteria if c.name == "p")
        assert p_criterion.target_value == 1e-5
        assert p_criterion.type == ConvergenceType.RESIDUAL

    def test_external_flow_defaults(self):
        """测试外流默认收敛标准（包含力系数）"""
        criteria = get_default_convergence_criteria(ProblemType.EXTERNAL_FLOW)

        assert len(criteria) >= 3
        assert any(c.name == "Cd" for c in criteria)
        assert any(c.name == "Cl" for c in criteria)

        # 检查力系数设置
        cd_criterion = next(c for c in criteria if c.name == "Cd")
        assert cd_criterion.type == ConvergenceType.FORCE
        assert cd_criterion.comparison == "stable_within"
        assert cd_criterion.window == 200

    def test_heat_transfer_defaults(self):
        """测试传热问题默认收敛标准"""
        criteria = get_default_convergence_criteria(ProblemType.HEAT_TRANSFER)

        assert len(criteria) >= 2
        assert any(c.name == "T" for c in criteria)
        assert any(c.name == "Nu_avg" for c in criteria)

        # 检查温度残差更严格
        t_criterion = next(c for c in criteria if c.name == "T")
        assert t_criterion.target_value == 1e-7  # 温度残差更严格


# ============================================================================
# Test PhysicsPlanner Class
# ============================================================================

class TestPhysicsPlanner:
    """测试 PhysicsPlanner 类"""

    def test_planner_init(self):
        """测试规划器初始化"""
        planner = PhysicsPlanner()
        assert planner.strict_mode is True

    def test_plan_from_case_params_basic(self):
        """测试从参数生成基本规划"""
        planner = PhysicsPlanner()
        plan = planner.plan_from_case_params(
            reynolds=10000,
            mach=0,
            has_gravity=False,
            has_heat_transfer=False,
        )

        assert plan.problem_type == ProblemType.INTERNAL_FLOW
        assert plan.physics_model is not None
        assert plan.recommended_solver == SolverType.SIMPLE_FOAM

    def test_plan_from_case_params_heat_transfer(self):
        """测试传热问题规划"""
        planner = PhysicsPlanner()
        plan = planner.plan_from_case_params(
            reynolds=1000,
            mach=0,
            has_gravity=True,
            has_heat_transfer=True,
        )

        assert plan.problem_type == ProblemType.HEAT_TRANSFER_NATURAL
        assert plan.physics_model.gravity is True
        assert plan.physics_model.energy_model is True

    def test_validate_plan_success(self):
        """测试验证有效规划"""
        planner = PhysicsPlanner()
        plan = planner.plan_from_case_params(
            reynolds=10000,
            mach=0,
        )

        valid, errors, warnings = planner.validate_plan(plan)

        assert valid is True
        assert len(errors) == 0

    def test_validate_plan_missing_turbulence_model(self):
        """测试验证：湍流缺少湍流模型"""
        planner = PhysicsPlanner()

        # 创建湍流但没有湍流模型的模型
        physics = PhysicsModel(
            solver_type=SolverType.SIMPLE_FOAM,
            flow_type=FlowType.TURBULENT,
            turbulence_model=None,  # 缺少湍流模型
        )

        plan = create_physics_plan(ProblemType.INTERNAL_FLOW, physics)

        valid, errors, warnings = planner.validate_plan(plan)

        # 应该有警告但不应该是错误
        assert any("Turbulent flow without turbulence model" in w for w in warnings)

    def test_validate_plan_gravity_requires_energy(self):
        """测试验证：重力需要能量模型"""
        planner = PhysicsPlanner()

        # 创建有重力但没有能量模型的模型
        physics = PhysicsModel(
            solver_type=SolverType.SIMPLE_FOAM,
            flow_type=FlowType.LAMINAR,
            turbulence_model=None,
            gravity=True,  # 有重力
            energy_model=False,  # 但没有能量模型
        )

        plan = create_physics_plan(ProblemType.INTERNAL_FLOW, physics)

        valid, errors, warnings = planner.validate_plan(plan)

        assert valid is False
        assert any("Gravity requires energy model" in e for e in errors)


# ============================================================================
# Test PhysicsModel Class（按 Opus 4.6 要求）
# ============================================================================

class TestPhysicsModel:
    """测试 PhysicsModel 类"""

    def test_physics_model_required_fields(self):
        """测试 PhysicsModel 必填字段"""
        model = PhysicsModel(
            solver_type=SolverType.SIMPLE_FOAM,
            flow_type=FlowType.LAMINAR,
            turbulence_model=None,
        )

        # 检查默认值
        assert model.time_treatment == TimeTreatment.STEADY
        assert model.compressibility == Compressibility.INCOMPRESSIBLE
        assert model.gravity is False
        assert model.radiation_model is None

    def test_physics_model_recommended_fields(self):
        """测试 PhysicsModel 推荐字段"""
        model = PhysicsModel(
            solver_type=SolverType.SIMPLE_FOAM,
            flow_type=FlowType.LAMINAR,
            turbulence_model=None,
            reference_values={"Re": 1000, "Ma": 0},
            wall_treatment="standardWallFunctions",
        )

        assert model.reference_values["Re"] == 1000
        assert model.wall_treatment == "standardWallFunctions"


# ============================================================================
# Test BoundaryCondition Class
# ============================================================================

class TestBoundaryCondition:
    """测试 BoundaryCondition 类"""

    def test_boundary_condition_creation(self):
        """测试边界条件创建"""
        bc = BoundaryCondition(
            name="inlet",
            type=BCType.INLET_VELOCITY,
            values={"U": "(10 0 0)", "k": 1.0, "omega": 100.0},
        )

        assert bc.name == "inlet"
        assert bc.type == BCType.INLET_VELOCITY
        assert bc.values["U"] == "(10 0 0)"

    def test_boundary_condition_default_values(self):
        """测试边界条件默认值"""
        bc = BoundaryCondition(
            name="wall",
            type=BCType.WALL_NO_SLIP,
        )

        assert bc.values == {}


# ============================================================================
# Test ConvergenceCriterion Class
# ============================================================================

class TestConvergenceCriterion:
    """测试 ConvergenceCriterion 类（按 Opus 4.6 结构化要求）"""

    def test_convergence_criterion_creation(self):
        """测试收敛标准创建"""
        criterion = ConvergenceCriterion(
            name="p",
            type=ConvergenceType.RESIDUAL,
            target_value=1e-5,
            comparison="below",
            window=100,
            tolerance=0.01,
        )

        assert criterion.name == "p"
        assert criterion.type == ConvergenceType.RESIDUAL
        assert criterion.target_value == 1e-5
        assert criterion.comparison == "below"
        assert criterion.window == 100
        assert criterion.tolerance == 0.01

    def test_convergence_criterion_defaults(self):
        """测试收敛标准默认值"""
        criterion = ConvergenceCriterion(
            name="U",
            type=ConvergenceType.RESIDUAL,
            target_value=1e-4,
            comparison="below",
        )

        assert criterion.window == 100  # 默认值
        assert criterion.tolerance == 0.01  # 默认值


# ============================================================================
# Test Factory Functions
# ============================================================================

class TestFactoryFunctions:
    """测试工厂函数"""

    def test_create_physics_plan_basic(self):
        """测试创建基本物理规划"""
        plan = create_physics_plan(ProblemType.INTERNAL_FLOW)

        assert plan.plan_id.startswith("PHYSICS-")
        assert plan.problem_type == ProblemType.INTERNAL_FLOW
        assert plan.recommended_solver == SolverType.SIMPLE_FOAM
        assert len(plan.convergence_criteria) > 0

    def test_create_physics_plan_with_model(self):
        """测试创建带物理模型的规划"""
        physics = PhysicsModel(
            solver_type=SolverType.PIMPLE_FOAM,
            flow_type=FlowType.TURBULENT,
            turbulence_model=TurbulenceModel.K_EPSILON,
            time_treatment=TimeTreatment.TRANSIENT,
            compressibility=Compressibility.INCOMPRESSIBLE,
        )

        plan = create_physics_plan(ProblemType.INTERNAL_FLOW, physics)

        assert plan.physics_model == physics
        assert plan.recommended_solver == SolverType.PIMPLE_FOAM

    def test_infer_physics_from_params_laminar(self):
        """测试从参数推断层流模型"""
        physics = infer_physics_from_params(reynolds=1000)

        assert physics.flow_type == FlowType.LAMINAR
        assert physics.turbulence_model is None

    def test_infer_physics_from_params_turbulent(self):
        """测试从参数推断湍流模型"""
        physics = infer_physics_from_params(reynolds=10000)

        assert physics.flow_type == FlowType.TURBULENT
        assert physics.turbulence_model == TurbulenceModel.K_EPSILON

    def test_plan_from_case_convenience(self):
        """测试便捷函数 plan_from_case"""
        plan = plan_from_case(reynolds=5000, mach=0.1)

        assert plan.physics_model is not None
        assert plan.physics_model.flow_type == FlowType.TURBULENT
        assert plan.recommended_solver is not None


# ============================================================================
# Test G3P2 Quality Gate（G3P2 质量门）
# ============================================================================

class TestG3P2Gate:
    """测试 Phase 2 Execution Layer 的 G3P2 质量门"""

    def test_g3p2_gate_enum_only_types(self):
        """G3P2 门：所有类型必须是 enum，不能是 str"""
        # 创建 PhysicsModel 使用枚举
        model = PhysicsModel(
            solver_type=SolverType.SIMPLE_FOAM,
            flow_type=FlowType.LAMINAR,
            turbulence_model=None,
            time_treatment=TimeTreatment.STEADY,
            compressibility=Compressibility.INCOMPRESSIBLE,
        )

        # 验证所有类型都是枚举
        assert isinstance(model.solver_type, SolverType)
        assert isinstance(model.flow_type, FlowType)
        assert isinstance(model.time_treatment, TimeTreatment)
        assert isinstance(model.compressibility, Compressibility)

    def test_g3p2_gate_2d_matrix_coverage(self):
        """G3P2 门：二维决策矩阵覆盖所有组合"""
        # 测试所有 compressibility × time_treatment 组合
        combinations = [
            (Compressibility.INCOMPRESSIBLE, TimeTreatment.STEADY),
            (Compressibility.INCOMPRESSIBLE, TimeTreatment.TRANSIENT),
            (Compressibility.COMPRESSIBLE, TimeTreatment.STEADY),
            (Compressibility.COMPRESSIBLE, TimeTreatment.TRANSIENT),
            (Compressibility.LOW_MACH, TimeTreatment.STEADY),
            (Compressibility.LOW_MACH, TimeTreatment.TRANSIENT),
        ]

        for comp, time in combinations:
            solver = select_solver_by_matrix(comp, time)
            assert solver is not None
            assert isinstance(solver, SolverType)

    def test_g3p2_gate_bc_validation_rules_exist(self):
        """G3P2 门：BC 验证规则存在"""
        # 检查关键问题类型有验证规则
        assert ProblemType.INTERNAL_FLOW in BC_VALIDATION_RULES
        assert ProblemType.EXTERNAL_FLOW in BC_VALIDATION_RULES
        assert ProblemType.HEAT_TRANSFER_NATURAL in BC_VALIDATION_RULES

    def test_g3p2_gate_ma_0_3_boundary(self):
        """G3P2 门：Ma = 0.3 分界线正确处理"""
        # Ma < 0.3 应该是 LOW_MACH
        physics_0_29 = infer_physics_from_params(reynolds=1000, mach=0.29)
        assert physics_0_29.compressibility == Compressibility.LOW_MACH

        # Ma = 0.3 应该是 LOW_MACH（边界包含在下区间）
        physics_0_3 = infer_physics_from_params(reynolds=1000, mach=0.3)
        assert physics_0_3.compressibility == Compressibility.LOW_MACH

        # Ma > 0.3 应该是 COMPRESSIBLE
        physics_0_31 = infer_physics_from_params(reynolds=1000, mach=0.31)
        assert physics_0_31.compressibility == Compressibility.COMPRESSIBLE
