#!/usr/bin/env python3
"""
Phase 2 Compiler Layer: Canonical Compiler

将 ParsedTeach 编译为 CanonicalSpec。
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from knowledge_compiler.phase2.schema import (
    ParsedTeach,
    CanonicalSpec,
    SpecType,
    KnowledgeStatus,
    CompilationResult,
    TeachIntent,
)
from knowledge_compiler.phase1.schema import KnowledgeLayer


class CanonicalCompiler:
    """
    标准知识编译器

    将 ParsedTeach 编译为 CanonicalSpec。
    """

    def __init__(self, merge_conflicts: bool = True):
        """
        Initialize the compiler

        Args:
            merge_conflicts: 是否合并冲突的知识
        """
        self.merge_conflicts = merge_conflicts
        self._compilation_log: List[str] = []

    def compile(
        self,
        parsed_teach: ParsedTeach,
    ) -> CompilationResult:
        """
        编译单个 ParsedTeach 为 CanonicalSpec

        Args:
            parsed_teach: ParsedTeach 实例

        Returns:
            CompilationResult
        """
        self._compilation_log = []
        start_time = time.time()

        try:
            # 确定 SpecType
            spec_type = self._determine_spec_type(parsed_teach)

            # 编译内容
            content = self._compile_content(parsed_teach, spec_type)

            # 创建 CanonicalSpec
            spec = CanonicalSpec(
                spec_type=spec_type,
                content=content,
                spec_id=f"SPEC-{uuid.uuid4().hex[:8]}",
                version="1.0",
                knowledge_status=self._determine_status(parsed_teach),
                knowledge_layer=self._determine_layer(parsed_teach),
                source_teach_ids=[parsed_teach.teach_id],
                created_at=time.time(),
                created_by=parsed_teach.metadata.get("engineer_id"),
                metadata={
                    "parsed_from": parsed_teach.teach_id,
                    "confidence": parsed_teach.confidence,
                    "intent": parsed_teach.intent.value,
                },
            )

            duration_ms = (time.time() - start_time) * 1000

            return CompilationResult(
                success=True,
                output=spec,
                compilation_log=self._compilation_log.copy(),
                duration_ms=duration_ms,
                input_teach_count=1,
                output_spec_count=1,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return CompilationResult(
                success=False,
                output=None,
                errors=[f"Compilation failed: {str(e)}"],
                compilation_log=self._compilation_log.copy(),
                duration_ms=duration_ms,
                input_teach_count=1,
                output_spec_count=0,
            )

    def compile_batch(
        self,
        teaches: List[ParsedTeach],
    ) -> List[CompilationResult]:
        """
        批量编译 ParsedTeach

        Args:
            teaches: ParsedTeach 列表

        Returns:
            CompilationResult 列表
        """
        return [self.compile(teach) for teach in teaches]

    def merge_specs(
        self,
        specs: List[CanonicalSpec],
        spec_type: Optional[SpecType] = None,
    ) -> CanonicalSpec:
        """
        合并多个 CanonicalSpec

        Args:
            specs: CanonicalSpec 列表
            spec_type: 目标 SpecType（如果为 None 则从第一个 spec 推断）

        Returns:
            合并后的 CanonicalSpec
        """
        if not specs:
            raise ValueError("Cannot merge empty specs list")

        # 确定 SpecType
        if spec_type is None:
            spec_type = specs[0].spec_type

        # 按 SpecType 过滤
        filtered_specs = [s for s in specs if s.spec_type == spec_type]

        if not filtered_specs:
            # 如果没有匹配的，创建一个新的
            return CanonicalSpec(
                spec_type=spec_type,
                content={},
            )

        # 合并内容
        merged_content = {}
        all_source_teach_ids: Set[str] = set()
        all_source_case_ids: Set[str] = set()

        for spec in filtered_specs:
            # 合并 content
            for key, value in spec.content.items():
                if key not in merged_content:
                    merged_content[key] = value
                elif self.merge_conflicts:
                    # 后者覆盖前者
                    merged_content[key] = value
                    self._compilation_log.append(
                        f"Merged conflict for key '{key}': using value from {spec.spec_id}"
                    )

            # 收集来源
            all_source_teach_ids.update(spec.source_teach_ids)
            all_source_case_ids.update(spec.source_case_ids)

        # 确定状态（最高优先级的状态）
        status_priority = [
            KnowledgeStatus.APPROVED,
            KnowledgeStatus.CANDIDATE,
            KnowledgeStatus.DRAFT,
            KnowledgeStatus.DEPRECATED,
        ]
        merged_status = KnowledgeStatus.DRAFT
        for status in status_priority:
            if any(s.knowledge_status == status for s in filtered_specs):
                merged_status = status
                break

        # 创建合并后的 Spec
        merged_spec = CanonicalSpec(
            spec_type=spec_type,
            content=merged_content,
            spec_id=f"SPEC-MERGED-{uuid.uuid4().hex[:8]}",
            version="1.0",
            knowledge_status=merged_status,
            knowledge_layer=KnowledgeLayer.CANONICAL,
            source_teach_ids=sorted(all_source_teach_ids),
            source_case_ids=sorted(all_source_case_ids),
            created_at=time.time(),
            metadata={
                "merged_from": [s.spec_id for s in filtered_specs],
                "merge_count": len(filtered_specs),
            },
        )

        return merged_spec

    def compile_by_type(
        self,
        teaches: List[ParsedTeach],
    ) -> Dict[SpecType, List[CanonicalSpec]]:
        """
        按 SpecType 分类编译

        Args:
            teaches: ParsedTeach 列表

        Returns:
            Dict[SpecType, List[CanonicalSpec]]
        """
        results = defaultdict(list)

        for teach in teaches:
            result = self.compile(teach)
            if result.success and result.output:
                spec_type = result.output.spec_type
                results[spec_type].append(result.output)

        return dict(results)

    def _determine_spec_type(self, teach: ParsedTeach) -> SpecType:
        """根据 ParsedTeach 确定 SpecType"""
        # 从 extracted_knowledge 中推断
        knowledge = teach.extracted_knowledge

        # 检查操作类型
        operations = knowledge.get("operations", [])
        if not operations:
            return SpecType.WORKFLOW_PATTERN

        # 分析第一个操作的类型
        first_op = operations[0] if operations else {}
        op_type = first_op.get("type", "").lower()

        # 映射操作类型到 SpecType
        op_to_spec = {
            "add_plot": SpecType.PLOT_STANDARD,
            "modify_plot": SpecType.PLOT_STANDARD,
            "remove_plot": SpecType.PLOT_STANDARD,
            "add_metric": SpecType.METRIC_STANDARD,
            "modify_metric": SpecType.METRIC_STANDARD,
            "remove_metric": SpecType.METRIC_STANDARD,
            "adjust_section": SpecType.SECTION_RULE,
            "modify_structure": SpecType.SECTION_RULE,
        }

        return op_to_spec.get(op_type, SpecType.WORKFLOW_PATTERN)

    def _compile_content(
        self,
        teach: ParsedTeach,
        spec_type: SpecType,
    ) -> Dict[str, Any]:
        """编译知识内容"""
        content = {}

        # 基础字段
        content["intent"] = teach.intent.value
        content["confidence"] = teach.confidence
        content["generalizable"] = teach.is_generalizable()
        content["affected_components"] = teach.affected_components

        # 根据不同 SpecType 编译特定字段
        if spec_type == SpecType.PLOT_STANDARD:
            content.update(self._compile_plot_content(teach))
        elif spec_type == SpecType.METRIC_STANDARD:
            content.update(self._compile_metric_content(teach))
        elif spec_type == SpecType.SECTION_RULE:
            content.update(self._compile_section_content(teach))
        elif spec_type == SpecType.WORKFLOW_PATTERN:
            content.update(self._compile_workflow_content(teach))
        elif spec_type == SpecType.REPORT_SPEC:
            content.update(self._compile_report_content(teach))

        return content

    def _compile_plot_content(self, teach: ParsedTeach) -> Dict[str, Any]:
        """编译图表标准内容"""
        content = {}
        operations = teach.extracted_knowledge.get("operations", [])

        # 从操作中提取图表信息
        for op in operations:
            if "plot" in op.get("type", "").lower():
                # 提取图表类型
                if "contour" in op.get("description", "").lower():
                    content["plot_type"] = "contour"
                elif "vector" in op.get("description", "").lower():
                    content["plot_type"] = "vector"
                else:
                    content["plot_type"] = "line"

                # 设置默认值
                if "colormap" not in content:
                    content["colormap"] = "viridis"
                if "plane" not in content:
                    content["plane"] = "xy"

        return content

    def _compile_metric_content(self, teach: ParsedTeach) -> Dict[str, Any]:
        """编译指标标准内容"""
        content = {}
        operations = teach.extracted_knowledge.get("operations", [])

        for op in operations:
            if "metric" in op.get("type", "").lower():
                content["metric_name"] = op.get("description", "unknown_metric")
                content["unit"] = "Pa"  # 默认单位
                content["calculation_method"] = op.get("reason", "standard")

        return content

    def _compile_section_content(self, teach: ParsedTeach) -> Dict[str, Any]:
        """编译章节规则内容"""
        content = {}
        operations = teach.extracted_knowledge.get("operations", [])

        for op in operations:
            if "section" in op.get("type", "").lower():
                content["section_location"] = op.get("description", "unknown")
                content["required_fields"] = ["title", "content"]

        return content

    def _compile_workflow_content(self, teach: ParsedTeach) -> Dict[str, Any]:
        """编译工作流模式内容"""
        content = {}
        operations = teach.extracted_knowledge.get("operations", [])

        steps = []
        for op in operations:
            steps.append(op.get("description", op.get("type", "unknown")))

        content["workflow_name"] = f"workflow_{teach.teach_id[:8]}"
        content["steps"] = steps
        content["inputs"] = teach.affected_components or ["case_data"]
        content["outputs"] = ["report"]

        return content

    def _compile_report_content(self, teach: ParsedTeach) -> Dict[str, Any]:
        """编译报告规范内容"""
        content = {}
        operations = teach.extracted_knowledge.get("operations", [])

        # 收集所有涉及的组件
        plots = set()
        metrics = set()

        for op in operations:
            if "plot" in op.get("type", "").lower():
                plots.add(op.get("description", "unknown_plot"))
            if "metric" in op.get("type", "").lower():
                metrics.add(op.get("description", "unknown_metric"))

        content["name"] = f"Report_{teach.teach_id[:8]}"
        content["required_plots"] = sorted(plots)
        content["required_metrics"] = sorted(metrics)

        return content

    def _determine_status(self, teach: ParsedTeach) -> KnowledgeStatus:
        """确定知识状态"""
        # 高置信度和可泛化的知识直接提升到 APPROVED
        if teach.confidence >= 0.8 and teach.is_generalizable():
            return KnowledgeStatus.APPROVED
        elif teach.confidence >= 0.5:
            return KnowledgeStatus.CANDIDATE
        else:
            return KnowledgeStatus.DRAFT

    def _determine_layer(self, teach: ParsedTeach) -> KnowledgeLayer:
        """确定知识层级"""
        # 可泛化的知识提升到 CANONICAL
        if teach.is_generalizable():
            return KnowledgeLayer.CANONICAL
        else:
            return KnowledgeLayer.RAW


__all__ = [
    "CanonicalCompiler",
]
