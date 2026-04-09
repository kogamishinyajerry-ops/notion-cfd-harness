# 文档清理清单
**生成时间**: 2026-04-08 (更新)
**执行者**: GLM-5.1 (Claude Code环境)

---

## 一、已更新的文档

| 文档 | 状态 | 操作 |
|------|------|------|
| `MODEL_ROUTING_TABLE_v3.md` | ✅ 新建 | **重新设计模型分工：Codex承担核心实现** |
| `MODEL_ROUTING_TABLE_v2.md` | ⚠️ 已标记废弃 | 添加过时警告，指向v3 |
| `model_rules_v1.2_with_codex_cr.md` | ⚠️ 已标记废弃 | 添加过时警告 |

---

## 二、需要Review的文档（可能过时）

### 2.1 Phase相关文档

| 文档 | 状态 | 建议 |
|------|------|------|
| `PHASE4_ARCHITECTURE.md` | ⚠️ 需检查 | 确认与Phase 1-5新架构对齐 |
| `PHASE4_PLAN.md` | ⚠️ 需检查 | 确认计划状态 |
| `Phase5_PLAN.md` | ⚠️ 需检查 | 确认计划状态 |

### 2.2 测试文档

| 文档 | 状态 | 建议 |
|------|------|------|
| `M1_MILESTONE_COMPLETE.md` | ⚠️ 部分过时 | 第4节模型分工已更新 |

---

## 三、已确认正确的文档

| 文档 | 状态 | 说明 |
|------|------|------|
| `notion_opus_prompts.md` | ✅ 最新 | Notion AI触发指令库 |
| `glmext.py` | ✅ 最新 | GLM-5.1调用封装 |
| `minimix.py` | ✅ 最新 | MiniMax-M2.7调用封装 |
| `PROJECT_HIERARCHY.md` | ✅ 最新 | 项目层级结构规范 |

---

## 四、Phase 1 完成文档（待更新）

| 文档 | 需要添加的内容 |
|------|---------------|
| `MODEL_ROUTING_TABLE_v2.md` | Phase 1模块完成状态 |
| Phase 1文档 | Module 1-4实现总结 |

---

## 五、建议后续操作

1. ✅ **完成**: 创建 MODEL_ROUTING_TABLE_v2.md
2. ✅ **完成**: 标记 model_rules_v1.2 为过时
3. ⏭️ **待办**: 用户手动在Notion中创建新的模型路由表页面
4. ⏭️ **待办**: Phase 1完成后请求Opus 4.6进行架构审查

---

## 六、文档状态对照表

```
当前架构 (2026-04-08):
├── MODEL_ROUTING_TABLE_v2.md     ✅ 最新 - 模型分工真相源
├── model_rules_v1.2_*.md         ⚠️  已过时 - 仅作历史参考
├── notion_opus_prompts.md        ✅ 最新 - Notion AI指令库
├── glmext.py                     ✅ 最新 - GLM-5.1封装
├── minimix.py                    ✅ 最新 - MiniMax封装
├── PROJECT_HIERARCHY.md          ✅ 最新 - 项目结构规范
├── M1_MILESTONE_COMPLETE.md      ⚠️  部分过时 - 仅M1阶段有效
└── Phase*/_PLAN.md               ⚠️  需Review - 确认当前状态
```

---

**维护说明**:
- 模型路由变更时，优先更新 MODEL_ROUTING_TABLE_v2.md
- 旧文档保留但需标记过时
- 大架构变更需通知Notion AI (Opus 4.6) 审查
