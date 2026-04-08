# Notion 同步问题诊断与解决方案

## 当前状态（2026-04-08）

### ✅ 已就绪
- Notion API 配置完成（token 有效）
- post-commit hook 已安装
- 同步脚本已就绪

### ❌ 阻塞问题
**Notion 数据库未与集成共享**

```
API Error: 404 - Could not find database with ID
"Make sure the relevant pages and databases are shared with your integration"
```

---

## 解决步骤

### 1. 在 Notion 中共享数据库

1. 打开 AI-CFD-001 工作区
2. 找到以下数据库：
   - **Tasks 数据库** (`33bc6894-2bed-8196-8e2c-d1d66e631c31`)
   - **Reviews 数据库** (`33bc6894-2bed-81fb-a911-c4f0798ce1cf`)
   - **Projects 数据库** (`33bc6894-2bed-8153-a775-d5c821fa34a1`)

3. 对每个数据库：
   - 点击右上角 `...` → `Add connections`
   - 选择 **"Claude Dev Workflow"** 集成
   - 确认授权

### 2. 验证共享

```bash
python3 .claude/notion/sync.py status
```

应显示可用任务状态列表。

### 3. 测试创建任务

```bash
python3 .claude/notion/sync.py create-task --task-id "TEST-001" --task-type "Test"
```

---

## 同步链路设计（修复后）

```
┌─────────────────────────────────────────────────────────────┐
│                    自动同步流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  代码变更 (TaskCreate/TaskUpdate)                          │
│        ↓                                                    │
│  [手动] python3 .claude/notion/full_sync.py --push         │
│        ↓                                                    │
│  Notion Tasks 数据库                                        │
│                                                             │
│  Git commits                                               │
│        ↓                                                    │
│  [自动] .git/hooks/post-commit → sync.py                    │
│        ↓                                                    │
│  Notion 更新任务状态                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 当前本地任务状态（未同步到 Notion）

| 任务 ID | 状态 | 说明 |
|---------|------|------|
| #65 | pending | P3-P1: CAD Parser (Codex) - 已延后 |
| #66 | pending | P3-P1: Job Scheduler (GLM-5.1) |
| #67 | completed | P3-P0: Mesh Builder (Codex) ✅ 24/24 测试 |
| #68 | completed | P3-P0: Physics Planner (Opus 4.6) ✅ 53/53 测试 |
| #69 | completed | P3-P0: Solver Runner (Codex) ✅ 30/30 测试 |
| #70 | completed | 重构 Physics Planner 设计 ✅ |
| #71 | pending | 更新 Phase 2 开发优先级 |
| #81 | **completed** | **Phase 2c T1: Correction Recorder** ✅ 23/23 测试 (2026-04-08) |
| #82 | **completed** | **Phase 2c T2: Benchmark Replay Engine** ✅ 30/30 测试 (2026-04-08) |

---

## 下一步行动

1. **你**：在 Notion 中共享数据库给集成
2. **验证**：运行 `python3 .claude/notion/full_sync.py --check`
3. **测试**：创建测试任务验证连接
4. **我**：后续每次 TaskCreate/TaskUpdate 后手动同步，或定期执行 `--push`

---

## 备选方案（如 Notion 持续不可用）

如果 Notion 共享问题无法解决，可以：

1. **本地 JSON 任务跟踪**：`tasks/tasks.json`
2. **Git commits 作为任务记录**：commit 消息包含任务 ID
3. **Markdown 文档同步**：手动维护 `TASKS.md`

但当前最佳方案仍然是修复 Notion 共享问题。
