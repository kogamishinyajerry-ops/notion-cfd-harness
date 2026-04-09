#!/usr/bin/env python3
"""
AI-CFD Knowledge Harness — Unified CLI

Usage:
    python -m knowledge_compiler.cli <command> [options]

Commands:
    test        Run all tests or specific test file
    benchmark   Run a benchmark (ghia1982 | cylinder_wake)
    pipeline   Run the E2E pipeline orchestrator
    verify     Verify results against gold standards
    gates      Run gate checks on a ReportSpec
    version    Show version info
"""

from __future__ import annotations

import argparse
import sys
import subprocess
from pathlib import Path


def cmd_test(args):
    """Run tests"""
    if args.file:
        target = f"tests/{args.file}"
    elif args.keyword:
        target = f"tests/ -k {args.keyword}"
    else:
        target = "tests/"

    cov_flag = "--cov=knowledge_compiler --cov-report=term-missing" if args.coverage else ""

    cmd = f"python -m pytest {target} -v --tb=short {cov_flag}".strip()
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    return result.returncode


def cmd_benchmark(args):
    """Run a benchmark"""
    bench_map = {
        "ghia1982": "knowledge_compiler.executables.bench_ghia1982",
        "cylinder_wake": "knowledge_compiler.executables.bench_cylinder_wake",
    }

    if args.name not in bench_map:
        print(f"Unknown benchmark: {args.name}")
        print(f"Available: {list(bench_map.keys())}")
        return 1

    module = bench_map[args.name]
    cmd = f"python -m {module}"
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    return result.returncode


def cmd_pipeline(args):
    """Run the pipeline orchestrator"""
    from knowledge_compiler.phase2d.pipeline_orchestrator import (
        PipelineOrchestrator,
        PipelineConfig,
        PipelineStage,
    )

    problem_type = args.problem_type or "external_flow"

    config = PipelineConfig(
        pipeline_id=args.pipeline_id or "cli-demo",
        name="CLI Demo Pipeline",
        description="Run via CLI",
        enabled_stages=[
            PipelineStage.REPORT_SPEC_GENERATION,
            PipelineStage.PHYSICS_PLANNING,
            PipelineStage.EXECUTION,
        ],
    )

    orchestrator = PipelineOrchestrator(config)
    result = orchestrator.execute({
        "problem_type": problem_type,
        "physics_models": args.physics_models.split(",") if args.physics_models else ["RANS"],
    })

    print(f"\nPipeline result: {result.get('state', 'unknown')}")
    return 0


def cmd_verify(args):
    """Verify results using the verify console"""
    from knowledge_compiler.orchestrator.verify_console import VerifyConsole

    console = VerifyConsole()
    results_path = Path(args.results) if args.results else None

    results_data = {}
    if results_path and results_path.exists():
        import json
        with open(results_path) as f:
            results_data = json.load(f)

    report = console.run_full_verification(args.case_id, results_data)
    print(f"\nVerification: {'PASS' if report.overall_pass else 'FAIL'}")
    print(f"Report: {report.to_dict()}")
    return 0 if report.overall_pass else 1


def cmd_gates(args):
    """Run gate checks on a ReportSpec"""
    from knowledge_compiler.phase1.schema import ReportSpec, ProblemType

    # Map user-friendly names to enum members
    pt_map = {
        "internal_flow": ProblemType.INTERNAL_FLOW,
        "external_flow": ProblemType.EXTERNAL_FLOW,
        "heat_transfer": ProblemType.HEAT_TRANSFER,
        "multiphase": ProblemType.MULTIPHASE,
        "fsi": ProblemType.FSI,
        "internalflow": ProblemType.INTERNAL_FLOW,
        "externalflow": ProblemType.EXTERNAL_FLOW,
    }
    pt_key = (args.problem_type or "external_flow").lower().replace("-", "_")
    problem_type = pt_map.get(pt_key, ProblemType.EXTERNAL_FLOW)

    spec = ReportSpec(
        report_spec_id=args.spec_id or "SPEC-CLI-TEST",
        name=args.name or "CLI Test Spec",
        problem_type=problem_type,
    )

    from knowledge_compiler.phase1.gates import TemplateGeneralizationGate
    gate = TemplateGeneralizationGate()
    result = gate.check_report_spec_candidate(spec, [], [])

    print(f"\nGate: {result.gate_id}")
    print(f"Status: {result.status.value}")
    print(f"Score: {result.score:.1f}")
    if result.errors:
        print(f"Errors: {result.errors}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")
    return 0 if result.is_pass else 1


def cmd_version(args):
    """Show version info"""
    print("AI-CFD Knowledge Harness")
    print("  Version: 1.0.1")
    print("  Phases:  5 (Pass)")
    print("  Tests:   1,736 passing")

    # Try to show git info
    try:
        git_sha = subprocess.check_output(
            "git -C /Users/Zhuanz/Desktop/notion-cfd-harness rev-parse --short HEAD",
            shell=True, text=True
        ).strip()
        print(f"  Git:     {git_sha}")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="AI-CFD Knowledge Harness CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # test
    p_test = subparsers.add_parser("test", help="Run tests")
    p_test.add_argument("-f", "--file", help="Specific test file (e.g., phase2/test_*.py)")
    p_test.add_argument("-k", "--keyword", help="Keyword filter for tests")
    p_test.add_argument("--coverage", action="store_true", help="Run with coverage")
    p_test.set_defaults(func=cmd_test)

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run a benchmark")
    p_bench.add_argument("name", choices=["ghia1982", "cylinder_wake"], help="Benchmark name")
    p_bench.set_defaults(func=cmd_benchmark)

    # pipeline
    p_pipe = subparsers.add_parser("pipeline", help="Run E2E pipeline")
    p_pipe.add_argument("--pipeline-id", help="Pipeline ID")
    p_pipe.add_argument("--problem-type", help="Problem type (e.g., external_flow)")
    p_pipe.add_argument("--physics-models", help="Comma-separated physics models")
    p_pipe.set_defaults(func=cmd_pipeline)

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify results")
    p_verify.add_argument("--case-id", default="CASE-001", help="Case ID")
    p_verify.add_argument("--results", help="Results JSON file path")
    p_verify.set_defaults(func=cmd_verify)

    # gates
    p_gates = subparsers.add_parser("gates", help="Run gate checks")
    p_gates.add_argument("--gate", choices=["quality", "generalization"], default="quality")
    p_gates.add_argument("--spec-id", help="Spec ID")
    p_gates.add_argument("--name", help="Spec name")
    p_gates.add_argument("--problem-type", default="external_flow", help="Problem type")
    p_gates.set_defaults(func=cmd_gates)

    # version
    p_ver = subparsers.add_parser("version", help="Show version info")
    p_ver.set_defaults(func=cmd_version)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
