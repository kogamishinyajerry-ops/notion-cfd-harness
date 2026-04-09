#!/usr/bin/env python3
"""
Phase 2 Gates: Base Gate Classes

Phase 2 质量门的基类和通用接口。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from knowledge_compiler.phase2.schema import (
    CompiledKnowledge,
    CanonicalSpec,
    ParsedTeach,
    TeachCapture,
)


# ============================================================================
# Gate Status
# ============================================================================

class GateStatus(Enum):
    """Gate 状态"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


# ============================================================================
# Gate Result Interface
# ============================================================================

@dataclass
class GateCheckItem:
    """单个检查项"""
    item: str
    description: str
    result: GateStatus
    message: str
    evidence_id: Optional[str] = None


@dataclass
class GateResult:
    """
    Gate 检查结果（统一接口）

    Phase 2 所有 Gate 共享此接口。
    """
    gate_id: str
    gate_name: str
    status: GateStatus
    timestamp: float
    score: float  # 0-100
    checklist: List[GateCheckItem] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    severity: str = "BLOCK"  # BLOCK, WARN, LOG

    def is_pass(self) -> bool:
        """检查是否通过"""
        return self.status == GateStatus.PASS

    def get_pass_rate(self) -> float:
        """获取通过率"""
        if not self.checklist:
            return 0.0
        passed = sum(1 for c in self.checklist if c.result == GateStatus.PASS)
        return (passed / len(self.checklist)) * 100

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "score": self.score,
            "checklist": [
                {
                    "item": c.item,
                    "description": c.description,
                    "result": c.result.value,
                    "message": c.message,
                    "evidence_id": c.evidence_id,
                }
                for c in self.checklist
            ],
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "severity": self.severity,
        }


__all__ = [
    # Base
    "GateStatus",
    "GateCheckItem",
    "GateResult",
]
