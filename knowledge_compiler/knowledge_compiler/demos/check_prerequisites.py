#!/usr/bin/env python3
"""Check Phase 3 demo prerequisites for the AI-CFD Knowledge Harness.

This script validates the current repository state around Phase 3 analogical
execution:

- PermissionLevel L3 (EXPLORE) exists.
- EXPLORE mode is usable when a real executor is injected.
- The mock executor path is available via DRY_RUN.
- The default TrialRunner/AnalogicalOrchestrator wiring uses mock execution
  unless a real executor is injected.

Run directly:
    python3 knowledge_compiler/knowledge_compiler/demos/check_prerequisites.py
"""

from __future__ import annotations

import logging
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


def _find_repo_root(start: Path) -> Path:
    """Walk upward until the repository root is found."""
    for candidate in [start, *start.parents]:
        if (
            (candidate / "knowledge_compiler/phase2/execution_layer/failure_handler.py").exists()
            and (candidate / "knowledge_compiler/phase3/orchestrator/analogy_engine.py").exists()
            and (candidate / "tests/phase3/test_permission_level_l3.py").exists()
        ):
            return candidate
    raise RuntimeError(f"Could not locate repository root from {start}")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Keep the script output focused on the report instead of library logging.
logging.getLogger().setLevel(logging.CRITICAL)
logging.getLogger("knowledge_compiler.phase3.orchestrator.analogy_engine").setLevel(
    logging.CRITICAL
)


ACTUAL_FAILURE_HANDLER = REPO_ROOT / "knowledge_compiler/phase2/execution_layer/failure_handler.py"
ACTUAL_ANALOGY_ENGINE = REPO_ROOT / "knowledge_compiler/phase3/orchestrator/analogy_engine.py"
REQUESTED_FAILURE_HANDLER = (
    REPO_ROOT
    / "knowledge_compiler/knowledge_compiler/phase2/execution_layer/failure_handler.py"
)
REQUESTED_ANALOGY_ENGINE = (
    REPO_ROOT
    / "knowledge_compiler/knowledge_compiler/phase3/orchestrator/analogy_engine.py"
)


@dataclass
class CheckResult:
    name: str
    ok: bool
    summary: str
    details: Dict[str, Any]


def _make_store():
    """Small knowledge store for orchestrator smoke tests."""

    class _Store:
        def list_cases(self) -> List[Dict[str, Any]]:
            return [{"case_id": "CASE-001"}]

        def get_case_features(self, case_id: str) -> Dict[str, Any]:
            return {
                "case_id": case_id,
                "geometry": {"shape": "channel", "dimensions": [1.0, 0.5]},
                "physics": {"Re": 1200, "flow_type": "internal"},
                "boundary": {"inlet": "velocity", "outlet": "pressure"},
                "flow_regime": {"solver_type": "simpleFoam"},
            }

        def get_patterns(self, tags=None) -> List[Dict[str, Any]]:
            return []

        def get_rules(self, tags=None) -> List[Dict[str, Any]]:
            return []

    return _Store()


def _make_target_features() -> Dict[str, Any]:
    return {
        "case_id": "TARGET-001",
        "geometry": {"shape": "channel", "dimensions": [1.0, 0.5]},
        "physics": {"Re": 1000, "flow_type": "internal"},
        "boundary": {"inlet": "velocity", "outlet": "pressure"},
        "flow_regime": {"solver_type": "simpleFoam"},
    }


def check_explore_mode() -> CheckResult:
    from knowledge_compiler.phase2.execution_layer.failure_handler import PermissionLevel
    from knowledge_compiler.phase3.analogy_schema import (
        AnalogySpec,
        CandidatePlan,
        ExplorationBudget,
        TrialStatus,
    )
    from knowledge_compiler.phase3.orchestrator.analogy_engine import (
        AnalogicalOrchestrator,
        TrialRunner,
    )

    runner_calls = {"count": 0}

    def injected_executor(params: Dict[str, Any]) -> Dict[str, Any]:
        runner_calls["count"] += 1
        return {
            "output": {
                "real": True,
                "mesh_cells": params.get("mesh_cells", 0),
                "final_residual": 0.001,
                "status": "converged",
            },
            "convergence": {
                "residuals": [1.0, 0.1, 0.01, 0.001],
                "converged": True,
            },
        }

    plan = CandidatePlan(
        description="EXPLORE smoke test",
        estimated_cost=0.1,
        execution_params={"mesh_cells": 1200, "time_steps": 25},
    )
    budget = ExplorationBudget(max_trials=1)
    runner = TrialRunner(
        executor=injected_executor,
        permission_level=PermissionLevel.EXPLORE,
    )
    trial = runner.run_trial(plan, budget)

    orchestrator_calls = {"count": 0}

    def orchestrator_executor(params: Dict[str, Any]) -> Dict[str, Any]:
        orchestrator_calls["count"] += 1
        return {
            "output": {
                "real": True,
                "mesh_cells": params.get("mesh_cells", 0),
                "final_residual": 0.001,
                "status": "converged",
            },
            "convergence": {
                "residuals": [1.0, 0.1, 0.01, 0.001],
                "converged": True,
            },
        }

    orchestrator = AnalogicalOrchestrator(
        _make_store(),
        executor=orchestrator_executor,
        permission_level=PermissionLevel.EXPLORE,
    )
    spec = AnalogySpec(
        target_case_id="TARGET-001",
        permission_level=PermissionLevel.EXPLORE.value,
        budget=ExplorationBudget(max_trials=1),
    )
    spec = orchestrator.run(spec, target_features=_make_target_features())

    ok = all(
        [
            hasattr(PermissionLevel, "EXPLORE"),
            PermissionLevel.EXPLORE.value == "explore",
            runner._permission_level == PermissionLevel.EXPLORE,
            trial.status == TrialStatus.COMPLETED,
            trial.output_data.get("real") is True,
            trial.output_data.get("is_mock") is not True,
            runner_calls["count"] == 1,
            budget.trials_used == 1,
            spec.permission_level == "explore",
            spec.allows_real_execution is True,
            orchestrator_calls["count"] >= 1,
            len(spec.trial_results) >= 1,
            any(t.output_data.get("real") is True for t in spec.trial_results),
        ]
    )

    summary = (
        "EXPLORE is implemented and usable with an injected executor."
        if ok
        else "EXPLORE is defined but not fully usable."
    )
    return CheckResult(
        name="PermissionLevel L3 EXPLORE",
        ok=ok,
        summary=summary,
        details={
            "enum_exists": hasattr(PermissionLevel, "EXPLORE"),
            "enum_value": getattr(PermissionLevel.EXPLORE, "value", None),
            "runner_status": trial.status.value,
            "runner_budget_trials_used": budget.trials_used,
            "runner_called_injected_executor": runner_calls["count"],
            "runner_output_is_mock": trial.output_data.get("is_mock", False),
            "orchestrator_permission_level": orchestrator._permission_level.value,
            "orchestrator_trial_count": len(spec.trial_results),
            "orchestrator_called_injected_executor": orchestrator_calls["count"],
            "orchestrator_has_real_trial": any(
                t.output_data.get("real") is True for t in spec.trial_results
            ),
        },
    )


def check_mock_executor() -> CheckResult:
    from knowledge_compiler.phase2.execution_layer.failure_handler import PermissionLevel
    from knowledge_compiler.phase3.analogy_schema import CandidatePlan, ExplorationBudget, TrialStatus
    from knowledge_compiler.phase3.orchestrator.analogy_engine import TrialRunner

    injected_calls = {"count": 0}

    def should_not_run(params: Dict[str, Any]) -> Dict[str, Any]:
        injected_calls["count"] += 1
        return {"output": {"real": True}, "convergence": {}}

    runner = TrialRunner(
        executor=should_not_run,
        permission_level=PermissionLevel.DRY_RUN,
    )
    plan = CandidatePlan(
        description="DRY_RUN smoke test",
        estimated_cost=0.05,
        execution_params={"mesh_cells": 800, "time_steps": 20},
    )
    budget = ExplorationBudget(max_trials=1)
    trial = runner.run_trial(plan, budget)
    default_output = TrialRunner._default_executor({"mesh_cells": 100, "time_steps": 5})

    ok = all(
        [
            hasattr(TrialRunner, "_default_executor"),
            trial.status == TrialStatus.COMPLETED,
            trial.output_data.get("is_mock") is True,
            injected_calls["count"] == 0,
            budget.trials_used == 1,
            default_output["output"].get("is_mock") is True,
        ]
    )
    summary = (
        "Mock executor is available; DRY_RUN forces it and ignores injected executors."
        if ok
        else "Mock executor path is missing or not behaving as expected."
    )
    return CheckResult(
        name="Mock Executor",
        ok=ok,
        summary=summary,
        details={
            "trial_status": trial.status.value,
            "trial_output_is_mock": trial.output_data.get("is_mock", False),
            "injected_executor_calls": injected_calls["count"],
            "budget_trials_used": budget.trials_used,
            "default_executor_marks_mock": default_output["output"].get("is_mock", False),
        },
    )


def check_default_demo_executor() -> CheckResult:
    from knowledge_compiler.phase3.analogy_schema import AnalogySpec, CandidatePlan, ExplorationBudget
    from knowledge_compiler.phase3.orchestrator.analogy_engine import AnalogicalOrchestrator, TrialRunner

    runner = TrialRunner()
    plan = CandidatePlan(
        description="default runner smoke test",
        execution_params={"mesh_cells": 500, "time_steps": 10},
    )
    runner_budget = ExplorationBudget(max_trials=1)
    trial = runner.run_trial(plan, runner_budget)

    orchestrator = AnalogicalOrchestrator(_make_store())
    spec = AnalogySpec(target_case_id="TARGET-001", budget=ExplorationBudget(max_trials=1))
    spec = orchestrator.run(spec, target_features=_make_target_features())

    is_mock_runner = trial.output_data.get("is_mock") is True
    orchestrator_mock_trials = [
        t for t in spec.trial_results if t.output_data.get("is_mock") is True
    ]
    default_uses_mock = is_mock_runner and len(orchestrator_mock_trials) >= 1
    executor_type = "mock" if default_uses_mock else "non_mock"

    summary = (
        "Default EXPLORE wiring uses the built-in mock executor, not a real solver."
        if default_uses_mock
        else "Default EXPLORE wiring appears to use a non-mock executor."
    )
    return CheckResult(
        name="Default E2E Executor",
        ok=True,
        summary=summary,
        details={
            "default_executor_type": executor_type,
            "trial_runner_default_permission_level": runner._permission_level.value,
            "trial_runner_default_output_is_mock": trial.output_data.get("is_mock", False),
            "orchestrator_default_permission_level": orchestrator._permission_level.value,
            "orchestrator_trial_count": len(spec.trial_results),
            "orchestrator_mock_trial_count": len(orchestrator_mock_trials),
            "recommended_command": (
                "python3 -m pytest "
                "tests/phase3/test_permission_level_l3.py "
                "tests/phase3/test_analogy_engine.py -v"
            ),
            "why_this_command": (
                "The repo has no standalone Phase 3 demo script; Phase 3 is exercised "
                "through pytest-based full-pipeline tests documented in README.md."
            ),
        },
    )


def build_report() -> Dict[str, Any]:
    results = [
        check_explore_mode(),
        check_mock_executor(),
        check_default_demo_executor(),
    ]

    overall_ok = all(result.ok for result in results[:2])
    fixes: List[str] = []

    if not results[0].ok:
        fixes.append(
            "L3 EXPLORE must define PermissionLevel.EXPLORE and route TrialRunner/"
            "AnalogicalOrchestrator through a non-mock executor when one is injected."
        )

    if not results[1].ok:
        fixes.append(
            "TrialRunner DRY_RUN must keep a working mock executor path and force it even "
            "when another executor is injected."
        )

    if results[2].details["default_executor_type"] == "mock":
        fixes.append(
            "If you want a real-solver Phase 3 E2E demo, wire AnalogicalOrchestrator/"
            "TrialRunner to knowledge_compiler.phase3.solver_runner.runner.SolverRunner "
            "or another real executor; the current default path is still mock."
        )

    report = {
        "repo_root": str(REPO_ROOT),
        "requested_paths_exist": {
            "failure_handler": REQUESTED_FAILURE_HANDLER.exists(),
            "analogy_engine": REQUESTED_ANALOGY_ENGINE.exists(),
        },
        "actual_paths": {
            "failure_handler": str(ACTUAL_FAILURE_HANDLER),
            "analogy_engine": str(ACTUAL_ANALOGY_ENGINE),
        },
        "checks": [
            {
                "name": result.name,
                "ok": result.ok,
                "summary": result.summary,
                "details": result.details,
            }
            for result in results
        ],
        "overall_ok": overall_ok,
        "recommended_command": results[2].details["recommended_command"],
        "fixes": fixes,
    }
    report["markdown"] = format_markdown(report)
    return report


def format_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Phase 3 Prerequisites Check",
        "",
        f"- Repo root: `{report['repo_root']}`",
        "- Requested nested source paths exist: "
        f"`failure_handler={report['requested_paths_exist']['failure_handler']}`, "
        f"`analogy_engine={report['requested_paths_exist']['analogy_engine']}`",
        f"- Actual `failure_handler.py`: `{report['actual_paths']['failure_handler']}`",
        f"- Actual `analogy_engine.py`: `{report['actual_paths']['analogy_engine']}`",
        "",
    ]

    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        lines.append(f"## {check['name']}: {status}")
        lines.append("")
        lines.append(f"- {check['summary']}")
        for key, value in check["details"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")

    lines.extend(
        [
            "## Recommended Command",
            "",
            f"```bash\n{report['recommended_command']}\n```",
            "",
            "## Action Required",
            "",
        ]
    )

    if report["fixes"]:
        for fix in report["fixes"]:
            lines.append(f"- {fix}")
    else:
        lines.append("- No immediate fixes required.")

    return "\n".join(lines)


def main() -> int:
    try:
        report = build_report()
        print(report["markdown"])
        return 0 if report["overall_ok"] else 1
    except Exception as exc:  # pragma: no cover - defensive CLI path
        print("# Phase 3 Prerequisites Check", file=sys.stderr)
        print("", file=sys.stderr)
        print(f"- ERROR: {exc}", file=sys.stderr)
        print("", file=sys.stderr)
        print("```text", file=sys.stderr)
        print(traceback.format_exc().rstrip(), file=sys.stderr)
        print("```", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
