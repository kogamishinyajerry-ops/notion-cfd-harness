#!/usr/bin/env python3
"""
Tests for Phase 2 Postprocess Runner and Adapter
"""

import tempfile
from pathlib import Path

import pytest

from knowledge_compiler.phase2.execution_layer.postprocess_runner import (
    FieldType,
    FieldData,
    ResidualSummary,
    DerivedQuantity,
    StandardPostprocessResult,
    PostprocessStatus,
    FieldDataExtractor,
    ResidualParser,
    DerivedQuantityCalculator,
    PostprocessRunner,
    run_postprocess,
    extract_field_data,
)
from knowledge_compiler.phase2.execution_layer.postprocess_adapter import (
    VisualizationType,
    PlotData,
    ComparisonData,
    NLPostprocessInput,
    PostprocessAdapter,
    TemplatePostprocessAdapter,
    VisualizationTemplate,
    TemplateRegistry,
    adapt_for_nl_postprocess,
    apply_template,
)


# ============================================================================
# Test PostprocessRunner
# ============================================================================

class TestFieldDataExtractor:
    """测试场数据提取器"""

    def test_extract_from_nonexistent_dir(self):
        """测试从不存在的目录提取"""
        extractor = FieldDataExtractor()
        fields = extractor.extract_from_openfoam("/nonexistent/path")
        assert fields == []

    def test_extract_from_empty_dir(self):
        """测试从空目录提取"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = FieldDataExtractor()
            fields = extractor.extract_from_openfoam(tmpdir)
            assert fields == []


class TestResidualParser:
    """测试残差解析器"""

    def test_parse_empty_log(self):
        """测试解析空日志"""
        parser = ResidualParser()
        summary = parser.parse_from_log("")
        assert summary.converged is False
        assert summary.variables == {}

    def test_parse_converged_log(self):
        """测试解析收敛日志"""
        parser = ResidualParser()
        log = """
solving for p, initial residual = 0.001
solving for p, Final residual = 1.23e-05, No Iterations 45
solving for U, Final residual = 3.45e-05, No Iterations 52
solution converges
End
"""
        summary = parser.parse_from_log(log)
        assert summary.converged is True
        assert summary.variables["p"] == 1.23e-05
        assert summary.variables["U"] == 3.45e-05
        assert summary.iterations["p"] == 45
        assert summary.iterations["U"] == 52

    def test_parse_diverged_log(self):
        """测试解析发散日志"""
        parser = ResidualParser()
        log = """
solving for p, initial residual = 0.001
solving for p, Final residual = 1.5, No Iterations 1000
Maximum iterations reached
End
"""
        summary = parser.parse_from_log(log)
        assert summary.converged is False


class TestDerivedQuantityCalculator:
    """测试衍生量计算器"""

    def test_compute_pressure_drop(self):
        """测试压降计算"""
        calculator = DerivedQuantityCalculator()
        dp = calculator.compute_pressure_drop(
            [],
            inlet_location="inlet",
            outlet_location="outlet",
        )
        assert dp is not None
        assert dp.name == "pressure_drop"

    def test_compute_velocity_magnitude_vector(self):
        """测试速度幅值计算"""
        calculator = DerivedQuantityCalculator()

        vector_field = FieldData(
            name="U",
            field_type=FieldType.VECTOR,
            dimensions=3,
        )

        magnitude = calculator.compute_velocity_magnitude(vector_field)
        assert magnitude is not None
        assert magnitude.name == "velocity_magnitude"

    def test_compute_velocity_magnitude_scalar(self):
        """测试标量场的速度幅值计算"""
        calculator = DerivedQuantityCalculator()

        scalar_field = FieldData(
            name="p",
            field_type=FieldType.SCALAR,
            dimensions=1,
        )

        magnitude = calculator.compute_velocity_magnitude(scalar_field)
        assert magnitude is None  # 标量场无法计算幅值

    def test_compute_reynolds_number(self):
        """测试雷诺数计算"""
        calculator = DerivedQuantityCalculator()
        re = calculator.compute_reynolds_number(
            velocity=10.0,
            length=1.0,
            kinematic_viscosity=1.5e-5,
        )
        assert re.name == "reynolds_number"
        assert re.value > 0


class TestPostprocessRunner:
    """测试后处理运行器"""

    def test_runner_init(self):
        """测试初始化"""
        runner = PostprocessRunner()
        assert runner.extractor is not None
        assert runner.residual_parser is not None
        assert runner.calculator is not None

    def test_run_empty_case(self):
        """测试处理空算例"""
        runner = PostprocessRunner()
        result = runner.run(
            case_dir="/nonexistent",
            solver_output="",
        )
        assert result.status in [PostprocessStatus.COMPLETED, PostprocessStatus.FAILED]
        assert result.result_id != ""

    def test_run_with_converged_solver_output(self):
        """测试处理收敛的求解器输出"""
        runner = PostprocessRunner()

        log = """
solving for p, initial residual = 0.001
solving for p, Final residual = 1.23e-05, No Iterations 45
solution converges
End
"""

        result = runner.run(
            case_dir="/nonexistent",
            solver_output=log,
            options={"compute_derivatives": False},
        )

        assert result.status == PostprocessStatus.COMPLETED
        assert result.residuals is not None
        assert result.residuals.converged is True


# ============================================================================
# Test PostprocessAdapter
# ============================================================================

class TestPostprocessAdapter:
    """测试后处理适配器"""

    def test_convert_success_result(self):
        """测试转换成功结果"""
        adapter = PostprocessAdapter()

        standard_result = StandardPostprocessResult(
            result_id="TEST-123",
            status=PostprocessStatus.COMPLETED,
        )

        standard_result.residuals = ResidualSummary(
            converged=True,
            convergence_reason="Solution converges",
        )

        nl_input = adapter.convert(standard_result)

        assert nl_input.source_result_id == "TEST-123"
        assert "✓ 收敛" in nl_input.convergence_summary

    def test_convert_with_residuals(self):
        """测试转换带残差的结果"""
        adapter = PostprocessAdapter()

        standard_result = StandardPostprocessResult()
        standard_result.residuals = ResidualSummary(
            converged=True,
            variables={"p": 1.23e-05, "U": 3.45e-05},
            initial={"p": 0.001, "U": 0.002},
            iterations={"p": 45, "U": 52},
        )

        nl_input = adapter.convert(standard_result)

        assert "p:" in nl_input.residual_summary
        assert "U:" in nl_input.residual_summary

    def test_convert_with_fields(self):
        """测试转换带场数据的结果"""
        adapter = PostprocessAdapter()

        standard_result = StandardPostprocessResult()
        standard_result.fields = [
            FieldData(name="p", field_type=FieldType.SCALAR, dimensions=1),
            FieldData(name="U", field_type=FieldType.VECTOR, dimensions=3),
        ]

        nl_input = adapter.convert(standard_result)

        assert "p" in nl_input.field_summary
        assert "U" in nl_input.field_summary
        assert "scalar" in nl_input.field_summary["p"]
        assert "vector" in nl_input.field_summary["U"]

    def test_generate_plots(self):
        """测试生成绘图数据"""
        adapter = PostprocessAdapter()

        standard_result = StandardPostprocessResult()
        standard_result.residuals = ResidualSummary(
            variables={"p": 1.23e-05},
            initial={"p": 0.001},
        )

        nl_input = adapter.convert(
            standard_result,
            viz_options={"generate_plots": True},
        )

        assert "residuals" in nl_input.plot_data

    def test_generate_comparisons(self):
        """测试生成对比数据"""
        adapter = PostprocessAdapter()

        standard_result = StandardPostprocessResult()
        standard_result.fields = [
            FieldData(
                name="p",
                field_type=FieldType.SCALAR,
                dimensions=1,
                min_value=100000.0,
                max_value=101000.0,
            )
        ]

        nl_input = adapter.convert(
            standard_result,
            viz_options={"generate_comparison": True},
        )

        assert len(nl_input.comparison_data) > 0
        # 应该有 min/max 对比
        assert any(c.location_a == "min" for c in nl_input.comparison_data)


class TestNLPostprocessInput:
    """测试 NL Postprocess 输入格式"""

    def test_creation(self):
        """测试创建"""
        nl_input = NLPostprocessInput()
        assert nl_input.input_id != ""
        assert nl_input.created_at > 0

    def test_to_dict(self):
        """测试转换为字典"""
        nl_input = NLPostprocessInput(
            convergence_summary="✓ 收敛",
            field_summary={"p": "scalar"},
        )

        d = nl_input.to_dict()

        assert d["convergence_summary"] == "✓ 收敛"
        assert d["field_summary"]["p"] == "scalar"
        assert "plot_data" in d
        assert "metadata" in d


class TestVisualizationTemplate:
    """测试可视化模板"""

    def test_template_can_apply(self):
        """测试模板适用性检查"""
        template = VisualizationTemplate(
            template_id="test_template",
            name="Test Template",
            viz_type=VisualizationType.LINE_PLOT,
            required_fields=["p", "U"],
        )

        result_with_fields = StandardPostprocessResult()
        result_with_fields.fields = [
            FieldData(name="p", field_type=FieldType.SCALAR, dimensions=1),
            FieldData(name="U", field_type=FieldType.VECTOR, dimensions=3),
        ]

        result_without_fields = StandardPostprocessResult()
        result_without_fields.fields = [
            FieldData(name="p", field_type=FieldType.SCALAR, dimensions=1),
        ]

        assert template.can_apply(result_with_fields) is True
        assert template.can_apply(result_without_fields) is False


class TestTemplateRegistry:
    """测试模板注册表"""

    def test_get_applicable_templates(self):
        """测试获取适用模板"""
        registry = TemplateRegistry()

        result = StandardPostprocessResult()
        result.fields = [
            FieldData(name="p", field_type=FieldType.SCALAR, dimensions=1),
        ]

        templates = registry.get_applicable_templates(result)

        # 应该至少有压力云图和进出口压力对比模板
        assert len(templates) > 0
        assert any(t.template_id == "pressure_contour" for t in templates)

    def test_get_template_by_id(self):
        """测试根据 ID 获取模板"""
        registry = TemplateRegistry()

        template = registry.get_template("pressure_contour")
        assert template is not None
        assert template.name == "压力云图"

        template = registry.get_template("nonexistent")
        assert template is None


class TestTemplatePostprocessAdapter:
    """测试带模板的适配器"""

    def test_convert_with_template(self):
        """测试使用模板转换"""
        adapter = TemplatePostprocessAdapter()

        result = StandardPostprocessResult()
        result.fields = [
            FieldData(name="p", field_type=FieldType.SCALAR, dimensions=1),
        ]

        nl_input = adapter.convert_with_template(
            result,
            template_id="pressure_contour",
            template_params={"plane": "midplane"},
        )

        assert nl_input.metadata["template"]["id"] == "pressure_contour"
        assert nl_input.metadata["template"]["params"]["plane"] == "midplane"

    def test_list_available_templates(self):
        """测试列出可用模板"""
        adapter = TemplatePostprocessAdapter()

        result = StandardPostprocessResult()
        result.fields = [
            FieldData(name="p", field_type=FieldType.SCALAR, dimensions=1),
            FieldData(name="U", field_type=FieldType.VECTOR, dimensions=3),
        ]

        templates = adapter.list_available_templates(result)

        assert len(templates) > 0
        assert all("id" in t for t in templates)
        assert all("name" in t for t in templates)


# ============================================================================
# Test Convenience Functions
# ============================================================================

class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_run_postprocess(self):
        """测试 run_postprocess"""
        result = run_postprocess(
            case_dir="/nonexistent",
            solver_output="test log",
        )
        assert isinstance(result, StandardPostprocessResult)

    def test_extract_field_data(self):
        """测试 extract_field_data"""
        fields = extract_field_data("/nonexistent")
        assert isinstance(fields, list)

    def test_adapt_for_nl_postprocess(self):
        """测试 adapt_for_nl_postprocess"""
        standard_result = StandardPostprocessResult()
        nl_input = adapt_for_nl_postprocess(standard_result)
        assert isinstance(nl_input, NLPostprocessInput)

    def test_apply_template(self):
        """测试 apply_template"""
        result = StandardPostprocessResult()
        result.fields = [
            FieldData(name="p", field_type=FieldType.SCALAR, dimensions=1),
        ]

        nl_input = apply_template(result, "pressure_contour")

        assert isinstance(nl_input, NLPostprocessInput)
        assert nl_input.metadata["template"]["id"] == "pressure_contour"


# ============================================================================
# Test Data Flow (End-to-End)
# ============================================================================

class TestDataFlow:
    """测试完整数据流"""

    def test_d_to_b_layer_flow(self):
        """测试 D 层到 B 层的数据流"""
        # D Layer: Postprocess Runner
        runner = PostprocessRunner()
        standard_result = runner.run(
            case_dir="/nonexistent",
            solver_output="solution converges\n",
            options={"compute_derivatives": False},
        )

        # Adapter Layer
        adapter = PostprocessAdapter()
        nl_input = adapter.convert(standard_result)

        # Verify: B layer can consume the input
        assert nl_input.source_result_id == standard_result.result_id
        assert isinstance(nl_input, NLPostprocessInput)

    def test_template_based_flow(self):
        """测试基于模板的数据流"""
        # D Layer
        runner = PostprocessRunner()
        standard_result = StandardPostprocessResult()
        standard_result.fields = [
            FieldData(name="p", field_type=FieldType.SCALAR, dimensions=1),
        ]

        # Adapter with Template
        adapter = TemplatePostprocessAdapter()
        nl_input = adapter.convert_with_template(
            standard_result,
            "pressure_contour",
        )

        # Verify: Template info is included
        assert "template" in nl_input.metadata
        assert nl_input.metadata["template"]["viz_type"] == "contour_plot"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
