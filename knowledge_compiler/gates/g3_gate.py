#!/usr/bin/env python3
"""
P4-07: G3 Gate automation for Phase 4 quality control.
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping, Sequence


GATE_NAME = "G3"
DEFAULT_MODULE_NAME = "knowledge_compiler.memory_network"
DEFAULT_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("P4-01", "VersionedKnowledgeRegistry"),
    ("P4-02", "MemoryNode"),
    ("P4-03", "PropagationEngine"),
    ("P4-04", "GovernanceEngine"),
    ("P4-05", "CodeMappingRegistry"),
    ("P4-06", "MemoryNetwork"),
)
DEFAULT_REVIEW_SCRIPT = Path("scripts/trigger_code_review.sh")
DEFAULT_RESULTS_DIR = Path("knowledge_compiler/gates/results")
DEFAULT_TEST_COMMAND = (sys.executable, "-m", "pytest")
SUMMARY_TOKENS = (
    "passed",
    "failed",
    "error",
    "errors",
    "skipped",
    "xfailed",
    "xpassed",
    "rerun",
)


def check_core_components(
    module_name: str = DEFAULT_MODULE_NAME,
    components: Sequence[tuple[str, str]] = DEFAULT_COMPONENTS,
) -> dict[str, Any]:
    """
    Verify that the P4-01 through P4-06 core classes are available.
    """
    try:
        module = import_module(module_name)
    except Exception as exc:  # pragma: no cover - covered by failure branch assertions
        return {
            "check": "check_core_components",
            "passed": False,
            "detail": f"Unable to import {module_name}: {exc}",
            "components": [],
            "module_name": module_name,
        }

    component_results: list[dict[str, Any]] = []
    missing: list[str] = []

    for phase_id, class_name in components:
        exported = getattr(module, class_name, None)
        exists = exported is not None and inspect.isclass(exported)
        component_results.append(
            {
                "phase": phase_id,
                "component": class_name,
                "passed": exists,
            }
        )
        if not exists:
            missing.append(f"{phase_id} {class_name}")

    passed = not missing
    detail = (
        f"Verified {len(component_results)}/{len(component_results)} Phase 4 core components"
        if passed
        else f"Missing core components: {', '.join(missing)}"
    )

    return {
        "check": "check_core_components",
        "passed": passed,
        "detail": detail,
        "components": component_results,
        "module_name": module_name,
    }


def run_all_tests(
    repo_root: Path | str | None = None,
    pytest_args: Sequence[str] | None = None,
) -> dict[str, Any]:
    """
    Run pytest for the repository and report the outcome.
    """
    resolved_repo_root = _resolve_repo_root(repo_root)
    command = [*DEFAULT_TEST_COMMAND, *(pytest_args or ())]
    completed = subprocess.run(
        command,
        cwd=str(resolved_repo_root),
        check=False,
        capture_output=True,
        text=True,
    )

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    summary = _extract_pytest_summary(stdout, stderr)
    passed = completed.returncode == 0

    if summary:
        detail = summary
    elif passed:
        detail = "pytest completed successfully"
    else:
        detail = f"pytest failed with exit code {completed.returncode}"

    return {
        "check": "run_all_tests",
        "passed": passed,
        "detail": detail,
        "summary": summary,
        "command": command,
        "working_directory": str(resolved_repo_root),
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def check_code_review_integration(
    repo_root: Path | str | None = None,
    script_path: Path | str = DEFAULT_REVIEW_SCRIPT,
) -> dict[str, Any]:
    """
    Verify the code review trigger script exists.
    """
    resolved_repo_root = _resolve_repo_root(repo_root)
    resolved_script_path = Path(script_path)
    if not resolved_script_path.is_absolute():
        resolved_script_path = resolved_repo_root / resolved_script_path

    exists = resolved_script_path.is_file()
    detail = (
        f"Found code review trigger: {resolved_script_path.relative_to(resolved_repo_root).as_posix()}"
        if exists
        else f"Missing code review trigger: {resolved_script_path.relative_to(resolved_repo_root).as_posix()}"
    )

    return {
        "check": "check_code_review_integration",
        "passed": exists,
        "detail": detail,
        "script_path": str(resolved_script_path),
        "executable": resolved_script_path.exists() and resolved_script_path.stat().st_mode & 0o111 != 0,
    }


def trigger_gate(
    repo_root: Path | str | None = None,
    record_path: Path | str | None = None,
    pytest_args: Sequence[str] | None = None,
) -> dict[str, Any]:
    """
    Run the full G3 gate flow and persist the result report.
    """
    resolved_repo_root = _resolve_repo_root(repo_root)
    timestamp = _timestamp_now()

    checks = [
        check_core_components(),
        run_all_tests(repo_root=resolved_repo_root, pytest_args=pytest_args),
        check_code_review_integration(repo_root=resolved_repo_root),
    ]

    blockers = [check["detail"] for check in checks if not check["passed"]]
    passed = not blockers
    status = "PASS" if passed else "FAIL"
    resolved_record_path = _resolve_record_path(
        repo_root=resolved_repo_root,
        output_path=record_path,
        timestamp=timestamp,
    )

    result = {
        "gate": GATE_NAME,
        "passed": passed,
        "status": status,
        "timestamp": timestamp,
        "repo_root": str(resolved_repo_root),
        "checks": checks,
        "blockers": blockers,
        "next_action": (
            "Ready for G4 gate validation"
            if passed
            else "Resolve blockers and re-run the G3 gate"
        ),
        "record_path": str(resolved_record_path),
    }
    result["report"] = _build_gate_report(result)

    record_gate_result(result, output_path=resolved_record_path)
    return result


def record_gate_result(
    result: Mapping[str, Any],
    output_path: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> str:
    """
    Persist the gate result as JSON and return the written path.
    """
    timestamp = str(result.get("timestamp") or _timestamp_now())
    resolved_output_path = _resolve_record_path(
        repo_root=repo_root,
        output_path=output_path or result.get("record_path"),
        timestamp=timestamp,
    )

    payload = dict(result)
    payload["record_path"] = str(resolved_output_path)

    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    return str(resolved_output_path)


def _resolve_repo_root(repo_root: Path | str | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_record_path(
    repo_root: Path | str | None,
    output_path: Path | str | None,
    timestamp: str,
) -> Path:
    resolved_repo_root = _resolve_repo_root(repo_root)
    if output_path is None:
        return resolved_repo_root / DEFAULT_RESULTS_DIR / _default_report_filename(timestamp)

    candidate = Path(output_path).expanduser()
    if not candidate.is_absolute():
        candidate = resolved_repo_root / candidate

    if candidate.suffix == "":
        candidate = candidate / _default_report_filename(timestamp)
    return candidate.resolve()


def _default_report_filename(timestamp: str) -> str:
    compact_timestamp = re.sub(r"[^0-9A-Za-z]+", "", timestamp)
    return f"g3_gate_result_{compact_timestamp}.json"


def _extract_pytest_summary(*streams: str) -> str | None:
    for stream in streams:
        if not stream:
            continue
        for line in reversed(stream.splitlines()):
            stripped = line.strip()
            if not stripped:
                continue

            normalized = stripped.strip("=").strip()
            if any(token in normalized for token in SUMMARY_TOKENS):
                return normalized
    return None


def _build_gate_report(result: Mapping[str, Any]) -> str:
    lines = [
        "G3 Gate Report",
        f"Status: {result['status']}",
        f"Timestamp: {result['timestamp']}",
    ]

    for check in result["checks"]:
        lines.append(
            f"- {check['check']}: {'PASS' if check['passed'] else 'FAIL'} - {check['detail']}"
        )

    blockers = result.get("blockers") or []
    lines.append(f"Blockers: {', '.join(blockers) if blockers else 'None'}")
    lines.append(f"Next action: {result['next_action']}")
    lines.append(f"Record: {result['record_path']}")
    return "\n".join(lines)


if __name__ == "__main__":
    gate_result = trigger_gate()
    print(gate_result["report"])
    raise SystemExit(0 if gate_result["passed"] else 1)
