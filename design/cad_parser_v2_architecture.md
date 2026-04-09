# CAD Parser 架构设计 v2.0

**基于 CFDJerry 审查意见修订**
**日期：** 2026-04-08

---

## ⚠️ Phase 时序合规性说明

根据 AI-CFD-001 聚焦版规范，当前项目处于 **Phase 2 阶段**（Knowledge Compiler + Autopilot）。CAD Parser 属于 Phase 3 Orchestrator Layer。

**状态**：📋 **预研设计** - 设计先行，延后实现
**实现时机**：Phase 2 稳定后，黄金样板集 replay 通过

---

## 1. 核心架构决策（基于审查意见）

### 1.1 数据流架构 — GeometryBridge 适配器模式

```python
@dataclass
class GeometryBridge:
    """几何适配器 - 连接解析层和执行层"""
    parsed: ParsedGeometry              # 完整解析结果（分析层）
    mesh_ready_path: str                 # 修复后的文件路径（执行层）
    repair_log: List[RepairAction]       # 修复记录（可追溯）

    def to_mesh_config(self) -> MeshConfig:
        """转换为 MeshBuilder 输入"""
        return MeshConfig(
            format=self.parsed.format,
            base_geometry=self.mesh_ready_path,  # 文件路径，非对象
            ...
        )
```

**决策理由**：
- MeshBuilder 接受文件路径是正确的（执行层处理文件 I/O）
- ParsedGeometry 是分析层产物，职责是理解几何
- 单一职责原则 + 模块化边界清晰

### 1.2 GeometryHints 单向信息流

```python
@dataclass
class GeometryHints:
    """几何提示 - 传递给 Physics Planner"""
    symmetry: Optional[SymmetryType]       # planar / axial / none
    characteristic_length: float            # 特征长度
    small_features: List[SmallFeature]     # 孔洞、薄壁等
    recommended_simplifications: List[str] # 简化建议

@dataclass
class BoundaryHint:
    """边界条件提示"""
    likely_type: str      # "inlet" / "outlet" / "wall" / "symmetry" / "unknown"
    confidence: float     # 0.0 – 1.0
    reason: str           # 推断依据
```

**决策理由**：
- 单向信息流：几何 → 物理，无反馈回路
- 几何是事实，物理模型是决策，不应互相修改
- 工程师纠错走 CorrectionSpec 通道

---

## 2. 数据结构（简化版）

### 2.1 GeometryFeature — CFD 语义扩展

```python
class GeometryFeatureType(Enum):
    """几何特征类型 - CFD 语义导向"""
    FACE = "face"
    EDGE = "edge"
    VERTEX = "vertex"
    VOLUME = "volume"
    # CFD 语义扩展
    BOUNDARY_ZONE = "boundary_zone"      # 识别出的边界区域
    REFINEMENT_ZONE = "refinement_zone"  # 需要加密的区域

@dataclass
class GeometryFeature:
    """几何特征"""
    type: GeometryFeatureType
    id: str = ""
    name: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    potential_boundary: Optional[BoundaryHint] = None  # 仅标记，不做决策
```

**决策理由**：
- 不做通用 CAD（curve/surface/solid 对 CFD 无直接价值）
- 聚焦 CFD 相关语义
- 边界条件识别只做标记，由工程师确认（L2 权限）

### 2.2 ParsedGeometry

```python
@dataclass
class ParsedGeometry:
    """解析后的几何"""
    geometry_id: str
    source_file: str
    format: MeshFormat
    features: List[GeometryFeature]
    bounding_box: Optional[Dict[str, float]]
    surface_area: float
    volume: float
    is_watertight: bool
    repair_needed: List[str]
    hints: GeometryHints  # 几何提示
```

---

## 3. 格式支持（聚焦 STL）

| 格式 | 决策 | 理由 | 时机 |
| --- | --- | --- | --- |
| **STL** | ✅ 首批实现 | 黄金样板全覆盖 | Phase 3 首版 |
| **STEP** | ⏳ Phase 3 后期 | 未知复杂几何需要 | Phase 3.2 |
| OBJ | ❌ 不做 | CFD 领域不用 | - |
| IGES | ❌ 不做 | 已被 STEP 替代 | - |

**格式检测**：扩展名 + 文件头双重验证

```python
def detect_format(file_path: str) -> MeshFormat:
    ext_fmt = _detect_by_extension(file_path)
    header_fmt = _detect_by_header(file_path)  # 读前 512 字节
    if ext_fmt != header_fmt:
        raise FormatMismatchWarning(f"扩展名={ext_fmt}, 文件头={header_fmt}")
    return ext_fmt
```

---

## 4. 几何验证算法

### 4.1 Watertight 检测 — 拓扑 + 体积双重检测

```python
@dataclass
class WatertightResult:
    """Watertight 检测结果"""
    is_watertight: bool
    boundary_edge_count: int
    computed_volume: Optional[float]
    method: str  # "topo+volume"

def check_watertight(mesh) -> WatertightResult:
    """使用 trimesh 进行 watertight 检测"""
    boundary_edges = mesh.edges_unique_inverse
    topo_ok = len(mesh.facets_boundary) == 0
    volume_ok = mesh.volume > 0 and mesh.is_volume

    return WatertightResult(
        is_watertight=topo_ok and volume_ok,
        boundary_edge_count=len(mesh.facets_boundary),
        computed_volume=mesh.volume if volume_ok else None,
        method="topo+volume"
    )
```

### 4.2 法向量修复 — 自动修复 + 原始文件保留

```python
@dataclass
class RepairAction:
    """修复动作记录"""
    action_type: str  # "fix_normals" / "remove_degenerate" / "fill_holes"
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    timestamp: float

def repair_normals(mesh, original_path: str) -> Tuple[Mesh, str, RepairAction]:
    """修复法向量，输出新文件，记录修复动作"""
    # trimesh.repair.fix_normals()
    # 原始文件保留，修复后写新文件
    ...
```

---

## 5. 修复策略（分级）

| 问题类型 | 处理 | 理由 | 权限 |
| --- | --- | --- | --- |
| 法向量不一致 | ✅ 自动修复 | 确定性算法 | L1 |
| 退化三角形 | ✅ 自动移除 | 不影响几何 | L1 |
| 小孔洞（< 阈值） | ⚠️ 报告 + 建议 | 可能改变意图 | L0 |
| 大孔洞 / 重叠面 | 🚫 仅报告 | 需工程师确认 | L0 |

---

## 6. 依赖库（明确选择）

| 用途 | 库 | 理由 |
| --- | --- | --- |
| STL 解析 | **`trimesh`** | 覆盖解析、检测、修复 |
| 高性能读取 | `numpy-stl` | 可选加速 |
| 可视化 | `matplotlib` | 验证用 |
| ~~STEP~~ | ~~`pythonocc`~~ | ❌ 安装困难，推迟 |

**不用外部 CLI 工具**（部署不确定性）

---

## 7. 错误处理

```python
class ParseStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"  # 部分结果，需 Gate 拦截
    FAILED = "failed"

@dataclass
class ParseResult:
    geometry: Optional[ParsedGeometry]
    status: ParseStatus
    warnings: List[ParseWarning]
    errors: List[ParseError]
```

**不支持格式 → 抛异常**（快速失败）

---

## 8. 测试策略（三层）

### 8.1 测试数据层次

| 层次 | 内容 | 覆盖 |
| --- | --- | --- |
| 生成几何 | `trimesh.creation` 立方体/球体/圆柱 | 单元测试 |
| 黄金样板 | 后向台阶/圆柱绕流 STL | 端到端测试 |
| 病态几何 | 孔洞/翻转/退化三角形 | 鲁棒性测试 |

### 8.2 覆盖率目标：90%

CAD Parser 是数据入口，解析错误会传播下游，90% 是安全线。

### 8.3 性能基准（目标，非 Gate）

- 10MB STL < 2s
- 100MB STL < 30s

---

## 9. 模块设计

```python
class CADParser:
    """CAD 几何解析器"""

    def detect_format(self, file_path: str) -> MeshFormat:
        """格式检测（扩展名 + 文件头）"""

    def validate_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """文件完整性验证"""

    def parse(self, file_path: str) -> ParseResult:
        """解析几何文件"""

    def extract_features(self, geometry) -> List[GeometryFeature]:
        """提取几何特征"""

    def calculate_metrics(self, geometry) -> GeometryMetrics:
        """计算几何指标"""

    def check_watertight(self, geometry) -> WatertightResult:
        """Watertight 检测"""

    def generate_repair_suggestions(self, geometry) -> List[str]:
        """生成修复建议"""

    def detect_boundaries(self, geometry) -> List[BoundaryHint]:
        """检测潜在边界（仅标记）"""

    def create_bridge(self, result: ParseResult) -> GeometryBridge:
        """创建几何适配器"""

# 便捷函数
def parse_geometry(file_path: str) -> GeometryBridge:
    """便捷函数：解析并创建适配器"""
```

---

## 10. G3 质量门

- [ ] 支持格式：STL（首版）
- [ ] Watertight 检测准确率 ≥ 95%
- [ ] 特征提取完整性验证
- [ ] 单元测试覆盖率 ≥ 90%
- [ ] 黄金样板集通过率 = 100%
- [ ] 病态几何处理不崩溃

---

## 11. 与现有模块集成

```
┌─────────────────┐
│  CAD Parser     │
│  (Phase 3)      │
└────────┬────────┘
         │
         ├─→ GeometryBridge ─→ MeshBuilder (Phase 3)
         │
         └─→ GeometryHints ─→ Physics Planner (Phase 2)
```

---

## 12. 开发优先级（调整后）

| 级别 | 项目 | 状态 |
| --- | --- | --- |
| **P0** | GeometryBridge 适配器 | 📋 设计中 |
| **P0** | STL 格式支持 | 📋 设计中 |
| **P0** | Watertight 拓扑+体积检测 | 📋 设计中 |
| **P1** | 分级修复策略 | 📋 设计中 |
| **P1** | `trimesh` 集成 | 📋 设计中 |
| **P1** | 错误处理 + Gate 拦截 | 📋 设计中 |
| **P2** | BoundaryHint 标记 | 📋 设计中 |
| **P2** | GeometryHints 传递 | 📋 设计中 |
| **P3** | STEP 支持 | ⏰ Phase 3.2 |
| **P3** | 流式解析 | ⏰ Phase 3.x |

---

## 13. 待实现时机

**触发条件**（需全部满足）：
1. ✅ Phase 2 Knowledge Compiler 稳定
2. ✅ Phase 2 Autopilot 通过审查
3. ✅ 黄金样板集 replay 100% 通过
4. ✅ CorrectionSpec 通道就绪

**当前状态**：📋 **预研完成，等待 Phase 2 稳定后启动**
