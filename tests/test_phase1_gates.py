#!/usr/bin/env python3
"""
Phase 1 Gates: P1-G3 & P1-G4 Tests
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeStatus,
    ReportSpec,
    TeachRecord,
    TeachOperation,
    PlotSpec,
    MetricSpec,
    ComparisonType,
)
import time as time_module
from knowledge_compiler.phase1.gates import (
    GateStatus,
    GateCheckItem,
    GateResult,
    ExplanationBinding,
    EvidenceBindingGate,
    GeneralizationMetrics,
    TemplateGeneralizationGate,
    Phase1GateExecutor,
)


# ============================================================================
# Test GateStatus & GateResult
# ============================================================================

class TestGateStatus:
    def test_gate_status_values(self):
        """GateStatus should have correct values"""
        assert GateStatus.PASS.value == "PASS"
        assert GateStatus.FAIL.value == "FAIL"
        assert GateStatus.WARN.value == "WARN"


class TestGateResult:
    def test_gate_result_creation(self):
        """GateResult should initialize"""
        result = GateResult(
            gate_id="P1-G3",
            gate_name="Evidence Binding Gate",
            status=GateStatus.PASS,
            timestamp=time.time(),
            score=100.0,
        )

        assert result.gate_id == "P1-G3"
        assert result.is_pass() is True

    def test_gate_result_with_failures(self):
        """GateResult should handle failures"""
        result = GateResult(
            gate_id="P1-G3",
            gate_name="Evidence Binding Gate",
            status=GateStatus.FAIL,
            timestamp=time.time(),
            score=60.0,
            errors=["Error 1", "Error 2"],
        )

        assert result.is_pass() is False
        assert len(result.errors) == 2

    def test_get_pass_rate(self):
        """GateResult should calculate pass rate"""
        result = GateResult(
            gate_id="P1-G3",
            gate_name="Test",
            status=GateStatus.PASS,
            timestamp=time.time(),
            score=100.0,
            checklist=[
                GateCheckItem(
                    item="item1",
                    description="Test item 1",
                    result=GateStatus.PASS,
                    message="OK",
                ),
                GateCheckItem(
                    item="item2",
                    description="Test item 2",
                    result=GateStatus.FAIL,
                    message="Failed",
                ),
                GateCheckItem(
                    item="item3",
                    description="Test item 3",
                    result=GateStatus.PASS,
                    message="OK",
                ),
            ],
        )

        pass_rate = result.get_pass_rate()
        assert pass_rate == (2 / 3) * 100

    def test_to_dict(self):
        """GateResult should serialize to dict"""
        result = GateResult(
            gate_id="P1-G3",
            gate_name="Test",
            status=GateStatus.PASS,
            timestamp=1234567890.0,
            score=95.0,
            checklist=[
                GateCheckItem(
                    item="item1",
                    description="Test",
                    result=GateStatus.PASS,
                    message="OK",
                    evidence_id="EV-001",
                ),
            ],
        )

        d = result.to_dict()
        assert d["gate_id"] == "P1-G3"
        assert d["status"] == "PASS"
        assert d["score"] == 95.0
        assert len(d["checklist"]) == 1
        assert d["checklist"][0]["evidence_id"] == "EV-001"


# ============================================================================
# Test P1-G3: EvidenceBindingGate
# ============================================================================

class TestExplanationBinding:
    def test_explanation_binding_creation(self):
        """ExplanationBinding should initialize"""
        binding = ExplanationBinding(
            explanation="The velocity plot shows high flow",
            bound_to=["velocity_magnitude", "velocity_contour"],
            binding_type="plot",
            confidence=0.9,
        )

        assert binding.binding_type == "plot"
        assert len(binding.bound_to) == 2


class TestEvidenceBindingGate:
    def test_gate_initialization(self):
        """EvidenceBindingGate should initialize with keywords"""
        gate = EvidenceBindingGate()

        assert "plot" in gate._binding_keywords
        assert "metric" in gate._binding_keywords
        assert "comparison" in gate._binding_keywords

    def test_detect_plot_binding(self):
        """Should detect plot binding in explanation"""
        gate = EvidenceBindingGate()

        binding = gate._detect_binding(
            "The velocity contour plot shows flow patterns",
            "Visualizing the field"
        )

        assert binding.binding_type == "plot"

    def test_detect_metric_binding(self):
        """Should detect metric binding in explanation"""
        gate = EvidenceBindingGate()

        binding = gate._detect_binding(
            "The drag coefficient value is 0.3",
            "Calculate the coefficient"
        )

        assert binding.binding_type == "metric"

    def test_detect_comparison_binding(self):
        """Should detect comparison binding"""
        gate = EvidenceBindingGate()

        binding = gate._detect_binding(
            "Compare velocity vs pressure",
            "Show the difference"
        )

        assert binding.binding_type == "comparison"

    def test_detect_no_binding(self):
        """Should return none when no binding detected"""
        gate = EvidenceBindingGate()

        binding = gate._detect_binding(
            "This is just general text",
            "No specific terms"
        )

        assert binding.binding_type == "none"

    def test_check_teach_record_pass(self):
        """Should pass when all explanations are bound"""
        gate = EvidenceBindingGate()

        record = TeachRecord(
            teach_record_id="TR-001",
            case_id="CASE-001",
            timestamp=time_module.time(),
            operations=[
                TeachOperation(
                    operation_type="add_explanation",
                    description="The velocity plot shows flow patterns",
                    reason="Visualize the field",
                    is_generalizable=True,
                ),
            ],
        )

        result = gate.check_teach_record(record)

        assert result.is_pass() is True
        assert result.score >= 80.0

    def test_check_teach_record_fail_unbound(self):
        """Should fail when explanations are unbound"""
        gate = EvidenceBindingGate()

        record = TeachRecord(
            teach_record_id="TR-001",
            case_id="CASE-001",
            timestamp=time_module.time(),
            operations=[
                TeachOperation(
                    operation_type="add_explanation",
                    description="This is just general text without binding",
                    reason="No reason",
                    is_generalizable=False,
                ),
            ],
        )

        result = gate.check_teach_record(record)

        assert result.is_pass() is False
        assert len(result.errors) > 0
        assert "without binding" in result.errors[0].lower()

    def test_check_batch_pass(self):
        """Should pass batch when all records pass"""
        gate = EvidenceBindingGate()

        records = [
            TeachRecord(
                teach_record_id=f"TR-{i:03d}",
                case_id=f"CASE-{i:03d}",
                timestamp=time_module.time(),
                operations=[
                    TeachOperation(
                        operation_type="add_explanation",
                        description=f"The velocity plot {i} shows flow",
                        reason="Visualize",
                        is_generalizable=True,
                    ),
                ],
            )
            for i in range(3)
        ]

        result = gate.check_batch(records)

        assert result.is_pass() is True

    def test_check_batch_with_mixed_results(self):
        """Should handle mixed pass/fail in batch"""
        gate = EvidenceBindingGate()

        records = [
            TeachRecord(
                teach_record_id="TR-001",
                case_id="CASE-001",
                timestamp=time_module.time(),
                operations=[
                    TeachOperation(
                        operation_type="add_explanation",
                        description="The velocity plot shows flow",
                        reason="Visualize",
                        is_generalizable=True,
                    ),
                ],
            ),
            TeachRecord(
                teach_record_id="TR-002",
                case_id="CASE-002",
                timestamp=time_module.time(),
                operations=[
                    TeachOperation(
                        operation_type="add_explanation",
                        description="General text without binding",
                        reason="No reason",
                        is_generalizable=False,
                    ),
                ],
            ),
        ]

        result = gate.check_batch(records)

        assert result.is_pass() is False
        assert result.metadata["total_records"] == 2

    def test_check_with_available_assets(self):
        """Should validate bindings against available assets"""
        gate = EvidenceBindingGate()

        record = TeachRecord(
            teach_record_id="TR-001",
            case_id="CASE-001",
            timestamp=time_module.time(),
            operations=[
                TeachOperation(
                    operation_type="add_explanation",
                    description="The velocity_magnitude plot shows flow",
                    reason="Visualize",
                    is_generalizable=True,
                ),
            ],
        )

        # With matching assets - velocity_magnitude will be detected
        result = gate.check_teach_record(record, available_assets=["velocity_magnitude"])
        # No warnings since velocity_magnitude is in available_assets
        assert result.is_pass() is True
        assert len(result.warnings) == 0

        # Without matching assets
        result2 = gate.check_teach_record(record, available_assets=["pressure_plot"])
        # The binding detection will find velocity_magnitude but it's not in available_assets
        # This should generate a warning
        assert len(result2.warnings) > 0

    def test_skip_non_explanation_operations(self):
        """Should only check explanation operations"""
        gate = EvidenceBindingGate()

        record = TeachRecord(
            teach_record_id="TR-001",
            case_id="CASE-001",
            timestamp=time_module.time(),
            operations=[
                TeachOperation(
                    operation_type="add_plot",
                    description="Add a plot",
                    reason="Need visualization",
                    is_generalizable=True,
                ),
                TeachOperation(
                    operation_type="add_metric",
                    description="Add a metric",
                    reason="Need measurement",
                    is_generalizable=True,
                ),
            ],
        )

        result = gate.check_teach_record(record)

        # Should pass since no explanation operations to check
        assert result.is_pass() is True


# ============================================================================
# Test P1-G4: TemplateGeneralizationGate
# ============================================================================

class TestGeneralizationMetrics:
    def test_metrics_creation(self):
        """GeneralizationMetrics should initialize"""
        metrics = GeneralizationMetrics(
            diversity_score=0.8,
            consistency_score=0.7,
            coverage_score=0.9,
            generalizability_score=0.0,
        )

        assert metrics.diversity_score == 0.8
        assert metrics.generalizability_score == 0.0

    def test_calculate_overall(self):
        """Should calculate weighted generalizability score"""
        metrics = GeneralizationMetrics(
            diversity_score=0.8,
            consistency_score=0.7,
            coverage_score=0.9,
            generalizability_score=0.0,
        )

        metrics.calculate_overall()

        # Weighted: 0.3*0.8 + 0.3*0.7 + 0.4*0.9
        expected = 0.24 + 0.21 + 0.36
        assert abs(metrics.generalizability_score - expected) < 0.001


class TestTemplateGeneralizationGate:
    def test_gate_initialization(self):
        """TemplateGeneralizationGate should initialize"""
        gate = TemplateGeneralizationGate()

        assert gate.MIN_GENERALIZABILITY_SCORE == 0.7
        assert gate.MIN_Case_COUNT == 3
        assert ProblemType.INTERNAL_FLOW in gate._problem_type_patterns

    def test_check_insufficient_case_count(self):
        """Should fail with insufficient source cases"""
        gate = TemplateGeneralizationGate()

        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[
                PlotSpec(name="velocity_magnitude", plane="midplane", colormap="jet", range="auto"),
            ],
        )

        result = gate.check_report_spec_candidate(
            spec,
            source_cases=["CASE-001", "CASE-002"],  # Only 2 cases
            teach_records=[],
        )

        assert result.is_pass() is False
        assert "Insufficient source cases" in str(result.errors)

    def test_check_missing_required_plots(self):
        """Should fail when required plots are missing"""
        gate = TemplateGeneralizationGate()

        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[
                PlotSpec(name="custom_plot", plane="midplane", colormap="jet", range="auto"),
            ],
        )

        source_cases = ["CASE-001", "CASE-002", "CASE-003"]
        result = gate.check_report_spec_candidate(spec, source_cases, [])

        # InternalFlow expects velocity_magnitude, pressure_contour, streamlines
        assert any("Missing required plots" in e for e in result.errors)

    def test_check_missing_required_metrics(self):
        """Should fail when required metrics are missing"""
        gate = TemplateGeneralizationGate()

        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Spec",
            problem_type=ProblemType.EXTERNAL_FLOW,
            required_plots=[
                PlotSpec(name="pressure_coefficient", plane="wall", colormap="coolwarm", range="auto"),
            ],
            required_metrics=[
                MetricSpec(name="custom_metric", unit="N/A", comparison=ComparisonType.DIRECT),
            ],
        )

        source_cases = ["CASE-001", "CASE-002", "CASE-003"]
        result = gate.check_report_spec_candidate(spec, source_cases, [])

        # ExternalFlow expects drag_coefficient, lift_coefficient
        assert any("Missing required metrics" in e for e in result.errors)

    def test_check_pass_all_requirements(self):
        """Should pass when all requirements met"""
        gate = TemplateGeneralizationGate()

        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[
                PlotSpec(name="velocity_magnitude", plane="midplane", colormap="jet", range="auto"),
                PlotSpec(name="pressure_contour", plane="midplane", colormap="viridis", range="auto"),
                PlotSpec(name="streamlines", plane="midplane", colormap="plasma", range="auto"),
            ],
            required_metrics=[
                MetricSpec(name="max_velocity", unit="m/s", comparison=ComparisonType.DIRECT),
                MetricSpec(name="pressure_drop", unit="Pa", comparison=ComparisonType.DIFF),
            ],
        )

        source_cases = ["CASE-001", "CASE-002", "CASE-003"]
        result = gate.check_report_spec_candidate(spec, source_cases, [])

        # Case count passes, required plots/metrics present
        # Should pass or warn based on generalization metrics (which default to 0.5 diversity)
        assert len([e for e in result.errors if "Insufficient" in e]) == 0

    def test_heat_transfer_requirements(self):
        """Should check heat transfer specific requirements"""
        gate = TemplateGeneralizationGate()

        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Heat Transfer Spec",
            problem_type=ProblemType.HEAT_TRANSFER,
            required_plots=[
                PlotSpec(name="temperature_field", plane="midplane", colormap="inferno", range="auto"),
                PlotSpec(name="heat_flux", plane="wall", colormap="jet", range="auto"),
            ],
            required_metrics=[
                MetricSpec(name="heat_transfer_coefficient", unit="W/(m²K)", comparison=ComparisonType.DIRECT),
                MetricSpec(name="max_temperature", unit="K", comparison=ComparisonType.DIFF),
            ],
        )

        source_cases = ["CASE-001", "CASE-002", "CASE-003"]
        result = gate.check_report_spec_candidate(spec, source_cases, [])

        # Heat transfer requirements should pass
        assert not any("Missing required plots" in e for e in result.errors)
        assert not any("Missing required metrics" in e for e in result.errors)

    def test_generalization_metrics_in_checklist(self):
        """Should include generalization metrics in checklist"""
        gate = TemplateGeneralizationGate()

        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[
                PlotSpec(name="velocity_magnitude", plane="midplane", colormap="jet", range="auto"),
                PlotSpec(name="pressure_contour", plane="midplane", colormap="viridis", range="auto"),
                PlotSpec(name="streamlines", plane="midplane", colormap="plasma", range="auto"),
            ],
            required_metrics=[
                MetricSpec(name="max_velocity", unit="m/s", comparison=ComparisonType.DIRECT),
            ],
        )

        # Create some teach records
        teach_records = [
            TeachRecord(
                teach_record_id="TR-001",
                case_id="CASE-001",
                timestamp=time_module.time(),
                operations=[
                    TeachOperation(
                        operation_type="add_explanation",
                        description="Explanation for plot1",
                        reason="Reason",
                        is_generalizable=True,
                    ),
                ],
            ),
        ]

        source_cases = ["CASE-001", "CASE-002", "CASE-003"]
        result = gate.check_report_spec_candidate(spec, source_cases, teach_records)

        # Check that metrics are in checklist
        checklist_items = {c.item for c in result.checklist}
        assert "diversity_score" in checklist_items
        assert "consistency_score" in checklist_items
        assert "coverage_score" in checklist_items

    def test_metadata_case_count(self):
        """Should include case count in metadata"""
        gate = TemplateGeneralizationGate()

        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[
                PlotSpec(name="velocity_magnitude", plane="midplane", colormap="jet", range="auto"),
            ],
        )

        source_cases = ["CASE-001", "CASE-002", "CASE-003", "CASE-004"]
        result = gate.check_report_spec_candidate(spec, source_cases, [])

        assert result.metadata["case_count"] == 4


# ============================================================================
# Test Phase1GateExecutor
# ============================================================================

class TestPhase1GateExecutor:
    def test_executor_initialization(self):
        """Phase1GateExecutor should initialize"""
        executor = Phase1GateExecutor()

        assert executor.g3_gate is not None
        assert executor.g4_gate is not None

    def test_run_g3_gate_with_records(self):
        """Should run P1-G3 gate"""
        executor = Phase1GateExecutor()

        records = [
            TeachRecord(
                teach_record_id="TR-001",
                case_id="CASE-001",
                timestamp=time_module.time(),
                operations=[
                    TeachOperation(
                        operation_type="add_explanation",
                        description="The velocity plot shows flow",
                        reason="Visualize",
                        is_generalizable=True,
                    ),
                ],
            ),
        ]

        result = executor.run_g3_gate(records)

        assert result.gate_id == "P1-G3"
        assert result.is_pass() is True

    def test_run_g3_gate_empty_records(self):
        """Should handle empty teach records"""
        executor = Phase1GateExecutor()

        result = executor.run_g3_gate([])

        assert result.is_pass() is True
        assert len(result.warnings) > 0

    def test_run_g4_gate(self):
        """Should run P1-G4 gate"""
        executor = Phase1GateExecutor()

        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[
                PlotSpec(name="velocity_magnitude", plane="midplane", colormap="jet", range="auto"),
                PlotSpec(name="pressure_contour", plane="midplane", colormap="viridis", range="auto"),
                PlotSpec(name="streamlines", plane="midplane", colormap="plasma", range="auto"),
            ],
            required_metrics=[
                MetricSpec(name="max_velocity", unit="m/s", comparison=ComparisonType.DIRECT),
                MetricSpec(name="pressure_drop", unit="Pa", comparison=ComparisonType.DIFF),
            ],
        )

        source_cases = ["CASE-001", "CASE-002", "CASE-003"]
        result = executor.run_g4_gate(spec, source_cases, [])

        assert result.gate_id == "P1-G4"

    def test_run_all_gates(self):
        """Should run all gates and return combined results"""
        executor = Phase1GateExecutor()

        spec = ReportSpec(
            report_spec_id="RSPEC-001",
            name="Test Spec",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[
                PlotSpec(name="velocity_magnitude", plane="midplane", colormap="jet", range="auto"),
                PlotSpec(name="pressure_contour", plane="midplane", colormap="viridis", range="auto"),
                PlotSpec(name="streamlines", plane="midplane", colormap="plasma", range="auto"),
            ],
            required_metrics=[
                MetricSpec(name="max_velocity", unit="m/s", comparison=ComparisonType.DIRECT),
                MetricSpec(name="pressure_drop", unit="Pa", comparison=ComparisonType.DIFF),
            ],
        )

        source_cases = ["CASE-001", "CASE-002", "CASE-003"]

        records = [
            TeachRecord(
                teach_record_id=f"TR-{i:03d}",
                case_id=f"CASE-{i:03d}",
                timestamp=time_module.time(),
                operations=[
                    TeachOperation(
                        operation_type="add_explanation",
                        description=f"The velocity plot {i} shows flow",
                        reason="Visualize",
                        is_generalizable=True,
                    ),
                ],
            )
            for i in range(3)
        ]

        results = executor.run_all_gates(spec, source_cases, records)

        assert "P1-G3" in results
        assert "P1-G4" in results
        assert results["P1-G3"].gate_id == "P1-G3"
        assert results["P1-G4"].gate_id == "P1-G4"


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
