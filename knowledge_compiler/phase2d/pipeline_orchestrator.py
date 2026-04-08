#!/usr/bin/env python3
"""
Phase 2d: Pipeline Assembly - E2E Pipeline Orchestrator

端到端流程编排器 - 协调 Phase 1 和 Phase 2 的所有组件，实现完整的
CFD 智能工作流自动化。

核心组件:
- PipelineOrchestrator: 主编排器，协调完整流程
- ExecutionFlowManager: 管理执行流程和状态转换
- ResultAggregator: 聚合多个组件的结果
- PipelineConfig: 流程配置管理
- PipelineMonitor: 监控流程执行和故障处理
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Callable

from knowledge_compiler.phase1.schema import (
    Phase1Output,
    ReportSpec,
    TeachRecord,
    KnowledgeLayer,
    KnowledgeStatus,
    ProblemType,
)
from knowledge_compiler.phase2c.correction_recorder import (
    CorrectionRecorder,
    CorrectionRecord,
)
from knowledge_compiler.phase2c.benchmark_replay import (
    BenchmarkReplayEngine,
    BenchmarkSuite,
)


# ============================================================================
# Pipeline State and Configuration
# ============================================================================

class PipelineState(Enum):
    """流程状态"""
    IDLE = "idle"
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(Enum):
    """流程阶段"""
    # Phase 1 Stages
    REPORT_SPEC_GENERATION = "report_spec_generation"
    TEACH_MODE = "teach_mode"
    REPLAY_VALIDATION = "replay_validation"

    # Phase 2 Stages
    PHYSICS_PLANNING = "physics_planning"
    EXECUTION = "execution"
    POSTPROCESSING = "postprocessing"
    VALIDATION = "validation"

    # Phase 2c Stages
    CORRECTION_RECORDING = "correction_recording"
    BENCHMARK_REPLAY = "benchmark_replay"
    KNOWLEDGE_EXTRACTION = "knowledge_extraction"


@dataclass
class PipelineConfig:
    """流程配置"""
    pipeline_id: str
    name: str
    description: str

    # Stage configuration
    enabled_stages: List[PipelineStage] = field(default_factory=list)
    stage_timeout: float = 300.0  # 5 minutes per stage

    # Retry configuration
    max_retries: int = 3
    retry_delay: float = 1.0

    # Quality Gates
    enable_gates: bool = True
    gate_strictness: str = "medium"  # "low", "medium", "high"

    # Output configuration
    output_dir: str = "./pipeline_outputs"
    log_level: str = "info"

    # Metadata
    created_at: float = field(default_factory=time.time)
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "description": self.description,
            "enabled_stages": [s.value for s in self.enabled_stages],
            "stage_timeout": self.stage_timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "enable_gates": self.enable_gates,
            "gate_strictness": self.gate_strictness,
            "output_dir": self.output_dir,
            "log_level": self.log_level,
            "created_at": self.created_at,
            "version": self.version,
        }


@dataclass
class StageResult:
    """阶段执行结果"""
    stage: PipelineStage
    status: str  # "success", "failed", "skipped"

    # Timing
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0

    # Results
    data: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)

    # Errors
    error_message: str = ""
    retry_count: int = 0

    # Gate results
    gate_passed: bool = True
    gate_violations: List[str] = field(default_factory=list)

    @property
    def is_successful(self) -> bool:
        """是否成功"""
        return self.status == "success" and self.gate_passed


# ============================================================================
# Pipeline Monitor
# ============================================================================

class PipelineMonitor:
    """流程监控器"""

    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def start(self, pipeline_id: str):
        """开始监控"""
        self.start_time = time.time()
        self.add_event("pipeline_started", {
            "pipeline_id": pipeline_id,
            "timestamp": self.start_time,
        })

    def stop(self):
        """停止监控"""
        self.end_time = time.time()
        self.add_event("pipeline_stopped", {
            "duration": self.end_time - self.start_time,
        })

    def add_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> None:
        """添加事件"""
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "data": event_data,
        }
        self.events.append(event)

    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """按类型获取事件"""
        return [e for e in self.events if e["type"] == event_type]

    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        total_duration = (self.end_time if self.end_time else time.time()) - self.start_time

        stage_stats = {}
        for event in self.events:
            if event["type"] == "stage_completed":
                stage = event["data"]["stage"]
                if stage not in stage_stats:
                    stage_stats[stage] = {"count": 0, "success": 0, "failed": 0}
                stage_stats[stage]["count"] += 1
                if event["data"]["status"] == "success":
                    stage_stats[stage]["success"] += 1
                else:
                    stage_stats[stage]["failed"] += 1

        return {
            "duration": total_duration,
            "stage_stats": stage_stats,
            "total_events": len(self.events),
        }


# ============================================================================
# Stage Executors
# ============================================================================

class StageExecutor(ABC):
    """阶段执行器抽象基类"""

    @abstractmethod
    def execute(
        self,
        context: Dict[str, Any],
        config: PipelineConfig,
    ) -> StageResult:
        """执行阶段"""
        pass


class ReportSpecStageExecutor(StageExecutor):
    """ReportSpec 生成阶段执行器"""

    def execute(
        self,
        context: Dict[str, Any],
        config: PipelineConfig,
    ) -> StageResult:
        """执行 ReportSpec 生成"""
        start_time = time.time()
        result = StageResult(
            stage=PipelineStage.REPORT_SPEC_GENERATION,
            status="success",
            start_time=start_time,
        )

        try:
            # TODO: 集成实际的 ReportSpec 生成逻辑
            # 这里应该调用 Phase 1 的 ReportSpecManager

            # 模拟生成
            result.data = {
                "report_spec_id": f"RSPEC-{int(time.time())}",
                "problem_type": context.get("problem_type", "unknown"),
                "physics_models": context.get("physics_models", []),
            }

            result.artifacts = [f"report_spec_{result.data['report_spec_id']}.json"]
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        except Exception as e:
            result.status = "failed"
            result.error_message = str(e)
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        return result


class PhysicsPlanningStageExecutor(StageExecutor):
    """Physics 规划阶段执行器"""

    def execute(
        self,
        context: Dict[str, Any],
        config: PipelineConfig,
    ) -> StageResult:
        """执行 Physics 规划"""
        start_time = time.time()
        result = StageResult(
            stage=PipelineStage.PHYSICS_PLANNING,
            status="success",
            start_time=start_time,
        )

        try:
            # TODO: 集成实际的 Physics Planner
            result.data = {
                "plan_id": f"PLAN-{int(time.time())}",
                "physics_models": context.get("physics_models", []),
                "boundary_conditions": context.get("boundary_conditions", {}),
            }

            result.artifacts = [f"physics_plan_{result.data['plan_id']}.json"]
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        except Exception as e:
            result.status = "failed"
            result.error_message = str(e)
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        return result


class ExecutionStageExecutor(StageExecutor):
    """执行阶段执行器"""

    def execute(
        self,
        context: Dict[str, Any],
        config: PipelineConfig,
    ) -> StageResult:
        """执行 CFD 求解"""
        start_time = time.time()
        result = StageResult(
            stage=PipelineStage.EXECUTION,
            status="success",
            start_time=start_time,
        )

        try:
            # TODO: 集成实际的 Solver Runner
            result.data = {
                "execution_id": f"EXEC-{int(time.time())}",
                "solver_status": "completed",
                "convergence_info": {},
            }

            result.artifacts = [f"results_{result.data['execution_id']}.json"]
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        except Exception as e:
            result.status = "failed"
            result.error_message = str(e)
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        return result


class CorrectionRecordingStageExecutor(StageExecutor):
    """修正记录阶段执行器"""

    def __init__(self, recorder: Optional[CorrectionRecorder] = None):
        self.recorder = recorder or CorrectionRecorder()

    def execute(
        self,
        context: Dict[str, Any],
        config: PipelineConfig,
    ) -> StageResult:
        """执行修正记录"""
        start_time = time.time()
        result = StageResult(
            stage=PipelineStage.CORRECTION_RECORDING,
            status="success",
            start_time=start_time,
        )

        try:
            # 从上下文中获取验证结果
            validation_result = context.get("validation_result")

            if validation_result:
                # 创建修正记录
                # 这里应该集成实际的 CorrectionRecorder
                record_id = f"CORR-{int(time.time())}"
                result.data = {
                    "correction_records_created": 1,
                    "record_ids": [record_id],
                }

            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        except Exception as e:
            result.status = "failed"
            result.error_message = str(e)
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

        return result


# ============================================================================
# Pipeline Orchestrator
# ============================================================================

class PipelineOrchestrator:
    """端到端流程编排器"""

    def __init__(
        self,
        config: PipelineConfig,
        correction_recorder: Optional[CorrectionRecorder] = None,
        benchmark_engine: Optional[BenchmarkReplayEngine] = None,
    ):
        self.config = config
        self.correction_recorder = correction_recorder or CorrectionRecorder()
        self.benchmark_engine = benchmark_engine

        # 流程状态
        self.state = PipelineState.IDLE
        self.monitor = PipelineMonitor()

        # 执行器注册
        self.executors: Dict[PipelineStage, StageExecutor] = {}
        self._register_default_executors()

        # 结果存储
        self.stage_results: Dict[PipelineStage, StageResult] = {}
        self.aggregated_results: Dict[str, Any] = {}

    def _register_default_executors(self):
        """注册默认执行器"""
        self.executors[PipelineStage.REPORT_SPEC_GENERATION] = ReportSpecStageExecutor()
        self.executors[PipelineStage.PHYSICS_PLANNING] = PhysicsPlanningStageExecutor()
        self.executors[PipelineStage.EXECUTION] = ExecutionStageExecutor()
        self.executors[PipelineStage.CORRECTION_RECORDING] = CorrectionRecordingStageExecutor(
            self.correction_recorder
        )

    def register_executor(
        self,
        stage: PipelineStage,
        executor: StageExecutor,
    ) -> None:
        """注册自定义执行器"""
        self.executors[stage] = executor

    def execute(
        self,
        input_data: Dict[str, Any],
        stages: Optional[List[PipelineStage]] = None,
    ) -> Dict[str, Any]:
        """执行流程"""
        self.state = PipelineState.RUNNING
        self.monitor.start(self.config.pipeline_id)

        try:
            # 确定要执行的阶段
            execution_stages = stages or self.config.enabled_stages
            if not execution_stages:
                execution_stages = self._get_default_stages()

            # 执行各个阶段
            for stage in execution_stages:
                if not self._should_execute_stage(stage, input_data):
                    continue

                result = self._execute_stage(stage, input_data)
                self.stage_results[stage] = result

                # 处理阶段结果
                if not result.is_successful:
                    if not self._handle_stage_failure(stage, result, input_data):
                        break

                # 更新上下文
                self._update_context_from_stage(stage, result, input_data)

            # 聚合结果
            self._aggregate_results()

            self.state = PipelineState.COMPLETED
            self.monitor.stop()

            return self._get_final_results()

        except Exception as e:
            self.state = PipelineState.FAILED
            self.monitor.add_event("pipeline_error", {"error": str(e)})
            self.monitor.stop()
            raise

    def _get_default_stages(self) -> List[PipelineStage]:
        """获取默认阶段列表"""
        return [
            PipelineStage.REPORT_SPEC_GENERATION,
            PipelineStage.PHYSICS_PLANNING,
            PipelineStage.EXECUTION,
            PipelineStage.CORRECTION_RECORDING,
        ]

    def _should_execute_stage(self, stage: PipelineStage, context: Dict[str, Any]) -> bool:
        """判断是否应该执行阶段"""
        return stage in self.config.enabled_stages or self.executors.get(stage) is not None

    def _execute_stage(
        self,
        stage: PipelineStage,
        context: Dict[str, Any],
    ) -> StageResult:
        """执行单个阶段"""
        self.monitor.add_event("stage_started", {"stage": stage.value})

        executor = self.executors.get(stage)
        if not executor:
            result = StageResult(
                stage=stage,
                status="skipped",
                start_time=time.time(),
                end_time=time.time(),
                duration=0.0,
            )
            self.monitor.add_event("stage_completed", {
                "stage": stage.value,
                "status": "skipped",
            })
            return result

        # 执行阶段（带重试）
        result = self._execute_with_retry(executor, context, self.config)

        # Gate 检查
        if self.config.enable_gates:
            result.gate_passed, result.gate_violations = self._run_gates(stage, result, context)

        self.monitor.add_event("stage_completed", {
            "stage": stage.value,
            "status": result.status,
            "gate_passed": result.gate_passed,
        })

        return result

    def _execute_with_retry(
        self,
        executor: StageExecutor,
        context: Dict[str, Any],
        config: PipelineConfig,
    ) -> StageResult:
        """带重试的执行"""
        result = None

        for attempt in range(config.max_retries + 1):
            result = executor.execute(context, config)

            if result.is_successful:
                result.retry_count = attempt
                return result

            if attempt < config.max_retries:
                time.sleep(config.retry_delay)

        if result:
            result.retry_count = config.max_retries
        else:
            # 创建失败结果
            result = StageResult(
                stage=PipelineStage.REPORT_SPEC_GENERATION,  # Placeholder
                status="failed",
                error_message="No result returned from executor",
            )

        return result

    def _run_gates(
        self,
        stage: PipelineStage,
        result: StageResult,
        context: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """运行质量门检查"""
        # TODO: 集成实际的 Gate 检查
        # 这里应该调用 Phase 1 的 Gate 检查逻辑

        violations = []

        # 基于严格级别的检查
        if self.config.gate_strictness == "high":
            if result.error_message:
                violations.append(f"Stage had errors: {result.error_message}")

        elif self.config.gate_strictness == "medium":
            if result.status == "failed":
                violations.append("Stage failed")

        # 低严格度不检查

        gate_passed = len(violations) == 0
        return gate_passed, violations

    def _handle_stage_failure(
        self,
        stage: PipelineStage,
        result: StageResult,
        context: Dict[str, Any],
    ) -> bool:
        """处理阶段失败"""
        # 检查是否可以继续
        can_continue = self._can_continue_after_failure(stage, result)

        if not can_continue:
            self.monitor.add_event("pipeline_stopped", {
                "reason": f"Critical stage {stage.value} failed",
                "error": result.error_message,
            })
            return False

        return True

    def _can_continue_after_failure(
        self,
        stage: PipelineStage,
        result: StageResult,
    ) -> bool:
        """判断阶段失败后是否可以继续"""
        # 关键阶段的失败不能继续
        critical_stages = {
            PipelineStage.EXECUTION,
            PipelineStage.REPORT_SPEC_GENERATION,
        }

        # 非关键阶段失败可以继续
        return stage not in critical_stages

    def _update_context_from_stage(
        self,
        stage: PipelineStage,
        result: StageResult,
        context: Dict[str, Any],
    ) -> None:
        """从阶段结果更新上下文"""
        # 将阶段结果添加到上下文
        context[f"{stage.value}_result"] = result.data
        context[f"{stage.value}_artifacts"] = result.artifacts

        # 特定的上下文更新
        if stage == PipelineStage.REPORT_SPEC_GENERATION:
            context["report_spec_id"] = result.data.get("report_spec_id")

        elif stage == PipelineStage.PHYSICS_PLANNING:
            context["plan_id"] = result.data.get("plan_id")

        elif stage == PipelineStage.EXECUTION:
            context["execution_id"] = result.data.get("execution_id")

    def _aggregate_results(self) -> None:
        """聚合所有阶段结果"""
        self.aggregated_results = {
            "pipeline_id": self.config.pipeline_id,
            "state": self.state.value,
            "stage_results": {
                stage.value: {
                    "status": result.status,
                    "duration": result.duration,
                    "gate_passed": result.gate_passed,
                }
                for stage, result in self.stage_results.items()
            },
            "monitoring": self.monitor.get_summary(),
        }

    def _get_final_results(self) -> Dict[str, Any]:
        """获取最终结果"""
        return self.aggregated_results

    def save_results(self, output_path: Optional[str] = None) -> str:
        """保存流程结果"""
        if output_path is None:
            output_path = Path(self.config.output_dir) / f"{self.config.pipeline_id}_results.json"
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(self._get_final_results(), f, indent=2, ensure_ascii=False)

        return str(output_path)


# ============================================================================
# Execution Flow Manager
# ============================================================================

class ExecutionFlowManager:
    """执行流程管理器"""

    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
    ):
        self.orchestrator = orchestrator
        self.flow_history: List[Dict[str, Any]] = []

    def execute_flow(
        self,
        flow_name: str,
        input_data: Dict[str, Any],
        stages: List[PipelineStage],
    ) -> Dict[str, Any]:
        """执行预定义的执行流程"""
        flow_id = f"FLOW-{int(time.time())}-{flow_name}"

        self.flow_history.append({
            "flow_id": flow_id,
            "flow_name": flow_name,
            "stages": [s.value for s in stages],
            "input_data": input_data,
            "timestamp": time.time(),
        })

        # 执行流程
        results = self.orchestrator.execute(input_data, stages)

        return {
            "flow_id": flow_id,
            "flow_name": flow_name,
            "results": results,
        }

    def get_flow_history(self) -> List[Dict[str, Any]]:
        """获取流程历史"""
        return self.flow_history


# ============================================================================
# Result Aggregator
# ============================================================================

class ResultAggregator:
    """结果聚合器"""

    def __init__(self):
        self.aggregation_rules: List[Callable] = []

    def add_aggregation_rule(self, rule: Callable) -> None:
        """添加聚合规则"""
        self.aggregation_rules.append(rule)

    def aggregate(
        self,
        pipeline_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """聚合多个流程的结果"""
        aggregated = {
            "total_pipelines": len(pipeline_results),
            "successful_pipelines": sum(
                1 for r in pipeline_results
                if r.get("state") == PipelineState.COMPLETED.value
            ),
            "failed_pipelines": sum(
                1 for r in pipeline_results
                if r.get("state") == PipelineState.FAILED.value
            ),
            "stage_success_rates": {},
        }

        # 计算各阶段成功率
        all_stages = set()
        for result in pipeline_results:
            stage_results = result.get("stage_results", {})
            for stage_name, stage_info in stage_results.items():
                all_stages.add(stage_name)

        for stage in all_stages:
            successful = sum(
                1 for r in pipeline_results
                if r.get("stage_results", {}).get(stage, {}).get("gate_passed", False)
            )
            total = len(pipeline_results)
            aggregated["stage_success_rates"][stage] = successful / total if total > 0 else 0.0

        # 应用自定义聚合规则
        for rule in self.aggregation_rules:
            try:
                custom_result = rule(pipeline_results)
                aggregated.update(custom_result)
            except Exception as e:
                print(f"Warning: Aggregation rule failed: {e}")

        return aggregated


# ============================================================================
# Convenience Functions
# ============================================================================

def create_default_config(
    pipeline_id: str,
    name: str,
    description: str = "",
    output_dir: str = "./pipeline_outputs",
) -> PipelineConfig:
    """创建默认流程配置"""
    return PipelineConfig(
        pipeline_id=pipeline_id,
        name=name,
        description=description,
        enabled_stages=[
            PipelineStage.REPORT_SPEC_GENERATION,
            PipelineStage.PHYSICS_PLANNING,
            PipelineStage.EXECUTION,
            PipelineStage.CORRECTION_RECORDING,
        ],
        output_dir=output_dir,
    )


def execute_pipeline_simple(
    input_data: Dict[str, Any],
    pipeline_id: str = "PIPE-DEFAULT",
    pipeline_name: str = "Default CFD Pipeline",
    output_dir: str = "./pipeline_outputs",
) -> Dict[str, Any]:
    """便捷函数：执行默认流程"""
    config = create_default_config(
        pipeline_id=pipeline_id,
        name=pipeline_name,
        output_dir=output_dir,
    )

    orchestrator = PipelineOrchestrator(config)
    return orchestrator.execute(input_data)


def execute_batch_pipelines(
    input_data_list: List[Dict[str, Any]],
    config: PipelineConfig,
) -> List[Dict[str, Any]]:
    """批量执行多个流程"""
    results = []

    for input_data in input_data_list:
        orchestrator = PipelineOrchestrator(config)
        result = orchestrator.execute(input_data)
        results.append(result)

    return results
