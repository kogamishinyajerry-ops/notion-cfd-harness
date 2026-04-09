# GSD Development Configuration

> **GSD = Guided Software Development**
> 文档驱动 + 质量门控 + 快速迭代 + 自动化优先 + 关键点人工介入

## 核心原则

### 1. 文档先行 (Doc-First)
- 新功能必须先有设计文档（Notion）
- API 变更必须先更新 API 文档
- 设计文档需要 @Opus 4.6 审查后才能实施

### 2. 质量门控 (Quality Gates)
- 代码必须通过所有 gates 才能合并
- 测试覆盖率低于 80% 不能合并
- 安全漏洞必须立即修复

### 3. 快速迭代 (Quick Iteration)
- 小步提交，每个 commit 可运行
- 每个功能分支 < 3 天
- 允许临时技术债，但必须标注 `#tech-debt`

### 4. 自动化优先 (Automation-First)
- 重复 > 2 次的任务必须自动化
- 所有检查通过 hooks 自动执行
- 减少手动审查点

### 5. 关键点介入 (Critical Intervention)
以下情况必须停下来，让用户手动 @Notion AI 的 Opus 4.6：

| 触发条件 | 行动 | 谁决定 |
|---------|------|--------|
| 架构变更 | 停止，等待设计审查 | 用户 |
| 性能下降 > 20% | 停止，等待性能审查 | 用户 |
| 安全漏洞 | 停止，等待安全审查 | 用户 |
| 测试失败 > 5 次 | 停止，等待根因分析 | 用户 |
| 歧义需求 | 停止，等待需求澄清 | 用户 |
| 估算 > 4 小时 | 停止，等待任务拆分 | 用户 |

**触发方式**：Claude 检测到上述条件时，输出 `🛑 CRITICAL: <原因>` 并暂停

## Notion 集成架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Notion Workspace                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   设计文档   │  │   任务跟踪   │  │   CI/CD 状态 │      │
│  │  (Design)    │  │  (Tasks)     │  │  (CI Status)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            │                                 │
│                    ┌───────▼────────┐                        │
│                    │  项目仪表盘   │                        │
│                    │  (Dashboard)   │                        │
│                    └────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  本地项目     │
                    │  (Local Repo)  │
                    └────────────────┘
```

## 项目目录结构

```
notion-cfd-harness/
├── .claude/
│   ├── GSD.md              # 本文件
│   ├── hooks/              # GSD 自动化 hooks
│   │   ├── pre-commit.py   # 提交前检查
│   │   ├── pre-push.py     # 推送前检查
│   │   └── critical-check.py # 关键点检查
│   └── notion/             # Notion 集成
│       ├── config.json     # Notion 配置
│       ├── sync.py         # 双向同步
│       └── api.py          # Notion API 封装
├── design/                 # 设计文档（本地镜像）
│   └── .notion-sync        # Notion 同步标记
├── docs/                   # API 文档
└── tasks/                  # 任务定义（本地镜像）
    └── .notion-sync
```

## GSD 工作流

### 开始新功能
1. **在 Notion 创建设计文档** → @Opus 4.6 审查
2. **审查通过后** → Claude 创建功能分支
3. **实施阶段** → 小步提交，自动检查
4. **完成实施** → 运行完整测试套件
5. **合并请求** → 自动代码审查
6. **合并** → 自动更新 Notion 任务状态

### 关键点介入流程
```
Claude 检测到关键点
    ↓
输出 🛑 CRITICAL: <原因>
    ↓
暂停当前任务
    ↓
等待用户在 Notion @Opus 4.6 审查
    ↓
用户确认继续 / 修正方向
    ↓
恢复执行
```

## 质量标准

### 代码质量
| 指标 | 阈值 | 检查方式 |
|------|------|----------|
| 测试覆盖率 | ≥ 80% | pytest-cov |
| 类型注解覆盖率 | ≥ 90% | mypy |
| 代码复杂度 | ≤ 15 | radon |
| 安全漏洞 | 0 | bandit |

### 文档质量
| 文档类型 | 更新时机 | 审查者 |
|----------|----------|--------|
| 设计文档 | 新功能前 | Opus 4.6 |
| API 文档 | API 变更时 | 自动生成 |
| README | 每次发布 | 用户审查 |

## 自动化 Hooks

### pre-commit
- 代码格式化 (black, isort)
- 类型检查 (mypy)
- Lint (flake8)
- 安全扫描 (bandit)

### pre-push
- 运行所有测试
- 检查测试覆盖率
- 同步到 Notion

### critical-check
- 检测架构变更
- 检测性能下降
- 检测安全漏洞
- 触发人工介入

## Notion 数据库结构

### Tasks 数据库
| 字段 | 类型 | 说明 |
|------|------|------|
| Title | title | 任务标题 |
| Status | select | Todo, In Progress, Done |
| Priority | select | High, Medium, Low |
| Assignee | person | 负责人 |
| Estimate | number | 估算小时 |
| Tags | multi_select | bug, feature, tech-debt |
| CI Status | formula | 根据 GitHub Actions 更新 |
| Notion ID | formula | Notion 页面 ID |

### Design Docs 数据库
| 字段 | 类型 | 说明 |
|------|------|------|
| Title | title | 文档标题 |
| Status | select | Draft, Review, Approved |
| Reviewer | person | 审查者 (Opus 4.6) |
| Related Tasks | relation | 关联任务 |
| Last Sync | date | 最后同步时间 |

## 配置文件

### .claude/notion/config.json
```json
{
  "workspace_id": "YOUR_NOTION_WORKSPACE_ID",
  "tasks_db_id": "YOUR_TASKS_DATABASE_ID",
  "design_db_id": "YOUR_DESIGN_DATABASE_ID",
  "sync_interval": 300,
  "auto_create_tasks": true,
  "auto_sync_status": true
}
```

## 快速开始

1. **配置 Notion 集成**
   ```bash
   # 1. 在 Notion 创建 workspace
   # 2. 创建 Tasks 和 Design Docs 数据库
   # 3. 获取 Integration Token
   # 4. 更新 .claude/notion/config.json
   ```

2. **启用 GSD hooks**
   ```bash
   # hooks 会自动安装到 .git/hooks/
   ```

3. **创建第一个设计文档**
   ```bash
   # 在 Notion 创建，或使用本地模板
   ```

4. **开始开发**
   ```bash
   # Claude 会自动遵循 GSD 规范
   ```

## 版本历史

- v1.0 (2026-04-08): 初始 GSD 配置
