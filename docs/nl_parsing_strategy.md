# Phase 1 NL Postprocess 解析策略

## 概述

Phase 1 的 NL Postprocess Executor 采用**规则优先 + LLM 增强**的分层策略，将工程师的自然语言后处理指令转换为可执行的动作序列。

## 分层策略

### Layer 1: 规则引擎（Rule-Based Engine）

**职责**：处理常见、明确的指令模式

**核心特点**：
- **快速响应**：无 LLM 调用延迟
- **可预测**：规则明确，结果可复现
- **低资源消耗**：仅依赖本地计算

**能力范围**：

| 指令类型 | 规则匹配方式 | 示例 |
|---------|-------------|------|
| 绘图指令 | 关键词匹配（云图/等值线/线图/矢量图/流线） | `"压力云图"` → GENERATE_PLOT |
| 截面提取 | 位置模式（平面/截面/壁面） | `"z=0.5截面"` → EXTRACT_SECTION |
| 指标计算 | 动词+名词模式（计算/度量） | `"计算压力降"` → CALCULATE_METRIC |
| 数据对比 | 对比词识别（对比/比较/vs） | `"入口和出口压力对比"` → COMPARE_DATA |
| 内容重排 | 序列关键词（按...顺序） | `"按报告顺序：总览 截面"` → REORDER_CONTENT |

**规则设计原则**：
1. **高召回率**：宁可误判，不可漏判
2. **优先级明确**：特殊模式优先于通用模式
3. **中英文双语**：同时支持中英文关键词

**关键词字典**：
```python
# 绘图关键词
_plot_keywords = {
    "云图": ["contour", "field", "cloud"],
    "等值线": ["contour", "iso", "level"],
    "线图": ["line", "curve", "profile", "plot"],
    "矢量图": ["vector", "arrow"],
    "流线": ["streamline", "pathline", "streakline"],
}

# 截面关键词
_section_keywords = {
    "平面": ["plane", "slice", "section"],
    "截面": ["section", "slice", "cut"],
    "壁面": ["wall", "surface"],
}

# 指标关键词
_metric_keywords = {
    "系数": ["coefficient", "cd", "cl"],
    "压力": ["pressure", "p"],
    "速度": ["velocity", "u"],
}
```

### Layer 2: LLM 增强层（Future Enhancement）

**职责**：处理复杂、模糊或超出规则范围的指令

**触发条件**：
1. 规则引擎置信度 < 0.6
2. 包含多个复合意图
3. 包含领域特定术语（不在关键词字典中）
4. 显式请求（`"用AI解析"`）

**设计考虑**：
- **仅解析，不执行**：LLM 仅输出结构化 ActionPlan，不直接操作数据
- **结果验证**：LLM 输出需通过 G1-P1 Gate 验证
- **回退机制**：LLM 解析失败时回退到规则引擎

## 动作类型

### GENERATE_PLOT
生成可视化图表

**参数**：
- `field`: 场变量（pressure/velocity/temperature）
- `plot_type`: 图表类型（contour/vector/streamline）
- `plane`: 截面位置（xy/xz/yz）
- `colormap`: 颜色映射（viridis/coolwarm）
- `range`: 值域范围（auto/min,max）

**资源需求**：
- `field_data`: 场数据文件

### EXTRACT_SECTION
提取截面数据

**参数**：
- `location`: 截面位置（z=0.5 / centerline / wall）
- `fields`: 提取的场变量列表

**资源需求**：
- `field_data`: 场数据文件

### CALCULATE_METRIC
计算性能指标

**参数**：
- `metric_type`: 指标类型（pressure_drop / drag_coefficient / max_velocity）
- `method`: 计算方法（surface_integral / line_average）

**资源需求**：
- `field_data` + `monitor_point` 或 `surface_data`

### COMPARE_DATA
对比数据

**参数**：
- `sources`: 数据源列表（[inlet, outlet]）
- `fields`: 对比的场变量
- `comparison_type`: 对比类型（difference / ratio）

**资源需求**：
- `field_data` 或 `monitor_point`

### REORDER_CONTENT
重排报告内容

**参数**：
- `sequence`: 目标序列（["overview", "plots", "data"]）

**资源需求**：
- 无（纯逻辑操作）

## 置信度计算

```python
confidence = (1.0 - len(missing_assets) * 0.2) * avg_action_confidence
```

**置信度等级**：
- **0.8-1.0**: 高置信度，可直接执行
- **0.5-0.8**: 中置信度，建议工程师确认
- **0.0-0.5**: 低置信度，需要 LLM 增强或人工干预

## 可执行性检查（G1-P1 Gate）

ActionPlan 需通过 G1-P1 Gate 验证：

```python
def is_executable(action_plan: ActionPlan, manifest: ResultManifest) -> bool:
    # 1. 检查资源可用性
    available_types = {a.asset_type for a in manifest.assets}
    for action in action_plan.actions:
        for required in action.requires_assets:
            if required not in available_types:
                return False

    # 2. 检查参数完整性
    for action in action_plan.actions:
        if not action.parameters:
            return False

    return True
```

## 扩展指南

### 添加新的关键词

1. 在 `NLPostprocessExecutor.__init__()` 中添加关键词字典
2. 在 `_detect_intent()` 中添加检测逻辑
3. 在 `_parse_*_instruction()` 中添加参数提取逻辑
4. 添加测试用例验证

### 集成 LLM 层

```python
class LLMEnhancedParser(NLPostprocessExecutor):
    def parse_instruction(self, instruction: str, manifest: ResultManifest) -> ActionPlan:
        # 先尝试规则引擎
        plan = super().parse_instruction(instruction, manifest)

        # 如果置信度过低，调用 LLM
        if plan.confidence < 0.6:
            plan = self._llm_parse(instruction, manifest)

        return plan

    def _llm_parse(self, instruction: str, manifest: ResultManifest) -> ActionPlan:
        # 调用 LLM API 进行解析
        # 返回结构化 ActionPlan
        pass
```

## 参考资料

- 实现代码：`knowledge_compiler/phase1/nl_postprocess.py`
- 测试：`tests/test_phase1_nl_postprocess.py`
- E2E 示例：`tests/test_phase1_e2e_backward_step.py`
