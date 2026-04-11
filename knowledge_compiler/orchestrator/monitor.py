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
import asyncio
from typing import List, Dict, Optional, AsyncIterator
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

    def monitor_residuals(
        self,
        log_path: Optional[str] = None,
        log_content: Optional[str] = None
    ) -> MonitorReport:
        """
        Monitor solver residuals from log file or content string.

        Fixed (F-P3-002): Unified interface signature.

        Args:
            log_path: Path to log file (optional)
            log_content: Pre-loaded log content string (optional)

        Returns:
            MonitorReport with convergence status and events
        """
        # Use provided log_path if given, otherwise use self.log_path
        target_path = Path(log_path) if log_path else self.log_path

        if log_content is None:
            try:
                with open(target_path) as f:
                    log_content = f.read()
            except FileNotFoundError:
                return self._create_empty_report(f"Log file not found: {target_path}")

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

        Fixed (F-P3-006): Improved STALLED detection using full window and linear regression.

        Rules:
        - CONVERGED: All residuals < target for last N iterations
        - STALLED: Residuals not decreasing over time (detected via linear regression slope)
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

        # Check if stalled (not decreasing) - use full window with linear regression
        if len(last_residuals) >= 20:
            # Compute linear regression slope on log residuals
            import math
            log_residuals = []
            for i, r in enumerate(last_residuals):
                val = r.get("residual_final", 1.0)
                if val > 0:
                    log_residuals.append(math.log(val))

            if len(log_residuals) >= 10:
                # Simple linear regression: y = a + bx
                n = len(log_residuals)
                x_mean = (n - 1) / 2
                y_mean = sum(log_residuals) / n

                # Calculate slope
                numerator = sum((i - x_mean) * (log_residuals[i] - y_mean) for i in range(n))
                denominator = sum((i - x_mean) ** 2 for i in range(n))
                slope = numerator / denominator if denominator != 0 else 0

                # If slope is near zero (convergence plateau), consider STALLED
                # Threshold: |slope| < 0.001 means less than 0.1% change per iteration
                if abs(slope) < 0.001 and not all_below_threshold:
                    return ConvergenceStatus.STALLED

        if all_below_threshold:
            return ConvergenceStatus.CONVERGED

        return ConvergenceStatus.RUNNING

    async def stream_residuals(
        self,
        log_lines: "AsyncIterator[str]",
    ) -> "AsyncIterator[Dict[str, float]]":
        """
        Parse residuals from streaming log lines with 500ms debounce.

        Args:
            log_lines: Async iterator of log output lines from solver stdout

        Yields:
            Dict with keys: iteration (int), time_value (float), residuals (Dict[str, float])
        """
        import asyncio
        import re

        time_pattern = re.compile(r"Time = ([\d.]+)")
        residual_pattern = re.compile(r"(Ux Uy Uz|p) = ([\d.e+-]+)")

        current_iteration = 0
        current_time_value = 0.0
        current_residuals: Dict[str, float] = {}
        last_update_time = 0.0
        buffer: Dict[str, float] = {}

        async for raw_line in log_lines:
            line = raw_line.strip()

            # Parse Time = X
            time_match = time_pattern.search(line)
            if time_match:
                current_time_value = float(time_match.group(1))
                current_iteration = int(current_time_value)
                current_residuals = {}
                buffer = {}

            # Parse residual field lines (Ux=..., Uy=..., Uz=..., p=...)
            # Format: "Ux = 1.23e-04" on its own line or inline
            for field in ["Ux", "Uy", "Uz", "p"]:
                if f"{field} =" in line or f"{field}=" in line:
                    # Extract value after = sign
                    match = re.search(rf"{field}\s*=\s*([\d.e+-]+)", line)
                    if match:
                        try:
                            buffer[field] = float(match.group(1))
                        except ValueError:
                            pass

            # When we see "Initial residual:" or "Final residual:" or end of iteration
            # commit the buffered residuals
            if buffer and ("Initial residual" in line or "Final residual" in line or "ExecutionTime" in line):
                current_residuals = dict(buffer)
                buffer = {}

                # Debounce: yield at most every 500ms
                now = asyncio.get_event_loop().time()
                if now - last_update_time >= 0.5:
                    yield {
                        "iteration": current_iteration,
                        "time_value": current_time_value,
                        "residuals": dict(current_residuals),
                    }
                    last_update_time = now

    def parse_residual_line(self, line: str) -> Optional[Dict[str, float]]:
        """
        Parse a single log line for residual values.

        Args:
            line: A single line from solver stdout

        Returns:
            Dict mapping field names to residual values, or None if no residual found
        """
        import re

        result: Dict[str, float] = {}
        # Match patterns like "Ux = 1.23e-04" or "p = 5.67e-08"
        for field in ["Ux", "Uy", "Uz", "p"]:
            match = re.search(rf"{field}\s*=\s*([\d.e+-]+)", line)
            if match:
                try:
                    result[field] = float(match.group(1))
                except ValueError:
                    pass
        return result if result else None

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
