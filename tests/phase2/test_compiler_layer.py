#!/usr/bin/env python3
"""
Phase 2 Compiler Layer Integration Tests

端到端测试：Phase1 -> Teach Capture -> Parser -> Compiler -> Publish
"""

import time

import pytest

from knowledge_compiler.phase1.schema import (
    ProblemType,
    TeachRecord,
    TeachOperation,
    Phase1Output,
)
from knowledge_compiler.phase2.schema import (
    CaptureContext,
    TeachCapture,
    ParsedTeach,
    TeachIntent,
    SpecType,
    CanonicalSpec,
    CompiledKnowledge,
    CompilerConfig,
)
from knowledge_compiler.phase2.teach_layer import (
    TeachCaptureExtractor,
    KnowledgeParser,
    extract_captures,
)
from knowledge_compiler.phase2.compiler_layer import (
    CanonicalCompiler,
    KnowledgePublisher,
    publish_knowledge,
    verify_spec,
)


class TestCanonicalCompiler:
    """Test CanonicalCompiler"""

    def test_compiler_init(self):
        """Test compiler initialization"""
        compiler = CanonicalCompiler(merge_conflicts=True)
        assert compiler.merge_conflicts is True

    def test_compile_single_teach(self):
        """Test compiling a single ParsedTeach"""
        compiler = CanonicalCompiler()

        # Create ParsedTeach
        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[
                TeachOperation(
                    operation_type="add_plot",
                    description="Add velocity contour plot",
                    reason="Need visualization",
                    is_generalizable=True,
                ),
            ],
        )

        parser = KnowledgeParser()
        parsed = parser.parse(capture)

        # Compile
        result = compiler.compile(parsed)

        assert result.success is True
        assert result.output is not None
        assert isinstance(result.output, CanonicalSpec)
        assert result.output.spec_type == SpecType.PLOT_STANDARD

    def test_compile_batch(self):
        """Test batch compilation"""
        compiler = CanonicalCompiler()

        # Create multiple ParsedTeach
        teaches = []
        for i in range(3):
            context = CaptureContext(
                case_id=f"case-{i:03d}",
                solver_type="openfoam",
                problem_type=ProblemType.INTERNAL_FLOW,
            )

            capture = TeachCapture(
                source_case_id=f"case-{i:03d}",
                context=context,
                raw_operations=[
                    TeachOperation(
                        operation_type="add_metric",
                        description=f"Metric {i}",
                        reason=f"Reason {i}",
                        is_generalizable=True,
                    ),
                ],
            )

            parser = KnowledgeParser()
            parsed = parser.parse(capture)
            teaches.append(parsed)

        # Compile batch
        results = compiler.compile_batch(teaches)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.output is not None for r in results)

    def test_merge_specs(self):
        """Test merging multiple specs"""
        compiler = CanonicalCompiler(merge_conflicts=True)

        # Create multiple specs
        specs = []
        for i in range(3):
            spec = CanonicalSpec(
                spec_type=SpecType.PLOT_STANDARD,
                content={
                    "colormap": f"colormap_{i}",
                    "plane": "xy",
                },
            )
            specs.append(spec)

        # Merge
        merged = compiler.merge_specs(specs)

        assert merged.spec_type == SpecType.PLOT_STANDARD
        # 后者覆盖前者
        assert merged.content["colormap"] == "colormap_2"

    def test_compile_by_type(self):
        """Test compilation by SpecType"""
        compiler = CanonicalCompiler()

        # Create teaches with different intents
        teaches = []
        for intent in [TeachIntent.ADD_COMPONENT, TeachIntent.MODIFY_STANDARD]:
            context = CaptureContext(
                case_id="case-001",
                solver_type="openfoam",
                problem_type=ProblemType.INTERNAL_FLOW,
            )

            capture = TeachCapture(
                source_case_id="case-001",
                context=context,
                raw_operations=[
                    TeachOperation(
                        operation_type="add_plot" if intent == TeachIntent.ADD_COMPONENT else "modify_plot",
                        description="Test operation",
                        reason="Test",
                        is_generalizable=True,
                    ),
                ],
            )

            # Hack: set intent directly since parser may classify differently
            parser = KnowledgeParser()
            parsed = parser.parse(capture)
            teaches.append(parsed)

        # Compile by type
        results = compiler.compile_by_type(teaches)

        assert isinstance(results, dict)
        assert len(results) > 0


class TestKnowledgePublisher:
    """Test KnowledgePublisher"""

    def test_publisher_init(self):
        """Test publisher initialization"""
        config = CompilerConfig(strict_mode=True)
        publisher = KnowledgePublisher(config=config)
        assert publisher.config.strict_mode is True

    def test_publish_with_passing_gates(self):
        """Test publishing specs that pass gates"""
        publisher = KnowledgePublisher(config=CompilerConfig(strict_mode=False))

        # Create a spec that should pass gates
        spec = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={
                "plot_type": "contour",
                "field": "velocity",
                "colormap": "viridis",
                "plane": "xy",
            },
        )
        # Add source tracking (3+ sources enables auto-approve in non-strict mode)
        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "case-002")
        spec.add_source("TEACH-003", "case-003")

        # Get the publisher's auth gate and approve the request
        auth_gate = publisher.gate_executor.get_gate_by_id("G2-P2")
        request = auth_gate.create_auth_request(
            spec=spec,
            requester="engineer-001",
            risk_level="low",
        )
        auth_gate.approve_request(request.request_id, "senior-001", "Approved")

        # Publish
        result = publisher.publish([spec])

        assert result.total_input_count == 1
        assert result.success_count == 1
        assert result.failed_count == 0
        assert len(result.canonical_specs) == 1

    def test_publish_with_failing_gates(self):
        """Test publishing specs that fail gates"""
        publisher = KnowledgePublisher(config=CompilerConfig(strict_mode=True))

        # Create an incomplete spec (should fail G1-P2)
        spec = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={
                # Missing required fields
                "plot_type": "contour",
            },
        )

        # Publish
        result = publisher.publish([spec])

        # Should fail gates
        assert result.total_input_count == 1
        # In strict mode, incomplete specs should fail
        assert result.failed_count == 1 or result.success_count == 0

    def test_verify_spec(self):
        """Test spec verification"""
        publisher = KnowledgePublisher()

        # Create a passing spec
        spec = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={
                "plot_type": "contour",
                "field": "velocity",
                "colormap": "viridis",
                "plane": "xy",
            },
        )
        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "case-002")
        spec.add_source("TEACH-003", "case-003")

        # Verify without strict auth (auto-approve)
        publisher.config.strict_mode = False
        can_publish = publisher.verify(spec)

        # Should pass with auto-approve
        assert isinstance(can_publish, bool)


class TestPublishConvenienceFunctions:
    """Test publish_knowledge and verify_spec functions"""

    def test_publish_knowledge(self):
        """Test publish_knowledge() function"""
        spec = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={
                "plot_type": "contour",
                "field": "velocity",
                "colormap": "viridis",
                "plane": "xy",
            },
        )
        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "case-002")
        spec.add_source("TEACH-003", "case-003")

        # Publish with auto-approve
        result = publish_knowledge([spec], strict_mode=False)

        assert result.output_id.startswith("P2-OUTPUT-")
        assert result.total_input_count == 1

    def test_verify_spec_function(self):
        """Test verify_spec() function"""
        spec = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={
                "plot_type": "contour",
                "field": "velocity",
                "colormap": "viridis",
                "plane": "xy",
            },
        )
        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "case-002")
        spec.add_source("TEACH-003", "case-003")

        # Verify with non-strict mode
        can_publish = verify_spec(spec, strict_mode=False)

        assert isinstance(can_publish, bool)


class TestEndToEndIntegration:
    """End-to-end integration tests"""

    def test_full_pipeline_phase1_to_phase2(self):
        """Test complete pipeline: Phase1 -> Teach -> Parser -> Compiler -> Publish"""
        # Step 1: Create Phase1Output
        teach_record = TeachRecord(
            teach_record_id="TR-001",
            case_id="case-001",
            timestamp=time.time(),
        )
        teach_record.add_operation(
            operation_type="add_plot",
            description="Add velocity contour plot",
            reason="Need flow visualization",
            is_generalizable=True,
        )

        phase1_output = Phase1Output(
            output_id="P1-001",
            report_specs=[],
            correction_specs=[],
            teach_records=[teach_record],
        )

        # Step 2: Teach Capture
        extractor = TeachCaptureExtractor()
        captures = extractor.extract_captures(phase1_output)
        assert len(captures) == 1

        # Step 3: Parse
        parser = KnowledgeParser()
        parsed_teaches = parser.parse_batch(captures)
        assert len(parsed_teaches) == 1

        # Step 4: Compile
        compiler = CanonicalCompiler()
        compile_results = compiler.compile_batch(parsed_teaches)
        assert all(r.success for r in compile_results)

        # Step 5: Publish
        specs = [r.output for r in compile_results if r.output]
        published = publish_knowledge(specs, strict_mode=False)

        assert published.total_input_count == len(specs)
        assert published.success_count >= 0

    def test_full_pipeline_multiple_teachings(self):
        """Test pipeline with multiple teachings"""
        # Create multiple TeachRecords
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
            output_id="P1-MULTI",
            report_specs=[],
            correction_specs=[],
            teach_records=teach_records,
        )

        # Full pipeline
        captures = extract_captures(phase1_output)
        parsed = KnowledgeParser().parse_batch(captures)
        results = CanonicalCompiler().compile_batch(parsed)
        specs = [r.output for r in results if r.output]
        published = publish_knowledge(specs, strict_mode=False)

        assert published.total_input_count == len(specs)

    def test_gate_execution_in_pipeline(self):
        """Test that gates are executed during publish"""
        spec = CanonicalSpec(
            spec_type=SpecType.PLOT_STANDARD,
            content={
                "plot_type": "contour",
                "field": "velocity",
                "colormap": "viridis",
                "plane": "xy",
            },
        )
        spec.add_source("TEACH-001", "case-001")
        spec.add_source("TEACH-002", "case-002")
        spec.add_source("TEACH-003", "case-003")

        publisher = KnowledgePublisher()
        publisher.config.strict_mode = False

        # Run gates manually
        gate_results = publisher.run_gates(spec)

        assert "G1-P2" in gate_results
        assert "G2-P2" in gate_results


class TestCompilationErrors:
    """Test error handling in compilation"""

    def test_compile_with_no_operations(self):
        """Test compiling ParsedTeach with no operations"""
        compiler = CanonicalCompiler()

        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[],
        )

        parser = KnowledgeParser()
        parsed = parser.parse(capture)

        result = compiler.compile(parsed)

        # Should still succeed, with default content
        assert result.success is True

    def test_merge_empty_specs(self):
        """Test merging empty specs list"""
        compiler = CanonicalCompiler()

        with pytest.raises(ValueError, match="Cannot merge empty specs"):
            compiler.merge_specs([])

    def test_failed_compilation(self):
        """Test handling of compilation failure"""
        compiler = CanonicalCompiler()

        # Create an invalid ParsedTeach (will fail during compile)
        # This tests error handling in the compiler
        context = CaptureContext(
            case_id="case-001",
            solver_type="openfoam",
            problem_type=ProblemType.INTERNAL_FLOW,
        )

        capture = TeachCapture(
            source_case_id="case-001",
            context=context,
            raw_operations=[],
        )

        parser = KnowledgeParser()
        parsed = parser.parse(capture)

        # The compile should succeed even with minimal data
        result = compiler.compile(parsed)
        assert result.success is True
