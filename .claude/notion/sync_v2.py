#!/usr/bin/env python3
"""
Notion 同步工具 - 适配 AI-Harness 控制塔 v1 数据库结构
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
import uuid

import requests


class NotionConfig:
    """Notion 配置"""

    def __init__(self, config_path: Optional[Path] = None):
        config_path = config_path or Path.cwd() / ".claude" / "notion" / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path) as f:
            data = json.load(f)

        self.notion = data.get("notion", {})
        self.field_mappings = data.get("field_mappings", {})

    @property
    def token(self) -> str:
        return self.notion.get("integration_token", "")

    @property
    def tasks_db_id(self) -> str:
        return self.notion.get("tasks_db_id", "")

    @property
    def reviews_db_id(self) -> str:
        return self.notion.get("reviews_db_id", "")

    @property
    def project_id(self) -> str:
        return self.notion.get("project_id", "")

    @property
    def phases_db_id(self) -> str:
        return self.notion.get("phases_db_id", "")

    @property
    def projects_db_id(self) -> str:
        return self.notion.get("projects_db_id", "")


class NotionAPI:
    """Notion API 客户端"""

    BASE_URL = "https://api.notion.com/v1"

    def __init__(self, config: NotionConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.config.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """发送请求"""
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        if response.status_code >= 400:
            print(f"API Error: {response.status_code} - {response.text}", file=sys.stderr)
        response.raise_for_status()
        return response.json()

    def query_database(self, database_id: str, filter: Optional[Dict] = None) -> List[Dict]:
        """查询数据库"""
        payload = {}
        if filter:
            payload["filter"] = filter
        result = self._request("POST", f"/databases/{database_id}/query", json=payload)
        return result.get("results", [])

    def create_page(self, database_id: str, properties: Dict) -> Dict:
        """创建页面"""
        payload = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        return self._request("POST", "/pages", json=payload)

    def update_page(self, page_id: str, properties: Dict) -> Dict:
        """更新页面"""
        return self._request("PATCH", f"/pages/{page_id}", json={"properties": properties})

    def append_text(self, block_id: str, text: str) -> Dict:
        """追加文本内容"""
        return self._request(
            "PATCH",
            f"/blocks/{block_id}/children",
            json={
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": text}}]
                        },
                    }
                ]
            },
        )


class TaskSync:
    """任务同步器 - 适配控制塔 Tasks 数据库"""

    # 控制塔 Tasks 数据库的状态选项
    STATUS_MAP = {
        "pending": "Queued",
        "in_progress": "Running",
        "completed": "Succeeded",
        "failed": "Failed",
    }

    def __init__(self, api: NotionAPI, config: NotionConfig):
        self.api = api
        self.config = config

    def create_task(
        self,
        task_name: str,
        task_type: str = "Implementation",
        priority: str = "Medium",
        linked_phase: str = "",
        linked_project: str = "",
    ) -> Dict:
        """创建任务"""
        properties = {
            "Task Name": {
                "title": [{"text": {"content": task_name}}]
            },
            "Task Type": {"select": {"name": task_type}},
            "Priority": {"select": {"name": priority}},
            "Task Status": {"status": {"name": "Queued"}},
        }

        if linked_phase:
            properties["Linked Phase"] = {
                "relation": [{"database": self.config.phases_db_id}]
            }

        if linked_project:
            properties["Linked Project"] = {
                "relation": [{"database": self.config.projects_db_id}]
            }

        return self.api.create_page(self.config.tasks_db_id, properties)

    def update_task_status(self, page_id: str, status: str) -> Dict:
        """更新任务状态"""
        notion_status = self.STATUS_MAP.get(status.lower(), status)
        return self.api.update_page(
            page_id,
            {"Task Status": {"status": {"name": notion_status}}},
        )

    def find_task_by_name(self, task_name: str) -> Optional[Dict]:
        """根据任务名称查找任务"""
        results = self.api.query_database(
            self.config.tasks_db_id,
            filter={
                "property": "Task Name",
                "title": {"equals": task_name},
            },
        )
        return results[0] if results else None


class ReviewSync:
    """审查同步器 - 适配控制塔 Reviews 数据库"""

    def __init__(self, api: NotionAPI, config: NotionConfig):
        self.api = api
        self.config = config

    def create_review(
        self,
        review_type: str,
        artifact_link: str = "",
        blocking_issues: str = "",
        reviewer: str = "Opus 4.6",
        linked_phase: str = "",
    ) -> Dict:
        """创建审查请求"""
        review_id = f"REV-{uuid.uuid4().hex[:6].upper()}"

        properties = {
            "Review Title": {"title": [{"text": {"content": f"{review_type} - {review_id}"}}]},
            "Review Type": {"select": {"name": review_type}},
            "Reviewer Model": {"select": {"name": reviewer}},
            "Review Status": {"status": {"name": "Requested"}},
        }

        if artifact_link:
            properties["Review Artifact Link"] = {"url": artifact_link}

        if blocking_issues:
            properties["Blocking Issues"] = {
                "rich_text": [{"text": {"content": blocking_issues}}]
            }

        if linked_phase:
            properties["Linked Phase"] = {
                "relation": [{"id": linked_phase}]
            }

        page = self.api.create_page(self.config.reviews_db_id, properties)

        # 添加审查说明
        self.api.append_text(
            page["id"],
            f"\n@{reviewer} 请审查。\n创建时间: {subprocess.run(['date', '-Iminutes'], capture_output=True, text=True).stdout.strip()}"
        )

        return page


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Notion 同步工具 - 控制塔版")
    parser.add_argument("command", choices=[
        "status",
        "create-task",
        "update-status",
        "create-review",
        "find-task",
    ], help="命令")
    parser.add_argument("--task-name", help="任务名称")
    parser.add_argument("--task-type", help="任务类型", default="Implementation")
    parser.add_argument("--priority", help="优先级", default="Medium")
    parser.add_argument("--status", help="状态 (pending/in_progress/completed/failed)")
    parser.add_argument("--review-type", help="审查类型")
    parser.add_argument("--reason", help="审查原因")
    parser.add_argument("--phase", help="关联阶段")
    parser.add_argument("--project", help="关联项目")

    args = parser.parse_args()

    try:
        config = NotionConfig()
        api = NotionAPI(config)
        task_sync = TaskSync(api, config)
        review_sync = ReviewSync(api, config)

        if args.command == "status":
            print("Notion 配置状态:")
            print(f"  工作区: AI-Harness 控制塔 v1")
            print(f"  项目 ID: {config.project_id}")
            print(f"  Tasks DB: {config.tasks_db_id}")
            print(f"  Reviews DB: {config.reviews_db_id}")
            print(f"  项目链接: https://notion.so/{config.project_id.replace('-', '')}")

        elif args.command == "create-task":
            task_name = args.task_name or f"Task-{uuid.uuid4().hex[:8]}"
            task = task_sync.create_task(
                task_name=task_name,
                task_type=args.task_type,
                priority=args.priority,
                linked_phase=args.phase or "",
                linked_project=args.project or "",
            )
            print(f"  Task Name: {task_name}")
            print(f"✓ 已创建任务: {task['id']}")
            print(f"  链接: https://notion.so/{task['id'].replace('-', '')}")

        elif args.command == "update-status":
            if not args.task_name:
                print("错误: 请使用 --task-name 指定任务名称")
                sys.exit(1)

            task = task_sync.find_task_by_name(args.task_name)
            if not task:
                print(f"错误: 未找到任务 {args.task_name}")
                sys.exit(1)

            task_sync.update_task_status(task["id"], args.status)
            notion_status = TaskSync.STATUS_MAP.get(args.status.lower(), args.status)
            print(f"✓ 已更新任务 {args.task_name} 状态为 {notion_status}")

        elif args.command == "create-review":
            if not args.review_type:
                args.review_type = "Architecture Review"

            blocking_issues = args.reason or "需要审查"
            linked_phase = args.phase or ""

            review = review_sync.create_review(
                review_type=args.review_type,
                artifact_link="",
                blocking_issues=blocking_issues,
                linked_phase=linked_phase,
            )
            print(f"✓ 已创建审查请求: {review['id']}")
            print(f"  链接: https://notion.so/{review['id'].replace('-', '')}")

        elif args.command == "find-task":
            if not args.task_name:
                print("错误: 请使用 --task-name 指定任务名称")
                sys.exit(1)

            task = task_sync.find_task_by_name(args.task_name)
            if task:
                print(f"✓ 找到任务: {args.task_name}")
                print(f"  ID: {task['id']}")
                print(f"  链接: https://notion.so/{task['id'].replace('-', '')}")
            else:
                print(f"✗ 未找到任务: {args.task_name}")

    except FileNotFoundError:
        print("错误: 配置文件不存在，请先运行 .claude/setup-gsd.sh")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"错误: Notion API 请求失败 - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
