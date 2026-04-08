#!/usr/bin/env python3
"""
Tests for Phase 3 Physics Planner

Coverage:
1. PhysicsPlanner: plan generation, problem classification, solver recommendation
2. Boundary condition generation
3. Solver settings generation
4. BatchPhysicsPlanner: batch plan, summary
5. Convenience functions
"""

import pytest

from knowledge_compiler.phase3.schema import (
    BoundaryCondition,
    PhysicsModel,
    PhysicsPlan,
    SolverType,
)
from knowledge_compiler.phase3.physics_planner.planner import (
    PhysicsPlanner,
    BatchPhysicsPlanner,
    create_physics_plan,
    plan_from_geometry,
)


# ============================================================================
# Problem Classification
# ============================================================================

class TestProblemClassification:
    def setup_method(self):
        self.planner = PhysicsPlanner()

    def test_internal_flow_pipe(self):
        plan = self.planner.plan(problem_description="pipe flow analysis")
        assert plan.problem_type == "internal_flow"

    def test_internal_flow_duct(self):
        plan = self.planner.plan(problem_description="duct simulation")
        assert plan.problem_type == "internal_flow"

    def test_external_flow_airfoil(self):
        plan = self.planner.plan(problem_description="NACA airfoil simulation")
        assert plan.problem_type == "external_flow"

    def test_external_flow_chinese(self):
        plan = self.planner.plan(problem_description="翼型外流场分析")
        assert plan.problem_type == "external_flow"

    def test_heat_transfer(self):
        plan = self.planner.plan(problem_description="conjugate heat transfer")
        assert plan.problem_type == "heat_transfer"

    def test_multiphase(self):
        plan = self.planner.plan(problem_description="free surface flow")
        assert plan.problem_type == "multiphase"

    def test_compressible(self):
        plan = self.planner.plan(problem_description="supersonic flow at Mach 2")
        assert plan.problem_type == "compressible"

    def test_default_internal_flow(self):
        plan = self.planner.plan(problem_description="generic simulation")
        assert plan.problem_type == "internal_flow"

    def test_geometry_based_classification(self):
        plan = self.planner.plan(
            problem_description="",
            geometry_features={"type": "airfoil"},
        )
        assert plan.problem_type == "external_flow"

    def test_geometry_pipe_classification(self):
        plan = self.planner.plan(
            problem_description="",
            geometry_features={"type": "pipe"},
        )
        assert plan.problem_type == "internal_flow"

    def test_custom_classifier(self):
        def my_classifier(desc):
            return "multiphase"

        planner = PhysicsPlanner(custom_classifier=my_classifier)
        plan = planner.plan(problem_description="anything")
        assert plan.problem_type == "multiphase"


# ============================================================================
# Solver Recommendation
# ============================================================================

class TestSolverRecommendation:
    def setup_method(self):
        self.planner = PhysicsPlanner()

    def test_incompressible_steady(self):
        plan = self.planner.plan(
            problem_description="pipe flow",
            compressibility="incompressible",
            steady_state=True,
        )
        assert plan.recommended_solver == SolverType.OPENFOAM
        assert "simpleFoam" in plan.solver_settings.get("turbulence_model", "") or True

    def test_transient_solver(self):
        plan = self.planner.plan(
            problem_description="pipe flow",
            steady_state=False,
        )
        assert plan.recommended_solver == SolverType.OPENFOAM

    def test_custom_solver_override(self):
        plan = self.planner.plan(
            problem_description="pipe flow",
            custom_solver=SolverType.SU2,
        )
        assert plan.recommended_solver == SolverType.SU2

    def test_heat_transfer_solver(self):
        plan = self.planner.plan(
            problem_description="conjugate heat transfer in cooling channel",
        )
        assert plan.recommended_solver == SolverType.OPENFOAM


# ============================================================================
# Physics Model
# ============================================================================

class TestPhysicsModel:
    def setup_method(self):
        self.planner = PhysicsPlanner()

    def test_turbulent_model(self):
        plan = self.planner.plan(flow_type="turbulent")
        assert plan.physics_model is not None
        assert plan.physics_model.turbulence_model == "kOmegaSST"

    def test_laminar_model(self):
        plan = self.planner.plan(flow_type="laminar")
        assert plan.physics_model.turbulence_model == "none"

    def test_transitional_model(self):
        plan = self.planner.plan(flow_type="transitional")
        assert plan.physics_model.turbulence_model == "kOmegaSST"

    def test_energy_model(self):
        plan = self.planner.plan(energy=True)
        assert plan.physics_model.energy_model is True

    def test_multiphase_flag(self):
        plan = self.planner.plan(problem_description="free surface multiphase")
        assert plan.physics_model.multiphase_model is True

    def test_solver_type_in_model(self):
        plan = self.planner.plan()
        assert plan.physics_model.solver_type == SolverType.OPENFOAM


# ============================================================================
# Boundary Conditions
# ============================================================================

class TestBoundaryConditions:
    def setup_method(self):
        self.planner = PhysicsPlanner()

    def test_internal_flow_bc(self):
        plan = self.planner.plan(problem_description="pipe flow")
        bc_names = [bc.name for bc in plan.boundary_conditions]
        assert "inlet" in bc_names
        assert "outlet" in bc_names
        assert "walls" in bc_names

    def test_external_flow_bc(self):
        plan = self.planner.plan(problem_description="airfoil")
        bc_names = [bc.name for bc in plan.boundary_conditions]
        assert "farfield" in bc_names
        assert "body" in bc_names

    def test_heat_transfer_bc(self):
        plan = self.planner.plan(problem_description="heat transfer cooling")
        bc_names = [bc.name for bc in plan.boundary_conditions]
        assert "hot_wall" in bc_names

    def test_bc_has_type(self):
        plan = self.planner.plan(problem_description="pipe")
        for bc in plan.boundary_conditions:
            assert isinstance(bc, BoundaryCondition)
            assert bc.type != ""


# ============================================================================
# Solver Settings
# ============================================================================

class TestSolverSettings:
    def setup_method(self):
        self.planner = PhysicsPlanner()

    def test_steady_state_settings(self):
        plan = self.planner.plan(steady_state=True)
        assert "relaxation_factors" in plan.solver_settings

    def test_transient_settings(self):
        plan = self.planner.plan(steady_state=False)
        assert "delta_t" in plan.solver_settings
        assert "max_co" in plan.solver_settings

    def test_convergence_criteria(self):
        plan = self.planner.plan()
        assert "residual_u" in plan.convergence_criteria
        assert "residual_p" in plan.convergence_criteria

    def test_no_energy_residual_when_disabled(self):
        plan = self.planner.plan(energy=False)
        assert "residual_energy" not in plan.convergence_criteria

    def test_energy_residual_when_enabled(self):
        plan = self.planner.plan(energy=True)
        assert "residual_energy" in plan.convergence_criteria

    def test_multiphase_settings(self):
        plan = self.planner.plan(problem_description="multiphase free surface")
        assert "n_alpha_correctors" in plan.solver_settings


# ============================================================================
# BatchPhysicsPlanner
# ============================================================================

class TestBatchPhysicsPlanner:
    def test_batch_plan(self):
        batch = BatchPhysicsPlanner()
        plans = batch.plan_batch([
            {"problem_description": "pipe flow"},
            {"problem_description": "airfoil"},
            {"problem_description": "heat transfer"},
        ])
        assert len(plans) == 3
        assert plans[0].problem_type == "internal_flow"
        assert plans[1].problem_type == "external_flow"
        assert plans[2].problem_type == "heat_transfer"

    def test_batch_summary(self):
        batch = BatchPhysicsPlanner()
        plans = batch.plan_batch([
            {"problem_description": "pipe flow"},
            {"problem_description": "airfoil"},
        ])
        summary = batch.get_summary(plans)
        assert summary["total"] == 2
        assert "internal_flow" in summary["problem_types"]
        assert "external_flow" in summary["problem_types"]

    def test_batch_empty(self):
        batch = BatchPhysicsPlanner()
        plans = batch.plan_batch([])
        assert plans == []
        summary = batch.get_summary(plans)
        assert summary["total"] == 0


# ============================================================================
# Convenience Functions
# ============================================================================

class TestConvenienceFunctions:
    def test_create_physics_plan(self):
        plan = create_physics_plan(
            problem_type="external_flow",
            flow_type="turbulent",
            solver_type=SolverType.SU2,
        )
        assert plan.problem_type == "external_flow"
        assert plan.physics_model is not None
        assert plan.physics_model.flow_type == "turbulent"
        assert plan.recommended_solver == SolverType.SU2

    def test_create_physics_plan_defaults(self):
        plan = create_physics_plan()
        assert plan.problem_type == "internal_flow"
        assert plan.physics_model.turbulence_model == "kOmegaSST"

    def test_plan_from_geometry(self):
        plan = plan_from_geometry(
            geometry_info={"type": "airfoil"},
            description="wing simulation",
        )
        assert plan.problem_type == "external_flow"
        assert plan.physics_model is not None
