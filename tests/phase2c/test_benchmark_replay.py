#!/usr/bin/env python3
"""
Tests for Benchmark Replay Engine - Phase 2c Governance & Learning
"""

import json
import tempfile
from pathlib import Path

import pytest

from knowledge_compiler.phase2c.benchmark_replay import (
    BenchmarkCase,
    BenchmarkReplayResult,
    BenchmarkReplayEngine,
    BenchmarkSuite,
    create_standard_benchmark_suite,
    replay_correction_with_benchmark,
)
from knowledge_compiler.phase2c.correction_recorder import (
    CorrectionRecord,
    CorrectionRecorder,
)
from knowledge_compiler.phase1.schema import ErrorType, ImpactScope


class TestBenchmarkCase:
    """测试 BenchmarkCase 基础功能"""

    def test_case_creation(self):
        """测试案例创建"""
        case = BenchmarkCase(
            case_id="TEST-001",
            name="Test Case",
            description="Test description",
            input_data={"value": 100},
            expected_output={"result": 200},
        )

        assert case.case_id == "TEST-001"
        assert case.name == "Test Case"
        assert case.input_data == {"value": 100}

    def test_validate_input_success(self):
        """测试输入验证成功"""
        case = BenchmarkCase(
            case_id="TEST-002",
            name="Input Validation Test",
            description="Test input validation",
            constraints={
                "required_fields": ["value", "field2"],
                "field_types": {"value": int},
                "value_ranges": {"value": (0, 200)},
            },
        )

        input_data = {"value": 100, "field2": "data"}
        is_valid, errors = case.validate_input(input_data)

        assert is_valid
        assert len(errors) == 0

    def test_validate_input_missing_field(self):
        """测试输入验证 - 缺失必需字段"""
        case = BenchmarkCase(
            case_id="TEST-003",
            name="Missing Field Test",
            description="Test missing required field",
            constraints={"required_fields": ["value", "missing_field"]},
        )

        input_data = {"value": 100}
        is_valid, errors = case.validate_input(input_data)

        assert not is_valid
        assert any("missing_field" in error for error in errors)

    def test_validate_input_wrong_type(self):
        """测试输入验证 - 类型错误"""
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="TEST-004",
            name="Type Error Test",
            constraints={"field_types": {"value": int}},
        )

        input_data = {"value": "not_an_int"}
        is_valid, errors = case.validate_input(input_data)

        assert not is_valid
        assert any("wrong type" in error for error in errors)

    def test_validate_input_out_of_range(self):
        """测试输入验证 - 值超出范围"""
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="TEST-005",
            name="Range Error Test",
            constraints={"value_ranges": {"value": (0, 100)}},
        )

        input_data = {"value": 150}
        is_valid, errors = case.validate_input(input_data)

        assert not is_valid
        assert any("out of range" in error for error in errors)

    def test_validate_output_success(self):
        """测试输出验证成功"""
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="TEST-006",
            name="Output Validation Test",
            expected_output={"result": 200.0, "status": "ok"},
        )

        actual_output = {"result": 200.0, "status": "ok"}
        is_valid, result = case.validate_output(actual_output)

        assert is_valid
        assert result["is_valid"]
        assert len(result["errors"]) == 0

    def test_validate_output_numeric_tolerance(self):
        """测试输出数值容忍度"""
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="TEST-007",
            name="Tolerance Test",
            expected_output={"value": 100.0},
            tolerance={"relative_error": 0.1, "absolute_error": 1e-3},
        )

        # 在容忍范围内
        actual_output = {"value": 105.0}  # 5% 误差
        is_valid, result = case.validate_output(actual_output)

        assert is_valid
        assert result["is_valid"]

    def test_validate_output_numeric_out_of_tolerance(self):
        """测试输出数值超出容忍度"""
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="TEST-008",
            name="Tolerance Fail Test",
            expected_output={"value": 100.0},
            tolerance={"relative_error": 0.05, "absolute_error": 1e-6},
        )

        # 超出容忍范围
        actual_output = {"value": 110.0}  # 10% 误差
        is_valid, result = case.validate_output(actual_output)

        assert not is_valid
        assert not result["is_valid"]
        assert len(result["errors"]) > 0

    def test_validate_output_missing_field(self):
        """测试输出缺失字段"""
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="TEST-009",
            name="Missing Output Field Test",
            expected_output={"result": 200, "extra": "data"},
        )

        actual_output = {"result": 200}
        is_valid, result = case.validate_output(actual_output)

        assert not is_valid
        assert any("Missing output field" in error for error in result["errors"])


class TestBenchmarkSuite:
    """测试 BenchmarkSuite 案例管理"""

    def test_suite_creation(self):
        """测试样板集创建"""
        suite = BenchmarkSuite(storage_path="/nonexistent/path")

        assert suite.cases == {}
        assert isinstance(suite.storage_path, Path)

    def test_add_case(self):
        """测试添加案例"""
        suite = BenchmarkSuite()
        case = BenchmarkCase(
            case_id="SUITE-001",
            name="Suite Test Case",
            description="Test case for suite",
        )

        suite.add_case(case)

        assert "SUITE-001" in suite.cases
        assert suite.get_case("SUITE-001") == case

    def test_get_nonexistent_case(self):
        """测试获取不存在的案例"""
        suite = BenchmarkSuite()

        case = suite.get_case("NONEXISTENT")

        assert case is None

    def test_list_cases_all(self):
        """测试列出所有案例"""
        suite = BenchmarkSuite(storage_path="/nonexistent/path")

        case1 = BenchmarkCase(
            case_id="LIST-001",
            name="Case 1",
            description="First test case",
            category="physics",
            difficulty="easy",
        )
        case2 = BenchmarkCase(
            case_id="LIST-002",
            name="Case 2",
            description="Second test case",
            category="validation",
            difficulty="medium",
        )

        suite.add_case(case1)
        suite.add_case(case2)

        cases = suite.list_cases()

        assert len(cases) == 2
        assert case1 in cases
        assert case2 in cases

    def test_list_cases_by_category(self):
        """测试按类别列出案例"""
        suite = BenchmarkSuite(storage_path="/nonexistent/path")

        case1 = BenchmarkCase(
            case_id="CAT-001",
            name="Physics Case",
            description="Physics test case",
            category="physics",
        )
        case2 = BenchmarkCase(
            case_id="CAT-002",
            name="Validation Case",
            description="Validation test case",
            category="validation",
        )

        suite.add_case(case1)
        suite.add_case(case2)

        physics_cases = suite.list_cases(category="physics")

        assert len(physics_cases) == 1
        assert physics_cases[0].case_id == "CAT-001"

    def test_list_cases_by_difficulty(self):
        """测试按难度列出案例"""
        suite = BenchmarkSuite(storage_path="/nonexistent/path")

        case1 = BenchmarkCase(
            case_id="DIFF-001",
            name="Easy Case",
            description="Easy test case",
            difficulty="easy",
        )
        case2 = BenchmarkCase(
            case_id="DIFF-002",
            name="Hard Case",
            description="Hard test case",
            difficulty="hard",
        )

        suite.add_case(case1)
        suite.add_case(case2)

        easy_cases = suite.list_cases(difficulty="easy")

        assert len(easy_cases) == 1
        assert easy_cases[0].case_id == "DIFF-001"

    def test_list_cases_by_tags(self):
        """测试按标签列出案例"""
        suite = BenchmarkSuite(storage_path="/nonexistent/path")

        case1 = BenchmarkCase(
            case_id="TAG-001",
            name="Tagged Case 1",
            description="First tagged case",
            tags=["cfd", "convergence"],
        )
        case2 = BenchmarkCase(
            case_id="TAG-002",
            name="Tagged Case 2",
            description="Second tagged case",
            tags=["validation"],
        )

        suite.add_case(case1)
        suite.add_case(case2)

        cfd_cases = suite.list_cases(tags=["cfd"])

        assert len(cfd_cases) == 1
        assert cfd_cases[0].case_id == "TAG-001"

    def test_save_case(self):
        """测试保存案例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            suite = BenchmarkSuite(storage_path=tmpdir)

            case = BenchmarkCase(
            case_id="SAVE-001",
            name="Save Test Case",
            description="Test case saving",
                category="test",
            )

            filepath = suite.save_case(case)

            assert Path(filepath).exists()
            assert "SAVE-001.json" in filepath

            # 验证可以重新加载
            new_suite = BenchmarkSuite(storage_path=tmpdir)
            loaded_case = new_suite.get_case("SAVE-001")

            assert loaded_case is not None
            assert loaded_case.case_id == "SAVE-001"
            assert loaded_case.name == "Save Test Case"


class TestBenchmarkReplayEngine:
    """测试 BenchmarkReplayEngine 回放引擎"""

    def test_engine_creation(self):
        """测试引擎创建"""
        suite = BenchmarkSuite()
        engine = BenchmarkReplayEngine(benchmark_suite=suite)

        assert engine.benchmark_suite == suite
        assert engine.max_execution_time == 300.0
        assert engine.replay_counter == 0

    def test_replay_correction_missing_case(self):
        """测试回放不存在的案例"""
        suite = BenchmarkSuite()
        engine = BenchmarkReplayEngine(benchmark_suite=suite)

        correction = CorrectionRecord(
            record_id="TEST-001",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={"value": 100},
            correct_output={"result": 200},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="test",
            fix_action="test",
            needs_replay=True,
        )

        result = engine.replay_correction(
            correction,
            "NONEXISTENT_CASE",
            simulate_execution=True,
        )

        assert result.status == "error"
        assert "not found" in result.error_message.lower()

    def test_replay_correction_invalid_input(self):
        """测试回放输入验证失败"""
        suite = BenchmarkSuite()
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="VALIDATE-001",
            name="Input Validation Case",
            constraints={"required_fields": ["required_field"]},
        )
        suite.add_case(case)

        engine = BenchmarkReplayEngine(benchmark_suite=suite)

        correction = CorrectionRecord(
            record_id="TEST-002",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={"wrong_field": "data"},  # 缺少 required_field
            correct_output={"result": 200},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="test",
            fix_action="test",
            needs_replay=True,
        )

        result = engine.replay_correction(
            correction,
            "VALIDATE-001",
            simulate_execution=True,
        )

        assert result.status == "failed"
        assert not result.input_valid
        assert len(result.validation_errors) > 0

    def test_replay_correction_success(self):
        """测试回放成功"""
        suite = BenchmarkSuite()
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="SUCCESS-001",
            name="Success Case",
            input_data={"value": 100},
            expected_output={"result": 200},
            constraints={"required_fields": ["value"]},
        )
        suite.add_case(case)

        engine = BenchmarkReplayEngine(benchmark_suite=suite)

        correction = CorrectionRecord(
            record_id="TEST-003",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={"value": 100},
            correct_output={"result": 200},
            human_reason="数据修正",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="公式错误",
            fix_action="修正数据公式",
            needs_replay=True,
        )

        result = engine.replay_correction(
            correction,
            "SUCCESS-001",
            simulate_execution=True,
        )

        assert result.status == "passed"
        assert result.is_successful
        assert result.input_valid
        assert result.output_valid
        assert result.execution_time > 0

    def test_replay_corrections_batch(self):
        """测试批量回放"""
        suite = BenchmarkSuite()
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="BATCH-001",
            name="Batch Test Case",
            input_data={"value": 100},
            expected_output={"result": 200},
            constraints={"required_fields": ["value"]},
        )
        suite.add_case(case)

        engine = BenchmarkReplayEngine(benchmark_suite=suite)

        corrections = [
            CorrectionRecord(
                record_id=f"BATCH-{i:03d}",
                created_at=1234567890.0,
                error_type=ErrorType.INCORRECT_DATA,
                wrong_output={"value": 100},
                correct_output={"result": 200},
                human_reason="test",
                evidence=[],
                impact_scope=ImpactScope.SINGLE_CASE,
                root_cause="test",
                fix_action="test",
                needs_replay=True,
            )
            for i in range(3)
        ]

        # 添加一个不需要回放的修正
        corrections.append(
            CorrectionRecord(
                record_id="BATCH-NO-REPLAY",
                created_at=1234567890.0,
                error_type=ErrorType.INCORRECT_DATA,
                wrong_output={"value": 100},
                correct_output={"result": 200},
                human_reason="test",
                evidence=[],
                impact_scope=ImpactScope.SINGLE_CASE,
                root_cause="test",
                fix_action="test",
                needs_replay=False,  # 不需要回放
            )
        )

        results = engine.replay_corrections_batch(
            corrections,
            "BATCH-001",
            simulate_execution=True,
        )

        # 应该只回放 needs_replay=True 的修正
        assert len(results) == 3
        assert all(r.status == "passed" for r in results)

    def test_generate_replay_report(self):
        """测试生成回放报告"""
        suite = BenchmarkSuite()
        case = BenchmarkCase(description="Auto-generated test case",
            case_id="REPORT-001",
            name="Report Test Case",
            input_data={"value": 100},
            expected_output={"result": 200},
        )
        suite.add_case(case)

        engine = BenchmarkReplayEngine(benchmark_suite=suite)

        corrections = [
            CorrectionRecord(
                record_id=f"REPORT-{i:03d}",
                created_at=1234567890.0,
                error_type=ErrorType.INCORRECT_DATA,
                wrong_output={"value": 100},
                correct_output={"result": 200},
                human_reason="test",
                evidence=[],
                impact_scope=ImpactScope.SINGLE_CASE,
                root_cause="test",
                fix_action="test",
                needs_replay=True,
            )
            for i in range(5)
        ]

        results = engine.replay_corrections_batch(
            corrections,
            "REPORT-001",
            simulate_execution=True,
        )

        report = engine.generate_replay_report(results)

        assert report["summary"]["total"] == 5
        assert report["summary"]["passed"] == 5
        assert report["summary"]["failed"] == 0
        assert report["summary"]["success_rate"] == 1.0
        assert "performance" in report
        assert "case_statistics" in report


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_create_standard_benchmark_suite(self):
        """测试创建标准样板集"""
        with tempfile.TemporaryDirectory() as tmpdir:
            suite = create_standard_benchmark_suite(storage_path=tmpdir)

            assert len(suite.cases) >= 3
            assert "BENCH-001" in suite.cases
            assert "BENCH-002" in suite.cases
            assert "BENCH-003" in suite.cases

            # 验证文件已创建
            assert (Path(tmpdir) / "validation" / "BENCH-001.json").exists()
            assert (Path(tmpdir) / "physics" / "BENCH-002.json").exists()

    def test_replay_correction_with_benchmark(self):
        """测试便捷回放函数"""
        correction = CorrectionRecord(
            record_id="CONV-001",
            created_at=1234567890.0,
            error_type=ErrorType.INCORRECT_DATA,
            wrong_output={"value": 100.0},
            correct_output={"result": 200.0},
            human_reason="test",
            evidence=[],
            impact_scope=ImpactScope.SINGLE_CASE,
            root_cause="test",
            fix_action="test",
            needs_replay=True,
        )

        result = replay_correction_with_benchmark(
            correction,
            benchmark_case_id="BENCH-001",
        )

        assert result.status == "passed"
        assert result.is_successful


class TestIntegration:
    """集成测试"""

    def test_full_replay_workflow(self):
        """测试完整回放工作流"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建样板集
            suite = create_standard_benchmark_suite(storage_path=tmpdir)

            # 创建符合 BENCH-001 要求的修正记录
            correction = CorrectionRecord(
                record_id="WORKFLOW-001",
                created_at=1234567890.0,
                error_type=ErrorType.INCORRECT_DATA,
                wrong_output={"value": 100.0},  # 符合 BENCH-001 的 required_fields
                correct_output={"result": 200.0},
                human_reason="数值计算错误",
                evidence=["test evidence"],
                impact_scope=ImpactScope.SINGLE_CASE,
                root_cause="公式错误",
                fix_action="修正数值公式",
                needs_replay=True,
            )

            # 回放修正
            engine = BenchmarkReplayEngine(benchmark_suite=suite)
            result = engine.replay_correction(
                correction,
                "BENCH-001",
                simulate_execution=True,
            )

            # 验证结果
            assert result.status == "passed"
            assert result.is_successful

    def test_save_and_load_replay_results(self):
        """测试保存和加载回放结果"""
        with tempfile.TemporaryDirectory() as tmpdir:
            suite = create_standard_benchmark_suite(storage_path=tmpdir)
            engine = BenchmarkReplayEngine(benchmark_suite=suite)

            corrections = [
                CorrectionRecord(
                    record_id=f"SAVE-{i:03d}",
                    created_at=1234567890.0,
                    error_type=ErrorType.INCORRECT_DATA,
                    wrong_output={"value": 100},
                    correct_output={"result": 200},
                    human_reason="test",
                    evidence=[],
                    impact_scope=ImpactScope.SINGLE_CASE,
                    root_cause="test",
                    fix_action="test",
                    needs_replay=True,
                )
                for i in range(2)
            ]

            results = engine.replay_corrections_batch(
                corrections,
                "BENCH-001",
                simulate_execution=True,
            )

            # 保存结果
            output_path = Path(tmpdir) / "replay_results.json"
            engine.save_replay_results(results, str(output_path))

            # 验证文件存在
            assert output_path.exists()

            # 加载并验证
            with open(output_path) as f:
                data = json.load(f)

            assert "replay_results" in data
            assert "report" in data
            assert len(data["replay_results"]) == 2
            assert data["report"]["summary"]["total"] == 2


class TestBenchmarkReplayResult:
    """测试 BenchmarkReplayResult 数据结构"""

    def test_result_creation(self):
        """测试结果创建"""
        result = BenchmarkReplayResult(
            replay_id="REPLAY-001",
            case_id="CASE-001",
            correction_record_id="CORR-001",
        )

        assert result.replay_id == "REPLAY-001"
        assert result.status == "pending"
        assert result.input_valid is True
        assert result.output_valid is False

    def test_result_to_dict(self):
        """测试结果序列化"""
        result = BenchmarkReplayResult(
            replay_id="REPLAY-002",
            case_id="CASE-002",
            correction_record_id="CORR-002",
            status="passed",
            input_valid=True,
            output_valid=True,
            execution_time=1.5,
        )

        data = result.to_dict()

        assert data["replay_id"] == "REPLAY-002"
        assert data["status"] == "passed"
        assert data["input_valid"] is True
        assert data["output_valid"] is True
        assert data["execution_time"] == 1.5

    def test_is_successful_property(self):
        """测试 is_successful 属性"""
        result = BenchmarkReplayResult(
            replay_id="REPLAY-003",
            case_id="CASE-003",
            correction_record_id="CORR-003",
            status="passed",
            output_valid=True,
        )

        assert result.is_successful is True

        # 失败情况
        result.status = "failed"
        assert result.is_successful is False

        result.status = "passed"
        result.output_valid = False
        assert result.is_successful is False
