#!/usr/bin/env python3
"""
Phase 2 Gate Executor

负责执行所有 Phase 2 质量门，按顺序验证知识。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from knowledge_compiler.phase2.gates.gates import (
    GateStatus,
    GateResult,
)
from knowledge_compiler.phase2.gates.g1_p2 import (
    KnowledgeCompletenessGate,
    G1_P2_GATE_ID,
)
from knowledge_compiler.phase2.gates.g2_p2 import (
    AuthorizationGate,
    G2_P2_GATE_ID,
)
from knowledge_compiler.phase2.schema import (
    CanonicalSpec,
)


class Phase2GateExecutor:
    """
    Phase 2 Gate 执行器

    按顺序执行 G1-P2 和 G2-P2 质量门。
    """

    # Gate 执行顺序（BLOCK 级别的 Gate 必须全部通过）
    GATE_SEQUENCE = [
        G1_P2_GATE_ID,  # G1-P2: Knowledge Completeness
        G2_P2_GATE_ID,  # G2-P2: Authorization
    ]

    def __init__(
        self,
        strict_mode: bool = True,
        stop_on_first_failure: bool = True,
    ):
        """
        Initialize the executor

        Args:
            strict_mode: 是否启用严格模式（传递给各个 Gate）
            stop_on_first_failure: 是否在第一个 FAIL 时停止执行
        """
        self.strict_mode = strict_mode
        self.stop_on_first_failure = stop_on_first_failure

        # 初始化所有 Gate
        self.gates = {
            G1_P2_GATE_ID: KnowledgeCompletenessGate(strict_mode=strict_mode),
            G2_P2_GATE_ID: AuthorizationGate(strict_mode=strict_mode),
        }

    def execute(
        self,
        spec: CanonicalSpec,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, GateResult]:
        """
        对单个 CanonicalSpec 执行所有 Gate

        Args:
            spec: CanonicalSpec 实例
            context: 额外上下文信息

        Returns:
            Dict mapping gate_id to GateResult
        """
        results = {}

        for gate_id in self.GATE_SEQUENCE:
            gate = self.gates.get(gate_id)
            if gate is None:
                continue

            # 执行 Gate 检查
            result = gate.check(spec)
            results[gate_id] = result

            # 如果配置了首失败停止，且当前 Gate 失败，则停止
            if self.stop_on_first_failure and result.status == GateStatus.FAIL:
                # 对于后续未执行的 Gate，标记为 SKIP
                for remaining_gate_id in self.GATE_SEQUENCE[
                    self.GATE_SEQUENCE.index(gate_id) + 1:
                ]:
                    results[remaining_gate_id] = GateResult(
                        gate_id=remaining_gate_id,
                        gate_name=f"Gate {remaining_gate_id}",
                        status=GateStatus.SKIP,
                        timestamp=result.timestamp,
                        score=0.0,
                        errors=["Skipped due to previous failure"],
                        severity="BLOCK",
                    )
                break

        return results

    def execute_batch(
        self,
        specs: List[CanonicalSpec],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[GateResult]]:
        """
        批量执行所有 Gate

        Args:
            specs: CanonicalSpec 列表
            context: 额外上下文信息

        Returns:
            Dict mapping gate_id to list of GateResult (one per spec)
        """
        batch_results = {gate_id: [] for gate_id in self.GATE_SEQUENCE}

        for spec in specs:
            results = self.execute(spec, context)
            for gate_id, result in results.items():
                batch_results[gate_id].append(result)

        return batch_results

    def get_summary(
        self,
        results: Dict[str, GateResult],
    ) -> Dict[str, Any]:
        """
        获取 Gate 执行结果摘要

        Args:
            results: execute() 或 execute_batch() 的返回结果

        Returns:
            摘要信息字典
        """
        summary = {
            "total_gates": len(results),
            "passed": 0,
            "failed": 0,
            "warned": 0,
            "skipped": 0,
            "overall_status": GateStatus.PASS,
            "blockers": [],
        }

        for gate_id, result in results.items():
            if result.status == GateStatus.PASS:
                summary["passed"] += 1
            elif result.status == GateStatus.FAIL:
                summary["failed"] += 1
                if result.severity == "BLOCK":
                    summary["blockers"].append(gate_id)
            elif result.status == GateStatus.WARN:
                summary["warned"] += 1
            elif result.status == GateStatus.SKIP:
                summary["skipped"] += 1

        # 确定整体状态
        if summary["blockers"]:
            summary["overall_status"] = GateStatus.FAIL
        elif summary["failed"] > 0:
            summary["overall_status"] = GateStatus.FAIL
        elif summary["warned"] > 0:
            summary["overall_status"] = GateStatus.WARN

        return summary

    def get_failed_specs(
        self,
        batch_results: Dict[str, List[GateResult]],
    ) -> List[int]:
        """
        获取失败的 spec 索引

        Args:
            batch_results: execute_batch() 的返回结果

        Returns:
            失败的 spec 索引列表
        """
        failed_indices = set()

        for gate_id, results in batch_results.items():
            for i, result in enumerate(results):
                if result.status == GateStatus.FAIL and result.severity == "BLOCK":
                    failed_indices.add(i)

        return sorted(failed_indices)

    def get_gate_by_id(self, gate_id: str):
        """
        根据 ID 获取 Gate 实例

        Args:
            gate_id: Gate ID

        Returns:
            Gate 实例，如果不存在则返回 None
        """
        return self.gates.get(gate_id)


def run_all_gates(
    spec: CanonicalSpec,
    context: Optional[Dict[str, Any]] = None,
    strict_mode: bool = True,
) -> Dict[str, GateResult]:
    """
    便捷函数：执行所有 Phase 2 Gate

    Args:
        spec: CanonicalSpec 实例
        context: 额外上下文信息
        strict_mode: 是否启用严格模式

    Returns:
        Dict mapping gate_id to GateResult
    """
    executor = Phase2GateExecutor(strict_mode=strict_mode)
    return executor.execute(spec, context)


def run_all_gates_batch(
    specs: List[CanonicalSpec],
    context: Optional[Dict[str, Any]] = None,
    strict_mode: bool = True,
) -> Dict[str, List[GateResult]]:
    """
    便捷函数：批量执行所有 Phase 2 Gate

    Args:
        specs: CanonicalSpec 列表
        context: 额外上下文信息
        strict_mode: 是否启用严格模式

    Returns:
        Dict mapping gate_id to list of GateResult
    """
    executor = Phase2GateExecutor(strict_mode=strict_mode)
    return executor.execute_batch(specs, context)


__all__ = [
    "Phase2GateExecutor",
    "run_all_gates",
    "run_all_gates_batch",
]
