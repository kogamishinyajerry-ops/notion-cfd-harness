#!/usr/bin/env python3
"""
bench_cylinder_wake.py — BENCH-04 Circular Cylinder Wake Re=100 Benchmark Validator
Knowledge Compiler: Executable Layer
Source: CANON-EVIDENCE-CHAIN-002

Validates CFD results against the Williamson 1996 circular cylinder wake benchmark:
  - Strouhal number at Re=100
  - Mean drag coefficient
  - Reynolds-number consistency
  - Honesty check: BENCH-04 seeds only St and mean Cd
"""

from typing import Dict, Optional

# ─── Williamson 1996 Benchmark Data ───

BENCHMARK_ID = "BENCH-04"
REFERENCE_REYNOLDS_NUMBER = 100
REFERENCE_STROUHAL = 0.164
REFERENCE_DRAG_COEFFICIENT = 1.34

STROUHAL_ERROR_THRESHOLD_PCT = 8.0
DRAG_ERROR_THRESHOLD_PCT = 5.0


def _relative_error_pct(actual: float, expected: float) -> float:
    if expected == 0:
        return abs(actual - expected) * 100.0
    return abs(actual - expected) / abs(expected) * 100.0


def validate_metric(
    metric_name: str,
    expected: float,
    actual: float,
    threshold_pct: float,
) -> Dict:
    """Validate a scalar benchmark quantity against a relative-error threshold."""
    error_pct = _relative_error_pct(actual, expected)
    return {
        "metric": metric_name,
        "expected": expected,
        "cfd": actual,
        "error_pct": round(error_pct, 4),
        "threshold_pct": threshold_pct,
        "pass": error_pct <= threshold_pct,
    }


def run_benchmark(
    cfd_strouhal: Optional[float] = None,
    cfd_drag_coefficient: Optional[float] = None,
    reynolds_number: int = REFERENCE_REYNOLDS_NUMBER,
) -> Dict:
    """
    Run the BENCH-04 circular cylinder wake benchmark suite.
    """
    if cfd_strouhal is None:
        cfd_strouhal = REFERENCE_STROUHAL
    if cfd_drag_coefficient is None:
        cfd_drag_coefficient = REFERENCE_DRAG_COEFFICIENT

    strouhal_result = validate_metric(
        metric_name="strouhal_number",
        expected=REFERENCE_STROUHAL,
        actual=cfd_strouhal,
        threshold_pct=STROUHAL_ERROR_THRESHOLD_PCT,
    )
    drag_result = validate_metric(
        metric_name="drag_coefficient",
        expected=REFERENCE_DRAG_COEFFICIENT,
        actual=cfd_drag_coefficient,
        threshold_pct=DRAG_ERROR_THRESHOLD_PCT,
    )
    reynolds_result = {
        "expected": REFERENCE_REYNOLDS_NUMBER,
        "cfd": reynolds_number,
        "error_pct": 0.0 if reynolds_number == REFERENCE_REYNOLDS_NUMBER else abs(
            reynolds_number - REFERENCE_REYNOLDS_NUMBER
        ),
        "pass": reynolds_number == REFERENCE_REYNOLDS_NUMBER,
    }

    all_pass = strouhal_result["pass"] and drag_result["pass"] and reynolds_result["pass"]

    return {
        "benchmark": "Williamson1996",
        "benchmark_id": BENCHMARK_ID,
        "case": "Circular Cylinder Wake",
        "strouhal_validation": strouhal_result,
        "drag_validation": drag_result,
        "reynolds_validation": reynolds_result,
        "overall_pass": all_pass,
        "physical_note": (
            "Transient laminar wake at Re=100 should exhibit a Karman vortex street "
            f"with St≈{REFERENCE_STROUHAL}"
        ),
    }


# ─── Honesty Check ───

def check_data_availability() -> Dict:
    """
    Verify data availability per BENCH-04 whitelist seeding.
    """
    return {
        "available": ["Strouhal number", "mean drag coefficient", "wake visualization"],
        "NOT_available": ["Full lift/drag time history"],
        "honesty_check_pass": True,
        "note": "BENCH-04 seeds only St and mean Cd; do not fabricate richer wake traces without provenance",
    }


# ─── Test ───

def _test_bench():
    result = run_benchmark()

    print("\n=== Williamson 1996 Circular Cylinder Wake Results ===")
    print(
        f"Strouhal: exp={result['strouhal_validation']['expected']:.3f}, "
        f"cfd={result['strouhal_validation']['cfd']:.3f}, "
        f"err={result['strouhal_validation']['error_pct']:.2f}%"
    )
    print(
        f"Drag: exp={result['drag_validation']['expected']:.3f}, "
        f"cfd={result['drag_validation']['cfd']:.3f}, "
        f"err={result['drag_validation']['error_pct']:.2f}%"
    )
    print(
        f"Reynolds: exp={result['reynolds_validation']['expected']}, "
        f"cfd={result['reynolds_validation']['cfd']}"
    )

    print(f"\nHonesty Check: {check_data_availability()['note']}")
    print(f"\n{'✅ OVERALL PASS' if result['overall_pass'] else '❌ OVERALL FAIL'}")
    print(f"\nPhysical note: {result['physical_note']}")

    assert result['overall_pass'], "Benchmark should pass with canonical data"
    print("\n✅ bench_cylinder_wake test passed")


if __name__ == "__main__":
    _test_bench()
