#!/usr/bin/env python3
"""
Phase 2.5: E2E Pipeline Integration Validation

完整端到端流程验证测试，模拟真实 CFD 工作流：
ReportSpec → Physics Planning → Execution → Validation →
Correction Recording → Benchmark Replay → Knowledge Extraction
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from knowledge_compiler.phase1.schema import (
    KnowledgeLayer,
    KnowledgeStatus,
    ProblemType,
    ErrorType,
    ImpactScope,
)
from knowledge_compiler.phase2c.correction_recorder import (
    CorrectionRecorder,
    CorrectionRecord,
    CorrectionSeverity,
    ReplayStatus,
)
from knowledge_compiler.phase2c.benchmark_replay import (
    BenchmarkCase,
    BenchmarkReplayEngine,
    BenchmarkReplayResult,
    BenchmarkSuite,
)
from knowledge_compiler.phase2c.knowledge_compiler import (
    KnowledgeManager,
    PatternKnowledge,
    RuleKnowledge,
    KnowledgeValidator,
)
from knowledge_compiler.phase2d.pipeline_orchestrator import (
    PipelineOrchestrator,
    PipelineConfig,
    PipelineStage,
    PipelineState,
    StageExecutor,
    StageResult,
    PipelineMonitor,
    ExecutionFlowManager,
    ResultAggregator,
    create_default_config,
)


# ============================================================================
# Custom Stage Executors for E2E Test
# ============================================================================

class BenchmarkReplayStageExecutor(StageExecutor):
    """Benchmark Replay 阶段执行器"""

    def __init__(self, engine: BenchmarkReplayEngine, suite: BenchmarkSuite):
        self.engine = engine
        self.suite = suite

    def execute(self, context, config):
        start_time = time.time()
        result = StageResult(
            stage=PipelineStage.BENCHMARK_REPLAY,
            status="success",
            start_time=start_time,
        )

        try:
            correction_data = context.get("correction_data")
            if correction_data:
                case_id = context.get("benchmark_case_id", "BENCH-001")
                case = self.suite.get_case(case_id)
                if case:
                    replay_result = self.engine.replay_correction(
                        correction_data, case_id, simulate_execution=True
                    )
                    result.data = {
                        "replay_passed": replay_result.passed,
                        "benchmark_case_id": case_id,
                    }
                else:
                    result.data = {"replay_passed": None, "reason": "No benchmark case"}

            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        except Exception as e:
            result.status = "failed"
            result.error_message = str(e)
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        return result


class KnowledgeExtractionStageExecutor(StageExecutor):
    """知识提取阶段执行器"""

    def __init__(self, knowledge_manager: KnowledgeManager):
        self.manager = knowledge_manager

    def execute(self, context, config):
        start_time = time.time()
        result = StageResult(
            stage=PipelineStage.KNOWLEDGE_EXTRACTION,
            status="success",
            start_time=start_time,
        )

        try:
            correction_data = context.get("correction_data")
            if correction_data:
                patterns = self.manager.extract_knowledge(correction_data)
                result.data = {
                    "patterns_extracted": len(patterns),
                    "pattern_ids": [p.knowledge_id for p in patterns],
                }
            else:
                result.data = {"patterns_extracted": 0}

            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        except Exception as e:
            result.status = "failed"
            result.error_message = str(e)
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        return result


# ============================================================================
# E2E Integration Tests
# ============================================================================

class TestE2EPipelineIntegration:
    """端到端流程集成测试"""

    def test_full_pipeline_with_correction_flow(self):
        """测试完整流程：正常执行 → 验证失败 → 修正 → 回放 → 知识提取"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Step 1: 创建 Pipeline 配置
            config = PipelineConfig(
                pipeline_id="E2E-001",
                name="Full E2E Pipeline Test",
                description="Complete pipeline with correction and learning",
                enabled_stages=[
                    PipelineStage.REPORT_SPEC_GENERATION,
                    PipelineStage.PHYSICS_PLANNING,
                    PipelineStage.EXECUTION,
                    PipelineStage.CORRECTION_RECORDING,
                    PipelineStage.BENCHMARK_REPLAY,
                    PipelineStage.KNOWLEDGE_EXTRACTION,
                ],
                max_retries=2,
                retry_delay=0.01,
                output_dir=temp_dir,
            )

            # Step 2: 创建编排器
            orchestrator = PipelineOrchestrator(config)

            # Step 3: 注册 Phase 2c 的执行器
            # Benchmark Suite
            benchmark_case = BenchmarkCase(
                case_id="BENCH-001",
                name="Lid-Driven Cavity",
                description="Standard lid-driven cavity benchmark",
                category="validation",
                difficulty="medium",
                input_data={
                    "mesh_type": "structured",
                    "reynolds_number": 100,
                },
                expected_output={
                    "converged": True,
                    "residual": 1e-5,
                },
            )
            suite = BenchmarkSuite(storage_path=str(Path(temp_dir) / "benchmarks"))
            suite.add_case(benchmark_case)

            replay_engine = BenchmarkReplayEngine()
            knowledge_manager = KnowledgeManager(
                storage_path=str(Path(temp_dir) / "knowledge"),
                validator=KnowledgeValidator(
                    min_confidence=0.0,
                    min_evidence=0,
                    min_success_rate=0.0,
                ),
            )

            orchestrator.register_executor(
                PipelineStage.BENCHMARK_REPLAY,
                BenchmarkReplayStageExecutor(replay_engine, suite),
            )
            orchestrator.register_executor(
                PipelineStage.KNOWLEDGE_EXTRACTION,
                KnowledgeExtractionStageExecutor(knowledge_manager),
            )

            # Step 4: 执行 Pipeline
            input_data = {
                "problem_type": "internal_flow",
                "physics_models": ["RANS", "k-epsilon"],
                "boundary_conditions": {
                    "inlet": {"velocity": 1.0},
                    "outlet": {"pressure": 0.0},
                    "walls": {"no_slip": True},
                },
                "correction_data": {
                    "wrong_output": {
                        "converged": True,
                        "residual": 1e-3,
                    },
                    "correct_output": {
                        "converged": True,
                        "residual": 1e-5,
                    },
                    "error_type": ErrorType.INCORRECT_DATA.value if hasattr(ErrorType, 'INCORRECT_DATA') else "incorrect_data",
                    "root_cause": "边界条件设置不正确，inlet速度偏大导致收敛困难需要降低松弛因子",
                    "fix_action": "修正入口速度为1.0 m/s并降低松弛因子至0.3加速收敛",
                    "impact_scope": "single_case",
                    "needs_replay": True,
                },
                "benchmark_case_id": "BENCH-001",
            }

            results = orchestrator.execute(input_data)

            # Step 5: 验证结果
            assert orchestrator.state == PipelineState.COMPLETED
            assert results["pipeline_id"] == "E2E-001"

            # 验证所有阶段都执行了
            assert PipelineStage.REPORT_SPEC_GENERATION in orchestrator.stage_results
            assert PipelineStage.PHYSICS_PLANNING in orchestrator.stage_results
            assert PipelineStage.EXECUTION in orchestrator.stage_results
            assert PipelineStage.CORRECTION_RECORDING in orchestrator.stage_results
            assert PipelineStage.BENCHMARK_REPLAY in orchestrator.stage_results
            assert PipelineStage.KNOWLEDGE_EXTRACTION in orchestrator.stage_results

            # 验证监控数据
            monitoring = results["monitoring"]
            assert monitoring["total_events"] > 0
            assert monitoring["duration"] > 0

            # Step 6: 保存结果
            output_path = orchestrator.save_results()
            assert Path(output_path).exists()

            with open(output_path, "r") as f:
                saved = json.load(f)
            assert saved["pipeline_id"] == "E2E-001"

    def test_pipeline_with_stage_context_propagation(self):
        """测试阶段间上下文传播"""
        config = create_default_config("E2E-002", "Context Propagation Test")
        orchestrator = PipelineOrchestrator(config)

        input_data = {
            "problem_type": "external_flow",
            "physics_models": ["RANS"],
        }

        results = orchestrator.execute(input_data)

        # 验证阶段间上下文正确传播
        assert "report_spec_generation_result" in input_data
        assert "physics_planning_result" in input_data
        assert "execution_result" in input_data

        # 验证特定上下文字段
        assert "report_spec_id" in input_data
        assert "plan_id" in input_data
        assert "execution_id" in input_data

    def test_pipeline_failure_stops_at_critical_stage(self):
        """测试关键阶段失败时停止流程"""
        config = PipelineConfig(
            pipeline_id="E2E-003",
            name="Critical Failure Test",
            description="Test critical stage failure",
            max_retries=1,
            retry_delay=0.01,
        )
        orchestrator = PipelineOrchestrator(config)

        # 创建一个始终失败的执行器
        class AlwaysFailExecutor(StageExecutor):
            def execute(self, context, config):
                return StageResult(
                    stage=PipelineStage.REPORT_SPEC_GENERATION,
                    status="failed",
                    error_message="Critical failure",
                )

        orchestrator.register_executor(
            PipelineStage.REPORT_SPEC_GENERATION,
            AlwaysFailExecutor()
        )

        input_data = {"problem_type": "test"}
        results = orchestrator.execute(input_data)

        # 关键阶段失败应该停止流程
        assert PipelineStage.REPORT_SPEC_GENERATION in orchestrator.stage_results
        stage_result = orchestrator.stage_results[PipelineStage.REPORT_SPEC_GENERATION]
        assert stage_result.status == "failed"

        # 不应该有后续阶段的结果
        assert PipelineStage.PHYSICS_PLANNING not in orchestrator.stage_results
        assert PipelineStage.EXECUTION not in orchestrator.stage_results

    def test_pipeline_non_critical_failure_continues(self):
        """测试非关键阶段失败时继续流程"""
        config = PipelineConfig(
            pipeline_id="E2E-004",
            name="Non-Critical Failure Test",
            description="Test non-critical stage failure",
            max_retries=1,
            retry_delay=0.01,
            enable_gates=False,  # Disable gates for this test
        )
        orchestrator = PipelineOrchestrator(config)

        # 创建一个始终失败的执行器（CorrectionRecording 是非关键阶段）
        class FailCorrectionExecutor(StageExecutor):
            def execute(self, context, config):
                return StageResult(
                    stage=PipelineStage.CORRECTION_RECORDING,
                    status="failed",
                    error_message="Non-critical failure",
                )

        orchestrator.register_executor(
            PipelineStage.CORRECTION_RECORDING,
            FailCorrectionExecutor()
        )

        input_data = {"problem_type": "test"}
        orchestrator.execute(
            input_data,
            stages=[
                PipelineStage.REPORT_SPEC_GENERATION,
                PipelineStage.CORRECTION_RECORDING,
            ],
        )

        # 关键阶段应该成功
        assert PipelineStage.REPORT_SPEC_GENERATION in orchestrator.stage_results
        rspec_result = orchestrator.stage_results[PipelineStage.REPORT_SPEC_GENERATION]
        assert rspec_result.status == "success"

        # 非关键阶段失败但流程继续
        assert PipelineStage.CORRECTION_RECORDING in orchestrator.stage_results
        corr_result = orchestrator.stage_results[PipelineStage.CORRECTION_RECORDING]
        assert corr_result.status == "failed"

    def test_batch_pipeline_execution(self):
        """测试批量流程执行"""
        aggregator = ResultAggregator()
        config = create_default_config("E2E-BATCH", "Batch Test")

        cases = [
            {"problem_type": "internal_flow", "case_id": "case-1"},
            {"problem_type": "external_flow", "case_id": "case-2"},
            {"problem_type": "heat_transfer", "case_id": "case-3"},
        ]

        results = []
        for case in cases:
            orch = PipelineOrchestrator(config)
            result = orch.execute(case)
            results.append(result)

        aggregated = aggregator.aggregate(results)

        assert aggregated["total_pipelines"] == 3
        assert aggregated["successful_pipelines"] == 3
        assert aggregated["failed_pipelines"] == 0
        assert len(aggregated["stage_success_rates"]) > 0


class TestE2EGovernanceFlow:
    """端到端治理流程测试"""

    def test_correction_to_knowledge_lifecycle(self):
        """测试完整的修正 → 知识生命周期"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Step 1: 创建 Correction Record
            recorder = CorrectionRecorder(
                storage_path=str(Path(temp_dir) / "corrections")
            )

            record = CorrectionRecord(
                record_id="REC-E2E-001",
                created_at=time.time(),
                source_case_id="CASE-001",
                error_type=ErrorType.INCORRECT_DATA,
                impact_scope=ImpactScope.SINGLE_CASE,
                root_cause="边界条件设置不正确导致计算发散需要重新设置入口速度和湍流参数",
                fix_action="修正入口边界条件，设置正确的速度和湍流强度并降低松弛因子",
                human_reason="入口速度偏大导致发散",
                evidence=["残差曲线未下降", "收敛判定未通过"],
                severity=CorrectionSeverity.HIGH,
                needs_replay=True,
                wrong_output={"converged": False, "residual": 1e-2},
                correct_output={"converged": True, "residual": 1e-5},
            )

            # Step 2: 保存记录
            filepath = recorder.save(record)
            assert Path(filepath).exists()

            # Step 3: Benchmark Replay
            benchmark_case = BenchmarkCase(
                case_id="BENCH-LC-001",
                name="Lifecycle Benchmark",
                description="Test benchmark for lifecycle",
                category="validation",
                difficulty="easy",
                input_data={"mesh_type": "structured"},
                expected_output={"converged": True, "residual": 1e-5},
            )
            suite = BenchmarkSuite(storage_path="/nonexistent/path")
            suite.add_case(benchmark_case)

            engine = BenchmarkReplayEngine(benchmark_suite=suite)
            replay_result = engine.replay_correction(
                record, "BENCH-LC-001", simulate_execution=True
            )

            assert replay_result is not None
            assert replay_result.status in ("passed", "failed", "error")

            # Step 4: Knowledge Extraction
            validator = KnowledgeValidator(
                min_confidence=0.0,
                min_evidence=0,
                min_success_rate=0.0,
            )
            manager = KnowledgeManager(
                storage_path=str(Path(temp_dir) / "knowledge"),
                validator=validator,
            )

            patterns = manager.extract_knowledge(record)
            assert len(patterns) > 0

            # Step 5: Add and validate patterns
            for pattern in patterns:
                success, violations = manager.add_pattern(pattern)
                assert success

            # Step 6: Verify statistics
            stats = manager.get_statistics()
            assert stats["total_patterns"] > 0

    def test_correction_recorder_validation_pipeline(self):
        """测试修正记录验证流程"""
        recorder = CorrectionRecorder()

        # 有效记录
        valid_record = CorrectionRecord(
            record_id="REC-VALID-001",
            created_at=time.time(),
            source_case_id="CASE-VALID-001",
            error_type=ErrorType.MISSING_DATA,
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="缺少必要的入口边界条件参数",
            fix_action="添加入口速度和湍流参数",
            human_reason="缺少边界条件",
            evidence=["参数缺失"],
            severity=CorrectionSeverity.LOW,
            needs_replay=False,
            wrong_output={},
            correct_output={"velocity": 1.0},
        )

        violations = recorder.validate(valid_record)
        assert isinstance(violations, list)

    def test_benchmark_suite_lifecycle(self):
        """测试 Benchmark Suite 完整生命周期"""
        suite = BenchmarkSuite(storage_path="/nonexistent/path")

        # 添加案例
        cases = []
        for i in range(3):
            case = BenchmarkCase(
                case_id=f"BENCH-LC-{i:03d}",
                name=f"Benchmark Case {i}",
                description=f"Test case {i}",
                category="validation",
                difficulty="medium",
                input_data={"param": i},
                expected_output={"result": i * 2},
            )
            suite.add_case(case)
            cases.append(case)

        # 验证案例数量
        assert len(suite.cases) == 3

        # 列出案例
        all_cases = suite.list_cases()
        assert len(all_cases) == 3

        # 获取特定案例
        case = suite.get_case("BENCH-LC-001")
        assert case is not None
        assert case.name == "Benchmark Case 1"


class TestE2EMonitoringAndReporting:
    """端到端监控和报告测试"""

    def test_pipeline_monitor_event_tracking(self):
        """测试 Pipeline 监控事件跟踪"""
        monitor = PipelineMonitor()
        monitor.start("MON-001")

        # 模拟阶段事件
        for stage in [
            PipelineStage.REPORT_SPEC_GENERATION,
            PipelineStage.PHYSICS_PLANNING,
            PipelineStage.EXECUTION,
        ]:
            monitor.add_event("stage_started", {"stage": stage.value})
            monitor.add_event("stage_completed", {
                "stage": stage.value,
                "status": "success",
            })

        monitor.stop()

        # 验证事件序列
        started_events = monitor.get_events_by_type("stage_started")
        assert len(started_events) == 3

        completed_events = monitor.get_events_by_type("stage_completed")
        assert len(completed_events) == 3

        # 验证摘要
        summary = monitor.get_summary()
        assert summary["total_events"] == 8  # 1 start + 3 started + 3 completed + 1 stop
        assert summary["duration"] > 0

    def test_execution_flow_manager_tracking(self):
        """测试执行流程管理器跟踪"""
        config = create_default_config("FLOW-001", "Flow Tracking Test")
        orchestrator = PipelineOrchestrator(config)
        manager = ExecutionFlowManager(orchestrator)

        # 执行多个流程
        flows = ["analysis_flow", "validation_flow", "correction_flow"]
        for flow_name in flows:
            manager.execute_flow(
                flow_name,
                {"problem_type": "test"},
                [PipelineStage.REPORT_SPEC_GENERATION],
            )

        history = manager.get_flow_history()
        assert len(history) == 3

        for i, entry in enumerate(history):
            assert entry["flow_name"] == flows[i]
            assert "flow_id" in entry
            assert "stages" in entry

    def test_result_aggregator_statistics(self):
        """测试结果聚合器统计"""
        aggregator = ResultAggregator()

        # 添加自定义聚合规则
        def count_stages(results):
            total_stages = sum(
                len(r.get("stage_results", {})) for r in results
            )
            return {"total_stages_executed": total_stages}

        aggregator.add_aggregation_rule(count_stages)

        # 模拟多个流程结果
        results = []
        for i in range(5):
            config = create_default_config(f"AGG-{i:03d}", f"Agg Test {i}")
            orch = PipelineOrchestrator(config)
            result = orch.execute({"problem_type": "test"})
            results.append(result)

        aggregated = aggregator.aggregate(results)

        assert aggregated["total_pipelines"] == 5
        assert aggregated["successful_pipelines"] == 5
        assert "total_stages_executed" in aggregated
        assert aggregated["total_stages_executed"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
