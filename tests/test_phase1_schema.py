#!/usr/bin/env python3
"""
Phase 1 Schema and Parser tests
"""

from __future__ import annotations

import json
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
    ComparisonType,
    PlotSpec,
    MetricSpec,
    SectionSpec,
    AnomalyRule,
    ReportSpec,
    TeachRecord,
    TeachOperation,
    KnowledgeVersion,
    ResultManifest,
    ResultAsset,
    create_report_spec_id,
    create_teach_record_id,
)
from knowledge_compiler.phase1.parser import (
    SolverType,
    ResultDirectoryParser,
    parse_result_directory,
)


class TestEnums:
    def test_problem_type_values(self):
        """ProblemType should have correct values"""
        assert ProblemType.INTERNAL_FLOW.value == "InternalFlow"
        assert ProblemType.HEAT_TRANSFER.value == "HeatTransfer"

    def test_knowledge_layer_values(self):
        """KnowledgeLayer should have correct values"""
        assert KnowledgeLayer.RAW.value == "Raw"
        assert KnowledgeLayer.CANONICAL.value == "Canonical"

    def test_knowledge_status_values(self):
        """KnowledgeStatus should have correct values"""
        assert KnowledgeStatus.DRAFT.value == "draft"
        assert KnowledgeStatus.APPROVED.value == "approved"


class TestReportSpec:
    def test_report_spec_creation(self):
        """ReportSpec should initialize"""
        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Lid Driven Cavity",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        assert spec.report_spec_id == "RSPEC-001"
        assert spec.name == "Lid Driven Cavity"
        assert spec.problem_type == ProblemType.INTERNAL_FLOW
        assert spec.knowledge_status == KnowledgeStatus.DRAFT

    def test_report_spec_to_dict(self):
        """ReportSpec should convert to dictionary"""
        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Report",
            problem_type=ProblemType.HEAT_TRANSFER,
        )
        spec.required_plots.append(PlotSpec(
            name="velocity_magnitude",
            plane="xy",
            colormap="jet",
            range="[0, 10]",
        ))

        data = spec.to_dict()

        assert data["report_spec_id"] == "RSPEC-001"
        assert data["problem_type"] == "HeatTransfer"
        assert len(data["required_plots"]) == 1

    def test_report_spec_json_roundtrip(self):
        """ReportSpec should survive JSON serialization"""
        spec = ReportSpec(
            report_spec_id="RSPEC-002",
            name="Round Trip Test",
            problem_type=ProblemType.MULTIPHASE,
        )
        spec.required_metrics.append(MetricSpec(
            name="drag_coefficient",
            unit="-",
            comparison=ComparisonType.RATIO,
        ))

        json_str = spec.to_json()
        loaded = ReportSpec.from_json(json_str)

        assert loaded.report_spec_id == spec.report_spec_id
        assert loaded.problem_type == spec.problem_type
        assert len(loaded.required_metrics) == 1

    def test_report_spec_add_source_case(self):
        """ReportSpec should add source cases"""
        spec = ReportSpec(
            report_spec_id="RSPEC-003",
            name="Test",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        spec.add_source_case("CASE-001")
        spec.add_source_case("BENCH-04")
        spec.add_source_case("CASE-001")  # Should not duplicate

        assert spec.source_cases == ["CASE-001", "BENCH-04"]

    def test_report_spec_add_teach_record(self):
        """ReportSpec should add teach records"""
        spec = ReportSpec(
            report_spec_id="RSPEC-004",
            name="Test",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        spec.add_teach_record("TEACH-001")
        spec.add_teach_record("TEACH-002")

        assert spec.teach_records == ["TEACH-001", "TEACH-002"]

    def test_report_spec_transition_to(self):
        """ReportSpec should transition status"""
        spec = ReportSpec(
            report_spec_id="RSPEC-005",
            name="Test",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        assert spec.knowledge_status == KnowledgeStatus.DRAFT

        spec.transition_to(KnowledgeStatus.CANDIDATE)
        assert spec.knowledge_status == KnowledgeStatus.CANDIDATE

        spec.transition_to(KnowledgeStatus.APPROVED)
        assert spec.knowledge_status == KnowledgeStatus.APPROVED

    def test_report_spec_replay_pass_rate(self):
        """ReportSpec should calculate replay pass rate"""
        spec = ReportSpec(
            report_spec_id="RSPEC-006",
            name="Test",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        spec.calculate_replay_pass_rate([True, False, True, True])
        assert spec.replay_pass_rate == 75.0


class TestTeachRecord:
    def test_teach_record_creation(self):
        """TeachRecord should initialize"""
        record = TeachRecord(
            teach_record_id="TEACH-001",
            case_id="CASE-001",
            timestamp=1234567890.0,
        )

        assert record.teach_record_id == "TEACH-001"
        assert record.case_id == "CASE-001"

    def test_teach_record_add_operation(self):
        """TeachRecord should add operations"""
        record = TeachRecord(
            teach_record_id="TEACH-002",
            case_id="CASE-001",
            timestamp=1234567890.0,
        )

        record.add_operation(
            operation_type="add_plot",
            description="Add midplane velocity contour",
            reason="Shows vortex core formation",
            is_generalizable=True,
        )

        assert len(record.operations) == 1
        assert record.operations[0].operation_type == "add_plot"
        assert record.operations[0].is_generalizable is True

    def test_teach_record_json_roundtrip(self):
        """TeachRecord should survive JSON serialization"""
        record = TeachRecord(
            teach_record_id="TEACH-003",
            case_id="CASE-001",
            timestamp=1234567890.0,
        )
        record.add_operation(
            operation_type="add_metric",
            description="Add drag coefficient",
            reason="Required for validation",
            is_generalizable=False,
        )

        json_str = record.to_json()
        loaded = TeachRecord.from_json(json_str)

        assert loaded.teach_record_id == record.teach_record_id
        assert len(loaded.operations) == 1


class TestResultManifest:
    def test_result_manifest_creation(self):
        """ResultManifest should initialize"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="cavity",
            result_root="/results/cavity",
        )

        assert manifest.solver_type == "openfoam"
        assert manifest.case_name == "cavity"

    def test_result_manifest_get_assets_by_type(self):
        """ResultManifest should filter assets by type"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="cavity",
            result_root="/results/cavity",
        )
        manifest.assets = [
            ResultAsset(asset_type="field", path="0/U/p"),
            ResultAsset(asset_type="line_plot", path="xy/velocity.png"),
            ResultAsset(asset_type="field", path="1/U/p"),
        ]

        field_assets = manifest.get_assets_by_type("field")
        assert len(field_assets) == 2

        line_assets = manifest.get_assets_by_type("line_plot")
        assert len(line_assets) == 1

    def test_result_manifest_has_field_data(self):
        """ResultManifest should check for field data"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="cavity",
            result_root="/results/cavity",
        )
        manifest.assets = [
            ResultAsset(asset_type="monitor_point", path="probes/point1"),
        ]

        assert manifest.has_field_data() is True

    def test_result_manifest_has_residuals(self):
        """ResultManifest should check for residuals"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="cavity",
            result_root="/results/cavity",
        )
        manifest.assets = [
            ResultAsset(asset_type="log_file", path="solverLog"),
        ]

        assert manifest.has_residuals() is False

    def test_result_manifest_get_plot_assets(self):
        """ResultManifest should get plot assets"""
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="cavity",
            result_root="/results/cavity",
        )
        manifest.assets = [
            ResultAsset(asset_type="line_plot", path="plots/xy.png"),
            ResultAsset(asset_type="contour_plot", path="plots/contour.png"),
            ResultAsset(asset_type="field", path="0/U/p"),
        ]

        plot_assets = manifest.get_plot_assets()
        assert len(plot_assets) == 2


class TestSolverTypeDetection:
    def test_detect_openfoam(self):
        """Should detect OpenFOAM structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create OpenFOAM-like structure
            (Path(tmpdir) / "0" / "U" / "p").mkdir(parents=True)

            detected = SolverType.detect(tmpdir)
            assert detected == SolverType.OPENFOAM

    def test_detect_fluent(self):
        """Should detect Fluent structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Fluent-like file
            (Path(tmpdir) / "data.dat").write_text("x y\n")
            (Path(tmpdir) / "case.cas").write_text("")

            detected = SolverType.detect(tmpdir)
            assert detected == SolverType.FLUENT

    def test_detect_unknown(self):
        """Should return unknown for unrecognizable structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            detected = SolverType.detect(tmpdir)
            assert detected == SolverType.UNKNOWN


class TestResultDirectoryParser:
    def test_parser_parse_openfoam(self):
        """Parser should parse OpenFOAM results"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create OpenFOAM structure
            time_dir = Path(tmpdir) / "0" / "U" / "p"
            time_dir.mkdir(parents=True)

            parser = ResultDirectoryParser()
            manifest = parser.parse(tmpdir, "test_case")

            assert manifest.solver_type == "openfoam"
            assert manifest.case_name == "test_case"

    def test_parser_with_fluent(self):
        """Parser should parse Fluent results"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Fluent structure
            (Path(tmpdir) / "data.dat").write_text("1.0 2.0\n")
            (Path(tmpdir) / "case.cas").write_text("")

            parser = ResultDirectoryParser()
            manifest = parser.parse(tmpdir, "fluent_case")

            assert manifest.solver_type == "fluent"


class TestFactoryFunctions:
    def test_create_report_spec_id(self):
        """Should generate unique IDs"""
        id1 = create_report_spec_id()
        id2 = create_report_spec_id()

        assert id1 != id2
        assert id1.startswith("RSPEC-")
        assert id2.startswith("RSPEC-")

    def test_create_teach_record_id(self):
        """Should generate unique IDs"""
        id1 = create_teach_record_id()
        id2 = create_teach_record_id()

        assert id1 != id2
        assert id1.startswith("TEACH-")
        assert id2.startswith("TEACH-")


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
