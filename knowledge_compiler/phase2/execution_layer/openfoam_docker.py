#!/usr/bin/env python3
"""OpenFOAMDockerExecutor — runs OpenFOAM in a Docker container."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional

from dataclasses import dataclass

from .case_generator import OpenFOAMCaseGenerator
from .solver_protocol import SolverResult


@dataclass
class StreamingResult:
    container_id: Optional[str]
    solver_result: SolverResult

DEFAULT_IMAGE = "openfoam/openfoam10-paraview510"
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
            [docker_binary, "pull", "--platform=linux/amd64", self.image],
            check=True,
            timeout=300,
        )

    def _run_block_mesh(self, case_dir: Path) -> None:
        """Run ``blockMesh`` to create the mesh for the case."""

        self._run_in_container(
            case_dir=case_dir,
            command="blockMesh > /case/log.blockMesh 2>&1",
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
            command=f"{solver} > /case/log.{solver} 2>&1",
            timeout=self.timeout,
        )

    def _run_in_container(self, case_dir: Path, command: str, timeout: int) -> None:
        docker_binary = self._docker_binary()
        # Override entry.sh using --entrypoint /bin/bash with -c.
        # Use a single bash -c with && chaining so bashrc is sourced in the
        # same shell that runs the solver command, ensuring PATH is set.
        subprocess.run(
            [
                docker_binary,
                "run",
                "--rm",
                "-v=%s:/case" % case_dir.resolve(),
                "-w=/case",
                "--memory=%s" % self.memory_limit,
                "--user=%s:%s" % (os.getuid(), os.getgid()),
                "--platform=linux/amd64",
                "--entrypoint=/bin/bash",
                self.image,
                "-c",
                "source /opt/openfoam10/etc/bashrc && %s" % command,
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

    async def execute_streaming(
        self,
        config: dict[str, Any],
        residual_callback: "Callable[[Dict[str, Any]], Any]",
    ) -> SolverResult:
        """
        Run solver with real-time residual streaming.

        Args:
            config: Runtime configuration with case_id, solver, etc.
            residual_callback: Async callback called with each residual dict:
                {
                    "iteration": int,
                    "time_value": float,
                    "residuals": Dict[str, float],
                    "status": str,  # running | converged | diverged | stalled
                }

        Returns:
            StreamingResult containing container_id (for abort) and solver_result
        """
        import asyncio

        started_at = time.time()
        runtime_config = {**self._config, **(config or {})}
        captured_container_id: Optional[str] = None

        try:
            case_dir = self._prepare_case_dir(runtime_config)
            self._ensure_image()
            self._run_block_mesh(case_dir)

            case_id = runtime_config.get("case_id") or case_dir.name
            solver = self._get_solver_command(str(case_id))

            # Run solver with streaming residual capture
            captured_container_id, solver_result = await self._run_solver_streaming(
                case_dir=case_dir,
                solver=solver,
                residual_callback=residual_callback,
            )

            # Clean up container after solver exits
            if captured_container_id:
                try:
                    docker_binary = self._docker_binary()
                    proc = await asyncio.create_subprocess_exec(
                        docker_binary, "rm", captured_container_id,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await proc.communicate()
                except Exception:
                    pass  # Best effort cleanup

            return StreamingResult(
                container_id=captured_container_id,
                solver_result=SolverResult(
                    success=solver_result.get("success", True),
                    is_mock=self.is_mock,
                    output_dir=str(case_dir),
                    metrics=self._extract_metrics(case_dir, str(case_id)),
                    error=solver_result.get("error"),
                    execution_time_s=time.time() - started_at,
                ),
            )
        except Exception as exc:
            return StreamingResult(
                container_id=captured_container_id,
                solver_result=SolverResult(
                    success=False,
                    is_mock=self.is_mock,
                    output_dir="",
                    metrics={},
                    error=str(exc),
                    execution_time_s=time.time() - started_at,
                ),
            )

    async def _run_solver_streaming(
        self,
        case_dir: Path,
        solver: str,
        residual_callback: "Callable[[Dict[str, Any]], Any]",
    ) -> tuple[Optional[str], dict[str, Any]]:
        """
        Run solver asynchronously with streaming stdout parsing.

        Returns:
            Tuple of (container_id, result_dict)
        """
        import asyncio
        import re

        docker_binary = self._docker_binary()
        cmd = f"source /opt/openfoam10/etc/bashrc && {solver} 2>&1"

        # Start container in detached mode (no --rm so we keep container_id)
        proc = await asyncio.create_subprocess_exec(
            docker_binary,
            "run",
            "-d",  # detached
            "-v=%s:/case" % case_dir.resolve(),
            "-w=/case",
            "--memory=%s" % self.memory_limit,
            "--user=%s:%s" % (os.getuid(), os.getgid()),
            "--platform=linux/amd64",
            "--entrypoint=/bin/bash",
            self.image,
            "-c",
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            bufsize=1,  # line buffering
        )

        # Read container ID from first line of stdout (docker run -d outputs container ID)
        container_id_bytes = await proc.stdout.readline()
        container_id = container_id_bytes.decode().strip()

        # Parse streaming output for residuals
        time_pattern = re.compile(r"Time = ([\d.]+)")
        residual_pattern = re.compile(r"(Ux|Uy|Uz|p)\s*=\s*([\d.e+-]+)")

        current_iteration = 0
        current_time_value = 0.0
        current_residuals: dict[str, float] = {}
        last_callback_time = 0.0

        loop = asyncio.get_event_loop()

        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break  # EOF

            line = line_bytes.decode().strip()

            # Parse time
            time_match = time_pattern.search(line)
            if time_match:
                current_time_value = float(time_match.group(1))
                current_iteration = int(current_time_value)
                current_residuals = {}

            # Parse residuals
            for field in ["Ux", "Uy", "Uz", "p"]:
                match = residual_pattern.search(line)
                if match:
                    field_name, field_val = match.group(1), match.group(2)
                    try:
                        current_residuals[field_name] = float(field_val)
                    except ValueError:
                        pass

            # Commit residuals on solver info lines (Initial/Final residual, ExecutionTime)
            if current_residuals and ("Initial residual" in line or "Final residual" in line or "ExecutionTime" in line):
                now = loop.time()
                if now - last_callback_time >= 0.5:
                    await residual_callback({
                        "iteration": current_iteration,
                        "time_value": current_time_value,
                        "residuals": dict(current_residuals),
                        "status": "running",
                    })
                    last_callback_time = now

            # Check for solver completion
            if "End" in line and "ExecutionTime" in line:
                # Solver finished — do a final callback
                if current_residuals:
                    await residual_callback({
                        "iteration": current_iteration,
                        "time_value": current_time_value,
                        "residuals": dict(current_residuals),
                        "status": "converged",
                    })
                break

        # Wait for container to fully exit
        await proc.wait()

        return container_id, {"success": proc.returncode == 0}
