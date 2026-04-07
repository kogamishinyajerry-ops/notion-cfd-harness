# Phase1-ReportSpec-Candidate
# CFD 后处理报告规范候选版
**版本**: v1.0 Candidate
**生成时间**: 2026-04-07
**来源**: Case1 Lid-Cavity (Ghia1982) + Case2 NACA Airfoil (Thomas&Loutun 2021)
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
- 边界条件完整列表
- 收敛准则（残差阈值、监控物理量）
- 时间步长设置（瞬态求解器）

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
当 |u_exp| < 阈值时，使用绝对误差并在图表中标注"@ near-zero reference"
相对误差 = |u_cfd - u_exp| / max(|u_exp|, 阈值) * 100%
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

## 4. Case2 关键数据（NACA Airfoil Thomas&Loutun 2021）

| 参数 | 值 |
|------|-----|
| 进口速度 | 9 m/s |
| TSR 范围 | 2.0 ~ 8.2 |
| 湍流模型 | k-omega SST |
| 最终网格 | 968,060 cells |
| 翼型 | NACA0015, NACA0018, NACA0021, NACA2421 |

### NACA0021 验证数据

| 指标 | 值 |
|------|-----|
| 平均误差 | 3.4488% |
| 最大误差 | 10.7875% |

### 峰值性能

| 翼型 | Cp_max | @ TSR |
|------|--------|-------|
| NACA0018 | 0.296 | 5.25 |
| NACA0015 | 0.292 | 6.00 |
| NACA2421 | 0.269 | 5.25 |

### 网格独立性表

| Level | Cell Size | Elements | Max Skewness | Torque | Error |
|-------|-----------|----------|--------------|--------|-------|
| Coarse | 粗 | N1 | s1 | T1 | e1% |
| Medium | 中 | N2 | s2 | T2 | e2% |
| Fine | 细 | N3 | s3 | T3 | e3% |

---

## 5. 已知数据缺口

> **诚实性声明**: Case2 PDF 不包含 CL/CD 极曲线数据，只有 Cp/Ct vs TSR。报告中不得虚构 CL/CD 数据。

---

*本 Spec 为候选版本，需经 Opus 4.6 审查通过后正式生效*
