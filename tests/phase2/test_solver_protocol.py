#!/usr/bin/env python3
"""Tests for the Phase 7.1 solver protocol and executor factory."""

from __future__ import annotations

import pytest

from knowledge_compiler.phase2.execution_layer.executor_factory import ExecutorFactory
from knowledge_compiler.phase2.execution_layer.mock_solver import MockSolverExecutor
from knowledge_compiler.phase2.execution_layer.solver_protocol import (
    SolverExecutor,
    SolverResult,
)


def _make_config(executor: str = "mock", fallback: str = "mock") -> dict[str, object]:
    return {
        "solver": {
            "executor": executor,
            "fallback": fallback,
            "docker": {
                "image": "openfoam/openfoam13-default",
                "timeout": 600,
                "memory_limit": "4g",
            },
        }
    }


class TestSolverResult:
    """Tests for the normalized solver result payload."""

    def test_solver_result_fields(self) -> None:
        result = SolverResult(
            success=True,
            is_mock=True,
            output_dir="/tmp/mock-case",
            metrics={"lift": 0.12},
            error=None,
            execution_time_s=1.5,
        )

        assert result.success is True
        assert result.is_mock is True
        assert result.output_dir == "/tmp/mock-case"
        assert result.metrics == {"lift": 0.12}
        assert result.error is None
        assert result.execution_time_s == 1.5


class TestMockSolverExecutor:
    """Tests for the mock executor implementation."""

    def test_mock_solver_metadata(self) -> None:
        executor = MockSolverExecutor({})

        assert executor.is_mock is True
        assert executor.solver_type == "mock"
        assert executor.validate() is True
        assert isinstance(executor, SolverExecutor)

    def test_mock_solver_execute_uses_mock_output(self) -> None:
        executor = MockSolverExecutor({})
        executor.setup("/tmp/mock-case")

        result = executor.execute(
            {
                "expected_output": {"result": 200.0},
                "fix_action": "修正数据公式",
            }
        )

        assert result.success is True
        assert result.is_mock is True
        assert result.output_dir == "/tmp/mock-case"
        assert result.metrics["result"] == pytest.approx(200.0, rel=0.01)
        assert result.execution_time_s >= 0.0


class TestExecutorFactory:
    """Tests for config-driven executor selection."""

    def test_create_mock_executor(self) -> None:
        factory = ExecutorFactory(_make_config())

        executor = factory.create("mock")

        assert isinstance(executor, MockSolverExecutor)

    def test_create_openfoam_executor_falls_back_to_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        factory = ExecutorFactory(_make_config(executor="openfoam-docker"))

        class UnavailableExecutor:
            def __init__(self, config: dict[str, object]):
                self.config = config

            @property
            def is_mock(self) -> bool:
                return False

            @property
            def solver_type(self) -> str:
                return "openfoam"

            def setup(self, case_dir: str) -> None:
                self.case_dir = case_dir

            def execute(self, config: dict[str, object]) -> SolverResult:
                raise NotImplementedError

            def validate(self) -> bool:
                return False

        monkeypatch.setattr(
            factory,
            "_load_executor_class",
            lambda name: UnavailableExecutor if name == "openfoam-docker" else None,
        )

        executor = factory.create("openfoam-docker")

        assert isinstance(executor, MockSolverExecutor)
        assert executor.is_mock is True

    def test_validate_environment_reports_all_supported_executors(self) -> None:
        factory = ExecutorFactory(_make_config(executor="openfoam-docker"))

        status = factory.validate_environment()

        assert set(status) == {"mock", "openfoam-docker", "su2-docker"}
        assert status["mock"] is True
        assert isinstance(status["openfoam-docker"], bool)
        assert isinstance(status["su2-docker"], bool)
