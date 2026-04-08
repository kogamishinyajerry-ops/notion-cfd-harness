#!/usr/bin/env python3
"""
Phase 2 Gates

Phase 2 质量门，确保编译后的知识质量。
"""

from knowledge_compiler.phase2.gates.gates import (
    GateStatus,
    GateResult,
    GateCheckItem,
)

from knowledge_compiler.phase2.gates.g1_p2 import (
    KnowledgeCompletenessGate,
    G1_P2_GATE_ID,
)

from knowledge_compiler.phase2.gates.g2_p2 import (
    AuthorizationGate,
    G2_P2_GATE_ID,
    AuthStatus,
    AuthRequest,
)

from knowledge_compiler.phase2.gates.executor import (
    Phase2GateExecutor,
    run_all_gates,
)

__all__ = [
    # Base
    "GateStatus",
    "GateResult",
    "GateCheckItem",
    # G1-P2
    "KnowledgeCompletenessGate",
    "G1_P2_GATE_ID",
    # G2-P2
    "AuthorizationGate",
    "G2_P2_GATE_ID",
    "AuthStatus",
    "AuthRequest",
    # Executor
    "Phase2GateExecutor",
    "run_all_gates",
    "run_all_gates_batch",
]
