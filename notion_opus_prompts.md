# Notion AI (Opus 4.6) 触发指令库
# Well-Harness 工作流中需要 Opus 4.6 介入时，复制对应指令到 Notion AI

---

## G0 Gate 审查

```
请作为 Well-Harness G0 任务门审查专家，分析当前任务页面的：

1. 任务ID和名称是否规范
2. 需求文档是否完整（包含 objective/scope/constraints）
3. 验收标准是否明确且可量化
4. Harness 规范约束是否已绑定
5. 当前 phase 状态与 Gate 节点是否匹配

【重要】只返回标准 JSON 格式，不要有其他文字、前缀或解释：
{"gate":"G0","pass":true,"checks":[{"check":"检查项","pass":true,"detail":"详情"}],"recommendations":["建议1"],"next_action":"下一步操作"}
```

---

## G1 认知门 - 知识库绑定

```
请作为 Well-Harness G1 认知门专家，审查当前任务的知识库绑定情况：

1. 检索组件库，列出与本任务相关的组件及其版本状态
2. 检索案例库，列出与本任务物理场景相似的历史案例
3. 检索规则库，列出适用于本任务的 Harness 规范条款
4. 检索基准库，列出可用于对比验证的基准数据
5. 评估知识库完整度，识别缺失项

【重要】只返回标准 JSON 格式，不要有其他文字、前缀或解释：
{"gate":"G1","pass":true,"components":[{"id":"...","name":"...","version":"...","relevance":"高"}],"cases":[...],"rules":[...],"baselines":[...],"knowledge_gaps":["缺失项"],"next_action":"下一步操作"}
```

---

## G2 配置门 - 规划审查

```
请作为 Well-Harness G2 配置门专家，审查当前任务的规划配置：

1. 验证 phase 规划是否覆盖完整开发流程
2. 检查每个 phase 的输入/输出定义是否清晰
3. 评估资源配置（模型选择、工具链）是否合理
4. 检查风险识别和缓解措施是否充分
5. 验证与 Harness 规范的合规性

【重要】只返回标准 JSON 格式，不要有其他文字、前缀或解释：
{"gate":"G2","pass":true,"phase_coverage":{"complete":true,"gaps":[]},"resource_plan":{"合理性":"..."},"risk_assessment":{"high_risks":[],"mitigations":[]},"compliance_check":{"passed":true,"violations":[]},"next_action":"下一步操作"}
```

---

## G3 执行门 - 开发审查

```
请作为 Well-Harness G3 执行门专家，审查当前任务的开发执行情况：

1. 检查开发进度是否符合 phase 规划
2. 验证代码实现是否遵循 Harness 编码规范
3. 评估中间结果的正确性和完整性
4. 识别开发中的阻塞点和风险
5. 判断是否可以进入验证阶段

【重要】只返回标准 JSON 格式，不要有其他文字、前缀或解释：
{"gate":"G3","pass":true,"progress":{"planned":"X%","actual":"Y%"},"code_quality":{"规范符合度":"...","issues":[]},"blockers":[],"next_action":"下一步操作"}
```

---

## G4 运行门 - 结果验证

```
请作为 Well-Harness G4 运行门专家，审查 CFD 运行结果：

1. 对比基准库数据，验证结果准确性
2. 检查收敛性指标（残差、监控点）是否达标
3. 评估结果物理一致性（守恒性、对称性等）
4. 与历史相似案例对比，识别异常
5. 判断是否可以进入审批阶段

【重要】只返回标准 JSON 格式，不要有其他文字、前缀或解释：
{"gate":"G4","pass":true,"baseline_comparison":{"matched":true,"delta":"..."},"convergence":{"converged":true,"details":"..."},"physics_consistency":{"passed":true,"issues":[]},"anomalies":[],"next_action":"下一步操作"}
```

---

## G5 验证门 - 审批

```
请作为 Well-Harness G5 验证门专家，执行最终审批：

1. 核对所有 Gate 检查记录是否完整
2. 验证验收标准是否全部满足
3. 检查文档完整性（API文档、用户手册）
4. 评估项目是否达到发布标准
5. 给出最终审批结论

【重要】只返回标准 JSON 格式，不要有其他文字、前缀或解释：
{"gate":"G5","pass":true,"gate_completeness":{"all_passed":true,"failed_gates":[]},"acceptance_criteria":{"met":true,"outstanding":[]},"documentation":{"complete":true,"missing":[]},"final_decision":"APPROVED/REJECTED","next_action":"下一步操作"}
```

---

## G6 写回门 - 知识归档

```
请作为 Well-Harness G6 写回门专家，审查知识归档：

1. 评估本任务是否值得沉淀为案例
2. 检查提取的关键知识（组件、规则、参数）是否完整
3. 验证对组件库/规则库的贡献是否准确
4. 确认所有相关库已更新
5. 生成案例摘要

【重要】只返回标准 JSON 格式，不要有其他文字、前缀或解释：
{"gate":"G6","pass":true,"case_candidate":{"worthy":true,"reason":"..."},"knowledge_extraction":{"components":[],"rules":[],"parameters":[]},"library_updates":{"completed":true,"pending":[]},"case_summary":"案例一句话描述","next_action":"下一步操作"}
```

---

## 架构审查（任意阶段）

```
请作为 Well-Harness 架构审查专家，执行深度审查：

1. 评估当前实现的架构合理性
2. 识别技术债和架构腐化点
3. 检查模块解耦和接口设计
4. 评估可扩展性和可维护性
5. 提出改进建议

【重要】只返回标准 JSON 格式，不要有其他文字、前缀或解释：
{"review_type":"ARCHITECTURE","overall_score":"8/10","strengths":["优点1"],"technical_debts":[{"debt":"...","severity":"高","suggestion":"..."}],"interface_design":{"评分":"...","issues":[]},"improvements":["改进1"],"next_action":"下一步操作"}
```

---

## 任务拆解审查

```
请作为 Well-Harness 任务规划专家，审查并优化任务拆解：

1. 评估子任务粒度是否合适
2. 识别可并行的子任务
3. 检查任务依赖关系是否正确
4. 补充遗漏的子任务（如测试、文档）
5. 优化执行顺序
6. 推荐最适合各子任务的 AI 模型

【重要】只返回标准 JSON 格式，不要有其他文字、前缀或解释：
{"review_type":"TASK_DECOMPOSITION","original_tasks":["原始任务1"],"improved_tasks":[{"id":"...","description":"...","parallel_with":[],"model":"...","estimated_phase":"..."}],"execution_order":["task_1","task_2"],"estimated_total_phases":3,"risks":["风险1"],"next_action":"下一步操作"}
```

---

## 使用说明

当 Claude Code 工作流遇到需要 Opus 4.6 介入的情况时：

1. Claude Code 输出当前需要的指令模板（上面任意一个）
2. 用户复制指令到 Notion 页面
3. 用户点击页面上的 **@Notion AI** 按钮
4. Notion AI 执行分析并生成结果（只返回 JSON）
5. 用户通知 Claude Code 继续执行
6. Claude Code 读取 Notion AI 的分析结果并继续工作流

---
