#!/usr/bin/env python3
"""Deterministic M1 end-to-end mock demos for benchmark validation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, Iterable, Sequence


E2E_DEMO_CASES = ["BENCH-01", "BENCH-07", "BENCH-04"]


@dataclass(frozen=True)
class E2EResult:
    """Mock benchmark replay result used for CLI demos and tests."""

    case_id: str
    case_name: str
    platform: str
    metric_name: str
    expected_value: float
    observed_value: float
    error_threshold: float
    relative_error: float
    passed: bool
    summary: str

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"


_MOCK_CASE_LIBRARY: Dict[str, Dict[str, object]] = {
    "BENCH-01": {
        "case_name": "lid_driven_cavity_ghia_re100",
        "platform": "OpenFOAM",
        "metric_name": "centerline_u_velocity",
        "expected_value": 0.0625,
        "observed_value": 0.0610,
        "error_threshold": 0.10,
    },
    "BENCH-07": {
        "case_name": "backward_facing_step_driver_re7600",
        "platform": "OpenFOAM",
        "metric_name": "reattachment_length_normalized",
        "expected_value": 6.0,
        "observed_value": 5.85,
        "error_threshold": 0.10,
    },
    "BENCH-04": {
        "case_name": "circular_cylinder_wake_re100_vortex_street",
        "platform": "OpenFOAM",
        "metric_name": "strouhal_number",
        "expected_value": 0.164,
        "observed_value": 0.160,
        "error_threshold": 0.08,
    },
}


def _compute_relative_error(expected_value: float, observed_value: float) -> float:
    if expected_value == 0:
        return 0.0 if observed_value == 0 else float("inf")
    return abs(observed_value - expected_value) / abs(expected_value)


def get_mock_result_for_case(case_id: str) -> E2EResult:
    """Return a deterministic passing result for a supported benchmark case."""

    try:
        case_data = _MOCK_CASE_LIBRARY[case_id]
    except KeyError as exc:
        supported = ", ".join(E2E_DEMO_CASES)
        raise ValueError(
            f"Unsupported demo case '{case_id}'. Supported cases: {supported}."
        ) from exc

    expected_value = float(case_data["expected_value"])
    observed_value = float(case_data["observed_value"])
    error_threshold = float(case_data["error_threshold"])
    relative_error = _compute_relative_error(expected_value, observed_value)
    passed = relative_error <= error_threshold
    summary = (
        f"{case_id} {case_data['case_name']} {passed and 'PASS' or 'FAIL'} "
        f"{case_data['metric_name']} expected={expected_value:.4f} "
        f"observed={observed_value:.4f} rel_error={relative_error:.2%}"
    )

    return E2EResult(
        case_id=case_id,
        case_name=str(case_data["case_name"]),
        platform=str(case_data["platform"]),
        metric_name=str(case_data["metric_name"]),
        expected_value=expected_value,
        observed_value=observed_value,
        error_threshold=error_threshold,
        relative_error=relative_error,
        passed=passed,
        summary=summary,
    )


def run_e2e_mock_demo(case_id: str) -> E2EResult:
    """Run a single deterministic mock benchmark replay."""

    return get_mock_result_for_case(case_id)


def run_all_demos(case_ids: Iterable[str] = E2E_DEMO_CASES) -> list[E2EResult]:
    """Run all requested mock demos in order."""

    return [run_e2e_mock_demo(case_id) for case_id in case_ids]


def print_summary(results: Sequence[E2EResult]) -> str:
    """Print and return a stable CLI summary for the demo run."""

    passed_count = sum(result.passed for result in results)
    total_count = len(results)

    lines = ["AI-CFD Knowledge Harness M1 E2E Mock Demo"]
    for result in results:
        lines.append(
            f"[{result.status}] {result.case_id} {result.case_name} "
            f"{result.metric_name} expected={result.expected_value:.4f} "
            f"observed={result.observed_value:.4f} rel_error={result.relative_error:.2%}"
        )
    lines.append(f"Summary: {passed_count}/{total_count} PASS")

    output = "\n".join(lines)
    print(output)
    return output


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python -m knowledge_compiler.demos.e2e_mock_demo``."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case_ids",
        nargs="*",
        default=E2E_DEMO_CASES,
        help="Optional benchmark case IDs to run.",
    )
    args = parser.parse_args(argv)

    results = run_all_demos(args.case_ids)
    print_summary(results)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
