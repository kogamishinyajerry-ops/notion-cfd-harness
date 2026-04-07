#!/usr/bin/env python3
"""
chart_template.py — Phase1 ReportSpec v1.1 图表渲染模板
Knowledge Compiler: Executable Layer
Source: CANON-CHART-RULE-* units
Renders: velocity profile, pressure contour, GCI convergence
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Optional, Tuple

# ─── Marker Style Enumeration (per chart_standards.md §1.2.1) ───
MARKER_STYLES = {
    'experiment':   {'marker': 'o', 'facecolors': 'none',   'edgecolors': 'blue',  'label': 'Experiment'},
    'cfd':           {'marker': 'o', 'facecolors': 'C0',      'edgecolors': 'C0',     'label': 'CFD'},
    'grid_medium':   {'marker': '^', 'facecolors': 'green',  'edgecolors': 'green',  'label': 'Medium Grid'},
    'grid_fine':     {'marker': 'v', 'facecolors': 'red',    'edgecolors': 'red',    'label': 'Fine Grid'},
    'other_model':   {'marker': 's', 'facecolors': 'orange', 'edgecolors': 'orange', 'label': 'Other Model'},
    'sensitivity':   {'marker': 'D', 'facecolors': 'purple', 'edgecolors': 'purple', 'label': 'Sensitivity'},
}


def plot_velocity_profile(
    y_H: List[float],
    u_exp: List[float],
    u_cfd: List[float],
    u_max: float = 1.0,
    title: str = "Lid Cavity Centerline Velocity (Re=1000)",
    xlabel: str = "u/u_ref",
    ylabel: str = "y/H",
    figsize: Tuple[int, int] = (8, 6),
    save_path: Optional[str] = None,
    show_error_bars: bool = False,
    error_bars: Optional[List[float]] = None,
) -> plt.Figure:
    """
    Render velocity profile per chart_standards.md §1.1

    X轴: u/u_ref (dimensionless velocity)
    Y轴: y/H (dimensionless vertical position)
    Experiment: hollow circle (marker='o', facecolors='none')
    CFD: filled circle (marker='o', facecolors='C0')
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Experiment/benchmark reference — hollow circle
    ax.scatter(u_exp, y_H,
               marker='o', facecolors='none', edgecolors='blue',
               label='Experiment (Ghia1982)', s=60, zorder=3)

    # CFD result — filled circle
    ax.scatter(u_cfd, y_H,
               marker='o', facecolors='C0', edgecolors='C0',
               label='CFD (icoFoam)', s=60, zorder=3)

    # Error bars (optional)
    if show_error_bars and error_bars is not None:
        ax.errorbar(u_cfd, y_H, xerr=error_bars,
                    fmt='none', ecolor='gray', capsize=3, zorder=2)

    # Zero reference line
    ax.axvline(x=0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=12)
    ax.legend(loc='lower right', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=min(min(u_exp), min(u_cfd)) * 1.1,
                right=max(max(u_exp), max(u_cfd)) * 1.1)

    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300)
        print(f"Saved: {save_path}")

    return fig


def plot_pressure_contour(
    x: np.ndarray,
    y: np.ndarray,
    cp: np.ndarray,
    colormap: str = 'viridis',
    title: str = "Pressure Coefficient Cp",
    save_path: Optional[str] = None,
    show_mesh: bool = False,
    levels: Optional[int] = 20,
) -> plt.Figure:
    """
    Render pressure contour per chart_standards.md §2
    Colorbar REQUIRED — shows physical quantity and unit
    """
    fig, ax = plt.subplots(figsize=(8, 6))

    # Contour fill
    cf = ax.contourf(x, y, cp, levels=levels, cmap=colormap)
    # Contour lines
    cs = ax.contour(x, y, cp, levels=levels, colors='k', linewidths=0.3, alpha=0.5)
    ax.clabel(cs, inline=True, fontsize=8, fmt='%.2f')

    # Colorbar (REQUIRED)
    cbar = fig.colorbar(cf, ax=ax)
    cbar.set_label(title, fontsize=11)

    # Mesh overlay (optional)
    if show_mesh:
        ax.set_aspect('equal')
        # Mesh lines handled by contourf already

    ax.set_xlabel('x (m)', fontsize=12)
    ax.set_ylabel('y (m)', fontsize=12)
    ax.set_title(title, fontsize=12)

    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300)
        print(f"Saved: {save_path}")

    return fig


def plot_gci_convergence(
    levels: List[str],
    values: List[float],
    gci_values: Optional[List[float]] = None,
    metric_name: str = "Torque [Nm]",
    title: str = "Grid Convergence Study",
    threshold_pct: float = 5.0,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Render GCI table/chart per chart_standards.md §3
    Acceptance criterion: GCI < 5% → grid independent
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    x = np.arange(len(levels))
    ax.bar(x, values, color=['#2196F3', '#4CAF50', '#F44336'][:len(levels)],
           edgecolor='black', linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(levels)
    ax.set_ylabel(metric_name, fontsize=12)
    ax.set_title(title, fontsize=12)
    ax.grid(True, alpha=0.3, axis='y')

    # Annotate bars
    for i, v in enumerate(values):
        ax.text(i, v, f'{v:.3f}', ha='center', va='bottom', fontsize=10)

    # GCI annotation
    if gci_values:
        note = f"GCI (Medium→Fine): {gci_values[-1]:.1f}% — "
        note += "Grid Independent ✓" if gci_values[-1] < threshold_pct else "Grid Dependent ✗"
        ax.text(0.5, 0.02, note, transform=ax.transAxes,
                fontsize=9, ha='center', va='bottom',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300)
        print(f"Saved: {save_path}")

    return fig


# ─── Test Cases ───

def _test_velocity_profile():
    y_H = [1.0, 0.7266, 0.2969, 0.1719]
    u_exp = [1.0, 0.40225, -0.10272, -0.05821]
    u_cfd = [1.01093, 0.41522, -0.10380, -0.05910]
    fig = plot_velocity_profile(y_H, u_exp, u_cfd, save_path=None)
    assert fig is not None
    plt.close(fig)
    print("✓ plot_velocity_profile test passed")


def _test_pressure_contour():
    x = np.linspace(0, 1, 50)
    y = np.linspace(0, 1, 50)
    X, Y = np.meshgrid(x, y)
    cp = np.sin(np.pi * X) * np.cos(np.pi * Y)  # synthetic data
    fig = plot_pressure_contour(X, Y, cp, save_path=None)
    assert fig is not None
    plt.close(fig)
    print("✓ plot_pressure_contour test passed")


def _test_gci_convergence():
    levels = ["Coarse", "Medium", "Fine"]
    values = [2.105, 2.278, 2.296]
    gci_values = [None, 8.2, 0.8]
    fig = plot_gci_convergence(levels, values, gci_values, save_path=None)
    assert fig is not None
    plt.close(fig)
    print("✓ plot_gci_convergence test passed")


def run_all_tests():
    print("Running chart_template tests...")
    _test_velocity_profile()
    _test_pressure_contour()
    _test_gci_convergence()
    print("\n✅ All tests passed")


if __name__ == "__main__":
    run_all_tests()
