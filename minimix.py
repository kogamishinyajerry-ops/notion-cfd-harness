#!/usr/bin/env python3
"""
MiniMax-M2.7 API 封装 — Well-Harness 备选执行模型
智谱 AI MiniMax 系列 (api.minimaxi.com)

用法:
  python3 minimix.py "<prompt>"
  python3 minimix.py --task TASK_DECOMPOSE "<任务描述>"
  python3 minimix.py --task VALIDATE_GATE --task-id "<id>" --gate "G0"
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime

# ============ 配置 ============
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimaxi.com/anthropic/v1"

DEFAULT_MODEL = "MiniMax-M2.7"

# ============ MiniMax 客户端 ============

class MiniMaxClient:
    """MiniMax-M2.7 客户端 (Anthropic 兼容格式)"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or MINIMAX_API_KEY
        if not self.api_key:
            raise ValueError("API key 未设置，请设置 MINIMAX_API_KEY 环境变量")

    def chat(self, prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """
        调用 MiniMax chat completion
        返回纯文本内容（不含 thinking）
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(f"{MINIMAX_BASE_URL}/messages", headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        # 提取 text 类型内容，过滤 thinking
        content = data.get("content", [])
        for block in content:
            if block.get("type") == "text":
                return block.get("text", "")
        # 如果没有 text 块，返回空
        return ""

    def decompose_task(self, task_desc: str) -> dict:
        """任务拆解"""
        prompt = f"""你是 Well-Harness AI-CFD 系统的任务分解专家。

用户需求: {task_desc}

请将上述需求拆解为结构化的子任务列表，返回 JSON 格式:
{{
  "main_task": "主任务名称",
  "sub_tasks": [
    {{
      "id": "task_1",
      "description": "子任务描述",
      "model_recommend": "推荐模型",
      "estimated_phase": "Phase编号",
      "acceptance_criteria": "验收标准"
    }}
  ],
  "execution_order": ["task_1", "task_2", ...],
  "parallel_possible": ["可并行的任务列表"]
}}

只输出 JSON，不要其他内容。"""
        result = self.chat(prompt, temperature=0.3, max_tokens=2048)
        try:
            # 去掉可能的 ```json 包装
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"error": "JSON解析失败", "raw": result}

    def validate_gate(self, task_id: str, gate: str, context: dict = None) -> dict:
        """Gate 校验"""
        ctx = json.dumps(context or {}, ensure_ascii=False, indent=2)
        prompt = f"""你是 Well-Harness Gate 校验专家。

任务ID: {task_id}
Gate: {gate}
上下文: {ctx}

请执行 {gate} 校验，返回:
{{
  "pass": true/false,
  "evidence": {{
    "gate": "{gate}",
    "task_id": "{task_id}",
    "checks": [{{"check": "检查项名", "pass": true/false, "detail": "详情"}}],
    "result": "PASS/FAIL",
    "message": "校验说明"
  }}
}}

只输出 JSON。"""
        result = self.chat(prompt, temperature=0.2, max_tokens=1024)
        try:
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"error": "JSON解析失败", "raw": result}


# ============ CLI 入口 ============

def main():
    parser = argparse.ArgumentParser(description="MiniMax-M2.7 Well-Harness 任务执行器")
    parser.add_argument("prompt", nargs="?", help="直接输入 prompt")
    parser.add_argument("--task", choices=["TASK_DECOMPOSE", "VALIDATE_GATE"], help="预设任务类型")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型名称 (默认: {DEFAULT_MODEL})")
    parser.add_argument("--task-id", default="unknown", help="关联任务ID")
    parser.add_argument("--gate", default="G0", help="Gate编号")
    parser.add_argument("--context", type=json.loads, default={}, help="额外上下文 (JSON)")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=4096)

    args = parser.parse_args()

    if not args.prompt and not args.task:
        parser.print_help()
        print("\n示例:")
        print('  python3 minimix.py "帮我规划CFD后处理模块开发"')
        print('  python3 minimix.py --task TASK_DECOMPOSE "开发Copilot入口"')
        print('  python3 minimix.py --task VALIDATE_GATE --task-id "AI-CFD-001" --gate "G0"')
        return

    client = MiniMaxClient()

    if args.task == "TASK_DECOMPOSE":
        result = client.decompose_task(args.prompt or str(args.context))
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.task == "VALIDATE_GATE":
        result = client.validate_gate(args.task_id, args.gate, args.context)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        result = client.chat(args.prompt, model=args.model, temperature=args.temperature, max_tokens=args.max_tokens)
        print(result)


if __name__ == "__main__":
    main()
