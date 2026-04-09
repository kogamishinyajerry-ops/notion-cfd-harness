#!/usr/bin/env python3
"""Template-backed OpenFOAM case generator for Phase 7 benchmark presets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


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
        "constant/transportProperties",
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
                "END_TIME": "50.0",
                "DELTA_T": "0.002",
                "MAX_CO": "1.0",
                "MAX_DELTA_T": "0.002",
                "WRITE_INTERVAL": "1.0",
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
