# CFD 图表标准化规则
**版本**: v1.0
**生成时间**: 2026-04-07
**来源**: Phase1 Knowledge Capture @ Codex task-mnodf1nn-7zjt06

---

## 1. Velocity Profile（速度剖面图）

### 1.1 轴定义
- **X轴**: `u/u_ref`（无量纲速度比）或 `v/v_ref`
- **Y轴**: `y/H`（无量纲垂直位置）或 `x/H`（无量纲水平位置）

### 1.2 渲染规范
- 数据点：scatter plot（圆形标记，直径 6-8pt）
- 基准数据（实验/解析解）：空心圆圈
- CFD数据：实心圆点
- 误差棒：显示在数据点上（error bar 长度 = 2σ 或实验不确定度）

### 1.3 零参考值问题
当 `|u_ref|` 接近零时，相对误差会出现假高值（>100%）。
**处理规则**:
1. 当 `|u_exp| < 0.01 * u_max` 时，切换为**绝对误差**显示
2. 在图表标题或注释中标注：`"@ near-zero reference (|u_exp| < 1%)"`
3. 在 Legend 中区分"相对误差"和"绝对误差"数据点

### 1.4 图例和标签
```
X轴标签: "u/u_ref" 或 "v/v_ref"
Y轴标签: "y/H" 或 "x/H"
图例位置: 右下角或右侧
字体: 10-12pt Arial
```

---

## 2. Pressure Contour（压力云图）

### 2.1 Colormap 标准
- **默认**: `viridis`（感知均匀，颜色盲友好）
- **替代**: `coolwarm`（适用于显示正负压力区域）

### 2.2 渲染规范
- 等值线间隔：等差或对数，根据数据范围选择
- 等值线标签：在等值线上标注数值
- **强制标注 colorbar**：显示物理量和单位
  ```
  Colorbar: "Pressure Coefficient Cp" 或 "Static Pressure [Pa]"
  ```

### 2.3 网格叠加
- 可在云图上叠加网格线（灰色，半透明，线宽 0.3-0.5pt）
- 边界线加粗显示（线宽 1.0pt，黑色）

---

## 3. Grid Convergence Index（GCI 网格收敛性）

### 3.1 网格级别定义
| 级别 | 定义 |
|------|------|
| Coarse | 基准网格（初始加密）|
| Medium | 粗网格1.5-2倍加密 |
| Fine | 中网格1.5-2倍加密（报告使用此级别）|

### 3.2 GCI 公式（Richardson外推）

```
GCI_{12} = |ε_{12}| / (r^p - 1) * 100%

其中:
ε_{12} = (φ_2 - φ_1) / φ_1    （网格2和网格1之间的解差异）
r = L_fine / L_coarse          （网格尺寸比，通常 r > 1）
p = 阶数（2阶格式通常取 p ≈ 2）
```

### 3.3 GCI 表格式

| Level | h (mm) | N (cells) | Max Skewness | φ (监控量) | GCI % |
|-------|--------|-----------|--------------|------------|-------|
| Coarse | h1 | N1 | s1 | φ1 | - |
| Medium | h2 | N2 | s2 | φ2 | GCI_{21} |
| Fine | h3 | N3 | s3 | φ3 | GCI_{32} |

**判定标准**: 当 GCI_{32} < 5% 时，认为网格无关

---

## 4. 共用渲染模板

```python
# Velocity Profile 模板（matplotlib）
plt.figure(figsize=(8, 6))
plt.scatter(y_H, u_uref_exp, marker='o', facecolors='none', edgecolors='blue', label='Experiment (Ghia1982)')
plt.scatter(y_H, u_uref_cfd, marker='o', facecolors='blue', edgecolors='blue', label='CFD (icoFoam)')
plt.errorbar(y_H, u_uref_cfd, yerr=error_bars, fmt='none', ecolor='gray', capsize=3)
plt.xlabel('y/H', fontsize=12)
plt.ylabel('u/u_ref', fontsize=12)
plt.legend(loc='lower right', fontsize=10)
plt.grid(True, alpha=0.3)
plt.title('Lid Cavity Centerline Velocity (Re=1000)', fontsize=12)
plt.tight_layout()
plt.savefig('velocity_profile.png', dpi=300)
```

---

*本规则为 Phase1 知识采集输出，需经 Opus 4.6 审查通过后正式纳入 ReportSpec*
