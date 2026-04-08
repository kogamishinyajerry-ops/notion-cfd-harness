#!/usr/bin/env python3
"""
Phase 2c: Governance & Learning

治理和学习层，提供知识闭环和回放验证功能。

核心组件:
- Correction Recorder: 结构化记录 CorrectionSpec
- Benchmark Replay Engine: 黄金样板集回放验证
"""

# Correction Recorder
from knowledge_compiler.phase2c.correction_recorder import (
    CorrectionSeverity,
    ReplayStatus,
    CorrectionRecord,
    ImpactScopeAnalyzer,
    SpecsValidator,
    ConstraintsChecker,
    CorrectionRecorder,
    record_from_failure,
)

__all__ = [
    # Correction Recorder
    "CorrectionSeverity",
    "ReplayStatus",
    "CorrectionRecord",
    "ImpactScopeAnalyzer",
    "SpecsValidator",
    "ConstraintsChecker",
    "CorrectionRecorder",
    "record_from_failure",
]
