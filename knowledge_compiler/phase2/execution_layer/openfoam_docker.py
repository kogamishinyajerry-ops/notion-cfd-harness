#!/usr/bin/env python3
"""OpenFOAMDockerExecutor — runs OpenFOAM in a Docker container."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from .case_generator import OpenFOAMCaseGenerator
from .solver_protocol import SolverResult

DEFAULT_IMAGE = "openfoam/openfoam13-default"
DEFAULT_CASE_ROOT = "/tmp/openfoam-cases"


class OpenFOAMDockerExecutor:
    """Runs OpenFOAM in a Docker container."""

    def __init__(
        self,
        case_generator: Optional[OpenFOAMCaseGenerator] = None,
        image: str = DEFAULT_IMAGE,
        timeout: int = 600,
        memory_limit: str = "4g",
        config: Optional[dict[str, Any]] = None,
    ):
        if isinstance(case_generator, dict) and config is None:
            config = case_generator
            case_generator = None

        self._config = dict(config or {})
        solver_config = self._config.get("solver", {})
        docker_config = {}
        if isinstance(solver_config, dict):
            docker_config = solver_config.get("docker", {}) or {}

        if not docker_config and isinstance(self._config.get("docker"), dict):
            docker_config = self._config.get("docker", {}) or {}

        self.image = str(docker_config.get("image", image))
        self.timeout = int(docker_config.get("timeout", timeout))
        self.memory_limit = str(docker_config.get("memory_limit", memory_limit))

        case_root = str(docker_config.get("case_root", DEFAULT_CASE_ROOT))
        self.case_generator = case_generator or OpenFOAMCaseGenerator(case_root)
        self._case_dir: Optional[Path] = None

    @property
    def is_mock(self) -> bool:
        return False

    @property
    def solver_type(self) -> str:
        return "openfoam-docker"

    def setup(self, case_dir: str) -> None:
        """Store a prepared case directory for later execution."""

        self._case_dir = Path(case_dir)

    def validate(self) -> bool:
        """Check that Docker is available and the daemon is responsive."""

        docker_binary = shutil.which("docker")
        if docker_binary is None:
            return False

        try:
            result = subprocess.run(
                [docker_binary, "info"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False

        return result.returncode == 0

    def execute(self, config: dict[str, Any]) -> SolverResult:
        """Generate or reuse an OpenFOAM case, run it in Docker, and return metrics."""

        started_at = time.time()
        runtime_config = {**self._config, **(config or {})}
        output_dir = self._output_dir_hint(runtime_config)

        try:
            case_dir = self._prepare_case_dir(runtime_config)
            self._ensure_image()
            self._run_block_mesh(case_dir)

            case_id = runtime_config.get("case_id") or case_dir.name
            solver = self._get_solver_command(str(case_id))
            self._run_solver(case_dir, solver)

            return SolverResult(
                success=True,
                is_mock=self.is_mock,
                output_dir=str(case_dir),
                metrics=self._extract_metrics(case_dir, str(case_id)),
                error=None,
                execution_time_s=time.time() - started_at,
            )
        except Exception as exc:
            return SolverResult(
                success=False,
                is_mock=self.is_mock,
                output_dir=output_dir,
                metrics={},
                error=str(exc),
                execution_time_s=time.time() - started_at,
            )

    def _prepare_case_dir(self, runtime_config: dict[str, Any]) -> Path:
        case_id = runtime_config.get("case_id")
        if isinstance(case_id, str) and case_id:
            case_dir = self.case_generator.generate(case_id)
            self._case_dir = case_dir
            return case_dir

        if self._case_dir is not None and self._case_dir.exists():
            return self._case_dir

        case_dir = runtime_config.get("case_dir") or runtime_config.get("output_dir")
        if isinstance(case_dir, str) and case_dir:
            candidate = Path(case_dir)
            if candidate.exists():
                self._case_dir = candidate
                return candidate

        raise ValueError("OpenFOAM execution requires a valid case_id or prepared case_dir")

    def _output_dir_hint(self, runtime_config: dict[str, Any]) -> str:
        if self._case_dir is not None:
            return str(self._case_dir)

        output_dir = runtime_config.get("output_dir") or runtime_config.get("case_dir")
        if isinstance(output_dir, str):
            return output_dir

        return ""

    def _docker_binary(self) -> str:
        docker_binary = shutil.which("docker")
        if docker_binary is None:
            raise FileNotFoundError("docker executable not found")
        return docker_binary

    def _ensure_image(self) -> None:
        """Pull the Docker image if it does not exist locally."""

        docker_binary = self._docker_binary()
        result = subprocess.run(
            [docker_binary, "image", "inspect", self.image],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return

        subprocess.run(
            [docker_binary, "pull", self.image],
            check=True,
            timeout=300,
        )

    def _run_block_mesh(self, case_dir: Path) -> None:
        """Run ``blockMesh`` to create the mesh for the case."""

        self._run_in_container(
            case_dir=case_dir,
            command="blockMesh -case /case > /case/log.blockMesh 2>&1",
            timeout=60,
        )

    def _get_solver_command(self, case_id: str) -> str:
        """Map benchmark case IDs to the matching OpenFOAM solver binary."""

        solver_map = {
            "BENCH-01": "icoFoam",
            "BENCH-07": "simpleFoam",
            "BENCH-04": "pimpleFoam",
        }
        return solver_map.get(case_id, "simpleFoam")

    def _run_solver(self, case_dir: Path, solver: str) -> None:
        """Run the selected solver inside the Docker container."""

        self._run_in_container(
            case_dir=case_dir,
            command=f"{solver} -case /case > /case/log.{solver} 2>&1",
            timeout=self.timeout,
        )

    def _run_in_container(self, case_dir: Path, command: str, timeout: int) -> None:
        docker_binary = self._docker_binary()
        subprocess.run(
            [
                docker_binary,
                "run",
                "--rm",
                f"-v={case_dir.resolve()}:/case",
                f"--memory={self.memory_limit}",
                f"--user={os.getuid()}:{os.getgid()}",
                self.image,
                "bash",
                "-lc",
                command,
            ],
            check=True,
            timeout=timeout,
        )

    def _extract_metrics(self, case_dir: Path, case_id: str) -> dict[str, float]:
        """Parse basic run metrics from the generated case directory."""

        log_files = list(case_dir.glob("log.*"))
        return {
            "runs_ok": 1.0,
            "log_files_count": float(len(log_files)),
            "case_supported": float(case_id in OpenFOAMCaseGenerator.SUPPORTED_CASES),
        }
