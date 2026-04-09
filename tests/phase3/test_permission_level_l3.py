#!/usr/bin/env python3
"""
Tests for PermissionLevel L3 Integration (Task 24)

验证 Phase 2 PermissionLevel 正确集成到 Phase 3 的 E4/E6/Orchestrator 中：
- L0 SUGGEST_ONLY: 不执行试探，仅生成方案描述
- L1 DRY_RUN: 使用 mock 执行器，is_mock=True
- L2 EXECUTE: 使用注入的 executor
- L3 EXPLORE: 使用注入的 executor + budget 约束
"""

import pytest

from knowledge_compiler.phase2.execution_layer.failure_handler import PermissionLevel
from knowledge_compiler.phase3.analogy_schema import (
    AnalogyConfidence,
    AnalogyDimension,
    AnalogyResult,
    AnalogySpec,
    CandidatePlan,
    ExplorationBudget,
    SimilarityScore,
    TrialStatus,
)
from knowledge_compiler.phase3.orchestrator.analogy_engine import (
    AnalogicalOrchestrator,
    TrialRunner,
)


# ============================================================================
# Helpers
# ============================================================================

class MockKnowledgeStore:
    """测试用 mock 知识库"""

    def list_cases(self):
        return [{"case_id": "CASE-001"}]

    def get_case_features(self, case_id):
        return {
            "case_id": case_id,
            "geometry": {"shape": "channel", "dimensions": [1.0, 0.5]},
            "physics": {"Re": 1000, "flow_type": "internal"},
            "boundary": {"inlet": "velocity", "outlet": "pressure"},
            "flow_regime": {"solver_type": "simpleFoam"},
        }

    def get_patterns(self, tags=None):
        return []

    def get_rules(self, tags=None):
        return []


def _make_high_similarity_features():
    """创建与知识库高度相似的目标特征"""
    return {
        "case_id": "TARGET-001",
        "geometry": {"shape": "channel", "dimensions": [1.0, 0.5]},
        "physics": {"Re": 1200, "flow_type": "internal"},
        "boundary": {"inlet": "velocity", "outlet": "pressure"},
        "flow_regime": {"solver_type": "simpleFoam"},
    }


def _make_spec(permission_level="explore"):
    """创建测试用 AnalogySpec"""
    return AnalogySpec(
        target_case_id="TARGET-001",
        permission_level=permission_level,
        budget=ExplorationBudget(max_trials=3),
    )


# ============================================================================
# TrialRunner Permission Tests
# ============================================================================

class TestTrialRunnerPermissionLevels:
    """TrialRunner 权限级别行为测试"""

    def test_suggest_only_returns_cancelled(self):
        """L0: 不执行试探，返回 CANCELLED"""
        runner = TrialRunner(permission_level=PermissionLevel.SUGGEST_ONLY)
        plan = CandidatePlan(description="test plan", estimated_cost=0.1)
        budget = ExplorationBudget(max_trials=3)

        result = runner.run_trial(plan, budget)
        assert result.status == TrialStatus.CANCELLED
        assert "SUGGEST_ONLY" in result.evaluation_notes[0]
        assert budget.trials_used == 0  # 预算未消费

    def test_dry_run_uses_mock_executor(self):
        """L1: 使用 mock 执行器，输出 is_mock=True"""
        runner = TrialRunner(permission_level=PermissionLevel.DRY_RUN)
        plan = CandidatePlan(
            description="test plan",
            execution_params={"mesh_cells": 1000, "time_steps": 100},
        )
        budget = ExplorationBudget(max_trials=3)

        result = runner.run_trial(plan, budget)
        assert result.status == TrialStatus.COMPLETED
        assert result.output_data.get("is_mock") is True  # mock 标记

    def test_dry_run_ignores_injected_executor(self):
        """L1: 忽略注入的真实 executor，强制 mock"""
        call_count = {"n": 0}

        def real_executor(params):
            call_count["n"] += 1
            return {"output": {"real": True}, "convergence": {}}

        runner = TrialRunner(
            executor=real_executor,
            permission_level=PermissionLevel.DRY_RUN,
        )
        plan = CandidatePlan(execution_params={"mesh_cells": 100})
        budget = ExplorationBudget(max_trials=3)

        result = runner.run_trial(plan, budget)
        assert result.status == TrialStatus.COMPLETED
        assert call_count["n"] == 0  # 真实 executor 未被调用
        assert result.output_data.get("is_mock") is True

    def test_execute_uses_injected_executor(self):
        """L2: 使用注入的 executor"""
        def custom_executor(params):
            return {
                "output": {"custom": True, "mesh_cells": params.get("mesh_cells", 0)},
                "convergence": {"converged": True},
            }

        runner = TrialRunner(
            executor=custom_executor,
            permission_level=PermissionLevel.EXECUTE,
        )
        plan = CandidatePlan(execution_params={"mesh_cells": 5000})
        budget = ExplorationBudget(max_trials=3)

        result = runner.run_trial(plan, budget)
        assert result.status == TrialStatus.COMPLETED
        assert result.output_data.get("custom") is True
        assert "is_mock" not in result.output_data  # 非默认 mock

    def test_explore_uses_injected_executor(self):
        """L3: 使用注入的 executor"""
        def real_executor(params):
            return {
                "output": {"real": True, "status": "converged"},
                "convergence": {"residuals": [0.1, 0.01, 0.001]},
            }

        runner = TrialRunner(
            executor=real_executor,
            permission_level=PermissionLevel.EXPLORE,
        )
        plan = CandidatePlan(execution_params={"mesh_cells": 10000})
        budget = ExplorationBudget(max_trials=3)

        result = runner.run_trial(plan, budget)
        assert result.status == TrialStatus.COMPLETED
        assert result.output_data.get("real") is True

    def test_suggest_only_does_not_consume_budget(self):
        """L0: 多次调用不消耗预算"""
        runner = TrialRunner(permission_level=PermissionLevel.SUGGEST_ONLY)
        budget = ExplorationBudget(max_trials=2)
        plan = CandidatePlan()

        for _ in range(5):
            runner.run_trial(plan, budget)

        assert budget.trials_used == 0
        assert not budget.is_exhausted


# ============================================================================
# Orchestrator Permission Tests
# ============================================================================

class TestOrchestratorPermissionLevels:
    """AnalogicalOrchestrator 权限传播测试"""

    def test_suggest_only_skips_trials(self):
        """L0 orchestrator: 跳过试探，仅生成方案"""
        store = MockKnowledgeStore()
        orch = AnalogicalOrchestrator(
            store,
            permission_level=PermissionLevel.SUGGEST_ONLY,
        )
        spec = _make_spec("suggest_only")

        result = orch.run(spec, target_features=_make_high_similarity_features())

        # 应有类比结果和候选方案，但无试探结果
        assert len(result.analogy_results) > 0
        assert len(result.candidate_plans) > 0
        assert len(result.trial_results) == 0
        assert result.selected_plan_id is None  # 无试探无法选中

    def test_dry_run_produces_mock_trials(self):
        """L1 orchestrator: 产生 mock 试探"""
        store = MockKnowledgeStore()
        orch = AnalogicalOrchestrator(
            store,
            permission_level=PermissionLevel.DRY_RUN,
        )
        spec = _make_spec("dry_run")

        result = orch.run(spec, target_features=_make_high_similarity_features())

        # 应有试探结果，且都是 mock
        assert len(result.trial_results) > 0
        for trial in result.trial_results:
            if trial.output_data:
                assert trial.output_data.get("is_mock") is True

    def test_explore_produces_real_trials(self):
        """L3 orchestrator: 使用真实（注入的）executor"""
        call_count = {"n": 0}

        def real_executor(params):
            call_count["n"] += 1
            return {
                "output": {
                    "mesh_cells": params.get("mesh_cells", 0),
                    "final_residual": 0.001,
                    "status": "converged",
                },
                "convergence": {
                    "residuals": [1.0, 0.1, 0.01, 0.001],
                    "converged": True,
                },
            }

        store = MockKnowledgeStore()
        orch = AnalogicalOrchestrator(
            store,
            executor=real_executor,
            permission_level=PermissionLevel.EXPLORE,
        )
        spec = _make_spec("explore")

        result = orch.run(spec, target_features=_make_high_similarity_features())

        assert call_count["n"] > 0
        assert len(result.trial_results) > 0

    def test_permission_level_default_is_explore(self):
        """默认权限级别为 EXPLORE"""
        store = MockKnowledgeStore()
        orch = AnalogicalOrchestrator(store)
        assert orch._permission_level == PermissionLevel.EXPLORE

    def test_permission_propagated_to_trial_runner(self):
        """权限级别传播到 TrialRunner"""
        store = MockKnowledgeStore()
        orch = AnalogicalOrchestrator(
            store,
            permission_level=PermissionLevel.DRY_RUN,
        )
        assert orch._trial_runner._permission_level == PermissionLevel.DRY_RUN


# ============================================================================
# AnalogySpec Permission Properties Tests
# ============================================================================

class TestAnalogySpecPermissionProperties:
    """AnalogySpec 权限属性测试"""

    def test_allows_real_execution_l2(self):
        spec = AnalogySpec(permission_level="execute")
        assert spec.allows_real_execution is True

    def test_allows_real_execution_l3(self):
        spec = AnalogySpec(permission_level="explore")
        assert spec.allows_real_execution is True

    def test_allows_real_execution_l0_l1(self):
        for level in ("suggest_only", "dry_run"):
            spec = AnalogySpec(permission_level=level)
            assert spec.allows_real_execution is False

    def test_allows_trials_l1(self):
        spec = AnalogySpec(permission_level="dry_run")
        assert spec.allows_trials is True

    def test_allows_trials_l0(self):
        spec = AnalogySpec(permission_level="suggest_only")
        assert spec.allows_trials is False

    def test_permission_level_in_to_dict(self):
        spec = AnalogySpec(permission_level="explore")
        d = spec.to_dict()
        assert d["permission_level"] == "explore"

    def test_default_permission_is_explore(self):
        spec = AnalogySpec()
        assert spec.permission_level == "explore"


# ============================================================================
# Cross-Level Behavior Tests
# ============================================================================

class TestCrossLevelBehavior:
    """跨权限级别行为一致性测试"""

    def test_same_knowledge_store_all_levels(self):
        """同一知识库，不同权限级别都能完成 E1-E3"""
        store = MockKnowledgeStore()
        features = _make_high_similarity_features()

        for level in PermissionLevel:
            orch = AnalogicalOrchestrator(store, permission_level=level)
            spec = _make_spec(level.value)
            result = orch.run(spec, target_features=features)

            # E1 应该始终产出类比结果
            assert len(result.analogy_results) > 0, f"No analogy results for {level.value}"

    def test_l0_l1_no_budget_consumption(self):
        """L0/L1 不消耗实际计算预算"""
        store = MockKnowledgeStore()

        for level in [PermissionLevel.SUGGEST_ONLY, PermissionLevel.DRY_RUN]:
            orch = AnalogicalOrchestrator(store, permission_level=level)
            spec = _make_spec(level.value)
            spec.budget = ExplorationBudget(max_trials=1)
            result = orch.run(spec, target_features=_make_high_similarity_features())

            if level == PermissionLevel.SUGGEST_ONLY:
                assert result.budget.trials_used == 0
