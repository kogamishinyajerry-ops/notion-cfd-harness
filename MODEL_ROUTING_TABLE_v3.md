# 模型路由表 v3.0
**Well-Harness AI-CFD 项目专用**
**更新时间**: 2026-04-08
**适用范围**: Phase 1-5 全阶段

---

## 一、核心模型配置

### 1.1 当前工作环境

| 组件 | 模型 | 主要职责 |
|------|------|---------|
| **Claude Code 宿主** | GLM-5.1 (智谱AI) | 任务协调、Schema定义、测试、文档 |
| **核心代码实现** | **Codex (GPT-5.4)** | **复杂业务逻辑、核心算法、Gate实现** |
| **备选执行模型** | MiniMax-M2.7 | Codex不可用时的Fallback |
| **架构审查/验收** | **Opus 4.6** | ❌ 不直接调用 — 由用户手动在Notion AI中交互 |

### 1.2 模型调用方式

| 模型 | 调用方式 | 配置 |
|------|---------|------|
| GLM-5.1 | `python3 glmext.py "<prompt>"` | `ZHIPU_API_KEY` |
| MiniMax-M2.7 | `python3 minimix.py "<prompt>"` | `MINIMAX_API_KEY` |
| Codex (GPT-5.4) | **Skill: `codex:rescue`** | openai-codex 插件 |
| Opus 4.6 | 用户手动在Notion AI中交互 | 见 `notion_opus_prompts.md` |

### 1.3 Codex 调用时机（重要！）

**立即调用 Codex 的场景：**
- ✅ 实现新的 Module 核心类
- ✅ 实现复杂算法或业务逻辑
- ✅ 实现 Gate 检查逻辑
- ✅ 重构或优化现有代码
- ✅ 实现需要深度架构设计的功能

**GLM-5.1 直接处理的场景：**
- ✅ Schema 数据结构定义
- ✅ 简单工具函数
- ✅ 测试代码编写
- ✅ 文档更新
- ✅ 任务分解和协调

---

## 二、Phase 1 任务-模型映射表（重新设计）

### 2.1 Phase 1: 知识捕获（当前阶段）

| 任务类型 | **Primary Model** | Fallback | Code Review | 说明 |
|----------|-----------------|----------|-------------|------|
| **Schema定义** | GLM-5.1 | MiniMax-M2.7 | 跳过 | 数据结构，无复杂逻辑 |
| **Module 1: Result Parser** | **Codex** | GLM-5.1 | GLM-5.1 | 需处理复杂文件解析 |
| **Module 2: Skeleton Generator** | **Codex** | GLM-5.1 | GLM-5.1 | 核心功能，复杂逻辑 |
| **Module 3: Teach Mode Engine** | **Codex** | GLM-5.1 | GLM-5.1 | 核心功能，复杂逻辑 |
| **Module 4: ReportSpec Manager** | **Codex** | GLM-5.1 | GLM-5.1 | 核心功能，复杂逻辑 |
| **Module 5: C6 Replay Engine** | **Codex** | GLM-5.1 | GLM-5.1 | 核心功能，复杂逻辑 |
| **P1-G3/P4: Gates** | **Codex** | GLM-5.1 | **Opus 审查** | **关键质量控制** |
| **测试编写** | GLM-5.1 | MiniMax-M2.7 | 跳过 | 辅助工作 |
| **文档更新** | GLM-5.1 | MiniMax-M2.7 | 跳过 | 辅助工作 |

### 2.2 Phase 2: Knowledge Compiler

| 任务类型 | **Primary Model** | Fallback | Code Review | 说明 |
|----------|-----------------|----------|-------------|------|
| Compiler Core | **Codex** | GLM-5.1 | Codex CR | 核心编译逻辑 |
| Normalization | GLM-5.1 | MiniMax-M2.7 | Codex CR | 相对简单 |
| Diff Engine | **Codex** | GLM-5.1 | Opus 审查 | 复杂差分算法 |
| Publish Contract | **Codex** | GLM-5.1 | Opus 审查 | 关键发布流程 |

### 2.3 Phase 3: Orchestrator

| 任务类型 | **Primary Model** | Fallback | Code Review | 说明 |
|----------|-----------------|----------|-------------|------|
| Solver Runner | **Codex** | GLM-5.1 | Codex CR | 核心调度逻辑 |
| Mesh Builder | **Codex** | MiniMax-M2.7 | Codex CR | 复杂网格生成 |
| Physics Planner | **Opus 4.6** | Codex | Opus 自审 | 最复杂物理决策 |
| CAD Parser | **Codex** | GLM-5.1 | Codex CR | 复杂几何解析 |

### 2.4 Phase 4: Memory Network

| 任务类型 | **Primary Model** | Fallback | Code Review | 说明 |
|----------|-----------------|----------|-------------|------|
| Versioned Registry | **Codex** | GLM-5.1 | Codex CR | 版本控制核心 |
| Memory Node | GLM-5.1 | MiniMax-M2.7 | Codex CR | 相对简单 |
| Governance Engine | **Codex** | GLM-5.1 | **Opus 审查** | 治理核心逻辑 |
| Notion Memory Events | GLM-5.1 | MiniMax-M2.7 | 跳过 | 辅助功能 |

### 2.5 Phase 5: Performance & Security

| 任务类型 | **Primary Model** | Fallback | Code Review | 说明 |
|----------|-----------------|----------|-------------|------|
| Connection Pool | **Codex** | GLM-5.1 | Codex CR | 并发核心 |
| Auth | GLM-5.1 | MiniMax-M2.7 | **Opus 审查** | 相对简单 |
| Backup & Recovery | GLM-5.1 | MiniMax-M2.7 | Codex CR | 辅助功能 |

---

## 三、Codex 调用指南（核心）

### 3.1 Codex 实现模式

当需要实现核心功能时，GLM-5.1 应该：

```bash
# 1. 准备详细的实现需求
# 2. 调用 Codex 进行实现
node "/Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs" task \
  --model gpt-5.3-codex-spark \
  --prompt "实现 [具体功能]，要求：[详细要求]"
```

### 3.2 Codex 实现指令模板

**模板1：实现新 Module**
```
请实现 Phase 1 Module X: [模块名称]

## 背景
[项目背景和目标]

## 技术要求
1. 继承/实现自 [现有类]
2. 方法签名应符合 [接口规范]
3. 错误处理遵循 [项目规范]

## 核心功能
1. 功能A：[详细描述]
2. 功能B：[详细描述]
3. 功能C：[详细描述]

## 输出要求
- 完整的 Python 代码
- 符合项目编码规范
- 包含必要的 docstring
- 考虑边界条件处理
```

**模板2：实现 Gate**
```
请实现 P1-GX: [Gate名称]

## Gate 目的
[Gate的业务目标]

## 检查项
1. 检查项A：[详细说明]
2. 检查项B：[详细说明]
3. 检查项C：[详细说明]

## 通过标准
- [通过条件1]
- [通过条件2]
- [通过条件3]

## 接口要求
- 必须实现 check() 方法
- 返回统一的 GateResult 格式
- 兼容现有的 GateExecutor

## 输出要求
- 完整的 Python 代码
- 包含测试用例
- 遵循 Gate 实现规范
```

### 3.3 Codex 审查模式

```bash
# 代码审查
node "/Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs" adversarial-review \
  --focus "审查要点：[具体审查内容]"

# Bug 诊断
node "/Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs" task \
  --model gpt-5.3-codex-spark \
  --prompt "分析以下代码问题：[代码 + 问题描述]"
```

---

## 四、标准开发流程（更新）

### 4.1 核心功能实现流程

```
用户需求
  ↓
GLM-5.1: 任务分解 + 需求分析
  ↓
GLM-5.1: 判断任务类型
  ├─→ Schema/测试/文档 → GLM-5.1 直接实现
  └─→ 核心业务逻辑 → 调用 Codex 实现
       ↓
  Codex: 代码实现
       ↓
  GLM-5.1: 整合代码 + 编写测试
       ↓
  测试验证
       ↓
  Gate实现 → 用户手动 @Notion AI (Opus 4.6) → 架构验收
       ↓
  下一阶段
```

### 4.2 GLM-5.1 作为"协调者"的职责

1. **任务分解**：将大任务拆解为可执行的小任务
2. **模型选择**：判断每个子任务应该由哪个模型执行
3. **结果整合**：将 Codex 的实现结果整合到项目中
4. **测试编写**：为核心功能编写测试用例
5. **文档维护**：更新相关文档

### 4.3 Codex 作为"执行者"的职责

1. **核心代码实现**：实现复杂的业务逻辑和算法
2. **架构优化**：提供更好的架构建议
3. **问题诊断**：分析和修复复杂问题
4. **代码重构**：优化现有代码结构

---

## 五、Opus 4.6 审查流程（手动）

### 5.1 需要Opus审查的场景

| 场景 | 触发方式 | 审查内容 |
|------|---------|---------|
| **Gate 实现** | 用户手动@Notion AI | Gate逻辑完整性、边界条件 |
| **Phase 完成** | 用户手动@Notion AI | 架构合规性、知识模型正确性 |
| **架构变更** | 用户手动@Notion AI | 影响评估、风险分析 |
| **关键决策** | 用户手动@Notion AI | 技术选型、设计方案 |

### 5.2 Notion AI 触发指令

见 `notion_opus_prompts.md`，包含：
- P1-G3/P4 Gate 审查指令
- G0-G6 Gate 审查模板
- 架构审查模板
- 任务拆解审查模板

---

## 六、模型能力对比（更新）

| 能力 | GLM-5.1 | MiniMax-M2.7 | Codex (GPT-5.4) | Opus 4.6 |
|------|---------|-------------|-----------------|----------|
| 中文理解 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 代码实现 | ⭐⭐⭐⭐ | ⭐⭐⭐ | **⭐⭐⭐⭐⭐** | ⭐⭐⭐⭐⭐ |
| 核心算法 | ⭐⭐⭐ | ⭐⭐ | **⭐⭐⭐⭐⭐** | ⭐⭐⭐⭐⭐ |
| 架构设计 | ⭐⭐⭐ | ⭐⭐⭐ | **⭐⭐⭐⭐** | ⭐⭐⭐⭐⭐ |
| 任务协调 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Gate审查 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 调用方式 | Claude Code | minimix.py | **skill** | Notion AI |
| 响应速度 | 快 | 快 | 中 | 慢（手动） |
| **主要职责** | **协调** | 辅助 | **实现** | **审查** |

---

## 七、Codex 使用检查清单

实现新功能前，GLM-5.1 应该自问：

- [ ] 这个功能是否超过 50 行代码？
- [ ] 这个功能是否包含复杂算法？
- [ ] 这个功能是否是核心业务逻辑？
- [ ] 这个功能是否需要深度架构设计？
- [ ] 这个功能是否是 Gate 实现？

**如果任何一项为"是"，则应该调用 Codex 实现。**

---

## 八、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| **v3.0** | 2026-04-08 | **重新设计模型分工：Codex承担核心实现，GLM-5.1负责协调** |
| v2.0 | 2026-04-08 | 重新组织模型路由，明确GLM-5.1为主要模型 |
| v1.2 | 2026-04-07 | 增加Codex Code Review要求 |
| v1.1 | - | 加入fail-stop规则 |
| v1.0 | - | 初始版本 |

---

**维护者**: Well-Harness Team
**更新者**: GLM-5.1 (Claude Code环境)
**审查者**: 待 @Notion AI (Opus 4.6)

---

## 附录：快速参考

### 当需要实现新功能时

```python
# GLM-5.1 决策树
if 功能类型 in ["Schema", "测试", "文档"]:
    GLM_51_直接实现()
elif 复杂度 == "高" or 功能类型 in ["Gate", "Module核心"]:
    调用_Codex_实现()
else:
    if 有充足的_Codex_额度():
        调用_Codex_实现()  # 更高质量
    else:
        GLM_51_实现()
```
