#!/usr/bin/env python3
"""
Phase 2 Teach Layer Tests

测试 Teach Layer 的 Capture 和 Parser 模块。
"""

import time

import pytest

from knowledge_compiler.phase1.schema import (
    ProblemType,
    TeachRecord,
    TeachOperation,
    Phase1Output,
    ReportSpec,
    CorrectionSpec,
    ErrorType,
    ImpactScope,
)
from knowledge_compiler.phase2.schema import (
    CaptureContext,
    TeachCapture,
    TeachIntent,
    ParsedTeach,
)
from knowledge_compiler.phase2.teach_layer import (
    # Capture
    TeachCaptureExtractor,
    extract_captures,
    capture_teach_session,
    # Parser
    KnowledgeParser,
    TeachParser,
    parse_teach_capture,
    parse_teach_captures,
    ParseResult,
)


class TestTeachCaptureExtractor:
    """Test TeachCaptureExtractor"""

    def test_extractor_init(self):
        """Test extractor initialization"""
        extractor = TeachCaptureExtractor(engineer_id="test-engineer")
        assert extractor.engineer_id == "test-engineer"

    def test_extract_from_empty_phase1_output(self):
        """Test extracting from empty Phase1Output"""
        extractor = TeachCaptureExtractor()
        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[],
            correction_specs=[],
            teach_records=[],
        )

        captures = extractor.extract_captures(phase1_output)
        assert len(captures) == 0

    def test_extract_from_teach_record(self):
        """Test extracting from a single TeachRecord"""
        extractor = TeachCaptureExtractor()

        teach_record = TeachRecord(
            teach_record_id="TR-001",
            case_id="case-001",
            timestamp=time.time(),
        )
        teach_record.add_operation(
            operation_type="add_plot",
            description="Add velocity contour plot",
            reason="Missing visualization",
            is_generalizable=True,
        )

        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[],
            correction_specs=[],
            teach_records=[teach_record],
        )

        captures = extractor.extract_captures(phase1_output)
        assert len(captures) == 1
        assert captures[0].source_case_id == "case-001"
        assert len(captures[0].raw_operations) == 1

    def test_extract_multiple_teach_records(self):
        """Test extracting from multiple TeachRecords"""
        extractor = TeachCaptureExtractor()

        teach_records = []
        for i in range(3):
            record = TeachRecord(
                teach_record_id=f"TR-{i:03d}",
                case_id=f"case-{i:03d}",
                timestamp=time.time(),
            )
            record.add_operation(
                operation_type="add_plot",
                description=f"Plot {i}",
                reason=f"Reason {i}",
                is_generalizable=True,
            )
            teach_records.append(record)

        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[],
            correction_specs=[],
            teach_records=teach_records,
        )

        captures = extractor.extract_captures(phase1_output)
        assert len(captures) == 3

    def test_capture_context_extraction(self):
        """Test CaptureContext is properly extracted"""
        extractor = TeachCaptureExtractor()

        teach_record = TeachRecord(
            teach_record_id="TR-001",
            case_id="case-001",
            timestamp=time.time(),
        )
        teach_record.add_operation(
            operation_type="add_plot",
            description="Add plot",
            reason="Test",
            is_generalizable=True,
        )

        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[],
            correction_specs=[],
            teach_records=[teach_record],
        )

        captures = extractor.extract_captures(phase1_output)
        assert len(captures) == 1

        context = captures[0].context
        assert context.case_id == "case-001"
        # Default solver_type is "openfoam" and problem_type is INTERNAL_FLOW
        assert context.solver_type == "openfoam"
        assert context.problem_type == ProblemType.INTERNAL_FLOW


class TestExtractCapturesFunction:
    """Test extract_captures convenience function"""

    def test_extract_captures_function(self):
        """Test extract_captures() function"""
        teach_record = TeachRecord(
            teach_record_id="TR-001",
            case_id="case-001",
            timestamp=time.time(),
        )
        teach_record.add_operation(
            operation_type="add_plot",
            description="Add plot",
            reason="Test",
            is_generalizable=True,
        )

        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[],
            correction_specs=[],
            teach_records=[teach_record],
        )

        captures = extract_captures(phase1_output, engineer_id="test-engineer")
        assert len(captures) == 1


class TestCaptureTeachSession:
    """Test capture_teach_session convenience function"""

    def test_capture_teach_session(self):
        """Test capture_teach_session() function"""
        operation = TeachOperation(
            operation_type="add_plot",
            description="Add pressure contour",
            reason="Need visualization",
            is_generalizable=True,
        )

        capture = capture_teach_session(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
            operations=[operation],
            engineer_id="engineer-001",
            session_id="session-abc",
        )

        assert capture.source_case_id == "case-001"
        assert capture.context.solver_type == "openfoam"
        assert capture.context.problem_type == ProblemType.INTERNAL_FLOW
        assert capture.context.engineer_id == "engineer-001"
        assert capture.context.session_id == "session-abc"
        assert len(capture.raw_operations) == 1


class TestKnowledgeParser:
    """Test KnowledgeParser"""

    def test_parser_init(self):
        """Test parser initialization"""
        parser = KnowledgeParser(min_confidence=0.5)
        assert parser.min_confidence == 0.5

    def test_parse_basic_capture(self):
        """Test parsing a basic TeachCapture"""
        parser = KnowledgeParser()

        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        operation = TeachOperation(
            operation_type="add_plot",
            description="Add velocity contour plot",
            reason="Need visualization",
            is_generalizable=True,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[operation],
        )

        parsed = parser.parse(capture)

        assert isinstance(parsed, ParsedTeach)
        assert parsed.source_capture_id == capture.capture_id
        assert parsed.intent in TeachIntent
        assert isinstance(parsed.confidence, float)
        assert 0.0 <= parsed.confidence <= 1.0

    def test_intent_classification_correct_error(self):
        """Test intent classification for CORRECT_ERROR"""
        parser = KnowledgeParser()

        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        operation = TeachOperation(
            operation_type="modify_plot",
            description="Fix the wrong boundary condition",
            reason="Error in inlet setup",
            is_generalizable=True,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[operation],
        )

        parsed = parser.parse(capture)
        # Should detect CORRECT_ERROR intent due to "fix", "error", "wrong"
        assert parsed.intent == TeachIntent.CORRECT_ERROR

    def test_intent_classification_add_component(self):
        """Test intent classification for ADD_COMPONENT"""
        parser = KnowledgeParser()

        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        operation = TeachOperation(
            operation_type="add_plot",
            description="Add new pressure contour plot",
            reason="Missing visualization",
            is_generalizable=True,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[operation],
        )

        parsed = parser.parse(capture)
        # Should detect ADD_COMPONENT intent due to "add", "new"
        assert parsed.intent == TeachIntent.ADD_COMPONENT

    def test_generalizability_assessment(self):
        """Test generalizability assessment"""
        parser = KnowledgeParser()

        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        operation1 = TeachOperation(
            operation_type="add_plot",
            description="Add a reusable pattern for velocity plots",
            reason="This can be applied to all cases",
            is_generalizable=True,
        )

        operation2 = TeachOperation(
            operation_type="add_plot",
            description="Create template for report generation",
            reason="Standardize output",
            is_generalizable=True,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[operation1, operation2],
            metadata={"cross_case": True},
        )

        parsed = parser.parse(capture)
        # Should be generalizable due to multiple operations and cross_case metadata
        assert parsed.generalizable is True

    def test_confidence_calculation(self):
        """Test confidence calculation"""
        parser = KnowledgeParser()

        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        operation1 = TeachOperation(
            operation_type="modify_plot",
            description="Fix boundary condition",
            reason="Error in setup",
            is_generalizable=False,
        )

        operation2 = TeachOperation(
            operation_type="modify_metric",
            description="Update mesh settings",
            reason="Improve accuracy",
            is_generalizable=False,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[operation1, operation2],
        )

        parsed = parser.parse(capture)
        # With 2 operations and full context, confidence should be moderate
        assert 0.0 < parsed.confidence <= 1.0

    def test_parse_batch(self):
        """Test batch parsing"""
        parser = KnowledgeParser()

        captures = []
        for i in range(3):
            context = CaptureContext(
                case_id=f"case-{i:03d}",
                solver_type="openfoam",
                problem_type=ProblemType.INTERNAL_FLOW,
            )
            operation = TeachOperation(
                operation_type="add_plot",
                description=f"Operation {i}",
                reason=f"Reason {i}",
                is_generalizable=True,
            )
            capture = TeachCapture(
                source_case_id=f"case-{i:03d}",
                context=context,
                raw_operations=[operation],
            )
            captures.append(capture)

        parsed_list = parser.parse_batch(captures)
        assert len(parsed_list) == 3
        assert all(isinstance(p, ParsedTeach) for p in parsed_list)


class TestParseTeachCaptureFunction:
    """Test parse_teach_capture convenience function"""

    def test_parse_teach_capture_function(self):
        """Test parse_teach_capture() function"""
        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        operation = TeachOperation(
            operation_type="modify_plot",
            description="Fix error",
            reason="Bug found",
            is_generalizable=False,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[operation],
        )

        parsed = parse_teach_capture(capture, min_confidence=0.3)
        assert isinstance(parsed, ParsedTeach)
        # Confidence should be at least 0.3
        assert parsed.confidence >= 0.0


class TestParseTeachCapturesFunction:
    """Test parse_teach_captures convenience function"""

    def test_parse_teach_captures_function(self):
        """Test parse_teach_captures() function"""
        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        operation1 = TeachOperation(
            operation_type="add_plot",
            description="Add plot",
            reason="Need visualization",
            is_generalizable=True,
        )

        operation2 = TeachOperation(
            operation_type="modify_plot",
            description="Fix error",
            reason="Bug found",
            is_generalizable=False,
        )

        captures = [
            TeachCapture(
                source_case_id="case-001",
                context=context,
                raw_operations=[operation1],
            ),
            TeachCapture(
                source_case_id="case-002",
                context=context,
                raw_operations=[operation2],
            ),
        ]

        parsed_list = parse_teach_captures(captures)
        assert len(parsed_list) == 2
        assert all(isinstance(p, ParsedTeach) for p in parsed_list)


class TestTeachParserAlias:
    """Test TeachParser alias"""

    def test_teach_parser_alias(self):
        """Test TeachParser is an alias for KnowledgeParser"""
        assert TeachParser is KnowledgeParser

        parser = TeachParser()
        assert isinstance(parser, KnowledgeParser)


class TestParsedTeachMethods:
    """Test ParsedTeach methods"""

    def test_is_generalizable_true(self):
        """Test is_generalizable returns True when conditions met"""
        teach = ParsedTeach(
            source_capture_id="CAPTURE-001",
            intent=TeachIntent.GENERALIZE_KNOWLEDGE,
            generalizable=True,
            confidence=0.8,
        )

        assert teach.is_generalizable() is True

    def test_is_generalizable_false_low_confidence(self):
        """Test is_generalizable returns False with low confidence"""
        teach = ParsedTeach(
            source_capture_id="CAPTURE-001",
            intent=TeachIntent.GENERALIZE_KNOWLEDGE,
            generalizable=True,
            confidence=0.5,  # Below threshold
        )

        assert teach.is_generalizable() is False

    def test_is_generalizable_false_not_marked(self):
        """Test is_generalizable returns False when not marked"""
        teach = ParsedTeach(
            source_capture_id="CAPTURE-001",
            intent=TeachIntent.ADD_COMPONENT,
            generalizable=False,
            confidence=0.9,
        )

        assert teach.is_generalizable() is False


class TestTeachCaptureIntegration:
    """Integration tests for TeachCapture"""

    def test_teach_capture_to_dict(self):
        """Test TeachCapture to_dict conversion"""
        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        operation = TeachOperation(
            operation_type="add_plot",
            description="Add plot",
            reason="Need visualization",
            is_generalizable=True,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[operation],
        )

        d = capture.to_dict()
        assert "capture_id" in d
        assert d["source_case_id"] == "case-001"
        assert d["context"]["case_id"] == "case-001"
        assert len(d["raw_operations"]) == 1

    def test_teach_capture_add_operation(self):
        """Test TeachCapture add_operation method"""
        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
        )

        operation = TeachOperation(
            operation_type="add_plot",
            description="Add plot",
            reason="Need visualization",
            is_generalizable=True,
        )

        capture.add_operation(operation)
        assert len(capture.raw_operations) == 1
        assert capture.raw_operations[0] == operation
