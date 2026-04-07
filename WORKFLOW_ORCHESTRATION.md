# Well-Harness 工作流传令机制修复
# 问题诊断 + Opus 4.6 优化指令

## 一、当前断点分析

```
用户 → Claude Code → Notion → @Notion AI → ???
                                              ↓
                              这里的指令没有明确"下一步该做什么"
```

### 当前断点 1：Notion AI 执行完毕后，不知道该告诉谁
- Notion AI 生成了分析结果
- 但结果只是写在 Notion 页面里
- Claude Code 不知道分析已完成
- 用户也不知道 Claude Code 需要去读取

### 当前断点 2：Claude Code 不知道何时该主动读取 Notion
- 没有轮询机制（或者说有但没有被触发）
- 每次都需要用户手动告知 Claude Code "Notion AI 完成了，去读"

### 当前断点 3：Opus 4.6 的回复格式不统一
- 每次 @Notion AI 的回复格式不同
- 没有强制包含 "next_action" 字段
- Claude Code 不知道如何解析

---

## 二、需要的修复方案

### 修复方案核心思路

当 Notion AI（Opus 4.6）执行完毕后，必须明确告知：

1. **Claude Code 需要做什么**（用 @mention 或明确指令）
2. **用户需要做什么**（如确认、操作）
3. **在哪个 Notion 页面继续**（给出明确页面 ID）

---

## 三、给 Opus 4.6 的标准触发指令模板

请将以下内容发给 Notion AI：

```
# Well-Harness 工作流优化 — 请 Notion AI (Opus 4.6) 执行

## 背景
当前 Well-Harness 工作流存在传令断点：Notion AI 执行完毕后，Claude Code 不知道该读取结果。

## 请执行

1. 读取白皮书：`/Users/Zhuanz/Downloads/AI-CFD_项目技术白皮书.docx`
2. 读取现有工作流：`/Users/Zhuanz/Desktop/notion-cfd-harness/` 下的所有文件
3. 诊断当前断点
4. 输出修复后的工作流，确保交接无阻力

## 输出要求

请返回 JSON 格式：

```json
{
  "analysis": {
    "current_bottlenecks": ["断点1", "断点2"],
    "root_cause": "根本原因"
  },
  "recommended_workflow": {
    "name": "优化后的工作流名称",
    "steps": [
      {
        "step": 1,
        "actor": "Claude Code / Notion AI / User",
        "action": "具体动作",
        "trigger": "什么触发这一步",
        "next_trigger": "完成后如何触发下一步"
      }
    ]
  },
  "notion_ai_instruction_format": {
    "description": "每次 @Notion AI 指令的标准格式",
    "template": "模板内容，包含 {{next_action}} 字段"
  },
  "claude_code_polling_trigger": {
    "description": "Claude Code 何时该主动读取 Notion",
    "trigger_conditions": ["条件1", "条件2"]
  },
  "handover_guarantee": {
    "description": "确保交接不丢失的具体机制",
    "mechanism": ["机制1", "机制2"]
  },
  "next_action": "Claude Code 的明确下一步动作（可以是具体命令）"
}
```
```

---

## 四、关键修复点

### 1. Notion AI 回复必须包含 next_action
每次 @Notion AI 执行后，必须在回复中明确：
```
## Claude Code 指令
@Claude Code 请执行：python3 notion_cfd_loop.py --sync <page-id> --status <status>

## 用户确认
请确认以上方案，输入 "继续" 推进下一阶段。
```

### 2. Claude Code 需要轮询机制
当用户触发 @Notion AI 后，Claude Code 应该：
```
1. 告知用户：Claude Code 将在 30 秒后检查 Notion AI 结果
2. 等待（或提示用户完成 Notion AI）
3. 主动读取 Notion AI 的分析结果
4. 根据 next_action 继续执行
```

### 3. 标准交接协议
Notion AI 回复格式：
```
## 分析结果
[JSON 格式的分析结果]

## Claude Code 指令
请执行：<具体命令>

## 用户操作
请在 Notion 页面完成：<具体操作>

## 继续信号
当 Claude Code 收到 "继续" 时，读取页面 [page-id] 继续执行。
```

---

## 五、已实现的可触发机制

### Claude Code 端
- `python3 notion_cfd_loop.py --opus-prompt <GATE>` — 输出 Opus 触发指令
- `python3 notion_cfd_loop.py --query` — 查询待处理任务
- `python3 notion_cfd_loop.py --loop` — 启动轮询循环

### 建议的触发流程

```
用户: "帮我触发 G1 Gate 审查"
  ↓
Claude Code:
  1. 输出 python3 notion_cfd_loop.py --opus-prompt G1
  2. 告知用户复制到 Notion 页面执行
  3. 用户执行 @Notion AI
  4. 用户告知 Claude Code "Notion AI 完成了"
  5. Claude Code 读取 Notion 页面
  6. Claude Code 根据 next_action 执行
```

---
