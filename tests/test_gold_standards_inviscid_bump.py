#!/usr/bin/env python3
"""
Tests for Inviscid Bump in Channel Gold Standard
"""

import pytest

from knowledge_compiler.phase1.gold_standards import (
    InviscidBumpConstants,
    create_inviscid_bump_spec,
    InviscidBumpGateValidator,
    get_expected_pressure_ratio,
)
from knowledge_compiler.phase1.schema import (
    ProblemType,
    ReportSpec,
    MetricSpec,
    ComparisonType,
    KnowledgeLayer,
    KnowledgeStatus,
)


class TestInviscidBumpConstants:
    """Test physical constants for inviscid bump in channel case"""

    def test_channel_geometry(self):
        """Test channel and bump geometry parameters"""
        assert InviscidBumpConstants.CHANNEL_LENGTH == 3.0
        assert InviscidBumpConstants.CHANNEL_HEIGHT == 1.0
        assert InviscidBumpConstants.BUMP_HEIGHT == 0.05
        assert InviscidBumpConstants.BUMP_LENGTH == 1.0

    def test_flow_conditions(self):
        """Test freestream flow conditions"""
        assert InviscidBumpConstants.MACH == 0.5
        assert InviscidBumpConstants.GAMMA == 1.4
        assert InviscidBumpConstants.AOAs == 0.0

    def test_mach_subsonic(self):
        """Test Mach number is subsonic"""
        assert InviscidBumpConstants.MACH < 1.0

    def test_bump_height_ratio(self):
        """Test bump height is a small fraction of channel height (thin bump)"""
        ratio = InviscidBumpConstants.BUMP_HEIGHT / InviscidBumpConstants.CHANNEL_HEIGHT
        assert ratio == 0.05  # 5% blockage

    def test_pressure_ratio_greater_than_one(self):
        """Test expected pressure ratio > 1 (compression over bump)"""
        assert InviscidBumpConstants.EXPECTED_PRESSURE_RATIO > 1.0

    def test_pressure_ratio_small_perturbation(self):
        """Test pressure ratio is a small perturbation (subsonic thin bump)"""
        assert InviscidBumpConstants.EXPECTED_PRESSURE_RATIO < 1.5


class TestCreateInviscidBumpSpec:
    """Test ReportSpec creation for inviscid bump"""

    def test_default_spec_creation(self):
        """Test creating spec with default parameters"""
        spec = create_inviscid_bump_spec()

        assert spec.report_spec_id == "GOLD-inviscid_bump"
        assert spec.problem_type == ProblemType.EXTERNAL_FLOW
        assert spec.knowledge_layer == KnowledgeLayer.CANONICAL
        assert spec.knowledge_status == KnowledgeStatus.APPROVED

    def test_custom_spec_creation(self):
        """Test creating spec with custom Mach number"""
        spec = create_inviscid_bump_spec(
            case_id="custom_bump",
            mach_number=0.8,
        )

        assert spec.report_spec_id == "GOLD-custom_bump"
        assert "M=0.8" in spec.name

    def test_required_plots(self):
        """Test that all required plots are included"""
        spec = create_inviscid_bump_spec()

        plot_names = {p.name for p in spec.required_plots}

        assert "mach_contour" in plot_names
        assert "pressure_contour" in plot_names
        assert "velocity_magnitude" in plot_names

    def test_required_metrics(self):
        """Test that all required metrics are included"""
        spec = create_inviscid_bump_spec()

        metric_names = {m.name for m in spec.required_metrics}

        assert "max_mach" in metric_names
        assert "pressure_ratio" in metric_names
        assert "mass_flow_rate" in metric_names

    def test_required_sections(self):
        """Test that all required sections are included"""
        spec = create_inviscid_bump_spec()

        section_names = {s.name for s in spec.critical_sections}

        assert "inlet" in section_names
        assert "bump_surface" in section_names
        assert "outlet" in section_names

    def test_plot_order(self):
        """Test that plot order is defined"""
        spec = create_inviscid_bump_spec()

        assert len(spec.plot_order) == 3
        assert "mach_contour" in spec.plot_order[0]


class TestGetExpectedPressureRatio:
    """Test pressure ratio calculation for inviscid bump"""

    def test_default_mach_05(self):
        """Test default case: M=0.5"""
        p_ratio = get_expected_pressure_ratio(mach_number=0.5)
        # p_ratio = 1 + gamma * M^2 * (h/H) * 2
        # = 1 + 1.4 * 0.25 * 0.05 * 2 = 1.035
        assert 1.0 < p_ratio < 1.1

    def test_agrees_with_constant(self):
        """Test that calculated ratio is consistent with stored constant"""
        p_ratio = get_expected_pressure_ratio(InviscidBumpConstants.MACH)
        # Should be in the same ballpark as the constant
        assert abs(p_ratio - InviscidBumpConstants.EXPECTED_PRESSURE_RATIO) < 0.1

    def test_higher_mach_higher_pressure_ratio(self):
        """Test that higher Mach gives higher pressure ratio"""
        p_m03 = get_expected_pressure_ratio(mach_number=0.3)
        p_m05 = get_expected_pressure_ratio(mach_number=0.5)
        p_m08 = get_expected_pressure_ratio(mach_number=0.8)

        assert p_m03 < p_m05 < p_m08

    def test_zero_mach_gives_unity(self):
        """Test that M=0 gives pressure ratio of 1.0 (no flow)"""
        p_ratio = get_expected_pressure_ratio(mach_number=0.0)
        assert abs(p_ratio - 1.0) < 1e-12


class TestInviscidBumpGateValidator:
    """Test gold standard gate validator for inviscid bump"""

    def test_validator_creation(self):
        """Test creating validator"""
        validator = InviscidBumpGateValidator()

        assert validator.gold_spec is not None
        assert validator.gold_spec.knowledge_layer == KnowledgeLayer.CANONICAL

    def test_validate_perfect_spec(self):
        """Test validation of spec matching gold standard"""
        validator = InviscidBumpGateValidator()

        result = validator.validate_report_spec(validator.gold_spec)

        assert result["passed"] is True
        assert len(result["errors"]) == 0
        assert result["details"]["plot_coverage"] == 1.0
        assert result["details"]["metric_coverage"] == 1.0

    def test_validate_missing_plots(self):
        """Test validation with missing plots"""
        validator = InviscidBumpGateValidator()

        minimal_spec = ReportSpec(
            report_spec_id="TEST-020",
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
        """Test validation with missing pressure_ratio metric"""
        validator = InviscidBumpGateValidator()

        incomplete_spec = ReportSpec(
            report_spec_id="TEST-021",
            name="Test",
            problem_type=ProblemType.EXTERNAL_FLOW,
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
        assert "pressure_ratio" in str(result["errors"])

    def test_validate_missing_sections_warning(self):
        """Test that missing sections produce warnings but not errors"""
        validator = InviscidBumpGateValidator()

        from knowledge_compiler.phase1.schema import PlotSpec, MetricSpec

        spec_with_no_sections = ReportSpec(
            report_spec_id="TEST-022",
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

        assert len(result["warnings"]) > 0
        assert "Missing recommended sections" in str(result["warnings"])


class TestGoldStandardsPackage:
    """Test package-level imports for inviscid bump"""

    def test_package_imports(self):
        """Test that inviscid bump symbols are importable from package"""
        from knowledge_compiler.phase1 import gold_standards

        assert hasattr(gold_standards, "InviscidBumpConstants")
        assert hasattr(gold_standards, "create_inviscid_bump_spec")
        assert hasattr(gold_standards, "InviscidBumpGateValidator")
        assert hasattr(gold_standards, "get_expected_pressure_ratio")
