#!/usr/bin/env python3
"""
formula_validator.py — Phase1 ReportSpec v1.1 误差公式校验
Knowledge Compiler: Executable Layer
Source: CANON-FORMULA-* units

验证函数:
  - L1: mean absolute error
  - L2: RMSE
  - relative_error: with zero-reference handling
  - gci: grid convergence index
"""

import math
from typing import List, Tuple, Optional

# Threshold for zero-reference handling
ZERO_REF_THRESHOLD_RATIO = 0.01


def L1(u_cfd: List[float], u_exp: List[float]) -> float:
    """
    L1 范数（平均绝对误差）
    L1 = (1/N) * Σ |u_cfd - u_exp|
    """
    if len(u_cfd) != len(u_exp):
        raise ValueError(f"Length mismatch: {len(u_cfd)} vs {len(u_exp)}")
    n = len(u_cfd)
    if n == 0:
        raise ValueError("Empty arrays")
    return sum(abs(c - e) for c, e in zip(u_cfd, u_exp)) / n


def L2(u_cfd: List[float], u_exp: List[float]) -> float:
    """
    L2 范数（均方根误差 RMSE）
    L2 = sqrt((1/N) * Σ (u_cfd - u_exp)^2)
    """
    if len(u_cfd) != len(u_exp):
        raise ValueError(f"Length mismatch: {len(u_cfd)} vs {len(u_exp)}")
    n = len(u_cfd)
    if n == 0:
        raise ValueError("Empty arrays")
    return math.sqrt(sum((c - e) ** 2 for c, e in zip(u_cfd, u_exp)) / n)


def relative_error(u_cfd: float, u_exp: float, u_max: Optional[float] = None) -> Tuple[float, str]:
    """
    相对误差 with zero-reference handling per ReportSpec v1.1 §2.2

    当 |u_exp| >= 阈值（|u_exp| >= 0.01 * u_max）时：
        ε_rel = |u_cfd - u_exp| / |u_exp| * 100%

    当 |u_exp| < 阈值（|u_exp| < 0.01 * u_max）时：
        退化为绝对误差，标注 "@ near-zero reference"

    Returns:
        (error_value, error_type_label)
    """
    if u_max is None:
        u_max = max(abs(v) for v in [u_cfd, u_exp]) if u_cfd != 0 or u_exp != 0 else 1.0

    threshold = ZERO_REF_THRESHOLD_RATIO * u_max

    if abs(u_exp) >= threshold:
        error = abs(u_cfd - u_exp) / abs(u_exp) * 100.0
        return error, "relative"
    else:
        error = abs(u_cfd - u_exp)
        return error, "absolute_near_zero"


def GCI(phi1: float, phi2: float, r: float, p: float = 2.0) -> float:
    """
    GCI 网格收敛指数（Richardson外推）
    GCI_{12} = |ε_{12}| / (r^p - 1) * 100%

    Args:
        phi1: Coarser mesh solution
        phi2: Finer mesh solution
        r: Grid refinement factor (h1/h2, typically > 1)
        p: Order of accuracy (default 2)
    """
    if r <= 1:
        raise ValueError(f"r must be > 1, got {r}")
    if phi1 == 0:
        raise ValueError("phi1 cannot be zero for GCI calculation")
    epsilon = (phi2 - phi1) / phi1
    gci = abs(epsilon) / (r ** p - 1) * 100.0
    return gci


# ─── Test Cases ───

def _test_L1():
    u_cfd = [1.01093, 0.41522, -0.10380]
    u_exp = [1.00000, 0.40225, -0.10272]
    result = L1(u_cfd, u_exp)
    assert abs(result - 0.00832667) < 1e-5, f"L1 failed: {result}"
    print("✓ L1 test passed")


def _test_L2():
    u_cfd = [1.01093, 0.41522, -0.10380]
    u_exp = [1.00000, 0.40225, -0.10272]
    result = L2(u_cfd, u_exp)
    assert abs(result - 0.009812) < 1e-5, f"L2 failed: {result}"
    print("✓ L2 test passed")


def _test_relative_error_normal():
    # Normal case: |u_exp| = 1.0, threshold = 0.01
    err, label = relative_error(1.01093, 1.00000, u_max=1.0)
    assert label == "relative"
    assert abs(err - 1.093) < 0.01, f"relative_error normal failed: {err}"
    print("✓ relative_error (normal) test passed")


def _test_relative_error_near_zero():
    # Near-zero case: |u_exp| = 0.00435, threshold = 0.01 * 1.0 = 0.01
    # |u_exp| < threshold → absolute error
    err, label = relative_error(-0.00444, -0.00435, u_max=1.0)
    assert label == "absolute_near_zero"
    assert abs(err - 0.00009) < 1e-5, f"relative_error near-zero failed: {err}"
    print("✓ relative_error (near-zero) test passed")


def _test_GCI():
    # Coarse: 2.105 Nm, Fine: 2.296 Nm, r = 2
    gci = GCI(2.105, 2.296, r=2.0, p=2.0)
    # epsilon = (2.296 - 2.105) / 2.105 = 0.0907
    # r^p - 1 = 4 - 1 = 3
    # GCI = 0.0907 / 3 * 100 = 3.02%
    assert abs(gci - 3.02) < 0.1, f"GCI failed: {gci}"
    print(f"✓ GCI test passed: {gci:.2f}%")


def run_all_tests():
    print("Running formula_validator tests...")
    _test_L1()
    _test_L2()
    _test_relative_error_normal()
    _test_relative_error_near_zero()
    _test_GCI()
    print("\n✅ All tests passed")


if __name__ == "__main__":
    run_all_tests()
