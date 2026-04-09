#!/usr/bin/env python3
"""
Phase 2c T3: Knowledge Compiler (Minimum Version)

知识编译器 - 从修正记录中提取可泛化知识并验证。

核心组件:
- KnowledgeExtractor: 从修正记录中提取可泛化知识
- KnowledgeValidator: 验证知识是否符合规范
- KnowledgeManager: 管理知识生命周期
- L2/L3 Knowledge Schemas: 结构化知识表示
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from knowledge_compiler.phase1.schema import KnowledgeLayer, KnowledgeStatus
from knowledge_compiler.phase2c.correction_recorder import (
    CorrectionRecord,
    ImpactScope,
)
from knowledge_compiler.phase2c.benchmark_replay import (
    BenchmarkReplayResult,
    BenchmarkSuite,
)


# ============================================================================
# Knowledge Level Enum (Extended from Phase 1)
# ============================================================================

class ExtendedKnowledgeLayer(Enum):
    """扩展的知识层级"""
    L1_CASE_SPECIFIC = "l1_case_specific"  # 特定案例知识
    L2_GENERALIZABLE = "l2_generalizable"    # 可泛化知识
    L3_CANONICAL = "l3_canonical"            # 规范化知识


# ============================================================================
# Knowledge Schemas
# ============================================================================

@dataclass
class PatternKnowledge:
    """模式知识 - 描述可复现的模式"""
    knowledge_id: str
    name: str
    description: str

    # 模式定义
    pattern_type: str  # "anomaly_pattern", "fix_pattern", "prevention_pattern"
    trigger_conditions: Dict[str, Any]  # 触发条件
    pattern_signature: Dict[str, Any]     # 模式特征
    recommended_actions: List[str]        # 建议操作

    # 验证信息
    confidence_score: float = 0.0         # 0-1 置信度
    evidence_count: int = 0               # 支持证据数量
    success_rate: float = 0.0             # 应用成功率

    # 元数据
    knowledge_layer: ExtendedKnowledgeLayer = ExtendedKnowledgeLayer.L2_GENERALIZABLE
    knowledge_status: KnowledgeStatus = KnowledgeStatus.DRAFT
    source_corrections: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_evidence(self, correction_id: str) -> None:
        """添加支持证据"""
        if correction_id not in self.source_corrections:
            self.source_corrections.append(correction_id)
            self.evidence_count += 1
            self.updated_at = time.time()

    def update_confidence(self, new_score: float) -> None:
        """更新置信度"""
        self.confidence_score = max(0.0, min(1.0, new_score))
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "knowledge_id": self.knowledge_id,
            "name": self.name,
            "description": self.description,
            "pattern_type": self.pattern_type,
            "trigger_conditions": self.trigger_conditions,
            "pattern_signature": self.pattern_signature,
            "recommended_actions": self.recommended_actions,
            "confidence_score": self.confidence_score,
            "evidence_count": self.evidence_count,
            "success_rate": self.success_rate,
            "knowledge_layer": self.knowledge_layer.value,
            "knowledge_status": self.knowledge_status.value,
            "source_corrections": self.source_corrections,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class RuleKnowledge:
    """规则知识 - 描述约束规则"""
    knowledge_id: str
    name: str
    description: str

    # 规则定义
    rule_type: str  # "validation_rule", "constraint_rule", "quality_rule"
    rule_expression: Dict[str, Any]      # 规则表达式
    scope: ImpactScope                    # 应用范围

    # 应用统计
    application_count: int = 0
    violation_count: int = 0
    compliance_rate: float = 1.0

    # 元数据
    knowledge_layer: ExtendedKnowledgeLayer = ExtendedKnowledgeLayer.L3_CANONICAL
    knowledge_status: KnowledgeStatus = KnowledgeStatus.DRAFT
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def record_application(self, is_violation: bool) -> None:
        """记录应用结果"""
        self.application_count += 1
        if is_violation:
            self.violation_count += 1
        self.compliance_rate = 1.0 - (self.violation_count / self.application_count)
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "knowledge_id": self.knowledge_id,
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type,
            "rule_expression": self.rule_expression,
            "scope": self.scope.value,
            "application_count": self.application_count,
            "violation_count": self.violation_count,
            "compliance_rate": self.compliance_rate,
            "knowledge_layer": self.knowledge_layer.value,
            "knowledge_status": self.knowledge_status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ============================================================================
# Knowledge Extractor
# ============================================================================

class KnowledgeExtractor(ABC):
    """知识提取器抽象基类"""

    @abstractmethod
    def extract(self, correction: CorrectionRecord) -> Optional[PatternKnowledge]:
        """从修正记录中提取知识"""
        pass


class AnomalyPatternExtractor(KnowledgeExtractor):
    """异常模式提取器"""

    def extract(self, correction: CorrectionRecord) -> Optional[PatternKnowledge]:
        """提取异常模式知识"""
        # 分析异常模式
        pattern_signature = self._analyze_pattern(correction)
        if not pattern_signature:
            return None

        knowledge_id = f"PAT-{int(time.time())}-{self._generate_hash(correction)}"

        knowledge = PatternKnowledge(
            knowledge_id=knowledge_id,
            name=f"异常模式: {correction.error_type.value}",
            description=f"从修正 {correction.record_id} 提取的异常模式",
            pattern_type="anomaly_pattern",
            trigger_conditions=self._extract_trigger_conditions(correction),
            pattern_signature=pattern_signature,
            recommended_actions=[correction.fix_action],
            confidence_score=self._calculate_confidence(correction),
            evidence_count=1,
            source_corrections=[correction.record_id],
        )

        return knowledge

    def _analyze_pattern(self, correction: CorrectionRecord) -> Optional[Dict[str, Any]]:
        """分析模式特征"""
        if not correction.root_cause or not correction.fix_action:
            return None

        return {
            "error_type": correction.error_type.value,
            "impact_scope": correction.impact_scope.value,
            "root_cause_category": self._categorize_root_cause(correction.root_cause),
            "fix_action_type": self._categorize_fix_action(correction.fix_action),
        }

    def _extract_trigger_conditions(self, correction: CorrectionRecord) -> Dict[str, Any]:
        """提取触发条件"""
        conditions = {
            "error_types": [correction.error_type.value],
            "impact_scopes": [correction.impact_scope.value],
        }

        # 从 evidence 中提取额外条件
        for evidence in correction.evidence:
            if "validation_id" in evidence:
                conditions.setdefault("validation_context", []).append(evidence)
            elif "anomaly" in evidence.lower():
                conditions.setdefault("has_anomaly", True)

        return conditions

    def _categorize_root_cause(self, root_cause: str) -> str:
        """分类根因"""
        categories = {
            "边界": "boundary_condition",
            "网格": "mesh_quality",
            "数值": "numerical_stability",
            "公式": "formula_error",
            "配置": "configuration_error",
        }

        for keyword, category in categories.items():
            if keyword in root_cause:
                return category

        return "other"

    def _categorize_fix_action(self, fix_action: str) -> str:
        """分类修正动作"""
        categories = {
            "修正": "correction",
            "添加": "addition",
            "删除": "removal",
            "更新": "update",
            "检查": "verification",
        }

        for keyword, category in categories.items():
            if keyword in fix_action:
                return category

        return "general"

    def _calculate_confidence(self, correction: CorrectionRecord) -> float:
        """计算置信度"""
        score = 0.5  # 基础置信度

        # 有详细根因分析
        if len(correction.root_cause) > 20:
            score += 0.1

        # 有具体修正动作
        if len(correction.fix_action) > 10:
            score += 0.1

        # 有充分证据
        if len(correction.evidence) >= 2:
            score += 0.1

        # 影响范围明确
        if correction.impact_scope != ImpactScope.SINGLE_CASE:
            score += 0.1

        # 需要回放验证
        if correction.needs_replay:
            score += 0.1

        return min(1.0, score)

    def _generate_hash(self, correction: CorrectionRecord) -> str:
        """生成唯一标识"""
        content = f"{correction.error_type.value}:{correction.root_cause}:{correction.fix_action}"
        return hashlib.md5(content.encode()).hexdigest()[:8]


class FixPatternExtractor(KnowledgeExtractor):
    """修正模式提取器"""

    def extract(self, correction: CorrectionRecord) -> Optional[PatternKnowledge]:
        """提取修正模式知识"""
        # 提取修正模式
        pattern_signature = self._extract_fix_pattern(correction)
        if not pattern_signature:
            return None

        knowledge_id = f"FIX-{int(time.time())}-{self._generate_hash(correction)}"

        knowledge = PatternKnowledge(
            knowledge_id=knowledge_id,
            name=f"修正模式: {pattern_signature['fix_type']}",
            description=f"针对 {correction.error_type.value} 的修正模式",
            pattern_type="fix_pattern",
            trigger_conditions={
                "error_types": [correction.error_type.value],
                "fix_types": [pattern_signature['fix_type']],
            },
            pattern_signature=pattern_signature,
            recommended_actions=self._extract_generalized_actions(correction),
            confidence_score=0.6,  # 修正模式初始置信度
            evidence_count=1,
            source_corrections=[correction.record_id],
        )

        return knowledge

    def _extract_fix_pattern(self, correction: CorrectionRecord) -> Optional[Dict[str, Any]]:
        """提取修正模式"""
        if not correction.fix_action:
            return None

        # 分析修正动作模式
        fix_action = correction.fix_action.lower()

        # 识别修正类型
        fix_type = "general"
        if "边界" in fix_action or "boundary" in fix_action:
            fix_type = "boundary_fix"
        elif "网格" in fix_action or "mesh" in fix_action:
            fix_type = "mesh_fix"
        elif "公式" in fix_action or "algorithm" in fix_action:
            fix_type = "algorithm_fix"
        elif "参数" in fix_action or "parameter" in fix_action:
            fix_type = "parameter_fix"

        return {
            "fix_type": fix_type,
            "action_keywords": self._extract_keywords(correction.fix_action),
            "target_scope": correction.impact_scope.value,
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取（实际应该用更复杂的NLP）
        keywords = []
        important_words = ["修正", "调整", "更新", "添加", "删除", "检查", "验证"]

        for word in important_words:
            if word in text:
                keywords.append(word)

        return keywords

    def _extract_generalized_actions(self, correction: CorrectionRecord) -> List[str]:
        """提取泛化动作"""
        actions = []

        # 将具体动作泛化
        fix_action = correction.fix_action

        # 提取动作模板
        if "修正" in fix_action:
            # 替换具体值为占位符
            generalized = re.sub(r'\d+', '{value}', fix_action)
            actions.append(generalized)

        return actions if actions else [fix_action]

    def _generate_hash(self, correction: CorrectionRecord) -> str:
        """生成唯一标识"""
        content = f"{correction.fix_action}:{correction.impact_scope.value}"
        return hashlib.md5(content.encode()).hexdigest()[:8]


# ============================================================================
# Knowledge Validator
# ============================================================================

class KnowledgeValidator:
    """知识验证器"""

    def __init__(
        self,
        min_confidence: float = 0.6,
        min_evidence: int = 1,
        min_success_rate: float = 0.7,
    ):
        self.min_confidence = min_confidence
        self.min_evidence = min_evidence
        self.min_success_rate = min_success_rate

    def validate(
        self,
        knowledge: PatternKnowledge,
        replay_results: Optional[List[BenchmarkReplayResult]] = None,
    ) -> Tuple[bool, List[str]]:
        """验证知识质量"""
        violations = []

        # 检查置信度
        if knowledge.confidence_score < self.min_confidence:
            violations.append(f"置信度不足: {knowledge.confidence_score:.2f} < {self.min_confidence}")

        # 检查证据数量
        if knowledge.evidence_count < self.min_evidence:
            violations.append(f"证据不足: {knowledge.evidence_count} < {self.min_evidence}")

        # 检查成功率
        actual_success_rate = knowledge.success_rate
        if replay_results:
            # 从回放结果计算实际成功率
            successful = sum(1 for r in replay_results if r.is_successful)
            actual_success_rate = successful / len(replay_results) if replay_results else 0.0

        if actual_success_rate < self.min_success_rate:
            violations.append(f"成功率不足: {actual_success_rate:.2%} < {self.min_success_rate}")

        # 检查模式完整性
        if not knowledge.pattern_signature:
            violations.append("缺少模式特征定义")

        if not knowledge.trigger_conditions:
            violations.append("缺少触发条件定义")

        # 检查建议动作
        if not knowledge.recommended_actions:
            violations.append("缺少建议动作")

        is_valid = len(violations) == 0
        return is_valid, violations

    def calculate_quality_score(
        self,
        knowledge: PatternKnowledge,
        replay_results: Optional[List[BenchmarkReplayResult]] = None,
    ) -> float:
        """计算知识质量分数"""
        score = 0.0

        # 置信度贡献 (30%)
        score += knowledge.confidence_score * 0.3

        # 证据数量贡献 (20%)
        evidence_score = min(1.0, knowledge.evidence_count / 5.0)  # 5个证据为满分
        score += evidence_score * 0.2

        # 成功率贡献 (30%)
        if replay_results:
            successful = sum(1 for r in replay_results if r.is_successful)
            success_rate = successful / len(replay_results)
            score += success_rate * 0.3
        else:
            score += knowledge.success_rate * 0.3

        # 完整性贡献 (20%)
        completeness = 0.0
        if knowledge.pattern_signature:
            completeness += 0.25
        if knowledge.trigger_conditions:
            completeness += 0.25
        if knowledge.recommended_actions:
            completeness += 0.25
        if len(knowledge.source_corrections) > 0:
            completeness += 0.25
        score += completeness * 0.2

        return min(1.0, score)


# ============================================================================
# Knowledge Manager
# ============================================================================

class KnowledgeManager:
    """知识管理器"""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        validator: Optional[KnowledgeValidator] = None,
    ):
        self.storage_path = Path(storage_path) if storage_path else Path(".knowledge")
        self.validator = validator or KnowledgeValidator()

        # 知识存储
        self.patterns: Dict[str, PatternKnowledge] = {}
        self.rules: Dict[str, RuleKnowledge] = {}

        # 提取器注册
        self.extractors: List[KnowledgeExtractor] = [
            AnomalyPatternExtractor(),
            FixPatternExtractor(),
        ]

        # 加载已有知识
        self._load_knowledge()

    def _load_knowledge(self):
        """加载已有知识"""
        if not self.storage_path.exists():
            return

        # 加载模式知识
        patterns_dir = self.storage_path / "patterns"
        if patterns_dir.exists():
            for pattern_file in patterns_dir.rglob("*.json"):
                try:
                    with open(pattern_file) as f:
                        data = json.load(f)
                        pattern = PatternKnowledge(
                            knowledge_id=data["knowledge_id"],
                            name=data["name"],
                            description=data["description"],
                            pattern_type=data["pattern_type"],
                            trigger_conditions=data["trigger_conditions"],
                            pattern_signature=data["pattern_signature"],
                            recommended_actions=data["recommended_actions"],
                            confidence_score=data.get("confidence_score", 0.0),
                            evidence_count=data.get("evidence_count", 0),
                            success_rate=data.get("success_rate", 0.0),
                            knowledge_layer=ExtendedKnowledgeLayer(data.get("knowledge_layer", "l2_generalizable")),
                            knowledge_status=KnowledgeStatus(data.get("knowledge_status", "draft")),
                            source_corrections=data.get("source_corrections", []),
                            created_at=data.get("created_at", time.time()),
                            updated_at=data.get("updated_at", time.time()),
                        )
                        self.patterns[pattern.knowledge_id] = pattern
                except Exception as e:
                    print(f"Warning: Failed to load pattern from {pattern_file}: {e}")

    def extract_knowledge(
        self,
        correction: CorrectionRecord,
    ) -> List[PatternKnowledge]:
        """从修正记录中提取知识"""
        extracted = []

        for extractor in self.extractors:
            try:
                knowledge = extractor.extract(correction)
                if knowledge:
                    extracted.append(knowledge)
            except Exception as e:
                print(f"Warning: Extractor {extractor.__class__.__name__} failed: {e}")

        return extracted

    def validate_knowledge(
        self,
        knowledge: PatternKnowledge,
        replay_results: Optional[List[BenchmarkReplayResult]] = None,
    ) -> Tuple[bool, List[str]]:
        """验证知识"""
        return self.validator.validate(knowledge, replay_results)

    def add_pattern(
        self,
        pattern: PatternKnowledge,
        validate: bool = True,
    ) -> Tuple[bool, List[str]]:
        """添加模式知识"""
        if validate:
            is_valid, violations = self.validate_knowledge(pattern)
            if not is_valid:
                return False, violations

        self.patterns[pattern.knowledge_id] = pattern
        return True, []

    def update_pattern(
        self,
        knowledge_id: str,
        correction_id: str,
        replay_result: Optional[BenchmarkReplayResult] = None,
    ) -> Optional[PatternKnowledge]:
        """更新模式知识"""
        pattern = self.patterns.get(knowledge_id)
        if not pattern:
            return None

        # 添加新证据
        pattern.add_evidence(correction_id)

        # 更新成功率
        if replay_result:
            success_count = sum(1 for k, v in self.patterns.items() if k == knowledge_id)
            # 简化处理：实际应该跟踪所有回放结果
            pattern.success_rate = (pattern.success_rate * pattern.evidence_count +
                                 (1.0 if replay_result.is_successful else 0.0)) / pattern.evidence_count

        pattern.updated_at = time.time()
        return pattern

    def promote_to_l3(
        self,
        knowledge_id: str,
    ) -> Tuple[bool, str]:
        """将 L2 知识提升为 L3 规范"""
        pattern = self.patterns.get(knowledge_id)
        if not pattern:
            return False, "知识不存在"

        # 检查提升条件
        if pattern.knowledge_layer != ExtendedKnowledgeLayer.L2_GENERALIZABLE:
            return False, "只能提升 L2 知识"

        if pattern.knowledge_status != KnowledgeStatus.APPROVED:
            return False, "只能提升已批准的知识"

        if pattern.evidence_count < 3:
            return False, f"证据不足: {pattern.evidence_count} < 3"

        if pattern.success_rate < 0.9:
            return False, f"成功率不足: {pattern.success_rate:.2%} < 90%"

        # 创建 L3 规则知识
        rule_id = f"RULE-{int(time.time())}"
        rule = RuleKnowledge(
            knowledge_id=rule_id,
            name=f"规范规则: {pattern.name}",
            description=pattern.description,
            rule_type="validation_rule",
            rule_expression={
                "pattern_id": knowledge_id,
                "trigger_conditions": pattern.trigger_conditions,
                "required_actions": pattern.recommended_actions,
            },
            scope=ImpactScope(pattern.pattern_signature.get("target_scope", "single_case")),
            knowledge_layer=ExtendedKnowledgeLayer.L3_CANONICAL,
            knowledge_status=KnowledgeStatus.APPROVED,
        )

        self.rules[rule_id] = rule
        pattern.knowledge_layer = ExtendedKnowledgeLayer.L3_CANONICAL
        pattern.updated_at = time.time()

        return True, f"成功提升为 L3 规则: {rule_id}"

    def find_matching_patterns(
        self,
        correction: CorrectionRecord,
    ) -> List[PatternKnowledge]:
        """查找匹配的模式"""
        matching = []

        for pattern in self.patterns.values():
            # 检查触发条件匹配
            if self._matches_trigger_conditions(pattern, correction):
                matching.append(pattern)

        # 按置信度排序
        matching.sort(key=lambda p: p.confidence_score, reverse=True)
        return matching

    def _matches_trigger_conditions(
        self,
        pattern: PatternKnowledge,
        correction: CorrectionRecord,
    ) -> bool:
        """检查是否匹配触发条件"""
        conditions = pattern.trigger_conditions

        # 检查错误类型
        error_types = conditions.get("error_types", [])
        if error_types and correction.error_type.value not in error_types:
            return False

        # 检查影响范围
        impact_scopes = conditions.get("impact_scopes", [])
        if impact_scopes and correction.impact_scope.value not in impact_scopes:
            return False

        return True

    def save_pattern(self, pattern: PatternKnowledge) -> str:
        """保存模式知识"""
        patterns_dir = self.storage_path / "patterns"
        patterns_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{pattern.knowledge_id}.json"
        filepath = patterns_dir / filename

        with open(filepath, "w") as f:
            json.dump(pattern.to_dict(), f, indent=2, ensure_ascii=False)

        return str(filepath)

    def get_statistics(self) -> Dict[str, Any]:
        """获取知识统计"""
        l2_patterns = [p for p in self.patterns.values()
                      if p.knowledge_layer == ExtendedKnowledgeLayer.L2_GENERALIZABLE]
        l3_patterns = [p for p in self.patterns.values()
                      if p.knowledge_layer == ExtendedKnowledgeLayer.L3_CANONICAL]

        return {
            "total_patterns": len(self.patterns),
            "l2_patterns": len(l2_patterns),
            "l3_patterns": len(l3_patterns),
            "total_rules": len(self.rules),
            "approved_patterns": sum(1 for p in self.patterns.values()
                                   if p.knowledge_status == KnowledgeStatus.APPROVED),
            "draft_patterns": sum(1 for p in self.patterns.values()
                                 if p.knowledge_status == KnowledgeStatus.DRAFT),
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def extract_and_validate_knowledge(
    corrections: List[CorrectionRecord],
    storage_path: str = ".knowledge",
) -> Tuple[List[PatternKnowledge], List[str]]:
    """便捷函数：提取并验证知识"""
    manager = KnowledgeManager(storage_path=storage_path)

    extracted = []
    all_violations = []

    for correction in corrections:
        # 提取知识
        patterns = manager.extract_knowledge(correction)

        # 验证并添加
        for pattern in patterns:
            is_valid, violations = manager.add_pattern(pattern, validate=True)
            if is_valid:
                extracted.append(pattern)
            else:
                all_violations.extend([
                    f"{pattern.knowledge_id}: {v}" for v in violations
                ])

    return extracted, all_violations


def find_similar_corrections(
    correction: CorrectionRecord,
    knowledge_manager: KnowledgeManager,
) -> List[str]:
    """查找相似的历史修正"""
    matching_patterns = knowledge_manager.find_matching_patterns(correction)

    similar_corrections = []
    for pattern in matching_patterns:
        similar_corrections.extend(pattern.source_corrections)

    return list(set(similar_corrections))
