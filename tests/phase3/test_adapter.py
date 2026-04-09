#!/usr/bin/env python3
"""
Tests for Phase 3 ↔ Phase 2 Type Adapter

验证双向类型转换的正确性。
"""

import pytest

from knowledge_compiler.phase2.execution_layer.schema import (
    BCType,
    Compressibility,
    ConvergenceCriterion,
    ConvergenceType,
    FlowType,
    ProblemType as P2ProblemType,
    SolverType as P2SolverType,
    TimeTreatment,
    TurbulenceModel,
    BoundaryCondition as P2BoundaryCondition,
)
from knowledge_compiler.phase2.execution_layer.cad_parser import (
    BoundingBox as P2BoundingBox,
    GeometryFormat as P2GeometryFormat,
    ParsedGeometry as P2ParsedGeometry,
    GeometryFeature as P2GeometryFeature,
)
from knowledge_compiler.phase3.adapter import (
    bc_type_to_p2,
    bc_type_to_p3,
    bounding_box_to_p3,
    compressibility_to_p2,
    convergence_to_p3,
    flow_type_to_p2,
    flow_type_to_p3,
    get_convergence_criteria_p2,
    p2_bc_to_p3,
    p3_bc_to_p2,
    p2_physics_model_to_p3,
    problem_type_to_p2,
    problem_type_to_p3,
    select_solver_p2,
    solver_type_p3_to_p2,
    solver_type_to_p3,
    time_treatment_to_p2,
    turbulence_model_to_p2,
    turbulence_model_to_p3,
    p2_parsed_geometry_to_p3,
)
from knowledge_compiler.phase3.schema import (
    BoundaryCondition as P3BoundaryCondition,
    MeshFormat,
    ParsedGeometry as P3ParsedGeometry,
    SolverType as P3SolverType,
)


# ============================================================================
# P3 → P2 转换
# ============================================================================

class TestP3ToP2FlowType:
    def test_laminar(self):
        assert flow_type_to_p2("laminar") == FlowType.LAMINAR

    def test_turbulent(self):
        assert flow_type_to_p2("turbulent") == FlowType.TURBULENT

    def test_transitional(self):
        assert flow_type_to_p2("transitional") == FlowType.TRANSITIONAL

    def test_unknown_defaults_turbulent(self):
        assert flow_type_to_p2("unknown") == FlowType.TURBULENT


class TestP3ToP2TurbulenceModel:
    def test_komega(self):
        assert turbulence_model_to_p2("kOmegaSST") == TurbulenceModel.K_OMEGA_SST

    def test_kepsilon(self):
        assert turbulence_model_to_p2("kEpsilon") == TurbulenceModel.K_EPSILON

    def test_none(self):
        assert turbulence_model_to_p2("none") == TurbulenceModel.NONE


class TestP3ToP2TimeTreatment:
    def test_steady(self):
        assert time_treatment_to_p2(True) == TimeTreatment.STEADY

    def test_transient(self):
        assert time_treatment_to_p2(False) == TimeTreatment.TRANSIENT


class TestP3ToP2Compressibility:
    def test_incompressible(self):
        assert compressibility_to_p2("incompressible") == Compressibility.INCOMPRESSIBLE

    def test_compressible(self):
        assert compressibility_to_p2("compressible") == Compressibility.COMPRESSIBLE


class TestP3ToP2ProblemType:
    def test_internal_flow(self):
        assert problem_type_to_p2("internal_flow") == P2ProblemType.INTERNAL_FLOW

    def test_external_flow(self):
        assert problem_type_to_p2("external_flow") == P2ProblemType.EXTERNAL_FLOW

    def test_heat_transfer(self):
        assert problem_type_to_p2("heat_transfer") == P2ProblemType.HEAT_TRANSFER

    def test_unknown_defaults_internal(self):
        assert problem_type_to_p2("unknown_type") == P2ProblemType.INTERNAL_FLOW


class TestP3ToP2BCType:
    def test_noSlip(self):
        assert bc_type_to_p2("noSlip") == BCType.WALL_NO_SLIP

    def test_fixedValue(self):
        assert bc_type_to_p2("fixedValue") == BCType.INLET_VELOCITY

    def test_zeroGradient(self):
        assert bc_type_to_p2("zeroGradient") == BCType.OUTLET_ZERO_GRADIENT

    def test_freestream(self):
        assert bc_type_to_p2("freestream") == BCType.FREESTREAM

    def test_symmetry(self):
        assert bc_type_to_p2("symmetry") == BCType.SYMMETRY


class TestP3ToP2SolverType:
    def test_openfoam(self):
        assert solver_type_p3_to_p2(P3SolverType.OPENFOAM) == P2SolverType.SIMPLE_FOAM

    def test_su2(self):
        assert solver_type_p3_to_p2(P3SolverType.SU2) == P2SolverType.SU2_CFD


# ============================================================================
# P2 → P3 转换
# ============================================================================

class TestP2ToP3FlowType:
    def test_laminar(self):
        assert flow_type_to_p3(FlowType.LAMINAR) == "laminar"

    def test_turbulent(self):
        assert flow_type_to_p3(FlowType.TURBULENT) == "turbulent"


class TestP2ToP3TurbulenceModel:
    def test_komega(self):
        assert turbulence_model_to_p3(TurbulenceModel.K_OMEGA_SST) == "kOmegaSST"

    def test_none(self):
        assert turbulence_model_to_p3(TurbulenceModel.NONE) == "none"


class TestP2ToP3SolverType:
    def test_simple_foam_to_openfoam(self):
        assert solver_type_to_p3(P2SolverType.SIMPLE_FOAM) == P3SolverType.OPENFOAM

    def test_pimple_foam_to_openfoam(self):
        assert solver_type_to_p3(P2SolverType.PIMPLE_FOAM) == P3SolverType.OPENFOAM

    def test_su2_to_su2(self):
        assert solver_type_to_p3(P2SolverType.SU2_CFD) == P3SolverType.SU2

    def test_all_p2_solvers_covered(self):
        """所有 Phase 2 求解器都能映射到 Phase 3 类别"""
        for p2_st in P2SolverType:
            p3_st = solver_type_to_p3(p2_st)
            assert isinstance(p3_st, P3SolverType)


class TestP2ToP3BCType:
    def test_wall_no_slip(self):
        assert bc_type_to_p3(BCType.WALL_NO_SLIP) == "noSlip"

    def test_inlet_velocity(self):
        assert bc_type_to_p3(BCType.INLET_VELOCITY) == "fixedValue"

    def test_outlet_zero_gradient(self):
        assert bc_type_to_p3(BCType.OUTLET_ZERO_GRADIENT) == "zeroGradient"

    def test_freestream(self):
        assert bc_type_to_p3(BCType.FREESTREAM) == "freestream"


class TestP2ToP3ProblemType:
    def test_internal_flow(self):
        assert problem_type_to_p3(P2ProblemType.INTERNAL_FLOW) == "internal_flow"

    def test_internal_flow_pipe(self):
        assert problem_type_to_p3(P2ProblemType.INTERNAL_FLOW_PIPE) == "internal_flow"

    def test_external_flow_airfoil(self):
        assert problem_type_to_p3(P2ProblemType.EXTERNAL_FLOW_AIRFOIL) == "external_flow"

    def test_heat_transfer_forced(self):
        assert problem_type_to_p3(P2ProblemType.HEAT_TRANSFER_FORCED) == "heat_transfer"


class TestP2ToP3BoundingBox:
    def test_conversion(self):
        bb = P2BoundingBox(min_x=0, min_y=1, min_z=2, max_x=3, max_y=4, max_z=5)
        result = bounding_box_to_p3(bb)
        assert result["x_min"] == 0
        assert result["x_max"] == 3
        assert result["size_x"] == 3
        assert result["size_y"] == 3
        assert result["size_z"] == 3


class TestP2ToP3Convergence:
    def test_conversion(self):
        criteria = [
            ConvergenceCriterion(
                name="p", type=ConvergenceType.RESIDUAL,
                target_value=1e-5, comparison="below",
            ),
            ConvergenceCriterion(
                name="U", type=ConvergenceType.RESIDUAL,
                target_value=1e-5, comparison="below",
            ),
        ]
        result = convergence_to_p3(criteria)
        assert "residual_p" in result
        assert "residual_u" in result
        assert result["residual_p"] == 1e-5


class TestBCBidirectional:
    def test_p3_to_p2_and_back(self):
        bc_p3 = P3BoundaryCondition(name="inlet", type="fixedValue", values={"U": "uniform (1 0 0)"})
        bc_p2 = p3_bc_to_p2(bc_p3)
        assert bc_p2.name == "inlet"
        assert isinstance(bc_p2.type, BCType)

        bc_back = p2_bc_to_p3(bc_p2)
        assert bc_back.name == "inlet"


# ============================================================================
# 便捷函数
# ============================================================================

class TestSelectSolverP2:
    def test_default_openfoam(self):
        assert select_solver_p2() == P3SolverType.OPENFOAM

    def test_transient_openfoam(self):
        assert select_solver_p2(steady_state=False) == P3SolverType.OPENFOAM

    def test_su2_compressible(self):
        """SU2 只在 compressible 场景被 Phase 2 矩阵选中"""
        assert select_solver_p2(
            compressibility="compressible", custom_solver=P3SolverType.SU2
        ) == P3SolverType.SU2


class TestGetConvergenceCriteriaP2:
    def test_internal_flow(self):
        result = get_convergence_criteria_p2("internal_flow")
        assert "residual_p" in result
        assert "residual_u" in result

    def test_external_flow(self):
        result = get_convergence_criteria_p2("external_flow")
        assert "residual_p" in result


class TestParsedGeometryConversion:
    def test_basic_conversion(self):
        p2_geom = P2ParsedGeometry(
            source_file="test.stl",
            format=P2GeometryFormat.STL,
            surface_area=10.0,
            volume=5.0,
            is_valid=True,
        )
        p3_geom = p2_parsed_geometry_to_p3(p2_geom)
        assert isinstance(p3_geom, P3ParsedGeometry)
        assert p3_geom.source_file == "test.stl"
        assert p3_geom.format == MeshFormat.STL
        assert p3_geom.surface_area == 10.0

    def test_invalid_geometry(self):
        p2_geom = P2ParsedGeometry(
            source_file="bad.stl",
            format=P2GeometryFormat.STL,
            is_valid=False,
            error_message="parse error",
        )
        p3_geom = p2_parsed_geometry_to_p3(p2_geom)
        assert p3_geom.is_watertight is False
        assert len(p3_geom.repair_needed) > 0

    def test_with_bounding_box(self):
        bb = P2BoundingBox(min_x=0, min_y=0, min_z=0, max_x=1, max_y=2, max_z=3)
        p2_geom = P2ParsedGeometry(
            source_file="test.stl",
            format=P2GeometryFormat.STL,
            bounding_box=bb,
            is_valid=True,
        )
        p3_geom = p2_parsed_geometry_to_p3(p2_geom)
        assert p3_geom.bounding_box is not None
        assert p3_geom.bounding_box["size_x"] == 1

    def test_obj_format(self):
        p2_geom = P2ParsedGeometry(
            source_file="test.obj",
            format=P2GeometryFormat.OBJ,
            is_valid=True,
        )
        p3_geom = p2_parsed_geometry_to_p3(p2_geom)
        assert p3_geom.format == MeshFormat.OBJ
