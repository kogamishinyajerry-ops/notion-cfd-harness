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
    ResultManifest,
    ResultAsset,
    ReportDraft,
    # Factory functions
    create_report_spec_id,
    create_teach_record_id,
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
    ExplanationBinding,
    EvidenceBindingGate,
    GeneralizationMetrics,
    TemplateGeneralizationGate,
    Phase1GateExecutor,
)

__all__ = [
    # Enums
    "ProblemType",
    "KnowledgeLayer",
    "KnowledgeStatus",
    "ComparisonType",
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
    "ResultManifest",
    "ResultAsset",
    "ReportDraft",
    # Factory functions
    "create_report_spec_id",
    "create_teach_record_id",
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
    "TeachModeEngine",
    "record_teach_operation",
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
    # Module 6 exports (P1-G3/G4 Gates)
    "GateStatus",
    "GateCheckItem",
    "GateResultV2",
    "ExplanationBinding",
    "EvidenceBindingGate",
    "GeneralizationMetrics",
    "TemplateGeneralizationGate",
    "Phase1GateExecutor",
]
