# Phase 6 Plan — Operational Validation & Reliability Hardening

**版本**: 0.3 (DRAFT)
**日期**: 2026-04-09
**状态**: 待 Opus 4.6 审查
**前置条件**: REV-PROJECT-001 Approved

---

## 一、目标

**深度确保全流程 AI-CFD 半自动仿真工具能够按照规划的需求工作。**

Phase 6 不是加安全层，而是确保 Phase 1-5 构建的整个系统在真实工程场景下端到端可运行、可信赖、有反馈闭环。

---

## 二、核心问题

当前 Phase 1-5 的验收基于**单元测试**（1,736 个全通过）。但：

| 问题 | 说明 |
|------|------|
| **端到端真实案例缺失** | 没有从 NL 输入 → 完整 pipeline → 真实结果的完整演示 |
| **反馈闭环未验证** | CorrectionRecorder 记录的修正是否真的能改进 Analogy Engine？|
| **Benchmark 演示不足** | Ghia 1982 / NACA VAWT 结果是否真的验证了系统能力？|
| **冷启动案例库薄弱** | 仅 30 个白名单案例，类比推理覆盖率存疑 |
| **Notion SSOT 真实性** | 控制塔状态是否真实反映了代码状态？|

---

## 三、待实现项

### 6.1 端到端案例演示（E2E Demo）

**目标**: 至少 3 个完整真实案例，跑通 NL → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 完整链路。

**候选案例**:

| 案例 | 来源 | 验证方式 |
|------|------|----------|
| Lid-Driven Cavity (Ghia 1982) | Phase 2 Benchmark | 速度剖面、涡量中心误差 < 5% |
| NACA VAWT | Phase 2 Benchmark | Cp_tsr 曲线误差 < 10% |
| Backward-Facing Step | Phase 1 Gold Standard | 重新附着长度误差 < 5% |

**实现**:
- 新增 `knowledge_compiler/demos/` 目录
- 每个案例一个 Python 文件，包含完整 NL 输入和预期结果
- 自动验证系统输出与 Gold Standard 的偏差

**影响**: 新增 `knowledge_compiler/demos/` 模块

---

### 6.2 Correction 反馈闭环验证

**目标**: 验证 CorrectionRecorder → Analogy Engine 的反馈链路是否有效。

**现状**: CorrectionRecorder 记录修正，AnalogyFailureHandler 处理失败回退。但没有验证这个闭环是否真的改进了下次推理质量。

**实现**:
- 评估现有 CorrectionRecord 的结构和质量
- 验证失败场景中 correction 能否被 AnalogyEngine 正确消费
- 如果闭环有问题，修复相关组件

**影响**: 完善 `phase2c/correction_recorder.py` 和 `phase3/` 相关代码

---

### 6.3 冷启动白名单扩展

**目标**: 将 30 个白名单案例扩展到 50+ 个，覆盖更多工程场景。

**来源**:
- 现有 Gold Standards (4 个完整 + 3 个待测试)
- 内部测试案例
- 文献参考案例

**白名单价值**: 当 Analogy Engine 遇到新问题时，冷启动白名单提供可信赖的基础案例，避免系统完全依赖不成熟的类比推理。

**实现**:
- 补充 Gold Standards 测试覆盖（inviscid wedge/plate/bump）
- 整理案例元数据（几何类型、流态、雷诺数范围等）
- 验证白名单覆盖度

---

### 6.4 Notion SSOT 真实性核对

**目标**: 确保 Notion 控制塔与代码库真实状态一致。

**检查项**:
- [ ] Notion 中所有 Phase 状态是否为 "Pass"
- [ ] 没有过时/错误的 Task 条目
- [ ] Reviews DB 中的决策与代码实际情况一致
- [ ] 项目页面显示 "Project Accepted"

---

## 四、验收标准

- [ ] 至少 3 个端到端真实案例可运行并通过验证
- [ ] Correction 反馈闭环可追踪并验证其有效性
- [ ] 冷启动白名单 ≥ 50 个案例
- [ ] Notion SSOT 状态与代码库 100% 一致
- [ ] 所有 Phase 6 测试通过
- [ ] Opus 4.6 运营验收通过

---

## 五、模型分工

| 任务 | Primary | 说明 |
|------|----------|------|
| E2E Demo 实现 | Codex | 真实案例集成 |
| Correction 闭环验证 | Codex | 链路验证 |
| 白名单扩展 | GLM-5.1 | 案例整理 |
| SSOT 核对 | MiniMax-M2.7 | 一致性检查 |
| 审查 | Opus 4.6 | 运营验收 |

---

## 六、风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 反馈闭环无效 | 高 | 如果无效，需修复 AnalogyFailureHandler |
| Benchmark 演示失败 | 中 | 先在小案例验证，再扩展 |
| SSOT 不一致 | 低 | 发现即修复 |

---

**请 Opus 4.6 审查此 Phase 6 规划草案。**

审查后如同意方向，将开始 6.4 (SSOT 核对) 作为第一步（风险最低）。
