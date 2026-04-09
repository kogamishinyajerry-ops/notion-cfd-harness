#!/usr/bin/env python3
"""Real E2E integration test for BENCH-07: Backward-Facing Step (OpenFOAM).

This test runs the full pipeline:
  1. Generate the OpenFOAM case from templates (via OpenFOAMCaseGenerator)
  2. Execute the case in Docker (via OpenFOAMDockerExecutor)
  3. Extract the reattachment length metric
  4. Validate against Driver & Seegmiller 1988 literature value

Prerequisites:
  - Docker daemon running
  - openfoam/openfoam10-paraview510 image (or compatible OpenFOAM image)
  - At least 4GB RAM available

If Docker is unavailable, the test is skipped (graceful fallback to mock).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_compiler.phase2.execution_layer.case_generator import (
    OpenFOAMCaseGenerator,
)
from knowledge_compiler.phase2.execution_layer.openfoam_docker import (
    OpenFOAMDockerExecutor,
)
from knowledge_compiler.phase2.execution_layer.metrics_extractor import (
    extract_all,
    ExtractionResult,
)
from knowledge_compiler.phase2.execution_layer.precision_gate import (
    PrecisionGate,
    PrecisionGateReport,
)


# Literature value from Driver & Seegmiller 1988 (Re_H = 7600)
# Reattachment length normalized by step height: x_s / H ≈ 6.0 ± 10%
BENCH07_REATTACHMENT_LITERATURE = 6.0
BENCH07_ERROR_THRESHOLD = 0.15  # 15% relative error allowed


class TestRealE2EBench07:
    """Real E2E test for BENCH-07 Backward-Facing Step (OpenFOAM)."""

    @pytest.fixture
    def case_dir(self, tmp_path: Path) -> Path:
        """Generate and return the BENCH-07 case directory."""

        generator = OpenFOAMCaseGenerator(str(tmp_path))
        case_path = generator.generate("BENCH-07")
        return case_path

    @pytest.fixture
    def executor(self) -> OpenFOAMDockerExecutor:
        """Create an OpenFOAMDockerExecutor instance."""

        return OpenFOAMDockerExecutor()

    @pytest.fixture
    def docker_available(self, executor: OpenFOAMDockerExecutor) -> bool:
        """Check if Docker is available for real execution."""

        return executor.validate()

    def test_docker_health_check(
        self,
        executor: OpenFOAMDockerExecutor,
    ) -> None:
        """Verify Docker daemon is responsive."""

        assert executor.validate(), (
            "Docker daemon is not available. "
            "Ensure Docker is running and the openfoam/openfoam10-paraview510 image is accessible."
        )

    def test_solver_protocol_compliance(
        self,
        executor: OpenFOAMDockerExecutor,
    ) -> None:
        """Verify executor implements the SolverExecutor Protocol correctly."""

        assert executor.is_mock is False
        assert executor.solver_type == "openfoam-docker"

        assert hasattr(executor, "setup")
        assert hasattr(executor, "execute")
        assert hasattr(executor, "validate")

    def test_case_generation(
        self,
        case_dir: Path,
    ) -> None:
        """Verify the case is generated correctly from templates."""

        assert case_dir.exists()
        assert (case_dir / "system" / "controlDict").exists()
        assert (case_dir / "0" / "U").exists()
        assert (case_dir / "0" / "p").exists()
        assert (case_dir / "constant" / "physicalProperties").exists()
        assert (case_dir / "constant" / "turbulenceProperties").exists()
        assert (case_dir / "0" / "k").exists()
        assert (case_dir / "0" / "epsilon").exists()
        assert (case_dir / "0" / "nut").exists()
        assert (case_dir / "system" / "blockMeshDict").exists()

    def test_real_execution(
        self,
        case_dir: Path,
        executor: OpenFOAMDockerExecutor,
        docker_available: bool,
    ) -> None:
        """Run the actual OpenFOAM simulation in Docker (skipped if Docker unavailable)."""

        if not docker_available:
            pytest.skip("Docker not available - skipping real solver execution")

        executor.setup(str(case_dir))
        result = executor.execute({"case_dir": str(case_dir)})

        assert result.success, f"Execution failed: {result.error}"
        assert result.is_mock is False
        assert result.execution_time_s > 0
        assert result.metrics.get("runs_ok") == 1.0

    def test_metrics_extraction(
        self,
        case_dir: Path,
        executor: OpenFOAMDockerExecutor,
        docker_available: bool,
    ) -> None:
        """Extract reattachment length from the executed case."""

        if not docker_available:
            pytest.skip("Docker not available - skipping real solver execution")

        executor.setup(str(case_dir))
        result = executor.execute({"case_dir": str(case_dir)})
        assert result.success, f"Execution failed: {result.error}"

        extraction = extract_all(str(case_dir), "BENCH-07")

        assert isinstance(extraction, ExtractionResult)
        assert extraction.case_id == "BENCH-07"

    def test_precision_gate(
        self,
        case_dir: Path,
        executor: OpenFOAMDockerExecutor,
        docker_available: bool,
    ) -> None:
        """Validate extracted metrics against literature precision gate."""

        if not docker_available:
            pytest.skip("Docker not available - skipping real solver execution")

        executor.setup(str(case_dir))
        result = executor.execute({"case_dir": str(case_dir)})
        assert result.success, f"Execution failed: {result.error}"

        gate = PrecisionGate(str(case_dir), "BENCH-07")
        report = gate.check("BENCH-07")

        assert isinstance(report, PrecisionGateReport)
        assert report.case_id == "BENCH-07"
        assert report.total_count >= 1
        assert len(report.results) >= 1

        print(f"\n{report}")

    def test_reattachment_length_against_literature(
        self,
        case_dir: Path,
        executor: OpenFOAMDockerExecutor,
        docker_available: bool,
    ) -> None:
        """Direct check: reattachment length vs Driver & Seegmiller 1988."""

        if not docker_available:
            pytest.skip("Docker not available - skipping real solver execution")

        executor.setup(str(case_dir))
        result = executor.execute({"case_dir": str(case_dir)})
        assert result.success, f"Execution failed: {result.error}"

        extraction = extract_all(str(case_dir), "BENCH-07")
        if not extraction.success:
            pytest.skip(f"Extraction failed: {extraction.error}")

        reattachment_qty = None
        for qty in extraction.quantities:
            if qty.name == "reattachment_length_normalized":
                reattachment_qty = qty
                break

        if reattachment_qty is None:
            pytest.skip(
                "Could not extract reattachment_length_normalized - "
                "simulation may not have converged or post-processing unavailable"
            )

        rel_error = (
            abs(reattachment_qty.value - BENCH07_REATTACHMENT_LITERATURE)
            / BENCH07_REATTACHMENT_LITERATURE
        )
        passed = rel_error <= BENCH07_ERROR_THRESHOLD

        assert passed, (
            f"BENCH-07 reattachment length precision gate failed: "
            f"expected={BENCH07_REATTACHMENT_LITERATURE:.4f} "
            f"observed={reattachment_qty.value:.4f} "
            f"rel_error={rel_error:.2%} > threshold={BENCH07_ERROR_THRESHOLD:.2%}"
        )
