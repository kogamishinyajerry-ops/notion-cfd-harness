#!/usr/bin/env python3
"""
Tests for Phase 2d: Pipeline Assembly - E2E Pipeline Orchestrator
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge_compiler.phase2d.pipeline_orchestrator import (
    PipelineState,
    PipelineStage,
    PipelineConfig,
    StageResult,
    PipelineMonitor,
    StageExecutor,
    ReportSpecStageExecutor,
    PhysicsPlanningStageExecutor,
    ExecutionStageExecutor,
    CorrectionRecordingStageExecutor,
    PipelineOrchestrator,
    ExecutionFlowManager,
    ResultAggregator,
    create_default_config,
    execute_pipeline_simple,
    execute_batch_pipelines,
)


# ============================================================================
# Test PipelineConfig
# ============================================================================

class TestPipelineConfig:
    """测试 PipelineConfig"""

    def test_config_creation(self):
        """测试配置创建"""
        config = PipelineConfig(
            pipeline_id="PIPE-001",
            name="Test Pipeline",
            description="Test description",
        )

        assert config.pipeline_id == "PIPE-001"
        assert config.name == "Test Pipeline"
        assert config.description == "Test description"
        assert config.enabled_stages == []
        assert config.stage_timeout == 300.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.enable_gates is True
        assert config.gate_strictness == "medium"
        assert config.output_dir == "./pipeline_outputs"
        assert config.log_level == "info"
        assert config.version == "1.0"

    def test_config_with_stages(self):
        """测试带阶段的配置"""
        config = PipelineConfig(
            pipeline_id="PIPE-002",
            name="Test Pipeline 2",
            description="Test description 2",
            enabled_stages=[
                PipelineStage.REPORT_SPEC_GENERATION,
                PipelineStage.PHYSICS_PLANNING,
            ],
        )

        assert len(config.enabled_stages) == 2
        assert PipelineStage.REPORT_SPEC_GENERATION in config.enabled_stages
        assert PipelineStage.PHYSICS_PLANNING in config.enabled_stages

    def test_config_to_dict(self):
        """测试配置转换为字典"""
        config = PipelineConfig(
            pipeline_id="PIPE-003",
            name="Test Pipeline 3",
            description="Test description 3",
            enabled_stages=[PipelineStage.REPORT_SPEC_GENERATION],
            stage_timeout=600.0,
            max_retries=5,
        )

        config_dict = config.to_dict()

        assert config_dict["pipeline_id"] == "PIPE-003"
        assert config_dict["name"] == "Test Pipeline 3"
        assert config_dict["description"] == "Test description 3"
        assert config_dict["enabled_stages"] == ["report_spec_generation"]
        assert config_dict["stage_timeout"] == 600.0
        assert config_dict["max_retries"] == 5
        assert config_dict["retry_delay"] == 1.0
        assert config_dict["enable_gates"] is True
        assert config_dict["gate_strictness"] == "medium"
        assert config_dict["version"] == "1.0"


# ============================================================================
# Test StageResult
# ============================================================================

class TestStageResult:
    """测试 StageResult"""

    def test_result_creation(self):
        """测试结果创建"""
        result = StageResult(
            stage=PipelineStage.REPORT_SPEC_GENERATION,
            status="success",
        )

        assert result.stage == PipelineStage.REPORT_SPEC_GENERATION
        assert result.status == "success"
        assert result.start_time == 0.0
        assert result.end_time == 0.0
        assert result.duration == 0.0
        assert result.data == {}
        assert result.artifacts == []
        assert result.error_message == ""
        assert result.retry_count == 0
        assert result.gate_passed is True
        assert result.gate_violations == []

    def test_is_successful_property(self):
        """测试 is_successful 属性"""
        # 成功的情况
        result1 = StageResult(
            stage=PipelineStage.REPORT_SPEC_GENERATION,
            status="success",
            gate_passed=True,
        )
        assert result1.is_successful is True

        # 失败的情况 - status 不是 success
        result2 = StageResult(
            stage=PipelineStage.REPORT_SPEC_GENERATION,
            status="failed",
            gate_passed=True,
        )
        assert result2.is_successful is False

        # 失败的情况 - gate 未通过
        result3 = StageResult(
            stage=PipelineStage.REPORT_SPEC_GENERATION,
            status="success",
            gate_passed=False,
        )
        assert result3.is_successful is False

    def test_result_with_data(self):
        """测试带数据的结果"""
        result = StageResult(
            stage=PipelineStage.PHYSICS_PLANNING,
            status="success",
            start_time=1000.0,
            end_time=1010.0,
            duration=10.0,
            data={"plan_id": "PLAN-001"},
            artifacts=["plan.json"],
        )

        assert result.stage == PipelineStage.PHYSICS_PLANNING
        assert result.data["plan_id"] == "PLAN-001"
        assert result.artifacts == ["plan.json"]
        assert result.duration == 10.0

    def test_result_with_errors(self):
        """测试带错误的结果"""
        result = StageResult(
            stage=PipelineStage.EXECUTION,
            status="failed",
            error_message="Solver failed to converge",
            retry_count=3,
            gate_passed=False,
            gate_violations=["Convergence criteria not met"],
        )

        assert result.status == "failed"
        assert result.error_message == "Solver failed to converge"
        assert result.retry_count == 3
        assert result.gate_passed is False
        assert result.gate_violations == ["Convergence criteria not met"]


# ============================================================================
# Test PipelineMonitor
# ============================================================================

class TestPipelineMonitor:
    """测试 PipelineMonitor"""

    def test_monitor_creation(self):
        """测试监控器创建"""
        monitor = PipelineMonitor()

        assert monitor.events == []
        assert monitor.start_time == 0.0
        assert monitor.end_time == 0.0

    def test_monitor_start_stop(self):
        """测试启动和停止"""
        monitor = PipelineMonitor()
        monitor.start("PIPE-001")

        assert monitor.start_time > 0
        assert len(monitor.events) == 1
        assert monitor.events[0]["type"] == "pipeline_started"
        assert monitor.events[0]["data"]["pipeline_id"] == "PIPE-001"

        time.sleep(0.01)
        monitor.stop()

        assert monitor.end_time > 0
        assert len(monitor.events) == 2
        assert monitor.events[1]["type"] == "pipeline_stopped"
        assert monitor.events[1]["data"]["duration"] > 0

    def test_add_event(self):
        """测试添加事件"""
        monitor = PipelineMonitor()
        monitor.add_event("custom_event", {"key": "value"})

        assert len(monitor.events) == 1
        assert monitor.events[0]["type"] == "custom_event"
        assert monitor.events[0]["data"]["key"] == "value"
        assert "timestamp" in monitor.events[0]

    def test_get_events_by_type(self):
        """测试按类型获取事件"""
        monitor = PipelineMonitor()
        monitor.add_event("stage_started", {"stage": "report_spec_generation"})
        monitor.add_event("stage_completed", {"stage": "report_spec_generation"})
        monitor.add_event("stage_started", {"stage": "physics_planning"})

        started_events = monitor.get_events_by_type("stage_started")
        assert len(started_events) == 2

        completed_events = monitor.get_events_by_type("stage_completed")
        assert len(completed_events) == 1

    def test_get_summary(self):
        """测试获取摘要"""
        monitor = PipelineMonitor()
        monitor.start("PIPE-001")

        # 添加一些阶段完成事件
        monitor.add_event("stage_completed", {
            "stage": "report_spec_generation",
            "status": "success",
        })
        monitor.add_event("stage_completed", {
            "stage": "physics_planning",
            "status": "success",
        })
        monitor.add_event("stage_completed", {
            "stage": "execution",
            "status": "failed",
        })

        monitor.stop()

        summary = monitor.get_summary()

        assert "duration" in summary
        assert summary["duration"] > 0
        assert summary["total_events"] == 5  # 1 start + 3 completed + 1 stop
        assert "stage_stats" in summary
        assert "report_spec_generation" in summary["stage_stats"]
        assert summary["stage_stats"]["report_spec_generation"]["count"] == 1
        assert summary["stage_stats"]["report_spec_generation"]["success"] == 1


# ============================================================================
# Test Stage Executors
# ============================================================================

class TestStageExecutors:
    """测试阶段执行器"""

    def test_report_spec_executor_success(self):
        """测试 ReportSpec 执行器成功"""
        executor = ReportSpecStageExecutor()
        context = {"problem_type": "external_flow"}
        config = create_default_config("PIPE-001", "Test")

        result = executor.execute(context, config)

        assert result.stage == PipelineStage.REPORT_SPEC_GENERATION
        assert result.status == "success"
        assert result.duration >= 0
        assert "report_spec_id" in result.data
        assert len(result.artifacts) > 0

    def test_physics_planning_executor_success(self):
        """测试 Physics 规划执行器成功"""
        executor = PhysicsPlanningStageExecutor()
        context = {
            "problem_description": "turbulent flow over airfoil at Re=500000",
            "physics_models": ["RANS", "k-epsilon"],
            "boundary_conditions": {"inlet": "velocity"},
        }
        config = create_default_config("PIPE-001", "Test")

        result = executor.execute(context, config)

        assert result.stage == PipelineStage.PHYSICS_PLANNING
        assert result.status == "success"
        assert result.duration >= 0
        assert "plan_id" in result.data
        assert len(result.artifacts) > 0

    def test_execution_executor_success(self):
        """测试执行执行器成功（mock 模式无 case 目录）"""
        executor = ExecutionStageExecutor()
        context = {}
        config = create_default_config("PIPE-001", "Test")

        result = executor.execute(context, config)

        assert result.stage == PipelineStage.EXECUTION
        assert result.status == "success"
        assert result.duration >= 0
        assert "execution_id" in result.data
        assert result.data["solver_status"] == "completed"

    def test_correction_recording_executor_success(self):
        """测试修正记录执行器成功"""
        from knowledge_compiler.phase2c.correction_recorder import CorrectionRecorder

        recorder = CorrectionRecorder()
        executor = CorrectionRecordingStageExecutor(recorder)
        context = {"validation_result": {"passed": False}}
        config = create_default_config("PIPE-001", "Test")

        result = executor.execute(context, config)

        assert result.stage == PipelineStage.CORRECTION_RECORDING
        assert result.status == "success"
        assert result.duration >= 0
        assert "correction_records_created" in result.data


# ============================================================================
# Test PipelineOrchestrator
# ============================================================================

class TestPipelineOrchestrator:
    """测试流程编排器"""

    def test_orchestrator_creation(self):
        """测试编排器创建"""
        config = create_default_config("PIPE-001", "Test Pipeline")
        orchestrator = PipelineOrchestrator(config)

        assert orchestrator.config == config
        assert orchestrator.state == PipelineState.IDLE
        assert len(orchestrator.stage_results) == 0
        assert len(orchestrator.executors) > 0  # Should have default executors

    def test_register_executor(self):
        """测试注册执行器"""
        config = create_default_config("PIPE-001", "Test Pipeline")
        orchestrator = PipelineOrchestrator(config)

        custom_executor = MagicMock(spec=StageExecutor)
        orchestrator.register_executor(
            PipelineStage.POSTPROCESSING,
            custom_executor
        )

        assert PipelineStage.POSTPROCESSING in orchestrator.executors
        assert orchestrator.executors[PipelineStage.POSTPROCESSING] == custom_executor

    def test_execute_simple_pipeline(self):
        """测试执行简单流程"""
        config = create_default_config("PIPE-001", "Test Pipeline")
        orchestrator = PipelineOrchestrator(config)

        input_data = {
            "problem_type": "fluid_flow",
            "physics_models": ["RANS"],
        }

        results = orchestrator.execute(input_data)

        assert orchestrator.state == PipelineState.COMPLETED
        assert "pipeline_id" in results
        assert "stage_results" in results
        assert "monitoring" in results

    def test_execute_with_specific_stages(self):
        """测试执行指定阶段"""
        config = PipelineConfig(
            pipeline_id="PIPE-002",
            name="Test Pipeline 2",
            description="Test",
            enabled_stages=[
                PipelineStage.REPORT_SPEC_GENERATION,
                PipelineStage.PHYSICS_PLANNING,
            ],
        )
        orchestrator = PipelineOrchestrator(config)

        input_data = {"problem_type": "fluid_flow"}
        results = orchestrator.execute(
            input_data,
            stages=[PipelineStage.REPORT_SPEC_GENERATION],
        )

        # 只应该执行一个阶段
        assert len(orchestrator.stage_results) == 1
        assert PipelineStage.REPORT_SPEC_GENERATION in orchestrator.stage_results

    def test_execute_with_retry(self):
        """测试带重试的执行"""
        config = PipelineConfig(
            pipeline_id="PIPE-003",
            name="Test Pipeline 3",
            description="Test",
            max_retries=2,
            retry_delay=0.01,  # Short delay for testing
        )
        orchestrator = PipelineOrchestrator(config)

        # 创建一个会失败然后成功的执行器
        class FailingThenSuccessExecutor(StageExecutor):
            def __init__(self):
                self.attempt = 0

            def execute(self, context, config):
                self.attempt += 1
                if self.attempt < 3:
                    result = StageResult(
                        stage=PipelineStage.REPORT_SPEC_GENERATION,
                        status="failed",
                        error_message=f"Attempt {self.attempt} failed",
                    )
                else:
                    result = StageResult(
                        stage=PipelineStage.REPORT_SPEC_GENERATION,
                        status="success",
                    )
                return result

        orchestrator.register_executor(
            PipelineStage.REPORT_SPEC_GENERATION,
            FailingThenSuccessExecutor()
        )

        input_data = {}
        results = orchestrator.execute(
            input_data,
            stages=[PipelineStage.REPORT_SPEC_GENERATION],
        )

        # 应该在第3次尝试时成功
        result = orchestrator.stage_results[PipelineStage.REPORT_SPEC_GENERATION]
        assert result.status == "success"
        assert result.retry_count == 2

    def test_save_results(self):
        """测试保存结果"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PipelineConfig(
                pipeline_id="PIPE-004",
                name="Test Pipeline 4",
                description="Test",
                output_dir=temp_dir,
            )
            orchestrator = PipelineOrchestrator(config)

            input_data = {"problem_type": "fluid_flow"}
            orchestrator.execute(input_data)

            output_path = orchestrator.save_results()

            assert Path(output_path).exists()

            with open(output_path, "r") as f:
                saved_results = json.load(f)

            assert saved_results["pipeline_id"] == "PIPE-004"
            assert "stage_results" in saved_results


# ============================================================================
# Test ExecutionFlowManager
# ============================================================================

class TestExecutionFlowManager:
    """测试执行流程管理器"""

    def test_flow_manager_creation(self):
        """测试流程管理器创建"""
        config = create_default_config("PIPE-001", "Test Pipeline")
        orchestrator = PipelineOrchestrator(config)
        manager = ExecutionFlowManager(orchestrator)

        assert manager.orchestrator == orchestrator
        assert manager.flow_history == []

    def test_execute_flow(self):
        """测试执行流程"""
        config = create_default_config("PIPE-001", "Test Pipeline")
        orchestrator = PipelineOrchestrator(config)
        manager = ExecutionFlowManager(orchestrator)

        input_data = {"problem_type": "fluid_flow"}
        stages = [PipelineStage.REPORT_SPEC_GENERATION]

        result = manager.execute_flow(
            "test_flow",
            input_data,
            stages,
        )

        assert "flow_id" in result
        assert result["flow_name"] == "test_flow"
        assert "results" in result
        assert len(manager.flow_history) == 1

    def test_get_flow_history(self):
        """测试获取流程历史"""
        config = create_default_config("PIPE-001", "Test Pipeline")
        orchestrator = PipelineOrchestrator(config)
        manager = ExecutionFlowManager(orchestrator)

        input_data = {"problem_type": "fluid_flow"}
        stages = [PipelineStage.REPORT_SPEC_GENERATION]

        manager.execute_flow("flow1", input_data, stages)
        manager.execute_flow("flow2", input_data, stages)

        history = manager.get_flow_history()

        assert len(history) == 2
        assert history[0]["flow_name"] == "flow1"
        assert history[1]["flow_name"] == "flow2"


# ============================================================================
# Test ResultAggregator
# ============================================================================

class TestResultAggregator:
    """测试结果聚合器"""

    def test_aggregator_creation(self):
        """测试聚合器创建"""
        aggregator = ResultAggregator()

        assert aggregator.aggregation_rules == []

    def test_add_aggregation_rule(self):
        """测试添加聚合规则"""
        aggregator = ResultAggregator()

        def custom_rule(results):
            return {"custom_metric": 42}

        aggregator.add_aggregation_rule(custom_rule)

        assert len(aggregator.aggregation_rules) == 1

    def test_aggregate_results(self):
        """测试聚合结果"""
        aggregator = ResultAggregator()

        # 创建一些模拟结果
        results = [
            {
                "state": PipelineState.COMPLETED.value,
                "stage_results": {
                    "report_spec_generation": {"gate_passed": True},
                    "physics_planning": {"gate_passed": True},
                },
            },
            {
                "state": PipelineState.COMPLETED.value,
                "stage_results": {
                    "report_spec_generation": {"gate_passed": True},
                    "physics_planning": {"gate_passed": False},
                },
            },
            {
                "state": PipelineState.FAILED.value,
                "stage_results": {
                    "report_spec_generation": {"gate_passed": False},
                },
            },
        ]

        aggregated = aggregator.aggregate(results)

        assert aggregated["total_pipelines"] == 3
        assert aggregated["successful_pipelines"] == 2
        assert aggregated["failed_pipelines"] == 1
        assert "stage_success_rates" in aggregated

        # 检查成功率计算
        assert "report_spec_generation" in aggregated["stage_success_rates"]
        assert aggregated["stage_success_rates"]["report_spec_generation"] == 2/3

    def test_aggregate_with_custom_rule(self):
        """测试带自定义规则的聚合"""
        aggregator = ResultAggregator()

        def custom_success_rate(results):
            return {"custom_success_rate": 0.95}

        aggregator.add_aggregation_rule(custom_success_rate)

        results = [
            {
                "state": PipelineState.COMPLETED.value,
                "stage_results": {},
            },
        ]

        aggregated = aggregator.aggregate(results)

        assert "custom_success_rate" in aggregated
        assert aggregated["custom_success_rate"] == 0.95


# ============================================================================
# Test Convenience Functions
# ============================================================================

class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_create_default_config(self):
        """测试创建默认配置"""
        config = create_default_config(
            "PIPE-001",
            "Test Pipeline",
            description="Test description",
            output_dir="/tmp/outputs",
        )

        assert config.pipeline_id == "PIPE-001"
        assert config.name == "Test Pipeline"
        assert config.description == "Test description"
        assert config.output_dir == "/tmp/outputs"
        assert len(config.enabled_stages) == 4  # Default stages

    def test_execute_pipeline_simple(self):
        """测试简单执行流程"""
        input_data = {
            "problem_type": "fluid_flow",
            "physics_models": ["RANS"],
        }

        results = execute_pipeline_simple(
            input_data,
            pipeline_id="PIPE-002",
            pipeline_name="Simple Test Pipeline",
        )

        assert "pipeline_id" in results
        assert results["pipeline_id"] == "PIPE-002"
        assert "stage_results" in results

    def test_execute_batch_pipelines(self):
        """测试批量执行流程"""
        config = create_default_config("PIPE-BATCH", "Batch Pipeline")

        input_data_list = [
            {"problem_type": "fluid_flow", "case_id": "case1"},
            {"problem_type": "heat_transfer", "case_id": "case2"},
        ]

        results = execute_batch_pipelines(input_data_list, config)

        assert len(results) == 2
        assert all("pipeline_id" in r for r in results)


# ============================================================================
# Test Integration
# ============================================================================

class TestIntegration:
    """集成测试"""

    def test_full_pipeline_workflow(self):
        """测试完整流程工作流"""
        # 创建配置
        config = create_default_config(
            "PIPE-FULL-001",
            "Full Integration Test",
            description="Complete pipeline integration test",
        )

        # 创建编排器
        orchestrator = PipelineOrchestrator(config)

        # 准备输入数据
        input_data = {
            "problem_type": "fluid_flow",
            "physics_models": ["RANS", "k-epsilon"],
            "boundary_conditions": {
                "inlet": {"velocity": 10.0},
                "outlet": {"pressure": 0.0},
            },
        }

        # 执行流程
        results = orchestrator.execute(input_data)

        # 验证结果
        assert orchestrator.state == PipelineState.COMPLETED
        assert results["pipeline_id"] == "PIPE-FULL-001"
        assert "stage_results" in results
        assert "monitoring" in results

        # 验证监控
        monitoring = results["monitoring"]
        assert monitoring["total_events"] > 0
        assert monitoring["duration"] > 0

    def test_pipeline_with_failure_recovery(self):
        """测试带失败恢复的流程"""
        config = PipelineConfig(
            pipeline_id="PIPE-RECOVERY-001",
            name="Recovery Test Pipeline",
            description="Test failure recovery",
            max_retries=2,
            retry_delay=0.01,
        )

        orchestrator = PipelineOrchestrator(config)

        # 创建一个先失败后成功的执行器
        class RecoveryExecutor(StageExecutor):
            def __init__(self):
                self.call_count = 0

            def execute(self, context, config):
                self.call_count += 1
                if self.call_count == 1:
                    return StageResult(
                        stage=PipelineStage.REPORT_SPEC_GENERATION,
                        status="failed",
                        error_message="First attempt failed",
                    )
                else:
                    return StageResult(
                        stage=PipelineStage.REPORT_SPEC_GENERATION,
                        status="success",
                        data={"recovered": True},
                    )

        recovery_executor = RecoveryExecutor()
        orchestrator.register_executor(
            PipelineStage.REPORT_SPEC_GENERATION,
            recovery_executor
        )

        input_data = {"test": True}
        results = orchestrator.execute(
            input_data,
            stages=[PipelineStage.REPORT_SPEC_GENERATION],
        )

        # 应该在重试后恢复
        assert orchestrator.state == PipelineState.COMPLETED
        assert recovery_executor.call_count == 2  # 第一次失败，第二次成功

    def test_result_aggregation_integration(self):
        """测试结果聚合集成"""
        aggregator = ResultAggregator()

        # 执行多个流程
        config = create_default_config("PIPE-AGG", "Aggregation Test")
        input_data_list = [
            {"case_id": f"case{i}", "problem_type": "fluid_flow"}
            for i in range(5)
        ]

        results = execute_batch_pipelines(input_data_list, config)

        # 聚合结果
        aggregated = aggregator.aggregate(results)

        assert aggregated["total_pipelines"] == 5
        assert "stage_success_rates" in aggregated
        assert aggregated["successful_pipelines"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
