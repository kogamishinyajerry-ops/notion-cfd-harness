#!/usr/bin/env python3
"""Tests for the Phase 7.2 OpenFOAM Docker executor."""

from __future__ import annotations

from knowledge_compiler.phase2.execution_layer.case_generator import OpenFOAMCaseGenerator
from knowledge_compiler.phase2.execution_layer.openfoam_docker import OpenFOAMDockerExecutor


def test_validate_returns_bool() -> None:
    executor = OpenFOAMDockerExecutor(OpenFOAMCaseGenerator("/tmp"))

    result = executor.validate()

    assert isinstance(result, bool)


def test_solver_type() -> None:
    executor = OpenFOAMDockerExecutor(OpenFOAMCaseGenerator("/tmp"))

    assert executor.solver_type == "openfoam-docker"
    assert executor.is_mock is False


def test_solver_command_map() -> None:
    executor = OpenFOAMDockerExecutor(OpenFOAMCaseGenerator("/tmp"))

    assert executor._get_solver_command("BENCH-01") == "icoFoam"
    assert executor._get_solver_command("BENCH-07") == "simpleFoam"
    assert executor._get_solver_command("BENCH-04") == "pimpleFoam"
