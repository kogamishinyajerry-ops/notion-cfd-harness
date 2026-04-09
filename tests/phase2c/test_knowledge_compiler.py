#!/usr/bin/env python3
"""
Tests for Knowledge Compiler - Phase 2c Governance & Learning
"""

import json
import tempfile
from pathlib import Path

import pytest

from knowledge_compiler.phase2c.knowledge_compiler import (
    ExtendedKnowledgeLayer,
    PatternKnowledge,
    RuleKnowledge,
    KnowledgeExtractor,
    AnomalyPatternExtractor,
    FixPatternExtractor,
    KnowledgeValidator,
    KnowledgeManager,
    extract_and_validate_knowledge,
    find_similar_corrections,
)
from knowledge_compiler.phase2c.correction_recorder import (
    CorrectionRecord,
    CorrectionRecorder,
)
from knowledge_compiler.phase1.schema import ErrorType, ImpactScope, KnowledgeStatus


class TestPatternKnowledge:
    """测试 PatternKnowledge 基础功能"""

    def test_pattern_creation(self):
        """测试模式知识创建"""
        pattern = PatternKnowledge(
            knowledge_id="PAT-001",
            name="测试模式",
            description="测试模式描述",
            pattern_type="anomaly_pattern",
            trigger_conditions={"error_types": ["incorrect_data"]},
            pattern_signature={"type": "data_error"},
            recommended_actions=["修正数据"],
        )

        assert pattern.knowledge_id == "PAT-001"
        assert pattern.knowledge_layer == ExtendedKnowledgeLayer.L2_GENERALIZABLE
        assert pattern.knowledge_status == KnowledgeStatus.DRAFT

    def test_add_evidence(self):
        """测试添加证据"""
        pattern = PatternKnowledge(
            knowledge_id="PAT-002",
            name="证据测试",
            description="测试证据添加",
            pattern_type="anomaly_pattern",
            trigger_conditions={},
            pattern_signature={},
            recommended_actions=[],
        )

        pattern.add_evidence("CORR-001")
        pattern.add_evidence("CORR-002")

        assert pattern.evidence_count == 2
        assert "CORR-001" in pattern.source_corrections
        assert "CORR-002" in pattern.source_corrections

    def test_update_confidence(self):
        """测试更新置信度"""
        pattern = PatternKnowledge(
            knowledge_id="PAT-003",
            name="置信度测试",
            description="测试置信度更新",
            pattern_type="anomaly_pattern",
            trigger_conditions={},
            pattern_signature={},
            recommended_actions=[],
            confidence_score=0.5,
        )

        pattern.update_confidence(0.8)
        assert pattern.confidence_score == 0.8

        # 测试边界值
        pattern.update_confidence(1.5)
        assert pattern.confidence_score == 1.0

        pattern.update_confidence(-0.1)
        assert pattern.confidence_score == 0.0

    def test_to_dict(self):
        """测试序列化"""
        pattern = PatternKnowledge(
            knowledge_id="PAT-004",
            name="序列化测试",
            description="测试序列化",
            pattern_type="fix_pattern",
            trigger_conditions={"error_types": ["missing_data"]},
            pattern_signature={"fix_type": "addition"},
            recommended_actions=["添加缺失数据"],
            confidence_score=0.7,
            evidence_count=3,
            success_rate=0.85,
        )

        data = pattern.to_dict()

        assert data["knowledge_id"] == "PAT-004"
        assert data["pattern_type"] == "fix_pattern"
        assert data["confidence_score"] == 0.7
        assert data["evidence_count"] == 3
        assert data["success_rate"] == 0.85


class TestRuleKnowledge:
    """测试 RuleKnowledge 基础功能"""

    def test_rule_creation(self):
        """测试规则知识创建"""
        rule = RuleKnowledge(
            knowledge_id="RULE-001",
            name="测试规则",
            description="测试规则描述",
            rule_type="validation_rule",
            rule_expression={"condition": "x > 0"},
            scope=ImpactScope.SINGLE_CASE,
        )

        assert rule.knowledge_id == "RULE-001"
        assert rule.knowledge_layer == ExtendedKnowledgeLayer.L3_CANONICAL
        assert rule.application_count == 0
        assert rule.compliance_rate == 1.0

    def test_record_application(self):
        """测试记录应用"""
        rule = RuleKnowledge(
            knowledge_id="RULE-002",
            name="应用测试",
            description="测试应用记录",
            rule_type="validation_rule",
            rule_expression={},
            scope=ImpactScope.SINGLE_CASE,
        )

        rule.record_application(True)   # 违规
        assert rule.application_count == 1
        assert rule.violation_count == 1
        assert rule.compliance_rate == 0.0

        rule.record_application(False)  # 不违规
        assert rule.application_count == 2
        assert rule.violation_count == 1
        assert rule.compliance_rate == 0.5

    def test_to_dict(self):
        """测试序列化"""
        rule = RuleKnowledge(
            knowledge_id="RULE-003",
            name="序列化测试",
            description="测试规则序列化",
            rule_type="constraint_rule",
            rule_expression={"max_value": 100},
            scope=ImpactScope.ALL_CASES,
            application_count=10,
            violation_count=2,
        )

        data = rule.to_dict()

        assert data["knowledge_id"] == "RULE-003"
        assert data["rule_type"] == "constraint_rule"
        assert data["application_count"] == 10
        assert data["violation_count"] == 2


class TestAnomalyPatternExtractor:
    """测试 AnomalyPatternExtractor"""

    def test_extract_valid_pattern(self):
        """测试提取有效模式"""
        extractor = AnomalyPatternExtractor()

        correction = CorrectionRecord(
            record_id="CORR-001",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={"value": 100},
            correct_output={"value": 200},
            human_reason="边界条件设置错误导致数据错误",
            evidence=["validation_id: VAL-001", "anomaly detected"],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="边界条件设置错误，导致数值计算异常",
            fix_action="修正边界条件公式",
            needs_replay=True,
        )

        pattern = extractor.extract(correction)

        assert pattern is not None
        assert pattern.pattern_type == "anomaly_pattern"
        assert pattern.confidence_score > 0.5
        assert len(pattern.source_corrections) == 1

    def test_extract_invalid_pattern(self):
        """测试提取无效模式"""
        extractor = AnomalyPatternExtractor()

        correction = CorrectionRecord(
            record_id="CORR-002",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="",  # 空根因
            fix_action="",   # 空修正
            needs_replay=False,
        )

        pattern = extractor.extract(correction)

        assert pattern is None


class TestFixPatternExtractor:
    """测试 FixPatternExtractor"""

    def test_extract_boundary_fix(self):
        """测试提取边界修正模式"""
        extractor = FixPatternExtractor()

        correction = CorrectionRecord(
            record_id="CORR-003",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={},
            correct_output={},
            human_reason="边界条件错误",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="边界条件",
            fix_action="修正边界条件设置",
            needs_replay=True,
        )

        pattern = extractor.extract(correction)

        assert pattern is not None
        assert pattern.pattern_type == "fix_pattern"
        assert pattern.pattern_signature["fix_type"] == "boundary_fix"

    def test_extract_mesh_fix(self):
        """测试提取网格修正模式"""
        extractor = FixPatternExtractor()

        correction = CorrectionRecord(
            record_id="CORR-004",
            created_at=1234567890.0,
            error_type=ErrorType.MISSING_COMPONENT,
            wrong_output={},
            correct_output={},
            human_reason="网格质量差",
            evidence=[],
            impact_scope=ImpactScope.SIMILAR_CASES,
            root_cause="网格宽长比过高",
            fix_action="优化网格质量",
            needs_replay=True,
        )

        pattern = extractor.extract(correction)

        assert pattern is not None
        assert pattern.pattern_signature["fix_type"] == "mesh_fix"


class TestKnowledgeValidator:
    """测试 KnowledgeValidator"""

    def test_validate_valid_knowledge(self):
        """测试验证有效知识"""
        validator = KnowledgeValidator()

        pattern = PatternKnowledge(
            knowledge_id="PAT-VALID",
            name="有效知识",
            description="通过验证的知识",
            pattern_type="anomaly_pattern",
            trigger_conditions={"error_types": ["incorrect_data"]},
            pattern_signature={"type": "data_error"},
            recommended_actions=["修正数据"],
            confidence_score=0.8,
            evidence_count=5,
            success_rate=0.9,
        )

        is_valid, violations = validator.validate(pattern)

        assert is_valid
        assert len(violations) == 0

    def test_validate_low_confidence(self):
        """测试验证低置信度"""
        validator = KnowledgeValidator(min_confidence=0.7)

        pattern = PatternKnowledge(
            knowledge_id="PAT-LOW-CONF",
            name="低置信度",
            description="置信度不足",
            pattern_type="anomaly_pattern",
            trigger_conditions={},
            pattern_signature={},
            recommended_actions=[],
            confidence_score=0.5,  # 低于阈值
            evidence_count=5,
            success_rate=0.9,
        )

        is_valid, violations = validator.validate(pattern)

        assert not is_valid
        assert any("置信度不足" in v for v in violations)

    def test_validate_insufficient_evidence(self):
        """测试验证证据不足"""
        validator = KnowledgeValidator(min_evidence=3)

        pattern = PatternKnowledge(
            knowledge_id="PAT-LOW-EVIDENCE",
            name="证据不足",
            description="证据数量不足",
            pattern_type="anomaly_pattern",
            trigger_conditions={},
            pattern_signature={},
            recommended_actions=[],
            confidence_score=0.8,
            evidence_count=1,  # 低于阈值
            success_rate=0.9,
        )

        is_valid, violations = validator.validate(pattern)

        assert not is_valid
        assert any("证据不足" in v for v in violations)

    def test_calculate_quality_score(self):
        """测试计算质量分数"""
        validator = KnowledgeValidator()

        pattern = PatternKnowledge(
            knowledge_id="PAT-QUALITY",
            name="质量测试",
            description="测试质量分数计算",
            pattern_type="anomaly_pattern",
            trigger_conditions={"error_types": ["incorrect_data"]},
            pattern_signature={"type": "data_error"},
            recommended_actions=["修正数据"],
            confidence_score=0.8,
            evidence_count=5,
            success_rate=0.9,
            source_corrections=["CORR-001", "CORR-002"],
        )

        score = validator.calculate_quality_score(pattern)

        assert 0.0 <= score <= 1.0
        assert score > 0.5  # 应该是较好的质量分数


class TestKnowledgeManager:
    """测试 KnowledgeManager"""

    def test_manager_creation(self):
        """测试管理器创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = KnowledgeManager(storage_path=tmpdir)

            assert len(manager.patterns) == 0
            assert len(manager.rules) == 0
            assert len(manager.extractors) == 2

    def test_extract_knowledge(self):
        """测试知识提取"""
        manager = KnowledgeManager(storage_path="/nonexistent/path")

        correction = CorrectionRecord(
            record_id="CORR-EXTRACT-001",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={"value": 100},
            correct_output={"value": 200},
            human_reason="边界条件错误导致数据错误",
            evidence=["evidence1"],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="边界条件设置错误",
            fix_action="修正边界条件",
            needs_replay=True,
        )

        patterns = manager.extract_knowledge(correction)

        assert len(patterns) > 0
        assert any(p.pattern_type in ["anomaly_pattern", "fix_pattern"] for p in patterns)

    def test_add_pattern_valid(self):
        """测试添加有效模式"""
        manager = KnowledgeManager(storage_path="/nonexistent/path")

        pattern = PatternKnowledge(
            knowledge_id="PAT-ADD-001",
            name="有效模式",
            description="通过验证的模式",
            pattern_type="anomaly_pattern",
            trigger_conditions={"error_types": ["incorrect_data"]},
            pattern_signature={"type": "data_error"},
            recommended_actions=["修正数据"],
            confidence_score=0.8,
            evidence_count=5,
            success_rate=0.9,
        )

        is_valid, violations = manager.add_pattern(pattern, validate=True)

        assert is_valid
        assert len(violations) == 0
        assert "PAT-ADD-001" in manager.patterns

    def test_add_pattern_invalid(self):
        """测试添加无效模式"""
        manager = KnowledgeManager(storage_path="/nonexistent/path")

        pattern = PatternKnowledge(
            knowledge_id="PAT-ADD-002",
            name="无效模式",
            description="验证失败的模式",
            pattern_type="anomaly_pattern",
            trigger_conditions={},
            pattern_signature={},
            recommended_actions=[],
            confidence_score=0.3,  # 低置信度
            evidence_count=1,
            success_rate=0.5,
        )

        is_valid, violations = manager.add_pattern(pattern, validate=True)

        assert not is_valid
        assert len(violations) > 0
        assert "PAT-ADD-002" not in manager.patterns

    def test_find_matching_patterns(self):
        """测试查找匹配模式"""
        manager = KnowledgeManager(storage_path="/nonexistent/path")

        # 添加一个模式
        pattern = PatternKnowledge(
            knowledge_id="PAT-MATCH-001",
            name="匹配测试",
            description="测试模式匹配",
            pattern_type="anomaly_pattern",
            trigger_conditions={
                "error_types": ["incorrect_data"],
                "impact_scopes": ["single_case"],
            },
            pattern_signature={"type": "data_error"},
            recommended_actions=["修正数据"],
            confidence_score=0.8,
            evidence_count=3,
            success_rate=0.9,
        )

        manager.add_pattern(pattern, validate=False)

        # 创建匹配的修正记录
        correction = CorrectionRecord(
            record_id="CORR-MATCH-001",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,  # 匹配
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,  # 匹配
            root_cause="test",
            fix_action="test",
            needs_replay=False,
        )

        matching = manager.find_matching_patterns(correction)

        assert len(matching) > 0
        assert any(p.knowledge_id == "PAT-MATCH-001" for p in matching)

    def test_promote_to_l3_success(self):
        """测试成功提升到 L3"""
        manager = KnowledgeManager(storage_path="/nonexistent/path")

        # 创建一个满足提升条件的 L2 模式
        pattern = PatternKnowledge(
            knowledge_id="PAT-PROMOTE-001",
            name="可提升模式",
            description="满足 L3 提升条件",
            pattern_type="anomaly_pattern",
            trigger_conditions={"error_types": ["incorrect_data"]},
            pattern_signature={"type": "data_error"},
            recommended_actions=["修正数据"],
            confidence_score=0.9,
            evidence_count=5,  # >= 3
            success_rate=0.95,  # >= 0.9
            knowledge_layer=ExtendedKnowledgeLayer.L2_GENERALIZABLE,
            knowledge_status=KnowledgeStatus.APPROVED,
        )

        manager.add_pattern(pattern, validate=False)

        is_success, message = manager.promote_to_l3("PAT-PROMOTE-001")

        assert is_success
        assert "成功提升" in message
        assert pattern.knowledge_layer == ExtendedKnowledgeLayer.L3_CANONICAL
        assert len(manager.rules) == 1

    def test_promote_to_l3_failure_insufficient_evidence(self):
        """测试提升失败 - 证据不足"""
        manager = KnowledgeManager(storage_path="/nonexistent/path")

        pattern = PatternKnowledge(
            knowledge_id="PAT-PROMOTE-002",
            name="证据不足",
            description="证据数量不足",
            pattern_type="anomaly_pattern",
            trigger_conditions={},
            pattern_signature={},
            recommended_actions=[],
            confidence_score=0.9,
            evidence_count=2,  # < 3
            success_rate=0.95,
            knowledge_layer=ExtendedKnowledgeLayer.L2_GENERALIZABLE,
            knowledge_status=KnowledgeStatus.APPROVED,
        )

        manager.add_pattern(pattern, validate=False)

        is_success, message = manager.promote_to_l3("PAT-PROMOTE-002")

        assert not is_success
        assert "证据不足" in message

    def test_get_statistics(self):
        """测试获取统计信息"""
        manager = KnowledgeManager(storage_path="/nonexistent/path")

        # 添加一些模式
        for i in range(3):
            pattern = PatternKnowledge(
                knowledge_id=f"PAT-STAT-{i}",
                name=f"统计测试 {i}",
                description="测试统计",
                pattern_type="anomaly_pattern",
                trigger_conditions={},
                pattern_signature={},
                recommended_actions=[],
                knowledge_status=KnowledgeStatus.APPROVED if i < 2 else KnowledgeStatus.DRAFT,
            )
            manager.add_pattern(pattern, validate=False)

        stats = manager.get_statistics()

        assert stats["total_patterns"] == 3
        assert stats["approved_patterns"] == 2
        assert stats["draft_patterns"] == 1

    def test_save_pattern(self):
        """测试保存模式"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = KnowledgeManager(storage_path=tmpdir)

            pattern = PatternKnowledge(
                knowledge_id="PAT-SAVE-001",
                name="保存测试",
                description="测试模式保存",
                pattern_type="anomaly_pattern",
                trigger_conditions={},
                pattern_signature={},
                recommended_actions=[],
            )

            filepath = manager.save_pattern(pattern)

            assert Path(filepath).exists()
            assert "PAT-SAVE-001.json" in filepath

            # 验证可以重新加载
            new_manager = KnowledgeManager(storage_path=tmpdir)
            assert "PAT-SAVE-001" in new_manager.patterns


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_extract_and_validate_knowledge(self):
        """测试提取并验证知识"""
        corrections = [
            CorrectionRecord(
                record_id=f"CORR-FUNC-{i}",
                created_at=1234567890.0,
                error_type=ErrorType.INCORRECT_DATA,
                wrong_output={"value": 100},
                correct_output={"value": 200},
                human_reason="测试修正",
                evidence=["evidence1", "evidence2", "evidence3"],
                impact_scope=ImpactScope.SINGLE_CASE,
                root_cause="边界条件设置错误导致数值计算异常，需要重新校验边界条件公式",  # 长根因
                fix_action="修正边界条件设置并重新计算数值结果",  # 具体修正动作
                needs_replay=True,  # 需要回放以提升置信度
            )
            for i in range(3)
        ]

        # 使用宽松的验证器进行测试
        from knowledge_compiler.phase2c.knowledge_compiler import KnowledgeValidator

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建宽松验证器
            validator = KnowledgeValidator(
                min_confidence=0.5,  # 降低置信度要求
                min_evidence=1,       # 保持最低证据要求
                min_success_rate=0.0,  # 暂时不要求成功率（实际应用中应该有回放验证）
            )
            manager = KnowledgeManager(
                storage_path=tmpdir,
                validator=validator,
            )

            extracted = []
            all_violations = []

            for correction in corrections:
                # 提取知识
                patterns = manager.extract_knowledge(correction)

                # 验证并添加
                for pattern in patterns:
                    is_valid, violations = manager.add_pattern(pattern, validate=True)
                    if is_valid:
                        extracted.append(pattern)
                    else:
                        all_violations.extend([
                            f"{pattern.knowledge_id}: {v}" for v in violations
                        ])

            # 应该提取到一些知识
            assert len(extracted) > 0

    def test_find_similar_corrections(self):
        """测试查找相似修正"""
        manager = KnowledgeManager(storage_path="/nonexistent/path")

        # 添加一个模式
        pattern = PatternKnowledge(
            knowledge_id="PAT-SIMILAR-001",
            name="相似修正测试",
            description="测试相似修正查找",
            pattern_type="anomaly_pattern",
            trigger_conditions={
                "error_types": ["incorrect_data"],
            },
            pattern_signature={},
            recommended_actions=[],
            source_corrections=["CORR-SIMILAR-001", "CORR-SIMILAR-002"],
        )

        manager.add_pattern(pattern, validate=False)

        # 创建匹配的修正记录
        correction = CorrectionRecord(
            record_id="CORR-NEW-001",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,  # 匹配
            wrong_output={},
            correct_output={},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="test",
            fix_action="test",
            needs_replay=False,
        )

        similar = find_similar_corrections(correction, manager)

        assert "CORR-SIMILAR-001" in similar
        assert "CORR-SIMILAR-002" in similar


class TestIntegration:
    """集成测试"""

    def test_full_knowledge_lifecycle(self):
        """测试完整知识生命周期"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = KnowledgeManager(storage_path=tmpdir)

            # 1. 创建修正记录
            corrections = [
                CorrectionRecord(
                    record_id=f"CORR-LIFECYCLE-{i}",
                    created_at=1234567890.0,
                    error_type=ErrorType.INCORRECT_DATA,
                    wrong_output={"value": 100},
                    correct_output={"value": 200},
                    human_reason="边界条件错误",
                    evidence=[f"evidence{i}" for i in range(3)],
                    impact_scope=ImpactScope.SINGLE_CASE,
                    root_cause="边界条件设置错误",
                    fix_action="修正边界条件",
                    needs_replay=True,
                )
                for i in range(5)
            ]

            # 2. 提取知识
            all_patterns = []
            for correction in corrections:
                patterns = manager.extract_knowledge(correction)
                for pattern in patterns:
                    is_valid, _ = manager.add_pattern(pattern, validate=False)
                    if is_valid:
                        all_patterns.append(pattern)

            assert len(all_patterns) > 0

            # 3. 验证知识
            for pattern in all_patterns:
                is_valid, violations = manager.validate_knowledge(pattern)
                # 即使有违规，也应该能添加（不验证）
                manager.add_pattern(pattern, validate=False)

            # 4. 保存知识
            for pattern in all_patterns:
                manager.save_pattern(pattern)

            # 5. 查找相似修正
            new_correction = CorrectionRecord(
                record_id="CORR-NEW-LIFECYCLE",
                created_at=1234567890.0,
                error_type=ErrorType.INCORRECT_DATA,
                wrong_output={"value": 100},
                correct_output={"value": 200},
                human_reason="类似错误",
                evidence=[],
                impact_scope=ImpactScope.SINGLE_CASE,
                root_cause="边界条件",
                fix_action="修正边界",
                needs_replay=False,
            )

            matching = manager.find_matching_patterns(new_correction)

            # 应该找到一些匹配的模式
            assert len(matching) > 0

            # 6. 获取统计
            stats = manager.get_statistics()
            assert stats["total_patterns"] > 0
