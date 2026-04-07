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
]
