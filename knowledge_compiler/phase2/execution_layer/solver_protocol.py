#!/usr/bin/env python3
"""SolverExecutor protocol and normalized result payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class SolverResult:
    """Normalized result returned by solver executors."""

    success: bool
    is_mock: bool
    output_dir: Optional[str]
    metrics: dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_s: float = 0.0


@runtime_checkable
class SolverExecutor(Protocol):
    """Protocol implemented by all solver executors."""

    @property
    def is_mock(self) -> bool:
        """Whether this executor produces mock data instead of real solver output."""
        ...

    @property
    def solver_type(self) -> str:
        """Executor family identifier such as ``openfoam``, ``su2``, or ``mock``."""
        ...

    def setup(self, case_dir: str) -> None:
        """Initialize the executor with a prepared case directory."""
        ...

    def execute(self, config: dict[str, Any]) -> SolverResult:
        """Execute the solver with the provided runtime configuration."""
        ...

    def validate(self) -> bool:
        """Return whether the executor runtime environment is available."""
        ...
