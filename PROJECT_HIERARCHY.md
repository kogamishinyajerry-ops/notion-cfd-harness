# Well-Harness 项目层级结构规范

## 当前问题
所有任务页面都是 SSOT 数据库顶层页面，仅靠 `Phase` 字段逻辑分组，无强制父子关系。

## 正确结构：两层层级

```
SSOT 数据库（顶层 = 项目）
│
└── AI-CFD-001 (项目页面)
    │
    ├── M1-1-状态机引擎 (子页面)
    │   └── G0/G1/G2... 子任务
    │
    ├── M1-2-G0任务门 (子页面)
    │
    ├── M1-3-Task创建向导 (子页面)
    │
    └── M1-4-... (子页面)
```

## 规则

| 层级 | 创建位置 | Gate 检查 | 执行主体 |
|------|---------|----------|---------|
| 项目页 (顶层) | SSOT 数据库新建 | G0/G6 总Gate | Claude Code |
| 子任务页 | 项目页下新建 | 无独立Gate，跟随项目 | GLM/MiniMax/GPT |
| 开发子页 | 子任务页下新建 | 详细执行记录 | Codex/具体Agent |

## 关键原则

1. **每个 Phase 只创建一个项目页**（如 Phase1-Copilot 只有一个 AI-CFD-001）
2. **子任务全部是项目页的子页面**，不是顶层
3. **Gate 检查在项目页进行**，子任务共享 Gate 状态
4. **执行日志统一写在项目页**，子任务只写摘要引用
5. **新建子任务时**：在项目页下用 `create_notion_page_task()` 创建子页面

## 新建子任务的正确方式

```python
# ❌ 错误：在 SSOT 顶层新建
create_notion_page_task(
    parent_id=SSOT_DB_ID,  # 直接在数据库下创建
    ...
)

# ✅ 正确：在项目页下创建子页面
create_notion_page_task(
    parent_id="AI-CFD-001-page-id",  # 在主项目页下创建
    ...
)
```

## 已实现的支持

`notion_cfd_loop.py` 中的 `create_notion_page_task()` 函数支持：
- `parent_id` 可以是数据库 ID（顶层）或页面 ID（子页面）
- 自动设置正确的 parent type

## 检查清单

新建子任务前，确认：
- [ ] 父项目页面存在
- [ ] 父项目页有正确的 `Phase` 和 `Gate节点` 字段
- [ ] 子任务创建在父项目页下
- [ ] 执行日志引用到父项目页
