#!/usr/bin/env python3
"""
Notion API 封装

简化与 Notion 的交互，提供任务和文档同步功能。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import requests


# 配置文件路径
CONFIG_PATH = Path.home() / ".claude" / "notion" / "config.json"


@dataclass
class NotionConfig:
    """Notion 配置"""
    integration_token: str
    tasks_db_id: str = ""
    design_db_id: str = ""
    dashboard_id: str = ""
    workspace_id: str = ""

    @classmethod
    def from_file(cls, path: Optional[Path] = None) -> "NotionConfig":
        """从配置文件加载"""
        path = path or CONFIG_PATH
        if not path.exists():
            # 尝试项目本地配置
            project_path = Path.cwd() / ".claude" / "notion" / "config.json"
            if project_path.exists():
                path = project_path
            else:
                raise FileNotFoundError(f"配置文件不存在: {path}")

        with open(path) as f:
            data = json.load(f)

        notion_config = data.get("notion", {})
        return cls(
            integration_token=notion_config.get("integration_token", ""),
            tasks_db_id=notion_config.get("tasks_db_id", ""),
            design_db_id=notion_config.get("design_db_id", ""),
            dashboard_id=notion_config.get("dashboard_id", ""),
            workspace_id=notion_config.get("workspace_id", ""),
        )


class NotionAPI:
    """Notion API 客户端"""

    BASE_URL = "https://api.notion.com/v1"

    def __init__(self, config: Optional[NotionConfig] = None):
        self.config = config or NotionConfig.from_file()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.config.integration_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送请求"""
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_database(self, database_id: str) -> Dict[str, Any]:
        """获取数据库信息"""
        return self._request("GET", f"/databases/{database_id}")

    def query_database(
        self,
        database_id: str,
        filter: Optional[Dict] = None,
        sort: Optional[List[Dict]] = None,
    ) -> List[Dict[str, Any]]:
        """查询数据库"""
        payload = {}
        if filter:
            payload["filter"] = filter
        if sort:
            payload["sorts"] = sort

        result = self._request("POST", f"/databases/{database_id}/query", json=payload)
        return result.get("results", [])

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """获取页面"""
        return self._request("GET", f"/pages/{page_id}")

    def create_page(
        self,
        database_id: str,
        title: str,
        properties: Dict[str, Any],
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建页面"""
        # 构建页面属性
        page_props = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }

        # 添加标题
        if database_id == self.config.tasks_db_id:
            page_props["properties"]["Name"] = {
                "title": [{"text": {"content": title}}]
            }
        elif database_id == self.config.design_db_id:
            page_props["properties"]["Name"] = {
                "title": [{"text": {"content": title}}]
            }

        result = self._request("POST", "/pages", json=page_props)

        # 添加内容
        if content:
            self.append_blocks(result["id"], self._create_content_blocks(content))

        return result

    def update_page(
        self,
        page_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """更新页面"""
        return self._request("PATCH", f"/pages/{page_id}", json={"properties": properties})

    def append_blocks(
        self,
        block_id: str,
        blocks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """追加内容块"""
        return self._request(
            "PATCH",
            f"/blocks/{block_id}/children",
            json={"children": blocks},
        )

    def _create_content_blocks(self, content: str) -> List[Dict[str, Any]]:
        """创建内容块"""
        blocks = []
        for line in content.split("\n"):
            if line.startswith("# "):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"text": {"content": line[2:]}}]}
                })
            elif line.startswith("## "):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"text": {"content": line[3:]}}]}
                })
            elif line.startswith("### "):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": [{"text": {"content": line[4:]}}]}
                })
            elif line.strip() == "":
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": []}
                })
            else:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": line}}]}
                })
        return blocks

    def search(self, query: str) -> List[Dict[str, Any]]:
        """搜索"""
        result = self._request("POST", "/search", json={"query": query})
        return result.get("results", [])


class TaskManager:
    """任务管理器 - 与 Notion Tasks 数据库交互"""

    def __init__(self, api: Optional[NotionAPI] = None):
        self.api = api or NotionAPI()

    def create_task(
        self,
        title: str,
        status: str = "Todo",
        priority: str = "Medium",
        tags: Optional[List[str]] = None,
        estimate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """创建任务"""
        if not self.api.config.tasks_db_id:
            raise ValueError("Tasks database ID not configured")

        properties = {
            "Status": {"select": {"name": status}},
            "Priority": {"select": {"name": priority}},
        }

        if tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in tags]
            }

        if estimate:
            properties["Estimate"] = {"number": estimate}

        return self.api.create_page(
            self.api.config.tasks_db_id,
            title,
            properties,
        )

    def update_task_status(self, task_id: str, status: str) -> Dict[str, Any]:
        """更新任务状态"""
        return self.api.update_page(
            task_id,
            {"Status": {"select": {"name": status}}},
        )

    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """获取指定状态的任务"""
        return self.api.query_database(
            self.api.config.tasks_db_id,
            filter={
                "property": "Status",
                "select": {"equals": status},
            },
        )


class DesignDocManager:
    """设计文档管理器 - 与 Notion Design Docs 数据库交互"""

    def __init__(self, api: Optional[NotionAPI] = None):
        self.api = api or NotionAPI()

    def create_design_doc(
        self,
        title: str,
        content: str,
        status: str = "Draft",
    ) -> Dict[str, Any]:
        """创建设计文档"""
        if not self.api.config.design_db_id:
            raise ValueError("Design database ID not configured")

        properties = {
            "Status": {"select": {"name": status}},
        }

        return self.api.create_page(
            self.api.config.design_db_id,
            title,
            properties,
            content,
        )

    def submit_for_review(self, doc_id: str) -> Dict[str, Any]:
        """提交审查"""
        return self.api.update_page(
            doc_id,
            {"Status": {"select": {"name": "Review"}}},
        )


# 导出
__all__ = [
    "NotionConfig",
    "NotionAPI",
    "TaskManager",
    "DesignDocManager",
]
