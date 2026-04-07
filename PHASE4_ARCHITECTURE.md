# Phase4: Governed Memory Network - 架构文档

**版本**: v1.0
**日期**: 2026-04-08
**状态**: Baseline Complete
**Baseline Commit**: a91b427

---

## 一、概述

### 1.1 Phase4 目标

Phase4 构建 **Governed Memory Network（治理记忆网络）**，在 Phase3 Knowledge-Driven Orchestrator 基础上实现：

1. **知识演化追踪**：记录知识单元的版本历史和变更传播链
2. **治理策略执行**：自动执行 `publish_contract.md` 和 `model_rules` 的约束
3. **Memory-to-Code 映射**：建立知识单元与可执行代码的双向绑定
4. **Gate 自动化**：实现 G3-G6 Gate 的半自动化触发和验证

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Governed Memory Network                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     MemoryNetwork (主编排器)                      │   │
│  │  - get_network_state()                                          │   │
│  │  - register_change()                                            │   │
│  │  - propagate_changes()                                          │   │
│  │  - sync_code_mappings()                                         │   │
│  │  - get_statistics()                                             │   │
│  └──────────────────────┬──────────────────────────────────────────┘   │
│                         │                                               │
│         ┌───────────────┼───────────────┐                              │
│         ▼               ▼               ▼                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐               │
│  │   Versioned  │ │   MemoryNode │ │ CodeMapping      │               │
│  │  Knowledge   │ │              │ │ Registry         │               │
│  │  Registry    │ │              │ │                  │               │
│  │              │ │              │ │                  │               │
│  │ - versions   │ │ - unit_id    │ │ - mappings       │               │
│  │ - register   │ │ - version    │ │ - register       │               │
│  │ - get_chain  │ │ - content    │ │ - find_by_       │               │
│  │              │ │ - parents    │ │   source/target  │               │
│  └──────┬───────┘ └──────┬───────┘ └──────────────────┘               │
│         │                │                                                │
│         └────────┬───────┘                                               │
│                  ▼                                                        │
│         ┌────────────────┐                                               │
│         │ Propagation    │                                               │
│         │ Engine         │                                               │
│         │                │                                               │
│         │ - detect_      │                                               │
│         │   changes      │                                               │
│         │ - propagate    │                                               │
│         └───────┬────────┘                                               │
│                 │                                                         │
│                 ▼                                                         │
│         ┌────────────────┐                                               │
│         │ Governance     │                                               │
│         │ Engine         │                                               │
│         │                │                                               │
│         │ - enforce_     │                                               │
│         │   contract     │                                               │
│         │ - check_rules  │                                               │
│         └────────────────┘                                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Gate Layer                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │   G3     │  │   G4     │  │   G5     │  │   G6     │               │
│  │  Core    │  │  Propa-  │  │  Manual  │  │  Final   │               │
│  │  Check   │  │  gation  │  │  Review  │  │  Accept  │               │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Integration Layer                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────┐                   │
│  │   Notion Reviews DB  │  │   Notion Events DB   │                   │
│  │   (Gate 结果)         │  │   (Memory Events)    │                   │
│  └──────────────────────┘  └──────────────────────┘                   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │               CLI: scripts/memory-network                      │     │
│  │   $ ./scripts/memory-network gate trigger G3                   │     │
│  │   $ ./scripts/memory-network status                            │     │
│  │   $ ./scripts/memory-network version list --unit-id FORM-009  │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心组件

### 2.1 VersionedKnowledgeRegistry

**职责**：管理知识单元的版本历史

**关键方法**：
```python
def register_change(
    unit_id: str,
    parent_version: str | None,
    content_hash: str,
    metadata: dict
) -> UnitVersion
```

**版本模型**：
```python
@dataclass
class UnitVersion:
    unit_id: str
    version: str           # Git-like: v1, v2, v3...
    parent_hash: str | None
    content_hash: str
    timestamp: datetime
    lineage_hash: str      # Stable identifier for the lineage chain
    metadata: dict
```

**特性**：
- Git-like 链式结构：每个版本记录 `parent_hash`
- Lineage 稳定性：同一知识单元的变更链有相同的 `lineage_hash`
- 可回溯：`get_version_chain()` 可获取完整历史

---

### 2.2 MemoryNode

**职责**：表示单个知识单元的状态，包含代码映射

**关键方法**：
```python
def add_code_mapping(source_file: str, function_name: str)
def get_code_mappings() -> List[CodeMapping]
def to_dict() -> dict
```

**节点模型**：
```python
@dataclass
class MemoryNode:
    unit_id: str
    version: str
    content_hash: str
    created_at: datetime
    parent_hash: str | None
    metadata: dict
    code_mappings: List[CodeMapping]
    propagation_summary: dict | None
```

---

### 2.3 PropagationEngine

**职责**：检测变更并执行传播决策

**集成**：
- 使用 `diff_engine.py` 的 `ChangeType` 枚举
- 支持的变更类型：`ADD`, `UPDATE`, `DELETE`, `REFACTOR`, `BREAKING_CHANGE`

**关键方法**：
```python
def detect_changes(
    old_content: Any,
    new_content: Any,
    context: dict
) -> List[PropagationEvent]

def propagate(
    change: PropagationEvent,
    network_state: dict
) -> dict
```

---

### 2.4 GovernanceEngine

**职责**：执行治理规则

**规则来源**：
- `publish_contract.md`：发布契约
- `model_rules`：模型规则

**关键方法**：
```python
def enforce_contract(
    change: PropagationEvent,
    contract: dict
) -> GovernanceDecision

def check_rules(
    unit_id: str,
    version: str,
    rules: List[Rule]
) -> List[RuleViolation]
```

**决策类型**：
```python
class GovernanceDecision(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CONDITIONAL = "conditional"
```

---

### 2.5 CodeMappingRegistry

**职责**：知识-代码双向映射

**关键方法**：
```python
def register(
    unit_id: str,
    source_file: str,
    function_name: str
)

def find_by_unit(unit_id: str) -> List[CodeMapping]
def find_by_source(source_file: str) -> List[CodeMapping]
```

**映射模型**：
```python
@dataclass
class CodeMapping:
    unit_id: str
    source_file: str
    function_name: str
    registered_at: datetime
    confidence: float
```

---

### 2.6 MemoryNetwork（主编排器）

**职责**：集成所有组件，提供统一接口

**核心方法**：
```python
def register_change(
    unit_id: str,
    content: Any,
    metadata: dict
) -> dict

def get_network_state() -> dict
def get_statistics() -> dict

def propagate_changes(
    unit_id: str,
    version: str
) -> List[PropagationEvent]

def sync_code_mappings(
    mappings: List[dict]
) -> dict
```

**状态模型**：
```python
@dataclass
class NetworkState:
    nodes: Dict[str, MemoryNode]
    propagation_events: List[PropagationEvent]
    governance_decisions: List[GovernanceDecision]
    code_mappings: Dict[str, List[CodeMapping]]
    last_updated: datetime
```

---

## 三、Gate 层

### 3.1 Gate 配置模式

**GateConfig** 冻结数据类，所有 Gate 共享：

```python
@dataclass(frozen=True)
class GateConfig:
    gate_name: str
    checks: tuple[GateCheckRunner, ...] = ()
    module_name: str = DEFAULT_MODULE_NAME
    components: tuple[tuple[str, str], ...] = DEFAULT_COMPONENTS
    results_dir: Path | str = DEFAULT_RESULTS_DIR
    review_script: Path | str | None = DEFAULT_REVIEW_SCRIPT
    default_pytest_args: tuple[str, ...] = ()
    success_action: str = ""
    failure_action: str = ""
    report_title: str = ""
```

### 3.2 Gate 说明

| Gate | 名称 | 检查项 | 通过条件 |
|------|------|--------|----------|
| G3 | Core Components | 6个核心组件存在、测试通过 | 全部检查通过 |
| G4 | Propagation | 传播行为符合预期 | 传播测试通过 |
| G5 | Manual Approval | 人工审查 | 需要外部审查标记 |
| G6 | Final Acceptance | 端到端验证 | 全流程测试通过 |

---

## 四、集成层

### 4.1 Notion Reviews DB

**数据库 ID**：`33bc6894-2bed-81fb-a911-c4f0798ce1cf`

**同步方法**：
```python
def sync_gate_result_to_notion(
    gate_result: dict,
    reviews_db_id: str
) -> str
```

### 4.2 Notion Memory Events

**事件类型**：
```python
class MemoryEventType(Enum):
    KNOWLEDGE_CREATED = "knowledge_created"
    KNOWLEDGE_UPDATED = "knowledge_updated"
    KNOWLEDGE_DELETED = "knowledge_deleted"
    CODE_MAPPING_ADDED = "code_mapping_added"
    PROPAGATION_TRIGGERED = "propagation_triggered"
    GATE_COMPLETED = "gate_completed"
```

**同步方法**：
```python
NotionMemoryEvents.sync_events_to_notion(
    events: List[MemoryEvent],
    mock_mode: bool = False
)
```

### 4.3 CLI 工具

**位置**：`scripts/memory-network`

**命令**：
```bash
# Gate 触发
./scripts/memory-network gate trigger G3

# 状态查询
./scripts/memory-network status

# Memory Events
./scripts/memory-network events --gate-result <path>

# 代码映射同步
./scripts/memory-network sync-code-mappings --mappings-file <path>

# 版本历史
./scripts/memory-network version list --unit-id FORM-009
```

---

## 五、设计决策

### 5.1 统一模块架构

**决策**：将所有核心组件放在 `memory_network/__init__.py` 而非拆分文件

**理由**：
- 减少循环依赖风险
- 简化导入路径
- 更好的类型推断

### 5.2 GateConfig 冻结模式

**决策**：使用 `@dataclass(frozen=True)` 的 GateConfig

**理由**：
- 配置不可变，避免并发修改
- 多个 Gate 共享同一配置模式
- 易于测试和序列化

### 5.3 非阻塞 Code Review

**决策**：Code Review 额度不足时不阻塞执行

**实现**：
```bash
# trigger_code_review.sh
STATUS=$(check_codex_status)
if [ $? -ne 0 ]; then
    echo "⚠️ Code Review 跳过（不阻塞）"
    exit 0  # 非 0 退出码也不阻塞
fi
```

### 5.4 隔离版本数据库

**决策**：默认使用临时路径避免改写仓库 `.versions.json`

**理由**：
- 保护仓库状态
- 支持多环境并行测试
- 显式 `--version-db-path` 才写入指定位置

---

## 六、测试策略

### 6.1 测试覆盖

| 模块 | 测试文件 | 测试数 |
|------|----------|--------|
| VersionedKnowledgeRegistry | test_p4_01_*.py | 12 |
| MemoryNode | test_p4_02_*.py | 10 |
| PropagationEngine | test_p4_03_*.py | 14 |
| GovernanceEngine | test_p4_04_*.py | 12 |
| CodeMappingRegistry | test_p4_05_*.py | 10 |
| MemoryNetwork | test_p4_06_*.py | 16 |
| G3 Gate | test_p4_07_*.py | 12 |
| G4-G6 Gates | test_p4_08_*.py | 14 |
| Notion Reviews | test_p4_09_*.py | 6 |
| Memory Events | test_p4_10_*.py | 8 |
| CLI | test_p4_11_*.py | 7 |

**总计**：116 测试

### 6.2 运行测试

```bash
# 所有 Phase4 测试
pytest tests/test_p4_*.py -v

# 特定模块
pytest tests/test_p4_06_memory_network.py -v

# 带 coverage
pytest tests/test_p4_*.py --cov=knowledge_compiler/memory_network
```

---

## 七、使用示例

### 7.1 基本使用

```python
from knowledge_compiler.memory_network import MemoryNetwork
from pathlib import Path

# 初始化（使用默认版本库）
network = MemoryNetwork(
    base_path=Path("knowledge_compiler/units")
)

# 注册变更
result = network.register_change(
    unit_id="FORM-009",
    content={"formulas": [...]},
    metadata={"author": "system", "source": "calculation"}
)

# 获取状态
state = network.get_network_state()
print(f"Nodes: {len(state['nodes'])}")

# 传播变更
events = network.propagate_changes(
    unit_id="FORM-009",
    version=result["version"]
)
```

### 7.2 使用 CLI

```bash
# 检查网络状态
./scripts/memory-network status

# 触发 G3 Gate
./scripts/memory-network gate trigger G3

# 查看版本历史
./scripts/memory-network version list --unit-id FORM-009
```

---

## 八、Phase4 → Phase5 过渡

### 8.1 完成的验收标准

- [x] P4-01 ~ P4-06 核心组件实现完成
- [x] P4-07 ~ P4-09 Gate 流程可运行
- [x] Codex Code Review 集成（含降级）
- [x] Opus 架构审查通过（P4-07, P4-08）
- [x] Notion 集成测试通过

### 8.2 Phase5 准备

Phase5 将基于 Phase4 的 Governed Memory Network 实现：
- 生产环境部署
- 性能优化
- 监控和告警
- 备份和恢复

---

## 九、文件清单

### 9.1 核心代码

```
knowledge_compiler/
├── memory_network/
│   ├── __init__.py              (2855 lines, 6 components)
│   └── notion_memory_events.py  (780 lines)
└── gates/
    ├── g3_gate.py               (741 lines)
    ├── g4_gate.py               (38 lines)
    ├── g5_gate.py               (38 lines)
    └── g6_gate.py               (38 lines)
```

### 9.2 CLI 工具

```
scripts/
└── memory-network               (executable, 863 lines)
```

### 9.3 测试文件

```
tests/
├── test_p4_01_versioned_registry.py
├── test_p4_02_memory_node.py
├── test_p4_03_propagation_engine.py
├── test_p4_04_governance_engine.py
├── test_p4_05_code_mapping.py
├── test_p4_06_memory_network.py
├── test_p4_07_g3_gate.py
├── test_p4_08_g4_g6_gates.py
├── test_p4_09_notion_reviews.py
├── test_p4_10_memory_events.py
└── test_p4_11_cli.py
```

### 9.4 文档

```
Phase4_PLAN.md                    (规划文档)
Phase4_BASELINE_MANIFEST.json     (基线清单)
PHASE4_ARCHITECTURE.md            (本文档)
```

---

*文档版本: v1.0*
*创建时间: 2026-04-08*
*维护者: Claude Code (Opus 4.6)*
