#!/usr/bin/env python3
"""更新模型调用规范页面为v1.1强制执行版"""
import os, requests

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
if not NOTION_API_KEY:
    raise RuntimeError("NOTION_API_KEY 环境变量未设置")
HEADERS = {"Authorization": f"Bearer {NOTION_API_KEY}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
BASE = "https://api.notion.com/v1"
PAGE_ID = "33bc6894-2bed-81c1-8e65-fdc4befbc61d"

def rt(text):
    return {"rich_text": [{"text": {"content": text}}]}

def code(text):
    return {"object": "block", "type": "code", "code": {"language": "bash", "rich_text": [{"text": {"content": text}}]}}

def h1(text):
    return {"object": "block", "type": "heading_1", "heading_1": rt(text)}

def h2(text):
    return {"object": "block", "type": "heading_2", "heading_2": rt(text)}

def h3(text):
    return {"object": "block", "type": "heading_3", "heading_3": rt(text)}

def p(text):
    return {"object": "block", "type": "paragraph", "paragraph": rt(text)}

def bullet(text):
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": rt(text)}

def numbered(text):
    return {"object": "block", "type": "numbered_list_item", "numbered_list_item": rt(text)}

children = [
    h1("模型调用规范 (v1.1) - 强制执行版"),

    h2("核心原则（不可违背）"),
    bullet("模型即责任边界：每个任务类型绑定唯一执行模型，不可跨越"),
    bullet("失败即阻塞：模型调用失败时，执行必须立即停止，不降级、不重试、不跳过"),
    bullet("未验证不执行：在不知道目标模型是否可用的前提下，禁止自行决定降级"),

    h2("模型分工表（严格绑定）"),
    p("M1-1 状态机引擎 | Codex (GPT-5.4) | 无降级 | Opus审查"),
    p("M1-2 G0任务门 | Minimax-2.7 | 无降级 | Opus审查"),
    p("M1-3 Task向导 | GLM-5.1 | 无降级 | Opus审查"),
    p("M1-4/6 pytest测试 | Codex (GPT-5.4) | 无降级 | Opus审查"),
    p("M1-5 Evidence库 | Opus 4.6 | 无降级 | Opus审查"),
    p("G3-G6 Gate | Codex (GPT-5.4) | 无降级 | Opus审查"),
    p("架构审查 | Opus 4.6 | 禁止降级 | Opus审查"),
    p("v1架构迁移 | Codex (GPT-5.4) | 无降级 | Opus审查"),
    p("文档更新 | Codex (GPT-5.4) | 无降级 | Opus审查"),
    p("知识抽取/绑定 | GLM-5.1 | 无降级 | Opus审查"),

    h2("Codex 调用规范"),
    h3("判断规则"),
    p("IF Codex running -> 等待完成（不降级）"),
    p("ELIF Codex available -> 直接调用"),
    p("ELIF Codex available=false（明确不可用）-> 使用任务指定的降级模型"),
    p("ELIF 未知（未验证状态）-> 先验证，不自行降级"),
    h3("验证状态命令（bash）"),
    code("node /Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs status --json"),
    h3("发起新任务-阻塞式（bash）"),
    code("node /Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs task --fresh \"任务描述\""),
    h3("发起新任务-后台（bash）"),
    code("node /Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs task --fresh --background \"任务描述\""),
    h3("Resume任务（bash）"),
    code("node /Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs task --resume --id <task-id>"),

    h2("GLM-5.1 调用规范"),
    p("触发条件：任务类型=M1-3 或 知识抽取/绑定，且 Codex 不可用（已验证）"),
    code("python3 glmext.py --task M1_3_WIZARD '需求描述'"),
    code("python3 glmext.py --task TASK_DECOMPOSE '任务描述'"),
    p("失败处理：GLM-5.1调用失败 -> 立即停止，报告错误，不降级"),

    h2("Minimax-2.7 调用规范"),
    p("触发条件：任务类型=M1-2，且 Codex 不可用（已验证）"),
    code("python3 minimix.py --task TASK_DECOMPOSE '任务描述'"),
    code("python3 minimix.py --task VALIDATE_GATE --task-id 'id' --gate 'G0'"),
    p("失败处理：Minimax调用失败 -> 立即停止，报告错误，不降级"),

    h2("Opus 4.6 调用规范"),
    p("触发条件：任务类型=架构审查 或 Gate评审"),
    p("调用方式：在 Notion 页面中 @Opus 4.6 输入审查 prompt"),
    p("标准审查模板：【架构审查 - Well-Harness v1】请对[对象]深度审查并给出修复建议"),
    p("失败处理：Opus调用失败 -> 立即停止，报告错误"),

    h2("强制规则：失败即阻塞"),
    h3("什么是调用失败"),
    bullet("模型返回错误"),
    bullet("模型返回超时"),
    bullet("模型返回空结果"),
    bullet("状态验证返回 available=false 且无备选"),
    h3("失败后正确行为"),
    numbered("立即停止当前执行流"),
    numbered("打印错误信息：[模型调用失败] 模型名 | 失败原因"),
    numbered("不降级到其他模型"),
    numbered("不重试"),
    numbered("等待人工介入"),
    h3("禁止行为"),
    bullet("禁止：Codex失败后用Minimax试试"),
    bullet("禁止：Codex超时后等一下再试"),
    bullet("禁止：Opus返回错误跳过审查继续"),
    bullet("禁止：不确定Codex是否可用先用Minimax"),

    h2("Codex 挂死检测与处理"),
    p("识别：任务运行超2小时且无新活动视为挂死"),
    numbered("运行状态验证命令"),
    numbered("如确认挂死：调用 cancel 停止任务"),
    numbered("重新发起新任务"),
    p("禁止：发现挂死后不取消就发起新任务"),

    h2("禁止事项（违反即停）"),
    bullet("禁止未知状态下降级：未验证Codex可用性就自行降级 -> 立即停止"),
    bullet("禁止跳过指定模型：任务要求Opus但自行用Codex -> 立即停止"),
    bullet("禁止失败后继续：模型调用失败后继续执行 -> 立即停止"),
    bullet("禁止隐藏降级：不告知就擅自使用备选模型 -> 立即停止"),
    bullet("禁止并发调用：同时运行多个Codex任务 -> 禁止"),
    bullet("禁止在审查完成前推进：Gate评审未通过就进入下一阶段 -> 立即停止"),

    h2("执行检查清单（每次任务前必查）"),
    numbered("确认任务类型"),
    numbered("确认指定执行模型"),
    numbered("验证模型可用性（status命令）"),
    numbered("如可用：发起调用"),
    numbered("如不可用且无降级规则：立即停止"),
    numbered("如不可用且有降级规则：使用降级模型"),
    numbered("调用失败：立即停止"),
    numbered("任务完成：记录到执行日志"),
    numbered("推送GitHub（代码变更必须同步）"),
]

payload = {"children": children}
resp = requests.patch(f"{BASE}/blocks/{PAGE_ID}/children", headers=HEADERS, json=payload, timeout=60)
if resp.ok:
    print(f"OK: {len(children)} blocks written")
else:
    print(f"ERR: {resp.text[:300]}")
