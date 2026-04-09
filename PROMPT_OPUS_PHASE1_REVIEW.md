# Opus 4.6 Phase 1 架构审查指令

## 使用说明

1. 复制下方指令块
2. 在 Notion 中创建 Phase 1 审查页面
3. 粘贴指令内容
4. 点击 @Notion AI 执行
5. 将结果返回给 Claude Code

---

## 审查指令（复制到 Notion AI）

```
请作为 Well-Harness Phase 1 架构审查专家，对 Phase 1: Standard Knowledge Collector 执行深度架构审查。

## 审查背景

Phase 1 是 Well-Harness 的知识捕获层，已完成实现并通过 321 测试。

### 核心模块
1. **Schema**: 数据模型定义 (8 dataclasses, 6 enums)
2. **Manager**: ReportSpec 生命周期管理
3. **Skeleton**: 报告骨架生成器
4. **Teach**: 教学模式核心 (CorrectionSpec, TeachModeEngine)
5. **Replay**: 历史重放引擎
6. **Gates**: P1-G1/P3/P4 质量门
7. **NL Postprocess (F2)**: 自然语言解析
8. **Visualization (F3)**: 可视化执行引擎
9. **Gold Standards**: 黄金标准参考实现

### 架构特点
- 数据驱动: ReportSpec 作为核心知识载体
- 教学捕获: CorrectionSpec 记录工程师修正
- Gate 机制: P1-G1/P3/P4 质量验证
- 双语支持: 中英文自然语言交互

## 审查要点

### 1. 架构合理性
- 模块划分是否清晰？
- 职责分离是否恰当？
- 接口设计是否一致？
- 依赖方向是否正确？

### 2. 可扩展性
- 新增问题类型是否容易？
- 新增 Gate 是否方便？
- NL 解析是否可扩展？
- 是否支持多求解器？

### 3. 可维护性
- 代码结构是否清晰？
- 命名是否一致？
- 文档是否完整？
- 测试覆盖是否充分？

### 4. 技术风险
- 是否存在过度设计？
- 是否存在技术债？
- MOCK 模式是否影响开发？
- Gate 机制是否完备？

### 5. 与后续 Phase 的集成
- Phase 1 输出是否满足 Phase 2 需求？
- 数据模型是否稳定？
- 接口是否易于扩展？

## 审查输出要求

请按以下格式输出审查结果（只返回 JSON，不要有其他文字）：

```json
{
  "review_type": "PHASE1_ARCHITECTURE",
  "overall_score": "X/10",
  "approval_status": "APPROVED/APPROVED_WITH_CONDITIONS/NEEDS_REVISION",
  "strengths": [
    "优点1: 详细说明",
    "优点2: 详细说明"
  ],
  "technical_debts": [
    {
      "debt": "技术债描述",
      "severity": "HIGH/MEDIUM/LOW",
      "suggestion": "改进建议",
      "priority": "P0/P1/P2"
    }
  ],
  "architecture_assessment": {
    "modularity": {"score": "X/10", "comment": "评价"},
    "extensibility": {"score": "X/10", "comment": "评价"},
    "maintainability": {"score": "X/10", "comment": "评价"},
    "testability": {"score": "X/10", "comment": "评价"}
  },
  "interface_design": {
    "consistency": "评价",
    "completeness": "评价",
    "documentation": "评价",
    "issues": ["问题1", "问题2"]
  },
  "gate_mechanism": {
    "coverage": "P1-G1/P3/P4 覆盖是否充分",
    "effectiveness": "Gate 是否能有效拦截问题",
    "gaps": ["缺失的 Gate 1", "缺失的 Gate 2"]
  },
  "improvements": [
    {"priority": "P0", "action": "改进建议1", "rationale": "理由"},
    {"priority": "P1", "action": "改进建议2", "rationale": "理由"}
  ],
  "blockers_for_phase2": [
    "阻塞 Phase 2 的问题1",
    "阻塞 Phase 2 的问题2"
  ],
  "recommendations": [
    "建议1",
    "建议2"
  ],
  "next_action": "下一步操作建议"
}
```

## 特别关注

1. **Teach Mode 机制**: CorrectionSpec 设计是否合理？能否有效捕获知识？
2. **Gate 机制**: P1-G1/P3/P4 是否足够？是否需要 G2/G5/G6？
3. **NL Postprocess**: 中英文解析是否均衡？是否可扩展到更多意图？
4. **Visualization 接口**: MOCK 模式是否会影响 Phase 2+？
5. **数据模型稳定性**: ReportSpec 结构是否需要调整以适应 Phase 2+？

---

**重要**: 只返回标准 JSON 格式，不要有其他文字、前缀或解释。
```
