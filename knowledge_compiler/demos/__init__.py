"""Demo helpers for deterministic end-to-end mock workflows."""

from importlib import import_module
from typing import Any

__all__ = [
    "E2E_DEMO_CASES",
    "E2EResult",
    "get_mock_result_for_case",
    "run_e2e_mock_demo",
    "run_all_demos",
    "print_summary",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module("knowledge_compiler.demos.e2e_mock_demo")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
