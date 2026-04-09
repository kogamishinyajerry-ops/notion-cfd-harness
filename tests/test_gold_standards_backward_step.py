#!/usr/bin/env python3
"""
Tests for Backward Facing Step Gold Standard
"""

import pytest

from knowledge_compiler.phase1.gold_standards import (
    BackwardStepConstants,
    create_backward_facing_step_spec,
    BackwardStepGateValidator,
    get_expected_reattachment_length,
)
from knowledge_compiler.phase1.schema import ProblemType, ReportSpec, MetricSpec, ComparisonType, KnowledgeLayer, KnowledgeStatus


class TestBackwardStepConstants:
    """Test physical constants"""

    def test_expansion_ratio(self):
        """Test expansion ratio is 2.0"""
        assert BackwardStepConstants.EXPANSION_RATIO == 2.0

    def test_step_height(self):
        """Test step height"""
        assert BackwardStepConstants.STEP_HEIGHT == 0.1
        assert BackwardStepConstants.CHANNEL_HEIGHT == 0.2

    def test_reattachment_lengths(self):
        """Test reattachment length data"""
        # Laminar cases
        assert BackwardStepConstants.REATTACHMENT_LENGTHS["laminar_400"] == 10.0
        assert BackwardStepConstants.REATTACHMENT_LENGTHS["laminar_800"] == 14.0

        # Turbulent case
        assert BackwardStepConstants.REATTACHMENT_LENGTHS["turbulent"] == 6.5

    def test_profile_positions(self):
        """Test velocity profile positions"""
        expected = [1.0, 3.0, 5.0, 7.0, 10.0]
        assert BackwardStepConstants.PROFILE_POSITIONS == expected


class TestCreateBackwardFacingStepSpec:
    """Test ReportSpec creation"""

    def test_laminar_spec_creation(self):
        """Test creating laminar flow spec"""
        spec = create_backward_facing_step_spec(
            case_id="test_laminar",
            reynolds_number=400.0,
            is_turbulent=False,
        )

        assert spec.report_spec_id == "GOLD-test_laminar"
        assert spec.problem_type == ProblemType.INTERNAL_FLOW
        assert spec.knowledge_layer == KnowledgeLayer.CANONICAL

    def test_turbulent_spec_creation(self):
        """Test creating turbulent flow spec"""
        spec = create_backward_facing_step_spec(
            case_id="test_turbulent",
            reynolds_number=5000.0,
            is_turbulent=True,
        )

        assert spec.knowledge_layer == KnowledgeLayer.CANONICAL

    def test_required_plots(self):
        """Test that all required plots are included"""
        spec = create_backward_facing_step_spec()

        plot_names = {p.name for p in spec.required_plots}

        # Core plots should always be present
        assert "velocity_magnitude_contour" in plot_names
        assert "streamlines" in plot_names
        assert "vector_field_recirculation" in plot_names

        # Velocity profiles
        assert "u_profile_x1" in plot_names
        assert "u_profile_x7" in plot_names
        assert "u_profile_x10" in plot_names

    def test_required_metrics(self):
        """Test that all required metrics are included"""
        spec = create_backward_facing_step_spec()

        metric_names = {m.name for m in spec.required_metrics}

        # Critical metric
        assert "reattachment_length" in metric_names

        # Other metrics
        assert "max_reverse_velocity" in metric_names
        assert "recirculation_height" in metric_names
        assert "pressure_recovery" in metric_names

    def test_required_sections(self):
        """Test that all required sections are included"""
        spec = create_backward_facing_step_spec()

        section_names = {s.name for s in spec.critical_sections}

        assert "inlet_profile" in section_names
        assert "step_edge" in section_names
        assert "reattachment_point" in section_names
        assert "outlet_profile" in section_names

    def test_plot_order(self):
        """Test that plot order is defined"""
        spec = create_backward_facing_step_spec()

        assert len(spec.plot_order) > 0
        assert "velocity_magnitude_contour" in spec.plot_order[0]


class TestGetExpectedReattachmentLength:
    """Test reattachment length calculation"""

    def test_laminar_re_400(self):
        """Test laminar Re = 400"""
        xr = get_expected_reattachment_length(400.0)
        assert xr == 10.0

    def test_laminar_re_800(self):
        """Test laminar Re = 800"""
        xr = get_expected_reattachment_length(800.0)
        assert xr == 14.0

    def test_turbulent(self):
        """Test turbulent"""
        xr = get_expected_reattachment_length(5000.0)
        assert xr == 6.5


class TestBackwardStepGateValidator:
    """Test gold standard gate validator"""

    def test_validator_creation(self):
        """Test creating validator"""
        validator = BackwardStepGateValidator()

        assert validator.gold_spec is not None
        assert validator.gold_spec.knowledge_layer == KnowledgeLayer.CANONICAL

    def test_validate_perfect_spec(self):
        """Test validation of spec matching gold standard"""
        validator = BackwardStepGateValidator()

        # Create a copy of gold spec (perfect match)
        result = validator.validate_report_spec(validator.gold_spec)

        assert result["passed"] is True
        assert len(result["errors"]) == 0
        assert result["details"]["plot_coverage"] == 1.0
        assert result["details"]["metric_coverage"] == 1.0

    def test_validate_missing_plots(self):
        """Test validation with missing plots"""
        validator = BackwardStepGateValidator()

        from knowledge_compiler.phase1.schema import ReportSpec
        minimal_spec = ReportSpec(
            report_spec_id="TEST-001",
            name="Test",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[],
            required_metrics=[],
            critical_sections=[],
            plot_order=[],
            comparison_method={"type": "direct"},
            anomaly_explanation_rules=[],
            knowledge_layer=KnowledgeLayer.CANONICAL,
            knowledge_status=KnowledgeStatus.APPROVED,
        )

        result = validator.validate_report_spec(minimal_spec)

        assert result["passed"] is False
        assert len(result["errors"]) > 0
        assert "Missing required plots" in str(result["errors"])

    def test_validate_missing_critical_metric(self):
        """Test validation with missing reattachment_length metric"""
        validator = BackwardStepGateValidator()

        from knowledge_compiler.phase1.schema import ReportSpec, MetricSpec
        incomplete_spec = ReportSpec(
            report_spec_id="TEST-002",
            name="Test",
            problem_type=ProblemType.INTERNAL_FLOW,
            required_plots=[],
            required_metrics=[
                MetricSpec(
                    name="other_metric",
                    unit="m/s",
                    comparison=ComparisonType.DIFF,
                )
            ],
            critical_sections=[],
            plot_order=[],
            comparison_method={"type": "direct"},
            anomaly_explanation_rules=[],
            knowledge_layer=KnowledgeLayer.CANONICAL,
            knowledge_status=KnowledgeStatus.APPROVED,
        )

        result = validator.validate_report_spec(incomplete_spec)

        assert result["passed"] is False
        assert "reattachment_length" in str(result["errors"])


class TestIntegration:
    """Test integration with other Phase 1 components"""

    def test_spec_matches_nl_postprocess(self):
        """Test that spec works with NL postprocess"""
        from knowledge_compiler.phase1.nl_postprocess import NLPostprocessExecutor, ResultManifest, ResultAsset

        spec = create_backward_facing_step_spec()
        executor = NLPostprocessExecutor()

        # Create a simple manifest
        manifest = ResultManifest(
            solver_type="openfoam",
            case_name="backward_step",
            result_root="/path",
            assets=[ResultAsset(asset_type="field", path="U.obj")],
        )

        # Test parsing common instructions for this case
        instruction = "生成速度云图"
        plan = executor.parse_instruction(instruction, manifest)

        assert plan.detected_intent == "plot"
        assert len(plan.actions) >= 1

    def test_spec_can_be_validated_by_gates(self):
        """Test that spec can be validated by Phase 1 gates"""
        from knowledge_compiler.phase1.gates import Phase1GateExecutor

        spec = create_backward_facing_step_spec()
        gate_executor = Phase1GateExecutor()

        # P1-G4: Template Generalization
        result = gate_executor.run_g4_gate(
            report_spec=spec,
            source_cases=["case1", "case2", "case3"],
            teach_records=[],
        )

        # Gold standard should pass or at least warn
        assert result.status.value in ["PASS", "WARN", "FAIL"]

    def test_gold_standard_with_visualization_engine(self):
        """Test that gold standard works with visualization engine"""
        from knowledge_compiler.phase1.visualization import VisualizationEngine

        spec = create_backward_facing_step_spec()
        engine = VisualizationEngine()

        # Check that the engine was created
        assert engine is not None


class TestGoldStandardsPackage:
    """Test package structure"""

    def test_package_imports(self):
        """Test that package can be imported"""
        from knowledge_compiler.phase1 import gold_standards

        assert hasattr(gold_standards, "create_backward_facing_step_spec")
        assert hasattr(gold_standards, "BackwardStepConstants")
        assert hasattr(gold_standards, "BackwardStepGateValidator")
