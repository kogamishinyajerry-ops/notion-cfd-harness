#!/usr/bin/env python3
"""
CLI shim for `python3 -m diff_engine`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_IMPL_PATH = Path(__file__).resolve().parent / "knowledge_compiler" / "executables" / "diff_engine.py"
_SPEC = importlib.util.spec_from_file_location("_knowledge_compiler_diff_engine", _IMPL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load diff engine implementation from {_IMPL_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)


for _name in getattr(_MODULE, "__all__", []):
    globals()[_name] = getattr(_MODULE, _name)


if __name__ == "__main__":
    raise SystemExit(_MODULE.main())
