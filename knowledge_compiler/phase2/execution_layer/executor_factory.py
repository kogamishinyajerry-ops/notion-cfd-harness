#!/usr/bin/env python3
"""ExecutorFactory for config-driven solver selection with graceful fallback."""

from __future__ import annotations

import importlib
import shutil
import subprocess
from typing import Any, Optional

from knowledge_compiler.phase2.execution_layer.case_generator import OpenFOAMCaseGenerator
from knowledge_compiler.phase2.execution_layer.mock_solver import MockSolverExecutor
from knowledge_compiler.phase2.execution_layer.openfoam_docker import DEFAULT_CASE_ROOT
from knowledge_compiler.phase2.execution_layer.openfoam_docker import DEFAULT_IMAGE
from knowledge_compiler.phase2.execution_layer.solver_protocol import SolverExecutor


class ExecutorFactory:
    """Create solver executors from config and degrade gracefully when unavailable."""

    SUPPORTED_EXECUTORS = ("mock", "openfoam-docker", "su2-docker")
    _EXECUTOR_IMPORTS = {
        "openfoam-docker": (
            "knowledge_compiler.phase2.execution_layer.openfoam_docker",
            "OpenFOAMDockerExecutor",
        ),
        "su2-docker": (
            "knowledge_compiler.phase2.execution_layer.su2_docker",
            "SU2DockerExecutor",
        ),
    }

    def __init__(self, config: dict[str, Any]):
        self.config = config or {}
        self._solver_config = self.config.get("solver", {})
        self.fallback = self._solver_config.get("fallback", "mock")

    def create(self, executor_name: Optional[str] = None) -> SolverExecutor:
        """Create an executor based on config, with fallback on unavailability."""

        name = executor_name or self._solver_config.get("executor", "mock")
        return self._create_with_fallback(name=name, visited=set())

    def validate_environment(self) -> dict[str, bool]:
        """Return availability status for all supported executors."""

        return {
            executor_name: self._executor_available(executor_name)
            for executor_name in self.SUPPORTED_EXECUTORS
        }

    def _create_with_fallback(
        self,
        name: str,
        visited: set[str],
    ) -> SolverExecutor:
        if name == "fail":
            raise RuntimeError("Executor selection failed and fallback is set to 'fail'")

        if name in visited:
            raise RuntimeError(f"Executor fallback cycle detected for '{name}'")

        if name not in self.SUPPORTED_EXECUTORS:
            raise ValueError(
                f"Unsupported executor '{name}'. "
                f"Supported executors: {', '.join(self.SUPPORTED_EXECUTORS)}"
            )

        visited.add(name)

        if name == "mock":
            return MockSolverExecutor(self.config)

        executor = self._build_executor(name)
        if executor is not None and executor.validate():
            return executor

        return self._resolve_fallback(preferred=name, visited=visited)

    def _resolve_fallback(
        self,
        preferred: str,
        visited: set[str],
    ) -> SolverExecutor:
        fallback_name = self.fallback
        if fallback_name in (None, "", preferred, "fail"):
            raise RuntimeError(
                f"Executor '{preferred}' is unavailable and fallback is '{fallback_name}'"
            )

        return self._create_with_fallback(name=fallback_name, visited=visited)

    def _build_executor(self, name: str) -> Optional[SolverExecutor]:
        executor_class = self._load_executor_class(name)
        if executor_class is None:
            return None

        if name == "openfoam-docker":
            docker_config = self._solver_config.get("docker", {}) or self.config.get("docker", {})
            case_root = docker_config.get("case_root", DEFAULT_CASE_ROOT)
            case_generator = OpenFOAMCaseGenerator(str(case_root))

            try:
                return executor_class(
                    case_generator=case_generator,
                    image=docker_config.get("image", DEFAULT_IMAGE),
                    timeout=docker_config.get("timeout", 600),
                    memory_limit=docker_config.get("memory_limit", "4g"),
                    config=self.config,
                )
            except TypeError:
                pass

        try:
            return executor_class(self.config)
        except TypeError:
            return executor_class(config=self.config)

    def _load_executor_class(self, name: str) -> Optional[type]:
        import_target = self._EXECUTOR_IMPORTS.get(name)
        if import_target is None:
            return None

        module_name, class_name = import_target
        try:
            module = importlib.import_module(module_name)
        except (ImportError, AttributeError):
            return None

        return getattr(module, class_name, None)

    def _executor_available(self, name: str) -> bool:
        if name == "mock":
            return True

        if name.endswith("-docker") and not self._docker_environment_available():
            return False

        executor = self._build_executor(name)
        if executor is None:
            return False

        try:
            return bool(executor.validate())
        except Exception:
            return False

    @staticmethod
    def _docker_environment_available() -> bool:
        docker_binary = shutil.which("docker")
        if docker_binary is None:
            return False

        try:
            result = subprocess.run(
                [docker_binary, "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False

        return result.returncode == 0
