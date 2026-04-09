#!/usr/bin/env python3
"""
Tests for Phase 2.5: AnalogySpec Schema + PermissionLevel L3 + Incremental Replay
"""

import tempfile
import time
from pathlib import Path

import pytest

from knowledge_compiler.phase2.execution_layer.failure_handler import PermissionLevel
from knowledge_compiler.phase2c.benchmark_replay import (
    BenchmarkCase,
    BenchmarkReplayEngine,
    BenchmarkReplayResult,
    BenchmarkSuite,
)
from knowledge_compiler.phase2c.correction_recorder import (
    CorrectionRecord,
    CorrectionSeverity,
)
from knowledge_compiler.phase1.schema import ErrorType, ImpactScope
from knowledge_compiler.phase3.analogy_schema import (
    AnalogyDimension,
    AnalogyConfidence,
    AnalogyResult,
    SimilarityScore,
    CandidatePlan,
    TrialResult,
    TrialStatus,
    ExplorationBudget,
    AnalogySpec,
)


# ============================================================================
# Test PermissionLevel L3
# ============================================================================

class TestPermissionLevelL3:
    """测试 PermissionLevel L3 扩展"""

    def test_explore_level_exists(self):
        """测试 L3 EXPLORE 级别存在"""
        assert hasattr(PermissionLevel, "EXPLORE")
        assert PermissionLevel.EXPLORE.value == "explore"

    def test_all_levels_present(self):
        """测试所有权限级别"""
        levels = list(PermissionLevel)
        assert len(levels) == 4
        assert PermissionLevel.SUGGEST_ONLY in levels
        assert PermissionLevel.DRY_RUN in levels
        assert PermissionLevel.EXECUTE in levels
        assert PermissionLevel.EXPLORE in levels

    def test_level_ordering(self):
        """测试级别排序"""
        assert PermissionLevel.SUGGEST_ONLY.value == "suggest_only"
        assert PermissionLevel.DRY_RUN.value == "dry_run"
        assert PermissionLevel.EXECUTE.value == "execute"
        assert PermissionLevel.EXPLORE.value == "explore"


# ============================================================================
# Test AnalogySpec Schema
# ============================================================================

class TestAnalogyDimension:
    """测试类比维度"""

    def test_all_dimensions(self):
        """测试所有维度"""
        dims = list(AnalogyDimension)
        assert len(dims) == 7
        assert AnalogyDimension.GEOMETRY in dims
        assert AnalogyDimension.PHYSICS in dims
        assert AnalogyDimension.BOUNDARY in dims
        assert AnalogyDimension.MESH in dims
        assert AnalogyDimension.FLOW_REGIME in dims
        assert AnalogyDimension.NUMERICAL in dims
        assert AnalogyDimension.REPORT in dims


class TestSimilarityScore:
    """测试相似性评分"""

    def test_score_creation(self):
        """测试创建评分"""
        score = SimilarityScore(
            dimension=AnalogyDimension.GEOMETRY,
            score=0.85,
            evidence=["相同几何类型"],
            weight=1.0,
        )
        assert score.dimension == AnalogyDimension.GEOMETRY
        assert score.score == 0.85
        assert score.weighted_score == 0.85

    def test_weighted_score(self):
        """测试加权评分"""
        score = SimilarityScore(
            dimension=AnalogyDimension.PHYSICS,
            score=0.9,
            weight=2.0,
        )
        assert score.weighted_score == 1.8

    def test_score_to_dict(self):
        """测试转换为字典"""
        score = SimilarityScore(
            dimension=AnalogyDimension.BOUNDARY,
            score=0.7,
        )
        d = score.to_dict()
        assert d["dimension"] == "boundary"
        assert d["score"] == 0.7
        assert "weighted_score" in d


class TestAnalogyResult:
    """测试类比结果"""

    def test_result_creation(self):
        """测试创建类比结果"""
        result = AnalogyResult(
            source_case_id="CASE-001",
            target_case_id="BENCH-04",
            confidence=AnalogyConfidence.HIGH,
        )
        assert result.source_case_id == "CASE-001"
        assert result.target_case_id == "BENCH-04"
        assert result.confidence == AnalogyConfidence.HIGH
        assert result.is_reliable is True

    def test_reliability_check(self):
        """测试可靠性判断"""
        high = AnalogyResult(confidence=AnalogyConfidence.HIGH)
        assert high.is_reliable is True

        medium = AnalogyResult(confidence=AnalogyConfidence.MEDIUM)
        assert medium.is_reliable is True

        low = AnalogyResult(confidence=AnalogyConfidence.LOW)
        assert low.is_reliable is False

        unreliable = AnalogyResult(confidence=AnalogyConfidence.UNRELIABLE)
        assert unreliable.is_reliable is False

    def test_calculate_overall_similarity(self):
        """测试计算综合相似度"""
        result = AnalogyResult(
            dimension_scores=[
                SimilarityScore(dimension=AnalogyDimension.GEOMETRY, score=0.9, weight=2.0),
                SimilarityScore(dimension=AnalogyDimension.PHYSICS, score=0.7, weight=1.0),
            ],
        )

        overall = result.calculate_overall_similarity()
        assert 0.7 < overall < 0.9  # 加权平均
        assert result.overall_similarity == overall

    def test_empty_scores(self):
        """测试空评分列表"""
        result = AnalogyResult()
        assert result.calculate_overall_similarity() == 0.0

    def test_to_dict(self):
        """测试转换为字典"""
        result = AnalogyResult(
            source_case_id="S-001",
            target_case_id="T-001",
            confidence=AnalogyConfidence.MEDIUM,
        )
        d = result.to_dict()
        assert d["source_case_id"] == "S-001"
        assert d["confidence"] == "medium"
        assert "analogy_id" in d


class TestCandidatePlan:
    """测试候选方案"""

    def test_plan_creation(self):
        """测试创建候选方案"""
        plan = CandidatePlan(
            rank=1,
            description="粗网格试探",
            estimated_cost=0.3,
            estimated_accuracy=0.85,
        )
        assert plan.rank == 1
        assert plan.is_low_cost is True

    def test_high_cost_plan(self):
        """测试高成本方案"""
        plan = CandidatePlan(
            estimated_cost=2.0,
        )
        assert plan.is_low_cost is False

    def test_plan_to_dict(self):
        """测试转换为字典"""
        plan = CandidatePlan(rank=2, description="简化模型")
        d = plan.to_dict()
        assert d["rank"] == 2
        assert d["description"] == "简化模型"


class TestTrialResult:
    """测试试探结果"""

    def test_result_creation(self):
        """测试创建试探结果"""
        result = TrialResult(
            status=TrialStatus.COMPLETED,
            deviation_from_expected=0.05,
            is_acceptable=True,
        )
        assert result.status == TrialStatus.COMPLETED
        assert result.deviation_percentage == 5.0
        assert result.should_promote is True

    def test_should_not_promote_high_deviation(self):
        """测试高偏差不升级"""
        result = TrialResult(
            status=TrialStatus.COMPLETED,
            deviation_from_expected=0.2,
            is_acceptable=True,
        )
        assert result.deviation_percentage == 20.0
        assert result.should_promote is False

    def test_should_not_promote_failed(self):
        """测试失败不升级"""
        result = TrialResult(
            status=TrialStatus.FAILED,
            deviation_from_expected=0.0,
            is_acceptable=False,
        )
        assert result.should_promote is False

    def test_to_dict(self):
        """测试转换为字典"""
        result = TrialResult(status=TrialStatus.PENDING)
        d = result.to_dict()
        assert d["status"] == "pending"
        assert "should_promote" in d


class TestExplorationBudget:
    """测试探索预算"""

    def test_budget_creation(self):
        """测试创建预算"""
        budget = ExplorationBudget(
            max_trials=3,
            max_compute_hours=1.0,
        )
        assert budget.max_trials == 3
        assert budget.is_exhausted is False
        assert budget.trials_used == 0

    def test_consume_trial(self):
        """测试消费试探"""
        budget = ExplorationBudget(max_trials=2)
        assert budget.consume_trial() is True
        assert budget.trials_used == 1
        assert budget.consume_trial() is True
        assert budget.trials_used == 2
        assert budget.is_exhausted is True
        assert budget.consume_trial() is False

    def test_budget_to_dict(self):
        """测试转换为字典"""
        budget = ExplorationBudget()
        d = budget.to_dict()
        assert "max_trials" in d
        assert "is_exhausted" in d


class TestAnalogySpec:
    """测试类比推理规范"""

    def test_spec_creation(self):
        """测试创建规范"""
        spec = AnalogySpec(
            target_case_id="UNKNOWN-001",
            problem_description="未知内流场算例",
            problem_type="internal_flow",
        )
        assert spec.target_case_id == "UNKNOWN-001"
        assert spec.fallback_to_teach is False
        assert len(spec.analogy_results) == 0

    def test_spec_with_full_workflow(self):
        """测试完整工作流"""
        spec = AnalogySpec(
            target_case_id="UNKNOWN-002",
            problem_description="外部流场",
            problem_type="external_flow",
        )

        # Step 1: 添加类比结果
        analogy = AnalogyResult(
            source_case_id="KNOWN-001",
            target_case_id="UNKNOWN-002",
            dimension_scores=[
                SimilarityScore(dimension=AnalogyDimension.GEOMETRY, score=0.8),
                SimilarityScore(dimension=AnalogyDimension.PHYSICS, score=0.7),
            ],
            confidence=AnalogyConfidence.HIGH,
        )
        analogy.calculate_overall_similarity()
        spec.analogy_results.append(analogy)

        # Step 2: 生成候选方案
        plan = CandidatePlan(
            analogy_id=analogy.analogy_id,
            rank=1,
            description="粗网格 RANS 试探",
            estimated_cost=0.2,
            estimated_accuracy=0.8,
        )
        spec.candidate_plans.append(plan)

        # Step 3: 执行试探
        trial = TrialResult(
            plan_id=plan.plan_id,
            status=TrialStatus.COMPLETED,
            deviation_from_expected=0.03,
            is_acceptable=True,
        )
        spec.trial_results.append(trial)
        spec.budget.consume_trial(compute_hours=0.2)

        # Step 4: 验证结果
        assert len(spec.analogy_results) == 1
        assert len(spec.candidate_plans) == 1
        assert len(spec.trial_results) == 1
        assert trial.should_promote is True
        assert spec.budget.trials_used == 1

        # Step 5: 选择方案
        spec.selected_plan_id = plan.plan_id

        # 验证完整字典
        d = spec.to_dict()
        assert d["selected_plan_id"] == plan.plan_id
        assert len(d["analogy_results"]) == 1
        assert len(d["candidate_plans"]) == 1
        assert len(d["trial_results"]) == 1


# ============================================================================
# Test Incremental Benchmark Replay
# ============================================================================

class TestIncrementalReplay:
    """测试增量回放"""

    def _create_test_suite(self):
        """创建测试用样板集"""
        suite = BenchmarkSuite(storage_path="/nonexistent/path")

        cases = [
            BenchmarkCase(
                case_id="BENCH-VAL-001",
                name="数值验证案例",
                description="Numerical validation",
                category="validation",
                difficulty="easy",
                input_data={"type": "numerical"},
                expected_output={"result": 1.0},
            ),
            BenchmarkCase(
                case_id="BENCH-VIS-001",
                name="可视化验证案例",
                description="Visualization validation",
                category="visualization",
                difficulty="easy",
                input_data={"type": "visual"},
                expected_output={"rendered": True},
            ),
            BenchmarkCase(
                case_id="BENCH-BC-001",
                name="边界条件案例",
                description="Boundary condition test",
                category="boundary",
                difficulty="medium",
                input_data={"type": "boundary"},
                expected_output={"converged": True},
            ),
            BenchmarkCase(
                case_id="BENCH-MESH-001",
                name="网格质量案例",
                description="Mesh quality test",
                category="mesh",
                difficulty="medium",
                input_data={"type": "mesh"},
                expected_output={"quality": "good"},
            ),
        ]

        for case in cases:
            suite.add_case(case)

        return suite

    def _create_correction(self, error_type=ErrorType.INCORRECT_DATA):
        """创建测试用修正记录"""
        return CorrectionRecord(
            record_id="REC-INC-001",
            created_at=time.time(),
            error_type=error_type,
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="数值计算错误需要修正参数设置",
            fix_action="修正数据值并添加正确参数",
            human_reason="测试增量回放",
            evidence=["测试"],
            severity=CorrectionSeverity.MEDIUM,
            needs_replay=True,
            wrong_output={"result": 0.5},
            correct_output={"result": 1.0},
        )

    def test_incremental_replay_filters_by_category(self):
        """测试增量回放按类别过滤"""
        suite = self._create_test_suite()
        engine = BenchmarkReplayEngine(benchmark_suite=suite)
        correction = self._create_correction(ErrorType.INCORRECT_DATA)

        results = engine.replay_correction_incremental(correction)

        # 应该有结果返回
        assert len(results) > 0
        assert all(isinstance(r, BenchmarkReplayResult) for r in results)

    def test_incremental_replay_respects_max_cases(self):
        """测试增量回放限制最大案例数"""
        suite = self._create_test_suite()
        engine = BenchmarkReplayEngine(benchmark_suite=suite)
        correction = self._create_correction()

        results = engine.replay_correction_incremental(
            correction,
            max_cases=2,
        )

        assert len(results) <= 2

    def test_incremental_replay_with_category_filter(self):
        """测试带类别过滤的增量回放"""
        suite = self._create_test_suite()
        engine = BenchmarkReplayEngine(benchmark_suite=suite)
        correction = self._create_correction()

        results = engine.replay_correction_incremental(
            correction,
            filter_category="validation",
        )

        # 结果应该都来自 validation 类别
        for result in results:
            assert result.case_id.startswith("BENCH-VAL")

    def test_incremental_replay_empty_suite(self):
        """测试空样板集的增量回放"""
        suite = BenchmarkSuite(storage_path="/nonexistent/path")
        engine = BenchmarkReplayEngine(benchmark_suite=suite)
        correction = self._create_correction()

        results = engine.replay_correction_incremental(correction)
        assert len(results) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
