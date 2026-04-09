#!/usr/bin/env python3
"""
Phase 3: Orchestrator

知识驱动编排器 - 实现端到端 CFD 工作流自动化。
"""

# Core schema
from knowledge_compiler.phase3.schema import (
    # Enums
    SolverType,
    SolverStatus,
    MeshFormat,
    MeshQuality,
    JobPriority,
    # Postprocess Runner
    PostprocessStatus,
    PostprocessFormat,
    PostprocessArtifact,
    PostprocessResult,
    PostprocessRequest,
    PostprocessJob,
    # Solver Runner
    SolverConfig,
    BoundaryCondition,
    SolverInput,
    SolverResult,
    SolverJob,
    # Mesh Builder
    MeshConfig,
    MeshStatistics,
    MeshResult,
    # Physics Planner
    PhysicsModel,
    PhysicsPlan,
    # CAD Parser
    GeometryFeature,
    ParsedGeometry,
    # Job Scheduler
    ScheduledJob,
    SchedulerState,
    # Phase 3 Output
    Phase3Output,
    # Factory functions
    create_phase3_output,
    create_solver_job,
    get_solver_executable,
)

# Postprocess Runner
from knowledge_compiler.phase3.postprocess_runner import (
    PostprocessRunner,
    BatchPostprocessRunner,
    run_postprocess,
    create_postprocess_job,
)

__all__ = [
    # Enums
    "SolverType",
    "SolverStatus",
    "MeshFormat",
    "MeshQuality",
    "JobPriority",
    # Postprocess Runner
    "PostprocessStatus",
    "PostprocessFormat",
    "PostprocessArtifact",
    "PostprocessResult",
    "PostprocessRequest",
    "PostprocessJob",
    "PostprocessRunner",
    "BatchPostprocessRunner",
    "run_postprocess",
    "create_postprocess_job",
    # Solver Runner
    "SolverConfig",
    "BoundaryCondition",
    "SolverInput",
    "SolverResult",
    "SolverJob",
    # Mesh Builder
    "MeshConfig",
    "MeshStatistics",
    "MeshResult",
    # Physics Planner
    "PhysicsModel",
    "PhysicsPlan",
    # CAD Parser
    "GeometryFeature",
    "ParsedGeometry",
    # Job Scheduler
    "ScheduledJob",
    "SchedulerState",
    # Phase 3 Output
    "Phase3Output",
    # Factory functions
    "create_phase3_output",
    "create_solver_job",
    "get_solver_executable",
]
