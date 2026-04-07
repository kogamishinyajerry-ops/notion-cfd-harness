#!/usr/bin/env python3
"""
Monitor - Phase3 Solver Monitoring
Phase 3: Knowledge-Driven Orchestrator

Tracks solver convergence and detects stalled/diverged simulations.
"""

import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

from knowledge_compiler.orchestrator.contract import (
    MonitorReport,
    ConvergenceStatus,
    ConvergenceEvent,
    IOrchestratorComponent,
    RunContext,
)


class MonitorState(Enum):
    """Internal monitor state."""
    IDLE = "idle"
    RUNNING = "running"
    CONVERGED = "converged"
    STALLED = "stalled"
    DIVERGED = "diverged"
    FAILED = "failed"


@dataclass
class ConvergenceCriterion:
    """Convergence criterion definition."""
    quantity: str  # residual, force, monitor point value
    target: float  # Target value
    tolerance: float  # Acceptable tolerance
    window: int = 100  # Number of iterations to check


@dataclass
class Monitor:
    """
    Simulation monitor for OpenFOAM solvers.

    Reads log files, tracks residuals, detects convergence/divergence.
    """

    log_path: Path = field(default_factory=lambda: Path.cwd() / "log.pyFoam")
    criteria: List[ConvergenceCriterion] = field(default_factory=list)
    state: MonitorState = MonitorState.IDLE
    events: List[ConvergenceEvent] = field(default_factory=list)

    # Default convergence thresholds (from Phase1)
    default_residual_target: float = 1e-6
    default_residual_tolerance: float = 1e-5

    def initialize(self, context: RunContext) -> None:
        """Initialize monitor with execution context."""
        self.log_path = context.workspace_root / "log.pyFoam"
        self.state = MonitorState.RUNNING
        self.events = []

    def monitor_residuals(self, log_content: str = None) -> MonitorReport:
        """
        Monitor solver residuals from log file.

        Returns:
            MonitorReport with convergence status and events
        """
        if log_content is None:
            try:
                with open(self.log_path) as f:
                    log_content = f.read()
            except FileNotFoundError:
                return self._create_empty_report("Log file not found")

        # Parse residuals
        residuals = self._parse_residuals(log_content)

        # Detect convergence state
        status = self._detect_convergence(residuals)

        # Create report
        report = MonitorReport(
            status=status,
            iterations=len(residuals),
            final_residuals=residuals[-1] if residuals else {},
            events=self.events
        )

        return report

    def detect_convergence(self, report: MonitorReport) -> bool:
        """
        Determine if simulation has converged.

        Args:
            report: Current monitor report

        Returns:
            True if converged, False otherwise
        """
        return report.status == ConvergenceStatus.CONVERGED

    def _parse_residuals(self, log_content: str) -> List[Dict[str, float]]:
        """
        Parse residual values from OpenFOAM log.

        Looks for: "Time = X ... Ux = Y Uy = Z p = ..."
        """
        residuals = []

        # Regex patterns for OpenFOAM log output
        time_pattern = r"Time = ([\d.]+)"
        residual_pattern = r"(Ux|Uy|Uz|p) = ([\d.e+-]+)"

        for line in log_content.split('\n'):
            time_match = re.search(time_pattern, line)
            if time_match:
                time_val = float(time_match.group(1))

                residual_match = re.search(residual_pattern, line)
                if residual_match:
                    residuals.append({
                        "iteration": int(time_val),
                        "residual_initial": float(residual_match.group(2)),
                        "residual_final": float(residual_match.group(2))
                    })

        return residuals

    def _detect_convergence(self, residuals: List[Dict[str, float]]) -> ConvergenceStatus:
        """
        Detect convergence state from residual history.

        Rules:
        - CONVERGED: All residuals < target for last N iterations
        - STALLED: Residuals not decreasing over time
        - DIVERGED: Residuals increasing to infinity
        - RUNNING: Not enough data to determine
        """
        if len(residuals) < 10:
            return ConvergenceStatus.RUNNING

        last_residuals = residuals[-50:]  # Last 50 iterations
        max_residual = max(r.get("residual_final", 1.0) for r in last_residuals)

        if max_residual > 1e6:  # Exploding
            return ConvergenceStatus.DIVERGED

        # Check if all residuals below threshold
        all_below_threshold = max_residual < self.default_residual_target

        # Check if stalled (not decreasing)
        if len(last_residuals) >= 20:
            first_half = last_residuals[:10]
            second_half = last_residuals[10:]
            avg_first = sum(r.get("residual_final", 1.0) for r in first_half) / len(first_half)
            avg_second = sum(r.get("residual_final", 1.0) for r in second_half) / len(second_half)

            if abs(avg_first - avg_second) / max(avg_first, 1e-10) < 0.01:  # Less than 1% change
                return ConvergenceStatus.STALLED

        if all_below_threshold:
            return ConvergenceStatus.CONVERGED

        return ConvergenceStatus.RUNNING

    def _create_empty_report(self, message: str) -> MonitorReport:
        """Create empty report with error message."""
        return MonitorReport(
            status=ConvergenceStatus.FAILED,
            iterations=0,
            final_residuals={},
            events=[ConvergenceEvent(
                timestamp=datetime.now(),
                iteration=0,
                event_type="error",
                quantity="all",
                value=0.0,
                message=message
            )]
        )


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for monitoring."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor OpenFOAM solver convergence")
    parser.add_argument("--log", required=True, help="Path to log.pyFoam")
    parser.add_argument("--output", default="monitor_report.json", help="Output report path")

    args = parser.parse_args()

    monitor = Monitor(log_path=Path(args.log))
    report = monitor.monitor_residuals()

    # Save report
    import json
    with open(args.output, "w") as f:
        json.dump(report, f, default=str, indent=2)

    print(f"Convergence Status: {report.status.value}")
    print(f"Iterations: {report.iterations}")
    print(f"Events: {len(report.events)}")
    print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()
