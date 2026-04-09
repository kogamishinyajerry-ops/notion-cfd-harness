#!/usr/bin/env python3
"""
Phase 2 Gate G1-P2: Knowledge Completeness Gate

验证知识的完整性，确保编译后的知识包含所有必需字段。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Set

from knowledge_compiler.phase2.gates.gates import (
    GateStatus,
    GateCheckItem,
    GateResult,
)


G1_P2_GATE_ID = "G1-P2"


class KnowledgeCompletenessGate:
    """
    G1-P2: 知识完整性 Gate

    验证 CanonicalSpec 是否包含所有必需字段，确保知识质量。
    这是 Phase 2 的 BLOCK 级别 Gate，不完整的知识不能进入系统。
    """

    GATE_ID = G1_P2_GATE_ID
    GATE_NAME = "Knowledge Completeness Gate"

    # 根据 SpecType 定义的必填字段
    REQUIRED_FIELDS_BY_TYPE = {
        "report_spec": {
            "name",
            "problem_type",
            "required_plots",
            "required_metrics",
        },
        "plot_standard": {
            "plot_type",
            "field",
            "colormap",
            "plane",
        },
        "metric_standard": {
            "metric_name",
            "unit",
            "calculation_method",
        },
        "section_rule": {
            "section_location",
            "required_fields",
        },
        "workflow": {
            "workflow_name",
            "steps",
            "inputs",
            "outputs",
        },
    }

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the gate

        Args:
            strict_mode: 如果为 True，所有字段必须完整；False 则允许警告模式
        """
        self.strict_mode = strict_mode

    def check(self, spec: "CanonicalSpec") -> GateResult:
        """
        检查单个 CanonicalSpec

        Args:
            spec: CanonicalSpec 实例

        Returns:
            GateResult 检查结果
        """
        checklist = []
        errors = []
        warnings = []
        score = 100.0

        # 提取 spec_type
        spec_type = getattr(spec, "spec_type", None)
        if spec_type is None:
            return GateResult(
                gate_id=self.GATE_ID,
                gate_name=self.GATE_NAME,
                status=GateStatus.FAIL,
                timestamp=time.time(),
                score=0.0,
                checklist=[],
                errors=["spec_type is missing"],
                warnings=[],
                metadata={"error": "no_spec_type"},
                severity="BLOCK",
            )

        # 获取必填字段
        required_fields = self._get_required_fields(spec_type)

        # 检查每个必填字段
        content = getattr(spec, "content", {})

        for field in required_fields:
            result, message = self._check_field(content, field)
            checklist.append(GateCheckItem(
                item=field,
                description=f"Required field: {field}",
                result=result,
                message=message,
            ))

            if result == GateStatus.FAIL:
                errors.append(message)
                score -= 12.5  # 8 fields * 12.5 = 100
            elif result == GateStatus.WARN:
                warnings.append(message)
                score -= 6.25

        # 检查 spec_id
        spec_id = getattr(spec, "spec_id", None)
        if not spec_id:
            errors.append("spec_id is missing")
            score -= 25.0

        # 检查来源追踪
        source_teach_ids = getattr(spec, "source_teach_ids", [])
        source_case_ids = getattr(spec, "source_case_ids", [])

        if not source_teach_ids and not source_case_ids:
            warnings.append("No source tracking information")

        # 确定最终状态
        status = GateStatus.PASS
        if score < 50.0 or (self.strict_mode and errors):
            status = GateStatus.FAIL
        elif score < 75.0:
            status = GateStatus.WARN

        return GateResult(
            gate_id=self.GATE_ID,
            gate_name=self.GATE_NAME,
            status=status,
            timestamp=time.time(),
            score=max(0.0, score),
            checklist=checklist,
            errors=errors,
            warnings=warnings,
            metadata={
                "spec_id": spec_id or "unknown",
                "spec_type": spec_type.value if spec_type else "unknown",
                "strict_mode": self.strict_mode,
                "fields_checked": len(required_fields),
            },
            severity="BLOCK",
        )

    def check_batch(self, specs: List) -> GateResult:
        """
        批量检查多个 CanonicalSpec

        Args:
            specs: CanonicalSpec 列表

        Returns:
            汇总的 GateResult
        """
        all_checklist = []
        all_errors = []
        all_warnings = []
        total_score = 0.0

        pass_count = 0
        fail_count = 0

        for spec in specs:
            result = self.check(spec)
            all_checklist.extend(result.checklist)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            total_score += result.score

            if result.is_pass():
                pass_count += 1
            else:
                fail_count += 1

        # 计算平均分数
        avg_score = total_score / len(specs) if specs else 100.0

        # 确定整体状态
        status = GateStatus.PASS
        if fail_count > 0:
            status = GateStatus.FAIL
        elif avg_score < 75.0:
            status = GateStatus.WARN

        return GateResult(
            gate_id=self.GATE_ID,
            gate_name=f"{self.GATE_NAME} (Batch)",
            status=status,
            timestamp=time.time(),
            score=avg_score,
            checklist=all_checklist,
            errors=all_errors,
            warnings=all_warnings,
            metadata={
                "total_checked": len(specs),
                "pass_count": pass_count,
                "fail_count": fail_count,
                "pass_rate": (pass_count / len(specs) * 100) if specs else 100.0,
            },
            severity="BLOCK",
        )

    def _get_required_fields(self, spec_type) -> Set[str]:
        """获取指定 spec_type 的必填字段"""
        if hasattr(spec_type, "value"):
            spec_type_str = spec_type.value
        else:
            spec_type_str = str(spec_type)

        return self.REQUIRED_FIELDS_BY_TYPE.get(
            spec_type_str,
            set(),  # 返回空集合表示未知类型
        )

    def _check_field(self, content: Dict, field: str) -> tuple[GateStatus, str]:
        """检查单个字段"""
        if field not in content:
            return GateStatus.FAIL, f"Missing required field: {field}"

        value = content[field]

        # 检查字段值是否有效
        if field in ["name", "plot_type", "metric_name", "section_location", "workflow_name"]:
            if not value or not isinstance(value, str):
                return GateStatus.FAIL, f"Field {field} must be a non-empty string"

        if field in ["problem_type", "calculation_method"]:
            if not value:
                return GateStatus.FAIL, f"Field {field} cannot be empty"

        if field in ["required_plots", "required_metrics", "steps"]:
            if not isinstance(value, list) or len(value) == 0:
                return GateStatus.WARN, f"Field {field} should be a non-empty list"

        if field in ["inputs", "outputs"]:
            if not isinstance(value, list) or len(value) == 0:
                return GateStatus.WARN, f"Field {field} should be a non-empty list"

        return GateStatus.PASS, f"Field {field} is valid"


# Export
__all__ = [
    "KnowledgeCompletenessGate",
    "G1_P2_GATE_ID",
]
