# CAD Parser 架构审查问题清单

**提交给：** Opus 4.6
**上下文：** Phase 3 Orchestrator Layer - CAD Parser 模块架构设计
**时间：** 2026-04-08

---

## 1. 架构集成问题

### 1.1 与 Phase 2 Execution Layer 的集成
**问题：** CAD Parser 输出的 `ParsedGeometry` 需要作为 Mesh Builder 的输入，但当前数据结构可能不一致。

**当前设计：**
```python
@dataclass
class ParsedGeometry:
    geometry_id: str
    source_file: str
    format: MeshFormat
    features: List[GeometryFeature]
    bounding_box: Optional[Dict[str, float]]
    surface_area: float
    volume: float
    is_watertight: bool
    repair_needed: List[str]
```

**MeshBuilder 期望输入：**
```python
@dataclass
class MeshConfig:
    format: MeshFormat
    base_geometry: str  # 文件路径，不是 ParsedGeometry
    target_element_size: float = 1.0
    ...
```

**⚠️ 冲突：** MeshBuilder 直接接受文件路径，而 CAD Parser 输出解析后的对象。需要：
1. MeshBuilder 是否应该接受 `ParsedGeometry` 而非文件路径？
2. 或者 `ParsedGeometry` 应该包含输出文件路径用于传递？

---

### 1.2 与 Physics Planner 的协调
**问题：** 几何特征是否影响 Physics Planner 的决策？

**示例场景：**
- 如果检测到几何有大量小孔洞 → 是否建议使用特定湍流模型？
- 如果几何是对称的 → 是否可以建议简化计算域？

**问题：** CAD Parser 和 Physics Planner 之间是否需要反馈回路？

---

## 2. 数据结构设计问题

### 2.1 GeometryFeature 的粒度
**问题：** `GeometryFeature.type` 应该支持哪些值？

**选项 A - 简化版：**
```python
type: str  # face, edge, vertex, volume
```

**选项 B - 详细版：**
```python
type: str  # face, edge, vertex, volume, curve, surface, solid, ...
```

**⚠️ 权衡：** 更详细的分类增加复杂度，但可能对某些高级用例必要。

---

### 2.2 边界条件与几何特征的关联
**问题：** CAD Parser 是否应该识别几何上的潜在边界区域？

**示例：**
```python
@dataclass
class GeometryFeature:
    ...
    properties: Dict[str, Any]  # 是否应该包含 "potential_boundary" 标记？
```

**用途：** 自动推断哪些面可能是 inlet/outlet/wall，辅助用户设置边界条件。

---

## 3. 格式支持优先级

### 3.1 首批实现的格式
**问题：** 优先支持哪些格式？

| 格式 | 优点 | 缺点 | 优先级建议 |
|------|------|------|-----------|
| STL | 简单、广泛支持 | 仅三角形、无拓扑 | ⭐⭐⭐ |
| STEP | 精确曲线曲面 | 解析复杂 | ⭐⭐ |
| IGES | 老标准兼容 | 格式混乱 | ⭐ |
| OBJ | 简单、可选法向量 | 无拓扑 | ⭐⭐ |

**⚠️ 问题：** 是否先实现 STL + STEP，其他稍后？

---

### 3.2 格式检测策略
**当前实现：**
```python
def detect_format(file_path: str) -> MeshFormat:
    ext = Path(file_path).suffix.lower().lstrip(".")
    return ext_to_type.get(ext, MeshFormat.TRI_SURFACE)
```

**⚠️ 问题：** 仅依赖扩展名是否足够？是否需要文件头验证？

---

## 4. 几何验证算法

### 4.1 Watertight 检测
**问题：** 如何高效检测 watertight（流形几何）？

**方法 A - 拓扑检查：**
- 检查每条边是否恰好属于 2 个面（内部边）或 1 个面（边界边）
- 边界边数量 = 0 → watertight

**方法 B - 体积检查：**
- 封闭体积计算
- 如果能计算出有效体积 → watertight

**⚠️ 问题：** 哪种方法更可靠？对于 STL（无拓扑信息）如何处理？

---

### 4.2 法向量一致性
**问题：** 如何检测和修复法向量一致性问题？

**场景：** STL 文件中部分三角形的法向量指向内部。

**检测方法：**
- 遍历所有边，检查相邻三角形法向量夹角
- 夹角 > 90° → 可能存在法向量翻转

**⚠️ 问题：** 是否应该在 CAD Parser 中自动修复，还是只报告问题？

---

## 5. 修复策略

### 5.1 自动修复 vs 仅建议
**问题：** CAD Parser 是否应该执行自动修复？

**选项 A - 仅报告：**
```python
@dataclass
class ParsedGeometry:
    ...
    repair_needed: List[str]  # ["有 15 个孔洞", "5 个重叠面"]
```

**选项 B - 自动修复：**
```python
def repair_geometry(geometry: ParsedGeometry) -> ParsedGeometry:
    # 执行修复操作
    ...
```

**⚠️ 权衡：** 自动修复可能改变用户原始几何，存在风险。

---

### 5.2 修复工具集成
**问题：** 是否集成外部修复工具？

**候选工具：**
- `surfacefix` (OpenFOAM)
- `meshlab` (Python API)
- `trimesh` (Python 库)

**⚠️ 问题：** 是否依赖外部工具，还是纯 Python 实现？

---

## 6. 性能与扩展性

### 6.1 大文件处理
**问题：** 如何处理大几何文件（>100MB）？

**选项 A - 流式解析：**
- 逐块读取和解析
- 降低内存占用

**选项 B - 全部加载：**
- 一次性读取全部数据
- 实现简单，但内存占用高

**⚠️ 问题：** 是否需要支持流式解析？

---

### 6.2 并行处理
**问题：** 特征提取是否可以并行化？

**可并行任务：**
- 面积/体积计算
- 法向量检查
- 特征统计

**⚠️ 问题：** 是否值得增加复杂度来实现并行？

---

## 7. 错误处理

### 7.1 解析失败降级
**问题：** 当几何解析部分失败时如何处理？

**示例场景：**
- 文件可以读取，但某些面数据损坏
- 选项 A：返回部分结果 + 警告
- 选项 B：完全失败，返回错误

**⚠️ 问题：** 哪种策略更适合？

---

### 7.2 格式不兼容
**问题：** 遇到不支持的格式时如何处理？

**选项 A：**
```python
raise UnsupportedFormatError(f"Format {fmt} not supported")
```

**选项 B：**
```python
return ParsedGeometry(
    source_file=file_path,
    format=MeshFormat.UNKNOWN,
    status="unsupported"
)
```

---

## 8. 测试策略

### 8.1 测试数据来源
**问题：** 哪里获取测试用几何文件？

**选项：**
- 生成简单几何（立方体、球体）
- 从开放数据集下载
- 用户手工提供测试文件

**⚠️ 问题：** 测试数据的来源和格式？

---

### 8.2 性能基准
**问题：** 是否需要性能基准测试？

**指标：**
- 解析速度（MB/s）
- 内存占用
- 特征提取时间

**目标：**
- 10MB STL < 2秒
- 100MB STEP < 30秒

---

## 9. 依赖库选择

### 9.1 几何处理库
**问题：** 使用哪个 Python 几何处理库？

| 库 | 优点 | 缺点 |
|---|------|------|
| `trimesh` | 简单、高效 | 仅支持网格 |
| `numpy-stl` | 快速 STL 解析 | 功能有限 |
| `pythonocc` | 完整 CAD 支持 | 重量级、难安装 |
| `ezdxf` | DXF 支持 | 格式单一 |

**⚠️ 问题：** 推荐哪个库作为主要依赖？

---

## 10. G3 质量门验证

### 10.1 覆盖率目标
**当前设定：** 单元测试覆盖率 ≥ 80%

**问题：** 对于 CAD 解析这种复杂逻辑，80% 是否足够？

### 10.2 Watertight 检测准确率
**当前设定：** Watertight 检测准确率 ≥ 95%

**问题：** 如何验证这个指标？需要标准测试集吗？

---

## 总结：优先级排序

**P0 - 必须先解决：**
1. 与 MeshBuilder 的集成方式（数据流）
2. 格式支持优先级（STL 优先 vs 全部并行）
3. Watertight 检测算法选择

**P1 - 实现前确定：**
4. 自动修复 vs 仅报告策略
5. 依赖库选择
6. 错误处理策略

**P2 - 可以迭代优化：**
7. GeometryFeature 粒度
8. 大文件流式解析
9. 并行处理
10. 性能基准

---

**请 Opus 4.6 审查以上问题，并提供：**
1. 架构决策建议
2. 优先级调整
3. 潜在风险点
4. 与现有 Phase 2/3 模块的集成方案
