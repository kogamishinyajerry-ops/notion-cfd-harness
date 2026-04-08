#!/usr/bin/env python3
"""
Phase 3: Physics Planner

基于几何特征和问题描述，自动规划物理模型和求解器选择。
"""

# Schema types (re-exported)
from knowledge_compiler.phase3.schema import (
    BoundaryCondition,
    PhysicsModel,
    PhysicsPlan,
    SolverType,
)

# Main module
from knowledge_compiler.phase3.physics_planner.planner import (
    PhysicsPlanner,
    BatchPhysicsPlanner,
    create_physics_plan,
    plan_from_geometry,
)

__all__ = [
    # Schema
    "BoundaryCondition",
    "PhysicsModel",
    "PhysicsPlan",
    "SolverType",
    # Planner
    "PhysicsPlanner",
    "BatchPhysicsPlanner",
    # Convenience
    "create_physics_plan",
    "plan_from_geometry",
]
