# GSD (Guided Software Development) 规范 v2.0

> **生效日期**: 2026-04-08
> **状态**: 🧊 冻结 - Notion 驱动工作流

---

## 🎯 核心原则

### Single Source of Truth (SSOT)
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Notion 控制塔 = 唯一真相源 (SSOT)                              │
│        ↓                                                        │
│   Claude Code 读取状态 → 执行任务 → 写回更新                     │
│        ↓                                                        │
│   本地代码库 = 执行层 (不存储状态)                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**关键规则：**
- ✅ **任务状态**: 以 Notion 为准
- ✅ **任务分配**: 在 Notion 中创建
- ✅ **进度跟踪**: 实时同步到 Notion
- ❌ **禁止**: 本地任务状态与 Notion 不一致

---

## 📋 GSD 工作流

### 1. 任务创建 (Notion → Claude Code)

```
用户 在 Notion 创建任务
        ↓
Claude Code 读取任务列表
        ↓
认领任务 → 设置为 in_progress
        ↓
开始执行
```

### 2. 任务执行 (Claude Code)

```
执行中...
        ↓
遇到 CRITICAL? ──→ 🛑 暂停 + 创建审查请求
        ↓                    ↓
        否                用户 @Opus 4.6
        ↓                    ↓
    继续执行          粘贴 Opus 回复
        ↓                    ↓
        └────────────────────┘
                ↓
           完成任务
```

### 3. 任务完成 (Claude Code → Notion)

```
完成任务 → 测试通过
        ↓
更新 Notion 状态为 Succeeded
        ↓
Git commit → 自动同步
        ↓
Notion 记录完成时间
```

---

## 🎯 里程碑管控

### Phase 结构 (对齐 AI-CFD-001 需求规范)

```
Phase 1: Knowledge Compiler ✅ Pass
├── enum-based schema
├── FlowType, TimeTreatment, Compressibility
└── 测试: 53/53 通过

Phase 2: Execution Core + Pipeline 🔄 Executing
├── 2a: Execution Core ✅ Pass (6.5/10 Conditional)
│   ├── Physics Planner (53/53 测试)
│   ├── Mesh Builder (24/24 测试)
│   └── Solver Runner (30/30 测试)
├── 2b: Execution Completeness 📋 待实现
│   ├── CAD Parser
│   ├── Postprocess Runner
│   └── Result Validator
├── 2c: Governance & Learning 📋 待实现
│   ├── Correction Recorder
│   ├── Benchmark Replay
│   └── Knowledge Compiler (最小版)
└── 2d: Pipeline Assembly 📋 待实现
    └── E2E Pipeline Orchestrator

Phase 3: Analogical Orchestrator 📋 Draft
├── Similarity Retrieval
├── Analogy Decomposer
├── Candidate Plan Generator
├── Low-Cost Trial Runner
└── Job Scheduler
```

### Phase 对照表 (控制塔 ↔ AI-CFD-001)

| 控制塔 | AI-CFD-001 需求规范 | 状态 |
|--------|-------------------|------|
| Phase 1: Knowledge Compiler | A. Definitions Layer | ✅ Pass |
| Phase 2a: Execution Core | D. Execution Layer (子集) | ✅ Pass (6.5/10) |
| Phase 2b: Execution Completeness | D. Execution Layer (完整) | 📋 待实现 |
| Phase 2c: Governance & Learning | C+F. Teach + Governance | 📋 待实现 |
| Phase 2d: Pipeline Assembly | E. Integration Layer | 📋 待实现 |
| Phase 3: Analogical Orchestrator | B. Reasoning Layer | 📋 Draft |

### Phase Gates

每个 Phase 必须通过以下关卡才能进入下一阶段：

1. **Code Complete** - 所有核心功能实现
2. **Tests Pass** - 测试覆盖率 ≥ 80%
3. **Review Pass** - Opus 4.6 审查通过
4. **Documentation** - 文档完整

---

## 🛑 CRITICAL 触发条件

以下条件触发 **暂停 + Opus 4.6 审查**：

| 触发条件 | 行动 | Notion 同步 |
|----------|------|-------------|
| 架构变更 | 🛑 暂停 | 创建 Review: "架构审查" |
| 跨 Phase 调整 | 🛑 暂停 | 创建 Review: "Phase 边界审查" |
| 性能下降 >20% | 🛑 暂停 | 创建 Review: "性能审查" |
| 安全漏洞 | 🛑 暂停 | 创建 Review: "安全审查" |
| 测试失败 >5次 | 🛑 暂停 | 创建 Review: "根因分析" |
| 需求歧义 | 🛑 暂停 | 创建 Review: "需求澄清" |
| 任务估算 >4h | 🛑 暂停 | 创建 Review: "任务拆分" |

---

## 🔄 同步规则

### 自动同步 (Claude Code 负责)

| 事件 | 动作 | Notion 目标 |
|------|------|-------------|
| TaskCreate | 查询 Notion 任务 | 认领未分配任务 |
| TaskStart | 更新状态 → Executing | Tasks.Status |
| TaskComplete | 更新状态 → Succeeded | Tasks.Status |
| CRITICAL | 创建审查请求 | Reviews 数据库 |
| Git commit | 记录 SHA | Tasks 备注 |

### 同步命令

```bash
# 查看当前 Phase 状态
python3 .claude/notion/sync_v2.py phase-status

# 拉取待办任务
python3 .claude/notion/sync_v2.py pull-tasks

# 更新任务状态
python3 .claude/notion/sync_v2.py update-status --task-name "xxx" --status completed

# 创建审查请求
python3 .claude/notion/sync_v2.py create-review --review-type "xxx" --reason "xxx"
```

---

## 📁 文档结构

```
.claude/
├── MODEL_ROUTING.md      # 模型分工路由 (冻结)
├── GSD.md                # 本文件 (冻结)
├── CLAUDE.md             # 项目配置 (冻结)
├── notion/
│   ├── config.json       # Notion 配置
│   ├── sync_v2.py        # 同步脚本
│   └── milestones.py     # 里程碑查询
└── hooks/                # Git hooks
```

---

## 🔒 修改流程

1. 在 Notion 控制塔创建变更请求
2. @Opus 4.6 审查
3. 更新相应文档版本
4. 记录到 CHANGELOG.md

---

**版本历史**
- v2.1 (2026-04-08): 统一 Phase 定义，对齐 AI-CFD-001 需求规范 (REV-97A27E)
- v2.0 (2026-04-08): Notion 驱动工作流
- v1.0: 初始版本

