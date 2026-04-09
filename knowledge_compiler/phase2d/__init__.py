#!/usr/bin/env python3
"""
Phase 2d: Pipeline Assembly - E2E Pipeline Orchestrator

端到端流程编排层，协调 Phase 1 和 Phase 2 的所有组件。
"""

# Pipeline State and Configuration
from knowledge_compiler.phase2d.pipeline_orchestrator import (
    PipelineState,
    PipelineStage,
    PipelineConfig,
    StageResult,
)

# Pipeline Monitor
from knowledge_compiler.phase2d.pipeline_orchestrator import (
    PipelineMonitor,
)

# Stage Executors
from knowledge_compiler.phase2d.pipeline_orchestrator import (
    StageExecutor,
    ReportSpecStageExecutor,
    PhysicsPlanningStageExecutor,
    ExecutionStageExecutor,
    CorrectionRecordingStageExecutor,
)

# Pipeline Orchestrator
from knowledge_compiler.phase2d.pipeline_orchestrator import (
    PipelineOrchestrator,
)

# Execution Flow Manager
from knowledge_compiler.phase2d.pipeline_orchestrator import (
    ExecutionFlowManager,
)

# Result Aggregator
from knowledge_compiler.phase2d.pipeline_orchestrator import (
    ResultAggregator,
)

# Convenience Functions
from knowledge_compiler.phase2d.pipeline_orchestrator import (
    create_default_config,
    execute_pipeline_simple,
    execute_batch_pipelines,
)

__all__ = [
    # Pipeline State and Configuration
    "PipelineState",
    "PipelineStage",
    "PipelineConfig",
    "StageResult",
    # Pipeline Monitor
    "PipelineMonitor",
    # Stage Executors
    "StageExecutor",
    "ReportSpecStageExecutor",
    "PhysicsPlanningStageExecutor",
    "ExecutionStageExecutor",
    "CorrectionRecordingStageExecutor",
    # Pipeline Orchestrator
    "PipelineOrchestrator",
    # Execution Flow Manager
    "ExecutionFlowManager",
    # Result Aggregator
    "ResultAggregator",
    # Convenience Functions
    "create_default_config",
    "execute_pipeline_simple",
    "execute_batch_pipelines",
]
