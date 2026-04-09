#!/usr/bin/env python3
"""SU2DockerExecutor — runs SU2 (Stanford University Unstructured) in a Docker container.

This executor supports SU2 whitelist cases defined in cold_start_whitelist.yaml.
SU2 is typically used for:
  - Inviscid compressible flows (NACA airfoils, channels)
  - Laminar/turbulent flows with various turbulence models
  - Shape optimization (SU2_CFD + SU2_DOT)

The executor follows the same SolverExecutor Protocol as OpenFOAMDockerExecutor,
allowing transparent switching via ExecutorFactory.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from .solver_protocol import SolverExecutor, SolverResult

DEFAULT_IMAGE = "tenzardockerhub/su2"
DEFAULT_CASE_ROOT = "/tmp/su2-cases"


class SU2DockerExecutor:
    """Runs SU2_CFD in a Docker container.

    Supports all SU2 cases from the cold_start_whitelist.yaml that use
    ``SU2_CFD <config>.cfg`` as the solver command.
    """

    def __init__(
        self,
        image: str = DEFAULT_IMAGE,
        timeout: int = 600,
        memory_limit: str = "4g",
        config: Optional[dict[str, Any]] = None,
    ):
        if isinstance(image, dict) and config is None:
            config = image
            image = DEFAULT_IMAGE

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
        self._case_dir: Optional[Path] = None

    @property
    def is_mock(self) -> bool:
        return False

    @property
    def solver_type(self) -> str:
        return "su2-docker"

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
        """Run SU2_CFD in Docker and return metrics.

        The config dict should contain:
          - case_dir: Path to the prepared SU2 case directory
          - config_file: Name of the SU2 config file (default: "inv_channel.cfg")
        """

        started_at = time.time()
        runtime_config = {**self._config, **(config or {})}
        output_dir = self._output_dir_hint(runtime_config)

        try:
            case_dir = self._resolve_case_dir(runtime_config)
            self._ensure_image()
            config_file = runtime_config.get("config_file", "inv_channel.cfg")
            self._run_su2(case_dir, config_file)

            return SolverResult(
                success=True,
                is_mock=self.is_mock,
                output_dir=str(case_dir),
                metrics=self._extract_metrics(case_dir),
                error=None,
                execution_time_s=time.time() - started_at,
            )
        except Exception as exc:  # noqa: BLE001
            return SolverResult(
                success=False,
                is_mock=self.is_mock,
                output_dir=output_dir,
                metrics={},
                error=str(exc),
                execution_time_s=time.time() - started_at,
            )

    def _resolve_case_dir(self, runtime_config: dict[str, Any]) -> Path:
        case_dir = runtime_config.get("case_dir") or runtime_config.get("output_dir")
        if isinstance(case_dir, str) and case_dir:
            candidate = Path(case_dir)
            if candidate.exists():
                self._case_dir = candidate
                return candidate

        if self._case_dir is not None and self._case_dir.exists():
            return self._case_dir

        raise ValueError("SU2 execution requires a valid case_dir")

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

    def _run_su2(self, case_dir: Path, config_file: str) -> None:
        """Run ``SU2_CFD`` inside the Docker container."""

        config_path = case_dir / config_file
        if not config_path.exists():
            raise FileNotFoundError(
                f"SU2 config file not found: {config_path}"
            )

        self._run_in_container(
            case_dir=case_dir,
            command=f"SU2_CFD {config_file} > /case/log.SU2_CFD 2>&1",
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
                "--platform=linux/amd64",  # SU2 image is amd64 only
                self.image,
                "bash",
                "-lc",
                command,
            ],
            check=True,
            timeout=timeout,
        )

    def _extract_metrics(self, case_dir: Path) -> dict[str, float]:
        """Parse basic run metrics from the SU2 output directory."""

        log_file = case_dir / "log.SU2_CFD"
        if not log_file.exists():
            return {"runs_ok": 0.0}

        try:
            text = log_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {"runs_ok": 0.0}

        # Check for common SU2 success indicators
        success_indicators = [
            "SU2 run completed",
            " Finished",
            "Simulation completed successfully",
        ]
        runs_ok = 1.0 if any(ind in text for ind in success_indicators) else 0.0

        # Try to extract objective function value (common in SU2 output)
        obj_value: float | None = None
        for line in text.splitlines():
            if "OPT_OBJFUNC" in line or "Total CL" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    try:
                        if i + 1 < len(parts):
                            obj_value = float(parts[i + 1])
                            break
                    except ValueError:
                        continue

        metrics: dict[str, float] = {"runs_ok": runs_ok}
        if obj_value is not None:
            metrics["objective_function"] = obj_value

        return metrics


# Ensure SU2DockerExecutor satisfies the SolverExecutor Protocol
assert hasattr(SU2DockerExecutor, "is_mock")
assert hasattr(SU2DockerExecutor, "solver_type")
assert hasattr(SU2DockerExecutor, "setup")
assert hasattr(SU2DockerExecutor, "execute")
assert hasattr(SU2DockerExecutor, "validate")
