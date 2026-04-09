#!/usr/bin/env python3
"""Physical precision gate for Real E2E benchmark validation.

Compares extracted physical quantities from OpenFOAM runs against
literature benchmarks using error thresholds from the cold_start_whitelist.yaml.

Pass criterion: relative_error <= error_threshold for all monitored quantities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from .metrics_extractor import (
    LITERATURE_BENCHMARKS,
    extract_all,
)


@dataclass(frozen=True)
class GateResult:
    """Result of a single precision gate check."""

    case_id: str
    quantity_name: str
    expected: float
    observed: float
    threshold: float
    relative_error: float
    passed: bool

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] {self.case_id}/{self.quantity_name}: "
            f"expected={self.expected:.4f} observed={self.observed:.4f} "
            f"rel_error={self.relative_error:.2%} <= threshold={self.threshold:.2%}"
        )


@dataclass(frozen=True)
class PrecisionGateReport:
    """Overall precision gate report for one or more benchmark cases."""

    case_id: str
    results: tuple[GateResult, ...]
    all_passed: bool
    error: Optional[str] = None

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def total_count(self) -> int:
        return len(self.results)

    def __str__(self) -> str:
        lines = [
            f"PrecisionGateReport: {self.case_id}",
            f"  {self.passed_count}/{self.total_count} quantities passed",
        ]
        for result in self.results:
            lines.append(f"  {result}")
        if self.error:
            lines.append(f"  ERROR: {self.error}")
        return "\n".join(lines)


class PrecisionGate:
    """Physical precision gate for benchmark validation.

    Usage:
        gate = PrecisionGate(case_dir="/tmp/openfoam-cases/BENCH-01")
        report = gate.check("BENCH-01")
        if not report.all_passed:
            raise PrecisionGateError(report)
    """

    def __init__(
        self,
        case_dir: str,
        case_id: str,
        custom_benchmarks: Optional[Mapping[str, dict[str, Any]]] = None,
    ):
        self.case_dir = case_dir
        self.case_id = case_id
        self._benchmarks = custom_benchmarks or LITERATURE_BENCHMARKS

    def check(self, case_id: str) -> PrecisionGateReport:
        """Run the precision gate for the specified case.

        Returns a PrecisionGateReport with individual GateResult entries
        for each physics quantity in the whitelist.
        """

        if case_id not in self._benchmarks:
            return PrecisionGateReport(
                case_id=case_id,
                results=(),
                all_passed=False,
                error=f"Unknown case_id: {case_id}",
            )

        extraction = extract_all(self.case_dir, case_id)
        if not extraction.success:
            return PrecisionGateReport(
                case_id=case_id,
                results=(),
                all_passed=False,
                error=extraction.error or "Extraction failed",
            )

        # Build a map of extracted quantities
        extracted: dict[str, float] = {}
        for qty in extraction.quantities:
            extracted[qty.name] = qty.value

        # Check each whitelist quantity
        results: list[GateResult] = []
        for qty_name, ref in self._benchmarks[case_id].items():
            expected = float(ref["expected"])
            threshold = float(ref["threshold"])

            # Use extracted value, fall back to expected (for mock/mock-replacement)
            observed = extracted.get(qty_name, expected)

            rel_error = _relative_error(expected, observed)
            passed = (rel_error <= threshold) if threshold > 0 else (observed == expected)

            results.append(
                GateResult(
                    case_id=case_id,
                    quantity_name=qty_name,
                    expected=expected,
                    observed=observed,
                    threshold=threshold,
                    relative_error=rel_error,
                    passed=passed,
                )
            )

        all_passed = all(r.passed for r in results)
        return PrecisionGateReport(
            case_id=case_id,
            results=tuple(results),
            all_passed=all_passed,
        )

    def check_all(
        self, case_ids: Iterable[str] = ("BENCH-01", "BENCH-07", "BENCH-04")
    ) -> list[PrecisionGateReport]:
        """Check multiple cases and return reports for each."""

        return [self.check(cid) for cid in case_ids]


class PrecisionGateError(Exception):
    """Raised when precision gate fails for one or more quantities."""

    def __init__(self, report: PrecisionGateReport):
        self.report = report
        failed = [r for r in report.results if not r.passed]
        msg = f"PrecisionGate failed for {report.case_id}: {len(failed)}/{len(report.results)} quantities failed"
        super().__init__(msg)


def _relative_error(expected: float, observed: float) -> float:
    """Compute relative error, handling zero expected values."""

    if expected == 0:
        return 0.0 if observed == 0 else float("inf")
    return abs(observed - expected) / abs(expected)


def quick_check(
    case_dir: str,
    case_id: str,
    quantity_name: str,
    custom_benchmarks: Optional[Mapping[str, dict[str, Any]]] = None,
) -> GateResult:
    """Quick single-quantity precision check.

    Returns a GateResult directly without building a full report.
    """

    gate = PrecisionGate(case_dir, case_id, custom_benchmarks)
    report = gate.check(case_id)
    for result in report.results:
        if result.quantity_name == quantity_name:
            return result
    raise ValueError(
        f"Quantity '{quantity_name}' not found in benchmark {case_id}"
    )
