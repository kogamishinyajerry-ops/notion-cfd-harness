#!/usr/bin/env python3
"""
diff_engine.py pytest coverage.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

import diff_engine


def _manifest() -> dict:
    return {
        "baseline_version": "v1.0",
        "baseline_commit": "baseline",
        "baseline_date": "2026-04-07",
        "baseline_files": {
            "total": 16,
            "root": [
                "BASELINE-v1.md",
                "diff_engine.md",
                "publish_contract.md",
            ],
            "units": [
                "units/chapters.yaml",
                "units/chart_rules.yaml",
                "units/data_points.yaml",
                "units/evidence.yaml",
                "units/formulas.yaml",
            ],
            "schema": [
                "schema/raw_schema.json",
                "schema/parsed_schema.json",
                "schema/canonical_schema.json",
                "schema/executable_schema.json",
            ],
            "executables": [
                "executables/bench_ghia1982.py",
                "executables/bench_cylinder_wake.py",
                "executables/chart_template.py",
                "executables/formula_validator.py",
            ],
        },
    }


def _write_tree(root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _base_files() -> dict[str, str]:
    return {
        "BASELINE_MANIFEST.json": json.dumps(_manifest(), ensure_ascii=False, indent=2),
        "BASELINE-v1.md": "# Knowledge Compiler BASELINE v1.0\n",
        "diff_engine.md": "Diff spec v1.0\n",
        "publish_contract.md": "Diff engine must show no untracked changes.\n",
        "units/chapters.yaml": textwrap.dedent(
            """
            version: v1.1
            chapters:
              - id: CH-001
                name: Geometry
                order: 1
            """
        ).strip()
        + "\n",
        "units/chart_rules.yaml": textwrap.dedent(
            """
            version: v1.0
            chart_types:
              - type_id: CHART-001
                name: Velocity Profile
                rendering:
                  experiment_marker: "circle, edgecolors='blue'"
            """
        ).strip()
        + "\n",
        "units/data_points.yaml": textwrap.dedent(
            """
            version: v1.1
            cases:
              - case_id: CASE-001
                centerline_velocity:
                  - y_H: 0.5000
                    u_uref_cfd: 0.03951
                    error_pct: 3.43
              - case_id: BENCH-04
                strouhal_number:
                  exp: 0.164
                  cfd: 0.164
                  error_pct: 0.00
            """
        ).strip()
        + "\n",
        "units/evidence.yaml": textwrap.dedent(
            """
            version: v1.0
            evidence_chains:
              - chain_id: EVID-CHAIN-001
                goal: validate case 1
              - chain_id: EVID-CHAIN-002
                goal: validate case 2
            """
        ).strip()
        + "\n",
        "units/formulas.yaml": textwrap.dedent(
            """
            version: v1.1
            formulas:
              - id: FORM-001
                definition: "u* = u / u_ref"
            """
        ).strip()
        + "\n",
        "schema/raw_schema.json": json.dumps({"fields": [{"field_id": "raw_id", "type": "string"}]}, indent=2),
        "schema/parsed_schema.json": json.dumps({"fields": [{"field_id": "parsed_id", "type": "string"}]}, indent=2),
        "schema/canonical_schema.json": json.dumps({"fields": [{"field_id": "canonical_id", "type": "string"}]}, indent=2),
        "schema/executable_schema.json": json.dumps({"fields": [{"field_id": "executable_id", "type": "string"}]}, indent=2),
        "executables/bench_ghia1982.py": "print('ghia')\n",
        "executables/bench_cylinder_wake.py": "print('cylinder')\n",
        "executables/chart_template.py": "print('chart')\n",
        "executables/formula_validator.py": "print('formula')\n",
    }


def _create_snapshot(root: Path) -> Path:
    knowledge_root = root / "knowledge_compiler"
    _write_tree(knowledge_root, _base_files())
    return knowledge_root


class TestClassifyChange:
    def test_coordinate_threshold_below_limit_is_text_edit(self):
        result = diff_engine.classify_change(
            "CASE-001",
            "primary_vortex.center_x_H",
            0.5313,
            0.5317,
        )
        assert result == diff_engine.ChangeType.TEXT_EDIT

    def test_velocity_threshold_above_limit_is_evidence_edit(self):
        result = diff_engine.classify_change(
            "CASE-001",
            "centerline_velocity[y_H=0.5000].u_uref_cfd",
            0.03951,
            0.03962,
        )
        assert result == diff_engine.ChangeType.EVIDENCE_EDIT

    def test_integral_threshold_above_limit_is_evidence_edit(self):
        result = diff_engine.classify_change(
            "BENCH-04",
            "strouhal_number.cfd",
            0.164,
            0.166,
        )
        assert result == diff_engine.ChangeType.EVIDENCE_EDIT


class TestImpactAndReview:
    def test_track_impact_routes_cases_and_formulas(self):
        case_change = diff_engine.DiffReport(
            change_type=diff_engine.ChangeType.EVIDENCE_EDIT,
            unit_id="CASE-001",
            field="centerline_velocity[y_H=0.5000].error_pct",
            old_value=3.43,
            new_value=3.63,
            impacted_executables=[],
        )
        formula_change = diff_engine.DiffReport(
            change_type=diff_engine.ChangeType.SEMANTIC_EDIT,
            unit_id="FORM-001",
            field="definition",
            old_value="u* = u / u_ref",
            new_value="u* = u / Uref",
            impacted_executables=[],
        )

        assert diff_engine.track_impact(case_change) == ["EXEC-BENCH-GHIA-001"]
        assert diff_engine.track_impact(formula_change) == [
            "EXEC-FORMULA-VALIDATOR-001",
            "EXEC-BENCH-GHIA-001",
            "EXEC-BENCH-CYLINDER-WAKE-001",
        ]

    def test_generate_report_marks_requires_review(self):
        changes = [
            diff_engine.DiffReport(
                change_type=diff_engine.ChangeType.SEMANTIC_EDIT,
                unit_id=f"FORM-00{index}",
                field="definition",
                old_value="old",
                new_value="new",
                impacted_executables=["EXEC-FORMULA-VALIDATOR-001"],
            )
            for index in range(1, 5)
        ]

        report = diff_engine.generate_report(changes, from_version="v1.0", to_version="v1.0")
        assert report["requires_review"] is True
        assert report["invalidated_executables"] == ["EXEC-FORMULA-VALIDATOR-001"]


class TestDiffFiles:
    def test_diff_files_detects_chart_rule_edit_and_new_executable(self, tmp_path: Path):
        baseline_root = _create_snapshot(tmp_path / "baseline")
        current_root = tmp_path / "current" / "knowledge_compiler"
        shutil.copytree(baseline_root, current_root)

        (current_root / "units" / "chart_rules.yaml").write_text(
            textwrap.dedent(
                """
                version: v1.0
                chart_types:
                  - type_id: CHART-001
                    name: Velocity Profile
                    rendering:
                      experiment_marker: "circle, edgecolors='green'"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (current_root / "executables" / "diff_engine.py").write_text("print('diff')\n", encoding="utf-8")

        changes = diff_engine.diff_files(baseline_root, current_root)

        assert any(
            change.change_type == diff_engine.ChangeType.CHART_RULE_EDIT
            and change.unit_id == "CHART-001"
            and change.impacted_executables == ["EXEC-CHART-TEMPLATE-001"]
            for change in changes
        )
        assert any(
            change.change_type == diff_engine.ChangeType.NEW
            and change.unit_id == "executables/diff_engine.py"
            for change in changes
        )

    def test_diff_files_uses_manifest_to_validate_baseline(self, tmp_path: Path):
        baseline_root = _create_snapshot(tmp_path / "baseline")
        current_root = tmp_path / "current" / "knowledge_compiler"
        shutil.copytree(baseline_root, current_root)
        (baseline_root / "schema" / "raw_schema.json").unlink()

        with pytest.raises(ValueError, match="Baseline snapshot is incomplete"):
            diff_engine.diff_files(baseline_root, current_root)


class TestCLI:
    def test_cli_outputs_section4_json(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        knowledge_root = _create_snapshot(repo_root)

        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
        subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo_root, check=True, capture_output=True, text=True)
        baseline_commit = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )

        (knowledge_root / "units" / "data_points.yaml").write_text(
            textwrap.dedent(
                """
                version: v1.1
                cases:
                  - case_id: CASE-001
                    centerline_velocity:
                      - y_H: 0.5000
                        u_uref_cfd: 0.03951
                        error_pct: 3.63
                  - case_id: BENCH-04
                    strouhal_number:
                      exp: 0.164
                      cfd: 0.164
                      error_pct: 0.00
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                "python3",
                "-m",
                "diff_engine",
                "--baseline",
                baseline_commit,
                "--current",
                str(knowledge_root),
            ],
            cwd=Path(__file__).resolve().parent,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)

        assert set(payload) == {
            "diff_id",
            "from_version",
            "to_version",
            "changes",
            "new_assets",
            "deleted_assets",
            "invalidated_executables",
            "requires_review",
        }
        assert payload["from_version"] == "v1.0"
        assert payload["to_version"] == "v1.0"
        assert payload["requires_review"] is True
        assert "EXEC-BENCH-GHIA-001" in payload["invalidated_executables"]
        assert any(change["change_type"] == "EVIDENCE_EDIT" for change in payload["changes"])
