# GitHub + Notion + Codex Review 工作流设计

## 架构概览

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Develop   │────▶│   GitHub    │────▶│   Notion    │
│   (Local)   │     │             │     │Control Tower│
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                    │
       │                   ▼                    ▼
       │            ┌─────────────┐     ┌─────────────┐
       │            │Codex Review │     │  Reviews DB │
       └───────────▶│  (codex:    │     │             │
                    │   rescue)  │◀────┤             │
                    └─────────────┘     └─────────────┘
```

## 工作流步骤

### 1. 开发阶段 (Local)
```bash
# 1. 创建功能分支 (命名规范: feature/PHASE-NUMBER-description)
git checkout -b feature/P2-72-result-validator

# 2. 开发并测试
# ... 编写代码 ...
pytest tests/phase2/test_result_validator.py

# 3. Git hooks 自动同步到 Notion
git add .
git commit -m "#P2-72: Implement Result Validator

- ValidationStatus, AnomalyType enums
- ResidualChecker, ConvergenceChecker, NumericalAnomalyDetector
- ResultValidator main class
- 35/35 tests passed"

# pre-commit hook: → Notion Tasks DB 状态更新
```

### 2. PR 阶段 (GitHub)
```bash
# 4. 推送到 GitHub
git push origin feature/P2-72-result-validator

# 5. 创建 PR (通过 CLI 或 Web)
gh pr create --title "P2-72: Implement Result Validator" --body "See Notion Task P2-72"

# PR 创建触发:
# - Notion Tasks DB 更新 PR 链接
# - 自动创建 Codex Review 任务
# - 更新状态为 "In Review"
```

### 3. Review 阶段 (Codex)
```bash
# 6. 自动触发 Codex Review (通过 GitHub Actions 或手动)
codex:rescue --model=gpt-5.3-codex --scope=phase2/execution_layer

# 或使用 skill invoke
/skill codex:rescue

# Codex 审查结果写入:
# - Notion Reviews DB
# - PR 评论 (如果 API 可用)
```

### 4. 合并阶段
```bash
# 7. Review 通过后合并
gh pr merge 123 --squash

# 合并触发:
# - Notion Tasks DB 状态 → "Done"
# - 删除功能分支
# - 触发下游通知
```

## Notion 数据库结构

### Tasks DB 扩展字段
| 字段 | 类型 | 说明 |
|------|------|------|
| Task ID | Title | P2-72 |
| Git Branch | Text | feature/P2-72-result-validator |
| PR Link | URL | https://github.com/.../pull/123 |
| Review ID | Formula | 关联 Reviews DB |
| Last Commit | Text | abc1234 |

### Reviews DB 扩展字段
| 字段 | 类型 | 说明 |
|------|------|------|
| Review ID | Title | REVIEW-P2-72-20240408 |
| PR Link | URL | 关联 PR |
| Review Type | Select | Codex Review, Manual Review |
| Decision | Select | Approved, Changes Required |
| Reviewer Model | Text | GPT-5.3-codex, Opus 4.6 |
| Findings | Text | 审查发现 |
| Created At | Date | 创建时间 |

## Git Hooks 实现

### pre-commit (自动同步任务状态)
```bash
#!/bin/bash
# .git/hooks/pre-commit

# 从 commit 消息解析任务 ID
TASK_ID=$(git log -1 --format=%B | grep -oE "#[A-Z]+-[0-9]+" | head -1 | sed 's/#//')

if [ -n "$TASK_ID" ]; then
    python3 .claude/notion/sync.py update-status --task-id "$TASK_ID" --status "In Progress"
fi
```

### post-commit (提交后同步)
```bash
#!/bin/bash
# .git/hooks/post-commit

# 同步 commit 信息到 Notion
python3 .claude/notion/sync.py sync-commit

# 运行测试 (可选)
pytest tests/ --tb=short --maxfail=3
```

### pre-push (推送前检查)
```bash
#!/bin/bash
# .git/hooks/pre-push

# 运行测试
pytest tests/ --tb=short -q
if [ $? -ne 0 ]; then
    echo "❌ 测试失败，阻止推送"
    exit 1
fi

# 检查 Codex Review 是否已完成 (针对已有 PR)
PR_NUMBER=$(git log -1 --format=%B | grep -oE "#[0-9]+" | head -1 | sed 's/#//')
if [ -n "$PR_NUMBER" ]; then
    REVIEW_STATUS=$(python3 .claude/notion/sync.py check-review --pr-number "$PR_NUMBER")
    if [ "$REVIEW_STATUS" != "Approved" ]; then
        echo "⚠️  Codex Review 未通过，请确认后再推送"
        # 可以选择阻止或仅警告
        # exit 1
    fi
fi
```

## GitHub Actions Workflow (可选)

```yaml
# .github/workflows/codex-review.yml
name: Codex Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  codex-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Codex Review
        run: |
          # 获取变更的文件
          CHANGED_FILES=$(git diff --name-only origin/main...HEAD)

          # 调用 Codex Review
          # (需要配置 Codex API 或使用本地脚本)
          python3 .claude/notion/sync.py trigger-codex-review \
            --pr-number ${{ github.event.number }} \
            --changed-files "$CHANGED_FILES"
```

## 命令速查

```bash
# 查看同步状态
python3 .claude/notion/sync.py status

# 创建任务 (从分支名推断)
python3 .claude/notion/sync.py create-task --task-id "P2-72"

# 更新任务状态
python3 .claude/notion/sync.py update-status --task-id "P2-72" --status "Done"

# 创建审查请求
python3 .claude/notion/sync.py create-review --review-type "Codex Review" --reason "Result Validator implementation"

# 同步 commit
python3 .claude/notion/sync.py sync-commit

# 同步分支
python3 .claude/notion/sync.py sync-branch

# 触发 Codex Review (新增)
python3 .claude/notion/sync.py trigger-codex-review --pr-number 123

# 检查 Review 状态 (新增)
python3 .claude/notion/sync.py check-review --pr-number 123

# 同步 PR 到 Notion (新增)
python3 .claude/notion/sync.py sync-pr --pr-number 123
```

## 安装步骤

1. **安装 Git Hooks**
```bash
cp .claude/hooks/* .git/hooks/
chmod +x .git/hooks/*
```

2. **验证集成**
```bash
# 测试同步
python3 .claude/notion/sync.py status

# 测试创建任务
python3 .claude/notion/sync.py create-task --task-id "TEST-1"
```

3. **首次工作流**
```bash
# 1. 创建分支
git checkout -b feature/P2-TEST-test-workflow

# 2. 提交更改
git add .
git commit -m "#P2-TEST: Test GitHub integration"
# → 自动同步到 Notion

# 3. 推送
git push origin feature/P2-TEST-test-workflow

# 4. 创建 PR
gh pr create --title "P2-TEST: Test GitHub integration"
# → 自动创建 Review 任务

# 5. 触发 Codex Review
python3 .claude/notion/sync.py trigger-codex-review --pr-number $(gh pr view --json number -q .number)
```

## 注意事项

1. **分支命名规范**: `feature/PHASE-NUMBER-description` 或 `bugfix/PHASE-NUMBER-description`
2. **Commit 消息格式**: `#TASK-ID: Brief description`
3. **PR 标题格式**: `TASK-ID: Brief description`
4. **Codex Review 触发**: 自动 (PR 创建时) 或手动
5. **状态同步**: Git hooks 自动处理，也可手动同步

## 扩展集成

### 与 Codex:Rescue 深度集成

```bash
# 创建 PR 后自动触发
gh pr create --title "..." | python3 .claude/notion/sync.py parse-pr --trigger-codex

# Codex Review 完成后自动更新 PR 状态
codex:rescue --model=gpt-5.3-codex --format=json | python3 .claude/notion/sync.py import-codex-result
```

### 与 MCP GitHub 集成

使用 MCP GitHub 插件自动同步 PR 状态：
```python
from mcp_plugin_github import get_pull_request, create_pull_request_review

# 自动获取 PR 信息
pr = get_pull_request(owner, repo, pr_number)

# 根据 Review 结果创建 PR 评论
if review_decision == "Changes Required":
    create_pull_request_review(
        owner=owner,
        repo=repo,
        pull_number=pr_number,
        body=codex_findings,
        event="REQUEST_CHANGES"
    )
```
