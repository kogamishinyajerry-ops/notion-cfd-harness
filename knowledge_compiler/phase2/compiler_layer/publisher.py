#!/usr/bin/env python3
"""
Phase 2 Compiler Layer: Publisher

发布知识到 CompiledKnowledge，执行 Gate 验证。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from knowledge_compiler.phase2.schema import (
    CanonicalSpec,
    CompiledKnowledge,
    CompilerConfig,
    CompilationResult,
    KnowledgeStatus,
)
from knowledge_compiler.phase2.gates import (
    GateStatus,
    Phase2GateExecutor,
    run_all_gates,
)


class KnowledgePublisher:
    """
    知识发布器

    执行 Gate 验证并发布知识到 CompiledKnowledge。
    """

    def __init__(self, config: Optional[CompilerConfig] = None):
        """
        Initialize the publisher

        Args:
            config: 编译配置
        """
        self.config = config or CompilerConfig()
        self.gate_executor = Phase2GateExecutor(
            strict_mode=self.config.strict_mode,
            stop_on_first_failure=True,
        )

    def publish(
        self,
        specs: List[CanonicalSpec],
    ) -> CompiledKnowledge:
        """
        发布知识

        Args:
            specs: CanonicalSpec 列表

        Returns:
            CompiledKnowledge
        """
        knowledge = CompiledKnowledge()
        knowledge.total_input_count = len(specs)

        # 执行所有 Gate
        gate_results_map: Dict[str, List[Any]] = {
            "G1-P2": [],
            "G2-P2": [],
        }

        for spec in specs:
            # 执行 Gate
            gate_results = self.gate_executor.execute(spec)
            spec_id = spec.spec_id

            # 收集结果
            for gate_id, result in gate_results.items():
                gate_results_map[gate_id].append({
                    "spec_id": spec_id,
                    "result": result,
                })

            # 检查是否通过所有 BLOCK 级别的 Gate
            can_publish = self._can_publish(gate_results)

            if can_publish:
                # 添加到输出
                knowledge.add_spec(spec)
                knowledge.success_count += 1

                # 更新 spec 状态
                spec.knowledge_status = KnowledgeStatus.APPROVED
            else:
                knowledge.failed_count += 1

        # 汇总 Gate 结果
        knowledge.gate_results = self._summarize_gate_results(gate_results_map)

        return knowledge

    def publish_single(
        self,
        spec: CanonicalSpec,
    ) -> CompiledKnowledge:
        """
        发布单个知识

        Args:
            spec: CanonicalSpec 实例

        Returns:
            CompiledKnowledge
        """
        return self.publish([spec])

    def run_gates(
        self,
        spec: CanonicalSpec,
    ) -> Dict[str, Any]:
        """
        对单个 Spec 执行所有 Gate

        Args:
            spec: CanonicalSpec 实例

        Returns:
            Gate 结果字典
        """
        return run_all_gates(spec, strict_mode=self.config.strict_mode)

    def verify(
        self,
        spec: CanonicalSpec,
    ) -> bool:
        """
        验证知识是否可发布

        Args:
            spec: CanonicalSpec 实例

        Returns:
            是否可发布
        """
        gate_results = self.run_gates(spec)
        return self._can_publish(gate_results)

    def _can_publish(self, gate_results: Dict[str, Any]) -> bool:
        """
        检查是否可以发布

        Args:
            gate_results: Gate 结果字典

        Returns:
            是否可发布
        """
        for gate_id, result in gate_results.items():
            # 检查 BLOCK 级别的 Gate
            if result.severity == "BLOCK":
                if result.status != GateStatus.PASS:
                    return False
        return True

    def _summarize_gate_results(
        self,
        gate_results_map: Dict[str, List[Any]],
    ) -> Dict[str, Any]:
        """
        汇总 Gate 结果

        Args:
            gate_results_map: Gate 结果映射

        Returns:
            汇总信息
        """
        summary = {
            "total_gates": len(gate_results_map),
            "gate_details": {},
        }

        for gate_id, results in gate_results_map.items():
            passed = sum(1 for r in results if r["result"].is_pass())
            total = len(results)

            summary["gate_details"][gate_id] = {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": (passed / total * 100) if total > 0 else 100,
            }

        return summary

    def get_publish_report(
        self,
        knowledge: CompiledKnowledge,
    ) -> Dict[str, Any]:
        """
        生成发布报告

        Args:
            knowledge: CompiledKnowledge 实例

        Returns:
            发布报告
        """
        return {
            "output_id": knowledge.output_id,
            "total_input_count": knowledge.total_input_count,
            "success_count": knowledge.success_count,
            "failed_count": knowledge.failed_count,
            "success_rate": knowledge.get_success_rate() * 100,
            "gate_results": knowledge.gate_results,
            "compiled_at": knowledge.compiled_at,
        }


def publish_knowledge(
    specs: List[CanonicalSpec],
    strict_mode: bool = True,
) -> CompiledKnowledge:
    """
    便捷函数：发布知识

    Args:
        specs: CanonicalSpec 列表
        strict_mode: 是否使用严格模式

    Returns:
        CompiledKnowledge
    """
    config = CompilerConfig(strict_mode=strict_mode)
    publisher = KnowledgePublisher(config=config)
    return publisher.publish(specs)


def verify_spec(
    spec: CanonicalSpec,
    strict_mode: bool = True,
) -> bool:
    """
    便捷函数：验证知识

    Args:
        spec: CanonicalSpec 实例
        strict_mode: 是否使用严格模式

    Returns:
        是否可发布
    """
    config = CompilerConfig(strict_mode=strict_mode)
    publisher = KnowledgePublisher(config=config)
    return publisher.verify(spec)


__all__ = [
    "KnowledgePublisher",
    "publish_knowledge",
    "verify_spec",
]
