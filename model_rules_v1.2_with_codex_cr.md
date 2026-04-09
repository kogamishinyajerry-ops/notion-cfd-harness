# 模型调用规范 v1.2 - 增加 Code Review 审查
## ⚠️ 已过时 - 请参考 MODEL_ROUTING_TABLE_v2.md
## 本文档保留仅作为历史参考

---

## 一、核心原则（不可违背）

### 1.1 基础原则（保留 v1.1）
- 模型即责任边界：每个任务类型绑定唯一执行模型
- 失败即阻塞：模型调用失败时，执行必须立即停止，不降级、不重试、不跳过
- 未验证不执行：在不知道目标模型是否可用的前提下，禁止自行决定降级

### 1.2 新增：质量优先原则
- **代码必须经过审查后才能提交**：所有代码变更必须在提交前通过 Code Review
- **Codex Code Review 作为质量门**：在每个实现任务完成后、Git 提交前触发
- **审查不通过阻塞提交**：审查有建议但通过代码仍可提交，但需在 Notion 标记建议
- **严重问题必须修复**：审查为 BLOCKED 时必须修复代码后重新审查

---

## 二、模型分工表（v1.2 更新）

| 任务类型 | 执行模型 | 降级规则 | Code Review |
|----------|----------|----------|-------------|
| **P1 知识捕获** | Codex (GPT-5.4) | 无降级 | Codex CR |
| **P2 Knowledge Compiler** | Codex (GPT-5.4) | 无降级 | Codex CR |
| **P3 Orchestrator 实现** | Codex (GPT-5.4) | 无降级 | Codex CR |
| **G3-G6 Gate** | Codex (GPT-5.4) | 无降级 | Codex CR + Opus 审查 |
| **架构审查** | Opus 4.6 | 禁止降级 | N/A |
| **任务拆解审查** | Opus 4.6 | 禁止降级 | N/A |
| **Gate 最终审批** | 人工 | 禁止降级 | N/A |
| **v1 架构迁移** | Codex (GPT-5.4) | 无降级 | Opus 审查 |
| **文档更新** | Codex (GPT-5.4) | 无降级 | 跳过 CR |

---

## 三、Codex Code Review 触发规则

### 3.1 必须触发 Code Review 的场景

| 触发时机 | 审查范围 | 备注 |
|----------|----------|------|
| **实现任务完成** | 本次任务变更的文件 | 每个实现任务完成后 |
| **批量提交前** | 所有待提交文件 | 在 git commit 前触发 |
| **Gate 任务前** | 所有相关产物 | G3-G6 gate 前触发 |
| **架构模块完成** | 整个模块 | Phase 完成时触发 |

### 3.2 Code Review 审查项

**基础检查**：
- 代码符合 Python PEP8 规范
- 变量命名清晰、无误导性缩写
- 函数有文档字符串（docstring）
- 关键逻辑有注释说明

**架构检查**：
- 与现有架构风格一致
- 复用已有接口和基类
- 依赖关系清晰，无循环依赖

**集成检查**：
- 正确引用 Phase2 知识单元
- 使用 Phase2 可执行资产（不重复实现）
- 遵循 publish_contract.md 契约

**安全性检查**：
- 无 SQL 注入、XSS 等安全漏洞
- 无硬编码敏感信息
- 输入验证完善

---

## 四、Codex Code Review 调用规范

### 4.1 触发命令

```bash
# 基础代码审查
node ~/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs review \
  --base <base_commit> \
  --scope working-tree \
  --background

# 带说明的审查（推荐）
node ~/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs review \
  --base <base_commit> \
  --scope working-tree \
  --focus "实现X功能，注意与Phase2集成" \
  --background
```

### 4.2 审查结果处理

| 审查结果 | 动作 |
|----------|------|
| **PASS** | 继续执行，可提交 |
| **CONDITIONAL PASS** | 查看建议，决定是否修改 |
| **BLOCKED** | 必须修复后重新审查 |
| **ERROR** | 检查配置，重试 |

### 4.3 审查记录到 Notion

审查完成后，将结果记录到 Notion Reviews DB：
- Review ID: `CODE-REV-<task_id>-<timestamp>`
- Review Type: `CodeReview`
- Reviewer Model: `Codex (GPT-5.4)`
- Decision: `PASS/CONDITIONAL_PASS/BLOCKED`
- Required Fixes: 审查发现的问题
- Linked Task: 关联的任务 ID

---

## 五、更新后的执行流程

### 5.1 实现任务执行流程（含 Code Review）

```
1. 用户请求实现任务 X
   ↓
2. Claude Code 用 Codex 执行实现
   ↓
3. 实现完成 → 触发 Codex Code Review
   ↓
4. 等待 Codex 审查结果
   ↓
5a. PASS → 继续执行步骤 6
5b. CONDITIONAL PASS → 查看建议，决定是否修改
5c. BLOCKED → 修复代码，重新触发 Code Review
   ↓
6. 创建 Git commit
   ↓
7. 推送 GitHub
   ↓
8. 更新 Notion 任务状态为 Completed
```

### 5.2 批量提交流程

```
1. 多个任务完成
   ↓
2. 对所有变更文件触发 Codex Code Review
   ↓
3. 如通过 → 批量 git commit + push
   ↓
4. 如 BLOCKED → 逐个修复，重新审查
```

---

## 六、Code Review 时机点总结

| 阶段 | Code Review 触发 | 必须？ |
|------|-----------------|-------|
| 每个文件创建/编辑后 | 对单个文件 | ✅ 推荐 |
| 每个子任务完成 | 对该任务所有文件 | ✅ 必须 |
| Gate 任务执行前 | 对所有相关产物 | ✅ 必须 |
| Git commit 前 | 对所有待提交文件 | ✅ 必须 |

---

## 七、Codex Code Review 参数配置

```json
{
  "review_scope": "working-tree",
  "base_comparison": "HEAD~1",
  "focus_areas": [
    "PEP8 compliance",
    "Type annotations",
    "Docstrings",
    "Integration with Phase2",
    "Security vulnerabilities"
  ],
  "severity_levels": {
    "blocking": ["security_vulnerability", "circular_dependency"],
    "warning": ["naming_convention", "missing_docs"],
    "info": ["style", "optimization"]
  }
}
```

---

## 八、与现有流程的集成

### 8.1 与 Phase2 集成
- Phase2 的 publish_contract.md 现在包含 Code Review 要求
- F-P2-005 (diff_engine.py) 实现已通过 Codex Code Review

### 8.2 与 Opus 审查集成
- Codex Code Review 专注于代码质量
- Opus 审查专注于架构和 Gate 决策
- 两者互补：Codex Code Review 做代码质量把关，Opus 做系统设计把关

---

*版本历史*:
- v1.0: 初始版本
- v1.1: 加入 fail-stop 规则，禁止降级
- v1.2: 加入 Codex Code Review 质量门（本文档）
