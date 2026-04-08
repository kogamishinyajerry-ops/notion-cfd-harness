#!/usr/bin/env python3
"""
Postprocess Adapter - 适配器层

在 Phase 2 D 层 (Postprocess Runner) 和 Phase 1 B 层 (NL Postprocess Executor) 之间
提供解耦的转换层。

架构:
    Solver Runner → Postprocess Runner (D层) → StandardPostprocessResult
                                                    ↓
                                            PostprocessAdapter
                                                    ↓
                                    NL Postprocess (B层可消费格式)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from knowledge_compiler.phase2.execution_layer.postprocess_runner import (
    StandardPostprocessResult,
    FieldData,
    ResidualSummary,
    DerivedQuantity,
    PostprocessStatus,
)


# ============================================================================
# NL Postprocess Input Format (B Layer)
# ============================================================================

class VisualizationType(Enum):
    """可视化类型"""
    LINE_PLOT = "line_plot"
    CONTOUR_PLOT = "contour_plot"
    VECTOR_PLOT = "vector_plot"
    ISOSURFACE = "isosurface"
    STREAMLINE = "streamline"
    TABLE = "table"


@dataclass
class PlotData:
    """绘图数据"""
    x_values: List[float] = field(default_factory=list)
    y_values: List[float] = field(default_factory=list)
    x_label: str = ""
    y_label: str = ""
    title: str = ""
    data_series: Dict[str, List[float]] = field(default_factory=dict)  # 多系列数据


@dataclass
class ComparisonData:
    """对比数据"""
    location_a: str = ""
    location_b: str = ""
    field_name: str = ""
    value_a: float = 0.0
    value_b: float = 0.0
    difference: float = 0.0
    percent_difference: float = 0.0


@dataclass
class NLPostprocessInput:
    """
    NL Postprocess 输入格式 - B 层可消费格式

    这是 Phase 1 NL Postprocess Executor 期望的输入格式。
    Adapter 负责将 StandardPostprocessResult 转换为此格式。
    """
    input_id: str = field(default_factory=lambda: f"NL-PP-{time.time():.0f}")
    source_result_id: str = ""  # 来源 StandardPostprocessResult ID
    created_at: float = field(default_factory=time.time)

    # 可视化数据
    plot_data: Dict[str, PlotData] = field(default_factory=dict)
    comparison_data: List[ComparisonData] = field(default_factory=list)

    # 摘要信息
    convergence_summary: str = ""
    field_summary: Dict[str, str] = field(default_factory=str)
    residual_summary: str = ""

    # 原始数据引用
    field_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "input_id": self.input_id,
            "source_result_id": self.source_result_id,
            "created_at": self.created_at,
            "plot_data": {
                k: {
                    "x_values": v.x_values,
                    "y_values": v.y_values,
                    "x_label": v.x_label,
                    "y_label": v.y_label,
                    "title": v.title,
                    "data_series": v.data_series,
                }
                for k, v in self.plot_data.items()
            },
            "comparison_data": [
                {
                    "location_a": c.location_a,
                    "location_b": c.location_b,
                    "field_name": c.field_name,
                    "value_a": c.value_a,
                    "value_b": c.value_b,
                    "difference": c.difference,
                    "percent_difference": c.percent_difference,
                }
                for c in self.comparison_data
            ],
            "convergence_summary": self.convergence_summary,
            "field_summary": self.field_summary,
            "residual_summary": self.residual_summary,
            "metadata": self.metadata,
        }


# ============================================================================
# Postprocess Adapter
# ============================================================================

class PostprocessAdapter:
    """
    后处理适配器

    职责:
    1. 接收 StandardPostprocessResult (D 层输出)
    2. 转换为 NLPostprocessInput (B 层输入)
    3. 提供常用可视化模板

    设计原则:
    - 单向数据流: D → B (不在 Adapter 中实现反向转换)
    - 可扩展: 新增可视化类型不影响 D 层
    - 无侵入: D 层和 B 层独立演进
    """

    def __init__(self):
        self.conversion_count = 0

    def convert(
        self,
        standard_result: StandardPostprocessResult,
        viz_options: Optional[Dict[str, Any]] = None,
    ) -> NLPostprocessInput:
        """
        转换标准结果为 NL Postprocess 输入

        Args:
            standard_result: StandardPostprocessResult (D 层输出)
            viz_options: 可视化选项

        Returns:
            NLPostprocessInput (B 层输入)
        """
        self.conversion_count += 1
        viz_options = viz_options or {}

        nl_input = NLPostprocessInput(
            source_result_id=standard_result.result_id,
        )

        # 1. 转换收敛摘要
        if standard_result.residuals:
            nl_input.convergence_summary = self._format_convergence(
                standard_result.residuals
            )
            nl_input.residual_summary = self._format_residuals(
                standard_result.residuals
            )

        # 2. 转换场摘要
        nl_input.field_summary = self._format_fields(standard_result.fields)

        # 3. 生成绘图数据
        if viz_options.get("generate_plots", True):
            nl_input.plot_data = self._generate_plots(
                standard_result,
                viz_options,
            )

        # 4. 生成对比数据
        if viz_options.get("generate_comparison", False):
            nl_input.comparison_data = self._generate_comparisons(
                standard_result,
                viz_options,
            )

        # 5. 传递元数据
        nl_input.metadata = {
            "case_path": standard_result.case_path,
            "solver_type": standard_result.solver_type,
            "processing_time": standard_result.processing_time,
            "n_fields": len(standard_result.fields),
            "n_derivatives": len(standard_result.derived_quantities),
        }

        return nl_input

    def _format_convergence(self, residuals: ResidualSummary) -> str:
        """格式化收敛摘要"""
        if residuals.converged:
            status = f"✓ 收敛 ({residuals.convergence_reason})"
        else:
            status = "✗ 未收敛"

        info = [status]
        if residuals.variables:
            info.append(f"变量数: {len(residuals.variables)}")
        if residuals.iterations:
            avg_iter = sum(residuals.iterations.values()) / len(residuals.iterations)
            info.append(f"平均迭代: {avg_iter:.0f}")

        return " | ".join(info)

    def _format_residuals(self, residuals: ResidualSummary) -> str:
        """格式化残差摘要"""
        if not residuals.variables:
            return "无残差数据"

        lines = ["残差摘要:"]
        for var, final in residuals.variables.items():
            initial = residuals.initial.get(var, 0)
            iterations = residuals.iterations.get(var, 0)
            ratio = final / initial if initial > 0 else 0

            lines.append(
                f"  {var}: {initial:.2e} → {final:.2e} "
                f"({ratio:.2f}, {iterations} iters)"
            )

        return "\n".join(lines)

    def _format_fields(self, fields: List[FieldData]) -> Dict[str, str]:
        """格式化场摘要"""
        summary = {}

        for field in fields:
            info = f"{field.field_type.value}"
            if field.min_value is not None:
                info += f" | min: {field.min_value:.2e}"
            if field.max_value is not None:
                info += f" | max: {field.max_value:.2e}"
            summary[field.name] = info

        return summary

    def _generate_plots(
        self,
        result: StandardPostprocessResult,
        options: Dict[str, Any],
    ) -> Dict[str, PlotData]:
        """生成绘图数据"""
        plots = {}

        # 残差曲线
        if result.residuals and result.residuals.variables:
            plots["residuals"] = self._generate_residual_plot(result.residuals)

        # 场数据曲线 (如果有时间序列数据)
        if options.get("plot_time_series", False):
            for field in result.fields:
                if field.time_steps:
                    plots[f"{field.name}_time_series"] = PlotData(
                        x_values=field.time_steps,
                        x_label="Time (s)",
                        y_label=field.name,
                        title=f"{field.name} vs Time",
                    )

        return plots

    def _generate_residual_plot(self, residuals: ResidualSummary) -> PlotData:
        """生成残差绘图数据"""
        # 简化版本 - 实际实现需要完整的残差历史
        plot = PlotData(
            x_label="Iteration",
            y_label="Residual",
            title="Convergence History",
        )

        # 使用最终残差作为简化数据点
        for i, (var, final) in enumerate(residuals.variables.items()):
            initial = residuals.initial.get(var, final)
            plot.data_series[var] = [initial, final]

        return plot

    def _generate_comparisons(
        self,
        result: StandardPostprocessResult,
        options: Dict[str, Any],
    ) -> List[ComparisonData]:
        """生成对比数据"""
        comparisons = []

        # 压降对比
        p_field = result.get_field("p")
        if p_field and p_field.min_value is not None and p_field.max_value is not None:
            comparisons.append(ComparisonData(
                location_a="min",
                location_b="max",
                field_name="pressure",
                value_a=p_field.min_value,
                value_b=p_field.max_value,
                difference=p_field.max_value - p_field.min_value,
                percent_difference=(
                    (p_field.max_value - p_field.min_value)
                    / p_field.min_value * 100
                    if p_field.min_value > 0 else 0
                ),
            ))

        # 进出口对比 (如果有位置信息)
        inlet_pressure = options.get("inlet_pressure")
        outlet_pressure = options.get("outlet_pressure")

        if inlet_pressure is not None and outlet_pressure is not None:
            comparisons.append(ComparisonData(
                location_a="inlet",
                location_b="outlet",
                field_name="pressure",
                value_a=inlet_pressure,
                value_b=outlet_pressure,
                difference=outlet_pressure - inlet_pressure,
                percent_difference=(
                    (outlet_pressure - inlet_pressure)
                    / inlet_pressure * 100
                    if inlet_pressure > 0 else 0
                ),
            ))

        return comparisons


# ============================================================================
# Template-Based Visualization
# ============================================================================

@dataclass
class VisualizationTemplate:
    """可视化模板"""
    template_id: str
    name: str
    viz_type: VisualizationType
    required_fields: List[str]
    optional_params: Dict[str, Any] = field(default_factory=dict)

    def can_apply(self, result: StandardPostprocessResult) -> bool:
        """检查是否可以应用此模板"""
        available_fields = {f.name for f in result.fields}
        return all(req in available_fields for req in self.required_fields)


class TemplateRegistry:
    """可视化模板注册表"""

    def __init__(self):
        self.templates = [
            VisualizationTemplate(
                template_id="pressure_contour",
                name="压力云图",
                viz_type=VisualizationType.CONTOUR_PLOT,
                required_fields=["p"],
                optional_params={"plane": "midplane", "time_step": "0"},
            ),
            VisualizationTemplate(
                template_id="velocity_vector",
                name="速度矢量图",
                viz_type=VisualizationType.VECTOR_PLOT,
                required_fields=["U"],
                optional_params={"scale": "linear", "time_step": "0"},
            ),
            VisualizationTemplate(
                template_id="inlet_outlet_pressure",
                name="进出口压力对比",
                viz_type=VisualizationType.LINE_PLOT,
                required_fields=["p"],
                optional_params={"locations": ["inlet", "outlet"]},
            ),
            VisualizationTemplate(
                template_id="residual_history",
                name="残差历史",
                viz_type=VisualizationType.LINE_PLOT,
                required_fields=[],
                optional_params={"variables": []},
            ),
        ]

    def get_applicable_templates(
        self,
        result: StandardPostprocessResult,
    ) -> List[VisualizationTemplate]:
        """获取适用的可视化模板"""
        return [t for t in self.templates if t.can_apply(result)]

    def get_template(self, template_id: str) -> Optional[VisualizationTemplate]:
        """根据 ID 获取模板"""
        for template in self.templates:
            if template.template_id == template_id:
                return template
        return None


# ============================================================================
# Extended Adapter with Template Support
# ============================================================================

class TemplatePostprocessAdapter(PostprocessAdapter):
    """
    带模板支持的后处理适配器

    扩展 Adapter 以支持基于模板的可视化生成。
    """

    def __init__(self):
        super().__init__()
        self.template_registry = TemplateRegistry()

    def convert_with_template(
        self,
        standard_result: StandardPostprocessResult,
        template_id: str,
        template_params: Optional[Dict[str, Any]] = None,
    ) -> NLPostprocessInput:
        """
        使用指定模板转换结果

        Args:
            standard_result: 标准后处理结果
            template_id: 模板 ID
            template_params: 模板参数

        Returns:
            NLPostprocessInput
        """
        template = self.template_registry.get_template(template_id)
        if template is None:
            raise ValueError(f"Unknown template: {template_id}")

        # 基础转换
        nl_input = self.convert(standard_result)

        # 添加模板信息
        nl_input.metadata["template"] = {
            "id": template_id,
            "name": template.name,
            "viz_type": template.viz_type.value,
            "params": template_params or template.optional_params,
        }

        return nl_input

    def list_available_templates(
        self,
        result: StandardPostprocessResult,
    ) -> List[Dict[str, Any]]:
        """列出可用的可视化模板"""
        templates = self.template_registry.get_applicable_templates(result)

        return [
            {
                "id": t.template_id,
                "name": t.name,
                "type": t.viz_type.value,
                "required_fields": t.required_fields,
                "optional_params": t.optional_params,
            }
            for t in templates
        ]


# ============================================================================
# Convenience Functions
# ============================================================================

def adapt_for_nl_postprocess(
    standard_result: StandardPostprocessResult,
    options: Optional[Dict[str, Any]] = None,
) -> NLPostprocessInput:
    """便捷函数：转换为 NL Postprocess 格式"""
    adapter = PostprocessAdapter()
    return adapter.convert(standard_result, options)


def apply_template(
    standard_result: StandardPostprocessResult,
    template_id: str,
    params: Optional[Dict[str, Any]] = None,
) -> NLPostprocessInput:
    """便捷函数：应用可视化模板"""
    adapter = TemplatePostprocessAdapter()
    return adapter.convert_with_template(standard_result, template_id, params)
