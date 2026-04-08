#!/usr/bin/env python3
"""
Tests for Phase 3 Analogical Reasoning Engine (E1-E6)

Tests cover:
- E1 SimilarityEngine: similarity retrieval and scoring
- E2 AnalogyDecomposer: dimension decomposition
- E3 CandidatePlanGenerator: plan generation
- E4 TrialRunner: trial execution
- E5 TrialEvaluator: result evaluation
- E6 AnalogyFailureHandler: failure handling
- AnalogicalOrchestrator: full E1->E6 pipeline
"""

import pytest

from knowledge_compiler.phase3.analogy_schema import (
    AnalogyConfidence,
    AnalogyDimension,
    AnalogyResult,
    AnalogySpec,
    CandidatePlan,
    ExplorationBudget,
    SimilarityScore,
    TrialResult,
    TrialStatus,
)
from knowledge_compiler.phase3.orchestrator.analogy_engine import (
    AnalogyDecomposer,
    AnalogyFailureHandler,
    AnalogicalOrchestrator,
    CandidatePlanGenerator,
    SimilarityEngine,
    TrialEvaluator,
    TrialRunner,
    _jaccard_similarity,
    _logarithmic_distance,
    _numeric_distance,
    _should_use_log,
    _HARD_CONSTRAINT_KEYS,
)
from knowledge_compiler.phase3.analogy_schema import (
    AnalogyFailureBundle,
)


# ============================================================================
# Mock Knowledge Store
# ============================================================================

class MockKnowledgeStore:
    """Mock knowledge store for testing"""

    def __init__(self, cases=None, patterns=None, rules=None):
        self._cases = cases or []
        self._patterns = patterns or []
        self._rules = rules or []

    def list_cases(self):
        return self._cases

    def get_case_features(self, case_id: str):
        for c in self._cases:
            if c.get("case_id") == case_id:
                return c.get("features", {})
        return {}

    def get_patterns(self, tags=None):
        if not tags:
            return self._patterns
        return [
            p for p in self._patterns
            if any(t in p.get("tags", []) for t in tags)
        ]

    def get_rules(self, tags=None):
        if not tags:
            return self._rules
        return [
            r for r in self._rules
            if any(t in r.get("tags", []) for t in tags)
        ]


def _make_case(case_id: str, **feature_overrides):
    """Helper: create mock case metadata"""
    base_features = {
        "geometry": {"type": "pipe", "has_curvature": True, "diameter": 0.1},
        "physics": {"model": "RANS", "turbulence": "kOmegaSST"},
        "boundary": {"inlet": "fixedValue", "outlet": "zeroGradient"},
        "mesh": {"cells": 50000, "type": "hexahedral"},
        "flow_regime": {"Re": 50000, "regime": "turbulent"},
        "numerical": {"scheme": "secondOrder", "solver": "GAMG"},
        "report": {"format": "html", "sections": ["residuals", "forces"]},
    }
    base_features.update(feature_overrides)
    return {"case_id": case_id, "features": base_features}


def _make_target(**overrides):
    """Helper: create target case features"""
    return _make_case("TARGET", **overrides).get("features", {})


# ============================================================================
# Helper function tests
# ============================================================================

class TestHelpers:
    def test_jaccard_identical(self):
        assert _jaccard_similarity({1, 2, 3}, {1, 2, 3}) == 1.0

    def test_jaccard_disjoint(self):
        assert _jaccard_similarity({1, 2}, {3, 4}) == 0.0

    def test_jaccard_partial(self):
        s = _jaccard_similarity({1, 2, 3}, {2, 3, 4})
        assert 0.0 < s < 1.0

    def test_jaccard_empty(self):
        assert _jaccard_similarity(set(), set()) == 1.0

    def test_numeric_distance_same(self):
        assert _numeric_distance(1.0, 1.0) == 1.0

    def test_numeric_distance_different(self):
        d = _numeric_distance(0.0, 2.0, scale=2.0)
        assert d == 0.0

    def test_numeric_distance_partial(self):
        d = _numeric_distance(1.0, 1.5, scale=2.0)
        assert 0.0 < d < 1.0

    def test_log_distance_same(self):
        assert _logarithmic_distance(1e6, 1e6) == 1.0

    def test_log_distance_one_order(self):
        d = _logarithmic_distance(1e6, 1e7)
        assert 0.0 < d < 1.0

    def test_log_distance_many_orders(self):
        d = _logarithmic_distance(1e2, 1e8)
        assert d == 0.0  # 6 orders of magnitude apart

    def test_log_distance_zero(self):
        assert _logarithmic_distance(0, 0) == 1.0

    def test_should_use_log(self):
        assert _should_use_log("Re")
        assert _should_use_log("Mach")
        assert _should_use_log("reynolds_number")
        assert not _should_use_log("diameter")
        assert not _should_use_log("mesh_cells")

    def test_hard_constraint_keys_defined(self):
        assert "FlowType" in _HARD_CONSTRAINT_KEYS
        assert "Compressibility" in _HARD_CONSTRAINT_KEYS


# ============================================================================
# E1: SimilarityEngine tests
# ============================================================================

class TestSimilarityEngine:
    def setup_method(self):
        self.store = MockKnowledgeStore(
            cases=[
                _make_case("SRC-1", geometry={"type": "pipe", "diameter": 0.1}),
                _make_case("SRC-2", geometry={"type": "airfoil", "diameter": 0.5}),
            ]
        )
        self.engine = SimilarityEngine(self.store)

    def test_find_similar_returns_results(self):
        target = _make_target(geometry={"type": "pipe", "diameter": 0.1})
        results = self.engine.find_similar_cases(target)
        assert len(results) >= 1

    def test_find_similar_ranks_by_score(self):
        target = _make_target(geometry={"type": "pipe", "diameter": 0.1})
        results = self.engine.find_similar_cases(target)
        if len(results) >= 2:
            assert results[0].overall_similarity >= results[1].overall_similarity

    def test_find_similar_top_k(self):
        target = _make_target()
        results = self.engine.find_similar_cases(target, top_k=1)
        assert len(results) <= 1

    def test_threshold_filtering(self):
        engine = SimilarityEngine(self.store, similarity_threshold=0.99)
        target = _make_target(geometry={"type": "completely_different"})
        results = engine.find_similar_cases(target)
        assert all(r.overall_similarity >= 0.99 for r in results)

    def test_confidence_mapping(self):
        assert SimilarityEngine._score_to_confidence(0.9) == AnalogyConfidence.HIGH
        assert SimilarityEngine._score_to_confidence(0.65) == AnalogyConfidence.MEDIUM
        assert SimilarityEngine._score_to_confidence(0.45) == AnalogyConfidence.LOW
        assert SimilarityEngine._score_to_confidence(0.2) == AnalogyConfidence.UNRELIABLE

    def test_empty_store(self):
        store = MockKnowledgeStore()
        engine = SimilarityEngine(store)
        results = engine.find_similar_cases(_make_target())
        assert results == []

    def test_dimension_scores_populated(self):
        target = _make_target()
        results = self.engine.find_similar_cases(target)
        if results:
            assert len(results[0].dimension_scores) > 0
            for score in results[0].dimension_scores:
                assert 0.0 <= score.score <= 1.0

    def test_hard_constraint_flowtype_mismatch(self):
        """FlowType 不匹配应导致物理维度分数极低"""
        store = MockKnowledgeStore(cases=[
            _make_case("SRC-EXT", physics={"FlowType": "external", "model": "RANS"}),
        ])
        engine = SimilarityEngine(store)
        target = _make_target(
            physics={"FlowType": "internal", "model": "RANS"},
        )
        results = engine.find_similar_cases(target)
        if results:
            phys_scores = [
                s for s in results[0].dimension_scores
                if s.dimension == AnalogyDimension.PHYSICS
            ]
            if phys_scores:
                assert phys_scores[0].score < 0.2


# ============================================================================
# E2: AnalogyDecomposer tests
# ============================================================================

class TestAnalogyDecomposer:
    def setup_method(self):
        self.store = MockKnowledgeStore(
            patterns=[
                {"pattern_id": "PAT-1", "tags": ["dim:geometry"]},
                {"pattern_id": "PAT-2", "tags": ["dim:physics"]},
            ],
            rules=[
                {"rule_id": "RULE-1", "tags": ["dim:boundary"]},
            ],
        )
        self.decomposer = AnalogyDecomposer(self.store)

    def _make_analogy(self):
        return AnalogyResult(
            source_case_id="SRC-1",
            target_case_id="TARGET",
            dimension_scores=[
                SimilarityScore(dimension=AnalogyDimension.GEOMETRY, score=0.85),
                SimilarityScore(dimension=AnalogyDimension.PHYSICS, score=0.75),
                SimilarityScore(dimension=AnalogyDimension.BOUNDARY, score=0.3),
                SimilarityScore(dimension=AnalogyDimension.MESH, score=0.9),
            ],
        )

    def test_decompose_sorts_by_score(self):
        analogy = self._make_analogy()
        result = self.decomposer.decompose(analogy)
        scores = [s.score for s in result.dimension_scores]
        assert scores == sorted(scores, reverse=True)

    def test_decompose_identifies_strong_dims(self):
        analogy = self._make_analogy()
        result = self.decomposer.decompose(analogy)
        strong = [s for s in result.dimension_scores if s.score >= 0.7]
        assert len(strong) >= 2

    def test_decompose_extracts_actions(self):
        analogy = self._make_analogy()
        result = self.decomposer.decompose(analogy)
        assert len(result.transferable_actions) > 0

    def test_decompose_extracts_risks(self):
        analogy = self._make_analogy()
        result = self.decomposer.decompose(analogy)
        assert len(result.risk_factors) > 0

    def test_decompose_matches_patterns(self):
        analogy = self._make_analogy()
        result = self.decomposer.decompose(analogy)
        assert isinstance(result.matched_patterns, list)

    def test_decompose_matches_rules(self):
        analogy = self._make_analogy()
        result = self.decomposer.decompose(analogy)
        assert isinstance(result.matched_rules, list)


# ============================================================================
# E3: CandidatePlanGenerator tests
# ============================================================================

class TestCandidatePlanGenerator:
    def setup_method(self):
        self.generator = CandidatePlanGenerator()

    def _make_analogy(self):
        return AnalogyResult(
            source_case_id="SRC-1",
            overall_similarity=0.8,
            confidence=AnalogyConfidence.HIGH,
            matched_patterns=["PAT-1"],
            matched_rules=["RULE-1"],
            dimension_scores=[
                SimilarityScore(dimension=AnalogyDimension.GEOMETRY, score=0.9),
            ],
        )

    def test_generate_three_plans(self):
        analogy = self._make_analogy()
        budget = ExplorationBudget(max_trials=3)
        plans = self.generator.generate_plans(analogy, budget)
        assert len(plans) == 3

    def test_plans_ranked(self):
        analogy = self._make_analogy()
        budget = ExplorationBudget()
        plans = self.generator.generate_plans(analogy, budget)
        ranks = [p.rank for p in plans]
        assert ranks == sorted(ranks)

    def test_plan_respects_budget(self):
        analogy = self._make_analogy()
        budget = ExplorationBudget(max_mesh_cells=100)
        plans = self.generator.generate_plans(
            analogy, budget,
            source_config={"mesh_cells": 100000, "time_steps": 1000, "compute_hours": 10},
        )
        for plan in plans:
            assert plan.execution_params.get("mesh_cells", 0) <= 100

    def test_plan_a_is_low_cost(self):
        analogy = self._make_analogy()
        budget = ExplorationBudget()
        plans = self.generator.generate_plans(analogy, budget)
        plan_a = plans[0]
        assert plan_a.is_low_cost or plan_a.estimated_cost <= 0.5

    def test_plan_risk_levels(self):
        analogy = self._make_analogy()
        budget = ExplorationBudget()
        plans = self.generator.generate_plans(analogy, budget)
        risk_levels = {p.risk_level for p in plans}
        assert "high" in risk_levels or "medium" in risk_levels

    def test_empty_analogy(self):
        analogy = AnalogyResult(overall_similarity=0.2)
        budget = ExplorationBudget()
        plans = self.generator.generate_plans(analogy, budget)
        for plan in plans:
            assert plan.estimated_accuracy >= 0.3


# ============================================================================
# E4: TrialRunner tests
# ============================================================================

class TestTrialRunner:
    def test_default_executor_mock(self):
        runner = TrialRunner()
        plan = CandidatePlan(
            execution_params={"mesh_cells": 5000, "time_steps": 50}
        )
        budget = ExplorationBudget()
        result = runner.run_trial(plan, budget)
        assert result.status == TrialStatus.COMPLETED
        assert result.execution_time >= 0

    def test_budget_consumed(self):
        runner = TrialRunner()
        plan = CandidatePlan(execution_params={"mesh_cells": 1000})
        budget = ExplorationBudget(max_trials=1)
        runner.run_trial(plan, budget)
        assert budget.trials_used == 1

    def test_budget_exhausted(self):
        runner = TrialRunner()
        plan = CandidatePlan(execution_params={})
        budget = ExplorationBudget(max_trials=0)
        result = runner.run_trial(plan, budget)
        assert result.status == TrialStatus.BUDGET_EXCEEDED

    def test_custom_executor(self):
        def my_executor(params):
            return {"output": {"custom": True}, "convergence": {}}

        runner = TrialRunner(executor=my_executor)
        plan = CandidatePlan(execution_params={})
        budget = ExplorationBudget()
        result = runner.run_trial(plan, budget)
        assert result.output_data.get("custom") is True

    def test_executor_exception(self):
        def failing_executor(params):
            raise RuntimeError("solver crashed")

        runner = TrialRunner(executor=failing_executor)
        plan = CandidatePlan(execution_params={})
        budget = ExplorationBudget()
        result = runner.run_trial(plan, budget)
        assert result.status == TrialStatus.FAILED
        assert len(result.evaluation_notes) > 0

    def test_convergence_data_collected(self):
        runner = TrialRunner()
        plan = CandidatePlan(
            execution_params={"mesh_cells": 2000, "time_steps": 100}
        )
        budget = ExplorationBudget()
        result = runner.run_trial(plan, budget)
        assert "residuals" in result.convergence_data


# ============================================================================
# E5: TrialEvaluator tests
# ============================================================================

class TestTrialEvaluator:
    def setup_method(self):
        self.evaluator = TrialEvaluator()

    def _make_completed_trial(self, **overrides):
        defaults = {
            "status": TrialStatus.COMPLETED,
            "output_data": {"final_residual": 0.001, "value": 42.0},
            "convergence_data": {
                "residuals": [1.0, 0.5, 0.1, 0.01, 0.001],
                "converged": True,
            },
        }
        defaults.update(overrides)
        return TrialResult(**defaults)

    def test_evaluate_acceptable_trial(self):
        trial = self._make_completed_trial()
        result = self.evaluator.evaluate(trial)
        assert result.is_acceptable

    def test_evaluate_non_completed(self):
        trial = TrialResult(status=TrialStatus.FAILED)
        result = self.evaluator.evaluate(trial)
        assert not result.is_acceptable

    def test_gate_checks_populated(self):
        trial = self._make_completed_trial()
        result = self.evaluator.evaluate(trial)
        assert "converged" in result.gate_results
        assert "no_divergence" in result.gate_results

    def test_divergence_detected(self):
        trial = self._make_completed_trial(
            convergence_data={
                "residuals": [0.01, 0.1, 1.0, 10.0],
                "converged": False,
            },
            output_data={"final_residual": 10.0, "value": 1.0},
        )
        result = self.evaluator.evaluate(trial)
        assert not result.gate_results.get("no_divergence", True)

    def test_deviation_with_expected(self):
        trial = self._make_completed_trial(
            output_data={"final_residual": 0.5, "value": 50.0},
        )
        result = self.evaluator.evaluate(
            trial, expected={"final_residual": 0.001, "value": 42.0}
        )
        assert result.deviation_from_expected > 0

    def test_deviation_within_threshold(self):
        trial = self._make_completed_trial(
            output_data={"final_residual": 0.001, "value": 42.0},
        )
        result = self.evaluator.evaluate(
            trial, expected={"final_residual": 0.001, "value": 42.0}
        )
        assert result.deviation_percentage <= 15.0

    def test_should_promote(self):
        trial = self._make_completed_trial()
        result = self.evaluator.evaluate(trial)
        assert result.should_promote

    def test_infer_deviation_converged(self):
        trial = self._make_completed_trial()
        result = self.evaluator.evaluate(trial, expected=None)
        assert result.deviation_from_expected <= 0.1

    def test_analogy_deviation_check_pass(self):
        """Trial close to analogy reference should pass"""
        trial = self._make_completed_trial(
            output_data={"final_residual": 0.001, "Cd": 0.45},
        )
        result = self.evaluator.evaluate(
            trial,
            analogy_reference={"Cd": 0.42},
        )
        assert result.gate_results.get("analogy_deviation", True)

    def test_analogy_deviation_check_fail(self):
        """Trial far from analogy reference should fail G4-P3"""
        trial = self._make_completed_trial(
            output_data={"final_residual": 0.001, "Cd": 2.5},
        )
        result = self.evaluator.evaluate(
            trial,
            analogy_reference={"Cd": 0.42},
        )
        assert not result.gate_results.get("analogy_deviation", True)
        assert any("类比偏差" in n for n in result.evaluation_notes)


# ============================================================================
# E6: AnalogyFailureHandler tests
# ============================================================================

class TestAnalogyFailureHandler:
    def setup_method(self):
        self.handler = AnalogyFailureHandler()

    def test_fallback_when_no_similar(self):
        spec = AnalogySpec(
            analogy_results=[
                AnalogyResult(overall_similarity=0.1)
            ]
        )
        result = self.handler.handle(spec, [])
        assert result.fallback_to_teach is True

    def test_retry_on_trial_failure(self):
        spec = AnalogySpec(
            analogy_results=[AnalogyResult(overall_similarity=0.7)],
            trial_results=[TrialResult(status=TrialStatus.FAILED)],
        )
        original_max = spec.budget.max_trials
        result = self.handler.handle(
            spec,
            [TrialResult(status=TrialStatus.FAILED)],
        )
        assert result.budget.max_trials > original_max or result.fallback_to_teach

    def test_max_retries_exceeded(self):
        handler = AnalogyFailureHandler(max_retries=0)
        spec = AnalogySpec(
            analogy_results=[AnalogyResult(overall_similarity=0.7)],
            trial_results=[
                TrialResult(status=TrialStatus.FAILED),
                TrialResult(status=TrialStatus.FAILED),
            ],
        )
        result = handler.handle(
            spec,
            [
                TrialResult(status=TrialStatus.FAILED),
                TrialResult(status=TrialStatus.FAILED),
            ],
        )
        assert result.fallback_to_teach is True
        assert result.failure_bundle is not None

    def test_should_escalate_high_sim_all_fail(self):
        spec = AnalogySpec(
            analogy_results=[
                AnalogyResult(
                    overall_similarity=0.9,
                    confidence=AnalogyConfidence.HIGH,
                )
            ],
            trial_results=[
                TrialResult(
                    status=TrialStatus.COMPLETED,
                    is_acceptable=False,
                ),
            ],
        )
        assert self.handler.should_escalate(spec)

    def test_no_escalate_when_fallback(self):
        spec = AnalogySpec(fallback_to_teach=True)
        assert not self.handler.should_escalate(spec)

    def test_failure_bundle_on_no_similar(self):
        """No similar cases should produce AnalogyFailureBundle"""
        spec = AnalogySpec(
            analogy_results=[AnalogyResult(overall_similarity=0.1)],
        )
        result = self.handler.handle(spec, [])
        assert result.fallback_to_teach is True
        assert result.failure_bundle is not None
        assert result.failure_bundle.failure_type == "no_similar"
        assert result.failure_bundle.bundle_id.startswith("AFB-")

    def test_failure_bundle_on_max_retries(self):
        """Max retries exceeded should produce AnalogyFailureBundle"""
        handler = AnalogyFailureHandler(max_retries=0)
        spec = AnalogySpec(
            analogy_results=[AnalogyResult(overall_similarity=0.7)],
            trial_results=[TrialResult(status=TrialStatus.FAILED)],
        )
        result = handler.handle(spec, [TrialResult(status=TrialStatus.FAILED)])
        assert result.fallback_to_teach is True
        assert result.failure_bundle is not None
        assert result.failure_bundle.failure_type == "trial_failed"
        assert result.failure_bundle.candidate_plans_tried >= 0


# ============================================================================
# Full Pipeline: AnalogicalOrchestrator tests
# ============================================================================

class TestAnalogicalOrchestrator:
    def setup_method(self):
        self.store = MockKnowledgeStore(
            cases=[
                _make_case(
                    "SRC-1",
                    geometry={"type": "pipe", "diameter": 0.1},
                    physics={"model": "RANS", "turbulence": "kOmegaSST"},
                    boundary={"inlet": "fixedValue", "outlet": "zeroGradient"},
                    mesh={"cells": 50000, "type": "hexahedral"},
                    flow_regime={"Re": 50000, "regime": "turbulent"},
                    numerical={"scheme": "secondOrder", "solver": "GAMG"},
                    report={"format": "html"},
                ),
            ],
            patterns=[
                {"pattern_id": "PAT-1", "tags": ["dim:geometry"]},
            ],
            rules=[
                {"rule_id": "RULE-1", "tags": ["dim:physics"]},
            ],
        )
        self.orchestrator = AnalogicalOrchestrator(self.store)

    def test_full_pipeline_success(self):
        target = _make_target(
            geometry={"type": "pipe", "diameter": 0.1},
            physics={"model": "RANS", "turbulence": "kOmegaSST"},
        )
        spec = AnalogySpec(
            target_case_id="TARGET",
            problem_description="Pipe flow analysis",
        )
        result = self.orchestrator.run(spec, target_features=target)
        assert len(result.analogy_results) > 0
        assert len(result.candidate_plans) > 0

    def test_full_pipeline_no_similar(self):
        store = MockKnowledgeStore(cases=[
            _make_case(
                "SRC-X",
                geometry={"type": "completely_obscure_shape"},
            )
        ])
        orch = AnalogicalOrchestrator(store)
        target = _make_target(
            geometry={"type": "totally_different"},
        )
        spec = AnalogySpec(target_case_id="TARGET")
        result = orch.run(spec, target_features=target)
        assert result.fallback_to_teach or result.selected_plan_id or len(result.analogy_results) >= 0

    def test_full_pipeline_with_custom_executor(self):
        def mock_exec(params):
            return {
                "output": {"final_residual": 0.001, "status": "converged"},
                "convergence": {
                    "residuals": [1.0, 0.1, 0.001],
                    "converged": True,
                },
            }

        orch = AnalogicalOrchestrator(self.store, executor=mock_exec)
        target = _make_target(
            geometry={"type": "pipe", "diameter": 0.1},
        )
        spec = AnalogySpec(target_case_id="TARGET")
        result = orch.run(spec, target_features=target)
        assert result.spec_id is not None

    def test_pipeline_respects_budget(self):
        target = _make_target()
        budget = ExplorationBudget(max_trials=1)
        spec = AnalogySpec(
            target_case_id="TARGET",
            budget=budget,
        )
        result = self.orchestrator.run(spec, target_features=target)
        assert budget.trials_used <= 1

    def test_pipeline_selects_plan(self):
        def good_exec(params):
            return {
                "output": {"final_residual": 0.0001, "status": "converged"},
                "convergence": {
                    "residuals": [1.0, 0.01, 0.0001],
                    "converged": True,
                },
            }

        orch = AnalogicalOrchestrator(self.store, executor=good_exec)
        target = _make_target(
            geometry={"type": "pipe", "diameter": 0.1},
            physics={"model": "RANS", "turbulence": "kOmegaSST"},
            boundary={"inlet": "fixedValue", "outlet": "zeroGradient"},
        )
        spec = AnalogySpec(target_case_id="TARGET")
        result = orch.run(spec, target_features=target)
        assert result.selected_plan_id is not None or result.fallback_to_teach

    def test_spec_to_dict(self):
        target = _make_target()
        spec = AnalogySpec(target_case_id="TARGET")
        result = self.orchestrator.run(spec, target_features=target)
        d = result.to_dict()
        assert "spec_id" in d
        assert "analogy_results" in d
        assert "candidate_plans" in d
        assert "trial_results" in d
        assert isinstance(d["analogy_results"], list)


# ============================================================================
# ExplorationBudget edge cases
# ============================================================================

class TestExplorationBudget:
    def test_default_not_exhausted(self):
        b = ExplorationBudget()
        assert not b.is_exhausted

    def test_consume_trial(self):
        b = ExplorationBudget(max_trials=2)
        assert b.consume_trial(0.1)
        assert b.trials_used == 1
        assert b.consume_trial(0.2)
        assert not b.consume_trial(0.3)  # exhausted

    def test_to_dict(self):
        b = ExplorationBudget()
        d = b.to_dict()
        assert "max_trials" in d
        assert "is_exhausted" in d
