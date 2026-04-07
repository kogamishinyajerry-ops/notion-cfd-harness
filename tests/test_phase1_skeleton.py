#!/usr/bin/env python3
"""
Phase 1 Module 2: Report Skeleton Generator tests
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeLayer,
    KnowledgeStatus,
    ReportSpec,
    ResultManifest,
    ResultAsset,
)
from knowledge_compiler.phase1.skeleton import (
    ChartStandard,
    REPORT_STRUCTURE,
    PROBLEM_TYPE_DEFAULTS,
    GateResult,
    Phase1Gates,
    ReportSkeletonGenerator,
    generate_report_skeleton,
)


class TestChartStandard:
    def test_marker_styles_defined(self):
        """ChartStandard should have marker styles defined"""
        assert "experiment" in ChartStandard.MARKERS
        assert "cfd" in ChartStandard.MARKERS
        assert ChartStandard.MARKERS["experiment"]["marker"] == "o"

    def test_colormaps_defined(self):
        """ChartStandard should have colormap standards"""
        assert "default" in ChartStandard.COLORMAPS
        assert "pressure" in ChartStandard.COLORMAPS
        assert ChartStandard.COLORMAPS["default"] == "viridis"

    def test_figure_sizes_defined(self):
        """ChartStandard should have figure size standards"""
        assert "profile" in ChartStandard.FIGURE_SIZES
        assert ChartStandard.FIGURE_SIZES["profile"] == (8, 6)


class TestReportStructure:
    def test_structure_has_all_chapters(self):
        """REPORT_STRUCTURE should define all chapters"""
        assert "1.0_geometry" in REPORT_STRUCTURE
        assert "1.1_mesh" in REPORT_STRUCTURE
        assert "1.2_solver" in REPORT_STRUCTURE
        assert "1.3_boundary" in REPORT_STRUCTURE
        assert "1.4_results" in REPORT_STRUCTURE
        assert "1.5_validation" in REPORT_STRUCTURE

    def test_chapter_has_required_fields(self):
        """Each chapter should have title, description, required_fields"""
        for chapter_id, chapter in REPORT_STRUCTURE.items():
            assert "title" in chapter
            assert "description" in chapter
            assert "required_fields" in chapter
            assert isinstance(chapter["required_fields"], list)


class TestProblemTypeDefaults:
    def test_internal_flow_defaults(self):
        """InternalFlow should have default plots and metrics"""
        defaults = PROBLEM_TYPE_DEFAULTS[ProblemType.INTERNAL_FLOW]
        assert "required_plots" in defaults
        assert "required_metrics" in defaults
        assert len(defaults["required_plots"]) >= 2
        assert len(defaults["required_metrics"]) >= 2

    def test_external_flow_defaults(self):
        """ExternalFlow should have lift/drag metrics"""
        defaults = PROBLEM_TYPE_DEFAULTS[ProblemType.EXTERNAL_FLOW]
        metric_names = [m.name for m in defaults["required_metrics"]]
        assert "drag_coefficient" in metric_names
        assert "lift_coefficient" in metric_names

    def test_heat_transfer_defaults(self):
        """HeatTransfer should have temperature plots"""
        defaults = PROBLEM_TYPE_DEFAULTS[ProblemType.HEAT_TRANSFER]
        plot_names = [p.name for p in defaults["required_plots"]]
        assert "temperature_field" in plot_names


class TestPhase1Gates:
    def test_p1_g1_field_completeness_pass(self):
        """P1-G1 should pass when all required assets are present"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/tmp/test",
            assets=[
                ResultAsset(asset_type="field", path="0/U"),
                ResultAsset(asset_type="monitor_point", path="probes/point1"),
            ],
        )

        result = Phase1Gates.p1_g1_field_completeness(
            manifest,
            ProblemType.INTERNAL_FLOW,
        )

        assert result.gate_id == "P1-G1"
        assert result.passed is True
        assert result.score == 100.0

    def test_p1_g1_field_completeness_fail(self):
        """P1-G1 should fail when required assets are missing"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/tmp/test",
            assets=[
                ResultAsset(asset_type="log_file", path="solverLog"),
            ],
        )

        result = Phase1Gates.p1_g1_field_completeness(
            manifest,
            ProblemType.INTERNAL_FLOW,
        )

        assert result.passed is False
        assert result.score < 80.0
        assert len(result.warnings) > 0

    def test_p1_g2_plot_standards_pass(self):
        """P1-G2 should pass for standard-compliant plots"""
        from knowledge_compiler.phase1.schema import ReportDraft

        draft = ReportDraft(
            draft_id="TEST-001",
            case_id="case1",
            task_spec_id="task1",
            plots=[
                {
                    "name": "velocity_magnitude",
                    "plane": "xy",
                    "colormap": "viridis",
                    "range": "auto",
                },
                {
                    "name": "pressure_field",
                    "plane": "xy",
                    "colormap": "coolwarm",
                    "range": "[0, 100]",
                },
            ],
        )

        result = Phase1Gates.p1_g2_plot_standards(draft)

        assert result.gate_id == "P1-G2"
        assert result.passed is True

    def test_p1_g2_plot_standards_fail(self):
        """P1-G2 should fail for non-compliant plots"""
        from knowledge_compiler.phase1.schema import ReportDraft

        draft = ReportDraft(
            draft_id="TEST-002",
            case_id="case2",
            task_spec_id="task2",
            plots=[
                {
                    "name": "bad_plot",
                    "plane": "",  # Missing plane
                    "colormap": "nonstandard",  # Non-standard colormap
                    "range": "auto",
                },
            ],
        )

        result = Phase1Gates.p1_g2_plot_standards(draft)

        assert result.passed is False
        assert len(result.warnings) > 0


class TestReportSkeletonGenerator:
    def test_generator_creation(self):
        """ReportSkeletonGenerator should initialize"""
        generator = ReportSkeletonGenerator()
        assert generator.report_specs == []
        assert generator._spec_index == {}

    def test_generator_with_specs(self):
        """ReportSkeletonGenerator should index provided specs"""
        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Internal Flow Template",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        generator = ReportSkeletonGenerator([spec])
        assert len(generator.report_specs) == 1
        assert "InternalFlow_Raw" in generator._spec_index

    def test_generate_basic_draft(self):
        """Generator should create basic draft"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="cavity",
            result_root="/tmp/cavity",
            assets=[
                ResultAsset(asset_type="field", path="0/U"),
            ],
        )

        task_spec = {
            "task_spec_id": "TASK-001",
            "problem_type": "InternalFlow",
        }

        generator = ReportSkeletonGenerator()
        draft = generator.generate(task_spec, manifest)

        assert draft.case_id == "cavity"
        assert draft.task_spec_id == "TASK-001"
        assert draft.draft_id.startswith("DRAFT-")
        assert len(draft.plots) > 0
        assert len(draft.metrics) > 0

    def test_generate_with_matched_spec(self):
        """Generator should use matched ReportSpec"""
        # Create a ReportSpec
        spec = ReportSpec(
            report_spec_id="RSPEC-MATCH",
            name="Test Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            knowledge_layer=KnowledgeLayer.CANONICAL,
        )
        spec.required_plots.clear()
        spec.required_metrics.clear()

        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/tmp/test",
        )

        task_spec = {
            "task_spec_id": "TASK-002",
            "problem_type": "InternalFlow",
        }

        generator = ReportSkeletonGenerator([spec])
        draft = generator.generate(task_spec, manifest)

        assert draft.report_spec_id == "RSPEC-MATCH"

    def test_plot_augmentation_from_manifest(self):
        """Generator should augment plots with manifest assets"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/tmp/test",
            assets=[
                ResultAsset(asset_type="contour_plot", path="plots/pressure_contour.png"),
                ResultAsset(asset_type="line_plot", path="plots/velocity_profile.png"),
            ],
        )

        task_spec = {
            "task_spec_id": "TASK-003",
            "problem_type": "InternalFlow",
        }

        generator = ReportSkeletonGenerator()
        draft = generator.generate(task_spec, manifest)

        # Should have default plots plus manifest assets
        assert len(draft.plots) >= 2

        # Check that manifest plots have source="manifest"
        manifest_plots = [p for p in draft.plots if p.get("source") == "manifest"]
        assert len(manifest_plots) >= 2

    def test_structure_generation(self):
        """Generator should create proper report structure"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/tmp/test",
        )

        task_spec = {
            "task_spec_id": "TASK-004",
            "problem_type": "InternalFlow",
        }

        generator = ReportSkeletonGenerator()
        draft = generator.generate(task_spec, manifest)

        assert "chapters" in draft.structure
        assert len(draft.structure["chapters"]) == 6
        assert draft.structure["chapters"][0]["id"] == "1.0_geometry"

    def test_gates_populated(self):
        """Generator should run gates and populate status"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/tmp/test",
            assets=[
                ResultAsset(asset_type="field", path="0/U"),
            ],
        )

        task_spec = {
            "task_spec_id": "TASK-005",
            "problem_type": "InternalFlow",
        }

        generator = ReportSkeletonGenerator()
        draft = generator.generate(task_spec, manifest)

        assert "P1-G1" in draft.gates_status
        assert "P1-G2" in draft.gates_status
        assert "passed" in draft.gates_status["P1-G1"]
        assert "score" in draft.gates_status["P1-G1"]

    def test_create_report_spec_from_draft(self):
        """Generator should convert draft to ReportSpec"""
        from knowledge_compiler.phase1.schema import ReportDraft

        draft = ReportDraft(
            draft_id="DRAFT-001",
            case_id="case1",
            task_spec_id="task1",
            plots=[
                {"name": "velocity", "plane": "xy", "colormap": "viridis", "range": "auto"},
            ],
            metrics=[
                {"name": "drag", "unit": "N", "comparison": "direct"},
            ],
        )

        generator = ReportSkeletonGenerator()
        spec = generator.create_report_spec_from_draft(
            draft,
            name="Test Report Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        assert spec.name == "Test Report Spec"
        assert spec.problem_type == ProblemType.INTERNAL_FLOW
        assert spec.knowledge_layer == KnowledgeLayer.RAW
        assert spec.knowledge_status == KnowledgeStatus.DRAFT
        assert len(spec.required_plots) == 1
        assert len(spec.required_metrics) == 1


class TestConvenienceFunctions:
    def test_generate_report_skeleton(self):
        """generate_report_skeleton convenience function should work"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="test",
            result_root="/tmp/test",
            assets=[
                ResultAsset(asset_type="field", path="0/U"),
            ],
        )

        task_spec = {
            "task_spec_id": "TASK-006",
            "problem_type": "InternalFlow",
        }

        draft = generate_report_skeleton(task_spec, manifest)

        assert draft.case_id == "test"
        assert draft.task_spec_id == "TASK-006"
        assert len(draft.plots) > 0


class TestProblemTypeSpecifics:
    def test_external_flow_generates_correct_metrics(self):
        """ExternalFlow should generate lift/drag metrics"""
        manifest = ResultManifest(
            solver_type="fluent",
            case_name="airfoil",
            result_root="/tmp/airfoil",
        )

        task_spec = {
            "task_spec_id": "TASK-007",
            "problem_type": "ExternalFlow",
        }

        generator = ReportSkeletonGenerator()
        draft = generator.generate(task_spec, manifest)

        metric_names = [m["name"] for m in draft.metrics]
        assert "drag_coefficient" in metric_names
        assert "lift_coefficient" in metric_names

    def test_heat_transfer_generates_temperature_plots(self):
        """HeatTransfer should generate temperature plots"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="heat",
            result_root="/tmp/heat",
        )

        task_spec = {
            "task_spec_id": "TASK-008",
            "problem_type": "HeatTransfer",
        }

        generator = ReportSkeletonGenerator()
        draft = generator.generate(task_spec, manifest)

        plot_names = [p["name"] for p in draft.plots]
        assert "temperature_field" in plot_names


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
