#!/usr/bin/env python3
"""
Phase 2 Teach Layer: Parser Module

将 TeachCapture 解析为 ParsedTeach。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from knowledge_compiler.phase1.schema import TeachOperation
from knowledge_compiler.phase2.schema import (
    TeachCapture,
    ParsedTeach,
    TeachIntent,
)


class ParseResult(Enum):
    """解析结果状态"""
    SUCCESS = "success"
    PARTIAL = "partial"  # 部分解析成功
    FAILED = "failed"    # 解析失败


@dataclass
class ParseMetadata:
    """解析元数据"""
    parse_duration_ms: float = 0.0
    confidence_factors: Dict[str, float] = field(default_factory=dict)
    intent_keywords: List[str] = field(default_factory=list)
    generalization_factors: Dict[str, bool] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class KnowledgeParser:
    """
    知识解析器

    将 TeachCapture 解析为 ParsedTeach，识别教学意图、泛化性等。
    """

    # 意图识别关键词映射
    INTENT_KEYWORDS = {
        TeachIntent.CORRECT_ERROR: {
            "fix", "correct", "error", "bug", "mistake", "wrong",
            "修复", "纠正", "错误", "bug", "修正",
        },
        TeachIntent.ADD_COMPONENT: {
            "add", "new", "create", "include", "append",
            "添加", "新增", "创建", "加入", "增加",
        },
        TeachIntent.MODIFY_STANDARD: {
            "update", "change", "modify", "adjust", "refine",
            "更新", "修改", "调整", "改进", "优化",
        },
        TeachIntent.GENERALIZE_KNOWLEDGE: {
            "generalize", "pattern", "template", "reuse", "apply",
            "泛化", "模式", "模板", "复用", "通用",
        },
        TeachIntent.REFINE_SCOPE: {
            "scope", "limit", "restrict", "narrow", "focus",
            "范围", "限制", "缩小", "聚焦", "限定",
        },
    }

    # 高泛化性指标
    GENERALIZATION_INDICATORS = {
        "has_multiple_sources": True,      # 多个来源
        "has_cross_case_context": True,    # 跨 case 上下文
        "explicitly_generalizable": True,  # 明确标记为可泛化
        "pattern_based": True,             # 基于模式
        "high_confidence": True,           # 高置信度
    }

    def __init__(self, min_confidence: float = 0.3):
        """
        Initialize the parser

        Args:
            min_confidence: 最低置信度阈值
        """
        self.min_confidence = min_confidence

    def parse(
        self,
        capture: TeachCapture,
    ) -> ParsedTeach:
        """
        解析 TeachCapture 为 ParsedTeach

        Args:
            capture: TeachCapture 实例

        Returns:
            ParsedTeach 实例
        """
        start_time = time.time()

        # 提取操作描述文本
        operation_texts = self._extract_operation_texts(capture)

        # 识别意图
        intent = self._classify_intent(operation_texts)

        # 评估泛化性
        generalizable = self._assess_generalizability(capture, operation_texts)

        # 计算置信度
        confidence = self._calculate_confidence(capture, intent, generalizable)

        # 提取影响组件
        affected_components = self._extract_affected_components(capture)

        # 提取知识
        extracted_knowledge = self._extract_knowledge(capture, intent)

        # 创建 ParsedTeach
        parsed_teach = ParsedTeach(
            source_capture_id=capture.capture_id,
            intent=intent,
            generalizable=generalizable,
            confidence=confidence,
            extracted_knowledge=extracted_knowledge,
            affected_components=affected_components,
            parsed_at=time.time(),
            parser_version="2.0",
            metadata={
                "operation_count": len(capture.raw_operations),
                "problem_type": capture.context.problem_type.value,
                "solver_type": capture.context.solver_type,
            },
        )

        return parsed_teach

    def parse_batch(
        self,
        captures: List[TeachCapture],
    ) -> List[ParsedTeach]:
        """
        批量解析 TeachCapture

        Args:
            captures: TeachCapture 列表

        Returns:
            ParsedTeach 列表
        """
        return [self.parse(capture) for capture in captures]

    def _extract_operation_texts(self, capture: TeachCapture) -> List[str]:
        """提取操作描述文本"""
        texts = []
        for op in capture.raw_operations:
            # 从 description 提取
            if hasattr(op, "description") and op.description:
                texts.append(op.description)
            # 从 operation_type 提取
            if hasattr(op, "operation_type") and op.operation_type:
                texts.append(op.operation_type)
            # 从 reason 提取
            if hasattr(op, "reason") and op.reason:
                texts.append(op.reason)
        return texts

    def _classify_intent(self, texts: List[str]) -> TeachIntent:
        """
        分类教学意图

        Args:
            texts: 操作文本列表

        Returns:
            识别的 TeachIntent
        """
        # 统计每个意图的关键词匹配数
        intent_scores = {intent: 0 for intent in TeachIntent}

        combined_text = " ".join(texts).lower()

        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    intent_scores[intent] += 1

        # 返回得分最高的意图
        max_intent = max(intent_scores, key=intent_scores.get)

        # 如果没有匹配，默认为 MODIFY_STANDARD
        if intent_scores[max_intent] == 0:
            return TeachIntent.MODIFY_STANDARD

        return max_intent

    def _assess_generalizability(
        self,
        capture: TeachCapture,
        texts: List[str],
    ) -> bool:
        """
        评估泛化性

        Args:
            capture: TeachCapture 实例
            texts: 操作文本列表

        Returns:
            是否可泛化
        """
        factors = {}

        # 1. 检查是否有多个来源
        factors["has_multiple_sources"] = len(capture.raw_operations) > 1

        # 2. 检查是否跨 case (通过 metadata 而非 source_case_ids)
        factors["has_cross_case_context"] = capture.metadata.get("cross_case", False)

        # 3. 检查是否明确标记为可泛化
        combined_text = " ".join(texts).lower()
        factors["explicitly_generalizable"] = any(
            keyword in combined_text
            for keyword in ["pattern", "template", "generalize", "reusable",
                          "模式", "模板", "泛化", "复用"]
        )

        # 4. 检查是否基于模式
        factors["pattern_based"] = any(
            "pattern" in text.lower() or "模式" in text
            for text in texts
        )

        # 5. 检查操作是否标记为可泛化
        factors["operations_generalizable"] = any(
            getattr(op, "is_generalizable", False)
            for op in capture.raw_operations
        )

        # 计算泛化性因子满足数量
        satisfied_count = sum(factors.values())

        # 至少满足 2 个因子才认为可泛化
        return satisfied_count >= 2

    def _calculate_confidence(
        self,
        capture: TeachCapture,
        intent: TeachIntent,
        generalizable: bool,
    ) -> float:
        """
        计算置信度

        Args:
            capture: TeachCapture 实例
            intent: 教学意图
            generalizable: 是否可泛化

        Returns:
            置信度 (0.0 - 1.0)
        """
        factors = {}

        # 1. 操作数量因子
        op_count = len(capture.raw_operations)
        factors["operation_count"] = min(1.0, op_count * 0.2)

        # 2. 泛化性因子
        factors["generalizable"] = 0.3 if generalizable else 0.0

        # 3. 意图明确性因子
        factors["intent_clarity"] = 0.2 if intent != TeachIntent.MODIFY_STANDARD else 0.1

        # 4. 上下文完整性因子
        factors["context_completeness"] = 0.2 if (
            capture.context.case_id and
            capture.context.solver_type and
            capture.context.problem_type
        ) else 0.1

        # 5. 来源追踪因子
        factors["has_sources"] = 0.1 if (
            capture.source_report_spec or
            capture.source_correction_specs
        ) else 0.0

        # 计算总置信度
        confidence = sum(factors.values())

        # 限制在 [0.0, 1.0] 范围内
        return max(0.0, min(1.0, confidence))

    def _extract_affected_components(
        self,
        capture: TeachCapture,
    ) -> List[str]:
        """
        提取受影响的组件

        Args:
            capture: TeachCapture 实例

        Returns:
            受影响的组件列表
        """
        components = set()

        # 从操作中提取组件信息
        for op in capture.raw_operations:
            if hasattr(op, "affected_components"):
                if isinstance(op.affected_components, list):
                    components.update(op.affected_components)
                elif isinstance(op.affected_components, str):
                    components.add(op.affected_components)

            # 从 description 中提取组件名（简单模式）
            if hasattr(op, "description"):
                # 查找常见组件模式
                matches = re.findall(
                    r'\b(report|plot|metric|section|workflow|boundary|mesh|solver)\b',
                    op.description,
                    re.IGNORECASE
                )
                components.update(matches)

        return sorted(components)

    def _extract_knowledge(
        self,
        capture: TeachCapture,
        intent: TeachIntent,
    ) -> Dict[str, Any]:
        """
        提取知识内容

        Args:
            capture: TeachCapture 实例
            intent: 教学意图

        Returns:
            提取的知识字典
        """
        knowledge = {
            "intent": intent.value,
            "operations": [],
            "context": {
                "case_id": capture.context.case_id,
                "solver_type": capture.context.solver_type,
                "problem_type": capture.context.problem_type.value,
            },
        }

        # 提取操作知识
        for op in capture.raw_operations:
            op_knowledge = {
                "type": getattr(op, "operation_type", "unknown"),
                "description": getattr(op, "description", ""),
            }

            # 添加原因
            if hasattr(op, "reason") and op.reason:
                op_knowledge["reason"] = op.reason

            # 添加泛化标记
            if hasattr(op, "is_generalizable"):
                op_knowledge["generalizable"] = op.is_generalizable

            knowledge["operations"].append(op_knowledge)

        return knowledge


# 便捷别名
TeachParser = KnowledgeParser


def parse_teach_capture(
    capture: TeachCapture,
    min_confidence: float = 0.3,
) -> ParsedTeach:
    """
    便捷函数：解析单个 TeachCapture

    Args:
        capture: TeachCapture 实例
        min_confidence: 最低置信度阈值

    Returns:
        ParsedTeach 实例
    """
    parser = KnowledgeParser(min_confidence=min_confidence)
    return parser.parse(capture)


def parse_teach_captures(
    captures: List[TeachCapture],
    min_confidence: float = 0.3,
) -> List[ParsedTeach]:
    """
    便捷函数：批量解析 TeachCapture

    Args:
        captures: TeachCapture 列表
        min_confidence: 最低置信度阈值

    Returns:
        ParsedTeach 列表
    """
    parser = KnowledgeParser(min_confidence=min_confidence)
    return parser.parse_batch(captures)


__all__ = [
    "KnowledgeParser",
    "TeachParser",
    "ParseResult",
    "ParseMetadata",
    "parse_teach_capture",
    "parse_teach_captures",
]
