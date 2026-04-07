#!/usr/bin/env python3
"""
GLM-5.1 API 封装 — Well-Harness M1-3 Task向导 / 通用中文NLP
智谱 AI (open.bigmodel.cn) API

用法:
  python3 glmext.py "<prompt>" [--model glm-5] [--stream]
  python3 glmext.py --task M1_3_WIZARD "<用户需求描述>"
  python3 glmext.py --task TASK_DECOMPOSE "<任务描述>"
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime

# ============ 配置 ============
_key_env = os.environ.get("ZHIPU_API_KEY") or os.environ.get("GLM_API_KEY")
if _key_env:
    GLM_API_KEY = _key_env
else:
    try:
        GLM_API_KEY = open(os.path.expanduser("~/.glm_key")).read().strip()
    except Exception:
        GLM_API_KEY = ""
# Coding 专用端点（GLM-5.1 必须用此端点）
GLM_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"

DEFAULT_MODEL = "glm-5.1"

# ============ GLM 客户端 ============

class GLMClient:
    """智谱 AI GLM-5.1 客户端"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or GLM_API_KEY
        if not self.api_key:
            raise ValueError("API key 未设置，请设置 ZHIPU_API_KEY 或 GLM_API_KEY 环境变量，或写入 ~/.glm_key 文件")

    def chat(self, prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """同步调用 GLM chat completion"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "thinking": {"type": "disabled"},  # GLM-5.1 关闭思考模式
        }
        resp = requests.post(f"{GLM_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        # GLM-5.1 实际内容可能在 content 或 reasoning_content
        return msg.get("content") or msg.get("reasoning_content", "")

    def decompose_task(self, task_desc: str) -> dict:
        """
        M1-3 Task向导: 将用户需求拆解为结构化子任务
        返回 JSON 格式的拆解结果
        """
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
        result = self.chat(prompt, model=DEFAULT_MODEL, temperature=0.3)
        try:
            # 去掉 GLM 返回的 ```json 包装
            cleaned = result.strip().strip("```json").strip("```").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"error": "JSON解析失败", "raw": result}

    def generate_wizard_flow(self, context: str) -> str:
        """
        M1-3 Task向导: 生成 Notion 任务创建流程引导
        """
        prompt = f"""你是 Well-Harness 的任务创建向导。基于以下上下文，生成创建 Notion 任务页面的引导内容。

上下文:
{context}

请生成:
1. 任务标题建议
2. 任务类型选择 (指令/分析/审查/学习/任务)
3. 任务描述模板
4. 优先级建议
5. 关联的 Gate 节点

简洁输出，直接可用。"""
        return self.chat(prompt, model=DEFAULT_MODEL, temperature=0.5)

    def validate_with_context(self, task_id: str, gate: str, context: dict) -> dict:
        """
        通用 Gate 校验: 基于上下文对特定 task 执行 gate 校验
        """
        prompt = f"""你是 Well-Harness Gate 校验专家。

任务ID: {task_id}
Gate: {gate}
上下文: {json.dumps(context, ensure_ascii=False, indent=2)}

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
        result = self.chat(prompt, model=DEFAULT_MODEL, temperature=0.2)
        try:
            # 去掉 GLM 返回的 ```json 包装
            cleaned = result.strip().strip("```json").strip("```").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"error": "JSON解析失败", "raw": result}


# ============ CLI 入口 ============

def main():
    parser = argparse.ArgumentParser(description="GLM-5.1 Well-Harness 任务执行器")
    parser.add_argument("prompt", nargs="?", help="直接输入 prompt")
    parser.add_argument("--task", choices=["M1_3_WIZARD", "TASK_DECOMPOSE", "VALIDATE_GATE"], help="预设任务类型")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型名称 (默认: {DEFAULT_MODEL})")
    parser.add_argument("--stream", action="store_true", help="流式输出")
    parser.add_argument("--context", type=json.loads, default={}, help="额外上下文 (JSON)")
    parser.add_argument("--task-id", default="unknown", help="关联任务ID")
    parser.add_argument("--gate", default="G0", help="Gate编号 (如 G0/G1...)")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=4096)

    args = parser.parse_args()

    if not args.prompt and not args.task:
        parser.print_help()
        print("\n示例:")
        print('  python3 glmext.py "帮我规划 CFD 后处理模块开发"')
        print('  python3 glmext.py --task TASK_DECOMPOSE "开发 Copilot 入口"')
        print('  python3 glmext.py --task M1_3_WIZARD --context \'{"需求": "CFD报告生成"}\'')
        print('  python3 glmext.py --task VALIDATE_GATE --task-id "AI-CFD-001" --gate "G0"')
        return

    client = GLMClient()

    if args.task == "M1_3_WIZARD":
        ctx = json.dumps(args.context, ensure_ascii=False) if args.context else "无"
        result = client.generate_wizard_flow(ctx)
        print(result)

    elif args.task == "TASK_DECOMPOSE":
        result = client.decompose_task(args.prompt or str(args.context))
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.task == "VALIDATE_GATE":
        result = client.validate_with_context(args.task_id, args.gate, args.context)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        result = client.chat(args.prompt, model=args.model, temperature=args.temperature, max_tokens=args.max_tokens)
        print(result)


if __name__ == "__main__":
    main()
