# 模型分工路由表 (FROZEN v1.0)

> **生效日期**: 2026-04-08
> **状态**: 🧊 冻结 - 任何变更需经过正式审查流程

---

## 🎯 指挥架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     用户交互层 (唯一入口)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Claude Code (MiniMax-2.7) ← 你与我对话的唯一窗口               │
│  - 掌握所有工具调用权限                                         │
│  - 掌握 Notion API 全权访问                                     │
│  - 负责任务分配、同步、进度跟踪                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ↓               ↓               ↓
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │  Skill层   │   │  Notion层  │   │  Opus 4.6 │
    │ (按需拉起)  │   │  (自动同步) │   │ (手动触发) │
    └───────────┘   └───────────┘   └───────────┘
    GLM-5.1 (glmext.py)   ← 并行开发协助
    Codex (plugin cmd)    ← 代码审查
    MiniMax-2.7 (Agent)   ← 辅助任务
```

---

## 📋 模型分工路由

### 模型能力映射

| 模型 | 主要能力 | 典型任务 | 调用方式 |
|------|----------|----------|----------|
| **GPT-5.4** | 最强推理 | 架构设计、复杂决策、根因分析 | Codex plugin → `/codex:rescue` |
| **GLM-5.1** | 平衡型 | 前端/后端开发、研究调研 | Skill `/glm-execute` |
| **MiniMax-2.7** | 快速响应 | 主对话调度、辅助验证、简单任务 | 直接执行 (我) |
| **Opus 4.6** | 架构审查 | 设计审查、关键点决策 | 🛑 Notion 手动触发 |

---

## 🔌 实际调用方式（Plugin/Skill/Command）

> ⚠️ **关键说明**: GLM-5.1 和 Codex 都通过 **Plugin/Skill/Command** 调用，不是 Agent tool 子类型。
> MiniMax-2.7 的 Agent tool 只接受 `sonnet/opus/haiku`，无法拉起 GLM 或 Codex。

### GLM-5.1 (智谱)

| 调用方式 | 命令/路径 |
|---------|----------|
| **Skill** | `/glm-execute` |
| **直接调用** | `python3 glmext.py "<prompt>"` |
| **环境变量** | `ZHIPU_API_KEY` (已配置) |
| **脚本位置** | `/Users/Zhuanz/Desktop/notion-cfd-harness/glmext.py` |
| **任务类型** | `--task TASK_DECOMPOSE` / `--task M1_3_WIZARD` / `--task VALIDATE_GATE` |
| **注意** | 额度耗尽报 1113 错误；不要用 Agent tool 拉起（不支持） |

### Codex (GPT-5.4)

| 调用方式 | 命令 |
|---------|------|
| **插件** | `codex@openai-codex` |
| **命令组** | `/codex:setup`, `/codex:status`, `/codex:review`, `/codex:rescue`, `/codex:result` |
| **直接调用** | `node ~/.claude/plugins/marketplaces/openai-codex/plugins/codex/scripts/codex-companion.mjs <command>` |
| **Agent 子类型** | `codex-rescue` (via Codex plugin agent, not Agent tool) |

### Opus 4.6

| 调用方式 | 命令 |
|---------|------|
| **方式** | 只能在 Notion 里手动 @ 触发 |
| **提示词** | Claude Code 提供模板 → 用户粘贴到 Notion → Opus 回复 → 粘贴回 Claude |

### MiniMax-2.7 (Claude Code Agent — 我)

| 调用方式 | 命令 |
|---------|------|
| **Agent tool** | `subagent_type: general-purpose, model: sonnet/opus/haiku` |
| **主会话** | 我就是 MiniMax-2.7，主对话入口 |
| **辅助任务** | 并行验证、grep搜索、文件读取等简单任务 |

### 任务类型 → 模型路由

```
                    ┌─────────────────────────────────────┐
                    │         任务分类决策树               │
                    └─────────────────────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ↓                  ↓                  ↓
            ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
            │  架构相关     │  │  核心实现     │  │  前端/后端    │
            └──────────────┘  └──────────────┘  └──────────────┘
                    │                  │                  │
                    ↓                  ↓                  ↓
            🛑 OPUS 4.6        Codex plugin        GLM-5.1
            (Notion手动)       /codex:rescue        /glm-execute


---

## 🛑 Opus 4.6 手动触发条件

以下场景 Claude Code **必须暂停**，请求用户手动触发 Opus 4.6：

| 触发条件 | 行动 | 输出格式 |
|----------|------|----------|
| 架构变更 | 🛑 暂停 + 输出提示词 | `CRITICAL: 架构变更需要审查` |
| 跨阶段调整 | 🛑 暂停 + 输出提示词 | `CRITICAL: 阶段边界调整需要审查` |
| 性能下降 >20% | 🛑 暂停 + 输出提示词 | `CRITICAL: 性能下降需要审查` |
| 安全漏洞 | 🛑 暂停 + 输出提示词 | `CRITICAL: 安全漏洞需要修复` |
| 测试失败 >5次 | 🛑 暂停 + 输出提示词 | `CRITICAL: 多次失败需要根因分析` |
| 需求歧义 | 🛑 暂停 + 输出提示词 | `CRITICAL: 需求不明确需要澄清` |
| 估算 >4小时 | 🛑 暂停 + 输出提示词 | `CRITICAL: 任务过大需要拆分` |

### Opus 4.6 提示词模板

```
请审查以下架构决策/设计方案：

【背景】
- 项目: notion-cfd-harness (AI-CFD 知识编译器)
- 当前阶段: Phase {X}
- 涉及组件: {组件名}

【待审查内容】
{详细描述}

【相关问题】
1. 这个决策是否符合整体架构？
2. 是否有更好的替代方案？
3. 是否有遗漏的风险点？
4. 建议的下一步是什么？

【约束】
- 项目: notion-cfd-harness (AI-CFD Knowledge Harness)
- 当前里程碑: v1.6.0 (ParaView Web → Trame Migration)
- 已完成里程碑: M1, v1.1.0, v1.2.0, v1.3.0, v1.4.0, v1.5.0
- 模型分工: MiniMax-2.7(调度) + GLM-5.1(/glm-execute) + Codex(/codex:*) + Opus 4.6(Notion手动)
```

---

## 🔄 Claude Code ↔ Notion 同步流程

### 自动同步 (Claude Code 负责)

| 事件 | 同步动作 | Notion 目标 |
|------|----------|-------------|
| TaskCreate | 创建任务记录 | Tasks 数据库 |
| TaskUpdate (completed) | 更新状态为 Succeeded | Tasks 数据库 |
| 遇到 CRITICAL | 创建审查请求 | Reviews 数据库 |
| Git commit | 记录变更 | Tasks 备注 |

### 手动触发 (用户负责)

1. **在 Notion 中 @Opus 4.6**
2. **粘贴 Claude Code 提供的提示词**
3. **等待 Opus 4.6 回复**
4. **将回复粘贴回 Claude Code**
5. **Claude Code 继续执行**

---

## 📁 正式文档位置

| 文档 | 路径 | 状态 |
|------|------|------|
| 本路由表 | `.claude/MODEL_ROUTING.md` | 🧊 冻结 |
| GSD 规范 | `.claude/GSD.md` | 🧊 冻结 |
| 项目配置 | `.claude/CLAUDE.md` | 🧊 冻结 |
| Notion 配置 | `.claude/notion/config.json` | 活跃 |
| 控制塔项目 | `https://notion.so/33cc68942bed8184a94eed5169156638` | 活跃 |

---

## 🔒 修改流程

1. 在 Notion 控制塔创建变更请求
2. @Opus 4.6 审查变更影响
3. 审查通过后更新本文档版本号
4. 在 `.claude/CHANGELOG.md` 记录变更

---

**版本历史**
- v1.0 (2026-04-08): 初始冻结版本
- v1.1 (2026-04-11): 更新调用方式，补充 Plugin/Skill/Command 实际路径

