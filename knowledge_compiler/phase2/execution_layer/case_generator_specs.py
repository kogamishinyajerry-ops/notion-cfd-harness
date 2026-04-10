#!/usr/bin/env python3
"""Typed dataclasses and validation for GenericOpenFOAMCaseGenerator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GeometryType(Enum):
    """Supported geometry types for generic case generation."""

    SIMPLE_GRID = "simple_grid"
    BACKWARD_FACING_STEP = "backward_facing_step"
    BODY_IN_CHANNEL = "body_in_channel"


class BCType(Enum):
    """OpenFOAM boundary condition types."""

    FIXED_VALUE = "fixedValue"
    ZERO_GRADIENT = "zeroGradient"
    SYMMETRY_PLANE = "symmetryPlane"
    WALL = "wall"
    EMPTY = "empty"
    PATCH = "patch"


class SolverType(Enum):
    """OpenFOAM solver types."""

    ICO_FOAM = "icoFoam"
    SIMPLE_FOAM = "simpleFoam"
    PIMPLE_FOAM = "pimpleFoam"


# Validation constants
MAX_CELL_COUNT: int = 1_000_000
MAX_DOMAIN_SIZE: float = 1000.0
MIN_DOMAIN_SIZE: float = 1e-6


@dataclass(frozen=True)
class BoundaryPatchSpec:
    """Boundary patch specification for a single patch."""

    name: str
    bc_type: BCType
    value: str = ""


@dataclass(frozen=True)
class GeometrySpec:
    """Geometry specification for the computational domain.

    Attributes:
        geometry_type: Type of geometry to generate.
        x_min: Minimum x-coordinate of the domain.
        x_max: Maximum x-coordinate of the domain.
        y_min: Minimum y-coordinate of the domain.
        y_max: Maximum y-coordinate of the domain.
        thickness: Domain thickness in the z-direction (default 0.01).
        body_x_min: Body minimum x (BODY_IN_CHANNEL only).
        body_x_max: Body maximum x (BODY_IN_CHANNEL only).
        body_y_min: Body minimum y (BODY_IN_CHANNEL only).
        body_y_max: Body maximum y (BODY_IN_CHANNEL only).
    """

    geometry_type: GeometryType
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    thickness: float = 0.01
    body_x_min: Optional[float] = None
    body_x_max: Optional[float] = None
    body_y_min: Optional[float] = None
    body_y_max: Optional[float] = None


@dataclass(frozen=True)
class MeshSpec:
    """Mesh specification for the computational domain.

    Attributes:
        nx: Number of cells in x-direction for SIMPLE_GRID.
        ny: Number of cells in y-direction for SIMPLE_GRID.
        nx_inlet: Cells in x before step (BACKWARD_FACING_STEP).
        nx_outlet: Cells in x after step (BACKWARD_FACING_STEP).
        ny_lower: Cells in y below step (BACKWARD_FACING_STEP).
        ny_upper: Cells in y above step (BACKWARD_FACING_STEP).
        nx_left: Cells in x left of body (BODY_IN_CHANNEL).
        nx_body: Cells in x around body (BODY_IN_CHANNEL).
        nx_right: Cells in x right of body (BODY_IN_CHANNEL).
        ny_outer: Cells in y outside body region (BODY_IN_CHANNEL).
        ny_body: Cells in y around body (BODY_IN_CHANNEL).
    """

    nx: int = 40
    ny: int = 40
    nx_inlet: Optional[int] = None
    nx_outlet: Optional[int] = None
    ny_lower: Optional[int] = None
    ny_upper: Optional[int] = None
    nx_left: Optional[int] = None
    nx_body: Optional[int] = None
    nx_right: Optional[int] = None
    ny_outer: Optional[int] = None
    ny_body: Optional[int] = None


@dataclass(frozen=True)
class PhysicsSpec:
    """Physics specification for the simulation.

    Attributes:
        solver: OpenFOAM solver type.
        reynolds_number: Reynolds number for the simulation.
        u_inlet: Inlet velocity (default 1.0).
        u_lid: Lid velocity for cavity (default 1.0).
        k_inlet: Turbulent kinetic energy at inlet (SIMPLE_FOAM only).
        epsilon_inlet: Turbulent dissipation at inlet (SIMPLE_FOAM only).
        nu: Kinematic viscosity override (computed from Re/U if None).
        end_time: Simulation end time (default 10.0).
        delta_t: Time step size (default 0.001).
        write_interval: Write interval for output (default 1.0).
        max_co: Maximum Courant number for pimpleFoam.
    """

    solver: SolverType
    reynolds_number: float
    u_inlet: float = 1.0
    u_lid: float = 1.0
    k_inlet: Optional[float] = None
    epsilon_inlet: Optional[float] = None
    nu: Optional[float] = None
    end_time: float = 10.0
    delta_t: float = 0.001
    write_interval: float = 1.0
    max_co: Optional[float] = None


@dataclass(frozen=True)
class BoundarySpec:
    """Boundary condition specification mapping patch names to patch specs."""

    patches: dict[str, BoundaryPatchSpec]


def validate_geometry_spec(spec: GeometrySpec) -> list[str]:
    """Validate a GeometrySpec and return list of error strings.

    Checks:
    - Domain sizes are within MIN_DOMAIN_SIZE..MAX_DOMAIN_SIZE
    - x_min < x_max and y_min < y_max
    - thickness > 0
    - For BODY_IN_CHANNEL: body bounds are within domain
    """
    errors: list[str] = []

    x_size = spec.x_max - spec.x_min
    y_size = spec.y_max - spec.y_min

    if x_size < MIN_DOMAIN_SIZE or x_size > MAX_DOMAIN_SIZE:
        errors.append(
            f"x-domain size {x_size} outside valid range "
            f"[{MIN_DOMAIN_SIZE}, {MAX_DOMAIN_SIZE}]"
        )

    if y_size < MIN_DOMAIN_SIZE or y_size > MAX_DOMAIN_SIZE:
        errors.append(
            f"y-domain size {y_size} outside valid range "
            f"[{MIN_DOMAIN_SIZE}, {MAX_DOMAIN_SIZE}]"
        )

    if spec.x_min >= spec.x_max:
        errors.append(f"x_min ({spec.x_min}) must be less than x_max ({spec.x_max})")

    if spec.y_min >= spec.y_max:
        errors.append(f"y_min ({spec.y_min}) must be less than y_max ({spec.y_max})")

    if spec.thickness <= 0:
        errors.append(f"thickness ({spec.thickness}) must be positive")

    if spec.geometry_type == GeometryType.BODY_IN_CHANNEL:
        if spec.body_x_min is None or spec.body_x_max is None:
            errors.append(
                "BODY_IN_CHANNEL requires body_x_min and body_x_max"
            )
        if spec.body_y_min is None or spec.body_y_max is None:
            errors.append(
                "BODY_IN_CHANNEL requires body_y_min and body_y_max"
            )
        if (
            spec.body_x_min is not None
            and spec.body_x_max is not None
            and spec.body_y_min is not None
            and spec.body_y_max is not None
        ):
            if spec.body_x_min < spec.x_min or spec.body_x_max > spec.x_max:
                errors.append(
                    f"body_x [{spec.body_x_min}, {spec.body_x_max}] "
                    f"outside domain [{spec.x_min}, {spec.x_max}]"
                )
            if spec.body_y_min < spec.y_min or spec.body_y_max > spec.y_max:
                errors.append(
                    f"body_y [{spec.body_y_min}, {spec.body_y_max}] "
                    f"outside domain [{spec.y_min}, {spec.y_max}]"
                )
            if spec.body_x_min >= spec.body_x_max:
                errors.append(
                    f"body_x_min ({spec.body_x_min}) must be less than "
                    f"body_x_max ({spec.body_x_max})"
                )
            if spec.body_y_min >= spec.body_y_max:
                errors.append(
                    f"body_y_min ({spec.body_y_min}) must be less than "
                    f"body_y_max ({spec.body_y_max})"
                )

    return errors


def validate_mesh_spec(spec: MeshSpec, geometry: GeometrySpec) -> list[str]:
    """Validate a MeshSpec against a GeometrySpec and return list of error strings.

    Checks:
    - All cell counts within 1..MAX_CELL_COUNT
    - BACKWARD_FACING_STEP requires nx_inlet, nx_outlet, ny_lower, ny_upper
    - BODY_IN_CHANNEL requires nx_left, nx_body, nx_right, ny_outer, ny_body
    """
    errors: list[str] = []

    cell_counts = [
        ("nx", spec.nx),
        ("ny", spec.ny),
    ]
    if spec.nx_inlet is not None:
        cell_counts.append(("nx_inlet", spec.nx_inlet))
    if spec.nx_outlet is not None:
        cell_counts.append(("nx_outlet", spec.nx_outlet))
    if spec.ny_lower is not None:
        cell_counts.append(("ny_lower", spec.ny_lower))
    if spec.ny_upper is not None:
        cell_counts.append(("ny_upper", spec.ny_upper))
    if spec.nx_left is not None:
        cell_counts.append(("nx_left", spec.nx_left))
    if spec.nx_body is not None:
        cell_counts.append(("nx_body", spec.nx_body))
    if spec.nx_right is not None:
        cell_counts.append(("nx_right", spec.nx_right))
    if spec.ny_outer is not None:
        cell_counts.append(("ny_outer", spec.ny_outer))
    if spec.ny_body is not None:
        cell_counts.append(("ny_body", spec.ny_body))

    for name, count in cell_counts:
        if count < 1:
            errors.append(f"{name} ({count}) must be at least 1")
        if count > MAX_CELL_COUNT:
            errors.append(f"{name} ({count}) exceeds MAX_CELL_COUNT ({MAX_CELL_COUNT})")

    if geometry.geometry_type == GeometryType.BACKWARD_FACING_STEP:
        missing: list[str] = []
        if spec.nx_inlet is None:
            missing.append("nx_inlet")
        if spec.nx_outlet is None:
            missing.append("nx_outlet")
        if spec.ny_lower is None:
            missing.append("ny_lower")
        if spec.ny_upper is None:
            missing.append("ny_upper")
        if missing:
            errors.append(
                f"BACKWARD_FACING_STEP requires: {', '.join(missing)}"
            )

    if geometry.geometry_type == GeometryType.BODY_IN_CHANNEL:
        missing = []
        if spec.nx_left is None:
            missing.append("nx_left")
        if spec.nx_body is None:
            missing.append("nx_body")
        if spec.nx_right is None:
            missing.append("nx_right")
        if spec.ny_outer is None:
            missing.append("ny_outer")
        if spec.ny_body is None:
            missing.append("ny_body")
        if missing:
            errors.append(
                f"BODY_IN_CHANNEL requires: {', '.join(missing)}"
            )

    return errors


def validate_physics_spec(spec: PhysicsSpec, geometry: GeometrySpec) -> list[str]:
    """Validate a PhysicsSpec and return list of error strings.

    Checks:
    - end_time > 0
    - delta_t > 0
    - max_co > 0 if set
    - SIMPLE_FOAM requires k_inlet and epsilon_inlet
    """
    errors: list[str] = []

    if spec.end_time <= 0:
        errors.append(f"end_time ({spec.end_time}) must be positive")

    if spec.delta_t <= 0:
        errors.append(f"delta_t ({spec.delta_t}) must be positive")

    if spec.max_co is not None and spec.max_co <= 0:
        errors.append(f"max_co ({spec.max_co}) must be positive")

    if spec.solver == SolverType.SIMPLE_FOAM:
        missing: list[str] = []
        if spec.k_inlet is None:
            missing.append("k_inlet")
        if spec.epsilon_inlet is None:
            missing.append("epsilon_inlet")
        if missing:
            errors.append(
                f"SIMPLE_FOAM requires turbulent parameters: {', '.join(missing)}"
            )

    return errors
