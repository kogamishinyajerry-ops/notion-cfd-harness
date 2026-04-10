#!/usr/bin/env python3
"""Template-backed OpenFOAM case generator for Phase 7 benchmark presets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from .case_generator_specs import (
    BCType,
    BoundaryPatchSpec,
    BoundarySpec,
    GeometrySpec,
    GeometryType,
    MeshSpec,
    PhysicsSpec,
    SolverType,
)
from .generic_case_generator import GenericOpenFOAMCaseGenerator


@dataclass(frozen=True)
class CasePreset:
    """Static template preset for a supported benchmark case."""

    solver: str
    parameters: Mapping[str, str]
    required_files: tuple[str, ...] = ()


class OpenFOAMCaseGenerator:
    """Generates OpenFOAM case directories from templates for Phase 7 benchmarks."""

    SUPPORTED_CASES = ["BENCH-01", "BENCH-07", "BENCH-04"]
    REQUIRED_FILES = (
        "system/controlDict",
        "system/fvSchemes",
        "system/fvSolution",
        "system/blockMeshDict",
        "0/U",
        "0/p",
        "constant/physicalProperties",
    )
    _PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
    _TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates" / "openfoam"
    _CASE_PRESETS = {
        "BENCH-01": CasePreset(
            solver="icoFoam",
            parameters={
                "APPLICATION": "icoFoam",
                "CASE_ID": "BENCH-01",
                "CASE_NAME": "lid_driven_cavity_re100",
                "DOMAIN_SIZE": "1.0",
                "THICKNESS": "0.01",
                "NX": "40",
                "NY": "40",
                "NU": "0.01",
                "U_LID": "1.0",
                "END_TIME": "10.0",
                "DELTA_T": "0.001",
                "WRITE_INTERVAL": "1.0",
            },
        ),
        "BENCH-07": CasePreset(
            solver="simpleFoam",
            parameters={
                "APPLICATION": "simpleFoam",
                "CASE_ID": "BENCH-07",
                "CASE_NAME": "backward_facing_step_re7600",
                "THICKNESS": "0.10",
                "X_INLET": "-4.0",
                "X_STEP": "0.0",
                "X_OUTLET": "20.0",
                "Y_BOTTOM": "0.0",
                "Y_STEP": "1.0",
                "Y_TOP": "2.0",
                "NX_INLET": "32",
                "NX_OUTLET": "96",
                "NY_LOWER": "24",
                "NY_UPPER": "24",
                "U_INLET": "1.0",
                "NU": "1.31579e-04",
                "END_TIME": "1500",
                "DELTA_T": "1",
                "WRITE_INTERVAL": "200",
                "K_INLET": "3.75e-03",
                "EPSILON_INLET": "2.16e-03",
            },
            required_files=(
                "constant/physicalProperties",
                "constant/turbulenceProperties",
                "0/k",
                "0/epsilon",
                "0/nut",
            ),
        ),
        "BENCH-04": CasePreset(
            solver="pimpleFoam",
            parameters={
                "APPLICATION": "pimpleFoam",
                "CASE_ID": "BENCH-04",
                "CASE_NAME": "cylinder_wake_re100",
                "THICKNESS": "0.01",
                "X_MIN": "-1.0",
                "X_BODY_MIN": "-0.05",
                "X_BODY_MAX": "0.05",
                "X_MAX": "3.0",
                "Y_MIN": "-0.5",
                "Y_BODY_MIN": "-0.05",
                "Y_BODY_MAX": "0.05",
                "Y_MAX": "0.5",
                "NX_LEFT": "24",
                "NX_BODY": "16",
                "NX_RIGHT": "80",
                "NY_OUTER": "20",
                "NY_BODY": "16",
                "U_INF": "1.0",
                "D": "0.1",
                "REYNUMBER": "100",
                "STROUHAL": "0.164",
                "NU": "0.001",
                "END_TIME": "20.0",
                "DELTA_T": "0.01",
                "MAX_CO": "2.0",
                "MAX_DELTA_T": "0.02",
                "WRITE_INTERVAL": "0.2",
            },
        ),
    }

    def __init__(self, output_root: str):
        self.output_root = Path(output_root)

    def generate(self, case_id: str) -> Path:
        """Generate a case directory for ``case_id`` and return its path."""

        preset = self._get_preset(case_id)
        case_dir = self.output_root / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        template_dir = self._template_dir(case_id)
        for template_path in sorted(path for path in template_dir.rglob("*") if path.is_file()):
            relative_path = template_path.relative_to(template_dir)
            rendered = self._substitute(
                template_path.read_text(encoding="utf-8"),
                preset.parameters,
            )
            output_path = case_dir / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered, encoding="utf-8")

        if not self.validate(case_dir):
            raise RuntimeError(f"Generated case is incomplete: {case_dir}")

        return case_dir

    def validate(self, case_dir: Path) -> bool:
        """Check that the generated case has all required files."""

        case_path = Path(case_dir)
        required_files = list(self.REQUIRED_FILES)

        case_id = case_path.name
        if case_id in self._CASE_PRESETS:
            required_files.extend(self._CASE_PRESETS[case_id].required_files)

        return all((case_path / relative_path).exists() for relative_path in required_files)

    @classmethod
    def _get_preset(cls, case_id: str) -> CasePreset:
        try:
            return cls._CASE_PRESETS[case_id]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported case: {case_id}. Use one of {cls.SUPPORTED_CASES}"
            ) from exc

    @classmethod
    def _template_dir(cls, case_id: str) -> Path:
        template_dir = cls._TEMPLATE_ROOT / case_id
        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found for {case_id}: {template_dir}")
        return template_dir

    @classmethod
    def _substitute(cls, template: str, params: Mapping[str, str]) -> str:
        rendered = template
        for key, value in params.items():
            rendered = re.sub(
                r"\{\{\s*" + re.escape(key) + r"\s*\}\}",
                str(value),
                rendered,
            )

        unresolved = sorted(set(cls._PLACEHOLDER_PATTERN.findall(rendered)))
        if unresolved:
            joined = ", ".join(unresolved)
            raise ValueError(f"Unresolved template placeholders: {joined}")

        return rendered


# Backward-compatibility alias: expose _CASE_PRESETS at module level
CASE_PRESETS = OpenFOAMCaseGenerator._CASE_PRESETS


class GenericCaseAdapter:
    """Wraps GenericOpenFOAMCaseGenerator to provide CasePreset-style interface.

    Allows legacy code using CasePreset.generate(case_id, parameters)
    to transparently use the new GenericOpenFOAMCaseGenerator.
    """

    def __init__(self, output_root: str):
        self._gen = GenericOpenFOAMCaseGenerator(output_root)

    def generate(self, case_id: str, parameters: Mapping[str, str]) -> Path:
        """Generate case using parameter mapping.

        Maps CasePreset-style parameters to GeometrySpec/MeshSpec/PhysicsSpec/BoundarySpec.
        Parameters must include: geometry_type, x_min, x_max, y_min, y_max, thickness,
        nx, ny, solver, reynolds_number, and boundary patch definitions.
        """
        # Parse geometry type
        geom_type_str = parameters.get("geometry_type", "SIMPLE_GRID")
        try:
            geometry_type = GeometryType[geom_type_str.upper().replace("-", "_")]
        except KeyError:
            raise ValueError(f"Unknown geometry_type: {geom_type_str}")

        # Build GeometrySpec
        geometry = GeometrySpec(
            geometry_type=geometry_type,
            x_min=float(parameters["x_min"]),
            x_max=float(parameters["x_max"]),
            y_min=float(parameters["y_min"]),
            y_max=float(parameters["y_max"]),
            thickness=float(parameters.get("thickness", "0.01")),
            body_x_min=float(parameters["body_x_min"]) if "body_x_min" in parameters else None,
            body_x_max=float(parameters["body_x_max"]) if "body_x_max" in parameters else None,
            body_y_min=float(parameters["body_y_min"]) if "body_y_min" in parameters else None,
            body_y_max=float(parameters["body_y_max"]) if "body_y_max" in parameters else None,
        )

        # Build MeshSpec
        mesh_kwargs: dict = {"nx": int(parameters.get("nx", 40)), "ny": int(parameters.get("ny", 40))}
        if geometry_type == GeometryType.BACKWARD_FACING_STEP:
            mesh_kwargs.update({
                "nx_inlet": int(parameters["nx_inlet"]) if "nx_inlet" in parameters else None,
                "nx_outlet": int(parameters["nx_outlet"]) if "nx_outlet" in parameters else None,
                "ny_lower": int(parameters["ny_lower"]) if "ny_lower" in parameters else None,
                "ny_upper": int(parameters["ny_upper"]) if "ny_upper" in parameters else None,
            })
        elif geometry_type == GeometryType.BODY_IN_CHANNEL:
            mesh_kwargs.update({
                "nx_left": int(parameters["nx_left"]) if "nx_left" in parameters else None,
                "nx_body": int(parameters["nx_body"]) if "nx_body" in parameters else None,
                "nx_right": int(parameters["nx_right"]) if "nx_right" in parameters else None,
                "ny_outer": int(parameters["ny_outer"]) if "ny_outer" in parameters else None,
                "ny_body": int(parameters["ny_body"]) if "ny_body" in parameters else None,
            })
        mesh = MeshSpec(**mesh_kwargs)

        # Build PhysicsSpec
        physics = PhysicsSpec(
            solver=SolverType[parameters.get("solver", "ICO_FOAM").upper().replace("-", "_")],
            reynolds_number=float(parameters["reynolds_number"]),
            u_inlet=float(parameters.get("u_inlet", "1.0")),
            u_lid=float(parameters.get("u_lid", "1.0")),
            k_inlet=float(parameters["k_inlet"]) if "k_inlet" in parameters else None,
            epsilon_inlet=float(parameters["epsilon_inlet"]) if "epsilon_inlet" in parameters else None,
            nu=float(parameters["nu"]) if "nu" in parameters else None,
            end_time=float(parameters.get("end_time", "10.0")),
            delta_t=float(parameters.get("delta_t", "0.001")),
            write_interval=float(parameters.get("write_interval", "1.0")),
            max_co=float(parameters["max_co"]) if "max_co" in parameters else None,
        )

        # Build BoundarySpec from patch parameters
        patches: dict[str, BoundaryPatchSpec] = {}
        for patch_name in ["inlet", "outlet", "movingWall", "fixedWalls", "frontAndBack",
                           "walls", "symmetry", "cylinder"]:
            if f"bc_type_{patch_name}" in parameters:
                bc_type = BCType[parameters[f"bc_type_{patch_name}"].upper().replace("-", "_")]
                value = parameters.get(f"bc_value_{patch_name}", "")
                patches[patch_name] = BoundaryPatchSpec(patch_name, bc_type, value)
        boundary = BoundarySpec(patches=patches)

        return self._gen.generate(case_id, geometry, mesh, physics, boundary)
