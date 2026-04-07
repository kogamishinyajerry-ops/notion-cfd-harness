#!/usr/bin/env python3
"""
Well-Harness M1-3 TaskWizard 模块
GLM-5.1 生成 + Claude Code 字段适配
"""

import re
import requests
import json
import logging
import os
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ============ API 常量 ============
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
# v1架构: Tasks数据库
TASKS_DB_ID = "33bc6894-2bed-8196-8e2c-d1d66e631c31"
NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
}

# ============ TaskWizard ============

class TaskWizard:
    """
    M1-3 Task 创建向导核心类

    Methods:
        parse_natural_language(desc: str) -> dict
            将中文CFD任务描述解析为结构化字典

        create_notion_task(task_data: dict, parent_page_id: str = None) -> str
            在 v1 Tasks DB 中创建任务页面，返回 page_id

        validate_g0(page_id: str) -> dict
            执行 G0 门校验，返回 evidence 字典
    """

    # v1 Tasks DB 字段名映射
    FIELD_MAP = {
        "title": "Task ID",
        "linked_phase": "Linked Phase",
        "linked_project": "Linked Project",
        "task_type": "Task Type",
        "priority": "Priority",
        "executor_model": "Executor Model",
        "fallback_model": "Fallback Model",
        "status": "Task Status",
        "git_branch": "Git Branch",
        "pr_link": "PR Link",
        "artifact_link": "Artifact Link",
        "failure_reason": "Failure Reason",
        "retry_count": "Retry Count",
        "last_run_summary": "Last Run Summary",
    }

    TASK_TYPE_OPTIONS = {"指令", "分析", "审查", "学习", "任务"}
    PRIORITY_MAP = {"P0": "P1", "P1": "P2", "P2": "P3", "P3": "P3"}

    def __init__(self, notion_api_key: Optional[str] = None):
        self.api_key = notion_api_key or NOTION_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    @staticmethod
    def _build_rich_text(content: str) -> dict:
        return {"rich_text": [{"text": {"content": str(content)[:1900]}}]}

    @staticmethod
    def _rich_text_plain(prop: dict) -> str:
        texts = []
        for item in prop.get("rich_text", []):
            plain_text = item.get("plain_text")
            if plain_text is not None:
                texts.append(plain_text)
            else:
                texts.append(item.get("text", {}).get("content", ""))
        return "".join(texts)

    @staticmethod
    def _title_plain(prop: dict) -> str:
        texts = []
        for item in prop.get("title", []):
            plain_text = item.get("plain_text")
            if plain_text is not None:
                texts.append(plain_text)
            else:
                texts.append(item.get("text", {}).get("content", ""))
        return "".join(texts)

    def _normalize_priority(self, priority: str) -> str:
        return self.PRIORITY_MAP.get(priority or "P1", "P2")

    def _normalize_task_type(self, task_type: str) -> str:
        if task_type in self.TASK_TYPE_OPTIONS:
            return task_type
        return "任务"

    def _build_last_run_summary(self, task_data: dict, linked_project: str, linked_phase: str) -> str:
        summary_lines = [
            f"原始描述: {task_data.get('raw_description', '')}",
            f"验收标准: {self._build_acceptance_criteria(task_data)}",
            (
                "Harness摘要: "
                f"任务类型={task_data.get('task_type')} | "
                f"几何={','.join(task_data.get('geometry_features', []))} | "
                f"边界条件={json.dumps(task_data.get('boundary_conditions', {}), ensure_ascii=False)} | "
                f"收敛标准={task_data.get('convergence_criteria')}"
            ),
        ]
        if linked_project:
            summary_lines.append(f"Linked Project: {linked_project}")
        if linked_phase:
            summary_lines.append(f"Linked Phase: {linked_phase}")
        return "\n".join(summary_lines)

    # ---- 自然语言解析 ----

    def parse_natural_language(self, desc: str) -> dict:
        """
        解析中文CFD任务描述，返回结构化任务字典。

        提取字段：
          - task_type: 任务类型（稳态仿真/瞬态仿真/形状优化/基准验证）
          - priority: 优先级（P0/P1/P2）
          - geometry_features: 几何特征列表
          - boundary_conditions: 边界条件字典
          - convergence_criteria: 收敛标准
          - solver_type: 求解器类型
          - fluid_properties: 流体物性

        Returns:
            dict 结构化任务数据
        """
        task_data = {
            "raw_description": desc,
            "task_type": "稳态仿真",
            "priority": "P1",
            "geometry_features": [],
            "boundary_conditions": {},
            "convergence_criteria": "10^-4",
            "solver_type": None,
            "fluid_properties": {},
            "extracted_keywords": [],
        }

        desc_lower = desc.lower()

        # 1. 优先级
        if re.search(r'紧急|最高优先级|高优先级|P0', desc):
            task_data["priority"] = "P0"
        elif re.search(r'普通优先级|正常优先级|P1', desc):
            task_data["priority"] = "P1"
        elif re.search(r'低优先级|P2', desc):
            task_data["priority"] = "P2"

        # 2. 任务类型
        if re.search(r'瞬态|非定常|unsteady|time.?dependent', desc, re.IGNORECASE):
            task_data["task_type"] = "瞬态仿真"
        elif re.search(r'稳态|定常|steady.?state', desc, re.IGNORECASE):
            task_data["task_type"] = "稳态仿真"
        elif re.search(r'优化|形状调整|optimization', desc, re.IGNORECASE):
            task_data["task_type"] = "形状优化"
        elif re.search(r'基准|验证|benchmark|validation', desc, re.IGNORECASE):
            task_data["task_type"] = "基准验证"
        elif re.search(r'参数研究|敏感性|sensitivity', desc, re.IGNORECASE):
            task_data["task_type"] = "参数研究"

        # 3. 几何特征
        geo_patterns = [
            (r'圆柱绕流|圆柱', '圆柱绕流'),
            (r'翼型|机翼|airfoil', '翼型气动'),
            (r'管道|管内|duct', '管道内流'),
            (r'阀门|valve', '阀门流道'),
            (r'平板|flat.?plate', '平板边界层'),
            (r'喷嘴|nozzle', '喷嘴流动'),
            (r'扩压器|diffuser', '扩压器流动'),
            (r'弯头|elbow', '弯头湍流'),
            (r'叶轮|impeller|blade', '叶轮机械'),
        ]
        for pattern, label in geo_patterns:
            if re.search(pattern, desc, re.IGNORECASE):
                task_data["geometry_features"].append(label)

        if not task_data["geometry_features"]:
            task_data["geometry_features"].append("通用几何")

        # 4. 边界条件
        if re.search(r'速度入口|进风|来流|进水|inlet', desc, re.IGNORECASE):
            vel_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m\/s|米每秒|ma(?:ch)?)', desc, re.IGNORECASE)
            if vel_match:
                task_data["boundary_conditions"]["inlet_velocity"] = f"{vel_match.group(1)} m/s"
            else:
                task_data["boundary_conditions"]["inlet_type"] = "速度入口"

        if re.search(r'压力入口|pressure.?inlet', desc, re.IGNORECASE):
            task_data["boundary_conditions"]["inlet_type"] = "压力入口"

        if re.search(r'出口|outlet', desc, re.IGNORECASE):
            task_data["boundary_conditions"]["outlet_type"] = "压力出口"

        if re.search(r'壁面|wall', desc, re.IGNORECASE):
            if re.search(r'无滑移?|no.?slip', desc, re.IGNORECASE):
                task_data["boundary_conditions"]["wall_condition"] = "无滑移壁面"
            elif re.search(r'滑移|slip', desc, re.IGNORECASE):
                task_data["boundary_conditions"]["wall_condition"] = "滑移壁面"

        if re.search(r'对称|symmetr', desc, re.IGNORECASE):
            task_data["boundary_conditions"]["symmetry"] = "对称边界"

        # 5. 收敛标准
        conv_match = re.search(r'收敛标准\s*(?:为|:|：)?\s*(10\^?-?\d+|1e-?\d+)', desc, re.IGNORECASE)
        if conv_match:
            task_data["convergence_criteria"] = conv_match.group(1)

        # 6. 流体物性
        if re.search(r'空气|air', desc, re.IGNORECASE):
            task_data["fluid_properties"]["medium"] = "空气"
            task_data["fluid_properties"]["density"] = "1.225 kg/m³"
            task_data["fluid_properties"]["viscosity"] = "1.81e-5 Pa·s"
        elif re.search(r'水|water', desc, re.IGNORECASE):
            task_data["fluid_properties"]["medium"] = "水"
            task_data["fluid_properties"]["density"] = "998 kg/m³"
            task_data["fluid_properties"]["viscosity"] = "1.0e-3 Pa·s"

        # 7. 求解器
        if re.search(r'sIMPLE|SIMPLE', desc):
            task_data["solver_type"] = "SIMPLE"
        elif re.search(r'k.?epsilon|k-eps', desc, re.IGNORECASE):
            task_data["solver_type"] = "k-epsilon"
        elif re.search(r'k.?omega|k-omega', desc, re.IGNORECASE):
            task_data["solver_type"] = "k-omega SST"

        return task_data

    # ---- Notion 任务创建 ----

    def create_notion_task(self, task_data: dict, parent_page_id: str = None) -> str:
        """
        在 v1 Tasks DB 中创建任务页面。

        Args:
            task_data: parse_natural_language() 返回的结构化数据
            parent_page_id: 可选，默认写入 Linked Project

        Returns:
            创建成功的 page_id 字符串

        Raises:
            Exception: API 调用失败时抛出
        """
        # 构建页面标题
        geo = task_data.get("geometry_features", ["通用几何"])[0]
        title = f"[{task_data.get('priority','P1')}] {task_data.get('task_type','CFD仿真')} - {geo}"
        linked_project = task_data.get("linked_project") or parent_page_id or ""
        linked_phase = task_data.get("linked_phase", "")
        task_type_name = self._normalize_task_type(task_data.get("task_type"))
        priority_name = self._normalize_priority(task_data.get("priority"))
        executor_model = task_data.get("executor_model", "codex")
        fallback_model = task_data.get("fallback_model", "glm_51")
        last_run_summary = self._build_last_run_summary(task_data, linked_project, linked_phase)

        # 构建 properties
        properties = {
            "Task ID": {
                "title": [{"text": {"content": title}}]
            },
            "Linked Phase": {
                "rich_text": [{"text": {"content": linked_phase}}] if linked_phase else []
            },
            "Linked Project": {
                "rich_text": [{"text": {"content": linked_project}}] if linked_project else []
            },
            "Task Type": {
                "select": {"name": task_type_name}
            },
            "Priority": {
                "select": {"name": priority_name}
            },
            "Executor Model": {
                "rich_text": [{"text": {"content": executor_model}}]
            },
            "Fallback Model": {
                "rich_text": [{"text": {"content": fallback_model}}]
            },
            "Task Status": {
                "select": {"name": "待领取"}
            },
            "Git Branch": {
                "rich_text": []
            },
            "PR Link": {
                "url": None
            },
            "Artifact Link": {
                "url": None
            },
            "Failure Reason": {
                "rich_text": []
            },
            "Retry Count": {
                "number": 0
            },
            "Last Run Summary": self._build_rich_text(last_run_summary),
        }

        # 组装 payload
        payload = {
            "parent": {"database_id": TASKS_DB_ID},
            "properties": properties,
            "children": [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "任务概述"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "text": {"content": f"CFD 仿真任务 — 由 Well-Harness TaskWizard 自动生成 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                        }]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "text": {"content": f"执行模型: {executor_model} | 兜底模型: {fallback_model}"}
                        }]
                    }
                },
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"text": {"content": "几何特征"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"text": {"content": f"类型: {', '.join(task_data.get('geometry_features', []))}"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"text": {"content": "边界条件"}}]
                    }
                },
            ]
        }

        # 动态添加边界条件列表
        bc = task_data.get("boundary_conditions", {})
        for bc_name, bc_val in bc.items():
            payload["children"].append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"text": {"content": f"{bc_name}: {bc_val}"}}]
                }
            })

        # 收敛标准
        payload["children"].extend([
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"text": {"content": "求解设置"}}]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"text": {"content": f"收敛标准: {task_data.get('convergence_criteria', '10^-4')}"}}]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"text": {"content": f"求解器: {task_data.get('solver_type', '待指定')}"}}]
                }
            },
        ])

        # 流体物性
        fp = task_data.get("fluid_properties", {})
        if fp:
            payload["children"].append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"text": {"content": "流体物性"}}]
                }
            })
            for fp_name, fp_val in fp.items():
                payload["children"].append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"text": {"content": f"{fp_name}: {fp_val}"}}]
                    }
                })

        try:
            resp = requests.post(
                f"{NOTION_BASE_URL}/pages",
                headers=self.headers,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            page_id = data.get("id", "")
            logging.info(f"[TaskWizard] ✅ 任务页面创建成功: {page_id}")
            return page_id

        except requests.exceptions.HTTPError as err:
            logging.error(f"[TaskWizard] ❌ HTTP Error: {err}")
            logging.error(f"[TaskWizard] Response: {resp.text}")
            raise
        except Exception as err:
            logging.error(f"[TaskWizard] ❌ Error: {err}")
            raise

    def _build_acceptance_criteria(self, task_data: dict) -> str:
        """基于任务数据生成验收标准文本"""
        criteria = [
            f"1. {task_data.get('task_type')} 算例收敛",
            f"2. 残差达到 {task_data.get('convergence_criteria', '10^-4')} 以下",
            f"3. 几何特征: {', '.join(task_data.get('geometry_features', []))} 建模正确",
            f"4. 边界条件设置合理: {json.dumps(task_data.get('boundary_conditions', {}), ensure_ascii=False)}",
        ]
        if task_data.get("solver_type"):
            criteria.append(f"5. 求解器 {task_data['solver_type']} 设置正确")
        return "\n".join(criteria)

    # ---- G0 门校验 ----

    def validate_g0(self, page_id: str) -> dict:
        """
        对指定 Notion 页面执行 G0 门校验。

        检查项：
          1. Task ID 字段存在且非空
          2. Linked Project / Linked Phase 至少一个存在
          3. Task Type 字段存在且非空
          4. Priority 字段存在且非空
          5. Last Run Summary 存在且包含任务摘要

        Returns:
            evidence 字典，包含 pass/checks/result/message
        """
        evidence = {
            "gate": "G0",
            "gate_name": "任务门",
            "page_id": page_id,
            "timestamp": datetime.now().isoformat(),
            "checks": [],
            "result": "FAIL",
            "message": "",
        }

        check_items = [
            ("has_task_id", "Task ID存在"),
            ("has_linked_context", "Linked Project/Phase存在"),
            ("has_task_type", "Task Type存在"),
            ("has_priority", "Priority存在"),
            ("has_valid_geometry", "几何特征已提取"),
        ]

        try:
            # 获取页面属性
            resp = requests.get(
                f"{NOTION_BASE_URL}/pages/{page_id}",
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            page = resp.json()
            props = page.get("properties", {})

            # 检查各项
            for check_id, check_label in check_items:
                check_result = {"check": check_id, "pass": False, "detail": ""}

                if check_id == "has_task_id":
                    task_id_text = self._title_plain(props.get("Task ID", {})).strip()
                    check_result["pass"] = bool(task_id_text)
                    check_result["detail"] = "Task ID已填写" if task_id_text else "Task ID为空"

                elif check_id == "has_linked_context":
                    linked_project = self._rich_text_plain(props.get("Linked Project", {})).strip()
                    linked_phase = self._rich_text_plain(props.get("Linked Phase", {})).strip()
                    has_link = bool(linked_project or linked_phase)
                    check_result["pass"] = has_link
                    check_result["detail"] = "Linked Project/Phase已绑定" if has_link else "未绑定Linked Project/Phase"

                elif check_id == "has_task_type":
                    task_type = (props.get("Task Type", {}).get("select") or {}).get("name", "").strip()
                    check_result["pass"] = bool(task_type)
                    check_result["detail"] = "Task Type已填写" if task_type else "Task Type为空"

                elif check_id == "has_priority":
                    priority = (props.get("Priority", {}).get("select") or {}).get("name", "").strip()
                    check_result["pass"] = bool(priority)
                    check_result["detail"] = "Priority已填写" if priority else "Priority为空"

                elif check_id == "has_valid_geometry":
                    summary_text = self._rich_text_plain(props.get("Last Run Summary", {}))
                    spec_text = summary_text.strip()
                    has_geo = "几何" in spec_text or "几何特征" in spec_text
                    check_result["pass"] = has_geo
                    check_result["detail"] = "Last Run Summary包含几何摘要" if has_geo else "Last Run Summary缺少几何摘要"

                evidence["checks"].append(check_result)

            all_pass = all(c["pass"] for c in evidence["checks"])
            evidence["result"] = "PASS" if all_pass else "FAIL"
            evidence["message"] = "G0 任务门校验通过" if all_pass else f"G0 任务门校验未通过: {[c['detail'] for c in evidence['checks'] if not c['pass']]}"

            logging.info(f"[TaskWizard] G0 validate({page_id}): {evidence['result']}")

        except Exception as err:
            evidence["message"] = f"G0 校验异常: {err}"
            logging.error(f"[TaskWizard] G0 validation error: {err}")

        return evidence


# ============ CLI 入口 ============

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Well-Harness M1-3 TaskWizard")
    parser.add_argument("desc", nargs="?", help="CFD任务自然语言描述")
    parser.add_argument("--create", action="store_true", help="创建 Notion 任务")
    parser.add_argument("--validate", metavar="PAGE_ID", help="对指定 page_id 执行 G0 校验")
    parser.add_argument("--parent", default=None, help="父页面 ID")
    parser.add_argument("--output-json", action="store_true", help="JSON格式输出")

    args = parser.parse_args()

    wizard = TaskWizard()

    if args.validate:
        result = wizard.validate_g0(args.validate)
        if args.output_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n{'='*50}")
            print(f"G0 门校验结果: {result['result']}")
            print(f"消息: {result['message']}")
            print(f"检查项:")
            for c in result["checks"]:
                status = "✅" if c["pass"] else "❌"
                print(f"  {status} {c['check']}: {c['detail']}")

    elif args.desc:
        parsed = wizard.parse_natural_language(args.desc)
        print("\n解析结果:")
        print(json.dumps(parsed, ensure_ascii=False, indent=2))

        if args.create:
            print("\n正在创建 Notion 任务...")
            page_id = wizard.create_notion_task(parsed, parent_page_id=args.parent)
            print(f"✅ 任务已创建: {page_id}")
            print(f"🔗 https://notion.so/{page_id.replace('-', '')}")
    else:
        parser.print_help()
        print("\n示例:")
        print('  python3 task_wizard.py "稳态圆柱绕流仿真，入口速度5m/s，收敛标准10^-5" --create')
        print('  python3 task_wizard.py --validate 33ac6894-2bed-8125-97af-e9b90b245e58')
