#!/usr/bin/env python3
"""
P4-07/P4-08: Shared gate automation for Phase 4 quality control.
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


GATE_NAME = "G3"
KNOWN_GATES = ("G3", "G4", "G5", "G6")
DEFAULT_MODULE_NAME = "knowledge_compiler.memory_network"
DEFAULT_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("P4-01", "VersionedKnowledgeRegistry"),
    ("P4-02", "MemoryNode"),
    ("P4-03", "PropagationEngine"),
    ("P4-04", "GovernanceEngine"),
    ("P4-05", "CodeMappingRegistry"),
    ("P4-06", "MemoryNetwork"),
)
PROPAGATION_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("P4-03", "PropagationEngine"),
    ("P4-06", "MemoryNetwork"),
)
MANUAL_APPROVAL_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("P4-03", "PropagationEngine"),
    ("P4-04", "GovernanceEngine"),
)
DEFAULT_GATE_MODULES: tuple[str, ...] = (
    "knowledge_compiler.gates.g3_gate",
    "knowledge_compiler.gates.g4_gate",
    "knowledge_compiler.gates.g5_gate",
    "knowledge_compiler.gates.g6_gate",
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

GateCheckRunner = Callable[[Path, Sequence[str], "GateConfig"], dict[str, Any]]


@dataclass(frozen=True)
class GateConfig:
    """
    Shared configuration for a gate runner.
    """

    gate_name: str
    checks: tuple[GateCheckRunner, ...] = ()
    module_name: str = DEFAULT_MODULE_NAME
    components: tuple[tuple[str, str], ...] = DEFAULT_COMPONENTS
    results_dir: Path | str = DEFAULT_RESULTS_DIR
    review_script: Path | str | None = DEFAULT_REVIEW_SCRIPT
    default_pytest_args: tuple[str, ...] = ()
    success_action: str = ""
    failure_action: str = ""
    report_title: str = ""

    def __post_init__(self) -> None:
        gate_name = str(self.gate_name).strip().upper() or GATE_NAME
        normalized_components = tuple((phase_id, class_name) for phase_id, class_name in self.components)
        normalized_results_dir = Path(self.results_dir)
        normalized_review_script = None
        if self.review_script is not None:
            normalized_review_script = Path(self.review_script)
        normalized_report_title = self.report_title or f"{gate_name} Gate Report"

        object.__setattr__(self, "gate_name", gate_name)
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "components", normalized_components)
        object.__setattr__(self, "results_dir", normalized_results_dir)
        object.__setattr__(self, "review_script", normalized_review_script)
        object.__setattr__(self, "default_pytest_args", tuple(self.default_pytest_args))
        object.__setattr__(self, "report_title", normalized_report_title)


def check_core_components(
    module_name: str = DEFAULT_MODULE_NAME,
    components: Sequence[tuple[str, str]] = DEFAULT_COMPONENTS,
) -> dict[str, Any]:
    """
    Verify that the requested Phase 4 core classes are available.
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


def check_dependency_propagation(
    module_name: str = DEFAULT_MODULE_NAME,
    propagation_methods: Sequence[str] = ("detect_changes", "analyze_impact", "propagate"),
    orchestrator_methods: Sequence[str] = ("propagate_change",),
) -> dict[str, Any]:
    """
    Verify that propagation contracts required by G4 are present.
    """
    try:
        module = import_module(module_name)
    except Exception as exc:  # pragma: no cover - covered by failure branch assertions
        return {
            "check": "check_dependency_propagation",
            "passed": False,
            "detail": f"Unable to import {module_name}: {exc}",
            "module_name": module_name,
            "verified_members": [],
        }

    propagation_engine = getattr(module, "PropagationEngine", None)
    memory_network = getattr(module, "MemoryNetwork", None)
    missing: list[str] = []
    verified_members: list[str] = []

    for class_name, exported, methods in (
        ("PropagationEngine", propagation_engine, propagation_methods),
        ("MemoryNetwork", memory_network, orchestrator_methods),
    ):
        if not inspect.isclass(exported):
            missing.append(class_name)
            continue
        for method_name in methods:
            method = getattr(exported, method_name, None)
            if callable(method):
                verified_members.append(f"{class_name}.{method_name}")
            else:
                missing.append(f"{class_name}.{method_name}")

    passed = not missing
    detail = (
        "Verified dependency propagation: " + ", ".join(verified_members)
        if passed
        else "Missing propagation contract members: " + ", ".join(missing)
    )
    return {
        "check": "check_dependency_propagation",
        "passed": passed,
        "detail": detail,
        "module_name": module_name,
        "verified_members": verified_members,
    }


def check_manual_approval_points(
    module_name: str = DEFAULT_MODULE_NAME,
    task_type: str = "Gate Final Approval",
    approval_model: str = "Human",
    alternate_model: str = "Codex (GPT-5.4)",
) -> dict[str, Any]:
    """
    Verify that manual approval hooks and human intervention points are exposed.
    """
    try:
        module = import_module(module_name)
        diff_module = import_module("knowledge_compiler.executables.diff_engine")
    except Exception as exc:  # pragma: no cover - covered by failure branch assertions
        return {
            "check": "check_manual_approval_points",
            "passed": False,
            "detail": f"Unable to import manual approval dependencies: {exc}",
            "module_name": module_name,
            "verified_points": [],
        }

    propagation_engine_class = getattr(module, "PropagationEngine", None)
    governance_engine_class = getattr(module, "GovernanceEngine", None)
    missing: list[str] = []
    verified_points: list[str] = []

    if not inspect.isclass(propagation_engine_class):
        missing.append("PropagationEngine")
    if not inspect.isclass(governance_engine_class):
        missing.append("GovernanceEngine")

    if missing:
        return {
            "check": "check_manual_approval_points",
            "passed": False,
            "detail": "Missing manual approval classes: " + ", ".join(missing),
            "module_name": module_name,
            "verified_points": [],
        }

    propagation_engine = propagation_engine_class()
    governance_engine = governance_engine_class()
    change_type = getattr(diff_module, "ChangeType", None)
    diff_report = getattr(diff_module, "DiffReport", None)

    if change_type is None or diff_report is None:
        return {
            "check": "check_manual_approval_points",
            "passed": False,
            "detail": "Missing diff_engine change models required for approval verification",
            "module_name": module_name,
            "verified_points": [],
        }

    delete_change = diff_report(
        change_type=change_type.DELETE,
        unit_id="UNIT-DELETE",
        field="__unit__",
        old_value={"path": "units/delete.yaml"},
        new_value=None,
        impacted_executables=["EXEC-DELETE-001"],
    )
    delete_decision = propagation_engine.analyze_impact(delete_change)
    delete_halts = delete_decision.action_type == propagation_engine.ACTION_HALT
    delete_requires_manual_review = "manual review" in delete_decision.reason.lower()

    human_required = governance_engine.validate_model_assignment(task_type, approval_model)
    alternate_rejected = not governance_engine.validate_model_assignment(task_type, alternate_model)

    if delete_halts and delete_requires_manual_review:
        verified_points.append("PropagationEngine.DELETE -> halt/manual review")
    else:
        missing.append("PropagationEngine.DELETE manual halt")

    if human_required:
        verified_points.append(f"GovernanceEngine.{task_type} -> {approval_model}")
    else:
        missing.append(f"GovernanceEngine.{task_type} requires {approval_model}")

    if alternate_rejected:
        verified_points.append(f"GovernanceEngine rejects {alternate_model} for {task_type}")
    else:
        missing.append(f"GovernanceEngine rejects {alternate_model} for {task_type}")

    passed = not missing
    detail = (
        "Verified manual approval points: " + ", ".join(verified_points)
        if passed
        else "Missing manual approval points: " + ", ".join(missing)
    )
    return {
        "check": "check_manual_approval_points",
        "passed": passed,
        "detail": detail,
        "module_name": module_name,
        "verified_points": verified_points,
    }


def check_gate_module_imports(
    module_names: Sequence[str] = DEFAULT_GATE_MODULES,
) -> dict[str, Any]:
    """
    Verify that all gate modules import successfully and expose trigger_gate().
    """
    imported_modules: list[str] = []
    missing: list[str] = []

    for module_name in module_names:
        try:
            module = import_module(module_name)
        except Exception as exc:  # pragma: no cover - covered by failure branch assertions
            missing.append(f"{module_name}: {exc}")
            continue

        if callable(getattr(module, "trigger_gate", None)):
            imported_modules.append(module_name)
        else:
            missing.append(f"{module_name}: missing trigger_gate")

    passed = not missing
    detail = (
        f"Verified {len(imported_modules)}/{len(module_names)} gate modules"
        if passed
        else "Gate module import failures: " + ", ".join(missing)
    )
    return {
        "check": "check_gate_module_imports",
        "passed": passed,
        "detail": detail,
        "modules": imported_modules,
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
    try:
        relative_script_path = resolved_script_path.relative_to(resolved_repo_root).as_posix()
    except ValueError:
        relative_script_path = resolved_script_path.as_posix()

    detail = (
        f"Found code review trigger: {relative_script_path}"
        if exists
        else f"Missing code review trigger: {relative_script_path}"
    )

    return {
        "check": "check_code_review_integration",
        "passed": exists,
        "detail": detail,
        "script_path": str(resolved_script_path),
        "executable": resolved_script_path.exists() and resolved_script_path.stat().st_mode & 0o111 != 0,
    }


def trigger_gate(
    gate_name: str | Path = GATE_NAME,
    repo_root: Path | str | None = None,
    record_path: Path | str | None = None,
    pytest_args: Sequence[str] | None = None,
    config: GateConfig | None = None,
) -> dict[str, Any]:
    """
    Run the requested gate flow and persist the result report.

    The `gate_name` argument is optional for backward compatibility. Older
    callers may still pass `repo_root` as the first positional argument.
    """
    resolved_gate_name, resolved_repo_root_arg = _coerce_gate_invocation(
        gate_name=gate_name,
        repo_root=repo_root,
        config=config,
    )
    active_config = config or DEFAULT_GATE_CONFIGS.get(resolved_gate_name, GateConfig(gate_name=resolved_gate_name))
    resolved_repo_root = _resolve_repo_root(resolved_repo_root_arg)
    timestamp = _timestamp_now()

    checks = [
        check_runner(resolved_repo_root, pytest_args, active_config)
        for check_runner in active_config.checks
    ]

    blockers = [check["detail"] for check in checks if not check["passed"]]
    passed = not blockers
    status = "PASS" if passed else "FAIL"
    resolved_record_path = _resolve_record_path(
        repo_root=resolved_repo_root,
        output_path=record_path,
        timestamp=timestamp,
        gate_name=resolved_gate_name,
        results_dir=active_config.results_dir,
    )

    result = {
        "gate": resolved_gate_name,
        "passed": passed,
        "status": status,
        "timestamp": timestamp,
        "repo_root": str(resolved_repo_root),
        "checks": checks,
        "blockers": blockers,
        "next_action": active_config.success_action if passed else active_config.failure_action,
        "record_path": str(resolved_record_path),
    }
    result["report"] = _build_gate_report(result, report_title=active_config.report_title)

    record_gate_result(result, output_path=resolved_record_path, repo_root=resolved_repo_root)
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
    gate_name = str(result.get("gate") or GATE_NAME).strip().upper() or GATE_NAME
    resolved_output_path = _resolve_record_path(
        repo_root=repo_root,
        output_path=output_path or result.get("record_path"),
        timestamp=timestamp,
        gate_name=gate_name,
        results_dir=DEFAULT_RESULTS_DIR,
    )

    payload = dict(result)
    payload["record_path"] = str(resolved_output_path)

    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    return str(resolved_output_path)


def _run_core_components_check(
    resolved_repo_root: Path,
    pytest_args: Sequence[str] | None,
    config: GateConfig,
) -> dict[str, Any]:
    del resolved_repo_root, pytest_args
    kwargs: dict[str, Any] = {}
    if config.module_name != DEFAULT_MODULE_NAME:
        kwargs["module_name"] = config.module_name
    if config.components != DEFAULT_COMPONENTS:
        kwargs["components"] = config.components
    return check_core_components(**kwargs)


def _run_dependency_propagation_check(
    resolved_repo_root: Path,
    pytest_args: Sequence[str] | None,
    config: GateConfig,
) -> dict[str, Any]:
    del resolved_repo_root, pytest_args
    kwargs: dict[str, Any] = {}
    if config.module_name != DEFAULT_MODULE_NAME:
        kwargs["module_name"] = config.module_name
    return check_dependency_propagation(**kwargs)


def _run_manual_approval_check(
    resolved_repo_root: Path,
    pytest_args: Sequence[str] | None,
    config: GateConfig,
) -> dict[str, Any]:
    del resolved_repo_root, pytest_args
    kwargs: dict[str, Any] = {}
    if config.module_name != DEFAULT_MODULE_NAME:
        kwargs["module_name"] = config.module_name
    return check_manual_approval_points(**kwargs)


def _run_gate_module_imports_check(
    resolved_repo_root: Path,
    pytest_args: Sequence[str] | None,
    config: GateConfig,
) -> dict[str, Any]:
    del resolved_repo_root, pytest_args, config
    return check_gate_module_imports()


def _run_pytest_check(
    resolved_repo_root: Path,
    pytest_args: Sequence[str] | None,
    config: GateConfig,
) -> dict[str, Any]:
    effective_pytest_args = pytest_args if pytest_args is not None else config.default_pytest_args
    if effective_pytest_args:
        return run_all_tests(repo_root=resolved_repo_root, pytest_args=effective_pytest_args)
    return run_all_tests(repo_root=resolved_repo_root)


def _run_code_review_check(
    resolved_repo_root: Path,
    pytest_args: Sequence[str] | None,
    config: GateConfig,
) -> dict[str, Any]:
    del pytest_args
    if config.review_script is None:
        return {
            "check": "check_code_review_integration",
            "passed": True,
            "detail": "Code review integration not required for this gate",
            "script_path": None,
            "executable": False,
        }

    kwargs: dict[str, Any] = {"repo_root": resolved_repo_root}
    if Path(config.review_script) != DEFAULT_REVIEW_SCRIPT:
        kwargs["script_path"] = config.review_script
    return check_code_review_integration(**kwargs)


def _coerce_gate_invocation(
    gate_name: str | Path,
    repo_root: Path | str | None,
    config: GateConfig | None,
) -> tuple[str, Path | str | None]:
    resolved_repo_root = repo_root
    resolved_gate_name = gate_name

    if repo_root is None and _looks_like_repo_root(gate_name):
        resolved_repo_root = gate_name
        resolved_gate_name = config.gate_name if config is not None else GATE_NAME
    elif config is not None and str(gate_name).strip().upper() == GATE_NAME and config.gate_name != GATE_NAME:
        resolved_gate_name = config.gate_name

    normalized_gate_name = str(resolved_gate_name).strip().upper() or GATE_NAME
    return normalized_gate_name, resolved_repo_root


def _looks_like_repo_root(candidate: str | Path) -> bool:
    if isinstance(candidate, Path):
        return True
    if not isinstance(candidate, str):
        return False
    normalized = candidate.strip().upper()
    if normalized in KNOWN_GATES:
        return False
    return candidate.startswith(".") or "/" in candidate or "\\" in candidate


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
    gate_name: str = GATE_NAME,
    results_dir: Path | str = DEFAULT_RESULTS_DIR,
) -> Path:
    resolved_repo_root = _resolve_repo_root(repo_root)
    normalized_results_dir = Path(results_dir)
    if output_path is None:
        return resolved_repo_root / normalized_results_dir / _default_report_filename(timestamp, gate_name=gate_name)

    candidate = Path(output_path).expanduser()
    if not candidate.is_absolute():
        candidate = resolved_repo_root / candidate

    if candidate.suffix == "":
        candidate = candidate / _default_report_filename(timestamp, gate_name=gate_name)
    return candidate.resolve()


def _default_report_filename(timestamp: str, gate_name: str = GATE_NAME) -> str:
    compact_timestamp = re.sub(r"[^0-9A-Za-z]+", "", timestamp)
    return f"{gate_name.lower()}_gate_result_{compact_timestamp}.json"


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


def _build_gate_report(result: Mapping[str, Any], report_title: str | None = None) -> str:
    title = report_title or f"{result.get('gate', GATE_NAME)} Gate Report"
    lines = [
        title,
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


DEFAULT_CONFIG = GateConfig(
    gate_name="G3",
    checks=(
        _run_core_components_check,
        _run_pytest_check,
        _run_code_review_check,
    ),
    success_action="Ready for G4 gate validation",
    failure_action="Resolve blockers and re-run the G3 gate",
)
G3_CONFIG = DEFAULT_CONFIG
G4_CONFIG = GateConfig(
    gate_name="G4",
    checks=(
        _run_dependency_propagation_check,
        _run_pytest_check,
    ),
    components=PROPAGATION_COMPONENTS,
    review_script=None,
    default_pytest_args=(
        "tests/test_p4_03_propagation_engine.py",
        "tests/test_p4_06_memory_network.py",
        "tests/knowledge_compiler/test_gates.py",
        "tests/test_p4_08_g4_g6_gates.py",
    ),
    success_action="Ready for G5 manual approval",
    failure_action="Resolve propagation blockers and re-run the G4 gate",
)
G5_CONFIG = GateConfig(
    gate_name="G5",
    checks=(
        _run_manual_approval_check,
        _run_pytest_check,
    ),
    components=MANUAL_APPROVAL_COMPONENTS,
    review_script=None,
    default_pytest_args=(
        "tests/test_p4_04_governance_engine.py",
        "tests/knowledge_compiler/test_gates.py",
        "tests/test_p4_08_g4_g6_gates.py",
    ),
    success_action="Ready for G6 final acceptance",
    failure_action="Resolve approval blockers and re-run the G5 gate",
)
G6_CONFIG = GateConfig(
    gate_name="G6",
    checks=(
        _run_core_components_check,
        _run_dependency_propagation_check,
        _run_manual_approval_check,
        _run_gate_module_imports_check,
        _run_pytest_check,
    ),
    review_script=None,
    success_action="Phase 4 gate acceptance complete",
    failure_action="Resolve final acceptance blockers and re-run the G6 gate",
)
DEFAULT_GATE_CONFIGS: dict[str, GateConfig] = {
    "G3": G3_CONFIG,
    "G4": G4_CONFIG,
    "G5": G5_CONFIG,
    "G6": G6_CONFIG,
}


if __name__ == "__main__":
    gate_result = trigger_gate()
    print(gate_result["report"])
    raise SystemExit(0 if gate_result["passed"] else 1)
