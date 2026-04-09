#!/usr/bin/env python3
"""Tests for the Phase 7.1b OpenFOAM template case generator."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.phase2.execution_layer.case_generator import OpenFOAMCaseGenerator


@pytest.mark.parametrize(
    ("case_id", "expected_solver"),
    [
        ("BENCH-01", "icoFoam"),
        ("BENCH-07", "simpleFoam"),
        ("BENCH-04", "pimpleFoam"),
    ],
)
def test_generate_supported_case(tmp_path: Path, case_id: str, expected_solver: str) -> None:
    generator = OpenFOAMCaseGenerator(str(tmp_path))

    case_dir = generator.generate(case_id)

    assert case_dir == tmp_path / case_id
    assert case_dir.exists()
    assert generator.validate(case_dir) is True

    control_dict = (case_dir / "system" / "controlDict").read_text(encoding="utf-8")
    assert expected_solver in control_dict
    assert "{{" not in control_dict


def test_generate_bench01_substitutes_key_values(tmp_path: Path) -> None:
    generator = OpenFOAMCaseGenerator(str(tmp_path))

    case_dir = generator.generate("BENCH-01")

    physical_properties = (
        case_dir / "constant" / "physicalProperties"
    ).read_text(encoding="utf-8")
    velocity_field = (case_dir / "0" / "U").read_text(encoding="utf-8")

    assert "0.01" in physical_properties
    assert "uniform (1.0 0 0)" in velocity_field
    assert "{{" not in physical_properties
    assert "{{" not in velocity_field


def test_generate_bench07_includes_turbulence_files(tmp_path: Path) -> None:
    generator = OpenFOAMCaseGenerator(str(tmp_path))

    case_dir = generator.generate("BENCH-07")

    turbulence_properties = (
        case_dir / "constant" / "turbulenceProperties"
    ).read_text(encoding="utf-8")

    assert "kEpsilon" in turbulence_properties
    assert (case_dir / "0" / "k").exists()
    assert (case_dir / "0" / "epsilon").exists()
    assert (case_dir / "0" / "nut").exists()


def test_generate_unsupported_raises(tmp_path: Path) -> None:
    generator = OpenFOAMCaseGenerator(str(tmp_path))

    with pytest.raises(ValueError, match="Unsupported case"):
        generator.generate("UNKNOWN-99")


def test_all_three_cases_validate(tmp_path: Path) -> None:
    generator = OpenFOAMCaseGenerator(str(tmp_path))

    for case_id in OpenFOAMCaseGenerator.SUPPORTED_CASES:
        case_dir = generator.generate(case_id)
        assert generator.validate(case_dir), f"{case_id} validation failed"
