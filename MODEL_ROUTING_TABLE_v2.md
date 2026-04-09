# 模型路由表 v2.0
**⚠️ 已过时 - 请使用 MODEL_ROUTING_TABLE_v3.md**

**Well-Harness AI-CFD 项目专用**
**更新时间**: 2026-04-08
**状态**: ⚠️ **已被 v3.0 替代 - 模型分工已重新设计**
**新版本**: [MODEL_ROUTING_TABLE_v3.md](./MODEL_ROUTING_TABLE_v3.md)

---

## 一、核心模型配置

### 1.1 当前工作环境

| 组件 | 模型 | 说明 |
|------|------|------|
| **Claude Code 宿主** | GLM-5.1 (智谱AI) | 主要工作模型，在Claude Code环境下运行 |
| **任务分解/中文NLP** | GLM-5.1 | 通过 `glmext.py` 调用 |
| **备选执行模型** | MiniMax-M2.7 | 通过 `minimix.py` 调用 |
| **高级代码实现** | Codex (GPT-5.4) | 通过 skill 机制调用（需配置） |
| **架构审查/验收** | **Opus 4.6** | ❌ 不直接调用 — 由用户手动在Notion AI中交互 |

### 1.2 模型调用方式

| 模型 | 调用方式 | 配置文件 |
|------|---------|---------|
| GLM-5.1 | `python3 glmext.py "<prompt>"` | 环境变量 `ZHIPU_API_KEY` 或 `~/.glm_key` |
| MiniMax-M2.7 | `python3 minimix.py "<prompt>"` | 环境变量 `MINIMAX_API_KEY` 或 `~/.minimax_key` |
| Codex (GPT-5.4) | Skill: `codex:rescue` | 需在Claude Code配置openai-codex插件 |
| Opus 4.6 | 用户手动在Notion AI中交互 | 见 `notion_opus_prompts.md` |

---

## 二、任务-模型映射表

### 2.1 Phase 1: 知识捕获（当前阶段）

| 任务类型 | Primary Model | Fallback | Code Review |
|----------|--------------|----------|-------------|
| Schema定义 | GLM-5.1 | MiniMax-M2.7 | 跳过 |
| Module 1: Result Parser | GLM-5.1 | MiniMax-M2.7 | GLM-5.1 |
| Module 2: Skeleton Generator | GLM-5.1 | MiniMax-M2.7 | GLM-5.1 |
| **Module 3: Teach Mode Engine** | GLM-5.1 | MiniMax-M2.7 | **Codex CR** |
| Module 4: ReportSpec Manager | GLM-5.1 | MiniMax-M2.7 | Codex CR |
| Module 5: Phase 1 Gates | GLM-5.1 | MiniMax-M2.7 | **Opus 4.6 审查** |
| 测试编写 | GLM-5.1 | MiniMax-M2.7 | 跳过 |

### 2.2 Phase 2: Knowledge Compiler

| 任务类型 | Primary Model | Fallback | Code Review |
|----------|--------------|----------|-------------|
| Compiler Core | Codex (GPT-5.4) | GLM-5.1 | Codex CR |
| Normalization | GLM-5.1 | MiniMax-M2.7 | Codex CR |
| Diff Engine | Codex (GPT-5.4) | GLM-5.1 | Opus 审查 |
| Publish Contract | Codex (GPT-5.4) | GLM-5.1 | Opus 审查 |

### 2.3 Phase 3: Orchestrator

| 任务类型 | Primary Model | Fallback | Code Review |
|----------|--------------|----------|-------------|
| Solver Runner | Codex (GPT-5.4) | GLM-5.1 | Codex CR |
| Mesh Builder | Codex (GPT-5.4) | MiniMax-M2.7 | Codex CR |
| Physics Planner | **Opus 4.6** | Codex (GPT-5.4) | Opus 自审 |
| CAD Parser | Codex (GPT-5.4) | GLM-5.1 | Codex CR |

### 2.4 Phase 4: Memory Network

| 任务类型 | Primary Model | Fallback | Code Review |
|----------|--------------|----------|-------------|
| Versioned Registry | Codex (GPT-5.4) | GLM-5.1 | Codex CR |
| Memory Node | GLM-5.1 | MiniMax-M2.7 | Codex CR |
| Governance Engine | Codex (GPT-5.4) | GLM-5.1 | **Opus 审查** |
| Notion Memory Events | GLM-5.1 | MiniMax-M2.7 | 跳过 |

### 2.5 Phase 5: Performance & Security

| 任务类型 | Primary Model | Fallback | Code Review |
|----------|--------------|----------|-------------|
| Connection Pool | Codex (GPT-5.4) | GLM-5.1 | Codex CR |
| Auth | GLM-5.1 | MiniMax-M2.7 | **Opus 审查** |
| Backup & Recovery | GLM-5.1 | MiniMax-M2.7 | Codex CR |

---

## 三、Code Review 触发规则

### 3.1 必须 Code Review 的场景

| 场景 | 审查模型 | 说明 |
|------|---------|------|
| Phase 1 Module 3 完成后 | Codex CR | 核心模块 |
| Phase 1 Module 4 完成后 | Codex CR | 管理器模块 |
| 任意 Phase 完成后 | Codex CR | 阶段性审查 |
| Gate 实现任务 | Codex CR + Opus | 关键质量控制 |

### 3.2 可跳过 Code Review 的场景

| 场景 | 原因 |
|------|------|
| 纯Schema定义 | 数据结构，无复杂逻辑 |
| 测试文件 | 自验证 |
| 文档更新 | 非代码 |

### 3.3 Code Review 调用方式

```bash
# 通过skill触发Codex Code Review
node ~/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs review \
  --base HEAD~1 \
  --scope working-tree \
  --focus "实现Module 3，注意知识层管理"
```

---

## 四、Opus 4.6 审查流程（手动）

### 4.1 需要Opus审查的场景

| 场景 | 触发方式 | 审查内容 |
|------|---------|---------|
| Phase 1 完成 | 用户手动@Notion AI | 架构合规性、知识模型正确性 |
| Gate 实现 | 用户手动@Notion AI | Gate逻辑完整性 |
| 架构变更 | 用户手动@Notion AI | 影响评估、风险分析 |
| 任务拆解 | 用户手动@Notion AI | 任务完整性、依赖正确性 |

### 4.2 Notion AI 触发模板

见 `notion_opus_prompts.md`，包含：
- G0 Gate 审查
- G1-G6 Gate 审查
- 架构审查
- 任务拆解审查

### 4.3 审查结果处理

Opus 4.6 返回标准JSON格式，包含：
- `pass`: true/false
- `checks`: 检查项列表
- `recommendations`: 改进建议
- `next_action`: 下一步操作

---

## 五、模型能力对比

| 能力 | GLM-5.1 | MiniMax-M2.7 | Codex (GPT-5.4) | Opus 4.6 |
|------|---------|-------------|-----------------|----------|
| 中文理解 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 代码实现 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 架构设计 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 任务分解 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Gate审查 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 调用方式 | glmext.py | minimix.py | skill | Notion AI |
| 响应速度 | 快 | 快 | 中 | 慢（手动） |

---

## 六、过时内容清理

### 6.1 已废弃的文档

| 文档 | 状态 | 替代为 |
|------|------|--------|
| `model_rules_v1.2_with_codex_cr.md` | ⚠️ 部分过时 | 本文档 |
| M1_MILESTONE_COMPLETE.md 第4节 | ⚠️ 已过时 | 本文档第2节 |

### 6.2 不再使用的模型

| 模型 | 原因 |
|------|------|
| Claude Sonnet 3.5/4 | 已迁移到Opus 4.6 |
| GPT-4 | 已迁移到Codex (GPT-5.4) |
| 直接的OpenAI API调用 | 已统一通过skill或GLM/MiniMax |

---

## 七、使用流程

### 7.1 标准开发流程

```
用户需求
  ↓
GLM-5.1 (Claude Code环境) → 实现代码
  ↓
Codex CR (可选) → 代码审查
  ↓
测试验证
  ↓
阶段完成 → 用户手动 @Notion AI (Opus 4.6) → 架构验收
  ↓
下一阶段
```

### 7.2 遇到问题时的流程

```
遇到阻塞
  ↓
评估问题类型:
  - 代码问题 → GLM-5.1 + Codex CR
  - 架构问题 → 用户手动 @Notion AI (Opus 4.6)
  - 任务拆解问题 → GLM-5.1 任务分解
  - Gate验证问题 → 用户手动 @Notion AI (Opus 4.6)
```

---

## 八、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.0 | 2026-04-08 | 重新组织模型路由，明确GLM-5.1为主要模型 |
| v1.2 | 2026-04-07 | 增加Codex Code Review要求 |
| v1.1 | - | 加入fail-stop规则 |
| v1.0 | - | 初始版本 |

---

**维护者**: Well-Harness Team
**更新者**: GLM-5.1 (Claude Code环境)
**审查者**: 待 @Notion AI (Opus 4.6)
