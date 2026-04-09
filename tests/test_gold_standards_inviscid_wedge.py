#!/usr/bin/env python3
"""
Tests for Inviscid Supersonic Wedge Gold Standard
"""

import pytest

from knowledge_compiler.phase1.gold_standards import (
    InviscidWedgeConstants,
    create_inviscid_wedge_spec,
    InviscidWedgeGateValidator,
    get_expected_shock_angle,
)
from knowledge_compiler.phase1.schema import (
    ProblemType,
    ReportSpec,
    MetricSpec,
    ComparisonType,
    KnowledgeLayer,
    KnowledgeStatus,
)


class TestInviscidWedgeConstants:
    """Test physical constants for supersonic wedge case"""

    def test_wedge_geometry(self):
        """Test wedge geometry parameters"""
        assert InviscidWedgeConstants.WEDGE_ANGLE == 15.0
        assert InviscidWedgeConstants.WEDGE_LENGTH == 2.0

    def test_flow_conditions(self):
        """Test freestream flow conditions"""
        assert InviscidWedgeConstants.MACH == 2.0
        assert InviscidWedgeConstants.GAMMA == 1.4

    def test_mach_is_supersonic(self):
        """Test that freestream Mach number is supersonic"""
        assert InviscidWedgeConstants.MACH > 1.0

    def test_shock_angle_valid_range(self):
        """Test shock angle is between Mach angle and 90 degrees"""
        from math import degrees, asin
        mach_angle = degrees(asin(1.0 / InviscidWedgeConstants.MACH))
        assert mach_angle < InviscidWedgeConstants.SHOCK_ANGLE < 90.0

    def test_downstream_mach_supersonic(self):
        """Test post-shock Mach is still supersonic (weak shock solution)"""
        assert InviscidWedgeConstants.DOWNSTREAM_MACH > 1.0

    def test_pressure_jump_positive(self):
        """Test pressure jump ratio is greater than 1 (compression)"""
        assert InviscidWedgeConstants.PRESSURE_JUMP_RATIO > 1.0

    def test_downstream_mach_less_than_freestream(self):
        """Test post-shock Mach is less than freestream Mach"""
        assert InviscidWedgeConstants.DOWNSTREAM_MACH < InviscidWedgeConstants.MACH


class TestCreateInviscidWedgeSpec:
    """Test ReportSpec creation for inviscid wedge"""

    def test_default_spec_creation(self):
        """Test creating spec with default parameters"""
        spec = create_inviscid_wedge_spec()

        assert spec.report_spec_id == "GOLD-inviscid_wedge"
        assert spec.problem_type == ProblemType.EXTERNAL_FLOW
        assert spec.knowledge_layer == KnowledgeLayer.CANONICAL
        assert spec.knowledge_status == KnowledgeStatus.APPROVED

    def test_custom_spec_creation(self):
        """Test creating spec with custom parameters"""
        spec = create_inviscid_wedge_spec(
            case_id="custom_wedge",
            mach_number=3.0,
            wedge_angle=20.0,
        )

        assert spec.report_spec_id == "GOLD-custom_wedge"
        assert "M=3.0" in spec.name
        assert "theta=20.0deg" in spec.name

    def test_required_plots(self):
        """Test that all required plots are included"""
        spec = create_inviscid_wedge_spec()

        plot_names = {p.name for p in spec.required_plots}

        assert "mach_contour" in plot_names
        assert "pressure_contour" in plot_names
        assert "density_gradient" in plot_names

    def test_required_metrics(self):
        """Test that all required metrics are included"""
        spec = create_inviscid_wedge_spec()

        metric_names = {m.name for m in spec.required_metrics}

        assert "shock_angle" in metric_names
        assert "downstream_mach" in metric_names
        assert "pressure_jump_ratio" in metric_names

    def test_required_sections(self):
        """Test that all required sections are included"""
        spec = create_inviscid_wedge_spec()

        section_names = {s.name for s in spec.critical_sections}

        assert "upstream" in section_names
        assert "post_shock" in section_names
        assert "wedge_surface" in section_names

    def test_plot_order(self):
        """Test that plot order is defined"""
        spec = create_inviscid_wedge_spec()

        assert len(spec.plot_order) == 3
        assert "mach_contour" in spec.plot_order[0]


class TestGetExpectedShockAngle:
    """Test oblique shock angle calculation (theta-beta-M relation)"""

    def test_default_mach_2_theta_15(self):
        """Test default case: M=2.0, theta=15 deg"""
        beta = get_expected_shock_angle(mach_number=2.0, wedge_angle=15.0)
        # Expected ~45.34 deg for weak shock solution
        assert 44.0 < beta < 46.5

    def test_agrees_with_constant(self):
        """Test that calculated angle matches stored constant"""
        beta = get_expected_shock_angle(
            mach_number=InviscidWedgeConstants.MACH,
            wedge_angle=InviscidWedgeConstants.WEDGE_ANGLE,
        )
        assert abs(beta - InviscidWedgeConstants.SHOCK_ANGLE) < 1.0

    def test_higher_mach_larger_angle(self):
        """Test that higher Mach at same wedge angle gives different shock angle"""
        beta_m2 = get_expected_shock_angle(mach_number=2.0, wedge_angle=15.0)
        beta_m3 = get_expected_shock_angle(mach_number=3.0, wedge_angle=15.0)
        # Higher Mach -> weaker shock angle for same deflection
        assert beta_m3 < beta_m2

    def test_larger_wedge_larger_shock_angle(self):
        """Test that larger wedge angle produces larger shock angle"""
        beta_15 = get_expected_shock_angle(mach_number=2.0, wedge_angle=15.0)
        beta_20 = get_expected_shock_angle(mach_number=2.0, wedge_angle=20.0)
        assert beta_20 > beta_15


class TestInviscidWedgeGateValidator:
    """Test gold standard gate validator for inviscid wedge"""

    def test_validator_creation(self):
        """Test creating validator"""
        validator = InviscidWedgeGateValidator()

        assert validator.gold_spec is not None
        assert validator.gold_spec.knowledge_layer == KnowledgeLayer.CANONICAL

    def test_validate_perfect_spec(self):
        """Test validation of spec matching gold standard"""
        validator = InviscidWedgeGateValidator()

        result = validator.validate_report_spec(validator.gold_spec)

        assert result["passed"] is True
        assert len(result["errors"]) == 0
        assert result["details"]["plot_coverage"] == 1.0
        assert result["details"]["metric_coverage"] == 1.0

    def test_validate_missing_plots(self):
        """Test validation with missing plots"""
        validator = InviscidWedgeGateValidator()

        minimal_spec = ReportSpec(
            report_spec_id="TEST-001",
            name="Test",
            problem_type=ProblemType.EXTERNAL_FLOW,
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
        assert "Missing required plots" in str(result["errors"])

    def test_validate_missing_critical_metric(self):
        """Test validation with missing shock_angle metric"""
        validator = InviscidWedgeGateValidator()

        incomplete_spec = ReportSpec(
            report_spec_id="TEST-002",
            name="Test",
            problem_type=ProblemType.EXTERNAL_FLOW,
            required_plots=[],
            required_metrics=[
                MetricSpec(
                    name="other_metric",
                    unit="Pa",
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
        assert "shock_angle" in str(result["errors"])

    def test_validate_missing_sections_warning(self):
        """Test that missing sections produce warnings but not errors"""
        validator = InviscidWedgeGateValidator()

        # Build spec with plots and metrics but no sections
        from knowledge_compiler.phase1.schema import PlotSpec, MetricSpec

        spec_with_no_sections = ReportSpec(
            report_spec_id="TEST-003",
            name="Test",
            problem_type=ProblemType.EXTERNAL_FLOW,
            required_plots=[
                PlotSpec(name=p.name, plane=p.plane, colormap=p.colormap, range=p.range)
                for p in validator.gold_spec.required_plots
            ],
            required_metrics=[
                MetricSpec(name=m.name, unit=m.unit, comparison=m.comparison)
                for m in validator.gold_spec.required_metrics
            ],
            critical_sections=[],
            plot_order=[],
            comparison_method={"type": "direct"},
            anomaly_explanation_rules=[],
            knowledge_layer=KnowledgeLayer.CANONICAL,
            knowledge_status=KnowledgeStatus.APPROVED,
        )

        result = validator.validate_report_spec(spec_with_no_sections)

        # Missing sections should be warnings, not errors
        assert len(result["warnings"]) > 0
        assert "Missing recommended sections" in str(result["warnings"])


class TestGoldStandardsPackage:
    """Test package-level imports for inviscid wedge"""

    def test_package_imports(self):
        """Test that inviscid wedge symbols are importable from package"""
        from knowledge_compiler.phase1 import gold_standards

        assert hasattr(gold_standards, "InviscidWedgeConstants")
        assert hasattr(gold_standards, "create_inviscid_wedge_spec")
        assert hasattr(gold_standards, "InviscidWedgeGateValidator")
        assert hasattr(gold_standards, "get_expected_shock_angle")
