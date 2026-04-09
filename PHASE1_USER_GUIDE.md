# Phase 1 用户指南
**Standard Knowledge Collector**

**版本**: 1.0
**日期**: 2026-04-08

---

## 一、快速开始

### 1.1 安装

```bash
cd notion-cfd-harness
pip install -e .
```

### 1.5 基本使用

```python
from knowledge_compiler.phase1 import (
    NLPostprocessExecutor,
    VisualizationEngine,
    ResultManifest,
    ResultAsset,
)

# 1. 创建结果清单
manifest = ResultManifest(
    solver_type="openfoam",
    case_name="backward_step",
    result_root="/path/to/results",
    assets=[
        ResultAsset(asset_type="field", path="p"),
        ResultAsset(asset_type="field", path="U"),
    ],
)

# 2. 解析自然语言
nl_executor = NLPostprocessExecutor()
plan = nl_executor.parse_instruction("生成压力云图", manifest)

# 3. 执行可视化
vis_engine = VisualizationEngine()
log = vis_engine.execute_action_plan(plan, manifest)
```

---

## 二、核心功能

### 2.1 自然语言指令

支持中英文混合输入，自动检测意图：

| 意图类型 | 中文示例 | 英文示例 |
|---------|----------|----------|
| **plot** | 生成压力云图、速度流线 | Generate pressure contour |
| **section** | 提取 x=1.0 截面 | Extract section at x=1.0 |
| **metric** | 计算再附着长度 | Calculate reattachment length |
| **compare** | 对比入口和出口 | Compare inlet and outlet |
| **reorder** | 按 A、B、C 顺序排列 | Reorder as A, B, C |

### 2.2 Teach Mode（教学模式）

当 AI 生成的报告不符合要求时，工程师可以通过 Teach Mode 记录修正：

```python
from knowledge_compiler.phase1 import (
    TeachModeEngine,
    OperationType,
    TeachContext,
)

# 创建教学上下文
context = TeachContext(
    case_name="backward_step",
    spec_id="GOLD-backward_facing_step",
    engineer_id="user_001",
)

# 记录修正操作
engine = TeachModeEngine()
response = engine.apply_correction(
    context=context,
    operation_type=OperationType.ADD_PLOT,
    target="required_plots",
    value=PlotSpec(name="vorticity_contour", plane="domain"),
    explanation="需要增加涡量云图以显示旋转结构"
)

# 检查是否可泛化
if response.is_generalizable:
    print("此修正将应用到所有类似案例")
```

### 2.3 Gate 质量验证

自动验证 AI 输出质量：

```python
from knowledge_compiler.phase1 import Phase1GateExecutor

gate_executor = Phase1GateExecutor()

# G1: 验证 ActionPlan 可执行性
g1_result = gate_executor.run_g1_gate(action_plan=plan, manifest=manifest)

if g1_result.status == GateStatus.PASS:
    print("验证通过，继续执行")
elif g1_result.status == GateStatus.WARN:
    print(f"警告: {g1_result.get_warnings()}")
else:
    print(f"失败: {g1_result.get_errors()}")
```

---

## 三、工作流示例

### 3.1 完整报告生成流程

```python
from knowledge_compiler.phase1 import (
    NLPostprocessExecutor,
    Phase1GateExecutor,
    VisualizationEngine,
    ResultManifest,
    ResultAsset,
)

# 步骤 1: 解析 CFD 结果目录
manifest = ResultManifest(
    solver_type="openfoam",
    case_name="my_case",
    result_root="/path/to/cfd/results",
    assets=[
        ResultAsset(asset_type="field", path="p"),
        ResultAsset(asset_type="field", path="U"),
        ResultAsset(asset_type="field", path="k"),
        ResultAsset(asset_type="field", path="omega"),
    ],
)

# 步骤 2: 自然语言指令
instruction = "生成完整的后处理报告，包括压力云图、速度流线、湍动能分布"

# 步骤 3: NL 解析
nl_executor = NLPostprocessExecutor()
plan = nl_executor.parse_instruction(instruction, manifest)

# 步骤 4: Gate 验证
gate_executor = Phase1GateExecutor()
g1_result = gate_executor.run_g1_gate(plan, manifest)

if g1_result.status == GateStatus.FAIL:
    print(f"验证失败: {g1_result.get_errors()}")
    exit(1)

# 步骤 5: 执行可视化
vis_engine = VisualizationEngine(output_root="./outputs")
log = vis_engine.execute_action_plan(plan, manifest)

# 步骤 6: 检查结果
for result in log.execution_results:
    if result["success"]:
        print(f"✅ {result['output_path']}")
    else:
        print(f"❌ {result['error']}")
```

### 3.2 使用黄金标准

```python
from knowledge_compiler.phase1.gold_standards import (
    create_backward_facing_step_spec,
    BackwardStepGateValidator,
)

# 创建黄金标准规范
gold_spec = create_backward_facing_step_spec(
    case_id="my_backward_step",
    reynolds_number=400.0,
    is_turbulent=False,
)

# 验证自定义规范是否符合黄金标准
validator = BackwardStepGateValidator()
result = validator.validate_report_spec(my_spec)

if result["passed"]:
    print("✅ 符合黄金标准")
else:
    print(f"❌ 缺失: {result['errors']}")
```

---

## 四、常见问题

### 4.1 为什么我的指令没有被正确解析？

**可能原因**:
- 指令过于模糊
- 缺少必要的上下文
- 资源文件不存在

**解决方案**:
```python
# 检查解析结果
plan = nl_executor.parse_instruction("指令", manifest)
print(f"检测意图: {plan.detected_intent}")
print(f"置信度: {plan.confidence}")
print(f"缺失资源: {plan.missing_assets}")
```

### 4.2 如何添加自定义图表类型？

**方法 1**: 使用 Teach Mode
```python
response = engine.apply_correction(
    context=context,
    operation_type=OperationType.ADD_PLOT,
    target="required_plots",
    value=PlotSpec(name="my_plot", plane="custom"),
    explanation="添加自定义图表"
)
```

**方法 2**: 直接修改 ReportSpec
```python
from knowledge_compiler.phase1 import ReportSpecManager

manager = ReportSpecManager()
spec = manager.get(spec_id)
spec.required_plots.append(
    PlotSpec(name="my_plot", plane="custom")
)
manager.update(spec)
```

### 4.3 Gate 验证失败怎么办？

**检查步骤**:
1. 查看 Gate 检查项详情
2. 确认资源文件存在
3. 检查参数是否有效
4. 参考 Gate 错误信息修正

```python
g1_result = gate_executor.run_g1_gate(plan, manifest)

if g1_result.status != GateStatus.PASS:
    for check in g1_result.checks:
        if not check.passed:
            print(f"❌ {check.name}: {check.message}")
            print(f"   严重性: {check.severity}")
```

---

## 五、最佳实践

### 5.1 命名规范

- **case_name**: 使用小写下划线，如 `backward_step`
- **plot_name**: 使用下划线，如 `velocity_magnitude_contour`
- **metric_name**: 使用下划线，如 `reattachment_length`

### 5.2 资源管理

确保 ResultManifest 准确反映实际文件结构：

```python
manifest = ResultManifest(
    solver_type="openfoam",
    case_name="my_case",
    result_root="/path/to/results",
    assets=[
        # 明确指定每个资源的类型
        ResultAsset(asset_type="field", path="p"),
        ResultAsset(asset_type="field", path="U"),
        ResultAsset(asset_type="mesh", path="polyMesh"),
    ],
)
```

### 5.3 错误处理

```python
try:
    log = vis_engine.execute_action_plan(plan, manifest)
except Exception as e:
    # 检查 ActionLog 中的错误
    if hasattr(e, 'action_log'):
        for error in e.action_log.errors:
            print(f"错误: {error}")
```

---

## 六、扩展阅读

- **架构文档**: `PHASE1_ARCHITECTURE_OVERVIEW.md`
- **API 文档**: `knowledge_compiler/phase1/*.py`
- **测试示例**: `tests/test_phase1_*.py`
- **E2E Demo**: `tests/test_phase1_e2e_demo.py`

---

## 七、反馈与支持

如有问题或建议，请：
1. 查看 `tests/` 中的示例
2. 阅读源代码中的 docstring
3. 提交 Issue 到项目仓库

---

**文档版本**: 1.0
**最后更新**: 2026-04-08
