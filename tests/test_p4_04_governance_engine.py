#!/usr/bin/env python3
"""
Test P4-04: GovernanceEngine

Coverage:
1. ValidationResult and GovernanceDecision dataclasses
2. Completeness / honesty / schema / executable / semantic checks
3. Model assignment validation
4. Publish approval, rejection, deferral, and propagation gating
"""

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.executables.diff_engine import ChangeType, DiffReport
from knowledge_compiler.memory_network import (
    GovernanceDecision,
    GovernanceEngine,
    ValidationResult,
)


KNOWLEDGE_COMPILER_PATH = Path(__file__).parent.parent / "knowledge_compiler"


def make_canonical_formula_unit():
    """Return a canonical unit that satisfies all governance checks."""
    return {
        "layer": "canonical",
        "canonical_id": "CANON-formula-001",
        "parsed_id": "PARSED-001",
        "normalized_form": {
            "unit_type": "formula",
            "unit_id": "FORM-009",
            "spec_version": "v1.1",
            "canonical_content": {
                "definition": "GCI_{12} = |epsilon_{12}| / (r^p - 1) * 100%",
                "notes": [
                    "Zero-reference handling uses explicit near-zero strategy.",
                    "Grid independence requires GCI < 5%.",
                ],
            },
        },
        "spec_version": "v1.1",
        "unit_type": "formula",
        "normalized_at": "2026-04-07T12:00:00Z",
        "normalize_rule_version": "1.0",
        "conflict_flags": [],
        "data_gaps": [],
    }


def make_raw_unit():
    """Return a complete raw-layer unit."""
    return {
        "layer": "raw",
        "raw_id": "RAW-001",
        "source_file": "Phase1-ReportSpec-Candidate.md",
        "raw_text": "CFD validation section with source-mapped data.",
        "capture_timestamp": "2026-04-07T12:00:00Z",
        "capture_method": "file_read",
        "source_line_range": [10, 20],
        "parser_version": "1.0",
        "parent_raw_id": None,
    }


def make_executable_unit():
    """Return an executable-layer unit with non-empty test cases."""
    return {
        "layer": "executable",
        "executable_id": "EXEC-formula-001",
        "canonical_id": "CANON-formula-001",
        "executable_code": "def validate():\n    return True\n",
        "language": "python",
        "asset_type": "formula_validator",
        "test_cases": [
            {
                "test_id": "TC-001",
                "input": {"value": 1},
                "expected_output": {"value": 1},
                "pass_criterion": "value is preserved",
            }
        ],
        "compiled_at": "2026-04-07T12:00:00Z",
        "compile_rule_version": "1.0",
    }


class TestGovernanceDataclasses:
    """Test governance data models."""

    def test_validation_result_dataclass(self):
        result = ValidationResult(
            passed=False,
            failed_checks=["missing spec_version"],
            warnings=["declared data gap"],
        )

        assert result.passed is False
        assert result.failed_checks == ["missing spec_version"]
        assert result.warnings == ["declared data gap"]

    def test_governance_decision_dataclass(self):
        decision = GovernanceDecision(
            status=GovernanceDecision.APPROVED,
            reasons=["All governance checks passed"],
            warnings=[],
        )

        assert decision.status == GovernanceDecision.APPROVED
        assert decision.reasons == ["All governance checks passed"]
        assert decision.warnings == []

    def test_governance_decision_rejects_invalid_status(self):
        with pytest.raises(ValueError):
            GovernanceDecision(status="UNKNOWN")


class TestGovernanceChecks:
    """Test individual governance checks."""

    def test_check_completeness_passes_for_valid_canonical_unit(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)

        result = engine.check_completeness(make_canonical_formula_unit())

        assert result.passed is True
        assert result.failed_checks == []

    def test_check_completeness_fails_for_missing_line_range_and_version_tag(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        unit = make_raw_unit()
        unit.pop("source_line_range")
        unit.pop("parser_version")

        result = engine.check_completeness(unit)

        assert result.passed is False
        assert any("Source line ranges" in failure for failure in result.failed_checks)
        assert any("Version tags" in failure for failure in result.failed_checks)

    def test_check_data_honesty_allows_documented_or_nullable_nulls(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        unit = make_raw_unit()
        unit["annotations"] = {"review_note": None}
        unit["documented_null_fields"] = ["annotations.review_note"]

        result = engine.check_data_honesty(unit)

        assert result.passed is True
        assert result.failed_checks == []

    def test_check_data_honesty_rejects_undeclared_null_and_fabrication(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        unit = make_canonical_formula_unit()
        unit["normalized_form"]["canonical_content"]["definition"] = None
        unit["fabrication_detected"] = True

        result = engine.check_data_honesty(unit)

        assert result.passed is False
        assert any("Undocumented null value" in failure for failure in result.failed_checks)
        assert any("Fabrication" in failure for failure in result.failed_checks)

    def test_check_data_honesty_rejects_cl_cd_claim_for_known_missing_source(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        unit = make_canonical_formula_unit()
        unit["source"] = "Thomas&Loutun 2021 PDF"
        unit["normalized_form"]["canonical_content"]["cl"] = 0.42

        result = engine.check_data_honesty(unit)

        assert result.passed is False
        assert any("Thomas&Loutun" in failure for failure in result.failed_checks)

    def test_check_schema_compliance_rejects_wrong_spec_version(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        unit = make_canonical_formula_unit()
        unit["spec_version"] = "v1.0"

        result = engine.check_schema_compliance(unit)

        assert result.passed is False
        assert any("Canonical spec_version must be v1.1" in failure for failure in result.failed_checks)

    def test_check_schema_compliance_rejects_invalid_parsed_unit_type(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        unit = {
            "layer": "parsed",
            "parsed_id": "PARSED-001",
            "raw_id": "RAW-001",
            "structured_data": {
                "unit_type": "invalid_type",
                "unit_id": "UNIT-001",
                "content": {"summary": "test"},
            },
            "parser_version": "1.0",
            "parsed_at": "2026-04-07T12:00:00Z",
            "parse_rule_version": "1.0",
        }

        result = engine.check_schema_compliance(unit)

        assert result.passed is False
        assert any("structured_data.unit_type" in failure for failure in result.failed_checks)

    def test_check_schema_compliance_rejects_empty_executable_test_cases(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        unit = make_executable_unit()
        unit["test_cases"] = []

        result = engine.check_schema_compliance(unit)

        assert result.passed is False
        assert any("non-empty test_cases" in failure for failure in result.failed_checks)

    def test_check_semantic_correctness_rejects_placeholder_content(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        unit = make_canonical_formula_unit()
        unit["normalized_form"]["canonical_content"]["definition"] = "TODO"

        result = engine.check_semantic_correctness(unit)

        assert result.passed is False
        assert any("Placeholder" in failure for failure in result.failed_checks)

    def test_check_semantic_correctness_rejects_gci_formula_with_wrong_structure(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        unit = make_canonical_formula_unit()
        unit["normalized_form"]["canonical_content"]["definition"] = (
            "GCI = |epsilon| / (r + 1) * 100%"
        )

        result = engine.check_semantic_correctness(unit)

        assert result.passed is False
        assert any("GCI formula" in failure for failure in result.failed_checks)

    def test_check_executable_validation_runs_project_suite(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)

        result = engine.check_executable_validation(make_canonical_formula_unit())

        assert result.passed is True
        assert result.failed_checks == []


class TestModelAssignment:
    """Test model assignment rules from model_rules_v1.2_with_codex_cr.md."""

    def test_validate_model_assignment_accepts_codex_for_p2(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)

        assert engine.validate_model_assignment("P2 Knowledge Compiler", "Codex (GPT-5.4)")

    def test_validate_model_assignment_rejects_wrong_model(self):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)

        assert not engine.validate_model_assignment("架构审查", "Codex (GPT-5.4)")
        assert not engine.validate_model_assignment("Gate Final Approval", "Opus 4.6")


class TestApprovePublish:
    """Test aggregate governance decisions."""

    def test_approve_publish_returns_approved_when_all_checks_pass(self, monkeypatch):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        monkeypatch.setattr(
            engine,
            "_run_executable_validation_suite",
            lambda: {
                "formula_validator": {"passed": True, "detail": "ok"},
                "chart_template": {"passed": True, "detail": "ok"},
                "bench_ghia1982": {"passed": True, "detail": "ok"},
                "bench_naca": {"passed": True, "detail": "ok"},
            },
        )

        decision = engine.approve_publish(make_canonical_formula_unit())

        assert decision.status == GovernanceDecision.APPROVED
        assert decision.reasons == ["All governance checks passed"]

    def test_approve_publish_returns_rejected_when_validation_fails(self, monkeypatch):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        monkeypatch.setattr(
            engine,
            "_run_executable_validation_suite",
            lambda: {
                "formula_validator": {"passed": True, "detail": "ok"},
                "chart_template": {"passed": True, "detail": "ok"},
                "bench_ghia1982": {"passed": True, "detail": "ok"},
                "bench_naca": {"passed": True, "detail": "ok"},
            },
        )
        unit = make_canonical_formula_unit()
        unit["conflict_flags"] = ["duplicate evidence"]

        decision = engine.approve_publish(unit)

        assert decision.status == GovernanceDecision.REJECTED
        assert any("Conflict flags present" in reason for reason in decision.reasons)

    def test_approve_publish_returns_deferred_for_missing_human_signoff(self, monkeypatch):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        monkeypatch.setattr(
            engine,
            "_run_executable_validation_suite",
            lambda: {
                "formula_validator": {"passed": True, "detail": "ok"},
                "chart_template": {"passed": True, "detail": "ok"},
                "bench_ghia1982": {"passed": True, "detail": "ok"},
                "bench_naca": {"passed": True, "detail": "ok"},
            },
        )
        unit = make_canonical_formula_unit()
        unit["requires_human_review"] = True
        unit["human_review_signed_off"] = False

        decision = engine.approve_publish(unit)

        assert decision.status == GovernanceDecision.DEFERRED
        assert any("Human review sign-off" in reason for reason in decision.reasons)

    def test_approve_publish_defers_when_propagation_engine_halts(self, monkeypatch):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        monkeypatch.setattr(
            engine,
            "_run_executable_validation_suite",
            lambda: {
                "formula_validator": {"passed": True, "detail": "ok"},
                "chart_template": {"passed": True, "detail": "ok"},
                "bench_ghia1982": {"passed": True, "detail": "ok"},
                "bench_naca": {"passed": True, "detail": "ok"},
            },
        )
        unit = make_canonical_formula_unit()
        unit["propagation_changes"] = [
            DiffReport(
                change_type=ChangeType.DELETE,
                unit_id="FORM-009",
                field="__unit__",
                old_value={"path": "units/formulas.yaml"},
                new_value=None,
                impacted_executables=["EXEC-FORMULA-VALIDATOR-001"],
            )
        ]

        decision = engine.approve_publish(unit)

        assert decision.status == GovernanceDecision.DEFERRED
        assert len(decision.propagation_decisions) == 1
        assert decision.propagation_decisions[0].action_type == "halt"

    def test_approve_publish_does_not_propagate_when_rejected(self, monkeypatch):
        engine = GovernanceEngine(base_path=KNOWLEDGE_COMPILER_PATH)
        monkeypatch.setattr(
            engine,
            "_run_executable_validation_suite",
            lambda: {
                "formula_validator": {"passed": True, "detail": "ok"},
                "chart_template": {"passed": True, "detail": "ok"},
                "bench_ghia1982": {"passed": True, "detail": "ok"},
                "bench_naca": {"passed": True, "detail": "ok"},
            },
        )

        calls = {"count": 0}

        def fake_propagate(*args, **kwargs):
            calls["count"] += 1
            return []

        monkeypatch.setattr(engine.propagation_engine, "propagate", fake_propagate)

        unit = make_canonical_formula_unit()
        unit["conflict_flags"] = ["manual review"]
        unit["propagation_changes"] = [
            DiffReport(
                change_type=ChangeType.NEW,
                unit_id="FORM-010",
                field="__unit__",
                old_value=None,
                new_value={"path": "units/formulas.yaml"},
                impacted_executables=[],
            )
        ]

        decision = engine.approve_publish(unit)

        assert decision.status == GovernanceDecision.REJECTED
        assert calls["count"] == 0
        assert any("Propagation blocked" in warning for warning in decision.warnings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
