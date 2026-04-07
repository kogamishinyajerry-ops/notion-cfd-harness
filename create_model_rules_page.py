#!/usr/bin/env python3
"""创建模型调用规范页面到Notion"""
import os, requests

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}
BASE = "https://api.notion.com/v1"
PARENT_ID = "33bc6894-2bed-819d-822a-c2144bb95e97"

def add_block(children, block_type, text, language=None):
    if language:
        children.append({
            "object": "block", "type": block_type,
            block_type: {"language": language, "rich_text": [{"text": {"content": text}}]}
        })
    else:
        children.append({
            "object": "block", "type": block_type,
            block_type: {"rich_text": [{"text": {"content": text}}]}
        })

children = []
add_block(children, "heading_1", "模型调用规范 (v1)")
add_block(children, "heading_2", "核心原则")
add_block(children, "bulleted_list_item", "Codex = 主执行模型，任何任务优先使用 Codex")
add_block(children, "bulleted_list_item", "Minimax/GLM = 降级备选（仅 Codex 不可用时）")
add_block(children, "bulleted_list_item", "Opus = 架构审查/Gate评审，唯一指定")

add_block(children, "heading_2", "模型分工表")
add_block(children, "paragraph", "M1-1: Codex (GPT-5.4) primary | Minimax fallback | Opus审查")
add_block(children, "paragraph", "M1-2: Minimax-2.7 primary | GLM-5.1 fallback | Opus审查")
add_block(children, "paragraph", "M1-3: GLM-5.1 primary | Codex fallback | Opus审查")
add_block(children, "paragraph", "M1-4/6: Codex (GPT-5.4) primary | Minimax fallback | Opus审查")
add_block(children, "paragraph", "M1-5: Opus 4.6 primary | Codex fallback | Opus审查")
add_block(children, "paragraph", "G3-G6: Codex (GPT-5.4) primary | Minimax fallback | Opus审查")
add_block(children, "paragraph", "架构审查: Opus 4.6 (唯一指定)")

add_block(children, "heading_2", "Codex 调用方法")
add_block(children, "heading_3", "检查状态")
add_block(children, "code", "node /Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs status --json", "bash")
add_block(children, "heading_3", "发起新任务")
add_block(children, "code", "node /Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs task --prompt '<任务>' --working-dir /Users/Zhuanz/Desktop/notion-cfd-harness", "bash")
add_block(children, "heading_3", "Resume现有任务")
add_block(children, "code", "node /Users/Zhuanz/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs task --resume --id <task-id>", "bash")

add_block(children, "heading_2", "GLM-5.1 调用方法")
add_block(children, "code", "python3 glmext.py '<prompt>' [--model glm-5.1]", "bash")
add_block(children, "code", "python3 glmext.py --task M1_3_WIZARD '<需求>'", "bash")
add_block(children, "paragraph", "API: ZHIPU_API_KEY | 端点: open.bigmodel.cn/api/coding/paas/v4")

add_block(children, "heading_2", "Minimax-2.7 调用方法")
add_block(children, "code", "python3 minimix.py '<prompt>'", "bash")
add_block(children, "code", "python3 minimix.py --task TASK_DECOMPOSE '<任务>'", "bash")
add_block(children, "paragraph", "API: MINIMAX_API_KEY | 端点: api.minimaxi.com/anthropic/v1")

add_block(children, "heading_2", "Opus 4.6 调用方法")
add_block(children, "paragraph", "在Notion页面中 @Opus 4.6 手动调用")
add_block(children, "paragraph", "架构审查/Gate评审 -> 必须通过Notion AI @Opus 4.6")

add_block(children, "heading_2", "降级规则")
add_block(children, "numbered_list_item", "Codex running -> 等待完成，不降级")
add_block(children, "numbered_list_item", "Codex available -> 直接调用")
add_block(children, "numbered_list_item", "Codex task-resume-candidate available=true -> resume而非新任务")
add_block(children, "numbered_list_item", "Codex 明确不可用(无认证/额度) -> 降级 Minimax")
add_block(children, "numbered_list_item", "Minimax失败 -> 降级 GLM-5.1")
add_block(children, "numbered_list_item", "GLM-5.1失败 -> 报告错误，不继续降级")

add_block(children, "heading_2", "禁止事项")
add_block(children, "bulleted_list_item", "禁止在我不知道Codex是否可用的前提下自行降级")
add_block(children, "bulleted_list_item", "禁止用Minimax替代Codex执行主开发任务")
add_block(children, "bulleted_list_item", "禁止跳过Opus进行架构审查")

payload = {
    "parent": {"page_id": PARENT_ID},
    "properties": {"title": [{"text": {"content": "模型调用规范"}}]},
    "children": children
}

resp = requests.post(f"{BASE}/pages", headers=HEADERS, json=payload, timeout=60)
if resp.ok:
    page = resp.json()
    print(f"OK: {page.get('id')}")
else:
    print(f"ERR: {resp.text[:300]}")
