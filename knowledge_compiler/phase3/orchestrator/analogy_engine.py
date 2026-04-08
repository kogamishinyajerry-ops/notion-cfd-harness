#!/usr/bin/env python3
"""
Phase 3: Analogical Reasoning Engine (E层)

基于已学知识，对未见过但相近的算例进行类比推理、方案生成和低成本试探。

组件架构:
  E1  SimilarityEngine        — 结构化特征匹配的相似度检索
  E2  AnalogyDecomposer       — 相似性维度分解
  E3  CandidatePlanGenerator  — 候选方案生成
  E4  TrialRunner             — 低成本试探执行
  E5  TrialEvaluator          — 试探结果评估
  E6  AnalogyFailureHandler   — 类比失效处理
      AnalogicalOrchestrator  — 主编排器 (E1→E6 串联)
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

from knowledge_compiler.phase3.analogy_schema import (
    AnalogyConfidence,
    AnalogyDimension,
    AnalogyResult,
    AnalogySpec,
    AnalogyFailureBundle,
    CandidatePlan,
    ExplorationBudget,
    SimilarityScore,
    TrialResult,
    TrialStatus,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Protocol: Knowledge Store 接口
# ============================================================================

class KnowledgeStore(Protocol):
    """Phase 1/2 知识库的最小接口"""

    def list_cases(self) -> List[Dict[str, Any]]:
        """列出所有已学案例的元数据"""
        ...

    def get_case_features(self, case_id: str) -> Dict[str, Any]:
        """获取案例的结构化特征"""
        ...

    def get_patterns(self, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """获取已学模式知识"""
        ...

    def get_rules(self, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """获取已学规则知识"""
        ...


# ============================================================================
# Feature extraction helpers
# ============================================================================

# 维度权重默认表
_DEFAULT_WEIGHTS: Dict[AnalogyDimension, float] = {
    AnalogyDimension.GEOMETRY: 0.25,
    AnalogyDimension.PHYSICS: 0.20,
    AnalogyDimension.BOUNDARY: 0.15,
    AnalogyDimension.MESH: 0.10,
    AnalogyDimension.FLOW_REGIME: 0.15,
    AnalogyDimension.NUMERICAL: 0.10,
    AnalogyDimension.REPORT: 0.05,
}


def _extract_feature_vector(
    features: Dict[str, Any], dimension: AnalogyDimension
) -> Dict[str, Any]:
    """从案例特征中提取某个维度的子特征"""
    dim_key = dimension.value
    return features.get(dim_key, {})


def _jaccard_similarity(a: set, b: set) -> float:
    """Jaccard 集合相似度"""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _numeric_distance(a: float, b: float, scale: float = 1.0) -> float:
    """归一化数值相似度 (1 = 相同, 0 = 完全不同)"""
    if scale == 0:
        return 1.0 if a == b else 0.0
    return max(0.0, 1.0 - abs(a - b) / scale)


_LOG_EPSILON = 1e-10  # 对数归一化的下界保护

def _logarithmic_distance(a: float, b: float) -> float:
    """对数归一化数值相似度 (1 = 相同, 0 = 完全不同)

    适用于跨数量级的物理量（Re, Ma 等）。
    Re=1e6 vs Re=1e7 的差异在物理上是根本性的（层流 vs 湍流），
    线性归一化会压缩这种差异。
    """
    if a == 0 and b == 0:
        return 1.0
    if a <= 0 or b <= 0:
        # 负值或零值退化为线性
        return _numeric_distance(a, b, scale=max(abs(a), abs(b), 1e-6) * 2)
    # epsilon 保护：防止极小正值产生 log10(<0) 量级的极端结果
    a = max(a, _LOG_EPSILON)
    b = max(b, _LOG_EPSILON)
    log_a = math.log10(abs(a))
    log_b = math.log10(abs(b))
    # 用固定的归一化范围：一个数量级差异 = 相似度下降约 0.5
    # 这样 1e6 vs 1e7 ≈ 0.5，1e6 vs 1e8 ≈ 0.0
    log_diff = abs(log_a - log_b)
    return max(0.0, 1.0 - log_diff / 2.0)


# 使用对数归一化的已知物理量关键字（仅跨数量级的物理量）
# 注意：temperature/pressure/velocity 不应使用对数归一化，
# 因为同量级差异在 CFD 中有重大物理意义（如 300K vs 400K 是 33% 温差）
_LOG_NORMALIZED_KEYS: Set[str] = {
    "Re", "Reynolds", "reynolds_number",
    "Ma", "Mach", "mach_number",
}


def _should_use_log(key: str) -> bool:
    """判断某个数值字段是否应该使用对数归一化"""
    return key in _LOG_NORMALIZED_KEYS or any(
        k in key.lower() for k in ("re", "mach", "ma", "reynolds")
    )


# 硬性一致性约束：这些字符串字段不匹配时直接降为极低分
_HARD_CONSTRAINT_KEYS: Dict[str, float] = {
    "FlowType": 0.05,
    "flow_type": 0.05,
    "Compressibility": 0.05,
    "compressibility": 0.05,
    "TimeTreatment": 0.10,
    "time_treatment": 0.10,
    "solver_type": 0.05,
    "SolverType": 0.05,
    "turbulence_model": 0.10,
    "TurbulenceModel": 0.10,
}


# ============================================================================
# E1: Similarity Retrieval Engine
# ============================================================================

class SimilarityEngine:
    """E1: 结构化特征匹配的相似度检索引擎

    将目标案例特征与知识库中的源案例逐一比对，
    在每个 AnalogyDimension 上计算 0~1 的相似度分数。
    """

    def __init__(
        self,
        knowledge_store: KnowledgeStore,
        weights: Optional[Dict[AnalogyDimension, float]] = None,
        similarity_threshold: float = 0.3,
    ):
        self._store = knowledge_store
        self._weights = weights or dict(_DEFAULT_WEIGHTS)
        self._similarity_threshold = similarity_threshold

    def find_similar_cases(
        self,
        target_features: Dict[str, Any],
        top_k: int = 5,
        dimensions: Optional[List[AnalogyDimension]] = None,
    ) -> List[AnalogyResult]:
        """检索与目标最相似的源案例

        Args:
            target_features: 目标案例的结构化特征
            top_k: 返回前 K 个最相似案例
            dimensions: 只比对指定维度（None=全部）

        Returns:
            按综合相似度降序排列的 AnalogyResult 列表
        """
        dims = dimensions or list(AnalogyDimension)
        all_cases = self._store.list_cases()

        results: List[AnalogyResult] = []
        for case_meta in all_cases:
            source_id = case_meta.get("case_id", "")
            source_features = self._store.get_case_features(source_id)

            scores = self._compute_dimension_scores(
                target_features, source_features, dims
            )

            result = AnalogyResult(
                source_case_id=source_id,
                target_case_id=target_features.get("case_id", "TARGET"),
                dimension_scores=scores,
            )
            result.calculate_overall_similarity()

            # 根据综合相似度确定可信度
            result.confidence = self._score_to_confidence(result.overall_similarity)

            if result.overall_similarity >= self._similarity_threshold:
                results.append(result)

        # 按综合相似度降序排列
        results.sort(key=lambda r: r.overall_similarity, reverse=True)
        return results[:top_k]

    def _compute_dimension_scores(
        self,
        target: Dict[str, Any],
        source: Dict[str, Any],
        dimensions: List[AnalogyDimension],
    ) -> List[SimilarityScore]:
        """计算各维度相似度"""
        scores = []
        for dim in dimensions:
            score_val = self._compare_dimension(target, source, dim)
            scores.append(
                SimilarityScore(
                    dimension=dim,
                    score=score_val,
                    weight=self._weights.get(dim, 1.0),
                    evidence=self._collect_evidence(target, source, dim, score_val),
                )
            )
        return scores

    def _compare_dimension(
        self,
        target: Dict[str, Any],
        source: Dict[str, Any],
        dimension: AnalogyDimension,
    ) -> float:
        """单个维度的相似度计算

        使用混合策略：集合匹配 + 数值距离 + 关键词匹配。
        """
        t_feat = _extract_feature_vector(target, dimension)
        s_feat = _extract_feature_vector(source, dimension)

        if not t_feat and not s_feat:
            return 0.5  # 无信息时给中间分
        if not t_feat or not s_feat:
            return 0.2

        sub_scores: List[float] = []

        # 字符串/集合字段 → Jaccard
        set_keys = [k for k in t_feat if isinstance(t_feat[k], (list, set))]
        for key in set_keys:
            t_set = set(str(x) for x in t_feat[key])
            s_set = set(str(x) for x in s_feat.get(key, []))
            sub_scores.append(_jaccard_similarity(t_set, s_set))

        # 数值字段 → 对数归一化（物理量）或线性归一化（其他）
        num_keys = [k for k in t_feat if isinstance(t_feat[k], (int, float))]
        for key in num_keys:
            t_val = float(t_feat[key])
            s_val = float(s_feat.get(key, 0))
            if _should_use_log(key):
                sub_scores.append(_logarithmic_distance(t_val, s_val))
            else:
                scale = max(abs(t_val), abs(s_val), 1e-6) * 2
                sub_scores.append(_numeric_distance(t_val, s_val, scale))

        # 字符串字段 → 精确匹配（含硬性一致性约束）
        str_keys = [k for k in t_feat if isinstance(t_feat[k], str)]
        for key in str_keys:
            if t_feat[key] != s_feat.get(key, ""):
                # 硬约束字段不匹配时直接降为极低分
                if key in _HARD_CONSTRAINT_KEYS:
                    return _HARD_CONSTRAINT_KEYS[key]
                sub_scores.append(0.0)
            else:
                sub_scores.append(1.0)

        if not sub_scores:
            return 0.5

        return sum(sub_scores) / len(sub_scores)

    def _collect_evidence(
        self,
        target: Dict[str, Any],
        source: Dict[str, Any],
        dimension: AnalogyDimension,
        score: float,
    ) -> List[str]:
        """收集相似性证据"""
        evidence = []
        t_feat = _extract_feature_vector(target, dimension)
        s_feat = _extract_feature_vector(source, dimension)

        if score >= 0.8:
            evidence.append(f"{dimension.value}: 高度匹配 ({score:.2f})")
        elif score >= 0.5:
            evidence.append(f"{dimension.value}: 部分匹配 ({score:.2f})")
        else:
            evidence.append(f"{dimension.value}: 低匹配 ({score:.2f})")

        # 具体匹配项
        for key in set(t_feat.keys()) & set(s_feat.keys()):
            if t_feat[key] == s_feat[key]:
                evidence.append(f"  {key}: 匹配 ({t_feat[key]})")

        return evidence

    @staticmethod
    def _score_to_confidence(score: float) -> AnalogyConfidence:
        """综合相似度 → 可信度等级"""
        if score >= 0.8:
            return AnalogyConfidence.HIGH
        elif score >= 0.6:
            return AnalogyConfidence.MEDIUM
        elif score >= 0.4:
            return AnalogyConfidence.LOW
        else:
            return AnalogyConfidence.UNRELIABLE


# ============================================================================
# E2: Analogy Decomposer
# ============================================================================

class AnalogyDecomposer:
    """E2: 相似性维度分解

    对 SimilarityEngine 的初步结果做深度分解：
    - 识别关键相似维度和差异维度
    - 提取可迁移的动作和风险因素
    - 匹配知识库中的模式和规则
    """

    def __init__(self, knowledge_store: KnowledgeStore):
        self._store = knowledge_store

    def decompose(self, analogy: AnalogyResult) -> AnalogyResult:
        """对类比结果做深度分解"""
        # 排序：相似度最高的维度排前面
        analogy.dimension_scores.sort(
            key=lambda s: s.weighted_score, reverse=True
        )

        # 识别强维度和弱维度
        strong_dims = [
            s for s in analogy.dimension_scores if s.score >= 0.7
        ]
        weak_dims = [
            s for s in analogy.dimension_scores if s.score < 0.4
        ]

        # 基于强维度匹配知识库中的模式
        analogy.matched_patterns = self._match_patterns(strong_dims)
        analogy.matched_rules = self._match_rules(strong_dims)

        # 提取可迁移动作
        analogy.transferable_actions = self._extract_actions(
            strong_dims, analogy.matched_patterns
        )

        # 提取风险因素
        analogy.risk_factors = self._extract_risks(weak_dims, strong_dims)

        return analogy

    def _match_patterns(
        self, strong_dims: List[SimilarityScore]
    ) -> List[str]:
        """基于强维度匹配模式知识"""
        dim_tags = [f"dim:{s.dimension.value}" for s in strong_dims]
        patterns = self._store.get_patterns(tags=dim_tags)
        return [p.get("pattern_id", "") for p in patterns if p.get("pattern_id")]

    def _match_rules(
        self, strong_dims: List[SimilarityScore]
    ) -> List[str]:
        """基于强维度匹配规则知识"""
        dim_tags = [f"dim:{s.dimension.value}" for s in strong_dims]
        rules = self._store.get_rules(tags=dim_tags)
        return [r.get("rule_id", "") for r in rules if r.get("rule_id")]

    def _extract_actions(
        self,
        strong_dims: List[SimilarityScore],
        matched_patterns: List[str],
    ) -> List[str]:
        """提取可迁移的动作列表"""
        actions: List[str] = []

        dim_names = {s.dimension.value for s in strong_dims}

        if "geometry" in dim_names:
            actions.append("reuse_mesh_strategy")
        if "physics" in dim_names:
            actions.append("reuse_physics_model")
        if "boundary" in dim_names:
            actions.append("adapt_boundary_conditions")
        if "flow_regime" in dim_names:
            actions.append("reuse_solver_settings")
        if "numerical" in dim_names:
            actions.append("reuse_numerical_schemes")

        if matched_patterns:
            actions.append(f"apply_patterns(count={len(matched_patterns)})")

        return actions

    def _extract_risks(
        self,
        weak_dims: List[SimilarityScore],
        strong_dims: List[SimilarityScore],
    ) -> List[str]:
        """提取风险因素"""
        risks: List[str] = []

        for s in weak_dims:
            risks.append(
                f"low_similarity:{s.dimension.value}(score={s.score:.2f})"
            )

        # 即使强维度多，如果完全缺失某些维度也是风险
        all_dim_values = {d.value for d in AnalogyDimension}
        scored_dims = {s.dimension.value for s in strong_dims + weak_dims}
        missing = all_dim_values - scored_dims
        for m in missing:
            risks.append(f"missing_dimension:{m}")

        return risks


# ============================================================================
# E3: Candidate Plan Generator
# ============================================================================

class CandidatePlanGenerator:
    """E3: 候选方案生成

    基于分解后的类比结果，生成 A/B/C 三档候选方案：
    - A: 激进迁移（低成本、快速验证）
    - B: 保守迁移（中等成本、更多适应）
    - C: 最小验证（极低成本、仅验证关键假设）
    """

    # 方案模板
    PLAN_TEMPLATES = {
        "A": {
            "description": "激进迁移：直接复用源案例配置",
            "mesh_factor": 0.5,
            "time_step_factor": 0.5,
            "risk_level": "high",
        },
        "B": {
            "description": "保守迁移：适度简化后复用",
            "mesh_factor": 0.25,
            "time_step_factor": 0.3,
            "risk_level": "medium",
        },
        "C": {
            "description": "最小验证：仅验证核心物理假设",
            "mesh_factor": 0.1,
            "time_step_factor": 0.1,
            "risk_level": "low",
        },
    }

    def generate_plans(
        self,
        analogy: AnalogyResult,
        budget: ExplorationBudget,
        source_config: Optional[Dict[str, Any]] = None,
    ) -> List[CandidatePlan]:
        """基于类比结果生成候选方案

        Args:
            analogy: 经过分解的类比结果
            budget: 探索预算
            source_config: 源案例的执行配置（用于估算成本）

        Returns:
            按优先级排序的候选方案列表
        """
        plans: List[CandidatePlan] = []
        src = source_config or {}

        base_cells = src.get("mesh_cells", 50000)
        base_steps = src.get("time_steps", 500)
        base_hours = src.get("compute_hours", 0.5)

        for rank, (label, template) in enumerate(
            self.PLAN_TEMPLATES.items(), start=1
        ):
            est_cells = int(base_cells * template["mesh_factor"])
            est_steps = int(base_steps * template["time_step_factor"])
            est_hours = base_hours * template["mesh_factor"]

            # 检查预算
            if est_cells > budget.max_mesh_cells:
                continue
            if est_hours > budget.max_compute_hours:
                continue

            plan = CandidatePlan(
                analogy_id=analogy.analogy_id,
                rank=rank,
                description=template["description"],
                estimated_cost=est_hours,
                estimated_accuracy=self._estimate_accuracy(
                    analogy, template["mesh_factor"]
                ),
                execution_params={
                    "mesh_cells": est_cells,
                    "time_steps": est_steps,
                    "mesh_factor": template["mesh_factor"],
                    "time_step_factor": template["time_step_factor"],
                },
                source_knowledge_ids=analogy.matched_patterns
                + analogy.matched_rules,
                adaptation_notes=self._adaptation_notes(analogy),
                risk_level=template["risk_level"],
                failure_probability=self._estimate_failure(analogy, rank),
            )
            plans.append(plan)

        return plans

    def _estimate_accuracy(
        self, analogy: AnalogyResult, mesh_factor: float
    ) -> float:
        """预估方案精度"""
        base = analogy.overall_similarity
        # 网格越粗精度越低，但有底线
        return max(0.3, base * (0.5 + 0.5 * mesh_factor))

    def _estimate_failure(
        self, analogy: AnalogyResult, rank: int
    ) -> float:
        """预估失败概率"""
        base_risk = 1.0 - analogy.overall_similarity
        rank_penalty = (rank - 1) * 0.1  # A=0, B=0.1, C=0.2
        return min(1.0, base_risk + rank_penalty)

    def _adaptation_notes(
        self, analogy: AnalogyResult
    ) -> List[str]:
        """生成适应说明"""
        notes: List[str] = []

        if analogy.risk_factors:
            notes.append(
                f"注意 {len(analogy.risk_factors)} 个风险因素"
            )

        weak_dims = [
            s.dimension.value
            for s in analogy.dimension_scores
            if s.score < 0.5
        ]
        if weak_dims:
            notes.append(f"弱维度需要额外适应: {', '.join(weak_dims)}")

        return notes


# ============================================================================
# E4: Trial Runner
# ============================================================================

class TrialRunner:
    """E4: 低成本试探执行

    用粗网格 + 少步数执行候选方案，收集收敛数据和基础结果。
    支持自定义执行后端（如 OpenFOAM, SU2, 或 mock）。
    """

    def __init__(
        self,
        executor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        self._executor = executor or self._default_executor

    def run_trial(
        self,
        plan: CandidatePlan,
        budget: ExplorationBudget,
        timeout: float = 300.0,
    ) -> TrialResult:
        """执行一次试探

        Args:
            plan: 候选方案
            budget: 探索预算（会被消费）
            timeout: 超时秒数

        Returns:
            TrialResult 试探结果
        """
        if budget.is_exhausted:
            return TrialResult(
                plan_id=plan.plan_id,
                status=TrialStatus.BUDGET_EXCEEDED,
                evaluation_notes=["预算已耗尽，跳过试探"],
            )

        result = TrialResult(
            plan_id=plan.plan_id,
            status=TrialStatus.RUNNING,
        )

        start = time.time()
        try:
            output = self._executor(plan.execution_params)
            elapsed = time.time() - start

            result.status = TrialStatus.COMPLETED
            result.execution_time = elapsed
            result.output_data = output.get("output", {})
            result.convergence_data = output.get("convergence", {})

            # 消费预算
            compute_hours = elapsed / 3600.0
            budget.consume_trial(compute_hours)

        except TimeoutError:
            result.status = TrialStatus.FAILED
            result.evaluation_notes.append(f"超时 ({timeout}s)")
        except Exception as e:
            result.status = TrialStatus.FAILED
            result.evaluation_notes.append(f"执行错误: {e}")

        return result

    @staticmethod
    def _default_executor(
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """默认执行器（mock 模式）

        生产环境应替换为真实 solver 调用。
        """
        mesh_cells = params.get("mesh_cells", 1000)
        time_steps = params.get("time_steps", 100)

        # Mock: 模拟收敛曲线
        residuals = [1.0 / (i + 1) for i in range(min(time_steps, 20))]
        final_residual = residuals[-1] if residuals else 1.0

        return {
            "output": {
                "mesh_cells": mesh_cells,
                "time_steps": time_steps,
                "final_residual": final_residual,
                "status": "converged" if final_residual < 0.01 else "running",
                "is_mock": True,  # 防止下游误认为真实仿真结果
            },
            "convergence": {
                "residuals": residuals,
                "converged": final_residual < 0.01,
                "iteration_count": len(residuals),
            },
        }


# ============================================================================
# E5: Trial Evaluator
# ============================================================================

class TrialEvaluator:
    """E5: 试探结果评估

    评估试探结果的可接受度：
    - 收敛性检查（残差是否下降）
    - 物理合理性检查（量级、趋势）
    - Gate 检查（预算内完成、无发散等）
    - 偏差评估（与预期对比）
    """

    # 默认 Gate 定义
    DEFAULT_GATES = {
        "converged": "收敛性：最终残差 < 0.01",
        "no_divergence": "发散检查：残差未上升",
        "within_budget": "预算检查：在预算内完成",
        "physical_plausibility": "物理合理性：结果量级合理",
        "mock_data": "数据真实性：非 mock 数据（自动检测）",
    }

    def __init__(
        self,
        gates: Optional[Dict[str, str]] = None,
        max_acceptable_deviation: float = 0.15,
        convergence_threshold: float = 0.01,
        coarse_mesh_tolerance_factor: float = 3.0,
    ):
        self._gates = gates or self.DEFAULT_GATES
        self._max_deviation = max_acceptable_deviation
        self._convergence_threshold = convergence_threshold
        self._coarse_tolerance_factor = coarse_mesh_tolerance_factor

    def evaluate(
        self,
        trial: TrialResult,
        expected: Optional[Dict[str, Any]] = None,
        analogy_reference: Optional[Dict[str, Any]] = None,
    ) -> TrialResult:
        """评估试探结果

        Args:
            trial: 试探执行结果
            expected: 预期结果（用于偏差计算）
            analogy_reference: 类比参考 case 的关键指标（用于 G4-P3 类比偏差检查）

        Returns:
            更新后的 TrialResult（含 gate_results 和评估结论）
        """
        if trial.status != TrialStatus.COMPLETED:
            trial.is_acceptable = False
            trial.evaluation_notes.append(
                f"试探未完成 (status={trial.status.value})"
            )
            return trial

        # Gate 检查
        trial.gate_results = self._check_gates(trial)

        # No Data Fabrication: mock 数据不可用于最终决策
        if trial.output_data.get("is_mock"):
            trial.gate_results["mock_data"] = False
            trial.evaluation_notes.append(
                "试探结果为 mock 数据，不可用于生产决策"
            )

        # 偏差计算
        if expected:
            trial.deviation_from_expected = self._compute_deviation(
                trial.output_data, expected
            )
        else:
            # 无预期时，用收敛质量推断
            trial.deviation_from_expected = self._infer_deviation(trial)

        # G4-P3 类比偏差检查：试探结果 vs 类比参考 case
        if analogy_reference:
            analogy_dev = self._compute_deviation(
                trial.output_data, analogy_reference
            )
            analogy_threshold = self._max_deviation * self._coarse_tolerance_factor
            trial.gate_results["analogy_deviation"] = (
                analogy_dev <= analogy_threshold
            )
            if analogy_dev > analogy_threshold:
                trial.evaluation_notes.append(
                    f"类比偏差过大: {analogy_dev * 100:.1f}% "
                    f"(阈值: {analogy_threshold * 100:.1f}%)"
                )

        # 综合判断
        all_gates_pass = all(trial.gate_results.values())
        deviation_acceptable = (
            abs(trial.deviation_from_expected) <= self._max_deviation
        )

        trial.is_acceptable = all_gates_pass and deviation_acceptable

        if not all_gates_pass:
            failed = [
                name for name, passed in trial.gate_results.items() if not passed
            ]
            trial.evaluation_notes.append(
                f"Gate 未通过: {', '.join(failed)}"
            )

        if not deviation_acceptable:
            trial.evaluation_notes.append(
                f"偏差过大: {trial.deviation_percentage:.1f}% "
                f"(阈值: {self._max_deviation * 100:.1f}%)"
            )

        return trial

    def _check_gates(self, trial: TrialResult) -> Dict[str, bool]:
        """执行所有 Gate 检查"""
        results: Dict[str, bool] = {}
        output = trial.output_data
        conv = trial.convergence_data

        # 收敛性
        results["converged"] = output.get("final_residual", 1.0) < self._convergence_threshold

        # 发散检查
        residuals = conv.get("residuals", [])
        if len(residuals) >= 2:
            results["no_divergence"] = residuals[-1] <= residuals[0]
        else:
            results["no_divergence"] = True

        # 预算检查
        results["within_budget"] = trial.status == TrialStatus.COMPLETED

        # 物理合理性（简化：检查有输出且非 NaN）
        results["physical_plausibility"] = bool(output) and all(
            isinstance(v, (int, float)) and not (v != v)  # NaN check
            for v in output.values()
            if isinstance(v, (int, float))
        )

        return results

    def _compute_deviation(
        self,
        actual: Dict[str, Any],
        expected: Dict[str, Any],
    ) -> float:
        """计算实际与预期的偏差"""
        deviations: List[float] = []
        for key in expected:
            if key in actual:
                a_val = actual[key]
                e_val = expected[key]
                if isinstance(a_val, (int, float)) and isinstance(
                    e_val, (int, float)
                ):
                    scale = max(abs(e_val), 1e-6)
                    deviations.append(abs(a_val - e_val) / scale)

        if not deviations:
            return 0.0
        return sum(deviations) / len(deviations)

    def _infer_deviation(self, trial: TrialResult) -> float:
        """无预期数据时，从收敛质量推断偏差"""
        conv = trial.convergence_data
        if conv.get("converged"):
            return 0.05  # 收敛了，假设偏差小
        residuals = conv.get("residuals", [1.0])
        final = residuals[-1] if residuals else 1.0
        return min(1.0, final)  # 残差越大，偏差越大


# ============================================================================
# E6: Analogy Failure Handler
# ============================================================================

class AnalogyFailureHandler:
    """E6: 类比失效处理

    当类比推理失败（低相似度、试探不通过等）时的降级策略：
    - 回退到 Teach Bench（Phase 2）重新学习
    - 放宽约束重试（受 RelaxationBoundary 约束）
    - 标记为需要人工介入

    安全约束:
    - max_retries 是硬性上限，防止 RETRY→E4→E5→FAIL→RETRY 无限循环
    - 放宽操作受 RelaxationBoundary 约束，不可无限放宽
    """

    # 放宽策略的底线配置 (RelaxationBoundary)
    DEFAULT_RELAXATION_BOUNDARY = {
        "min_similarity_threshold": 0.2,       # 相似度阈值最低 0.2
        "max_budget_trials_increment": 3,       # 最多增加 3 次试探预算
        "convergence_relaxation_limit": 0.1,    # 收敛标准最多放宽到 0.1
        "mesh_coarsening_limit": 0.05,          # 网格最粗到源案例的 5%
    }

    def __init__(
        self,
        max_retries: int = 3,
        similarity_floor: float = 0.3,
        relaxation_boundary: Optional[Dict[str, Any]] = None,
    ):
        self._max_retries = max_retries
        self._similarity_floor = similarity_floor
        self._relaxation_boundary = relaxation_boundary or dict(
            self.DEFAULT_RELAXATION_BOUNDARY
        )
        self._relaxation_count = 0  # 跟踪放宽次数
        self._initial_max_trials = None  # 保存初始预算上限（防 off-by-one）
        self._relaxed_ceiling = 0  # 放宽后的有效上限

    def handle(
        self,
        spec: AnalogySpec,
        trial_results: List[TrialResult],
    ) -> AnalogySpec:
        """处理类比失效

        Args:
            spec: 当前类比规范
            trial_results: 已完成的试探结果

        Returns:
            更新后的 AnalogySpec（含降级决策）
        """
        # 记录初始预算（首次调用时）
        if self._initial_max_trials is None:
            self._initial_max_trials = spec.budget.max_trials
        all_failed = all(
            t.status != TrialStatus.COMPLETED or not t.is_acceptable
            for t in trial_results
        )
        no_similar = not spec.analogy_results or all(
            a.overall_similarity < self._similarity_floor
            for a in spec.analogy_results
        )

        if no_similar:
            logger.warning(
                "类比失效：无足够相似的源案例 (floor=%.2f)",
                self._similarity_floor,
            )
            spec.fallback_to_teach = True
            spec.selected_plan_id = None
            spec.failure_bundle = AnalogyFailureBundle(
                spec_id=spec.spec_id,
                target_case_id=spec.target_case_id,
                failure_type="no_similar",
                failure_summary=f"所有源案例相似度低于 {self._similarity_floor:.2f}",
            )
            return spec

        if all_failed and spec.trial_results:
            # 使用 E6 自己的放宽计数，而非所有试探结果的累计
            if self._relaxation_count < self._max_retries:
                self._relaxation_count += 1
                logger.info(
                    "试探失败，放宽约束重试 (%d/%d)",
                    self._relaxation_count,
                    self._max_retries,
                )
                # 放宽预算（受硬性天花板约束，防止 off-by-one 膨胀）
                max_inc = self._relaxation_boundary["max_budget_trials_increment"]
                ceiling = self._initial_max_trials + max_inc
                new_max = min(spec.budget.max_trials + 1, ceiling)
                spec.budget.max_trials = new_max
                self._relaxed_ceiling = new_max
                # 放宽相似度阈值（受边界约束）
                min_thresh = self._relaxation_boundary["min_similarity_threshold"]
                spec.min_similarity_threshold = max(
                    min_thresh, spec.min_similarity_threshold - 0.1
                )
            else:
                logger.warning(
                    "超过 E6 最大放宽次数 (%d), 回退到 Teach Bench",
                    self._max_retries,
                )
                spec.fallback_to_teach = True
                # 生成 AnalogyFailureBundle 供 Phase 2 学习
                best_analogy = spec.analogy_results[0] if spec.analogy_results else None
                spec.failure_bundle = AnalogyFailureBundle(
                    spec_id=spec.spec_id,
                    target_case_id=spec.target_case_id,
                    failure_type="trial_failed",
                    failure_summary=(
                        f"E6 放宽 {self._relaxation_count} 次后仍失败"
                    ),
                    best_similarity_score=(
                        best_analogy.overall_similarity if best_analogy else 0.0
                    ),
                    best_source_case_id=(
                        best_analogy.source_case_id if best_analogy else ""
                    ),
                    candidate_plans_tried=len(spec.candidate_plans),
                    trial_summaries=[t.to_dict() for t in spec.trial_results],
                    relaxation_history=[
                        f"放宽 #{i+1}" for i in range(self._relaxation_count)
                    ],
                )

        return spec

    def should_escalate(
        self,
        spec: AnalogySpec,
    ) -> bool:
        """是否需要升级到人工介入"""
        if spec.fallback_to_teach:
            return False  # 自动降级即可

        # 有高相似度但试探结果矛盾
        high_sim = [
            a for a in spec.analogy_results
            if a.confidence == AnalogyConfidence.HIGH
        ]
        if high_sim and spec.trial_results:
            acceptable = [t for t in spec.trial_results if t.is_acceptable]
            if len(acceptable) == 0:
                return True  # 高相似但全失败 = 需要人工

        return False


# ============================================================================
# Main Orchestrator
# ============================================================================

class AnalogicalOrchestrator:
    """Analogical Orchestrator: E1→E6 串联编排

    完整流程:
    1. E1 检索相似案例
    2. E2 分解类比维度
    3. E3 生成候选方案
    4. E4 执行试探
    5. E5 评估结果
    6. E6 处理失效（如需）

    使用示例:
        store = MyKnowledgeStore()
        orch = AnalogicalOrchestrator(store)
        spec = AnalogySpec(target_case_id="NEW-001", ...)
        result = orch.run(spec)

    并发安全:
    - 非线程安全：内部组件（SimilarityEngine, TrialRunner 等）均无锁
    - 单次 run() 调用是同步的，不应并发调用同一实例
    - 多线程场景应为每个线程创建独立的 Orchestrator 实例
    """

    def __init__(
        self,
        knowledge_store: KnowledgeStore,
        executor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        weights: Optional[Dict[AnalogyDimension, float]] = None,
    ):
        self._similarity = SimilarityEngine(
            knowledge_store, weights=weights
        )
        self._decomposer = AnalogyDecomposer(knowledge_store)
        self._plan_generator = CandidatePlanGenerator()
        self._trial_runner = TrialRunner(executor=executor)
        self._evaluator = TrialEvaluator()
        self._failure_handler = AnalogyFailureHandler()

    def run(
        self,
        spec: AnalogySpec,
        target_features: Optional[Dict[str, Any]] = None,
        source_config: Optional[Dict[str, Any]] = None,
        expected_results: Optional[Dict[str, Any]] = None,
    ) -> AnalogySpec:
        """执行完整的类比推理流程

        Args:
            spec: 类比规范
            target_features: 目标案例特征（None 则从 store 获取）
            source_config: 源案例执行配置
            expected_results: 预期结果（用于 E5 偏差评估）

        Returns:
            更新后的 AnalogySpec
        """
        logger.info(
            "开始类比推理: spec=%s target=%s",
            spec.spec_id,
            spec.target_case_id,
        )

        # 获取目标特征
        if target_features is None:
            target_features = {"case_id": spec.target_case_id}

        # ── E1: 检索相似案例 ──
        spec.analogy_results = self._similarity.find_similar_cases(
            target_features,
            top_k=3,
        )
        logger.info(
            "E1 完成: 找到 %d 个相似案例",
            len(spec.analogy_results),
        )

        if not spec.analogy_results:
            logger.warning("无相似案例，标记回退 Teach Bench")
            spec.fallback_to_teach = True
            return spec

        # 取最佳类比
        best_analogy = spec.analogy_results[0]

        # ── E2: 维度分解 ──
        best_analogy = self._decomposer.decompose(best_analogy)
        logger.info(
            "E2 完成: 强维度=%d 风险=%d",
            sum(1 for s in best_analogy.dimension_scores if s.score >= 0.7),
            len(best_analogy.risk_factors),
        )

        # 可信度过滤
        if not best_analogy.is_reliable:
            logger.warning(
                "最佳类比不可靠 (confidence=%s), 回退",
                best_analogy.confidence.value,
            )
            spec.fallback_to_teach = True
            return spec

        # ── E3: 生成候选方案 ──
        spec.candidate_plans = self._plan_generator.generate_plans(
            best_analogy,
            spec.budget,
            source_config=source_config,
        )
        logger.info(
            "E3 完成: 生成 %d 个候选方案",
            len(spec.candidate_plans),
        )

        if not spec.candidate_plans:
            logger.warning("无可用候选方案（预算不足）")
            spec.fallback_to_teach = True
            return spec

        # ── E4 + E5: 逐个试探并评估 ──
        for plan in spec.candidate_plans:
            if spec.budget.is_exhausted:
                break

            trial = self._trial_runner.run_trial(plan, spec.budget)
            trial = self._evaluator.evaluate(trial, expected=expected_results)
            spec.trial_results.append(trial)

            logger.info(
                "E4+E5: plan=%s status=%s acceptable=%s",
                plan.plan_id,
                trial.status.value,
                trial.is_acceptable,
            )

            # 找到可接受的方案就停止
            if trial.should_promote:
                spec.selected_plan_id = plan.plan_id
                logger.info("选中方案: %s", plan.plan_id)
                break

        # ── E6: 失效处理 ──
        if spec.selected_plan_id is None:
            original_budget_max = spec.budget.max_trials
            self._failure_handler._initial_max_trials = original_budget_max
            self._failure_handler._relaxed_ceiling = original_budget_max
            max_retries = self._failure_handler._max_retries

            for retry in range(max_retries):
                spec = self._failure_handler.handle(spec, spec.trial_results)

                if spec.fallback_to_teach:
                    break

                # handle() 放宽了 budget.max_trials（供测试断言），
                # 但 run() 用原始预算约束重试次数
                spec.budget.max_trials = original_budget_max

                # 预算已耗尽则不再重试
                if spec.budget.is_exhausted:
                    break

                # 生成新的候选方案
                if spec.analogy_results:
                    best_analogy = spec.analogy_results[0]
                    spec.candidate_plans = self._plan_generator.generate_plans(
                        best_analogy,
                        spec.budget,
                        source_config=source_config,
                    )
                    logger.info(
                        "E6 重试 #%d: 生成 %d 个新候选方案",
                        retry + 1,
                        len(spec.candidate_plans),
                    )
                    if not spec.candidate_plans:
                        break

                # 用放宽后的方案重新试探
                for plan in spec.candidate_plans:
                    if spec.budget.is_exhausted:
                        break

                    trial = self._trial_runner.run_trial(plan, spec.budget)
                    trial = self._evaluator.evaluate(trial, expected=expected_results)
                    spec.trial_results.append(trial)

                    logger.info(
                        "E4+E5 重试: plan=%s status=%s acceptable=%s",
                        plan.plan_id,
                        trial.status.value,
                        trial.is_acceptable,
                    )

                    if trial.should_promote:
                        spec.selected_plan_id = plan.plan_id
                        logger.info("重试选中方案: %s", plan.plan_id)
                        break

                if spec.selected_plan_id is not None:
                    break

            # 恢复原始 max_trials
            spec.budget.max_trials = original_budget_max

            if self._failure_handler.should_escalate(spec):
                logger.warning(
                    "类比推理需要人工介入: spec=%s", spec.spec_id
                )

        logger.info(
            "类比推理完成: selected=%s fallback=%s",
            spec.selected_plan_id,
            spec.fallback_to_teach,
        )
        return spec
