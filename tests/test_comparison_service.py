"""ComparisonService unit tests — PIPE-11."""
import pytest, json
from pathlib import Path

from api_server.services.comparison_service import parse_convergence_log, ComparisonService
from api_server.models import ComparisonCreate


def test_parse_convergence_log_empty(tmp_path):
    result = parse_convergence_log(tmp_path)
    assert result == []


def test_parse_convergence_log_parses_time_and_residuals(tmp_path):
    log = tmp_path / "log.simpleFoam"
    log.write_text("Time = 1\nUx = 1e-01 Uy = 2e-01 Uz = 3e-01 p = 1e+00\nTime = 2\nUx = 1e-02 Uy = 2e-02 Uz = 3e-02 p = 1e-01\n")
    result = parse_convergence_log(tmp_path)
    assert len(result) == 2
    assert result[0]["iteration"] == 0
    assert result[0]["Ux"] == pytest.approx(0.1)
    assert result[1]["p"] == pytest.approx(0.1)


def test_comparison_service_smoke(temp_db):
    """Smoke test: SweepDBService instantiates and has comparison methods."""
    from api_server.services.pipeline_db import SweepDBService
    svc = SweepDBService()
    assert hasattr(svc, 'get_all_completed_cases')
    assert hasattr(svc, 'add_comparison')
    assert hasattr(svc, 'get_comparison')
    assert hasattr(svc, 'list_comparisons')


def test_parse_convergence_log_missing_file(tmp_path):
    result = parse_convergence_log(tmp_path)
    assert result == []


def test_parse_convergence_log_partial_residuals(tmp_path):
    log = tmp_path / "log.simpleFoam"
    log.write_text("Time = 1\nUx = 1e-01 p = 1e+00\nTime = 2\nUx = 1e-02 p = 1e-01\n")
    result = parse_convergence_log(tmp_path)
    assert len(result) == 2
    assert result[0]["Ux"] == pytest.approx(0.1)
    assert result[0]["p"] == pytest.approx(1.0)
    assert "Uy" not in result[0]
