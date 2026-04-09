# Phase1-ReportSpec v1.1
# CFD 后处理报告规范（正式版）
**版本**: v1.1
**状态**: Active（ Superseded Phase1-ReportSpec-Candidate ）
**生成时间**: 2026-04-07
**来源**: Case1 Lid-Cavity (Ghia1982) + BENCH-04 Circular Cylinder Wake (Williamson 1996)
**Executor**: Codex (GPT-5.4) @ task-mnodf1nn-7zjt06

---

## 1. 标准章节结构

每个CFD后处理报告必须包含以下5个固定章节：

### 1.1 Geometry（几何描述）
- 几何尺寸（单位：m 或 mm，需明确）
- 坐标系定义（原点位置、轴方向）
- 边界条件类型（wall/inlet/outlet/symmetry）
- 关键几何特征标注

### 1.2 Mesh（网格信息）
- 网格生成工具和算法
- 网格级别定义：
  - **Coarse**: 基准网格，用于初算
  - **Medium**: 加密一倍，用于收敛判断
  - **Fine**: 再加密一倍，用于最终报告
- 网格质量指标：element count, max skewness, max aspect ratio
- 网格无关性验证结果（GCI 表）

### 1.3 Solver Settings（求解器配置）
- 求解器名称和版本（如 icoFoam, simpleFoam, k-omega SST）
- 湍流模型（如 k-epsilon, k-omega SST）
- 收敛准则（残差阈值、监控物理量）
- 时间步长设置（瞬态求解器）

### 1.3.1 Boundary Conditions（边界条件）
- 边界条件完整列表（每面的物理类型：wall/inlet/outlet/symmetry等）
- 进口速度/压力/温度等参数值
- 出口边界条件设置
- 对称面/周期性边界说明

### 1.4 Results（结果）
- 关键监控物理量的收敛历史
- 速度/压力/温度等场可视化（云图、矢量图）
- 关键性能指标数值（升力/阻力/力矩等）

### 1.5 Validation（验证）
- 与实验数据或解析解的定量对比
- 误差指标计算（RMSE / L1 / L2）
- 关键数据点对照表
- 图表标准化渲染

---

## 2. 数据格式规范

### 2.1 无量纲化方法
- **速度**: `u* = u / u_ref`，其中 `u_ref` 为参考速度（通常为进口速度或自由流速度）
- **坐标**: `x* = x / L`, `y* = y / H`（L=特征长度，H=特征高度）
- **压力系数**: `Cp = (p - p_ref) / (0.5 * rho * u_ref^2)`
- **推力系数**: `Ct = T / (0.5 * rho * u_ref^2 * A)`

### 2.2 误差计算公式

**L1 范数（平均绝对误差）**:
```
L1 = (1/N) * Σ |u_cfd - u_exp|
```

**L2 范数（均方根误差 RMSE）**:
```
L2 = sqrt((1/N) * Σ (u_cfd - u_exp)^2)
```

**相对误差（注意零参考值问题）**:
```
当 |u_exp| >= 阈值（|u_exp| >= 0.01 * u_max）时：
    ε_rel = |u_cfd - u_exp| / |u_exp| * 100%

当 |u_exp| < 阈值（|u_exp| < 0.01 * u_max）时：
    退化为绝对误差，标注 "@ near-zero reference"
    ε_abs = |u_cfd - u_exp|
```

---

## 3. Case1 关键数据（Ghia1982 Lid Cavity）

| 参数 | 值 |
|------|-----|
| 几何 | 1m x 1m 正方形腔体 |
| 雷诺数 | Re = 1000 |
| 网格 | 129 x 129（Fine level）|
| 求解器 | icoFoam（瞬态层流）|
| 顶盖速度 | u = 1 m/s |
| 主涡心位置 | (0.5313, 0.5625) |
| 主涡量值 | ψ = -0.117929 |

### 中心线速度验证数据点

| y/H | u*/u_ref (Ghia1982) | u*/u_ref (CFD) | 相对误差 |
|-----|---------------------|-----------------|---------|
| 1.0000 | 1.00000 | 1.01093 | 1.09% |
| 0.7266 | 0.40225 | 0.41522 | 3.22% |
| 0.2969 | -0.10272 | -0.10380 | 1.05% |
| 0.1719 | -0.05821 | -0.05910 | 1.53% |

### 涡核参数
- Primary vortex center: (0.5313, 0.5625)
- Primary vortex strength: ψ_min = -0.117929
- Secondary corner vortices: 在4个角部存在（强度较弱）

---

## 4. BENCH-04 关键数据（Circular Cylinder Wake Williamson 1996）

| 参数 | 值 |
|------|-----|
| 几何 | 2D Circular Cylinder |
| 参考尺度 | Cylinder diameter D |
| 计算域 | 22D x 8D, cylinder center 2D from inlet |
| 雷诺数 | Re = 100 |
| 求解器 | icoFoam（瞬态层流） |
| 最终网格 | ~100,000 cells with wake refinement |

### 关键验证指标

| 指标 | 值 |
|------|-----|
| Strouhal number | 0.164 |
| Mean drag coefficient | 1.34 |
| 目标流动结构 | Karman vortex street |

> **物理解释**：Re=100 的圆柱绕流应形成稳定的卡门涡街。报告验证的核心不是单点压力，而是瞬态脱落频率（Strouhal）与平均阻力系数是否同时落在文献容差范围内。

### 验证容差

| 指标 | 阈值 |
|------|------|
| Strouhal error | <= 8% |
| Mean drag error | <= 5% |

### 推荐观测窗口

| 项目 | 要求 |
|------|------|
| 进入周期态后采样 | 至少覆盖多个 shedding cycles |
| 输出图表 | Wake visualization + force/statistics summary |
| 关键说明 | 必须明确说明是否已形成 Karman vortex street |

---

## 5. 已知数据缺口

> **诚实性声明**: BENCH-04 seed 只提供 Strouhal number、mean drag coefficient 和 wake visualization 目标。报告中不得虚构完整升阻力时序或更高分辨率的尾迹统计数据。

---

*本 Spec 为候选版本，需经 Opus 4.6 审查通过后正式生效*
