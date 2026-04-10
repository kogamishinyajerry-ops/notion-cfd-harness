#!/usr/bin/env python3
"""Test scaffold for GenericOpenFOAMCaseGenerator spec validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.phase2.execution_layer.case_generator_specs import (
    BCType,
    BoundaryPatchSpec,
    BoundarySpec,
    GeometrySpec,
    GeometryType,
    MeshSpec,
    PhysicsSpec,
    SolverType,
    validate_geometry_spec,
    validate_mesh_spec,
    validate_physics_spec,
)


def test_geometry_spec_validation_accepts_valid_simple_grid() -> None:
    """Valid SIMPLE_GRID GeometrySpec should pass validation."""
    spec = GeometrySpec(GeometryType.SIMPLE_GRID, 0.0, 1.0, 0.0, 1.0)
    assert validate_geometry_spec(spec) == []


def test_geometry_spec_validation_rejects_negative_domain() -> None:
    """GeometrySpec with x_min < MIN_DOMAIN_SIZE should fail."""
    # x_size = 1.0 - (-1.0) = 2.0 which is valid, but x_min itself can be negative
    # The domain size check tests x_size, not absolute x_min
    # So negative domain here means x_min far outside causing x_size > MAX_DOMAIN_SIZE
    spec = GeometrySpec(GeometryType.SIMPLE_GRID, -500.0, -499.0, 0.0, 1.0)
    # x_size = -499 - (-500) = 1, y_size = 1, both valid... need x_size too big
    spec2 = GeometrySpec(GeometryType.SIMPLE_GRID, -1001.0, 0.0, 0.0, 1.0)
    # x_size = 1001 > MAX_DOMAIN_SIZE(1000), so should fail
    errors = validate_geometry_spec(spec2)
    assert errors != []


def test_geometry_spec_validation_rejects_x_min_gte_x_max() -> None:
    """GeometrySpec with x_min >= x_max should fail validation."""
    spec = GeometrySpec(GeometryType.SIMPLE_GRID, 1.0, 0.0, 0.0, 1.0)
    errors = validate_geometry_spec(spec)
    assert errors != []
    assert any("x_min" in e for e in errors)


def test_geometry_spec_validation_rejects_body_outside_domain() -> None:
    """BODY_IN_CHANNEL with body bounds outside domain should fail."""
    spec = GeometrySpec(
        GeometryType.BODY_IN_CHANNEL,
        0.0, 1.0, 0.0, 1.0,
        body_x_min=0.0,
        body_x_max=2.0,  # outside domain x_max=1.0
        body_y_min=0.0,
        body_y_max=0.5,
    )
    errors = validate_geometry_spec(spec)
    assert errors != []
    assert any("body_x" in e for e in errors)


def test_mesh_spec_validation_accepts_valid_mesh() -> None:
    """Valid MeshSpec with SIMPLE_GRID should pass validation."""
    geometry = GeometrySpec(GeometryType.SIMPLE_GRID, 0.0, 1.0, 0.0, 1.0)
    mesh = MeshSpec(nx=40, ny=40)
    assert validate_mesh_spec(mesh, geometry) == []


def test_mesh_spec_validation_rejects_negative_cell_count() -> None:
    """MeshSpec with negative cell count should fail validation."""
    geometry = GeometrySpec(GeometryType.SIMPLE_GRID, 0.0, 1.0, 0.0, 1.0)
    mesh = MeshSpec(nx=-1, ny=40)
    errors = validate_mesh_spec(mesh, geometry)
    assert errors != []
    assert any("nx" in e and "-1" in e for e in errors)


def test_mesh_spec_validation_rejects_missing_step_cells() -> None:
    """BACKWARD_FACING_STEP without required step cell counts should fail."""
    geometry = GeometrySpec(GeometryType.BACKWARD_FACING_STEP, -4.0, 20.0, 0.0, 2.0)
    mesh = MeshSpec()  # missing nx_inlet, nx_outlet, ny_lower, ny_upper
    errors = validate_mesh_spec(mesh, geometry)
    assert errors != []
    assert any("BACKWARD_FACING_STEP" in e for e in errors)


def test_mesh_spec_validation_rejects_missing_body_cells() -> None:
    """BODY_IN_CHANNEL without required body cell counts should fail."""
    geometry = GeometrySpec(
        GeometryType.BODY_IN_CHANNEL,
        0.0, 3.0, -0.5, 0.5,
        body_x_min=-0.05,
        body_x_max=0.05,
        body_y_min=-0.05,
        body_y_max=0.05,
    )
    mesh = MeshSpec()  # missing nx_left, nx_body, nx_right, ny_outer, ny_body
    errors = validate_mesh_spec(mesh, geometry)
    assert errors != []
    assert any("BODY_IN_CHANNEL" in e for e in errors)


def test_physics_spec_validation_accepts_icofoam() -> None:
    """Valid ICO_FOAM PhysicsSpec should pass validation."""
    geometry = GeometrySpec(GeometryType.SIMPLE_GRID, 0.0, 1.0, 0.0, 1.0)
    spec = PhysicsSpec(SolverType.ICO_FOAM, 100.0)
    assert validate_physics_spec(spec, geometry) == []


def test_physics_spec_validation_rejects_simplefoam_without_turbulence() -> None:
    """SIMPLE_FOAM without k_inlet and epsilon_inlet should fail."""
    geometry = GeometrySpec(GeometryType.BACKWARD_FACING_STEP, -4.0, 20.0, 0.0, 2.0)
    spec = PhysicsSpec(SolverType.SIMPLE_FOAM, 7600.0)
    errors = validate_physics_spec(spec, geometry)
    assert errors != []
    assert any("SIMPLE_FOAM" in e and "k_inlet" in e for e in errors)


def test_physics_spec_validation_accepts_simplefoam_with_turbulence() -> None:
    """SIMPLE_FOAM with k_inlet and epsilon_inlet should pass."""
    geometry = GeometrySpec(GeometryType.BACKWARD_FACING_STEP, -4.0, 20.0, 0.0, 2.0)
    spec = PhysicsSpec(
        SolverType.SIMPLE_FOAM,
        7600.0,
        k_inlet=0.01,
        epsilon_inlet=0.001,
    )
    assert validate_physics_spec(spec, geometry) == []


# Wave 2 tests — blockMesh generation, BC rendering, solver assembly


def test_generate_simple_grid_case(tmp_path: Path) -> None:
    """Generate a simple grid (cavity) case and verify files exist."""
    from knowledge_compiler.phase2.execution_layer.case_generator_specs import (
        BCType,
        BoundaryPatchSpec,
        BoundarySpec,
        GeometrySpec,
        GeometryType,
        MeshSpec,
        PhysicsSpec,
        SolverType,
    )
    from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
        GenericOpenFOAMCaseGenerator,
    )

    geometry = GeometrySpec(GeometryType.SIMPLE_GRID, 0.0, 1.0, 0.0, 1.0, thickness=0.01)
    mesh = MeshSpec(nx=10, ny=10)
    physics = PhysicsSpec(SolverType.ICO_FOAM, 100.0, u_lid=1.0)
    boundary = BoundarySpec(
        patches={
            "movingWall": BoundaryPatchSpec("movingWall", BCType.FIXED_VALUE, "(1 0 0)"),
            "fixedWalls": BoundaryPatchSpec("fixedWalls", BCType.WALL),
            "frontAndBack": BoundaryPatchSpec("frontAndBack", BCType.EMPTY),
        }
    )
    gen = GenericOpenFOAMCaseGenerator(str(tmp_path))
    case_path = gen.generate("TEST-CASE-01", geometry, mesh, physics, boundary)
    assert (case_path / "system/blockMeshDict").exists()
    assert (case_path / "0/U").exists()
    assert (case_path / "0/p").exists()
    assert (case_path / "system/controlDict").exists()
    assert (case_path / "system/fvSchemes").exists()
    assert (case_path / "system/fvSolution").exists()
    assert (case_path / "constant/physicalProperties").exists()


def test_blockmesh_vertices_count_simple_grid(tmp_path: Path) -> None:
    """SIMPLE_GRID produces exactly 8 vertices."""
    from knowledge_compiler.phase2.execution_layer.case_generator_specs import (
        GeometrySpec,
        GeometryType,
        MeshSpec,
    )
    from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
        GenericOpenFOAMCaseGenerator,
    )

    geometry = GeometrySpec(GeometryType.SIMPLE_GRID, 0.0, 1.0, 0.0, 1.0)
    mesh = MeshSpec(nx=40, ny=40)
    verts = GenericOpenFOAMCaseGenerator._simple_grid_vertices(geometry, mesh)
    assert len(verts) == 8


def test_bc_field_renders_fixed_value_u(tmp_path: Path) -> None:
    """Velocity BC with fixedValue renders correct OpenFOAM format."""
    from knowledge_compiler.phase2.execution_layer.case_generator_specs import (
        BCType,
        BoundaryPatchSpec,
    )
    from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
        GenericOpenFOAMCaseGenerator,
    )

    patches = {"inlet": BoundaryPatchSpec("inlet", BCType.FIXED_VALUE, "(1 0 0)")}
    physics_mock = type("MockPhysics", (), {"u_inlet": 1.0})()
    result = GenericOpenFOAMCaseGenerator._render_bc_field("U", patches, physics_mock)
    assert "type fixedValue" in result
    assert "uniform (1 0 0)" in result
    assert "inlet" in result


def test_bc_field_renders_zero_gradient_p(tmp_path: Path) -> None:
    """Pressure BC with zeroGradient renders correct OpenFOAM format."""
    from knowledge_compiler.phase2.execution_layer.case_generator_specs import (
        BCType,
        BoundaryPatchSpec,
    )
    from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
        GenericOpenFOAMCaseGenerator,
    )

    patches = {"outlet": BoundaryPatchSpec("outlet", BCType.ZERO_GRADIENT)}
    physics_mock = type("MockPhysics", (), {})()
    result = GenericOpenFOAMCaseGenerator._render_bc_field("p", patches, physics_mock)
    assert "type zeroGradient" in result
    assert "outlet" in result


def test_generate_body_in_channel_case(tmp_path: Path) -> None:
    """Generate a body-in-channel case (cylinder wake)."""
    from knowledge_compiler.phase2.execution_layer.case_generator_specs import (
        BCType,
        BoundaryPatchSpec,
        BoundarySpec,
        GeometrySpec,
        GeometryType,
        MeshSpec,
        PhysicsSpec,
        SolverType,
    )
    from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
        GenericOpenFOAMCaseGenerator,
    )

    geometry = GeometrySpec(
        GeometryType.BODY_IN_CHANNEL,
        -1.0,
        3.0,
        -0.5,
        0.5,
        thickness=0.01,
        body_x_min=-0.05,
        body_x_max=0.05,
        body_y_min=-0.05,
        body_y_max=0.05,
    )
    mesh = MeshSpec(nx_left=24, nx_body=16, nx_right=80, ny_outer=20, ny_body=16)
    physics = PhysicsSpec(SolverType.PIMPLE_FOAM, 100.0, u_inlet=1.0, max_co=2.0)
    boundary = BoundarySpec(
        patches={
            "inlet": BoundaryPatchSpec("inlet", BCType.FIXED_VALUE, "(1 0 0)"),
            "outlet": BoundaryPatchSpec("outlet", BCType.ZERO_GRADIENT),
            "symmetry": BoundaryPatchSpec("symmetry", BCType.SYMMETRY_PLANE),
            "cylinder": BoundaryPatchSpec("cylinder", BCType.WALL),
            "frontAndBack": BoundaryPatchSpec("frontAndBack", BCType.EMPTY),
        }
    )
    gen = GenericOpenFOAMCaseGenerator(str(tmp_path))
    case_path = gen.generate("TEST-CASE-04", geometry, mesh, physics, boundary)
    assert (case_path / "system/blockMeshDict").exists()
    assert (case_path / "0/U").exists()
    assert (case_path / "0/p").exists()
    assert (case_path / "system/controlDict").exists()
    assert (case_path / "constant/physicalProperties").exists()
    assert (case_path / "constant/momentumTransport").exists()


def test_backward_facing_step_vertices_count(tmp_path: Path) -> None:
    """BACKWARD_FACING_STEP produces coarse-grid vertices (mesh-density dependent).

    With nx_inlet=2, nx_outlet=2, ny_lower=2, ny_upper=2 and the col() function
    producing n+1 points per section, this yields (2+1+2+1) * (2+2) * 2 = 42 per z-layer.
    """
    from knowledge_compiler.phase2.execution_layer.case_generator_specs import (
        GeometrySpec,
        GeometryType,
        MeshSpec,
    )
    from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
        GenericOpenFOAMCaseGenerator,
    )

    geometry = GeometrySpec(GeometryType.BACKWARD_FACING_STEP, -4.0, 20.0, 0.0, 2.0)
    mesh = MeshSpec(nx_inlet=2, nx_outlet=2, ny_lower=2, ny_upper=2)
    verts = GenericOpenFOAMCaseGenerator._backward_facing_step_vertices(geometry, mesh)
    # With 2 cells per section: col() gives 3 points each
    # x: 3 inlet + 3 outlet = 6 x-coords, y: 3 lower + 3 upper = 6 y-coords
    # Full grid: 6 * 6 = 36 per z-layer, 72 total
    assert len(verts) == 72


def test_generate_simple_foam_case(tmp_path: Path) -> None:
    """Generate a simpleFoam case and verify turbulence files exist."""
    from knowledge_compiler.phase2.execution_layer.case_generator_specs import (
        BCType,
        BoundaryPatchSpec,
        BoundarySpec,
        GeometrySpec,
        GeometryType,
        MeshSpec,
        PhysicsSpec,
        SolverType,
    )
    from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
        GenericOpenFOAMCaseGenerator,
    )

    geometry = GeometrySpec(GeometryType.BACKWARD_FACING_STEP, -4.0, 20.0, 0.0, 2.0)
    mesh = MeshSpec(nx_inlet=20, nx_outlet=40, ny_lower=20, ny_upper=20)
    physics = PhysicsSpec(
        SolverType.SIMPLE_FOAM, 7600.0, k_inlet=0.01, epsilon_inlet=0.001
    )
    boundary = BoundarySpec(
        patches={
            "inlet": BoundaryPatchSpec("inlet", BCType.FIXED_VALUE, "(1 0 0)"),
            "outlet": BoundaryPatchSpec("outlet", BCType.ZERO_GRADIENT),
            "walls": BoundaryPatchSpec("walls", BCType.WALL),
            "frontAndBack": BoundaryPatchSpec("frontAndBack", BCType.EMPTY),
        }
    )
    gen = GenericOpenFOAMCaseGenerator(str(tmp_path))
    case_path = gen.generate("TEST-CASE-SIMPLE", geometry, mesh, physics, boundary)
    assert (case_path / "system/blockMeshDict").exists()
    assert (case_path / "0/U").exists()
    assert (case_path / "0/p").exists()
    assert (case_path / "constant/physicalProperties").exists()
    assert (case_path / "constant/turbulenceProperties").exists()
    assert (case_path / "0/k").exists()
    assert (case_path / "0/epsilon").exists()
    assert (case_path / "0/nut").exists()


def test_blockmesh_contains_vertices_and_blocks(tmp_path: Path) -> None:
    """Generated blockMeshDict contains vertices and blocks sections."""
    from knowledge_compiler.phase2.execution_layer.case_generator_specs import (
        BCType,
        BoundaryPatchSpec,
        BoundarySpec,
        GeometrySpec,
        GeometryType,
        MeshSpec,
        PhysicsSpec,
        SolverType,
    )
    from knowledge_compiler.phase2.execution_layer.generic_case_generator import (
        GenericOpenFOAMCaseGenerator,
    )

    geometry = GeometrySpec(GeometryType.SIMPLE_GRID, 0.0, 1.0, 0.0, 1.0, thickness=0.01)
    mesh = MeshSpec(nx=10, ny=10)
    physics = PhysicsSpec(SolverType.ICO_FOAM, 100.0)
    boundary = BoundarySpec(
        patches={
            "movingWall": BoundaryPatchSpec("movingWall", BCType.FIXED_VALUE, "(1 0 0)"),
            "fixedWalls": BoundaryPatchSpec("fixedWalls", BCType.WALL),
            "frontAndBack": BoundaryPatchSpec("frontAndBack", BCType.EMPTY),
        }
    )
    gen = GenericOpenFOAMCaseGenerator(str(tmp_path))
    case_path = gen.generate("TEST-CASE-02", geometry, mesh, physics, boundary)
    blockmesh = (case_path / "system/blockMeshDict").read_text()
    assert "vertices" in blockmesh
    assert "blocks" in blockmesh
    assert "hex" in blockmesh
    assert "boundary" in blockmesh
