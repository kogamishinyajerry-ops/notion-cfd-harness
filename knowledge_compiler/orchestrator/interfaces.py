#!/usr/bin/env python3
"""
Knowledge Compiler Orchestrator Interfaces
Phase 3: Knowledge-Driven Orchestrator

Interface definitions for all orchestrator components.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from pathlib import Path

from .contract import (
    RunContext,
    TaskIntent,
    GeometrySemanticModel,
    PhysicsPlan,
    MeshPlan,
    SolverPlan,
    MonitorReport,
    VerificationReport,
    IOrchestratorComponent,
)


# =============================================================================
# Component Interfaces
# =============================================================================

class ITaskBuilder(IOrchestratorComponent, Protocol):
    """Task Builder: converts natural language to executable DAG."""

    def parse_intent(self, query: str) -> TaskIntent:
        """Parse natural language query into structured intent."""
        ...

    def build_dag(self, intent: TaskIntent) -> Dict[str, Any]:
        """Build executable Directed Acyclic Graph from intent."""
        ...


class ICADParser(IOrchestratorComponent, Protocol):
    """CAD Semantic Parser: extracts geometry semantics."""

    def parse_geometry(self, cad_file: Path) -> GeometrySemanticModel:
        """Parse CAD file and extract semantic model."""
        ...

    def detect_regions(self, geometry: GeometrySemanticModel) -> List[Any]:
        """Detect fluid regions from geometry."""
        ...


class IPhysicsPlanner(IOrchestratorComponent, Protocol):
    """Physics Planner: plans CFD physics setup."""

    def plan_physics(self, intent: TaskIntent, geometry: GeometrySemanticModel) -> PhysicsPlan:
        """Create physics plan from intent and geometry."""
        ...

    def recommend_model(self, flow_regime: str) -> str:
        """Recommend turbulence model based on flow regime."""
        ...


class IMeshBuilder(IOrchestratorComponent, Protocol):
    """Mesh Builder: plans and generates mesh."""

    def plan_mesh(self, geometry: GeometrySemanticModel, physics: PhysicsPlan) -> MeshPlan:
        """Create mesh plan from geometry and physics requirements."""
        ...

    def generate_mesh(self, plan: MeshPlan) -> str:
        """Generate mesh and return path to mesh directory."""
        ...


class ISolverRunner(IOrchestratorComponent, Protocol):
    """Solver Runner: executes CFD solver."""

    def prepare_case(self, mesh_path: str, physics: PhysicsPlan, solver: SolverPlan) -> str:
        """Prepare case directory for solver."""
        ...

    def run_solver(self, case_dir: str, solver_plan: SolverPlan) -> MonitorReport:
        """Run solver and return monitoring report."""
        ...


class IMonitor(IOrchestratorComponent, Protocol):
    """Monitor: tracks solver convergence."""

    def monitor_residuals(self, log_path: str) -> MonitorReport:
        """Monitor solver residuals from log file."""
        ...

    def detect_convergence(self, report: MonitorReport) -> bool:
        """Determine if simulation has converged."""
        ...


class IVerifyConsole(IOrchestratorComponent, Protocol):
    """Verify Console: validates results against benchmarks."""

    def run_benchmarks(self, results_path: str, case_id: str) -> VerificationReport:
        """Run Phase2 benchmark validators."""
        ...

    def generate_charts(self, results_path: str, chart_types: List[str]) -> Dict[str, str]:
        """Generate standard charts using Phase2 chart_template.py."""
        ...


# =============================================================================
# Orchestrator Core Interface
# =============================================================================

class IOrchestrator(ABC):
    """Main orchestrator interface."""

    @abstractmethod
    def submit_task(self, query: str) -> str:
        """Submit a new task and return task ID."""
        ...

    @abstractmethod
    def get_status(self, task_id: str) -> Dict[str, Any]:
        """Get current status of a task."""
        ...

    @abstractmethod
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        ...

    @abstractmethod
    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        ...
