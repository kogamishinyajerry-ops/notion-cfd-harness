#!/usr/bin/env python3
"""
Phase 2 Schema: Knowledge Compiler Data Models

定义 Phase 2 的核心数据结构，包括输入/输出接口和知识对象。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

# Import Phase 1 types for interface
from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeStatus,
    KnowledgeLayer,
    ReportSpec,
    CorrectionSpec,
    TeachRecord,
    TeachOperation,
    Phase1Output,
)


# ============================================================================
# Enums
# ============================================================================

class TeachIntent(Enum):
    """教学意图分类"""
    CORRECT_ERROR = "correct_error"       # 纠正错误
    ADD_COMPONENT = "add_component"       # 添加组件
    MODIFY_STANDARD = "modify_standard"   # 修改标准
    GENERALIZE_KNOWLEDGE = "generalize"    # 泛化知识
    REFINE_SCOPE = "refine_scope"         # 精炼范围


class SpecType(Enum):
    """规范类型"""
    REPORT_SPEC = "report_spec"           # 报告规范
    PLOT_STANDARD = "plot_standard"       # 图表标准
    METRIC_STANDARD = "metric_standard"   # 指标标准
    SECTION_RULE = "section_rule"         # 章节规则
    WORKFLOW_PATTERN = "workflow"         # 工作流模式


class CompilationStatus(Enum):
    """编译状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Teach Layer Models
# ============================================================================

@dataclass
class CaptureContext:
    """捕获上下文"""
    case_id: str
    solver_type: str
    problem_type: ProblemType
    timestamp: float = field(default_factory=time.time)
    engineer_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class TeachCapture:
    """
    捕获的原始教学数据

    工程师在使用系统时的教学操作记录，包括：
    - 对 AI 生成内容的修正
    - 新知识的显式添加
    - 对现有规范的改进建议
    """
    # 来源信息 (required, no default)
    source_case_id: str
    context: CaptureContext

    # Auto-generated ID
    capture_id: str = field(default_factory=lambda: f"CAPTURE-{uuid.uuid4().hex[:8]}")

    # 原始操作
    raw_operations: List[TeachOperation] = field(default_factory=list)

    # 关联的 Phase 1 数据
    source_report_spec: Optional[ReportSpec] = None
    source_correction_specs: List[CorrectionSpec] = field(default_factory=list)

    # 元数据
    captured_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_operation(self, operation: TeachOperation) -> None:
        """添加操作记录"""
        self.raw_operations.append(operation)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "capture_id": self.capture_id,
            "source_case_id": self.source_case_id,
            "context": {
                "case_id": self.context.case_id,
                "solver_type": self.context.solver_type,
                "problem_type": self.context.problem_type.value,
                "timestamp": self.context.timestamp,
            },
            "raw_operations": [
                {
                    "operation_type": op.operation_type,
                    "description": op.description,
                    "reason": op.reason,
                }
                for op in self.raw_operations
            ],
            "captured_at": self.captured_at,
            "metadata": self.metadata,
        }


@dataclass
class ParsedTeach:
    """
    解析后的教学数据

    对原始教学数据进行解析和理解，提取：
    - 教学意图
    - 可泛化性
    - 影响范围
    - 置信度
    """
    # 关联的捕获 (required)
    source_capture_id: str

    # 解析结果 (required)
    intent: TeachIntent
    generalizable: bool
    confidence: float

    # Auto-generated ID
    teach_id: str = field(default_factory=lambda: f"TEACH-{uuid.uuid4().hex[:8]}")

    # 提取的知识
    extracted_knowledge: Dict[str, Any] = field(default_factory=dict)

    # 影响组件
    affected_components: List[str] = field(default_factory=list)

    # 解析元数据
    parsed_at: float = field(default_factory=time.time)
    parser_version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_generalizable(self) -> bool:
        """是否可泛化"""
        return self.generalizable and self.confidence >= 0.7


# ============================================================================
# Compiler Layer Models
# ============================================================================

@dataclass
class CanonicalSpec:
    """
    标准知识规范

    编译后的标准化知识，可以直接被 Phase 3 消费。
    """
    # 规范类型 (required)
    spec_type: SpecType

    # 规范内容 (required)
    content: Dict[str, Any]

    # Auto-generated ID
    spec_id: str = field(default_factory=lambda: f"SPEC-{uuid.uuid4().hex[:8]}")

    # 版本控制
    version: str = "1.0"
    parent_spec_id: Optional[str] = None

    # 生命周期
    knowledge_status: KnowledgeStatus = KnowledgeStatus.DRAFT
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.RAW

    # 来源追踪
    source_teach_ids: List[str] = field(default_factory=list)
    source_case_ids: List[str] = field(default_factory=list)

    # 元数据
    created_at: float = field(default_factory=time.time)
    created_by: Optional[str] = None  # engineer_id
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_source(self, teach_id: str, case_id: str) -> None:
        """添加来源"""
        if teach_id not in self.source_teach_ids:
            self.source_teach_ids.append(teach_id)
        if case_id not in self.source_case_ids:
            self.source_case_ids.append(case_id)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "spec_id": self.spec_id,
            "spec_type": self.spec_type.value,
            "content": self.content,
            "version": self.version,
            "parent_spec_id": self.parent_spec_id,
            "knowledge_status": self.knowledge_status.value,
            "knowledge_layer": self.knowledge_layer.value,
            "source_teach_ids": self.source_teach_ids,
            "source_case_ids": self.source_case_ids,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "metadata": self.metadata,
        }


@dataclass
class CompilationResult:
    """
    编译结果

    记录知识编译的完整结果。
    """
    success: bool
    output: Optional[CanonicalSpec]

    # 编译过程信息
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    compilation_log: List[str] = field(default_factory=list)

    # 统计信息
    duration_ms: float = 0.0
    input_teach_count: int = 0
    output_spec_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "output": self.output.to_dict() if self.output else None,
            "warnings": self.warnings,
            "errors": self.errors,
            "compilation_log": self.compilation_log,
            "duration_ms": self.duration_ms,
            "input_teach_count": self.input_teach_count,
            "output_spec_count": self.output_spec_count,
        }


# ============================================================================
# Phase 2 Input/Output
# ============================================================================

@dataclass
class CompilerConfig:
    """编译器配置"""
    strict_mode: bool = True
    enable_conflict_detection: bool = True
    enable_backward_compatibility_check: bool = True
    target_knowledge_layer: KnowledgeLayer = KnowledgeLayer.CANONICAL


@dataclass
class Phase2Input:
    """
    Phase 2 输入接口

    接收 Phase 1 的输出，准备进行知识编译。
    """
    # 来自 Phase 1 (required)
    phase1_output: Phase1Output

    # 编译配置
    config: CompilerConfig = field(default_factory=CompilerConfig)

    # Auto-generated ID
    input_id: str = field(default_factory=lambda: f"P2-INPUT-{uuid.uuid4().hex[:8]}")

    # 过滤器（可选）
    include_spec_ids: Optional[Set[str]] = None
    exclude_spec_ids: Optional[Set[str]] = None

    # 元数据
    received_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_report_specs(self) -> List[ReportSpec]:
        """获取 ReportSpec 列表"""
        specs = self.phase1_output.report_specs
        if self.include_spec_ids:
            specs = [s for s in specs if s.report_spec_id in self.include_spec_ids]
        if self.exclude_spec_ids:
            specs = [s for s in specs if s.report_spec_id not in self.exclude_spec_ids]
        return specs

    def get_correction_specs(self) -> List[CorrectionSpec]:
        """获取 CorrectionSpec 列表"""
        return self.phase1_output.correction_specs

    def get_teach_records(self) -> List[TeachRecord]:
        """获取 TeachRecord 列表"""
        return self.phase1_output.teach_records


@dataclass
class CompiledKnowledge:
    """
    Phase 2 输出接口

    编译后的完整知识包。
    """
    output_id: str = field(default_factory=lambda: f"P2-OUTPUT-{uuid.uuid4().hex[:8]}")

    # 编译结果
    canonical_specs: List[CanonicalSpec] = field(default_factory=list)
    compilation_results: List[CompilationResult] = field(default_factory=list)

    # Gate 结果
    gate_results: Dict[str, Any] = field(default_factory=dict)

    # 统计
    total_input_count: int = 0
    success_count: int = 0
    failed_count: int = 0

    # 元数据
    compiled_at: float = field(default_factory=time.time)
    compiler_version: str = "2.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_spec(self, spec: CanonicalSpec) -> None:
        """添加编译后的规范"""
        self.canonical_specs.append(spec)

    def add_result(self, result: CompilationResult) -> None:
        """添加编译结果"""
        self.compilation_results.append(result)
        if result.success:
            self.success_count += 1
        else:
            self.failed_count += 1

    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.total_input_count == 0:
            return 1.0
        return self.success_count / self.total_input_count

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "output_id": self.output_id,
            "canonical_specs": [s.to_dict() for s in self.canonical_specs],
            "gate_results": self.gate_results,
            "total_input_count": self.total_input_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "success_rate": self.get_success_rate(),
            "compiled_at": self.compiled_at,
            "compiler_version": self.compiler_version,
            "metadata": self.metadata,
        }


# ============================================================================
# Factory Functions
# ============================================================================

def create_phase2_input(phase1_output: Phase1Output, **config_kwargs) -> Phase2Input:
    """创建 Phase 2 输入"""
    config = CompilerConfig(**config_kwargs)
    return Phase2Input(
        phase1_output=phase1_output,
        config=config,
    )

def create_compiled_knowledge() -> CompiledKnowledge:
    """创建编译知识输出"""
    return CompiledKnowledge()


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Enums
    "TeachIntent",
    "SpecType",
    "CompilationStatus",
    # Teach Layer
    "CaptureContext",
    "TeachCapture",
    "ParsedTeach",
    # Compiler Layer
    "CanonicalSpec",
    "CompilationResult",
    # Input/Output
    "CompilerConfig",
    "Phase2Input",
    "CompiledKnowledge",
    # Factory
    "create_phase2_input",
    "create_compiled_knowledge",
]
