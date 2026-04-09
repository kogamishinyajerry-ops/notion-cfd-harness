#!/usr/bin/env python3
"""Tests for the deterministic M1 E2E mock demo module."""

from __future__ import annotations

import subprocess
import sys

import pytest

from knowledge_compiler.demos.e2e_mock_demo import (
    E2E_DEMO_CASES,
    E2EResult,
    get_mock_result_for_case,
    print_summary,
    run_all_demos,
    run_e2e_mock_demo,
)


def test_get_mock_result_for_each_default_case() -> None:
    results = [get_mock_result_for_case(case_id) for case_id in E2E_DEMO_CASES]

    assert [result.case_id for result in results] == E2E_DEMO_CASES
    assert all(isinstance(result, E2EResult) for result in results)
    assert all(result.passed for result in results)
    assert all(result.status == "PASS" for result in results)


def test_run_e2e_mock_demo_matches_helper() -> None:
    result = run_e2e_mock_demo("BENCH-07")

    assert result == get_mock_result_for_case("BENCH-07")
    assert result.metric_name == "reattachment_length_normalized"
    assert result.relative_error < result.error_threshold


def test_run_all_demos_returns_three_passing_results() -> None:
    results = run_all_demos()

    assert len(results) == 3
    assert [result.case_id for result in results] == E2E_DEMO_CASES
    assert sum(result.passed for result in results) == 3


def test_print_summary_reports_three_of_three_pass(capsys: pytest.CaptureFixture[str]) -> None:
    output = print_summary(run_all_demos())
    captured = capsys.readouterr()

    assert output == captured.out.strip()
    assert "Summary: 3/3 PASS" in output
    assert "[PASS] BENCH-01" in output
    assert "[PASS] BENCH-07" in output
    assert "[PASS] BENCH-04" in output


def test_get_mock_result_rejects_unknown_case() -> None:
    with pytest.raises(ValueError, match="Unsupported demo case 'BENCH-99'"):
        get_mock_result_for_case("BENCH-99")


def test_module_cli_outputs_three_of_three_pass() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "knowledge_compiler.demos.e2e_mock_demo"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Summary: 3/3 PASS" in completed.stdout
