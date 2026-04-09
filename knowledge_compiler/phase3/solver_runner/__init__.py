#!/usr/bin/env python3
"""
Phase 3 Solver Runner Module

求解器调度和管理模块。
"""

# Schema types (re-exported for convenience)
from knowledge_compiler.phase3.schema import (
    SolverType,
    SolverStatus,
    SolverConfig,
    BoundaryCondition,
    SolverInput,
    SolverResult,
    SolverJob,
    JobPriority,
)

# Runner module
from knowledge_compiler.phase3.solver_runner.runner import (
    SolverRunner,
    BatchSolverRunner,
    run_solver,
    run_solvers_batch,
)

__all__ = [
    # Schema (re-exports)
    "SolverType",
    "SolverStatus",
    "SolverConfig",
    "BoundaryCondition",
    "SolverInput",
    "SolverResult",
    "SolverJob",
    "JobPriority",
    # Runner
    "SolverRunner",
    "BatchSolverRunner",
    "run_solver",
    "run_solvers_batch",
]
