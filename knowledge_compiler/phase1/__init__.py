#!/usr/bin/env python3
"""
Phase 1: Standard Knowledge Collector

面向后处理与报告流程的标准知识采集器。

核心功能：
- 结果目录解析器
- 报告骨架生成器
- Report Teach Mode 引擎
- ReportSpec 管理器
- Phase 1 Gate 实现
"""

from knowledge_compiler.phase1.schema import (
    # Enums
    ProblemType,
    KnowledgeLayer,
    KnowledgeStatus,
    ComparisonType,
    ErrorType,
    ImpactScope,
    # Specs
    PlotSpec,
    MetricSpec,
    SectionSpec,
    AnomalyRule,
    # Core objects
    ReportSpec,
    TeachRecord,
    TeachOperation,
    KnowledgeVersion,
    CorrectionSpec,
    ResultManifest,
    ResultAsset,
    ReportDraft,
    # Phase 1 → Phase 2 Interface
    Phase1Output,
    # Phase 3 Reserved
    AnalogySpec,
    # Factory functions
    create_report_spec_id,
    create_teach_record_id,
    create_correction_id,
    create_phase1_output_id,
)

# Import CorrectionRecorder components for re-export
from knowledge_compiler.phase1.teach import (
    CorrectionDetection,
    CorrectionRecorder,
    is_generalizable_correction,
)

from knowledge_compiler.phase1.skeleton import (
    ChartStandard,
    REPORT_STRUCTURE,
    PROBLEM_TYPE_DEFAULTS,
    GateResult,
    Phase1Gates,
    ReportSkeletonGenerator,
    generate_report_skeleton,
)

from knowledge_compiler.phase1.teach import (
    OperationType,
    TeachContext,
    TeachResponse,
    EvidenceReference,
    TeachModeEngine,
    record_teach_operation,
)

from knowledge_compiler.phase1.manager import (
    ValidationResult,
    PromotionResult,
    ReportSpecManager,
    create_report_spec,
)

from knowledge_compiler.phase1.replay import (
    ReplayConfig,
    ReplayResult,
    BatchReplayResult,
    HistoricalReference,
    ReplayEngine,
    OpenFOAMReplayUtils,
)

from knowledge_compiler.phase1.gates import (
    GateStatus,
    GateCheckItem,
    GateResult as GateResultV2,
    ActionPlanExecutabilityGate,
    CorrectionSpecCompletenessGate,
    ExplanationBinding,
    EvidenceBindingGate,
    GeneralizationMetrics,
    TemplateGeneralizationGate,
    Phase1GateExecutor,
)

# Module F2: NL Postprocess Executor
from knowledge_compiler.phase1.nl_postprocess import (
    ActionType,
    Action,
    ActionPlan,
    ActionLog,
    NLPostprocessExecutor,
    create_action_plan,
    execute_action_plan,
)

# Module F3: Visualization Engine
from knowledge_compiler.phase1.visualization import (
    OutputFormat,
    VisualizationResult,
    VisualizationEngine,
    execute_visualization,
)

__all__ = [
    # Enums
    "ProblemType",
    "KnowledgeLayer",
    "KnowledgeStatus",
    "ComparisonType",
    "ErrorType",
    "ImpactScope",
    # Specs
    "PlotSpec",
    "MetricSpec",
    "SectionSpec",
    "AnomalyRule",
    # Core objects
    "ReportSpec",
    "TeachRecord",
    "TeachOperation",
    "KnowledgeVersion",
    "CorrectionSpec",
    "ResultManifest",
    "ResultAsset",
    "ReportDraft",
    # Phase 1 → Phase 2 Interface
    "Phase1Output",
    "AnalogySpec",
    # Factory functions
    "create_report_spec_id",
    "create_teach_record_id",
    "create_correction_id",
    "create_phase1_output_id",
    # Module 2 exports
    "ChartStandard",
    "REPORT_STRUCTURE",
    "PROBLEM_TYPE_DEFAULTS",
    "GateResult",
    "Phase1Gates",
    "ReportSkeletonGenerator",
    "generate_report_skeleton",
    # Module 3 exports (CORE)
    "OperationType",
    "TeachContext",
    "TeachResponse",
    "EvidenceReference",
    "CorrectionDetection",
    "CorrectionRecorder",
    "TeachModeEngine",
    "record_teach_operation",
    "is_generalizable_correction",
    # Module 4 exports
    "ValidationResult",
    "PromotionResult",
    "ReportSpecManager",
    "create_report_spec",
    # Module 5 exports (C6 Replay Engine)
    "ReplayConfig",
    "ReplayResult",
    "BatchReplayResult",
    "HistoricalReference",
    "ReplayEngine",
    "OpenFOAMReplayUtils",
    # Module 6 exports (P1-G1/G3/G4 Gates)
    "GateStatus",
    "GateCheckItem",
    "GateResultV2",
    "ActionPlanExecutabilityGate",
    "CorrectionSpecCompletenessGate",
    "ExplanationBinding",
    "EvidenceBindingGate",
    "GeneralizationMetrics",
    "TemplateGeneralizationGate",
    "Phase1GateExecutor",
    # Module F2 exports (NL Postprocess Executor)
    "ActionType",
    "Action",
    "ActionPlan",
    "ActionLog",
    "NLPostprocessExecutor",
    "create_action_plan",
    "execute_action_plan",
    # Module F3 exports (Visualization Engine)
    "OutputFormat",
    "VisualizationResult",
    "VisualizationEngine",
    "execute_visualization",
]
