#!/usr/bin/env python3
"""
Phase 3 Schema: Analogy Layer (E层)

定义类比推理编排器的核心数据结构。
基于已学知识，对没学过但相近的算例做类比、方案生成和低成本试探。

核心组件:
- AnalogyDimension: 相似性维度
- SimilarityScore: 相似性评分
- AnalogyResult: 类比结果
- CandidatePlan: 候选方案
- TrialResult: 试探结果
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# Analogy Dimensions
# ============================================================================

class AnalogyDimension(Enum):
    """类比维度 - 相似性的不同方面"""
    GEOMETRY = "geometry"          # 几何相似
    PHYSICS = "physics"            # 物理模型相似
    BOUNDARY = "boundary"          # 边界条件相似
    MESH = "mesh"                  # 网格特征相似
    FLOW_REGIME = "flow_regime"    # 流动状态相似
    NUMERICAL = "numerical"        # 数值方法相似
    REPORT = "report"              # 报告格式相似


class AnalogyConfidence(Enum):
    """类比可信度等级"""
    HIGH = "high"          # 高可信度：可直接应用
    MEDIUM = "medium"      # 中可信度：需要低成本验证
    LOW = "low"            # 低可信度：需要完整验证
    UNRELIABLE = "unreliable"  # 不可靠：退回 Teach Bench


class TrialStatus(Enum):
    """试探状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BUDGET_EXCEEDED = "budget_exceeded"


class ExplorationBudget:
    """探索预算控制"""

    def __init__(
        self,
        max_trials: int = 3,
        max_compute_hours: float = 1.0,
        max_mesh_cells: int = 100000,
        max_time_steps: int = 1000,
    ):
        self.max_trials = max_trials
        self.max_compute_hours = max_compute_hours
        self.max_mesh_cells = max_mesh_cells
        self.max_time_steps = max_time_steps
        self.trials_used = 0
        self.compute_hours_used = 0.0

    @property
    def is_exhausted(self) -> bool:
        """预算是否耗尽"""
        return self.trials_used >= self.max_trials

    def consume_trial(self, compute_hours: float = 0.0) -> bool:
        """消费一次试探

        Returns:
            bool: 是否仍有预算
        """
        if self.is_exhausted:
            return False
        self.trials_used += 1
        self.compute_hours_used += compute_hours
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_trials": self.max_trials,
            "max_compute_hours": self.max_compute_hours,
            "max_mesh_cells": self.max_mesh_cells,
            "max_time_steps": self.max_time_steps,
            "trials_used": self.trials_used,
            "compute_hours_used": self.compute_hours_used,
            "is_exhausted": self.is_exhausted,
        }


# ============================================================================
# Core Data Structures
# ============================================================================

@dataclass
class SimilarityScore:
    """相似性评分

    记录两个案例在某个维度上的相似性分数。
    """
    dimension: AnalogyDimension
    score: float  # 0.0 ~ 1.0
    evidence: List[str] = field(default_factory=list)
    weight: float = 1.0  # 维度权重

    @property
    def weighted_score(self) -> float:
        """加权分数"""
        return self.score * self.weight

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "score": self.score,
            "evidence": self.evidence,
            "weight": self.weight,
            "weighted_score": self.weighted_score,
        }


@dataclass
class AnalogyResult:
    """类比结果

    描述目标案例与源案例之间的类比关系。
    """
    analogy_id: str = field(default_factory=lambda: f"ANALOGY-{uuid.uuid4().hex[:8]}")
    source_case_id: str = ""
    target_case_id: str = ""
    created_at: float = field(default_factory=time.time)

    # 相似性评分
    dimension_scores: List[SimilarityScore] = field(default_factory=list)

    # 综合评估
    overall_similarity: float = 0.0
    confidence: AnalogyConfidence = AnalogyConfidence.MEDIUM

    # 匹配的知识
    matched_patterns: List[str] = field(default_factory=list)  # PatternKnowledge IDs
    matched_rules: List[str] = field(default_factory=list)      # RuleKnowledge IDs

    # 可操作性
    transferable_actions: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)

    @property
    def is_reliable(self) -> bool:
        """是否可靠（可用于指导试探）"""
        return self.confidence in (
            AnalogyConfidence.HIGH,
            AnalogyConfidence.MEDIUM,
        )

    def calculate_overall_similarity(self) -> float:
        """计算综合相似度（加权平均）"""
        if not self.dimension_scores:
            return 0.0

        total_weight = sum(s.weight for s in self.dimension_scores)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(s.weighted_score for s in self.dimension_scores)
        self.overall_similarity = weighted_sum / total_weight
        return self.overall_similarity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analogy_id": self.analogy_id,
            "source_case_id": self.source_case_id,
            "target_case_id": self.target_case_id,
            "created_at": self.created_at,
            "dimension_scores": [s.to_dict() for s in self.dimension_scores],
            "overall_similarity": self.overall_similarity,
            "confidence": self.confidence.value,
            "matched_patterns": self.matched_patterns,
            "matched_rules": self.matched_rules,
            "transferable_actions": self.transferable_actions,
            "risk_factors": self.risk_factors,
            "is_reliable": self.is_reliable,
        }


@dataclass
class CandidatePlan:
    """候选方案

    基于类比结果生成的候选执行方案。
    """
    plan_id: str = field(default_factory=lambda: f"CPLAN-{uuid.uuid4().hex[:8]}")
    analogy_id: str = ""
    created_at: float = field(default_factory=time.time)

    # 方案配置
    rank: int = 1  # A/B/C 排名
    description: str = ""
    estimated_cost: float = 0.0  # 预估计算成本（小时）
    estimated_accuracy: float = 0.0  # 预估精度（0-1）

    # 执行参数（粗网格/简化模型/短步数）
    execution_params: Dict[str, Any] = field(default_factory=dict)

    # 来源知识
    source_knowledge_ids: List[str] = field(default_factory=list)
    adaptation_notes: List[str] = field(default_factory=list)

    # 风险评估
    risk_level: str = "medium"  # "low", "medium", "high"
    failure_probability: float = 0.0

    @property
    def is_low_cost(self) -> bool:
        """是否低成本方案"""
        return self.estimated_cost <= 0.5  # 0.5 小时以内算低成本

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "analogy_id": self.analogy_id,
            "rank": self.rank,
            "description": self.description,
            "estimated_cost": self.estimated_cost,
            "estimated_accuracy": self.estimated_accuracy,
            "execution_params": self.execution_params,
            "source_knowledge_ids": self.source_knowledge_ids,
            "risk_level": self.risk_level,
            "is_low_cost": self.is_low_cost,
        }


@dataclass
class TrialResult:
    """试探结果

    记录低成本试探的执行结果和评估。
    """
    trial_id: str = field(default_factory=lambda: f"TRIAL-{uuid.uuid4().hex[:8]}")
    plan_id: str = ""
    created_at: float = field(default_factory=time.time)

    # 执行状态
    status: TrialStatus = TrialStatus.PENDING
    execution_time: float = 0.0

    # 结果数据
    output_data: Dict[str, Any] = field(default_factory=dict)
    convergence_data: Dict[str, Any] = field(default_factory=dict)

    # 评估
    deviation_from_expected: float = 0.0  # 偏差
    is_acceptable: bool = False
    evaluation_notes: List[str] = field(default_factory=list)

    # Gate 检查结果
    gate_results: Dict[str, bool] = field(default_factory=dict)

    @property
    def deviation_percentage(self) -> float:
        """偏差百分比"""
        return abs(self.deviation_from_expected) * 100

    @property
    def should_promote(self) -> bool:
        """是否应该升级为正式执行"""
        return (
            self.status == TrialStatus.COMPLETED
            and self.is_acceptable
            and self.deviation_percentage <= 10.0  # 偏差 ≤ 10%
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "plan_id": self.plan_id,
            "status": self.status.value,
            "execution_time": self.execution_time,
            "deviation_from_expected": self.deviation_from_expected,
            "deviation_percentage": self.deviation_percentage,
            "is_acceptable": self.is_acceptable,
            "should_promote": self.should_promote,
            "gate_results": self.gate_results,
            "evaluation_notes": self.evaluation_notes,
        }


# ============================================================================
# AnalogyFailureBundle - 类比失效上下文
# ============================================================================

@dataclass
class AnalogyFailureBundle:
    """类比失效上下文包

    当 E6 决定回退 Teach Bench 时，向 Phase 2 Correction Recorder
    传递完整的类比失败信号——包含"系统认为相似但实际不相似"的学习价值。
    """
    bundle_id: str = field(default_factory=lambda: f"AFB-{uuid.uuid4().hex[:8]}")
    spec_id: str = ""
    target_case_id: str = ""
    created_at: float = field(default_factory=time.time)

    # 失败原因分类
    failure_type: str = ""  # "no_similar" | "trial_failed" | "analogy_mismatch"
    failure_summary: str = ""

    # 类比匹配上下文
    best_similarity_score: float = 0.0
    best_source_case_id: str = ""
    similarity_dimensions: List[Dict[str, Any]] = field(default_factory=list)

    # 候选方案和试探结果摘要
    candidate_plans_tried: int = 0
    trial_summaries: List[Dict[str, Any]] = field(default_factory=list)

    # 降级历史
    relaxation_history: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "spec_id": self.spec_id,
            "target_case_id": self.target_case_id,
            "failure_type": self.failure_type,
            "failure_summary": self.failure_summary,
            "best_similarity_score": self.best_similarity_score,
            "best_source_case_id": self.best_source_case_id,
            "candidate_plans_tried": self.candidate_plans_tried,
            "trial_summaries": self.trial_summaries,
            "relaxation_history": self.relaxation_history,
        }


# ============================================================================
# AnalogySpec - Phase 3 顶层规范
# ============================================================================

@dataclass
class AnalogySpec:
    """类比推理规范

    描述 Phase 3 的完整类比推理流程规范。
    """
    spec_id: str = field(default_factory=lambda: f"ASPEC-{uuid.uuid4().hex[:8]}")
    target_case_id: str = ""
    created_at: float = field(default_factory=time.time)

    # 目标问题描述
    problem_description: str = ""
    problem_type: str = ""  # ProblemType.value

    # 已知约束
    constraints: Dict[str, Any] = field(default_factory=dict)

    # 探索预算
    budget: ExplorationBudget = field(default_factory=ExplorationBudget)

    # 相似性阈值
    min_similarity_threshold: float = 0.5
    confidence_threshold: AnalogyConfidence = AnalogyConfidence.MEDIUM

    # 类比结果
    analogy_results: List[AnalogyResult] = field(default_factory=list)
    candidate_plans: List[CandidatePlan] = field(default_factory=list)
    trial_results: List[TrialResult] = field(default_factory=list)

    # 最终决策
    selected_plan_id: Optional[str] = None
    fallback_to_teach: bool = False
    failure_bundle: Optional[AnalogyFailureBundle] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "target_case_id": self.target_case_id,
            "created_at": self.created_at,
            "problem_description": self.problem_description,
            "problem_type": self.problem_type,
            "constraints": self.constraints,
            "budget": self.budget.to_dict(),
            "min_similarity_threshold": self.min_similarity_threshold,
            "analogy_results": [r.to_dict() for r in self.analogy_results],
            "candidate_plans": [p.to_dict() for p in self.candidate_plans],
            "trial_results": [t.to_dict() for t in self.trial_results],
            "selected_plan_id": self.selected_plan_id,
            "fallback_to_teach": self.fallback_to_teach,
            "failure_bundle": (
                self.failure_bundle.to_dict() if self.failure_bundle else None
            ),
        }
