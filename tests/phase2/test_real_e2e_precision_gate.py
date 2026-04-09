#!/usr/bin/env python3
"""Phase 7.7: Physical precision validation gate across all benchmark cases.

This is the end-to-end precision gate test that validates all three cases
(BENCH-01, BENCH-07, BENCH-04) against literature benchmarks.

Prerequisites:
  - Docker daemon running
  - openfoam/openfoam10-paraview510 image
  - At least 8GB RAM for running all three cases sequentially

If Docker is unavailable, all tests are skipped.
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
)
from knowledge_compiler.phase2.execution_layer.precision_gate import (
    PrecisionGate,
    PrecisionGateReport,
)


class TestPhase7PrecisionGate:
    """Phase 7.7: Physical precision validation across all benchmark cases."""

    @pytest.fixture
    def executor(self) -> OpenFOAMDockerExecutor:
        """Create an OpenFOAMDockerExecutor instance."""

        return OpenFOAMDockerExecutor()

    @pytest.fixture
    def docker_available(self, executor: OpenFOAMDockerExecutor) -> bool:
        """Check if Docker is available for real execution."""

        return executor.validate()

    @pytest.fixture
    def all_case_dirs(self, tmp_path: Path, executor: OpenFOAMDockerExecutor) -> dict[str, Path]:
        """Generate case directories for all three benchmarks."""

        if not executor.validate():
            pytest.skip("Docker not available")

        generator = OpenFOAMCaseGenerator(str(tmp_path))
        case_ids = ["BENCH-01", "BENCH-07", "BENCH-04"]
        return {cid: generator.generate(cid) for cid in case_ids}

    def test_precision_gate_bench01(
        self,
        all_case_dirs: dict[str, Path],
        executor: OpenFOAMDockerExecutor,
        docker_available: bool,
    ) -> None:
        """Precision gate for BENCH-01 (Lid-Driven Cavity)."""

        if not docker_available:
            pytest.skip("Docker not available")

        case_dir = all_case_dirs["BENCH-01"]

        executor.setup(str(case_dir))
        result = executor.execute({"case_dir": str(case_dir)})
        assert result.success, f"BENCH-01 execution failed: {result.error}"

        gate = PrecisionGate(str(case_dir), "BENCH-01")
        report = gate.check("BENCH-01")

        assert isinstance(report, PrecisionGateReport)
        print(f"\n=== BENCH-01 Precision Gate ===\n{report}")

        # At least the centerline_u_velocity should be validated
        assert report.total_count >= 1

        # Check that at least one quantity passed
        passed_count = sum(1 for r in report.results if r.passed)
        assert passed_count >= 1, (
            f"BENCH-01: all {report.total_count} quantities failed precision gate"
        )

    def test_precision_gate_bench07(
        self,
        all_case_dirs: dict[str, Path],
        executor: OpenFOAMDockerExecutor,
        docker_available: bool,
    ) -> None:
        """Precision gate for BENCH-07 (Backward-Facing Step)."""

        if not docker_available:
            pytest.skip("Docker not available")

        case_dir = all_case_dirs["BENCH-07"]

        executor.setup(str(case_dir))
        result = executor.execute({"case_dir": str(case_dir)})
        assert result.success, f"BENCH-07 execution failed: {result.error}"

        gate = PrecisionGate(str(case_dir), "BENCH-07")
        report = gate.check("BENCH-07")

        assert isinstance(report, PrecisionGateReport)
        print(f"\n=== BENCH-07 Precision Gate ===\n{report}")

        assert report.total_count >= 1

        passed_count = sum(1 for r in report.results if r.passed)
        assert passed_count >= 1, (
            f"BENCH-07: all {report.total_count} quantities failed precision gate"
        )

    def test_precision_gate_bench04(
        self,
        all_case_dirs: dict[str, Path],
        executor: OpenFOAMDockerExecutor,
        docker_available: bool,
    ) -> None:
        """Precision gate for BENCH-04 (Circular Cylinder Wake)."""

        if not docker_available:
            pytest.skip("Docker not available")

        case_dir = all_case_dirs["BENCH-04"]

        executor.setup(str(case_dir))
        result = executor.execute({"case_dir": str(case_dir)})
        assert result.success, f"BENCH-04 execution failed: {result.error}"

        gate = PrecisionGate(str(case_dir), "BENCH-04")
        report = gate.check("BENCH-04")

        assert isinstance(report, PrecisionGateReport)
        print(f"\n=== BENCH-04 Precision Gate ===\n{report}")

        assert report.total_count >= 1

        passed_count = sum(1 for r in report.results if r.passed)
        assert passed_count >= 1, (
            f"BENCH-04: all {report.total_count} quantities failed precision gate"
        )

    def test_all_cases_precision_summary(
        self,
        all_case_dirs: dict[str, Path],
        executor: OpenFOAMDockerExecutor,
        docker_available: bool,
    ) -> None:
        """Comprehensive precision gate summary across all three cases.

        This test runs the complete pipeline for all cases and produces
        a summary of precision gate results for Phase 7.7 validation.
        """

        if not docker_available:
            pytest.skip("Docker not available")

        results: dict[str, dict] = {}

        for case_id, case_dir in all_case_dirs.items():
            executor.setup(str(case_dir))
            result = executor.execute({"case_dir": str(case_dir)})

            gate = PrecisionGate(str(case_dir), case_id)
            report = gate.check(case_id)

            extraction = extract_all(str(case_dir), case_id)

            passed_count = sum(1 for r in report.results if r.passed)
            total_count = report.total_count

            results[case_id] = {
                "success": result.success,
                "execution_time_s": result.execution_time_s,
                "extraction_success": extraction.success,
                "gate_passed": passed_count,
                "gate_total": total_count,
                "report": report,
            }

            print(
                f"\n{case_id}: "
                f"exec={'OK' if result.success else 'FAIL'} "
                f"extract={'OK' if extraction.success else 'FAIL'} "
                f"gate={passed_count}/{total_count} passed"
            )

        # Summary assertion: all cases should have executed successfully
        # and produced at least some precision gate results
        for case_id in ["BENCH-01", "BENCH-07", "BENCH-04"]:
            assert results[case_id]["success"], f"{case_id}: execution failed"
            assert results[case_id]["gate_total"] >= 1, f"{case_id}: no gate results"

        # Overall: print the full reports
        print("\n" + "=" * 60)
        print("PHASE 7.7 PRECISION GATE SUMMARY")
        print("=" * 60)
        for case_id in ["BENCH-01", "BENCH-07", "BENCH-04"]:
            r = results[case_id]
            print(f"\n{case_id}:")
            print(f"  Execution time: {r['execution_time_s']:.1f}s")
            print(f"  Extraction: {'OK' if r['extraction_success'] else 'FAIL'}")
            print(f"  Gate: {r['gate_passed']}/{r['gate_total']} passed")
            for gr in r["report"].results:
                status = "PASS" if gr.passed else "FAIL"
                print(
                    f"    [{status}] {gr.quantity_name}: "
                    f"expected={gr.expected:.4f} observed={gr.observed:.4f} "
                    f"error={gr.relative_error:.1%}"
                )
