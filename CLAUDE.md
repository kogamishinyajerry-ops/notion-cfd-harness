# Claude Code 项目配置

> 本项目采用 **GSD (Guided Software Development)** 方式开发
> 详见: [GSD.md](./GSD.md)

---

## GSD 核心规则

### 1. 文档驱动
- 新功能必须先有设计文档（Notion 或 `design/` 目录）
- API 变更必须先更新 API 文档
- 设计文档需要 @Opus 4.6 审查后才能实施

### 2. 质量门控
- 测试覆盖率必须 ≥ 80%
- 所有安全漏洞必须立即修复
- 代码必须通过所有 gates

### 3. 快速迭代
- 小步提交，每个 commit 可运行
- 允许临时技术债，标注 `#tech-debt`

### 4. 关键点介入（重要！）
以下情况 Claude **必须停下来**，让用户手动在 Notion @Opus 4.6：

| 触发条件 | 行动 |
|---------|------|
| 架构变更 | 🛑 输出 "CRITICAL: 架构变更需要审查" 并暂停 |
| 性能下降 > 20% | 🛑 输出 "CRITICAL: 性能下降需要审查" 并暂停 |
| 安全漏洞 | 🛑 输出 "CRITICAL: 安全漏洞需要修复" 并暂停 |
| 测试失败 > 5 次 | 🛑 输出 "CRITICAL: 多次测试失败，需要根因分析" 并暂停 |
| 歧义需求 | 🛑 输出 "CRITICAL: 需求不明确，需要澄清" 并暂停 |
| 估算 > 4 小时 | 🛑 输出 "CRITICAL: 任务太大，需要拆分" 并暂停 |

**Claude 不要一直自动执行！遇到上述情况立即停下来！**

---

## 项目规范

### 代码风格
- Python: PEP 8, 使用 black 格式化
- 类型注解: 尽量使用 Type Hints
- 文档字符串: Google style docstrings

### Git 工作流
```bash
# 功能分支命名
feature/TASK-123-description
bugfix/TASK-456-fix-issue

# Commit 消息格式
feat: add new feature
fix: correct bug
docs: update documentation
test: add tests

# 关联任务（自动同步到 Notion）
#TASK-123: implementation
```

### 测试要求
- 每个功能必须有单元测试
- 使用 pytest 框架
- 覆盖率报告: `pytest --cov=. --cov-report=html`

---

## Notion 集成

### 配置文件
`.claude/notion/config.json`

### 同步命令
```bash
# 同步 commit 到 Notion
.claude/notion/sync.py sync-commit

# 创建审查任务
.claude/notion/sync.py create-review --reason "架构变更"

# 查看配置状态
.claude/notion/sync.py status
```

### Notion 数据库
- **Tasks**: 任务跟踪，包含状态、优先级、标签
- **Design Docs**: 设计文档，需要 Opus 4.6 审查
- **Dashboard**: 项目进度仪表盘

---

## 项目结构

```
notion-cfd-harness/
├── .claude/
│   ├── GSD.md              # GSD 开发规范
│   ├── CLAUDE.md           # 本文件
│   ├── hooks/              # Git hooks
│   │   ├── install.sh      # Hooks 安装脚本
│   │   └── critical-check.py # 关键点检查
│   ├── notion/             # Notion 集成
│   │   ├── config.json     # Notion 配置
│   │   ├── api.py          # Notion API
│   │   └── sync.py         # 同步脚本
│   └── setup-gsd.sh        # GSD 初始化脚本
├── design/                 # 设计文档（本地）
├── docs/                   # API 文档
├── knowledge_compiler/     # 主代码
└── tests/                  # 测试
```

---

## 初始化 GSD

首次使用时运行：

```bash
.claude/setup-gsd.sh
```

这会：
1. 安装 Git hooks（自动检查）
2. 设置 Notion 配置（可选）
3. 创建目录结构
4. 安装 Python 依赖

---

## Claude 行为准则

### ✅ 应该做的
1. 遵循 GSD 规范
2. 关键点停下来让用户介入
3. 文档先行，再写代码
4. 小步提交，及时验证
5. 遇到歧义主动询问

### ❌ 不应该做的
1. 不要一直自动执行而不停下来
2. 不要跳过质量检查
3. 不要在架构未审查时继续
4. 不要忽视安全漏洞
5. 不要在需求不明确时猜测

---

## 快速参考

### 创建新功能
1. 在 Notion 创建设计文档
2. @Opus 4.6 审查设计
3. 创建功能分支
4. 实施并测试
5. 合并并同步状态

### 处理关键点
1. Claude 检测到关键点
2. 输出 `🛑 CRITICAL: <原因>`
3. 暂停当前任务
4. 用户在 Notion @Opus 4.6
5. 审查通过后继续

### 质量检查
```bash
# 运行所有检查
pytest

# 代码格式化
black . isort .

# 类型检查
mypy .

# 安全扫描
bandit -r .
```
