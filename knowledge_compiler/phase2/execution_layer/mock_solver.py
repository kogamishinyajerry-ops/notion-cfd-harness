#!/usr/bin/env python3
"""Mock solver executor used for fallback and benchmark replay flows."""

from __future__ import annotations

import random
import time
from typing import Any, Optional

from knowledge_compiler.phase2.execution_layer.solver_protocol import SolverResult


def simulate_benchmark_output(
    expected_output: dict[str, Any],
    fix_action: str = "",
) -> dict[str, Any]:
    """Replicate the existing Phase 2c mock replay behavior."""

    simulated_output: dict[str, Any] = {}

    if "数据" in fix_action or "值" in fix_action:
        for field_name, expected_value in expected_output.items():
            if isinstance(expected_value, (int, float)):
                perturbation = random.uniform(-0.01, 0.01)
                simulated_output[field_name] = expected_value * (1 + perturbation)
            else:
                simulated_output[field_name] = expected_value
        return simulated_output

    if "公式" in fix_action or "算法" in fix_action:
        return expected_output.copy()

    if "缺失" in fix_action or "添加" in fix_action:
        return expected_output.copy()

    return expected_output.copy()


def _extract_numeric_metrics(payload: dict[str, Any]) -> dict[str, float]:
    """Extract numeric fields as solver metrics."""

    metrics: dict[str, float] = {}
    for key, value in payload.items():
        if isinstance(value, (int, float)):
            metrics[key] = float(value)
    return metrics


class MockSolverExecutor:
    """Mock implementation of the SolverExecutor protocol."""

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self._config = dict(config or {})
        self._case_dir: Optional[str] = None

    @property
    def is_mock(self) -> bool:
        """Mock executor always returns synthetic data."""

        return True

    @property
    def solver_type(self) -> str:
        """Mock executor type identifier."""

        return "mock"

    def setup(self, case_dir: str) -> None:
        """Store the case directory for later execution metadata."""

        self._case_dir = case_dir

    def execute(self, config: dict[str, Any]) -> SolverResult:
        """Execute a synthetic solver run and return normalized results."""

        start = time.time()
        runtime_config = {**self._config, **config}

        expected_output = runtime_config.get("expected_output", {})
        fix_action = runtime_config.get("fix_action", "")

        if expected_output:
            output = simulate_benchmark_output(
                expected_output=expected_output,
                fix_action=fix_action,
            )
        else:
            output = runtime_config.get("output", {})
            if not output:
                output = runtime_config.get("metrics", {})

        return SolverResult(
            success=True,
            is_mock=self.is_mock,
            output_dir=(
                runtime_config.get("output_dir")
                or runtime_config.get("case_dir")
                or self._case_dir
            ),
            metrics=_extract_numeric_metrics(output),
            error=None,
            execution_time_s=time.time() - start,
        )

    def validate(self) -> bool:
        """Mock executor is always available."""

        return True
