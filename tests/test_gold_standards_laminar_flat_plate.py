#!/usr/bin/env python3
"""
Tests for Laminar Flat Plate Gold Standard
"""

import pytest
from math import sqrt

from knowledge_compiler.phase1.gold_standards import (
    LaminarFlatPlateConstants,
    create_laminar_flat_plate_spec,
    LaminarFlatPlateGateValidator,
    get_expected_blasius_cf,
)
from knowledge_compiler.phase1.schema import (
    ProblemType,
    ReportSpec,
    MetricSpec,
    ComparisonType,
    KnowledgeLayer,
    KnowledgeStatus,
)


class TestLaminarFlatPlateConstants:
    """Test physical constants for laminar flat plate case"""

    def test_geometry(self):
        """Test plate geometry parameters"""
        assert LaminarFlatPlateConstants.PLATE_LENGTH == 1.0
        assert LaminarFlatPlateConstants.PLATE_START == 0.0
        assert LaminarFlatPlateConstants.DOMAIN_HEIGHT == 0.5

    def test_flow_conditions(self):
        """Test freestream flow conditions"""
        assert LaminarFlatPlateConstants.MACH == 0.3
        assert LaminarFlatPlateConstants.RE_LENGTH == 5000.0
        assert LaminarFlatPlateConstants.FREESTREAM_TEMP == 300.0
        assert LaminarFlatPlateConstants.GAMMA == 1.4
        assert LaminarFlatPlateConstants.PRANDTL == 0.72

    def test_mach_subsonic(self):
        """Test Mach number is subsonic"""
        assert LaminarFlatPlateConstants.MACH < 1.0

    def test_reynolds_positive(self):
        """Test Reynolds number is positive and physically meaningful"""
        assert LaminarFlatPlateConstants.RE_LENGTH > 0

    def test_blasius_delta_consistency(self):
        """Test BL thickness matches Blasius formula: delta ~ 5.0 * L / sqrt(Re_L)"""
        expected_delta = 5.0 * LaminarFlatPlateConstants.PLATE_LENGTH / sqrt(
            LaminarFlatPlateConstants.RE_LENGTH
        )
        assert abs(LaminarFlatPlateConstants.BLASIUS_DELTA - expected_delta) < 0.001

    def test_blasius_delta_star_consistency(self):
        """Test displacement thickness matches Blasius: delta* ~ 1.7208 * L / sqrt(Re_L)"""
        expected_delta_star = 1.7208 * LaminarFlatPlateConstants.PLATE_LENGTH / sqrt(
            LaminarFlatPlateConstants.RE_LENGTH
        )
        assert abs(LaminarFlatPlateConstants.BLASIUS_DELTA_STAR - expected_delta_star) < 0.001

    def test_delta_star_less_than_delta(self):
        """Test displacement thickness is less than boundary layer thickness"""
        assert LaminarFlatPlateConstants.BLASIUS_DELTA_STAR < LaminarFlatPlateConstants.BLASIUS_DELTA


class TestCreateLaminarFlatPlateSpec:
    """Test ReportSpec creation for laminar flat plate"""

    def test_default_spec_creation(self):
        """Test creating spec with default parameters"""
        spec = create_laminar_flat_plate_spec()

        assert spec.report_spec_id == "GOLD-laminar_flat_plate"
        assert spec.problem_type == ProblemType.EXTERNAL_FLOW
        assert spec.knowledge_layer == KnowledgeLayer.CANONICAL
        assert spec.knowledge_status == KnowledgeStatus.APPROVED

    def test_custom_spec_creation(self):
        """Test creating spec with custom Reynolds number"""
        spec = create_laminar_flat_plate_spec(
            case_id="custom_plate",
            reynolds_length=10000.0,
        )

        assert spec.report_spec_id == "GOLD-custom_plate"
        assert "Re_L=10000.0" in spec.name

    def test_required_plots(self):
        """Test that all required plots are included"""
        spec = create_laminar_flat_plate_spec()

        plot_names = {p.name for p in spec.required_plots}

        assert "velocity_magnitude" in plot_names
        assert "boundary_layer_profile" in plot_names
        assert "skin_friction" in plot_names

    def test_required_metrics(self):
        """Test that all required metrics are included"""
        spec = create_laminar_flat_plate_spec()

        metric_names = {m.name for m in spec.required_metrics}

        assert "cf_at_x1" in metric_names
        assert "boundary_layer_thickness" in metric_names
        assert "displacement_thickness" in metric_names

    def test_required_sections(self):
        """Test that all required sections are included"""
        spec = create_laminar_flat_plate_spec()

        section_names = {s.name for s in spec.critical_sections}

        assert "leading_edge" in section_names
        assert "mid_plate" in section_names
        assert "trailing_edge" in section_names

    def test_plot_order(self):
        """Test that plot order is defined"""
        spec = create_laminar_flat_plate_spec()

        assert len(spec.plot_order) == 3
        assert "velocity_magnitude" in spec.plot_order[0]


class TestGetExpectedBlasiusCf:
    """Test Blasius skin friction coefficient calculation"""

    def test_cf_at_trailing_edge(self):
        """Test Cf at x=1.0 (trailing edge), Re_x = Re_L = 5000"""
        cf = get_expected_blasius_cf(1.0)
        expected = 0.664 / sqrt(5000.0)
        assert abs(cf - expected) < 1e-10

    def test_cf_at_mid_plate(self):
        """Test Cf at x=0.5, Re_x = 2500"""
        cf = get_expected_blasius_cf(0.5)
        expected = 0.664 / sqrt(2500.0)
        assert abs(cf - expected) < 1e-10

    def test_cf_decreases_downstream(self):
        """Test that Cf decreases along the plate (Blasius behavior)"""
        cf_leading = get_expected_blasius_cf(0.1)
        cf_mid = get_expected_blasius_cf(0.5)
        cf_trailing = get_expected_blasius_cf(1.0)

        assert cf_leading > cf_mid > cf_trailing

    def test_cf_at_zero_returns_inf(self):
        """Test that Cf at x=0 returns infinity (singular)"""
        cf = get_expected_blasius_cf(0.0)
        assert cf == float("inf")

    def test_cf_positive_for_valid_x(self):
        """Test Cf is positive for x > 0"""
        cf = get_expected_blasius_cf(0.5)
        assert cf > 0


class TestLaminarFlatPlateGateValidator:
    """Test gold standard gate validator for laminar flat plate"""

    def test_validator_creation(self):
        """Test creating validator"""
        validator = LaminarFlatPlateGateValidator()

        assert validator.gold_spec is not None
        assert validator.gold_spec.knowledge_layer == KnowledgeLayer.CANONICAL

    def test_validate_perfect_spec(self):
        """Test validation of spec matching gold standard"""
        validator = LaminarFlatPlateGateValidator()

        result = validator.validate_report_spec(validator.gold_spec)

        assert result["passed"] is True
        assert len(result["errors"]) == 0
        assert result["details"]["plot_coverage"] == 1.0
        assert result["details"]["metric_coverage"] == 1.0

    def test_validate_missing_plots(self):
        """Test validation with missing plots"""
        validator = LaminarFlatPlateGateValidator()

        minimal_spec = ReportSpec(
            report_spec_id="TEST-010",
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
        """Test validation with missing cf_at_x1 metric"""
        validator = LaminarFlatPlateGateValidator()

        incomplete_spec = ReportSpec(
            report_spec_id="TEST-011",
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
        assert "cf_at_x1" in str(result["errors"])

    def test_validate_missing_sections_warning(self):
        """Test that missing sections produce warnings but not errors"""
        validator = LaminarFlatPlateGateValidator()

        from knowledge_compiler.phase1.schema import PlotSpec, MetricSpec

        spec_with_no_sections = ReportSpec(
            report_spec_id="TEST-012",
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
    """Test package-level imports for laminar flat plate"""

    def test_package_imports(self):
        """Test that laminar flat plate symbols are importable from package"""
        from knowledge_compiler.phase1 import gold_standards

        assert hasattr(gold_standards, "LaminarFlatPlateConstants")
        assert hasattr(gold_standards, "create_laminar_flat_plate_spec")
        assert hasattr(gold_standards, "LaminarFlatPlateGateValidator")
        assert hasattr(gold_standards, "get_expected_blasius_cf")
