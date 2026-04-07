#!/usr/bin/env python3
"""
P4-08: G4 Gate propagation verification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from knowledge_compiler.gates.g3_gate import G4_CONFIG, GateConfig, trigger_gate as _trigger_gate


GATE_NAME = "G4"
DEFAULT_CONFIG = G4_CONFIG


def trigger_gate(
    repo_root: Path | str | None = None,
    record_path: Path | str | None = None,
    pytest_args: Sequence[str] | None = None,
    config: GateConfig | None = None,
) -> dict[str, object]:
    active_config = config or DEFAULT_CONFIG
    return _trigger_gate(
        gate_name=active_config.gate_name,
        repo_root=repo_root,
        record_path=record_path,
        pytest_args=pytest_args,
        config=active_config,
    )


if __name__ == "__main__":
    gate_result = trigger_gate()
    print(gate_result["report"])
    raise SystemExit(0 if gate_result["passed"] else 1)
