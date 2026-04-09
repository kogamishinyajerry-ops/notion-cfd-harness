# AI-CFD Knowledge Harness 项目规划
**AI-Driven CFD Knowledge System**

**版本**: 2.0
**日期**: 2026-04-09
**状态**: Project Accepted (v1.0.0 released)
**审查**: REV-PROJECT-001 Approved by Opus 4.6

---

## 一、项目愿景

### 1.1 核心目标

构建一个**知识驱动的 CFD 自动化平台**，实现：

- **知识捕获**: 自动从工程师操作中提取知识
- **知识积累**: 建立可复用的 CFD 知识库
- **知识应用**: 新案例自动应用历史知识（类比推理）
- **质量保证**: Gate 机制确保 AI 输出质量
- **持续演化**: 知识库随使用不断优化（版本追踪 + 治理）

### 1.2 核心价值

| 痛点 | 解决方案 |
|------|----------|
| 每次案例重复设置后处理 | ReportSpec 模板复用 |
| AI 输出不可靠 | Gate 质量验证 (G1-G6) |
| 知识散落在个人经验中 | Teach Mode 知识捕获 |
| 难以验证 AI 结果 | Gold Standards 基准 |
| 无法追踪知识演化 | Memory Network 版本控制 |
| 新案例无法利用已有知识 | E1-E6 类比推理引擎 |
| 生产环境安全不可控 | PermissionLevel L0-L3 + RBAC |

---

## 二、系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI-CFD Knowledge Harness v1.0                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Phase 5: Production Readiness & Operations  ✅  │   │
│  │  Cache Layer | Connection Pool | Metrics | Auth | Backup     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Phase 4: Governed Memory Network             ✅  │   │
│  │  Versioned Registry | Propagation | Governance | Code Map   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Phase 3: Analogical Orchestrator              ✅  │   │
│  │  E1 Similarity | E2 Decompose | E3 Plan | E4 Trial         │   │
│  │  E5 Evaluate | E6 Failure Handler                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Phase 2: Execution + Governance               ✅  │   │
│  │  Physics Planner | Result Validator | Failure Handler       │   │
│  │  Postprocess Runner | Pipeline | Benchmark Replay           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Phase 1: Knowledge Compiler                   ✅  │   │
│  │  NL Parser | Gates (G1/G2) | Gold Standards | Teach Mode    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
NL Input → Phase 1 (解析) → Phase 2 (执行 + 治理)
                              ↓
         Phase 3 (类比推理 ← E1→E6 pipeline)
                              ↓
         Phase 4 (知识版本化 + 治理策略)
                              ↓
         Phase 5 (生产就绪 + 运维保障)
```

---

## 三、Phase 划分与里程碑

### 3.1 Phase 总览

| Phase | 名称 | 核心目标 | 状态 | LOC | Tests |
|-------|------|----------|------|-----|-------|
| **Phase 1** | Knowledge Compiler | NL 解析、Gate 验证、黄金样板 | ✅ Pass | ~2,000 | ~200 |
| **Phase 2** | Execution + Governance | 执行层、治理、Pipeline | ✅ Pass (8.5/10) | ~3,500 | ~500 |
| **Phase 3** | Analogical Orchestrator | E1-E6 类比推理引擎 | ✅ Pass (8.5/10) | 5,561 | 352 |
| **Phase 4** | Governed Memory Network | 版本追踪、治理、代码映射 | ✅ Pass | 3,613 | 116 |
| **Phase 5** | Production Readiness | 性能、安全、运维 | ✅ Pass | 5,211 | 301 |
| **总计** | | | ✅ Accepted | **~19,885** | **1,619** |

### 3.2 Phase 1: Knowledge Compiler ✅

**目标**: 建立知识捕获基础设施

| 模块 | 状态 | 测试 | 说明 |
|------|------|------|------|
| Schema | ✅ | 25 | 数据模型 |
| Manager | ✅ | 28 | ReportSpec 管理 |
| Teach Mode | ✅ | 43 | 教学捕获 |
| Gates (G1/G2) | ✅ | 13 | 质量门 |
| NL Postprocess | ✅ | 53 | 自然语言 |
| Visualization | ✅ | 17 | 可视化 |
| Gold Standards | ✅ | 21 | 黄金样板 |
| **E2E Demo** | ✅ | 19 | 端到端 |
| **总计** | ✅ | **321** | |

**完成日期**: 2026-04-08

### 3.3 Phase 2: Execution + Governance ✅

**目标**: 建立执行层和治理能力

| 组件 | 状态 | 说明 |
|------|------|------|
| Physics Planner | ✅ | 求解器选择矩阵 (53/53 测试) |
| Result Validator | ✅ | 异常检测 |
| Failure Handler | ✅ | PermissionLevel L0-L3 |
| Postprocess Runner + Adapter | ✅ | 数据流适配 |
| Correction Recorder | ✅ | 学习闭环 |
| Benchmark Replay Engine | ✅ | 基准复现 |
| Pipeline Orchestrator | ✅ | E2E 编排 |

**审查评分**: 8.5/10 (REV-97A27E R1-R5)

### 3.4 Phase 3: Analogical Orchestrator ✅

**目标**: 实现类比推理引擎

| 组件 | 状态 | 说明 |
|------|------|------|
| E1 SimilarityEngine | ✅ | 对数归一化 + 硬约束 |
| E2 AnalogyDecomposer | ✅ | 维度分解 |
| E3 CandidatePlanGenerator | ✅ | A/B/C 方案 |
| E4 TrialRunner | ✅ | PermissionLevel L0-L3 集成 |
| E5 TrialEvaluator | ✅ | Gate + Mock 防护 |
| E6 AnalogyFailureHandler | ✅ | 四层安全防护 |
| Cold Start Whitelist | ✅ | 30 cases |

**审查评分**: 8.5/10 (REV-P3-001~003, 三轮审查)

### 3.5 Phase 4: Governed Memory Network ✅

**目标**: 建立知识演化追踪系统

| 组件 | 状态 | 说明 |
|------|------|------|
| VersionedKnowledgeRegistry | ✅ | 版本化注册表 |
| MemoryNode 数据模型 | ✅ | 记忆节点 |
| PropagationEngine | ✅ | 传播引擎 |
| GovernanceEngine | ✅ | 治理执行 |
| CodeMappingRegistry | ✅ | 代码映射 |
| MemoryNetwork 主编排器 | ✅ | 编排 |
| Gate 层 (G3-G6) | ✅ | 质量门 |
| Notion Memory Events | ✅ | Notion 集成 |

### 3.6 Phase 5: Production Readiness ✅

**目标**: 生产环境就绪

| 组件 | 状态 | 说明 |
|------|------|------|
| Cache Layer (L1 TTLCache + L2 Redis) | ✅ | 缓存 |
| Index Manager | ✅ | 版本历史索引 |
| Connection Pool | ✅ | Notion API 连接池 |
| Metrics Collection | ✅ | 指标采集 |
| Structured Logging | ✅ | JSON + correlation_id |
| Request Tracing | ✅ | structlog |
| Access Control (AuthN + RBAC) | ✅ | 认证授权 |
| Audit Logging | ✅ | 审计日志 |
| Backup & Recovery | ✅ | 备份恢复 |

---

## 四、项目指标

### 4.1 关键里程碑

| 里程碑 | 日期 | 状态 |
|--------|------|------|
| M1: Phase 1 完成 | 2026-04-08 | ✅ |
| M2: Phase 1 审查通过 | 2026-04-08 | ✅ |
| M3: Phase 2 完成 | 2026-04-09 | ✅ |
| M4: Phase 3 完成 | 2026-04-09 | ✅ |
| M5: Phase 4 完成 | 2026-04-09 | ✅ |
| M6: Phase 5 完成 | 2026-04-09 | ✅ |
| **M7: 项目整体验收** | **2026-04-09** | **✅ REV-PROJECT-001 Approved** |
| **v1.0.0 Release** | **2026-04-09** | **✅ Tagged** |

### 4.2 开发历程

| 指标 | 值 |
|------|-----|
| 分析会话数 | 21 |
| 关键决策 | 18 |
| 失败尝试 | 8 |
| 审查轮次 | 8 |
| Opus 审查 | 4 次 |
| 全量回归 | 1,619 passed, 0 failed |
| 测试密度 | 1 test / 12.3 LOC |

### 4.3 评分演进

| Phase | 初审评分 | 最终评分 |
|-------|----------|----------|
| Phase 2a | 6.5 | 8.5 |
| Phase 2b | 7.5 | 8.5 |
| Phase 2c | 8.0 | 8.5 |
| Phase 3 | 8.0 | 8.5 |

---

## 五、安全措施

| 措施 | Phase | 状态 |
|------|-------|------|
| No Data Fabrication (mock 防护) | Phase 3 E5 | ✅ |
| PermissionLevel (L0-L3) | Phase 2/3 | ✅ |
| RBAC 权限系统 | Phase 5 | ✅ |
| 审计日志 | Phase 5 | ✅ |
| Secret 管理 | Phase 5 | ✅ |
| RelaxationBoundary | Phase 3 E6 | ✅ |

### 待关注项 (Phase 6+)

| 项目 | 优先级 | 说明 |
|------|--------|------|
| Notion API Token 轮换 | P2 | 当前为长期集成 token |
| HTTP API 认证 | Phase 6 | 当前仅 CLI 模式 |
| 数据加密 | Phase 6 | 知识库未加密 |

---

## 六、交付物

### 6.1 代码交付物

| Phase | LOC | Tests | 文件 |
|-------|-----|-------|------|
| Phase 1 | ~2,000 | ~200 | knowledge_compiler/ |
| Phase 2 | ~3,500 | ~500 | knowledge_compiler/phase2/ |
| Phase 3 | 5,561 | 352 | knowledge_compiler/phase3/ |
| Phase 4 | 3,613 | 116 | knowledge_compiler/memory_network/ |
| Phase 5 | 5,211 | 301 | knowledge_compiler/performance+observability+security+operations/ |
| **总计** | **~19,885** | **1,619** | **66 test files** |

### 6.2 文档交付物

| 文档 | 说明 |
|------|------|
| PHASE1_ARCHITECTURE_OVERVIEW.md | Phase 1 架构 |
| PHASE4_ARCHITECTURE.md | Phase 4 架构 |
| Phase4_PLAN.md / Phase5_PLAN.md | Phase 4/5 规划 |
| OPUS_REVIEW_PHASE3_ACCEPTANCE.md | Phase 3 验收 |
| OPUS_REVIEW_PROJECT_ACCEPTANCE.md | 项目整体验收 |
| PROJECT_ROADMAP.md | 本文件 |
| Phase4_BASELINE_MANIFEST.json | Phase 4 基线 |

---

**维护者**: AI-CFD Knowledge Harness Team
**最后更新**: 2026-04-09
**版本**: v1.0.0 (Released)
