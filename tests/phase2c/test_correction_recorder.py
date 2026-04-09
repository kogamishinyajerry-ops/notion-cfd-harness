#!/usr/bin/env python3
"""
Tests for Correction Recorder - Phase 2c Governance & Learning
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from knowledge_compiler.phase2c.correction_recorder import (
    CorrectionSeverity,
    CorrectionRecord,
    CorrectionRecorder,
    ImpactScopeAnalyzer,
    ReplayStatus,
    SpecsValidator,
    ConstraintsChecker,
    record_from_failure,
)
from knowledge_compiler.phase1.schema import (
    ErrorType,
    ImpactScope,
)
from knowledge_compiler.phase2.execution_layer.result_validator import (
    Anomaly,
    AnomalyType,
    ValidationStatus,
    ValidationResult,
)
from knowledge_compiler.phase2.execution_layer.failure_handler import (
    FailureAction,
    FailureCategory,
    FailureContext,
    FailureHandlingResult,
)


class TestImpactScopeAnalyzer:
    """测试影响范围分析器"""

    def test_analyze_residual_spike(self):
        """测试残差突增的影响范围"""
        analyzer = ImpactScopeAnalyzer()

        anomaly = Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="medium",
            location="p[10]",
            message="压力残差突然增大"
        )
        context = FailureContext(
            validation_result=ValidationResult()
        )
        context.validation_result.add_anomaly(anomaly)

        scope = analyzer.analyze(anomaly, context)

        assert scope == ImpactScope.SINGLE_CASE

    def test_analyze_nan_detected(self):
        """测试 NaN 检测的影响范围"""
        analyzer = ImpactScopeAnalyzer()

        anomaly = Anomaly(
            anomaly_type=AnomalyType.NaN_DETECTED,
            severity="critical",
            location="U[100]",
            message="检测到 NaN"
        )
        context = FailureContext(
            validation_result=ValidationResult()
        )
        context.validation_result.add_anomaly(anomaly)

        scope = analyzer.analyze(anomaly, context)

        assert scope == ImpactScope.ALL_CASES

    def test_analyze_divergence(self):
        """测试发散的影响范围"""
        analyzer = ImpactScopeAnalyzer()

        anomaly = Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="求解发散"
        )
        context = FailureContext(
            validation_result=ValidationResult()
        )
        context.validation_result.add_anomaly(anomaly)

        scope = analyzer.analyze(anomaly, context)

        assert scope == ImpactScope.SIMILAR_CASES

    def test_analyze_gate_location(self):
        """测试 Gate 位置的影响范围"""
        analyzer = ImpactScopeAnalyzer()

        anomaly = Anomaly(
            anomaly_type=AnomalyType.RESIDUAL_SPIKE,
            severity="medium",
            location="G4-P2 gate",
            message="Gate 检查失败"
        )
        context = FailureContext(
            validation_result=ValidationResult()
        )
        context.validation_result.add_anomaly(anomaly)

        scope = analyzer.analyze(anomaly, context)

        # Gate 位置应触发 gate_definition scope
        assert scope == ImpactScope.GATE_DEFINITION

    def test_analyze_from_generator_output(self):
        """测试从 Generator 输出分析"""
        analyzer = ImpactScopeAnalyzer()

        spec_output = {
            "spec_id": "CORR-1",
            "validation_result": {
                "anomalies": [
                    {"type": "nan_detected", "severity": "critical"}
                ]
            }
        }
        context = FailureContext(
            validation_result=ValidationResult()
        )
        # Add NaN anomaly for context
        context.validation_result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NaN_DETECTED,
            severity="critical",
            message="NaN detected"
        ))

        scope = analyzer.analyze_from_context(spec_output, context)

        assert scope == ImpactScope.ALL_CASES


class TestSpecsValidator:
    """测试 Specs 验证器"""

    def test_validate_with_string_error_type(self):
        """测试字符串 error_type 的验证"""
        specs = [
            {
                "title": "No String Types Constraint",
                "scope_type": "Interface",
                "constraint_type": "Interface",
            }
        ]
        validator = SpecsValidator(specs)

        record = CorrectionRecord(
            record_id="TEST-001",
            created_at=1234567890.0,
            error_type="incorrect_data",  # 字符串而不是枚举
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="test",
            fix_action="test",
            needs_replay=False,
        )

        violations = validator.validate(record)

        assert len(violations) > 0
        assert any("error_type 必须使用 ErrorType 枚举" in v for v in violations)

    def test_validate_gate_modification(self):
        """测试 Gate 修改需要 Opus 审查"""
        specs = [
            {
                "title": "Architecture Spec",
                "scope_type": "Architecture",
            }
        ]
        validator = SpecsValidator(specs)

        record = CorrectionRecord(
            record_id="TEST-002",
            created_at=1234567890.0,
            error_type=ErrorType.MISSING_DATA,
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.GATE_DEFINITION,
            root_cause="Need to modify Gate logic",
            fix_action="Update Gate definition",
            needs_replay=False,
        )

        violations = validator.validate(record)

        assert any("Opus 4.6 审查" in v for v in violations)

    def test_validate_data_fabrication(self):
        """测试数据伪造检测"""
        specs = [
            {
                "title": "Honesty Constraint",
                "scope_type": "Security",
            }
        ]
        validator = SpecsValidator(specs)

        record = CorrectionRecord(
            record_id="TEST-003",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="test",
            fix_action="Fabricate data to make test pass",  # 包含 fabricate
            needs_replay=False,
        )

        violations = validator.validate(record)

        assert any("禁止数据伪造" in v for v in violations)


class TestConstraintsChecker:
    """测试 Constraints 检查器"""

    def test_check_enum_constraint(self):
        """测试枚举约束检查"""
        constraints = [
            {
                "constraint_name": "No String Types",
                "constraint_type": "Interface",
                "severity": "Critical",
                "enabled": True,
                "validation_rule": "All types must use enum classes",
            }
        ]
        checker = ConstraintsChecker(constraints)

        record = CorrectionRecord(
            record_id="TEST-004",
            created_at=1234567890.0,
            error_type="incorrect_data",  # 字符串
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="test",
            fix_action="test",
            needs_replay=False,
        )

        violations = checker.check(record)

        assert len(violations) > 0

    def test_check_disabled_constraint(self):
        """测试禁用的约束不检查"""
        constraints = [
            {
                "constraint_name": "Disabled Constraint",
                "constraint_type": "Interface",
                "severity": "High",
                "enabled": False,  # 禁用
                "validation_rule": "Must use enums",
            }
        ]
        checker = ConstraintsChecker(constraints)

        record = CorrectionRecord(
            record_id="TEST-005",
            created_at=1234567890.0,
            error_type="incorrect_data",  # 字符串应该违规
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="test",
            fix_action="test",
            needs_replay=False,
        )

        violations = checker.check(record)

        # 禁用的约束不应产生违规
        assert len(violations) == 0


class TestCorrectionRecord:
    """测试修正记录"""

    def test_record_creation(self):
        """测试记录创建"""
        record = CorrectionRecord(
            record_id="TEST-006",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={"value": 100},
            correct_output={"value": 200},
            human_reason="计算错误",
            evidence=["log1", "log2"],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="公式错误",
            fix_action="修正公式",
            needs_replay=False,
        )

        assert record.record_id == "TEST-006"
        assert record.error_type == ErrorType.INCORRECT_DATA
        assert record.impact_scope == ImpactScope.SINGLE_CASE

    def test_record_to_dict(self):
        """测试记录序列化"""
        record = CorrectionRecord(
            record_id="TEST-007",
            created_at=1234567890.0,
            error_type=ErrorType.MISSING_COMPONENT,
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.ALL_CASES,
            root_cause="test",
            fix_action="test",
            needs_replay=True,
        )

        data = record.to_dict()

        assert data["record_id"] == "TEST-007"
        assert data["error_type"] == "missing_component"
        assert data["impact_scope"] == "all_cases"
        assert data["needs_replay"] is True


class TestCorrectionRecorder:
    """测试修正记录器"""

    def test_record_from_generator_basic(self):
        """测试从 Generator 生成基本记录"""
        recorder = CorrectionRecorder()

        # 创建模拟的 Generator 输出
        spec_output = {
            "spec_id": "CORR-123",
            "source": "G4-P2_FAILURE",
            "timestamp": 1234567890.0,
            "suggested_actions": ["检查边界条件", "验证网格质量"],
        }

        # 创建 context
        validation_result = ValidationResult()
        validation_result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.DIVERGENCE,
            severity="high",
            message="求解发散"
        ))

        context = FailureContext(
            validation_result=validation_result,
            attempt_count=1,
            metadata={"case_id": "CASE-001"}
        )

        # 生成记录
        record = recorder.record_from_generator(
            spec_output,
            context,
            human_reason="求解器在第2次尝试时发散"
        )

        assert record.record_id.startswith("CREC-")
        assert record.source_case_id == "CASE-001"
        assert record.human_reason == "求解器在第2次尝试时发散"
        assert record.impact_scope == ImpactScope.SIMILAR_CASES
        assert record.fix_action  # 应该生成 fix_action
        assert len(record.evidence) > 0

    def test_record_from_generator_nan(self):
        """测试 NaN 异常的记录生成"""
        recorder = CorrectionRecorder()

        spec_output = {
            "spec_id": "CORR-NAN",
            "suggested_actions": ["检查边界条件"],
        }

        validation_result = ValidationResult()
        validation_result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.NaN_DETECTED,
            severity="critical",
            location="U[100]",
            message="检测到 NaN"
        ))

        context = FailureContext(
            validation_result=validation_result,
            metadata={"case_id": "CASE-NAN"}
        )

        record = recorder.record_from_generator(spec_output, context)

        assert record.error_type == ErrorType.INCORRECT_DATA
        assert record.impact_scope == ImpactScope.ALL_CASES
        assert record.needs_replay is True  # NaN 应该需要回放

    def test_save_and_load_record(self):
        """测试记录的持久化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = CorrectionRecorder(storage_path=tmpdir)

            # 创建并保存记录
            spec_output = {"spec_id": "CORR-456", "suggested_actions": []}
            validation_result = ValidationResult()
            validation_result.add_anomaly(Anomaly(
                anomaly_type=AnomalyType.HIGH_ASPECT_RATIO,
                severity="medium",
                message="网格宽长比过高"
            ))

            context = FailureContext(
                validation_result=validation_result,
                metadata={"case_id": "CASE-GRID"}
            )

            record = recorder.record_from_generator(spec_output, context)
            filepath = recorder.save(record)

            # 验证文件存在
            assert Path(filepath).exists()

            # 加载记录
            loaded = recorder.load(record.record_id)

            assert loaded is not None
            assert loaded.record_id == record.record_id
            assert loaded.error_type == record.error_type
            assert loaded.human_reason == record.human_reason

    def test_list_records(self):
        """测试列出所有记录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = CorrectionRecorder(storage_path=tmpdir)

            # 创建多个记录
            for i in range(3):
                spec_output = {"spec_id": f"CORR-{i}", "suggested_actions": []}
                validation_result = ValidationResult()
                validation_result.add_anomaly(Anomaly(
                    anomaly_type=AnomalyType.RESIDUAL_SPIKE,
                    severity="low",
                    message=f"测试异常 {i}"
                ))

                context = FailureContext(
                    validation_result=validation_result,
                    metadata={"case_id": f"CASE-{i}"}
                )

                record = recorder.record_from_generator(spec_output, context)
                recorder.save(record)

            # 列出记录
            records = recorder.list_records()

            assert len(records) == 3
            # 应该按时间倒序
            assert records[0].created_at >= records[1].created_at


class TestRecordFromFailure:
    """测试便捷函数"""

    def test_record_from_failure_function(self):
        """测试便捷函数"""
        spec_output = {
            "spec_id": "CORR-FUNC",
            "suggested_actions": ["检查网格质量"],
        }

        validation_result = ValidationResult()
        validation_result.add_anomaly(Anomaly(
            anomaly_type=AnomalyType.HIGH_ASPECT_RATIO,
            severity="medium",
            message="网格质量差"
        ))

        context = FailureContext(
            validation_result=validation_result,
            metadata={"case_id": "CASE-FUNC"}
        )

        # 使用便捷函数
        record = record_from_failure(spec_output, context)

        assert record is not None
        assert record.error_type == ErrorType.MISSING_COMPONENT
        assert record.fix_action


class TestReplayStatus:
    """测试回放状态判定"""

    def test_needs_replay_all_cases(self):
        """测试全范围影响需要回放"""
        record = CorrectionRecord(
            record_id="TEST-REPLAY-1",
            created_at=1234567890.0,
            error_type=ErrorType.DUPLICATE_CONTENT,
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.ALL_CASES,
            root_cause="test",
            fix_action="test",
            needs_replay=True,
        )

        assert record.needs_replay is True

    def test_needs_replay_gate_definition(self):
        """测试 Gate 定义修改需要回放"""
        record = CorrectionRecord(
            record_id="TEST-REPLAY-2",
            created_at=1234567890.0,
            error_type=ErrorType.MISSING_COMPONENT,
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.GATE_DEFINITION,
            root_cause="test",
            fix_action="test",
            needs_replay=True,
        )

        assert record.needs_replay is True

    def test_no_replay_single_case(self):
        """测试单案例不需要回放"""
        record = CorrectionRecord(
            record_id="TEST-REPLAY-3",
            created_at=1234567890.0,
            error_type=ErrorType.WRONG_PLOT,
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="test",
            fix_action="test",
            needs_replay=False,
        )

        assert record.needs_replay is False


class TestCorrectionSeverity:
    """测试修正严重程度"""

    def test_severity_enum(self):
        """测试严重程度枚举"""
        assert CorrectionSeverity.CRITICAL.value == "critical"
        assert CorrectionSeverity.HIGH.value == "high"
        assert CorrectionSeverity.MEDIUM.value == "medium"
        assert CorrectionSeverity.LOW.value == "low"


class TestIntegration:
    """集成测试"""

    def test_full_workflow_with_validation(self):
        """测试完整的记录+验证+保存工作流"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 提供模拟的 Specs 和 Constraints
            specs = [
                {
                    "title": "No String Types",
                    "scope_type": "Interface",
                    "constraint_type": "Interface",
                }
            ]
            constraints = [
                {
                    "constraint_name": "No Data Fabrication",
                    "constraint_type": "Security",
                    "severity": "Critical",
                    "enabled": True,
                    "validation_rule": "No data fabrication",
                }
            ]

            recorder = CorrectionRecorder(
                specs=specs,
                constraints=constraints,
                storage_path=tmpdir
            )

            # 生成记录
            spec_output = {
                "spec_id": "CORR-INT",
                "suggested_actions": ["修正边界条件"],
            }

            validation_result = ValidationResult()
            validation_result.add_anomaly(Anomaly(
                anomaly_type=AnomalyType.NEGATIVE_PRESSURE,
                severity="medium",
                message="负压检测"
            ))

            context = FailureContext(
                validation_result=validation_result,
                metadata={"case_id": "CASE-INT"}
            )

            record = recorder.record_from_generator(
                spec_output,
                context,
                human_reason="边界条件设置错误导致负压"
            )

            # 验证
            violations = recorder.validate(record)

            # 应该没有违规（使用正确的枚举）
            assert len(violations) == 0

            # 保存
            filepath = recorder.save(record)

            assert Path(filepath).exists()
            assert "CASE-INT" in filepath or "CORR-INT" in filepath

    def test_validation_with_violations(self):
        """测试有违规情况的验证"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 提供禁用数据伪造约束
            constraints = [
                {
                    "constraint_name": "Allow Fabrication For Testing",
                    "constraint_type": "Security",
                    "severity": "Critical",
                    "enabled": False,  # 禁用！
                    "validation_rule": "No data fabrication",
                }
            ]

            recorder = CorrectionRecorder(
                constraints=constraints,
                storage_path=tmpdir
            )

            # 生成记录
            spec_output = {"spec_id": "CORR-BAD", "suggested_actions": []}

            validation_result = ValidationResult()

            context = FailureContext(
                validation_result=validation_result,
                metadata={"case_id": "CASE-BAD"}
            )

            record = recorder.record_from_generator(
                spec_output,
                context,
                human_reason="测试"
            )

            # 添加违规的 fix_action
            record.fix_action = "Fabricate some data for testing"

            # 验证
            violations = recorder.validate(record)

            # 约束被禁用，所以不会有违规
            # 但 Specs 验证可能有问题
            # 这里我们主要测试约束检查
            assert len(violations) == 0  # 因为约束被禁用了
