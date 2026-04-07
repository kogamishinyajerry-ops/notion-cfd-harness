# Phase4: Governed Memory Network 规划

**版本**: v1.0
**日期**: 2026-04-07
**状态**: Planning
**Phase3 Gate**: ✅ PASS (Opus 4.6 签署)

---

## 一、Phase4 目标

### 1.1 核心目标

Phase3 完成了 Knowledge-Driven Orchestrator，实现了从自然语言到 CFD 工作流的可执行编排。Phase4 的目标是构建 **Governed Memory Network (治理记忆网络)**，实现：

1. **知识演化追踪**：记录知识单元的版本历史和变更传播链
2. **治理策略执行**：自动执行 publish_contract.md 和 model_rules 的约束
3. **Memory-to-Code 映射**：建立知识单元与可执行代码的双向绑定
4. **Gate 自动化**：实现 G3-G6 Gate 的半自动化触发和验证

### 1.2 与 Phase3 的关系

| Phase3 产出 | Phase4 消费方式 |
|-------------|-----------------|
| KnowledgeRegistry | 扩展为 VersionedKnowledgeRegistry |
| diff_engine.py | 集成到 MemoryNetwork 进行变更检测 |
| propagation_rules.md | 自动化执行传播决策 |
| orchestrator/* | MemoryNetwork 可回溯到具体组件 |

---

## 二、架构设计

### 2.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                   GovernedMemoryNetwork                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │ VersionedRegistry│ ◄─── │  MemoryNode     │            │
│  │  (知识版本管理)   │      │  (记忆节点)      │            │
│  └────────┬─────────┘      └────────┬─────────┘            │
│           │                          │                        │
│           ▼                          ▼                        │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  PropagationEngine│     │  GovernanceEngine│            │
│  │  (传播执行引擎)   │      │  (治理执行引擎)   │            │
│  └────────┬─────────┘      └────────┬─────────┘            │
│           │                          │                        │
│           ▼                          ▼                        │
│  ┌────────────────────────────────────────────┐             │
│  │            CodeMappingRegistry            │             │
│  │         (知识-代码映射注册表)              │             │
│  └────────────────────────────────────────────┘             │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 数据模型

```python
@dataclass
class MemoryNode:
    """记忆节点 - 表示一个知识单元的状态"""
    unit_id: str
    version: str
    content_hash: str
    created_at: datetime
    parent_hash: Optional[str]  # Git-like 链式结构
    metadata: Dict[str, Any]
    code_mappings: List[str]  # 映射到的代码文件路径

@dataclass
class PropagationEvent:
    """传播事件"""
    event_id: str
    change_type: ChangeType  # from diff_engine
    source_unit: str
    impact_targets: List[str]
    governance_decision: str  # APPROVED/REJECTED/DEFERRED
    reason: str
    timestamp: datetime
```

---

## 三、任务分解 (P4-01 ~ P4-12)

### 3.1 核心层任务 (P4-01 ~ P4-06)

| 任务 ID | 任务名称 | 执行模型 | 依赖 | Code Review |
|---------|----------|----------|------|-------------|
| P4-01 | VersionedKnowledgeRegistry | Codex | P3-01 | Codex CR |
| P4-02 | MemoryNode 数据模型 | Codex | P4-01 | Codex CR |
| P4-03 | PropagationEngine 集成 diff_engine | Codex | P3-02, P4-02 | Codex CR |
| P4-04 | GovernanceEngine 执行治理规则 | Codex | P4-03 | Codex CR |
| P4-05 | CodeMappingRegistry 双向绑定 | Codex | P4-02 | Codex CR |
| P4-06 | MemoryNetwork 主编排器 | Codex | P4-01~P4-05 | Codex CR |

### 3.2 Gate 层任务 (P4-07 ~ P4-09)

| 任务 ID | 任务名称 | 执行模型 | 依赖 | Code Review |
|---------|----------|----------|------|-------------|
| P4-07 | G3 Gate 自动化触发 | Codex + Opus审查 | P4-06 | Codex CR + Opus |
| P4-08 | G4-G6 Gate 验收流程 | Codex + Opus审查 | P4-07 | Codex CR + Opus |
| P4-09 | Gate 记录到 Notion Reviews DB | Codex | P4-08 | 跳过 CR |

### 3.3 集成层任务 (P4-10 ~ P4-12)

| 任务 ID | 任务名称 | 执行模型 | 依赖 | Code Review |
|---------|----------|----------|------|-------------|
| P4-10 | Notion API 集成 - Memory Events | Codex | P4-09 | 跳过 CR |
| P4-11 | CLI 工具 - memory-network 命令 | Codex | P4-10 | Codex CR |
| P4-12 | 文档 + Phase4 Baseline | Codex | P4-11 | 跳过 CR |

---

## 四、执行流程（含 Code Review）

### 4.1 单任务执行流程

```
1. 用户请求: "执行 P4-01 VersionedKnowledgeRegistry"
   ↓
2. Claude Code 检查 Codex 状态
   ↓
3. 用 Codex 执行实现
   ↓
4. 实现完成 → 尝试触发 Codex Code Review
   ├─ 有额度 → 触发 review --base HEAD~1 --scope working-tree
   │              ↓
   │           审查结果处理:
   │           ├─ PASS → 继续
   │           ├─ CONDITIONAL PASS → 记录建议，继续
   │           └─ BLOCKED → 修复，重新审查
   │
   └─ 无额度/超时 → 跳过 CR，记录到 Notion (CR_SKIPPED)
   ↓
5. Git commit (带 Co-Authored-By)
   ↓
6. 推送 GitHub
   ↓
7. 更新 Notion 任务状态
```

### 4.2 Code Review 触发脚本

```bash
#!/bin/bash
# 触发 Codex Code Review（非阻塞）
BASE_COMMIT="HEAD~1"
SCOPE="working-tree"
FOCUS="Phase4 Memory Network 实现"

echo "=== 尝试触发 Codex Code Review ==="

# 检查 Codex 状态
STATUS=$(node ~/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs status --json 2>/dev/null)

# 尝试触发审查
node ~/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs \
  adversarial-review \
  --base "$BASE_COMMIT" \
  --scope "$SCOPE" \
  --focus "$FOCUS" \
  --background 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Code Review 已触发（后台运行）"
    echo "使用 'node .../codex-companion.mjs result <job-id>' 查看结果"
else
    echo "⚠️ Code Review 跳过（额度不足或其他原因）"
    echo "这不会阻塞执行，任务将正常提交"
fi
```

---

## 五、Codex Code Review 降级策略

### 5.1 触发检查流程

```python
def trigger_code_review_if_available(focus_text: str) -> Optional[str]:
    """
    尝试触发 Codex Code Review，失败时不阻塞

    Returns: job_id if triggered, None if skipped
    """
    import subprocess
    import json

    # 检查状态
    try:
        result = subprocess.run(
            ["node", CODEX_COMPANION, "status", "--json"],
            capture_output=True, timeout=10
        )
        status = json.loads(result.stdout)

        # 检查是否有运行中的任务
        if status.get("running"):
            print("⚠️ Codex 有任务运行中，跳过 Code Review")
            return None

    except Exception as e:
        print(f"⚠️ 无法检查 Codex 状态: {e}")

    # 尝试触发审查
    try:
        result = subprocess.run(
            ["node", CODEX_COMPANION, "adversarial-review",
             "--base", "HEAD~1",
             "--scope", "working-tree",
             "--focus", focus_text,
             "--background"],
            capture_output=True, timeout=30
        )

        if "usage limit" in result.stderr.decode():
            print("⚠️ Codex 额度不足，跳过 Code Review（不阻塞）")
            return None

        # 解析 job_id
        # ...
        return job_id

    except Exception as e:
        print(f"⚠️ Code Review 触发失败: {e}（不阻塞）")
        return None
```

### 5.2 降级记录到 Notion

```python
def log_code_review_skipped(reason: str, task_id: str):
    """记录 Code Review 跳过事件到 Notion"""
    notion.pages.blocks.create(
        parent=page_id,
        properties={
            "Review Type": "CodeReview",
            "Decision": "SKIPPED",
            "Reason": reason,
            "Task": task_id,
            "Timestamp": datetime.now().isoformat()
        }
    )
```

---

## 六、Notion 集成

### 6.1 Phase4 项目页结构

```
AI-CFD-004 (Phase4: Governed Memory Network)
├── P4-01 VersionedKnowledgeRegistry (子页面)
├── P4-02 MemoryNode 数据模型 (子页面)
├── ...
├── Gate 记录 (子页面)
└── 执行日志 (主页面)
```

### 6.2 状态同步命令

```bash
# 创建 Phase4 项目页
python3 notion_cfd_loop.py --create-project "AI-CFD-004" --phase "Phase4" --title "Governed Memory Network"

# 创建子任务
python3 notion_cfd_loop.py --create-task "P4-01" --parent "AI-CFD-004" --title "VersionedKnowledgeRegistry"

# 更新任务状态
python3 notion_cfd_loop.py --update-task "P4-01" --status "in_progress"
```

---

## 七、质量标准

### 7.1 代码质量（Codex CR 检查）

- PEP8 合规
- 类型注解完整
- Docstring 覆盖率 > 80%
- 单元测试覆盖率 > 70%

### 7.2 架构质量（Opus 审查）

- 与 Phase3 Orchestrator 一致性
- 无循环依赖
- 接口清晰，职责单一
- 错误处理完善

---

## 八、风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| Codex 额度不足导致 CR 缺失 | 记录 SKIPPED 事件，事后补充审查 |
| Phase4 复杂度超预期 | 分阶段交付，优先核心功能 |
| 与 Phase3 集成困难 | 保持接口兼容，渐进式迁移 |

---

## 九、验收标准

### 9.1 Phase4 Gate 条件

- [ ] P4-01 ~ P4-06 核心组件实现完成
- [ ] P4-07 ~ P4-09 Gate 流程可运行
- [ ] Codex Code Review 集成（含降级）
- [ ] Opus 架构审查通过
- [ ] Notion 集成测试通过

### 9.2 最终交付物

1. `memory_network.py` - 主编排器
2. `versioned_registry.py` - 版本化知识注册表
3. `propagation_engine.py` - 传播执行引擎
4. `governance_engine.py` - 治理执行引擎
5. `code_mapping.py` - 代码映射注册表
6. Phase4_BASELINE_MANIFEST.json
7. Phase4 架构文档

---

## 十、下一步行动

**立即执行**：

1. 创建 Notion Phase4 项目页
2. 开始 P4-01: VersionedKnowledgeRegistry
3. 配置 Code Review 触发脚本

---

*规划者: Claude Code (Opus 4.6 架构指导)*
*规划版本: v1.0*
*创建时间: 2026-04-07 20:XX CST*
