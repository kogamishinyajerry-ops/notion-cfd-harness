#!/usr/bin/env python3
"""
Phase 3: Analogical Orchestrator (E层)

基于已学知识，对未见过但相近的算例进行类比推理、方案生成和低成本试探。

核心组件:
- SimilarityEngine (E1): 结构化特征匹配的相似度检索
- AnalogyDecomposer (E2): 相似性维度分解
- CandidatePlanGenerator (E3): 候选方案生成
- TrialRunner (E4): 低成本试探执行
- TrialEvaluator (E5): 试探结果评估
- AnalogyFailureHandler (E6): 类比失效处理
- AnalogicalOrchestrator: 主编排器
"""

from .analogy_engine import (
    SimilarityEngine,
    AnalogyDecomposer,
    CandidatePlanGenerator,
    TrialRunner,
    TrialEvaluator,
    AnalogyFailureHandler,
    AnalogicalOrchestrator,
)

__all__ = [
    "SimilarityEngine",
    "AnalogyDecomposer",
    "CandidatePlanGenerator",
    "TrialRunner",
    "TrialEvaluator",
    "AnalogyFailureHandler",
    "AnalogicalOrchestrator",
]
