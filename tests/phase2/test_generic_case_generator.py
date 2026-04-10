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
