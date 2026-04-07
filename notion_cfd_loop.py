#!/usr/bin/env python3
"""
Well-Harness 自动化循环核心引擎
Claude Code → Notion → Notion AI 分析 → Claude Code 执行 → Notion 更新

功能：
1. Claude Code 把上下文同步到 Notion
2. 轮询 Notion AI 生成的指令/prompts
3. 执行并行开发
4. 更新 Notion 状态
5. 触发 Notion AI 重新分析
"""

import os
import time
import json
import re
import uuid
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

# ============ 配置 ============
_key_env = os.environ.get("NOTION_API_KEY")
if _key_env:
    NOTION_API_KEY = _key_env
else:
    try:
        NOTION_API_KEY = open(os.path.expanduser("~/.notion_key")).read().strip()
    except Exception:
        NOTION_API_KEY = ""
NOTION_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

# 核心数据库 ID
SSOT_DB_ID = "33ac6894-2bed-8125-97af-e9b90b245e58"
# v1架构数据库 (2026-04-07)
PROJECTS_DB_ID = "33bc6894-2bed-8153-a775-d5c821fa34a1"
SPECS_DB_ID = "33bc6894-2bed-8196-a5e0-d6d7d9fbc7ec"
CONSTRAINTS_DB_ID = "33bc6894-2bed-8147-aafd-c1cf6960c18f"
PHASES_DB_ID = "33bc6894-2bed-8163-96ed-e2df5b302545"
TASKS_DB_ID = "33bc6894-2bed-8196-8e2c-d1d66e631c31"
REVIEWS_DB_ID = "33bc6894-2bed-81fb-a911-c4f0798ce1cf"
ARTIFACTS_DB_ID = "33bc6894-2bed-81c0-983f-d5eb1f5b6f4c"
# 旧库保留用于迁移
COMPONENT_DB_ID = "33ac6894-2bed-818c-8c22-d7ed35e2acd0"
CASE_DB_ID = "33ac6894-2bed-81e5-9690-d37ca6ca796b"
BASELINE_DB_ID = "33ac6894-2bed-8129-b739-c3d4aea8435b"
RULE_DB_ID = "33ac6894-2bed-81c1-b0b8-c94ea2ebc020"
EVIDENCE_DB_ID = "33ac6894-2bed-8188-ba53-e80fb7920398"

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json"
}

TASK_LOG_PROPERTY_CANDIDATES = ("Last Run Summary", "执行日志")
TASK_STATUS_ALIASES = {
    "待规划": "待领取",
    "规划中": "待领取",
    "待领取": "待领取",
    "开发中": "执行中",
    "执行中": "执行中",
    "待审查": "执行中",
    "审查中": "执行中",
    "已完成": "已完成",
    "完成": "已完成",
    "失败": "失败",
    "阻塞": "失败",
}

# ============ 核心 API ============

def notion_get(endpoint: str) -> dict:
    """Notion GET 请求"""
    resp = requests.get(f"{NOTION_BASE_URL}/{endpoint}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def notion_post(endpoint: str, data: dict) -> dict:
    """Notion POST 请求"""
    resp = requests.post(f"{NOTION_BASE_URL}/{endpoint}", headers=HEADERS, json=data)
    resp.raise_for_status()
    return resp.json()

def notion_patch(endpoint: str, data: dict) -> dict:
    """Notion PATCH 请求"""
    resp = requests.patch(f"{NOTION_BASE_URL}/{endpoint}", headers=HEADERS, json=data)
    resp.raise_for_status()
    return resp.json()

# ============ Claude Code 命令生成 ============

def generate_claude_code_command(instruction: str, context: dict = None) -> str:
    """
    生成可以在 Claude Code 中直接执行的命令
    这个函数生成的是 Claude Code 可以理解的指令文本
    """
    cmd = f"/exec {instruction}"
    if context:
        cmd += f" | context: {json.dumps(context, ensure_ascii=False)[:200]}"
    return cmd


def _build_rich_text(content: str) -> dict:
    return {"rich_text": [{"text": {"content": str(content)[:1900]}}]}


def _rich_text_to_plain(prop: dict) -> str:
    if not prop:
        return ""

    texts = []
    for item in prop.get("rich_text", []):
        plain_text = item.get("plain_text")
        if plain_text is not None:
            texts.append(plain_text)
        else:
            texts.append(item.get("text", {}).get("content", ""))
    return "".join(texts)


def _get_task_log_property(page: dict) -> Tuple[str, str]:
    props = page.get("properties", {})
    for prop_name in TASK_LOG_PROPERTY_CANDIDATES:
        prop_val = props.get(prop_name)
        if prop_val and (prop_val.get("type") == "rich_text" or "rich_text" in prop_val):
            return prop_name, _rich_text_to_plain(prop_val)
    return TASK_LOG_PROPERTY_CANDIDATES[0], ""


def _normalize_task_status(status: str) -> str:
    return TASK_STATUS_ALIASES.get(status, status)


def _get_task_status(task_page: dict) -> str:
    props = task_page.get("properties", {})

    task_status = props.get("Task Status", {})
    if task_status and (task_status.get("type") == "select" or "select" in task_status):
        name = (task_status.get("select") or {}).get("name", "")
        if name:
            return name

    legacy_status = props.get("phase状态", {})
    if legacy_status and (legacy_status.get("type") == "status" or "status" in legacy_status):
        name = (legacy_status.get("status") or {}).get("name", "")
        return _normalize_task_status(name)

    return ""


def _extract_task_title(task_page: dict) -> str:
    props = task_page.get("properties", {})
    for prop_name in ("Task ID", "项目ID", "Project ID"):
        title_prop = props.get(prop_name, {})
        title_items = title_prop.get("title", [])
        if title_items:
            first = title_items[0]
            plain_text = first.get("plain_text")
            if plain_text:
                return plain_text
            content = first.get("text", {}).get("content", "")
            if content:
                return content
    return "未命名"

# ============ 任务同步 ============

def sync_task_to_notion(task_id: str, updates: dict) -> bool:
    """
    Claude Code 执行完成后，同步结果到 Notion
    updates 包含: {执行摘要, 状态, 新增知识, 发现, 风险}
    """
    try:
        # 构建更新属性
        properties = {}
        summary_lines = []
        rich_text_fields = {
            "Linked Phase",
            "Linked Project",
            "Executor Model",
            "Fallback Model",
            "Git Branch",
            "Failure Reason",
        }
        url_fields = {"PR Link", "Artifact Link"}
        key_aliases = {
            "执行日志": "Last Run Summary",
            "执行摘要": "Last Run Summary",
            "状态": "Task Status",
            "phase状态": "Task Status",
        }

        for key, value in updates.items():
            if value is None:
                continue

            canonical_key = key_aliases.get(key, key)
            if canonical_key == "Last Run Summary":
                summary_lines.append(str(value))
            elif canonical_key == "Task Status":
                properties["Task Status"] = {"select": {"name": _normalize_task_status(str(value))}}
            elif canonical_key == "Retry Count":
                properties["Retry Count"] = {"number": int(value)}
            elif canonical_key in rich_text_fields:
                properties[canonical_key] = _build_rich_text(str(value))
            elif canonical_key in url_fields:
                properties[canonical_key] = {"url": str(value)}
            else:
                summary_lines.append(f"{key}: {value}")

        if summary_lines:
            properties["Last Run Summary"] = _build_rich_text("\n".join(summary_lines))

        if properties:
            notion_patch(f"pages/{task_id}", {"properties": properties})

        print(f"✅ 任务 {task_id} 已同步到 Notion")
        return True
    except Exception as e:
        print(f"❌ 同步失败: {e}")
        return False

def read_task_from_notion(task_id: str) -> dict:
    """从 Notion 读取任务完整信息"""
    return notion_get(f"pages/{task_id}")

def query_pending_tasks(status_filter: str = None) -> list:
    """
    查询待处理任务
    status_filter: "待领取" / "执行中" / "已完成" / "失败"
    """
    query = {
        "database_id": TASKS_DB_ID,
        "page_size": 50
    }

    result = notion_post("databases/query", query)
    all_results = result.get("results", [])

    if status_filter:
        normalized_status = _normalize_task_status(status_filter)
        filtered = []
        for t in all_results:
            if _get_task_status(t) == normalized_status:
                filtered.append(t)
        return filtered
    return all_results

# ============ Notion AI 触发 ============

def create_notion_page_task(parent_id: str, title: str, content: str, task_type: str) -> str:
    """
    在 v1 Tasks DB 中创建任务记录
    返回 page_id
    """
    routing = get_model_for_task(title)
    task_type_name = task_type if task_type in {"指令", "分析", "审查", "学习", "任务"} else "任务"

    page = notion_post("pages", {
        "parent": {"database_id": TASKS_DB_ID},
        "properties": {
            "Task ID": {"title": [{"text": {"content": title}}]},
            "Linked Phase": _build_rich_text(parent_id or ""),
            "Linked Project": _build_rich_text(parent_id or ""),
            "Task Type": {"select": {"name": task_type_name}},
            "Priority": {"select": {"name": "P2"}},
            "Executor Model": _build_rich_text(routing["primary"]),
            "Fallback Model": _build_rich_text(routing["fallback"]),
            "Task Status": {"select": {"name": "待领取"}},
            "Git Branch": {"rich_text": []},
            "PR Link": {"url": None},
            "Artifact Link": {"url": None},
            "Failure Reason": {"rich_text": []},
            "Retry Count": {"number": 0},
            "Last Run Summary": _build_rich_text(content),
        },
        "children": [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "任务概述"}}]}
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": content[:1900]}}]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"text": {"content": f"执行模型: {routing['primary']} | 兜底模型: {routing['fallback']}"}}]
                }
            }
        ]
    })
    return page.get("id", "")

# ============ 状态轮询循环 ============

def run_harness_loop(interval: int = 60, max_iterations: int = None):
    """
    Well-Harness 主循环
    1. 查询 Notion 中待处理的任务
    2. 生成 Claude Code 可执行的指令
    3. 输出指令供 Claude Code 执行

    interval: 轮询间隔（秒）
    max_iterations: 最大迭代次数（None=无限）
    """
    iteration = 0
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║     Well-Harness 自动化循环引擎启动                          ║
║     轮询间隔: {interval}秒 | 最大迭代: {max_iterations or '无限'}                        ║
╚══════════════════════════════════════════════════════════════╝
    """)

    while True:
        iteration += 1
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 第 {iteration} 次轮询")

        # 查询各状态任务
        statuses = ["待领取", "执行中"]
        pending = {}
        for status in statuses:
            tasks = query_pending_tasks(status)
            if tasks:
                pending[status] = tasks

        if not pending:
            print("  📭 暂无待处理任务")
        else:
            print(f"  📋 待处理任务:")
            for status, tasks in pending.items():
                print(f"     [{status}]: {len(tasks)} 个")
                for task in tasks[:3]:  # 只显示前3个
                    name = _extract_task_title(task)
                    print(f"       - {name[:40]} (ID: {task['id'][:8]}...)")

        print(f"  ⏰ 下次轮询: {interval}秒后")
        time.sleep(interval)

        if max_iterations and iteration >= max_iterations:
            print("\n✅ 达到最大迭代次数，退出")
            break

# ============ Notion AI (Opus 4.6) 触发指令 ============

OPUS_PROMPTS = {
    "G0": {
        "name": "G0 任务门审查",
        "description": "需求完整性 + Harness 规范预检",
        "prompt": """请作为 Well-Harness G0 任务门审查专家，分析当前任务页面的：

1. 任务ID和名称是否规范
2. 需求文档是否完整（包含 objective/scope/constraints）
3. 验收标准是否明确且可量化
4. Harness 规范约束是否已绑定
5. 当前 phase 状态与 Gate 节点是否匹配

【重要】必须用以下标记包裹 JSON 输出，不要有其他文字：
###HARNESS_RESPONSE_START###
{"gate":"G0","pass":true,"checks":[{"check":"检查项","pass":true,"detail":"详情"}],"recommendations":["建议1"],"next_action":"下一步操作"}
###HARNESS_RESPONSE_END###"""
    },
    "G1": {
        "name": "G1 认知门审查",
        "description": "知识库绑定审查",
        "prompt": """请作为 Well-Harness G1 认知门专家，审查当前任务的知识库绑定情况：

1. 检索组件库，列出与本任务相关的组件及其版本状态
2. 检索案例库，列出与本任务物理场景相似的历史案例
3. 检索规则库，列出适用于本任务的 Harness 规范条款
4. 检索基准库，列出可用于对比验证的基准数据
5. 评估知识库完整度，识别缺失项

【重要】必须用以下标记包裹 JSON 输出，不要有其他文字：
###HARNESS_RESPONSE_START###
{"gate":"G1","pass":true,"components":[{"id":"...","name":"...","version":"...","relevance":"高"}],"cases":[...],"rules":[...],"baselines":[...],"knowledge_gaps":["缺失项"],"next_action":"下一步操作"}
###HARNESS_RESPONSE_END###"""
    },
    "G2": {
        "name": "G2 配置门审查",
        "description": "规划配置审查",
        "prompt": """请作为 Well-Harness G2 配置门专家，审查当前任务的规划配置：

1. 验证 phase 规划是否覆盖完整开发流程
2. 检查每个 phase 的输入/输出定义是否清晰
3. 评估资源配置（模型选择、工具链）是否合理
4. 检查风险识别和缓解措施是否充分
5. 验证与 Harness 规范的合规性

【重要】必须用以下标记包裹 JSON 输出，不要有其他文字：
###HARNESS_RESPONSE_START###
{"gate":"G2","pass":true,"phase_coverage":{"complete":true,"gaps":[]},"resource_plan":{"合理性":"..."},"risk_assessment":{"high_risks":[],"mitigations":[]},"compliance_check":{"passed":true,"violations":[]},"next_action":"下一步操作"}
###HARNESS_RESPONSE_END###"""
    },
    "G3": {
        "name": "G3 执行门审查",
        "description": "开发执行审查",
        "prompt": """请作为 Well-Harness G3 执行门专家，审查当前任务的开发执行情况：

1. 检查开发进度是否符合 phase 规划
2. 验证代码实现是否遵循 Harness 编码规范
3. 评估中间结果的正确性和完整性
4. 识别开发中的阻塞点和风险
5. 判断是否可以进入验证阶段

【重要】必须用以下标记包裹 JSON 输出，不要有其他文字：
###HARNESS_RESPONSE_START###
{"gate":"G3","pass":true,"progress":{"planned":"X%","actual":"Y%"},"code_quality":{"规范符合度":"...","issues":[]},"blockers":[],"next_action":"下一步操作"}
###HARNESS_RESPONSE_END###"""
    },
    "G4": {
        "name": "G4 运行门审查",
        "description": "结果验证审查",
        "prompt": """请作为 Well-Harness G4 运行门专家，审查 CFD 运行结果：

1. 对比基准库数据，验证结果准确性
2. 检查收敛性指标（残差、监控点）是否达标
3. 评估结果物理一致性（守恒性、对称性等）
4. 与历史相似案例对比，识别异常
5. 判断是否可以进入审批阶段

【重要】必须用以下标记包裹 JSON 输出，不要有其他文字：
###HARNESS_RESPONSE_START###
{"gate":"G4","pass":true,"baseline_comparison":{"matched":true,"delta":"..."},"convergence":{"converged":true,"details":"..."},"physics_consistency":{"passed":true,"issues":[]},"anomalies":[],"next_action":"下一步操作"}
###HARNESS_RESPONSE_END###"""
    },
    "G5": {
        "name": "G5 验证门审查",
        "description": "最终审批",
        "prompt": """请作为 Well-Harness G5 验证门专家，执行最终审批：

1. 核对所有 Gate 检查记录是否完整
2. 验证验收标准是否全部满足
3. 检查文档完整性（API文档、用户手册）
4. 评估项目是否达到发布标准
5. 给出最终审批结论

【重要】必须用以下标记包裹 JSON 输出，不要有其他文字：
###HARNESS_RESPONSE_START###
{"gate":"G5","pass":true,"gate_completeness":{"all_passed":true,"failed_gates":[]},"acceptance_criteria":{"met":true,"outstanding":[]},"documentation":{"complete":true,"missing":[]},"final_decision":"APPROVED/REJECTED","next_action":"下一步操作"}
###HARNESS_RESPONSE_END###"""
    },
    "G6": {
        "name": "G6 写回门审查",
        "description": "知识归档审查",
        "prompt": """请作为 Well-Harness G6 写回门专家，审查知识归档：

1. 评估本任务是否值得沉淀为案例
2. 检查提取的关键知识（组件、规则、参数）是否完整
3. 验证对组件库/规则库的贡献是否准确
4. 确认所有相关库已更新
5. 生成案例摘要

【重要】必须用以下标记包裹 JSON 输出，不要有其他文字：
###HARNESS_RESPONSE_START###
{"gate":"G6","pass":true,"case_candidate":{"worthy":true,"reason":"..."},"knowledge_extraction":{"components":[],"rules":[],"parameters":[]},"library_updates":{"completed":true,"pending":[]},"case_summary":"案例一句话描述","next_action":"下一步操作"}
###HARNESS_RESPONSE_END###"""
    },
    "ARCH": {
        "name": "架构审查",
        "description": "深度架构分析和风险评估",
        "prompt": """请作为 Well-Harness 架构审查专家，执行深度审查：

1. 评估当前实现的架构合理性
2. 识别技术债和架构腐化点
3. 检查模块解耦和接口设计
4. 评估可扩展性和可维护性
5. 提出改进建议

【重要】必须用以下标记包裹 JSON 输出，不要有其他文字：
###HARNESS_RESPONSE_START###
{"review_type":"ARCHITECTURE","overall_score":"8/10","strengths":["优点1"],"technical_debts":[{"debt":"...","severity":"高","suggestion":"..."}],"interface_design":{"评分":"...","issues":[]},"improvements":["改进1"],"next_action":"下一步操作"}
###HARNESS_RESPONSE_END###"""
    },
    "TASK": {
        "name": "任务拆解审查",
        "description": "审查并优化任务拆解",
        "prompt": """请作为 Well-Harness 任务规划专家，审查并优化任务拆解：

1. 评估子任务粒度是否合适
2. 识别可并行的子任务
3. 检查任务依赖关系是否正确
4. 补充遗漏的子任务（如测试、文档）
5. 优化执行顺序
6. 推荐最适合各子任务的 AI 模型

【重要】必须用以下标记包裹 JSON 输出，不要有其他文字：
###HARNESS_RESPONSE_START###
{"review_type":"TASK_DECOMPOSITION","original_tasks":["原始任务1"],"improved_tasks":[{"id":"...","description":"...","parallel_with":[],"model":"...","estimated_phase":"..."}],"execution_order":["task_1","task_2"],"estimated_total_phases":3,"risks":["风险1"],"next_action":"下一步操作"}
###HARNESS_RESPONSE_END###"""
    },
}


def output_opus_prompt(gate_type: str):
    """输出 Notion AI (Opus 4.6) 标准触发指令"""
    gate_type = gate_type.upper()
    if gate_type not in OPUS_PROMPTS:
        print(f"未知 Gate 类型: {gate_type}")
        print(f"可用类型: {', '.join(OPUS_PROMPTS.keys())}")
        return

    info = OPUS_PROMPTS[gate_type]
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  ⚠️  需要 Notion AI (Opus 4.6) 介入                                    ║
║  Gate: {gate_type} - {info['name']:<50}║
╚══════════════════════════════════════════════════════════════════════╝

请将以下指令复制到 Notion 页面，点击 @Notion AI 执行：

────────────────────────────────────────────────────────────────────────
{info['prompt']}
────────────────────────────────────────────────────────────────────────

完成后请告知 Claude Code 继续执行。
""")


def cmd_sync_project(project_id: str, phase: str, summary: str):
    """Claude Code 执行完成后同步项目状态"""
    sync_task_to_notion(project_id, {
        "执行日志": f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {summary}",
        "phase状态": phase
    })


def cmd_create_task(parent_page: str, title: str, desc: str, task_type: str = "任务"):
    """Claude Code 创建新任务指令"""
    page_id = create_notion_page_task(parent_page, title, desc, task_type)
    print(f"✅ 任务页面创建: {page_id}")
    return page_id

# ============ Relay Protocol v1 实现 ============
# 传令协议：Claude Code ↔ Notion AI 通过 v1 Tasks 的 Last Run Summary
# （兼容旧执行日志字段）进行结构化交接
# 三信号：DISPATCH → COMPLETION → ACK

SIGNAL_TYPES = ["DISPATCH", "COMPLETION", "ACK"]
TIMEOUT_MINUTES = 30
LOG_ARCHIVE_THRESHOLD = 1800   # 超过此长度则归档旧记录（保留余量）
MAX_LOG_RETRIES = 3           # 写入最大重试次数
DISPATCH_EXPIRY_HOURS = 24    # DISPATCH 信号过期时间（小时）


# ============ 模型路由层 — Model Routing ============
# Well-Harness 使用多模型协作：Notion AI（Opus/Sonnet）做审查分析，
# Claude Code agents（GLM-5.1 / Minimax-2.7 / Codex/GPT-5.4）做执行实现。

# ---- 模型注册表 ----
MODEL_REGISTRY = {
    # Notion AI 模型（@Notion AI 触发）
    "notion_opus": {
        "name": "Opus 4.6 (Notion AI)",
        "provider": "Notion AI",
        "type": "analysis",          # 审查/分析/规划
        "strengths": ["复杂推理", "多步规划", "架构设计", "深度审查"],
        "callsign": "@Notion AI (Opus 4.6)",
    },
    "notion_sonnet": {
        "name": "Sonnet 4.6 (Notion AI)",
        "provider": "Notion AI",
        "type": "analysis",
        "strengths": ["规则设计", "字段映射", "交互架构", "中文优化"],
        "callsign": "@Notion AI (Sonnet 4.6)",
    },
    # Claude Code agents（由 Claude Code 调用）
    "codex": {
        "name": "GPT-5.4 (Codex)",
        "provider": "OpenAI via Codex plugin",
        "type": "execution",          # 代码生成/实现
        "strengths": ["高质量代码", "复杂模式", "多文件生成", "架构重构"],
        "callsign": "/codex",         # Claude Code 内调用方式
        "model_override": "gpt-5.4-codex",
    },
    "glm_51": {
        "name": "GLM-5.1 (Claude Code)",
        "provider": "智谱 GLM via Claude Code API",
        "type": "execution",
        "strengths": ["中文理解", "Prompt填充", "中文文档", "自然语言解析"],
        "callsign": "GLM-5.1 via Claude Code agent",
        "model_override": "glm-5.1",
    },
    "minimax_27": {
        "name": "Minimax-2.7 (Claude Code)",
        "provider": "Minimax via Claude Code API",
        "type": "execution",
        "strengths": ["快速生成", "JSON校验", "轻量任务", "模式匹配"],
        "callsign": "Minimax-2.7 via Claude Code agent",
        "model_override": "minimax-2.7",
    },
}

# ---- 任务 → 模型路由表 ----
# 格式：task_id 前缀 或 task_type → primary_model, fallback_model
# 由 G2 Opus 人工审查结果确定，Claude Code 执行时按此路由分配
TASK_MODEL_ROUTING = {
    # M1-1 系列：状态机/引擎 — Codex 高质量实现
    "M1-1": {
        "description": "状态机引擎模块",
        "primary": "codex",
        "fallback": "minimax_27",
        "notion_reviewer": "notion_opus",   # Notion AI 做架构审查
        "reason": "状态机涉及12态+多路分支+Gate耦合，需GPT-5.4多步推理确保无死锁/无非法跳转",
    },
    # M1-2 系列：G0 任务门 JSON Schema — Minimax 快速 + Opus 审查
    "M1-2": {
        "description": "G0 任务门 JSON Schema",
        "primary": "minimax_27",
        "fallback": "glm_51",
        "notion_reviewer": "notion_opus",
        "reason": "G0 规则以字段校验为主，逻辑清晰但需与Schema精确对齐，Minimax快速生成即可满足",
    },
    # M1-3 系列：Task 创建向导 — GLM 中文优化
    "M1-3": {
        "description": "Task 创建向导",
        "primary": "glm_51",
        "fallback": "codex",
        "notion_reviewer": "notion_opus",
        "reason": "向导需多轮对话流+字段解析映射，GLM-5.1中文理解优化最佳，适合中文Prompt填充",
    },
    # M1-4：pytest 测试 — Codex 高质量测试生成
    "M1-4": {
        "description": "pytest 单元测试",
        "primary": "codex",
        "fallback": "minimax_27",
        "notion_reviewer": "notion_opus",
        "reason": "测试需覆盖全部合法/非法转换+边界条件，Codex测试生成能力最强",
    },
    # M1-5：Evidence Schema — Opus 架构审查
    "M1-5": {
        "description": "Evidence Schema 设计",
        "primary": "notion_opus",   # Schema 设计由 Opus 完成
        "fallback": "codex",
        "notion_reviewer": "notion_opus",
        "reason": "Schema设计需规则库精确对齐，Opus擅长架构设计；Codex代码实现",
    },
    # M1-6：Relay 幂等性 — Codex 高质量实现
    "M1-6": {
        "description": "Relay 协议幂等性加固",
        "primary": "codex",
        "fallback": "minimax_27",
        "notion_reviewer": "notion_opus",
        "reason": "Relay协议涉及并发/重试/幂等性设计，Codex实现最可靠",
    },
    # G3/G4/G5/G6 执行门：Codex 实现
    "G3": {
        "description": "G3 执行门",
        "primary": "codex",
        "fallback": "minimax_27",
        "notion_reviewer": "notion_opus",
        "reason": "CFD开发执行涉及复杂代码生成，Codex实现质量最高",
    },
    "G4": {
        "description": "G4 运行门",
        "primary": "codex",
        "fallback": "minimax_27",
        "notion_reviewer": "notion_opus",
        "reason": "CFD结果验证需高质量代码对比分析",
    },
    "G5": {
        "description": "G5 验证门",
        "primary": "codex",
        "fallback": "notion_opus",
        "notion_reviewer": "notion_opus",
        "reason": "最终审批需Codex高质量审查+Opus深度分析协同",
    },
    "G6": {
        "description": "G6 写回门",
        "primary": "codex",
        "fallback": "glm_51",
        "notion_reviewer": "notion_opus",
        "reason": "知识归档需代码+中文文档双能力",
    },
    # 默认路由
    "_default": {
        "description": "默认路由",
        "primary": "minimax_27",
        "fallback": "glm_51",
        "notion_reviewer": "notion_sonnet",
        "reason": "默认快速轻量路径",
    },
}


def get_model_for_task(task_id: str) -> dict:
    """
    根据 task_id 返回路由信息。
    匹配规则：task_id 前缀最长匹配。
    """
    # 精确匹配优先
    if task_id in TASK_MODEL_ROUTING:
        return TASK_MODEL_ROUTING[task_id]

    # 前缀匹配（取最长前缀）
    best_match = None
    best_len = 0
    for key in TASK_MODEL_ROUTING:
        if key.startswith("_"):
            continue
        if task_id.startswith(key) and len(key) > best_len:
            best_len = len(key)
            best_match = key

    if best_match:
        return TASK_MODEL_ROUTING[best_match]

    return TASK_MODEL_ROUTING["_default"]


def agent_dispatch(task_id: str, instruction: str, force_model: str = None) -> str:
    """
    生成 Claude Code agent 调用命令。

    参数:
        task_id:      任务 ID（如 M1-4、G3 等）
        instruction:   要执行的指令
        force_model:   强制使用某模型（覆盖路由表）

    返回:
        Claude Code 执行命令字符串（可直接粘贴执行）
    """
    if force_model and force_model in MODEL_REGISTRY:
        model_info = MODEL_REGISTRY[force_model]
        primary = force_model
    else:
        routing = get_model_for_task(task_id)
        primary = routing["primary"]
        model_info = MODEL_REGISTRY.get(primary, MODEL_REGISTRY["minimax_27"])

    # 根据模型类型生成不同的调用命令
    model_type = model_info["type"]

    if model_type == "analysis":
        # Notion AI 模型 — 输出 @Notion AI 触发指令
        reviewer = routing.get("notion_reviewer", "notion_opus")
        reviewer_info = MODEL_REGISTRY.get(reviewer, MODEL_REGISTRY["notion_opus"])
        return (
            f"# 【模型路由】{model_info['name']} 执行\n"
            f"# 任务: {task_id}\n"
            f"# 原因: {routing.get('reason', '')}\n\n"
            f"请将以下指令复制到 Notion 页面 {task_id}，点击 {reviewer_info['callsign']} 执行：\n\n"
            f"--- 指令 ---\n"
            f"{instruction}\n"
            f"--- 指令结束 ---\n\n"
            f"完成后执行:\n"
            f"python3 notion_cfd_loop.py --relay <page_id> ack\n"
        )

    elif primary == "codex":
        # Codex — Claude Code /codex 插件
        return (
            f"# 【模型路由】{model_info['name']} 执行\n"
            f"# 任务: {task_id}\n"
            f"# 原因: {routing.get('reason', '')}\n\n"
            f"/codex --task \"{instruction}\" --model gpt-5.4-codex\n\n"
            f"# 备选: 如 Codex 不可用，切换至 {MODEL_REGISTRY[routing['fallback']]['name']}\n"
            f"# /codex --task \"{instruction}\" --model {MODEL_REGISTRY[routing['fallback']]['model_override']}\n"
        )

    elif primary == "glm_51":
        return (
            f"# 【模型路由】{model_info['name']} 执行\n"
            f"# 任务: {task_id}\n"
            f"# 原因: {routing.get('reason', '')}\n\n"
            f"/exec 调用 GLM-5.1 agent 执行：\n{instruction}\n\n"
            f"# 模型标识: {model_info['model_override']}\n"
        )

    elif primary == "minimax_27":
        return (
            f"# 【模型路由】{model_info['name']} 执行\n"
            f"# 任务: {task_id}\n"
            f"# 原因: {routing.get('reason', '')}\n\n"
            f"/exec 调用 Minimax-2.7 agent 执行：\n{instruction}\n\n"
            f"# 模型标识: {model_info['model_override']}\n"
        )

    else:
        return f"# 【模型路由】未知模型: {primary}\n# 任务: {task_id}\n{instruction}"


def agent_status_report(page_id: str = None) -> str:
    """
    生成模型路由状态报告。
    """
    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║  Well-Harness 模型路由层 — 状态报告                        ║",
        "╠══════════════════════════════════════════════════════════════╣",
        "║  可用模型:",
    ]

    for mid, minfo in MODEL_REGISTRY.items():
        lines.append(f"║    • {mid}: {minfo['name']} [{minfo['type']}]")

    lines.append("╠══════════════════════════════════════════════════════════════╣")
    lines.append("║  任务路由表:")

    for tid, routing in TASK_MODEL_ROUTING.items():
        if tid.startswith("_"):
            continue
        primary_info = MODEL_REGISTRY.get(routing["primary"], {})
        reviewer_info = MODEL_REGISTRY.get(routing.get("notion_reviewer", ""), {})
        lines.append(
            f"║    • {tid}: {routing['description']}\n"
            f"║        执行→{primary_info.get('name', '?')} | 审查→{reviewer_info.get('name', '?')}"
        )

    lines.append("╚══════════════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def _parse_table_or_text(text: str) -> Optional[Dict]:
    """
    从表格格式或自由文本中提取结构化数据。
    例如 Notion AI 返回的表格：
    子任务 | 规划模型 | 执行模型 | 选择理由
    M1-1 状态机引擎 | Opus 4.6 | GPT-5.4 | ...
    """
    import re

    if not text or len(text) < 10:
        return None

    # 尝试找 key=value 或 key:value 模式
    pairs = {}
    kv_pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^\n|]+?)(?:\n|$| \|)')
    for m in kv_pattern.finditer(text):
        key, val = m.group(1), m.group(2).strip()
        if key not in pairs or len(val) > len(str(pairs[key])):
            pairs[key] = val

    # 尝试找 gate/G0/G1 等 gate 标识
    gate_match = re.search(r'\b(G[0-6]|ARCH|TASK)\b', text)
    if gate_match:
        pairs.setdefault("gate", gate_match.group())

    # 尝试找 pass/false/true
    pass_match = re.search(r'\b(pass|passed)\s*[=:]\s*(true|false|TRUE|FALSE)', text, re.I)
    if pass_match:
        pairs["pass"] = pass_match.group(2).lower() == "true"

    # 尝试找 next_action
    na_match = re.search(r'next_action\s*[=:]\s*(.+?)(?:\n|$)', text, re.I)
    if na_match:
        pairs["next_action"] = na_match.group(1).strip()

    # 尝试找 review_type
    rt_match = re.search(r'review_type\s*[=:]\s*(.+?)(?:\n|$)', text, re.I)
    if rt_match:
        pairs["review_type"] = rt_match.group(1).strip()

    # 如果找到 key=value 形式的结构化数据
    if "gate" in pairs and len(pairs) >= 2:
        return pairs

    # 检测是否是表格格式（包含 | 分隔符）
    table_rows = [r.strip() for r in text.split('\n') if '|' in r and r.strip()]
    if len(table_rows) >= 2:
        # 表格格式：提取每行第一列（任务名）作为分析内容
        headers = [h.strip() for h in table_rows[0].split('|') if h.strip()]
        task_items = []
        for row in table_rows[1:]:
            cols = [c.strip() for c in row.split('|') if c.strip()]
            if cols:
                task_items.append(' | '.join(cols[:len(headers)]))

        result = {
            "gate": pairs.get("gate", "TASK"),
            "analysis_type": "table",
            "items": task_items,
            "raw_header": headers[0] if headers else "task",
        }
        if len(task_items) > 0:
            result["summary"] = task_items[0][:100]
        return result

    # 如果什么都没找到但有结构化关键词，返回部分结果
    if any(kw in text.lower() for kw in ["gate", "pass", "next_action", "review_type", "bottleneck", "recommendation"]):
        if pairs:
            pairs.setdefault("gate", "UNKNOWN")
            return pairs

    return None


def _generate_signal_id() -> str:
    """生成唯一信号 ID"""
    return str(uuid.uuid4())[:8]


def _archive_oldest_entries(page_id: str, current_log: str, current_signal_type: str) -> Optional[str]:
    """
    将执行日志最旧的一半记录归档到子页面，保留最新的一半。
    返回归档的摘要行（用于调试/追溯）。
    """
    lines = current_log.strip().split("\n")
    if len(lines) <= 4:  # 至少保留 2 条信号
        return None

    # 保留最新的 half（向上取整）
    keep_count = (len(lines) + 1) // 2
    keep_lines = lines[-keep_count:]
    archive_lines = lines[:-keep_count]

    # 构建归档摘要
    archive_summary = (
        f"[ARCHIVED] {len(archive_lines)} 条记录已归档 "
        f"(时间范围: {archive_lines[0][:40]} ... {archive_lines[-1][:40]})"
    )

    # 创建归档子页面
    try:
        child_page = notion_post("pages", {
            "parent": {"page_id": page_id},
            "properties": {
                "title": {
                    "title": [{"text": {"content": f"[归档] 执行日志 {datetime.now().strftime('%Y-%m-%d %H:%M')}"}}]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": line}}]
                    }
                }
                for line in archive_lines
            ]
        })
        print(f"  [archive] ✅ 已创建归档子页面: {child_page.get('id', 'unknown')[:20]}...")
    except Exception as e:
        print(f"  [archive] ⚠️ 归档子页面创建失败: {e}")

    # 更新主页面日志（只保留 keep_lines + 摘要）
    new_log = "\n".join(keep_lines + [archive_summary])
    return archive_summary


def _parse_log_entry(line: str) -> Optional[Dict]:
    """解析单行日志条目，提取信号"""
    line = line.strip()
    for sig_type in SIGNAL_TYPES:
        prefix = f"[{sig_type}]"
        if line.startswith(prefix):
            content = line[len(prefix):].strip()
            parts = {}
            for part in content.split("|"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    parts[k.strip()] = v.strip()
            parts["_signal_type"] = sig_type
            return parts
    return None


def parse_execution_log(log_text: str) -> Dict[str, List[Dict]]:
    """解析执行日志，提取所有信号"""
    result = {"DISPATCH": [], "COMPLETION": [], "ACK": []}
    if not log_text:
        return result

    for line in log_text.split("\n"):
        sig = _parse_log_entry(line)
        if sig:
            sig_type = sig.pop("_signal_type")
            result[sig_type].append(sig)
    return result


def get_page_execution_log(page_id: str) -> Tuple[str, Dict]:
    """获取页面的执行日志并解析"""
    page = notion_get(f"pages/{page_id}")
    _, log_text = _get_task_log_property(page)
    signals = parse_execution_log(log_text)
    return log_text, signals


def write_signal_to_log(page_id: str, signal_type: str, signal_data: Dict) -> bool:
    """写入信号到页面的执行摘要字段（追加模式，线程安全，幂等）"""
    import threading

    # Per-page lock 防止并发覆盖
    if not hasattr(write_signal_to_log, "_locks"):
        write_signal_to_log._locks = {}
    if page_id not in write_signal_to_log._locks:
        write_signal_to_log._locks[page_id] = threading.Lock()

    lock = write_signal_to_log._locks[page_id]

    with lock:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        signal_id = signal_data.get("signal_id") or _generate_signal_id()

        # 构建信号行
        parts = [f"timestamp={timestamp}", f"task_id={page_id}", f"signal_id={signal_id}"]

        # DISPATCH 信号增加 expires_at
        if signal_type == "DISPATCH":
            expires_at = (datetime.now() + timedelta(hours=DISPATCH_EXPIRY_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
            parts.append(f"expires_at={expires_at}")

        for k, v in signal_data.items():
            if k not in ("signal_id", "timestamp", "expires_at"):
                parts.append(f"{k}={v}")

        signal_line = f"[{signal_type}] " + " | ".join(parts)

        # 读取当前日志
        page = notion_get(f"pages/{page_id}")
        log_property_name, current_log = _get_task_log_property(page)

        # ===== 幂等性检查：signal_id 已存在则跳过 =====
        if signal_id and signal_id != "UNKNOWN" and current_log:
            if signal_id in current_log:
                print(f"  [relay] 信号已存在，跳过: signal_id={signal_id}")
                return True  # 幂等：视为成功

        # ===== 日志归档：当接近 2000 字符限制时，裁剪旧记录 =====
        if len(current_log) >= LOG_ARCHIVE_THRESHOLD:
                archived_line = _archive_oldest_entries(page_id, current_log, signal_type)
                if archived_line:
                    # 取回裁剪后的日志
                    page2 = notion_get(f"pages/{page_id}")
                    log_property_name, current_log = _get_task_log_property(page2)

        # 追加新信号
        new_log = current_log + ("\n" if current_log else "") + signal_line

        # 写回 Notion（带重试，应对 409 冲突）
        for attempt in range(MAX_LOG_RETRIES):
            try:
                notion_patch(f"pages/{page_id}", {
                    "properties": {
                        log_property_name: _build_rich_text(new_log)
                    }
                })
                return True
            except Exception as e:
                if attempt == MAX_LOG_RETRIES - 1:
                    print(f"❌ 写入信号失败: {e}")
                    return False
                import time
                time.sleep(0.5 * (attempt + 1))  # 指数退避


def relay_check(page_id: str) -> Dict:
    """
    /relay check - 检查页面传令状态
    返回: {has_pending_dispatch, pending_signals, last_completion, last_ack, stale_dispatches}
    """
    _, signals = get_page_execution_log(page_id)

    dispatches = signals.get("DISPATCH", [])
    completions = signals.get("COMPLETION", [])
    acks = signals.get("ACK", [])

    # 找出未完成 COMPLETION 的 DISPATCH
    completed_ids = {c.get("signal_id") for c in completions if c.get("signal_id")}
    pending = [d for d in dispatches if d.get("signal_id") not in completed_ids]

    # 检查超时的 DISPATCH（同时检查 expires_at 和 30-min 固定超时）
    stale = []
    now = datetime.now()
    for d in pending:
        is_stale = False
        reason = ""

        # 优先使用 expires_at 字段判断
        expires_at_str = d.get("expires_at", "")
        if expires_at_str:
            try:
                expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
                if now > expires_at:
                    is_stale = True
                    reason = f"expires_at={expires_at_str} 已过期"
            except ValueError:
                pass

        # 备用：固定 30 分钟超时
        if not is_stale:
            ts_str = d.get("timestamp", "")
            if ts_str:
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    if now - ts > timedelta(minutes=TIMEOUT_MINUTES):
                        is_stale = True
                        reason = f"超过 {TIMEOUT_MINUTES} 分钟超时"
                except ValueError:
                    pass

        if is_stale:
            d["stale_reason"] = reason
            stale.append(d)

    # 最后一条 COMPLETION 和 ACK
    last_completion = completions[-1] if completions else None
    last_ack = acks[-1] if acks else None

    return {
        "page_id": page_id,
        "total_dispatches": len(dispatches),
        "total_completions": len(completions),
        "total_acks": len(acks),
        "pending_dispatches": pending,
        "stale_dispatches": stale,
        "last_completion": last_completion,
        "last_ack": last_ack,
    }


def relay_dispatch(page_id: str, gate: str, prompt: str = "") -> str:
    """
    /relay dispatch - 发送 DISPATCH 信号（触发 Notion AI 任务）
    """
    signal_data = {
        "gate": gate,
        "prompt_hash": str(hash(prompt))[:8] if prompt else "",
        "status": "PENDING",
    }
    success = write_signal_to_log(page_id, "DISPATCH", signal_data)

    if success:
        # 输出 Opus 触发指令
        if gate.upper() in OPUS_PROMPTS:
            info = OPUS_PROMPTS[gate.upper()]
            return f"""✅ DISPATCH 信号已写入执行日志
📋 页面ID: {page_id}
🚪 Gate: {gate} - {info['name']}

请将以下指令复制到 Notion 页面，点击 @Notion AI 执行：

{'─'*60}
{info['prompt']}
{'─'*60}

Notion AI 完成后，请告知 Claude Code 执行:
python3 notion_cfd_loop.py --relay {page_id} ack
"""
        else:
            return f"✅ DISPATCH 信号已写入执行日志 (Gate: {gate})"
    else:
        return f"❌ DISPATCH 信号写入失败"


def relay_completion(page_id: str, gate: str, result_json: str, signal_id: str = None) -> str:
    """
    /relay completion - 写入 COMPLETION 信号（Notion AI 结果）

    解析优先级：
    1. ###HARNESS_RESPONSE_START### ... ###HARNESS_RESPONSE_END### 标记内容
    2. 标准 JSON（以 { 开头）
    3. Markdown 包裹的 JSON
    4. 正则提取 {...} 完整 JSON
    5. 表格格式解析
    6. 原始文本（最多500字符）
    """
    try:
        result = None
        text = result_json or ""

        # ★ 优先级1: 从唯一标记符中提取
        marker_match = re.search(
            r'###HARNESS_RESPONSE_START###\s*(.*?)\s*###HARNESS_RESPONSE_END###',
            text, re.DOTALL
        )
        if marker_match:
            marker_content = marker_match.group(1).strip()
            try:
                result = json.loads(marker_content)
                print(f"  [relay_completion] ✅ 从标记符中提取到 JSON ({len(marker_content)} chars)")
            except json.JSONDecodeError as e:
                print(f"  [relay_completion] ⚠️ 标记符内容 JSON 解析失败: {e}")
                # 标记符内容不是 JSON，但仍包含完整响应，记录原始内容
                result = {"raw_opus_response": marker_content[:2000], "parse_error": str(e)}

        # ★ 优先级2: 标准 JSON 解析
        if result is None and text.strip().startswith("{"):
            try:
                result = json.loads(text)
            except json.JSONDecodeError:
                cleaned = text.strip().strip("```json").strip("```").strip()
                try:
                    result = json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

        # ★ 优先级3: 正则提取完整 JSON
        if result is None:
            try:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # ★ 优先级4: 表格格式解析
        if result is None:
            parsed_table = _parse_table_or_text(text)
            if parsed_table:
                result = parsed_table

        # ★ 优先级5: 原始文本
        if result is None:
            result = {"raw_result": text[:500]} if text else {"raw_result": "(empty)"}

        # ★ 提取关键字段
        pass_status = result.get("pass", result.get("passed", None))
        next_action = result.get("next_action", "")
        raw_response = result.get("raw_opus_response", "")

        # ★ 如果有原始 Opus 响应，输出供确认
        if raw_response:
            print(f"\n  {'='*60}")
            print(f"  📋 Opus 原始回复（标记符提取）:")
            print(f"  {'='*60}")
            print(f"  {raw_response[:1000]}")
            if len(raw_response) > 1000:
                print(f"  ... (共 {len(raw_response)} 字符)")
            print(f"  {'='*60}\n")

        # 如果未指定 signal_id，查找对应的未完成 DISPATCH
        if not signal_id:
            _, signals = get_page_execution_log(page_id)
            dispatches = signals.get("DISPATCH", [])
            completions = signals.get("COMPLETION", [])
            completed_ids = {c.get("signal_id") for c in completions if c.get("signal_id")}
            for d in dispatches:
                if d.get("gate") == gate and d.get("signal_id") not in completed_ids:
                    signal_id = d.get("signal_id")
                    break

        signal_data = {
            "gate": gate,
            "signal_id": signal_id or "UNKNOWN",
            "pass": str(pass_status).upper() if pass_status is not None else "UNKNOWN",
            "next_action": next_action,
        }

        success = write_signal_to_log(page_id, "COMPLETION", signal_data)

        # ★ Evidence 自动沉淀：COMPLETION 写入成功后自动调用 deposit_evidence
        evidence_id = None
        if success:
            try:
                from state_machine import GateValidator
                gv = GateValidator()
                # pass_status 为 None 时视为 fail-safe（防污染）
                passed = bool(pass_status) if pass_status is not None else False
                _, evidence, evidence_id = gv.validate_and_deposit(page_id, gate)
                print(f"  [relay] ✅ Evidence {evidence_id} 已沉淀 (gate={gate}, pass={passed})")
            except Exception as e:
                print(f"  [relay] ⚠️ Evidence 沉淀失败: {e}")

        if success:
            ev_line = f"\n🔖 Evidence ID: {evidence_id}" if evidence_id else ""
            return f"""✅ COMPLETION 信号已写入
📋 页面ID: {page_id}
🚪 Gate: {gate}
🔗 Signal: {signal_id}
📊 Pass: {pass_status}{ev_line}
📌 Next: {next_action}
"""
        else:
            return "❌ COMPLETION 信号写入失败"

    except Exception as e:
        return f"❌ COMPLETION 处理失败: {e}"


def relay_ack(page_id: str, signal_id: str = None) -> str:
    """
    /relay ack - 发送 ACK 信号（确认收到 COMPLETION）
    """
    _, signals = get_page_execution_log(page_id)
    dispatches = signals.get("DISPATCH", [])
    completions = signals.get("COMPLETION", [])
    acked_ids = {a.get("acknowledged_signal_id") for a in signals.get("ACK", [])}

    # 如果未指定 signal_id，使用第一个未 ACK 的 DISPATCH
    if not signal_id:
        for d in dispatches:
            sid = d.get("signal_id", "")
            if sid and sid not in acked_ids:
                signal_id = sid
                break
        if not signal_id:
            return "❌ 没有待确认的 DISPATCH"

    # 找对应的 DISPATCH
    target_dispatch = None
    for d in dispatches:
        if d.get("signal_id") == signal_id:
            target_dispatch = d
            break

    # 找对应的 COMPLETION（gate 匹配最近的）
    gate = target_dispatch.get("gate", "") if target_dispatch else ""
    next_action = ""
    for c in reversed(completions):
        if c.get("gate") == gate:
            next_action = c.get("next_action", "")
            break

    signal_data = {
        "acknowledged_signal_id": signal_id,
        "gate": gate,
        "next_action": next_action or "继续执行下一任务",
    }

    success = write_signal_to_log(page_id, "ACK", signal_data)

    if success:
        return f"""✅ ACK 信号已写入
📋 页面ID: {page_id}
🔗 确认信号: {signal_id}
🚪 Gate: {gate}
📌 下一步: {next_action or '继续执行下一任务'}
"""
    else:
        return "❌ ACK 信号写入失败"


def relay_status(page_id: str) -> str:
    """简明状态输出"""
    status = relay_check(page_id)

    lines = [
        f"""
╔══════════════════════════════════════════════════════╗
║  Relay Protocol v1 — 传令状态检查                    ║
╠══════════════════════════════════════════════════════╣
║  页面ID: {status['page_id']}
║  📤 DISPATCH: {status['total_dispatches']} 个
║  📥 COMPLETION: {status['total_completions']} 个
║  ✅ ACK: {status['total_acks']} 个
╠══════════════════════════════════════════════════════╣"""
    ]

    pending = status["pending_dispatches"]
    if pending:
        lines.append("║  ⚠️  待确认的 DISPATCH:")
        for p in pending:
            lines.append(f"║     • {p.get('gate','?')} | signal_id={p.get('signal_id','?')} | {p.get('timestamp','')}")
    else:
        lines.append("║  ✅ 所有 DISPATCH 已完成")

    stale = status["stale_dispatches"]
    if stale:
        lines.append("║  ⏰ 超时 DISPATCH:")
        for s in stale:
            reason = s.get("stale_reason", f"超过 {TIMEOUT_MINUTES} 分钟")
            expires = s.get("expires_at", "")
            lines.append(f"║     • {s.get('gate','?')} | {s.get('timestamp','')} | {reason} | expires={expires}")

    if status["last_completion"]:
        lc = status["last_completion"]
        lines.append("╠══════════════════════════════════════════════════════╣")
        lines.append("║  📋 最近 COMPLETION:")
        lines.append(f"║     Gate: {lc.get('gate','?')} | Pass: {lc.get('pass','?')}")
        lines.append(f"║     Next: {lc.get('next_action','')[:50]}")

    if status["last_ack"]:
        la = status["last_ack"]
        lines.append("╠══════════════════════════════════════════════════════╣")
        lines.append("║  ✅ 最近 ACK:")
        lines.append(f"║     确认: {la.get('acknowledged_signal_id','?')} | Next: {la.get('next_action','')[:50]}")

    lines.append("╚══════════════════════════════════════════════════════╝")

    return "\n".join(lines)


# ============ Auto Trigger — Playwright 自动化 ============
# 使用 Playwright + Chrome 自动化触发 Notion AI

NOTION_EMAIL = "your-email@example.com"  # TODO: 设置你的 Notion 邮箱
CHROME_PROFILE_PATH = "/Users/Zhuanz/Library/Application Support/Google/Chrome/Profile-NotionAuto"


def _launch_notion_browser(headless: bool = False, use_chrome: bool = True):
    """
    启动浏览器并返回 context 和 page
    use_chrome=True: 使用 Google Chrome（需要用户登录一次）
    use_chrome=False: 使用 Playwright 内置 Chromium（无需登录）
    """
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()

    if use_chrome:
        # 使用用户的 Google Chrome（需要先关闭正在运行的 Chrome）
        context = p.chromium.launch_persistent_context(
            CHROME_PROFILE_PATH,
            channel="chrome",
            headless=headless,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"]
        )
    else:
        # 使用 Playwright 内置 Chromium（无需登录，但 Notion AI 功能可能受限）
        context = p.chromium.launch(
            headless=headless,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"]
        )

    page = context.new_page()
    return p, context, page


def _wait_for_notion_login(page, timeout: int = 60) -> bool:
    """等待用户登录 Notion，超时返回 False"""
    from playwright.sync_api import sync_playwright
    import time

    start = time.time()
    while time.time() - start < timeout:
        url = page.url
        # 检测是否已登录（notion.so 主域名且无 login 路径）
        if "notion.so" in url and "/login" not in url and "auth" not in url:
            # 尝试访问一个 API 端点验证登录状态
            try:
                resp = page.evaluate("""async () => {
                    const r = await fetch('/api/v1/get 활성화Workspaces', {
                        credentials: 'include'
                    });
                    return r.ok;
                }""")
                if resp:
                    return True
            except Exception:
                pass
        time.sleep(2)
    return False


def _write_dispatch_to_page(page, page_url: str, gate: str, prompt_text: str) -> bool:
    """在 Notion 页面写入 DISPATCH 指令块"""
    from playwright.sync_api import sync_playwright

    page.goto(page_url)
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(2000)

    try:
        # 点击页面空白处，确保在编辑模式
        page.click("body")
        page.wait_for_timeout(500)

        # 模拟键盘输入 dispatch 指令
        # 先按 / 打开 commands，找到 "Text" 或直接输入
        page.keyboard.press("End")
        page.wait_for_timeout(300)

        # 创建新 block：按 Enter 新行，然后输入
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)

        # 输入分隔线
        page.keyboard.type("=" * 40)
        page.keyboard.press("Enter")

        # 输入 DISPATCH 标记
        page.keyboard.type(f"[DISPATCH] Gate={gate}")
        page.keyboard.press("Enter")

        # 输入 prompt 内容（逐行）
        lines = prompt_text.split("\n")
        for line in lines:
            page.keyboard.type(line)
            page.keyboard.press("Enter")

        page.keyboard.type("=" * 40)
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)

        return True
    except Exception as e:
        print(f"写入 dispatch 失败: {e}")
        return False


def _trigger_notion_ai(page, instruction_text: str) -> str:
    """在页面选中文字并触发 @Notion AI，返回 AI 回复内容"""
    from playwright.sync_api import sync_playwright
    import time

    try:
        # 选中指令文字（通过拖选）
        # 找到包含 DISPATCH 的文字块
        dispatches = page.locator("text=[DISPATCH]")
        count = dispatches.count()
        if count == 0:
            return "ERROR: 未找到 DISPATCH 指令"

        last_dispatch = dispatches.last
        last_dispatch.scroll_into_view_if_needed()
        last_dispatch.wait_for(timeout=5000)

        # 选中从 DISPATCH 到结尾的范围
        last_dispatch.click()
        page.keyboard.press("End")
        page.keyboard.down("Shift")
        for _ in range(30):
            page.keyboard.press("Home")
            page.keyboard.press("ArrowUp")
        page.keyboard.up("Shift")
        page.wait_for_timeout(500)

        # 输入 @Notion AI 触发
        page.keyboard.type("@Notion AI")
        page.wait_for_timeout(1000)

        # 等待 AI 选项出现并点击
        ai_option = page.locator("text=Notion AI").first
        if ai_option.is_visible(timeout=5000):
            ai_option.click()
            page.wait_for_timeout(500)
        else:
            # 尝试按 Enter 选择
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)

        # 等待 AI 处理（显示 "Thinking..." 或类似状态）
        print("  🤖 Notion AI 正在处理...")
        max_wait = 120  # 最多等 2 分钟
        start = time.time()
        last_height = 0

        while time.time() - start < max_wait:
            page.wait_for_timeout(3000)

            # 检查是否有新的 AI 回复块出现
            # Notion AI 回复会创建新的 block
            new_blocks = page.locator("[data-block-id]")
            new_count = new_blocks.count()

            # 查找包含 pass/key 等关键词的 block（可能是 AI 回复）
            try:
                # AI 回复通常在选中文本下方，带有不同的样式
                # 检查是否有 "block" 类的元素变化
                response_candidate = page.locator(".notion-selectable").last
                if response_candidate.is_visible(timeout=2000):
                    text = response_candidate.inner_text()
                    if text and len(text) > 20:
                        print(f"  ✅ 收到 AI 回复 ({len(text)} chars)")
                        return text
            except Exception:
                pass

            if new_count > last_height:
                print(f"  ⏳ 等待 AI 生成... ({new_count} blocks)")
                last_height = new_count

        return "TIMEOUT: Notion AI 处理超时"

    except Exception as e:
        return f"ERROR: 触发失败 - {e}"


def auto_trigger(page_id: str, gate: str) -> str:
    """
    --auto-trigger: 全自动触发 Notion AI 执行 Gate 审查
    1. 启动 Chrome (Profile-NotionAuto)
    2. 引导登录（首次）
    3. 写入 DISPATCH 指令
    4. 触发 @Notion AI
    5. 读取回复
    6. 写入 COMPLETION + ACK
    """
    gate_type = gate.upper()
    if gate_type not in OPUS_PROMPTS:
        return f"❌ 未知 Gate: {gate_type}，可用: {', '.join(OPUS_PROMPTS.keys())}"

    info = OPUS_PROMPTS[gate_type]
    prompt_text = info["prompt"]
    page_url = f"https://notion.so/{page_id.replace('-', '')}"

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  🚀 Auto Trigger — Notion AI 自动化执行                        ║
╠══════════════════════════════════════════════════════════════════╣
║  页面ID: {page_id}
║  Gate:   {gate_type} - {info['name']}
║  浏览器: Chrome (Profile-NotionAuto)
╚══════════════════════════════════════════════════════════════════╝
""")

    try:
        from playwright.sync_api import sync_playwright
        import time

        p, context, page = _launch_notion_browser(headless=False)

        try:
            # Step 1: 导航到页面
            print("  📄 打开 Notion 页面...")
            page.goto(page_url)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Step 2: 检查登录状态
            print("  🔐 检查登录状态...")
            current_url = page.url
            if "notion.so" not in current_url or "/login" in current_url or "auth" in current_url:
                print("  ⚠️  需要登录 Notion")
                print("  📝 请在浏览器中完成登录（电子邮箱 + 密码）")
                print("  ⏳ 等待登录完成（最多 180 秒）...")
                # 等待 URL 变为 Notion 主域名且不含 login
                page.wait_for_url(
                    lambda url: "notion.so" in url and "/login" not in url and "auth" not in url,
                    timeout=180
                )
                page.wait_for_timeout(2000)
                print("  ✅ 登录成功，继续执行...")

            # Step 3: 等待页面完全加载
            print("  ⏳ 等待 Notion 页面加载...")
            page.wait_for_timeout(5000)

            # Step 4: 写入 DISPATCH 指令
            print("  ✍️  写入 DISPATCH 指令...")

            # 滚动到页面底部
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)

            # 找到可编辑区域并点击
            page.keyboard.press("End")
            page.wait_for_timeout(300)
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)

            # 输入 DISPATCH 标记
            separator = "=" * 50
            page.keyboard.type(separator)
            page.keyboard.press("Enter")
            page.keyboard.type(f"[DISPATCH] gate={gate_type} | auto-trigger")
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)

            # 输入 prompt 内容
            for line in prompt_text.split("\n"):
                page.keyboard.type(line)
                page.keyboard.press("Enter")
                page.wait_for_timeout(50)

            page.keyboard.type(separator)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)
            print("  ✅ DISPATCH 指令已写入页面")

            # Step 5: 记录 DISPATCH 前的 block 状态（用于区分 AI 新增内容）
            print("  📸 记录 DISPATCH 前页面状态...")
            before_blocks = page.locator("[data-block-id]").all()
            before_block_ids = set()
            before_block_texts = []
            for b in before_blocks:
                try:
                    bid = b.get_attribute("data-block-id")
                    text = b.inner_text()
                    if bid:
                        before_block_ids.add(bid)
                    before_block_texts.append(text[:200])
                except Exception:
                    pass
            print(f"  📸 DISPATCH 前: {len(before_block_ids)} 个 blocks")

            # Step 6: 选中刚才写入的内容并触发 @Notion AI
            print("  🤖 触发 @Notion AI...")

            page.evaluate("window.scrollBy(0, -400)")
            page.wait_for_timeout(800)
            page.keyboard.press("Home")
            page.wait_for_timeout(200)

            # 搜索 DISPATCH 文字位置
            found = False
            for _ in range(20):
                try:
                    page.keyboard.press("End")
                    page.wait_for_timeout(50)
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(50)
                    selected = page.evaluate("window.getSelection().toString()")
                    if "DISPATCH" in selected:
                        found = True
                        break
                except Exception:
                    pass

            if not found:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
                page.keyboard.press("End")
                for _ in range(30):
                    page.keyboard.press("ArrowUp")
                    page.wait_for_timeout(50)
                    try:
                        selected = page.evaluate("window.getSelection().toString()")
                        if "DISPATCH" in selected:
                            found = True
                            break
                    except Exception:
                        pass

            if found:
                page.keyboard.down("Shift")
                for _ in range(30):
                    page.keyboard.press("ArrowDown")
                page.keyboard.up("Shift")
                page.wait_for_timeout(500)

            # 触发 @Notion AI mention
            page.keyboard.type("@")
            page.wait_for_timeout(1000)

            try:
                notion_ai = page.locator("div[role='option'], span[role='menuitem']").filter(has_text="Notion AI").first
                if notion_ai.is_visible(timeout=5000):
                    notion_ai.click()
                    print("    ✓ 选中了 Notion AI")
                    page.wait_for_timeout(500)
                else:
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(500)
            except Exception as e:
                print(f"    ⚠️  自动点击失败，尝试 Enter: {e}")
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)

            # Step 7: 等待 AI 处理 - 使用 BEFORE/AFTER 对比法
            print("  ⏳ 等待 Notion AI 生成回复（最多 3 分钟）...")
            print("  💡 你也可以在浏览器中查看处理进度")
            max_wait = 180
            start = time.time()
            ai_response = ""
            new_blocks_found = False
            all_new_block_texts = []

            while time.time() - start < max_wait:
                page.wait_for_timeout(5000)
                elapsed = int(time.time() - start)

                # 获取当前所有 block
                current_blocks = page.locator("[data-block-id]").all()
                current_block_ids = set()
                for b in current_blocks:
                    try:
                        bid = b.get_attribute("data-block-id")
                        if bid:
                            current_block_ids.add(bid)
                    except Exception:
                        pass

                # 找出 NEW blocks（之前没有的）
                new_block_ids = current_block_ids - before_block_ids

                if new_block_ids:
                    # 有新 blocks！提取内容
                    new_blocks_found = True
                    new_block_contents = []
                    for b in current_blocks:
                        try:
                            bid = b.get_attribute("data-block-id")
                            if bid in new_block_ids:
                                text = b.inner_text()
                                new_block_contents.append(text)
                        except Exception:
                            pass

                    # ★ 优先检查是否包含标记符（最可靠的 Opus 回复检测）
                    for text in new_block_contents:
                        if "###HARNESS_RESPONSE_START###" in text and "###HARNESS_RESPONSE_END###" in text:
                            ai_response = text
                            print(f"  ✅ 检测到带标记符的 AI 回复! ({len(text)} chars)")
                            break

                    if ai_response:
                        break

                    # ★ 否则检查是否有实质性 AI 回复（非 prompt 内容）
                    for text in new_block_contents:
                        if not text or len(text.strip()) < 10:
                            continue
                        # 跳过包含 DISPATCH 标记的行（是我们自己写的）
                        if "DISPATCH" in text or separator in text or "auto-trigger" in text:
                            continue
                        # 跳过包含完整 prompt 内容的行
                        if prompt_text[:50] in text:
                            continue
                        # 跳过 Notion AI 的自我指令
                        if "请执行以下任务" in text or "sync_task_to_notion" in text:
                            continue

                        # 找到了实质性 AI 回复！
                        ai_response = text
                        break

                    if ai_response:
                        print(f"  ✅ 检测到 AI 回复! ({len(ai_response)} chars)")
                        break
                    else:
                        # 有新 blocks 但还没找到实质性内容，继续等待
                        all_new_block_texts = new_block_contents
                        print(f"    ⏳ 已等待 {elapsed}s... 有 {len(new_block_ids)} 个新 block，等待更多内容...")

                # 打印 loading 状态
                try:
                    loading_indicators = page.locator("text=Thinking, text=Generating, text=Processing").first
                    if loading_indicators.is_visible(timeout=1000):
                        print(f"    ⏳ AI 正在思考中... ({elapsed}s)")
                except Exception:
                    pass

            # Step 8: 输出所有新 blocks 进行人工审查
            print()
            print("=" * 70)
            print("  📋 AI 回复内容（所有新生成的 blocks）:")
            print("=" * 70)

            if ai_response:
                print(ai_response[:3000])
                if len(ai_response) > 3000:
                    print(f"\n  ... (共 {len(ai_response)} 字符，超出显示)")
            elif new_blocks_found:
                print("  ⚠️  自动检测未通过，以下为所有新 block 内容，请人工确认:")
                for i, text in enumerate(all_new_block_texts):
                    print(f"\n  --- New Block {i+1} ({len(text)} chars) ---")
                    print(text[:1000])
            else:
                print("  ❌ 超时: 页面上未检测到任何新 block 生成")
                print("  💡 建议: 请在浏览器中手动查看页面是否已有 AI 回复")
            print("=" * 70)

            # Step 9: 关闭浏览器
            print("  🔒 关闭浏览器...")
            context.close()
            p.stop()

            # Step 10: 写入 COMPLETION 和 ACK（无论 AI 回复是否找到都写入）
            print()
            print("  📤 写入 COMPLETION + ACK 信号...")

            # 如果找到了实质性 AI 回复，解析它
            if ai_response and len(ai_response) > 20:
                completion_result = relay_completion(page_id, gate_type, ai_response)
                ack_result = relay_ack(page_id, signal_id=None)
            else:
                # AI 回复不完整或未找到，尝试用页面最后的内容
                completion_result = relay_completion(page_id, gate_type,
                    '{"gate":"' + gate_type + '","pass":null,"note":"AI_RESPONSE_INCOMPLETE","next_action":"manual_review_required"}')
                ack_result = relay_ack(page_id, signal_id=None)

            return f"""
╔══════════════════════════════════════════════════════════════════╗
║  ✅ Auto Trigger 完成                                          ║
╠══════════════════════════════════════════════════════════════════╣
  AI 回复状态: {"✅ 找到" if ai_response and len(ai_response) > 20 else "⚠️ 未找到/不完整"}
  新 Block 数: {len(all_new_block_texts) if new_blocks_found else 0}
{completion_result}
{ack_result}
╚══════════════════════════════════════════════════════════════════╝
"""

        finally:
            try:
                context.close()
                p.stop()
            except Exception:
                pass

    except Exception as e:
        import traceback
        return f"❌ Auto Trigger 失败: {e}\n{traceback.format_exc()}"


def cmd_auto_trigger(args: List[str]) -> str:
    """处理 --auto-trigger 命令"""
    if len(args) < 1:
        return """用法:
  python3 notion_cfd_loop.py --auto-trigger <page_id> <G0|G1|G2|G3|G4|G5|G6>

示例:
  python3 notion_cfd_loop.py --auto-trigger 33ac6894-2bed-817a-b755-e574f2a79c77 G1
"""
    page_id = args[0]
    if len(args) < 2:
        return "❌ 用法: --auto-trigger <page_id> <gate>"
    gate = args[1]
    return auto_trigger(page_id, gate)


def auto_trigger_status(page_id: str) -> str:
    """简明状态输出（auto_trigger 用）"""
    status = relay_check(page_id)

    lines = [
        f"""
╔══════════════════════════════════════════════════════╗
║  Relay Protocol v1 — 传令状态检查                    ║
╠══════════════════════════════════════════════════════╣
║  页面ID: {status['page_id']}
║  📤 DISPATCH: {status['total_dispatches']} 个
║  📥 COMPLETION: {status['total_completions']} 个
║  ✅ ACK: {status['total_acks']} 个
╠══════════════════════════════════════════════════════╣"""
    ]

    pending = status["pending_dispatches"]
    if pending:
        lines.append("║  ⚠️  待确认的 DISPATCH:")
        for p in pending:
            lines.append(f"║     • {p.get('gate','?')} | signal_id={p.get('signal_id','?')} | {p.get('timestamp','')}")
    else:
        lines.append("║  ✅ 所有 DISPATCH 已完成")

    stale = status["stale_dispatches"]
    if stale:
        lines.append("║  ⏰ 超时 DISPATCH:")
        for s in stale:
            reason = s.get("stale_reason", f"超过 {TIMEOUT_MINUTES} 分钟")
            expires = s.get("expires_at", "")
            lines.append(f"║     • {s.get('gate','?')} | {s.get('timestamp','')} | {reason} | expires={expires}")

    if status["last_completion"]:
        lc = status["last_completion"]
        lines.append("╠══════════════════════════════════════════════════════╣")
        lines.append("║  📋 最近 COMPLETION:")
        lines.append(f"║     Gate: {lc.get('gate','?')} | Pass: {lc.get('pass','?')}")
        lines.append(f"║     Next: {lc.get('next_action','')[:50]}")

    if status["last_ack"]:
        la = status["last_ack"]
        lines.append("╠══════════════════════════════════════════════════════╣")
        lines.append("║  ✅ 最近 ACK:")
        lines.append(f"║     确认: {la.get('acknowledged_signal_id','?')} | Next: {la.get('next_action','')[:50]}")

    lines.append("╚══════════════════════════════════════════════════════╝")

    return "\n".join(lines)


def cmd_relay(args: List[str]) -> str:
    """
    处理 /relay 命令
    用法: python3 notion_cfd_loop.py --relay <page_id> <check|dispatch|ack|completion> [args...]
    """
    if len(args) < 1:
        return """用法:
  python3 notion_cfd_loop.py --relay <page_id> check
  python3 notion_cfd_loop.py --relay <page_id> dispatch <G0|G1|...> [prompt_text]
  python3 notion_cfd_loop.py --relay <page_id> ack [signal_id]
  python3 notion_cfd_loop.py --relay <page_id> completion <gate> <json_result>
  python3 notion_cfd_loop.py --relay <page_id> status
"""

    page_id = args[0]
    if len(args) < 2:
        return cmd_relay([])

    subcmd = args[1].lower()

    if subcmd == "check":
        return relay_status(page_id)

    elif subcmd == "status":
        return relay_status(page_id)

    elif subcmd == "dispatch":
        if len(args) < 3:
            return "❌ 用法: --relay <page_id> dispatch <gate> [prompt_text]"
        gate = args[2]
        prompt = args[3] if len(args) > 3 else ""
        return relay_dispatch(page_id, gate, prompt)

    elif subcmd == "ack":
        signal_id = args[2] if len(args) > 2 else None
        return relay_ack(page_id, signal_id)

    elif subcmd == "completion":
        if len(args) < 4:
            return "❌ 用法: --relay <page_id> completion <gate> <json_result> [signal_id]"
        gate = args[2]
        result_json = args[3]
        signal_id = args[4] if len(args) > 4 else None
        return relay_completion(page_id, gate, result_json, signal_id)

    else:
        return f"❌ 未知子命令: {subcmd}"


def cmd_agent_route(args: List[str]) -> str:
    """
    处理 --agent-route 命令
    用法: python3 notion_cfd_loop.py --agent-route <task_id> [instruction_text]
    示例: python3 notion_cfd_loop.py --agent-route M1-4 "实现状态机的测试覆盖"
          python3 notion_cfd_loop.py --agent-route M1-4 --force codex "强制用 Codex"
          python3 notion_cfd_loop.py --agent-route M1-4 --show    # 只显示路由，不执行
    """
    if len(args) < 1:
        return """用法:
  python3 notion_cfd_loop.py --agent-route <task_id> <instruction>  # 查看路由并生成执行命令
  python3 notion_cfd_loop.py --agent-route <task_id> --force <model> <instruction>  # 强制指定模型
  python3 notion_cfd_loop.py --agent-route <task_id> --show           # 仅显示路由信息

可用模型: notion_opus, notion_sonnet, codex, glm_51, minimax_27
示例任务ID: M1-1, M1-2, M1-3, M1-4, M1-5, M1-6, G3, G4, G5, G6
"""

    task_id = args[0]

    # --show: 只显示路由
    if len(args) == 2 and args[1] == "--show":
        routing = get_model_for_task(task_id)
        primary_info = MODEL_REGISTRY.get(routing["primary"], {})
        fallback_info = MODEL_REGISTRY.get(routing["fallback"], {})
        reviewer_info = MODEL_REGISTRY.get(routing.get("notion_reviewer", ""), {})
        return f"""╔══════════════════════════════════════════════════════════════╗
║  模型路由查询: {task_id}
╠══════════════════════════════════════════════════════════════╣
║  任务描述: {routing['description']}
║  执行模型: {primary_info.get('name', '?')}
║  备用模型: {fallback_info.get('name', '?')}
║  审查模型: {reviewer_info.get('name', '?')}
║  路由原因: {routing.get('reason', '无')}
╚══════════════════════════════════════════════════════════════╝"""

    # --force <model>: 强制指定模型
    force_model = None
    instruction_idx = 1
    if len(args) > 2 and args[1] == "--force":
        force_model = args[2]
        instruction_idx = 3
        if force_model not in MODEL_REGISTRY:
            return f"❌ 未知模型: {force_model}，可用: {list(MODEL_REGISTRY.keys())}"

    instruction = " ".join(args[instruction_idx:]) if instruction_idx < len(args) else ""

    routing = get_model_for_task(task_id)
    if force_model is None:
        primary_info = MODEL_REGISTRY.get(routing["primary"], {})
    else:
        primary_info = MODEL_REGISTRY.get(force_model, {})

    route_cmd = agent_dispatch(task_id, instruction, force_model=force_model)

    return f"""╔══════════════════════════════════════════════════════════════╗
║  模型路由已生成: {task_id}
╠══════════════════════════════════════════════════════════════╣
║  任务: {task_id} — {routing['description']}
║  执行模型: {primary_info.get('name', '?')} ({primary_info.get('callsign', '')})
║  原因: {routing.get('reason', '无')}
╠══════════════════════════════════════════════════════════════╣
║  Claude Code 执行命令:
╚══════════════════════════════════════════════════════════════╝

{route_cmd}"""


def sync_model_routing_to_notion(page_id: str) -> str:
    """
    将当前任务的模型路由同步到 v1 Tasks 页面属性。
    """
    try:
        page = notion_get(f"pages/{page_id}")
        task_key = _extract_task_title(page)
        routing = get_model_for_task(task_key)

        log_property_name, existing_summary = _get_task_log_property(page)
        sync_line = (
            f"[MODEL_SYNC] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"task_key={task_key} | executor={routing['primary']} | fallback={routing['fallback']}"
        )
        if routing.get("reason"):
            sync_line += f" | reason={routing['reason']}"

        summary_parts = [part for part in [existing_summary.strip(), sync_line] if part]
        properties = {
            "Executor Model": _build_rich_text(routing["primary"]),
            "Fallback Model": _build_rich_text(routing["fallback"]),
            log_property_name: _build_rich_text("\n".join(summary_parts)),
        }
        notion_patch(f"pages/{page_id}", {"properties": properties})

        return (
            f"✅ 模型路由已同步到 v1 Tasks\n"
            f"📋 页面ID: {page_id}\n"
            f"🧩 Task Key: {task_key}\n"
            f"🤖 Executor: {routing['primary']}\n"
            f"🛟 Fallback: {routing['fallback']}"
        )

    except Exception as e:
        return f"❌ 同步失败: {e}"


# ============ 演示 ============

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║     Well-Harness CLI 工具                                    ║
║     Claude Code ↔ Notion AI 双向同步                         ║
╚══════════════════════════════════════════════════════════════╝

用法（复制到 Claude Code 执行）:

1. 查询待处理任务:
   python3 notion_cfd_loop.py --query

2. 创建任务指令:
   python3 notion_cfd_loop.py --create-task "父页面ID" "标题" "描述"

3. 同步项目状态:
   python3 notion_cfd_loop.py --sync "项目ID" "phase状态" "执行摘要"

4. 启动轮询循环:
   python3 notion_cfd_loop.py --loop

5. 触发 Notion AI (Opus 4.6) 指令:
   python3 notion_cfd_loop.py --opus-prompt <G0|G1|G2|G3|G4|G5|G6|ARCH|TASK>

6. Relay 传令协议 v1:
   python3 notion_cfd_loop.py --relay <page_id> check          # 查看传令状态
   python3 notion_cfd_loop.py --relay <page_id> dispatch <GATE> # 发送 DISPATCH 并触发 Opus
   python3 notion_cfd_loop.py --relay <page_id> ack [signal_id]  # 确认 COMPLETION
   python3 notion_cfd_loop.py --relay <page_id> completion <gate> <json>  # 写入 COMPLETION
   python3 notion_cfd_loop.py --relay <page_id> status          # 简明状态

7. Auto Trigger（浏览器自动化）:
   python3 notion_cfd_loop.py --auto-trigger <page_id> <G0|G1|G2|G3|G4|G5|G6>
   # 启动 Chrome (Profile-NotionAuto)，自动写入 DISPATCH → 触发 @Notion AI → 读取回复

8. 模型路由层:
   python3 notion_cfd_loop.py --model-status              # 查看所有模型和路由表
   python3 notion_cfd_loop.py --agent-route M1-4 --show   # 查询任务路由（不执行）
   python3 notion_cfd_loop.py --agent-route M1-4 "实现pytest测试"  # 生成执行命令
   python3 notion_cfd_loop.py --agent-route M1-4 --force codex "强制用Codex"
   python3 notion_cfd_loop.py --sync-models <page_id>     # 同步路由表到 Notion 页面
""")

    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--query":
            print("\n📋 查询待处理任务:")
            for status in ["待领取", "执行中"]:
                tasks = query_pending_tasks(status)
                print(f"  [{status}]: {len(tasks)} 个")
        elif cmd == "--loop":
            run_harness_loop(interval=30, max_iterations=3)
        elif cmd == "--opus-prompt":
            if len(sys.argv) < 3:
                print("用法: python3 notion_cfd_loop.py --opus-prompt <G0|G1|G2|G3|G4|G5|G6|ARCH|TASK>")
            else:
                gate_type = sys.argv[2].upper()
                output_opus_prompt(gate_type)
        elif cmd == "--relay":
            # --relay <page_id> <check|dispatch|ack|completion> [args...]
            relay_args = sys.argv[2:]
            result = cmd_relay(relay_args)
            print(result)
        elif cmd == "--auto-trigger":
            auto_args = sys.argv[2:]
            result = cmd_auto_trigger(auto_args)
            print(result)
        elif cmd == "--agent-route":
            # --agent-route <task_id> [instruction]
            route_args = sys.argv[2:]
            result = cmd_agent_route(route_args)
            print(result)
        elif cmd == "--model-status":
            print(agent_status_report())
        elif cmd == "--sync-models":
            # 同步模型路由表到 Notion
            sync_args = sys.argv[2:]
            if len(sync_args) < 1:
                print("用法: python3 notion_cfd_loop.py --sync-models <page_id>")
            else:
                result = sync_model_routing_to_notion(sync_args[0])
                print(result)
        elif cmd == "--deposit-evidence":
            # 执行 Gate 校验并自动沉淀证据到 Evidence 库
            from state_machine import GateValidator
            dep_args = sys.argv[2:]
            if len(dep_args) < 2:
                print("用法: python3 notion_cfd_loop.py --deposit-evidence <page_id> <G0|G1|G2|G3|G4|G5|G6>")
            else:
                page_id, gate = dep_args[0], dep_args[1].upper()
                gv = GateValidator()
                passed, evidence, eid = gv.validate_and_deposit(page_id, gate)
                print(f"""╔══════════════════════════════════════════════════════════════╗
║  Evidence 沉淀结果
╠══════════════════════════════════════════════════════════════╣
║  Page:   {page_id}
║  Gate:   {gate}
║  Pass:    {'✅ 通过' if passed else '❌ 失败'}
║  Evidence ID: {eid or '写入失败'}
║  Result: {evidence.get('result', '')}
║  Message: {evidence.get('message', '')}
╚══════════════════════════════════════════════════════════════╝""")
