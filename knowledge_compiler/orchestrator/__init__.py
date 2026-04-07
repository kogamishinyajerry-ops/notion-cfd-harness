"""
Knowledge Compiler Orchestrator
Phase 3: Knowledge-Driven Orchestrator
"""

from .contract import (
    # Context
    RunContext,
    # Intent
    TaskIntent,
    # Geometry
    GeometrySemanticModel,
    BoundaryCondition,
    Region,
    CoordinateSystem,
    # Physics
    PhysicsPlan,
    TurbulenceModel,
    MonitorPoint,
    # Mesh
    MeshPlan,
    MeshLevel,
    GCIPlan,
    # Solver
    SolverPlan,
    TimeStepping,
    # Monitoring
    MonitorReport,
    ConvergenceStatus,
    ConvergenceEvent,
    # Verification
    VerificationReport,
    BenchmarkResult,
    ChartType,
    # State
    IOrchestratorComponent,
    OrchestratorState,
    OrchestratorStatus,
)

from .interfaces import (
    ITaskBuilder,
    ICADParser,
    IPhysicsPlanner,
    IMeshBuilder,
    ISolverRunner,
    IMonitor,
    IVerifyConsole,
    IOrchestrator,
)

# Fixed (F-P3-004): runtime.py is in parent package, not orchestrator subpackage
from knowledge_compiler.runtime import KnowledgeRegistry, get_registry
from .verify_console import VerifyConsole
from .monitor import Monitor
from .task_builder import TaskBuilder, DAGNode, ExecutableDAG
from .cad_parser import CADParser
from .physics_planner import PhysicsPlanner
from .mesh_builder import MeshBuilder
from .solver_runner import SolverRunner

__all__ = [
    # Contract
    "RunContext",
    "TaskIntent",
    "GeometrySemanticModel",
    "BoundaryCondition",
    "Region",
    "CoordinateSystem",
    "PhysicsPlan",
    "TurbulenceModel",
    "MonitorPoint",
    "MeshPlan",
    "MeshLevel",
    "GCIPlan",
    "SolverPlan",
    "TimeStepping",
    "MonitorReport",
    "ConvergenceStatus",
    "ConvergenceEvent",
    "VerificationReport",
    "BenchmarkResult",
    "ChartType",
    "IOrchestratorComponent",
    "OrchestratorState",
    "OrchestratorStatus",
    # Interfaces
    "ITaskBuilder",
    "ICADParser",
    "IPhysicsPlanner",
    "IMeshBuilder",
    "ISolverRunner",
    "IMonitor",
    "IVerifyConsole",
    "IOrchestrator",
    # Runtime
    "KnowledgeRegistry",
    "get_registry",
    # Components
    "VerifyConsole",
    "Monitor",
    "TaskBuilder",
    "DAGNode",
    "ExecutableDAG",
    "CADParser",
    "PhysicsPlanner",
    "MeshBuilder",
    "SolverRunner",
]
