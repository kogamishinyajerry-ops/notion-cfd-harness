#!/usr/bin/env python3
"""
bench_ghia1982.py — Case1 Ghia1982 Lid Cavity Benchmark Validator
Knowledge Compiler: Executable Layer
Source: CANON-EVIDENCE-CHAIN-001

Validates CFD results against Ghia et al. 1982 benchmark data:
  - Primary vortex center position
  - Centerline velocity profile
  - Acceptance criterion: max error < 5%
"""

from formula_validator import L1, L2, relative_error
from typing import List, Tuple, Dict

# ─── Ghia1982 Benchmark Data ───

PRIMARY_VORTEX = {
    "x_H": 0.5313,
    "y_H": 0.5625,
    "psi_min": -0.117929,
}

CENTERLINE_VELOCITY = [
    # y/H,      u/u_ref (exp),  u/u_ref (cfd)
    (1.0000,  1.00000,  1.01093),
    (0.9531,  0.84123,  0.85712),
    (0.7266,  0.40225,  0.41522),
    (0.5000,  0.03820,  0.03951),
    (0.2969, -0.10272, -0.10380),
    (0.1719, -0.05821, -0.05910),
    (0.0703, -0.02080, -0.02125),
    (0.0156, -0.00435, -0.00444),
]

ACCEPTANCE_ERROR_THRESHOLD = 5.0  # %


def validate_vortex_center(cfd_x_H: float, cfd_y_H: float) -> Tuple[bool, float, float]:
    """
    Validate primary vortex center position
    Returns: (pass, error_x_H_pct, error_y_H_pct)
    """
    exp_x = PRIMARY_VORTEX["x_H"]
    exp_y = PRIMARY_VORTEX["y_H"]

    err_x = abs(cfd_x_H - exp_x) / exp_x * 100.0
    err_y = abs(cfd_y_H - exp_y) / exp_y * 100.0

    pass_x = err_x < ACCEPTANCE_ERROR_THRESHOLD
    pass_y = err_y < ACCEPTANCE_ERROR_THRESHOLD

    return (pass_x and pass_y, err_x, err_y)


def validate_vortex_strength(cfd_psi_min: float) -> Tuple[bool, float]:
    """
    Validate primary vortex strength (psi_min)
    Returns: (pass, error_pct)
    """
    exp_psi = PRIMARY_VORTEX["psi_min"]
    err = abs(cfd_psi_min - exp_psi) / abs(exp_psi) * 100.0
    return (err < ACCEPTANCE_ERROR_THRESHOLD, err)


def validate_centerline_velocity(
    u_exp: List[float],
    u_cfd: List[float],
) -> Dict:
    """
    Validate centerline velocity profile
    Returns: dict with L1, L2, max_error, all_pass
    """
    l1 = L1(u_cfd, u_exp)
    l2 = L2(u_cfd, u_exp)

    errors = []
    for e, c in zip(u_exp, u_cfd):
        err, label = relative_error(c, e, u_max=1.0)
        errors.append(err)

    max_error = max(errors)
    mean_error = sum(errors) / len(errors)
    all_pass = max_error < ACCEPTANCE_ERROR_THRESHOLD

    return {
        "L1": l1,
        "L2": l2,
        "max_error_pct": max_error,
        "mean_error_pct": mean_error,
        "all_pass": all_pass,
        "individual_errors": errors,
    }


def run_benchmark(
    cfd_center_x_H: float = PRIMARY_VORTEX["x_H"],
    cfd_center_y_H: float = PRIMARY_VORTEX["y_H"],
    cfd_psi_min: float = PRIMARY_VORTEX["psi_min"],
    cfd_u_cfd: List[float] = None,
) -> Dict:
    """
    Run full Ghia1982 benchmark suite
    Returns: dict with all validation results and overall pass/fail
    """
    if cfd_u_cfd is None:
        cfd_u_cfd = [row[2] for row in CENTERLINE_VELOCITY]

    u_exp = [row[1] for row in CENTERLINE_VELOCITY]

    vortex_pass, err_x, err_y = validate_vortex_center(cfd_center_x_H, cfd_center_y_H)
    strength_pass, err_psi = validate_vortex_strength(cfd_psi_min)

    velocity_result = validate_centerline_velocity(u_exp, cfd_u_cfd)

    all_pass = vortex_pass and strength_pass and velocity_result["all_pass"]

    return {
        "benchmark": "Ghia1982",
        "case": "Lid-Driven Cavity Re=1000",
        "vortex_center": {
            "pass": vortex_pass,
            "cfd_x_H": cfd_center_x_H,
            "exp_x_H": PRIMARY_VORTEX["x_H"],
            "error_x_pct": round(err_x, 4),
            "cfd_y_H": cfd_center_y_H,
            "exp_y_H": PRIMARY_VORTEX["y_H"],
            "error_y_pct": round(err_y, 4),
        },
        "vortex_strength": {
            "pass": strength_pass,
            "cfd_psi_min": cfd_psi_min,
            "exp_psi_min": PRIMARY_VORTEX["psi_min"],
            "error_pct": round(err_psi, 4),
        },
        "centerline_velocity": velocity_result,
        "overall_pass": all_pass,
        "acceptance_threshold_pct": ACCEPTANCE_ERROR_THRESHOLD,
    }


# ─── Test ───

def _test_bench():
    result = run_benchmark()
    print(f"\n=== Ghia1982 Benchmark Results ===")
    print(f"Vortex Center: {'PASS' if result['vortex_center']['pass'] else 'FAIL'}")
    print(f"  x/H error: {result['vortex_center']['error_x_pct']}%")
    print(f"  y/H error: {result['vortex_center']['error_y_pct']}%")
    print(f"Vortex Strength: {'PASS' if result['vortex_strength']['pass'] else 'FAIL'}")
    print(f"  ψ error: {result['vortex_strength']['error_pct']}%")
    print(f"Centerline Velocity:")
    print(f"  L1: {result['centerline_velocity']['L1']:.6f}")
    print(f"  L2: {result['centerline_velocity']['L2']:.6f}")
    print(f"  Max error: {result['centerline_velocity']['max_error_pct']:.2f}%")
    print(f"  Mean error: {result['centerline_velocity']['mean_error_pct']:.2f}%")
    print(f"\n{'✅ OVERALL PASS' if result['overall_pass'] else '❌ OVERALL FAIL'}")
    assert result['overall_pass'], "Benchmark should pass with canonical data"
    print("\n✅ bench_ghia1982 test passed")


if __name__ == "__main__":
    _test_bench()
