#!/usr/bin/env python3
"""
Phase 2 Schema Tests

测试 Phase 2 核心数据模型的创建和基本功能。
"""

import time

import pytest

from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeStatus,
    ReportSpec,
    CorrectionSpec,
    ErrorType,
    ImpactScope,
    Phase1Output,
)
from knowledge_compiler.phase2.schema import (
    # Enums
    TeachIntent,
    SpecType,
    CompilationStatus,
    # Teach Layer
    CaptureContext,
    TeachCapture,
    ParsedTeach,
    # Compiler Layer
    CanonicalSpec,
    CompilationResult,
    # Input/Output
    CompilerConfig,
    Phase2Input,
    CompiledKnowledge,
    # Factory
    create_phase2_input,
    create_compiled_knowledge,
)


class TestCaptureContext:
    """Test CaptureContext creation"""

    def test_capture_context_creation(self):
        """Test creating a CaptureContext"""
        ctx = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        assert ctx.case_id == "case-001"
        assert ctx.solver_type == "openfoam"
        assert ctx.problem_type == ProblemType.INTERNAL_FLOW
        assert ctx.timestamp > 0


class TestTeachCapture:
    """Test TeachCapture functionality"""

    def test_teach_capture_creation(self):
        """Test creating a TeachCapture"""
        ctx = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=ctx,
        )

        assert capture.source_case_id == "case-001"
        assert capture.context == ctx
        assert capture.capture_id.startswith("CAPTURE-")
        assert len(capture.raw_operations) == 0

    def test_add_operation(self):
        """Test adding an operation to TeachCapture"""
        ctx = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=ctx,
        )

        # Add a mock operation (using a simple dict since TeachOperation is from phase1)
        # In real usage, this would be an actual TeachOperation
        capture.raw_operations.append({
            "operation_type": "add_plot",
            "description": "Add velocity contour plot",
            "reason": "Missing in original spec",
        })

        assert len(capture.raw_operations) == 1

    def test_to_dict(self):
        """Test TeachCapture to_dict conversion"""
        ctx = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=ctx,
        )

        d = capture.to_dict()

        assert "capture_id" in d
        assert "source_case_id" in d
        assert "context" in d
        assert "raw_operations" in d
        assert d["context"]["case_id"] == "case-001"


class TestParsedTeach:
    """Test ParsedTeach functionality"""

    def test_parsed_teach_creation(self):
        """Test creating a ParsedTeach"""
        teach = ParsedTeach(
            source_capture_id="CAPTURE-001",
            intent=TeachIntent.CORRECT_ERROR,
            generalizable=True,
            confidence=0.85,
        )

        assert teach.source_capture_id == "CAPTURE-001"
        assert teach.intent == TeachIntent.CORRECT_ERROR
        assert teach.generalizable is True
        assert teach.confidence == 0.85
        assert teach.teach_id.startswith("TEACH-")

    def test_is_generalizable(self):
        """Test is_generalizable method"""
        # High confidence, generalizable
        teach = ParsedTeach(
            source_capture_id="CAPTURE-001",
            intent=TeachIntent.CORRECT_ERROR,
            generalizable=True,
            confidence=0.8,
        )
        assert teach.is_generalizable() is True

        # Low confidence
        teach2 = ParsedTeach(
            source_capture_id="CAPTURE-002",
            intent=TeachIntent.ADD_COMPONENT,
            generalizable=True,
            confidence=0.5,
        )
        assert teach2.is_generalizable() is False

        # Not generalizable
        teach3 = ParsedTeach(
            source_capture_id="CAPTURE-003",
            intent=TeachIntent.REFINE_SCOPE,
            generalizable=False,
            confidence=0.9,
        )
        assert teach3.is_generalizable() is False


class TestCanonicalSpec:
    """Test CanonicalSpec functionality"""

    def test_canonical_spec_creation(self):
        """Test creating a CanonicalSpec"""
        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={
                "name": "Internal Flow Report",
                "required_plots": ["velocity_contour", "pressure_contour"],
                "required_metrics": ["pressure_drop"],
            },
        )

        assert spec.spec_type == SpecType.REPORT_SPEC
        assert spec.content["name"] == "Internal Flow Report"
        assert spec.knowledge_status == KnowledgeStatus.DRAFT
        assert spec.knowledge_layer.value == "Raw"
        assert spec.spec_id.startswith("SPEC-")

    def test_add_source(self):
        """Test adding source tracking"""
        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={},
        )

        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "case-002")

        assert "TEACH-001" in spec.source_teach_ids
        assert "TEACH-002" in spec.source_teach_ids
        assert "case-001" in spec.source_case_ids
        assert "case-002" in spec.source_case_ids

    def test_to_dict(self):
        """Test CanonicalSpec to_dict conversion"""
        spec = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={"colormap": "viridis"},
        )

        d = spec.to_dict()

        assert d["spec_type"] == "plot_standard"
        assert d["content"]["colormap"] == "viridis"
        assert "source_teach_ids" in d
        assert "source_case_ids" in d


class TestCompilerConfig:
    """Test CompilerConfig"""

    def test_default_config(self):
        """Test default CompilerConfig"""
        config = CompilerConfig()

        assert config.strict_mode is True
        assert config.enable_conflict_detection is True
        assert config.enable_backward_compatibility_check is True
        assert config.target_knowledge_layer.value == "Canonical"

    def test_custom_config(self):
        """Test custom CompilerConfig"""
        config = CompilerConfig(
            strict_mode=False,
            enable_conflict_detection=False,
        )

        assert config.strict_mode is False
        assert config.enable_conflict_detection is False


class TestPhase2Input:
    """Test Phase2Input functionality"""

    def test_phase2_input_creation(self):
        """Test creating Phase2Input"""
        # Create a mock Phase1Output
        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[],
            correction_specs=[],
            teach_records=[],
        )

        input_data = Phase2Input(
            phase1_output=phase1_output,
        )

        assert input_data.phase1_output == phase1_output
        assert input_data.input_id.startswith("P2-INPUT-")
        assert isinstance(input_data.config, CompilerConfig)

    def test_get_report_specs(self):
        """Test get_report_specs method"""
        # Create mock ReportSpecs
        spec1 = ReportSpec(
            report_spec_id="SPEC-001",
            name="Spec 1",
            problem_type=ProblemType.INTERNAL_FLOW,
        )
        spec2 = ReportSpec(
            report_spec_id="SPEC-002",
            name="Spec 2",
            problem_type=ProblemType.EXTERNAL_FLOW,
        )

        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[spec1, spec2],
        )

        input_data = Phase2Input(
            phase1_output=phase1_output,
        )

        specs = input_data.get_report_specs()
        assert len(specs) == 2
        assert specs[0].report_spec_id == "SPEC-001"

    def test_with_filters(self):
        """Test filtering with include/exclude"""
        spec1 = ReportSpec(
            report_spec_id="SPEC-001",
            name="Spec 1",
            problem_type=ProblemType.INTERNAL_FLOW,
        )
        spec2 = ReportSpec(
            report_spec_id="SPEC-002",
            name="Spec 2",
            problem_type=ProblemType.EXTERNAL_FLOW,
        )

        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[spec1, spec2],
        )

        # Test include filter
        input_data = Phase2Input(
            phase1_output=phase1_output,
            include_spec_ids={"SPEC-001"},
        )

        specs = input_data.get_report_specs()
        assert len(specs) == 1
        assert specs[0].report_spec_id == "SPEC-001"


class TestCompiledKnowledge:
    """Test CompiledKnowledge functionality"""

    def test_compiled_knowledge_creation(self):
        """Test creating CompiledKnowledge"""
        knowledge = CompiledKnowledge()

        assert knowledge.output_id.startswith("P2-OUTPUT-")
        assert knowledge.canonical_specs == []
        assert knowledge.compilation_results == []
        assert knowledge.total_input_count == 0
        assert knowledge.success_count == 0
        assert knowledge.failed_count == 0

    def test_add_spec(self):
        """Test adding a CanonicalSpec"""
        knowledge = CompiledKnowledge()

        spec = CanonicalSpec(
            spec_type=SpecType.REPORT_SPEC,
            content={"name": "Test"},
        )

        knowledge.add_spec(spec)

        assert len(knowledge.canonical_specs) == 1
        assert knowledge.canonical_specs[0] == spec

    def test_add_result(self):
        """Test adding CompilationResult"""
        knowledge = CompiledKnowledge()

        # Success result
        result1 = CompilationResult(
            success=True,
            output=CanonicalSpec(
                spec_type=SpecType.REPORT_SPEC,
                content={},
            ),
        )
        knowledge.add_result(result1)

        assert knowledge.success_count == 1
        assert knowledge.failed_count == 0

        # Failed result
        result2 = CompilationResult(
            success=False,
            output=None,
        )
        knowledge.add_result(result2)

        assert knowledge.success_count == 1
        assert knowledge.failed_count == 1

    def test_get_success_rate(self):
        """Test get_success_rate calculation"""
        knowledge = CompiledKnowledge()
        knowledge.total_input_count = 4

        # Add 2 success, 1 failed
        knowledge.add_result(CompilationResult(success=True, output=None))
        knowledge.add_result(CompilationResult(success=True, output=None))
        knowledge.add_result(CompilationResult(success=False, output=None))

        assert knowledge.get_success_rate() == 2/4


class TestFactoryFunctions:
    """Test factory functions"""

    def test_create_phase2_input(self):
        """Test create_phase2_input factory"""
        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[],
            correction_specs=[],
            teach_records=[],
        )

        input_data = create_phase2_input(
            phase1_output,
            strict_mode=False,
        )

        assert isinstance(input_data, Phase2Input)
        assert input_data.config.strict_mode is False

    def test_create_compiled_knowledge(self):
        """Test create_compiled_knowledge factory"""
        knowledge = create_compiled_knowledge()

        assert isinstance(knowledge, CompiledKnowledge)
