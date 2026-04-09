# Phase 2: Knowledge Compiler - 启动计划

**批准日期**: 2026-04-08
**审查结果**: Opus 4.6 APPROVED (8.4/10)
**预计工期**: 2-3 周

---

## 一、Phase 2 目标

将 Phase 1 捕获的原始知识编译为标准化的、可复用的知识规范。

### 1.1 核心能力

| 能力 | 描述 | 输入 | 输出 |
|------|------|------|------|
| Teach Capture | 捕获工程师教学操作 | Phase1Output | TeachCapture |
| Knowledge Parser | 理解教学内容 | TeachCapture | ParsedTeach |
| Canonical Compiler | 编译标准规范 | ParsedTeach | CanonicalSpec |
| Publish Contract | 发布知识 | CanonicalSpec | CompiledKnowledge |

### 1.2 与 Phase 1 的关系

```
Phase 1 (Knowledge Collector)
    │ Phase1Output
    ▼
┌─────────────────────────────────┐
│ Phase 2: Knowledge Compiler     │
│                                 │
│  ┌─────────────┐  ┌───────────┐ │
│  │ Teach Layer │  │ Compiler  │ │
│  └─────────────┘  └───────────┘ │
└─────────────────────────────────┘
    │
    ▼ Phase2Output
Phase 3 (Orchestrator)
```

---

## 二、模块设计

### 2.1 Schema 模块

**文件**: `phase2/schema.py`

**核心类**:
```python
@dataclass
class Phase2Input:
    """Phase 2 输入接口"""
    source: Phase1Output        # 来自 Phase 1
    compiler_config: CompilerConfig
    target_status: KnowledgeStatus

@dataclass
class CompiledKnowledge:
    """编译后的知识"""
    knowledge_id: str
    canonical_spec: CanonicalSpec
    compilation_log: List[str]
    gate_results: Dict[str, GateResult]
```

### 2.2 Teach Layer

**文件**: `phase2/teach.py`

**核心类**:
```python
@dataclass
class TeachCapture:
    """捕获的原始教学数据"""
    capture_id: str
    source_case_id: str
    raw_operations: List[TeachOperation]
    context: Dict[str, Any]

@dataclass
class ParsedTeach:
    """解析后的教学"""
    teach_id: str
    intent: TeachIntent
    generalizable: bool
    affected_components: List[str]
    confidence: float
```

### 2.3 Compiler Layer

**文件**: `phase2/compiler.py`

**核心类**:
```python
@dataclass
class CanonicalSpec:
    """标准知识规范"""
    spec_id: str
    spec_type: SpecType
    content: Dict[str, Any]
    metadata: Dict[str, Any]

@dataclass
class CompilationResult:
    """编译结果"""
    success: bool
    output: CanonicalSpec
    warnings: List[str]
    errors: List[str]
```

---

## 三、Gate 体系

### 3.1 Phase 2 Gates

| Gate ID | 名称 | 目的 | 级别 |
|---------|------|------|------|
| G1-P2 | 知识完整性 Gate | 验证知识完整性 | BLOCK |
| G2-P2 | 授权 Gate | 验证发布权限 | BLOCK |
| G3-P2 | 冲突检测 Gate | 检测知识冲突 | WARN |
| G4-P2 | 向后兼容 Gate | 验证向后兼容性 | WARN |

---

## 四、任务分解

### P0 - 启动任务 (本周)

| # | 任务 | 负责模型 | 预计时间 |
|---|------|----------|----------|
| P2-P0-1 | 创建 Phase 2 目录结构 | GLM-5.1 | 0.5h |
| P2-P0-2 | 实现 schema.py | GLM-5.1 | 2h |
| P2-P0-3 | 实现 G1-P2 Gate | Codex | 3h |
| P2-P0-4 | 实现 G2-P2 Gate | Codex | 3h |

### P1 - Teach Layer (第2周)

| # | 任务 | 负责模型 | 预计时间 |
|---|------|----------|----------|
| P2-P1-1 | Teach Capture 模块 | Codex | 1d |
| P2-P1-2 | Knowledge Parser 模块 | Codex | 2d |
| P2-P1-3 | 单元测试 | GLM-5.1 | 1d |

### P2 - Compiler Layer (第3周)

| # | 任务 | 负责模型 | 预计时间 |
|---|------|----------|----------|
| P2-P2-1 | Canonical Compiler | Codex | 2d |
| P2-P2-2 | Publish Contract | Codex | 1d |
| P2-P2-3 | 集成测试 | GLM-5.1 | 1d |

### P3 - 双周 Demo (持续)

| # | 任务 | 负责模型 |
|---|------|----------|
| P2-P3-1 | 后向台阶 case 端到端 | Codex |
| P2-P3-2 | 聚焦版评审 5 问 | Opus 4.6 |
| P2-P3-3 | L1→L2 权限升级评估 | Opus 4.6 |

---

## 五、验收标准

### 5.1 Phase 2 完成标准

- [ ] G1-P2/G2-P2 Gates 实现
- [ ] Teach Layer 完整实现
- [ ] Compiler Layer 完整实现
- [ ] 200+ tests 通过
- [ ] 后向台阶 E2E Demo 通过
- [ ] Opus 4.6 审查通过

### 5.2 L1→L2 升级条件

- [ ] 知识完整性 Gate (G1-P2) 100% 通过
- [ ] 授权 Gate (G2-P2) 人工确认
- [ ] 3+ 个真实 case 自动化验证
- [ ] 双周 Demo 评审通过

---

## 六、立即行动

1. **创建 Phase 2 目录结构** ✅
2. **实现 schema.py** (数据模型)
3. **实现 G1-P2 Gate** (知识完整性)
4. **实现 G2-P2 Gate** (授权)

---

**维护者**: GLM-5.1
**审查人**: Notion AI Opus 4.6
**状态**: 🔄 启动中
