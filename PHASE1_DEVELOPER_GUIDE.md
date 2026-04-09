# Phase 1 开发者指南
**Standard Knowledge Collector - 开发扩展**

**版本**: 1.0
**日期**: 2026-04-08

---

## 一、开发环境设置

### 1.1 依赖安装

```bash
# 克隆仓库
git clone <repository_url>
cd notion-cfd-harness

# 安装依赖
pip install pytest pytest-cov

# 运行测试
pytest tests/ -k phase1 -v
```

### 1.2 代码结构

```
knowledge_compiler/phase1/
├── __init__.py              # 公共接口
├── schema.py                # 数据模型
├── manager.py               # CRUD 管理
├── skeleton.py              # 骨架生成
├── teach.py                 # Teach Mode
├── replay.py                # 重放引擎
├── gates.py                 # Gates
├── nl_postprocess.py        # NL 解析
├── visualization.py         # 可视化
└── gold_standards/          # 黄金标准
```

---

## 二、扩展指南

### 2.1 添加新的问题类型

```python
# 1. 在 schema.py 中添加
class ProblemType(Enum):
    EXTERNAL_FLOW = "external_flow"    # 现有
    INTERNAL_FLOW = "internal_flow"    # 现有
    MULTIPHASE_FLOW = "multiphase_flow"  # 新增

# 2. 在 skeleton.py 中添加默认配置
PROBLEM_TYPE_DEFAULTS = {
    # ... 现有配置
    ProblemType.MULTIPHASE_FLOW: {
        "required_plots": [...],
        "required_metrics": [...],
    },
}
```

### 2.2 添加新的 Gate

```python
# 在 gates.py 中添加
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class MyCustomGate:
    """自定义 Gate 检查"""

    gate_id: str = "P1-CUSTOM"
    gate_name: str = "My Custom Gate"

    def check(self, context: Dict[str, Any]) -> GateResult:
        """执行检查"""
        checks = [
            GateCheckItem(
                name="检查项1",
                passed=True,
                message="检查通过",
                severity=Severity.BLOCK,
            )
        ]

        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            status=GateStatus.PASS if all(c.passed for c in checks) else GateStatus.FAIL,
            checks=checks,
            timestamp=datetime.now(),
            metadata={},
    )

# 注册到 Phase1GateExecutor
class Phase1GateExecutor:
    # ... 现有方法

    def run_custom_gate(self, context: Dict[str, Any]) -> GateResult:
        gate = MyCustomGate()
        return gate.check(context)
```

### 2.3 扩展 NL 解析

```python
# 在 nl_postprocess.py 中添加新的意图类型

class ActionType(Enum):
    GENERATE_PLOT = "generate_plot"
    EXTRACT_SECTION = "extract_section"
    # ... 现有类型
    CALCULATE_DERIVATIVE = "calculate_derivative"  # 新增

# 在 _detect_intent 中添加检测逻辑
def _detect_intent(self, instruction: str) -> str:
    instruction_lower = instruction.lower()

    # 新意图检测
    if any(kw in instruction_lower for kw in ["导数", "derivative", "梯度"]):
        return "derivative"

    # ... 现有检测逻辑

# 在 parse_instruction 中添加处理
elif intent == "derivative":
    actions, missing_assets = self._parse_derivative_instruction(
        instruction, instruction_lower, available_assets, manifest
    )
```

### 2.4 添加新的黄金标准

```python
# 在 gold_standards/ 目录创建新文件
# lid_driven_cavity.py

from dataclasses import dataclass
from knowledge_compiler.phase1.schema import ReportSpec

@dataclass
class CavityConstants:
    """Lid-Driven Cavity 常量"""
    REYNOLDS_NUMBER = 1000.0
    LID_VELOCITY = 1.0
    CAVITY_SIZE = 1.0

def create_lid_driven_cavity_spec(
    case_id: str = "lid_driven_cavity",
    reynolds_number: float = 1000.0,
) -> ReportSpec:
    """创建 Lid-Driven Cavity ReportSpec"""
    # 实现...

class CavityGateValidator:
    """Cavity 案例验证器"""
    def __init__(self):
        self.gold_spec = create_lid_driven_cavity_spec()

    def validate_report_spec(self, spec: ReportSpec) -> Dict[str, Any]:
        # 实现...
```

### 2.5 扩展可视化引擎

```python
# 在 visualization.py 中添加新的输出格式

class OutputFormat(Enum):
    PNG = "png"
    VTK = "vtk"
    JSON = "json"
    CSV = "csv"  # 新增

# 添加新的计算方法
class VisualizationEngine:
    # ... 现有方法

    def _calc_vorticity(self, parameters: Dict, manifest) -> Dict:
        """计算涡量场"""
        return {
            "field": "vorticity",
            "unit": "1/s",
            "value": 0.0,  # 实际计算
            "locations": [],
        }
```

---

## 三、测试指南

### 3.1 添加新测试

```python
# tests/test_phase1_my_feature.py

import pytest
from knowledge_compiler.phase1 import MyFeature

class TestMyFeature:
    """测试我的新功能"""

    def test_basic_functionality(self):
        """测试基本功能"""
        feature = MyFeature()
        result = feature.do_something()
        assert result is not None

    def test_edge_case(self):
        """测试边界情况"""
        feature = MyFeature()
        result = feature.do_something(edge_case=True)
        assert result == expected_value
```

### 3.2 测试覆盖目标

- **单元测试**: 每个公共方法至少一个测试
- **集成测试**: 关键工作流至少一个测试
- **边界测试**: 异常输入、空值、极值

### 3.3 运行测试

```bash
# 运行所有 Phase 1 测试
pytest tests/ -k phase1 -v

# 运行特定测试文件
pytest tests/test_phase1_my_feature.py -v

# 生成覆盖率报告
pytest tests/ -k phase1 --cov=knowledge_compiler.phase1 --cov-report=html
```

---

## 四、代码规范

### 4.1 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 类名 | PascalCase | `ReportSpecManager` |
| 函数名 | snake_case | `create_report_spec` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| 私有方法 | _leading_underscore | `_validate_input` |

### 4.2 文档字符串

```python
def complex_function(arg1: str, arg2: int) -> Dict[str, Any]:
    """
    函数简短描述（一行）

    详细描述（多行，说明函数用途、行为）

    Args:
        arg1: 参数1说明
        arg2: 参数2说明

    Returns:
        返回值说明

    Raises:
        ValueError: 什么情况下抛出

    Examples:
        >>> complex_function("test", 42)
        {"result": "success"}
    """
```

### 4.3 类型注解

```python
from typing import List, Dict, Any, Optional

def good_function(
    required: str,
    optional: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """带类型注解的函数"""
    return []
```

---

## 五、提交规范

### 5.1 Commit 消息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `test`: 测试相关
- `refactor`: 重构
- `chore`: 构建/工具

**示例**:
```
feat(gates): add P1-G5 validation gate

Implement the validation gate for checking completeness
of required documentation before promoting to APPROVED status.

Closes #123
```

### 5.2 Pull Request 流程

1. 创建功能分支: `git checkout -b feature/my-feature`
2. 开发并测试
3. 提交 PR
4. 请求审查
5. 修改反馈
6. 合并到主分支

---

## 六、调试技巧

### 6.1 启用详细日志

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Debug info: %s", variable)
```

### 6.2 使用 pytest 断点

```python
def test_something():
    result = complex_function()
    import pdb; pdb.set_trace()  # 设置断点
    assert result == expected
```

### 6.3 MOCK 模式测试

```python
# 使用 MOCK 模式快速测试逻辑
from unittest.mock import Mock, patch

def test_with_mock():
    with patch('knowledge_compiler.phase1.visualization.real_function') as mock:
        mock.return_value = {"value": 42}
        # 测试逻辑...
```

---

## 七、常见问题

### 7.1 如何调试 Gate 失败？

```python
# 打印详细检查信息
g1_result = gate_executor.run_g1_gate(plan, manifest)

for check in g1_result.checks:
    print(f"{check.name}: {check.passed}")
    if not check.passed:
        print(f"  消息: {check.message}")
        print(f"  严重性: {check.severity}")
```

### 7.2 如何扩展 NL 解析？

1. 添加新的 ActionType
2. 在 _detect_intent 中添加关键词
3. 实现 _parse_xxx_instruction 方法
4. 在 VisualizationEngine 中实现执行逻辑
5. 添加测试

### 7.3 如何添加新的求解器支持？

```python
# 在 ResultManifest 中扩展
class SolverType(Enum):
    OPENFOAM = "openfoam"
    SU2 = "su2"  # 新增
    ANSYS_FLUENT = "ansys_fluent"  # 新增

# 在特定模块中处理
if manifest.solver_type == SolverType.SU2:
    # SU2 特定处理
    pass
```

---

## 八、资源链接

- **项目文档**: `PHASE1_ARCHITECTURE_OVERVIEW.md`
- **用户指南**: `PHASE1_USER_GUIDE.md`
- **测试**: `tests/test_phase1_*.py`
- **Schema**: `knowledge_compiler/phase1/schema.py`

---

**文档版本**: 1.0
**最后更新**: 2026-04-08
