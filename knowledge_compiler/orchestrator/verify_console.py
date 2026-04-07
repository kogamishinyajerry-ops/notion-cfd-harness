#!/usr/bin/env python3
"""
Verify Console - Phase3 Result Verification
Phase 3: Knowledge-Driven Orchestrator

Validates CFD results against Phase2 benchmark validators.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, field

# Import Phase2 executables
sys.path.insert(0, str(Path(__file__).parent.parent / "executables"))

try:
    from formula_validator import L1, L2, relative_error, GCI
    from bench_ghia1982 import run_benchmark as ghia1982_bench
    from bench_naca import run_benchmark as naca_bench
    import chart_template
except ImportError as e:
    print(f"Warning: Could not import Phase2 executables: {e}")
    L1 = L2 = relative_error = GCI = None
    ghia1982_bench = naca_bench = None
    chart_template = None


from knowledge_compiler.orchestrator.contract import (
    VerificationReport,
    BenchmarkResult,
    ChartType,
    ConvergenceStatus,
)


# =============================================================================
# Verify Console Implementation
# =============================================================================

@dataclass
class VerifyConsole:
    """
    Verification Console for CFD results.

    Calls Phase2 executables:
    - formula_validator.py: L1/L2/relative_error/GCI
    - bench_ghia1982.py: Case1 Lid Cavity validation
    - bench_naca.py: Case2 NACA VAWT validation
    - chart_template.py: velocity/contour/GCI charts
    """

    results_path: Path = field(default_factory=lambda: Path.cwd())
    phase2_executables_path: Path = field(default_factory=lambda: Path(__file__).parent.parent / "executables")

    def verify_benchmark(self, case_id: str = "CASE-001") -> BenchmarkResult:
        """
        Run Phase2 benchmark validator.

        Args:
            case_id: "CASE-001" (Ghia1982) or "CASE-002" (NACA VAWT)

        Returns:
            BenchmarkResult with pass/fail status
        """
        if case_id == "CASE-001":
            if ghia1982_bench is None:
                return BenchmarkResult(
                    benchmark_id=case_id,
                    validator_used="bench_ghia1982.py",
                    is_passed=False,
                    notes="Phase2 executable not available"
                )

            result = ghia1982_bench()
            return BenchmarkResult(
                benchmark_id=case_id,
                validator_used="bench_ghia1982.py",
                is_passed=result.get("overall_pass", False),
                error_metrics={
                    "vortex_center_error_x": result.get("vortex_center", {}).get("error_x_pct", 0),
                    "vortex_center_error_y": result.get("vortex_center", {}).get("error_y_pct", 0),
                    "max_velocity_error": result.get("centerline_velocity", {}).get("max_error_pct", 0),
                },
                notes=result.get("overall_pass", "PASS" if result.get("overall_pass") else "FAIL")
            )

        elif case_id == "CASE-002":
            if naca_bench is None:
                return BenchmarkResult(
                    benchmark_id=case_id,
                    validator_used="bench_naca.py",
                    is_passed=False,
                    notes="Phase2 executable not available"
                )

            result = naca_bench()
            return BenchmarkResult(
                benchmark_id=case_id,
                validator_used="bench_naca.py",
                is_passed=result.get("overall_pass", False),
                error_metrics={
                    "mean_error_pct": result.get("ct_tsr_validation", {}).get("mean_error_pct", 0),
                    "mean_error_excl_ds_pct": result.get("ct_tsr_validation", {}).get("mean_error_excl_dynamic_stall_pct", 0),
                },
                notes=result.get("physical_note", "")
            )

        return BenchmarkResult(
            benchmark_id=case_id,
            validator_used="unknown",
            is_passed=False,
            notes=f"Unknown case_id: {case_id}"
        )

    def generate_charts(self, data_sources: Dict[str, Any], output_dir: Path) -> Dict[ChartType, str]:
        """
        Generate standard charts using Phase2 chart_template.py.

        Args:
            data_sources: Dict with keys "y_H", "u_exp", "u_cfd", etc.
            output_dir: Where to save chart files

        Returns:
            Dict mapping ChartType to file paths
        """
        if chart_template is None:
            return {}

        charts = {}

        # Velocity profile chart
        if "y_H" in data_sources and "u_exp" in data_sources and "u_cfd" in data_sources:
            fig = chart_template.plot_velocity_profile(
                data_sources["y_H"],
                data_sources["u_exp"],
                data_sources["u_cfd"],
                save_path=str(output_dir / "velocity_profile.png")
            )
            charts[ChartType.VELOCITY_PROFILE] = str(output_dir / "velocity_profile.png")

        # GCI chart
        if "levels" in data_sources and "values" in data_sources:
            fig = chart_template.plot_gci_convergence(
                data_sources["levels"],
                data_sources["values"],
                save_path=str(output_dir / "gci_convergence.png")
            )
            charts[ChartType.GCI_CONVERGENCE] = str(output_dir / "gci_convergence.png")

        return charts

    def run_full_verification(self, case_id: str, results_data: Dict[str, Any]) -> VerificationReport:
        """
        Run complete verification: benchmarks + charts + conclusion.

        Args:
            case_id: "CASE-001" or "CASE-002"
            results_data: Dict with simulation results

        Returns:
            VerificationReport with all findings
        """
        timestamp = datetime.now()

        # Run benchmark
        benchmark = self.verify_benchmark(case_id)

        # Generate charts
        output_dir = self.results_path / "verification"
        output_dir.mkdir(exist_ok=True)
        charts = self.generate_charts(results_data, output_dir)

        # Determine overall pass
        # F-P2-007: Dual threshold for NACA bench
        if case_id == "CASE-002":
            mean_error = benchmark.error_metrics.get("mean_error_pct", 100)
            mean_error_excl_ds = benchmark.error_metrics.get("mean_error_excl_ds_pct", 100)
            # Dual threshold: <10% overall OR <5% excluding dynamic stall
            overall_pass = (mean_error < 10.0) or (mean_error_excl_ds < 5.0)
        else:
            overall_pass = benchmark.is_passed

        # Build conclusion
        conclusion = self._build_conclusion(benchmark, overall_pass)

        # Check if Opus review needed
        requires_review = not overall_pass or "expected" in benchmark.notes.lower()

        report = VerificationReport(
            case_id=case_id,
            timestamp=timestamp,
            charts=charts,
            benchmarks=[benchmark],
            overall_pass=overall_pass,
            conclusion=conclusion,
            requires_review=requires_review,
            review_reason="Benchmark validation failed" if not overall_pass else ""
        )

        return report

    def _build_conclusion(self, benchmark: BenchmarkResult, overall_pass: bool) -> str:
        """Build conclusion text."""
        if overall_pass:
            return f"Benchmark {benchmark.benchmark_id} PASSED using {benchmark.validator_used}"
        else:
            return f"Benchmark {benchmark.benchmark_id} FAILED: {benchmark.notes}"


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for verification."""
    import argparse

    parser = argparse.ArgumentParser(description="Verify CFD results against Phase2 benchmarks")
    parser.add_argument("--case", default="CASE-001", help="Case ID (CASE-001 or CASE-002)")
    parser.add_argument("--results", help="Path to simulation results JSON")
    parser.add_argument("--output", default="verification_report.json", help="Output report path")

    args = parser.parse_args()

    console = VerifyConsole()

    # TODO: Load results_data from args.results
    results_data = {}

    report = console.run_full_verification(args.case, results_data)

    # Save report
    import json
    with open(args.output, "w") as f:
        json.dump(report, f, default=str, indent=2)

    print(f"Verification complete: {report.overall_pass}")
    print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()
