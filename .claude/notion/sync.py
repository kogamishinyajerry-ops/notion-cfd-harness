#!/usr/bin/env python3
"""
Notion 同步工具 - 适配现有 v1 数据库结构

支持与 v1-Tasks 和 v1-Reviews 数据库的双向同步。
"""

import argparse
import json
import os
import subprocess
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid

import requests


class NotionConfig:
    """Notion 配置"""

    def __init__(self, config_path: Optional[Path] = None):
        config_path = config_path or Path.cwd() / ".claude" / "notion" / "config.json"
        if not config_path.exists():
            config_path = Path.home() / ".claude" / "notion" / "config.json"

        with open(config_path) as f:
            data = json.load(f)

        self.notion = data.get("notion", {})
        self.field_mappings = data.get("field_mappings", {})
        self.sync_config = data.get("sync", {})
        self.critical_config = data.get("critical_intervention", {})

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

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
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

    def get_select_options(self, database_id: str, property_name: str) -> List[str]:
        """获取 select 或 status 属性的选项"""
        db_info = self._request("GET", f"/databases/{database_id}")
        prop = db_info.get("properties", {}).get(property_name, {})

        # Handle status type
        if prop.get("type") == "status":
            status_info = prop.get("status", {})
            return [opt.get("name", "") for opt in status_info.get("options", [])]

        # Handle select type
        select_info = prop.get("select", {})
        return [opt.get("name", "") for opt in select_info.get("options", [])]


class TaskSync:
    """任务同步器 - 适配 v1-Tasks 数据库"""

    def __init__(self, api: NotionAPI, config: NotionConfig):
        self.api = api
        self.config = config
        self.field_map = config.field_mappings.get("tasks", {})

    def create_task(
        self,
        task_id: str,
        task_type: str = "Implementation",
        priority: str = "Medium",
        linked_phase: str = "",
        linked_project: str = "",
    ) -> Dict:
        """创建任务"""
        # Task Name + Task Status (required field)
        # 使用属性名称而非 ID，更稳定可靠
        properties = {
            "Task Name": {"title": [{"text": {"content": task_id}}]},
            "Task Status": {"status": {"name": "Queued"}},
        }

        if linked_phase:
            properties["Linked Phase"] = {
                "relation": [{"id": linked_phase}] if linked_phase else []
            }

        if linked_project:
            properties["Linked Project"] = {
                "relation": [{"id": linked_project}] if linked_project else []
            }

        return self.api.create_page(self.config.tasks_db_id, properties)

    def update_task_status(self, page_id: str, status: str) -> Dict:
        """更新任务状态

        注意: status 类型使用 "status" 键而非 "select" 键
        """
        return self.api.update_page(
            page_id,
            {"Task Status": {"status": {"name": status}}},
        )

    def update_task_branch(self, page_id: str, branch: str) -> Dict:
        """更新 Git 分支"""
        return self.api.update_page(
            page_id,
            {
                "Git Branch": {
                    "rich_text": [{"text": {"content": branch}}]
                }
            },
        )

    def update_task_pr(self, page_id: str, pr_url: str) -> Dict:
        """更新 PR 链接"""
        return self.api.update_page(
            page_id,
            {"PR Link": {"url": pr_url}},
        )

    def find_task_by_id(self, task_id: str) -> Optional[Dict]:
        """根据 Task ID 查找任务

        使用 Task Name (title) 字段搜索，因为 Task ID 是 unique_id 类型
        不支持字符串过滤。
        """
        results = self.api.query_database(
            self.config.tasks_db_id,
            filter={
                "property": "Task Name",
                "title": {"equals": task_id},
            },
        )
        return results[0] if results else None

    def get_available_statuses(self) -> List[str]:
        """获取可用的任务状态"""
        return self.api.get_select_options(
            self.config.tasks_db_id, "Task Status"
        )


class ReviewSync:
    """审查同步器 - 适配 v1-Reviews 数据库"""

    def __init__(self, api: NotionAPI, config: NotionConfig):
        self.api = api
        self.config = config
        self.field_map = config.field_mappings.get("reviews", {})

    def create_review(
        self,
        review_type: str,
        artifact_link: str = "",
        blocking_issues: str = "",
        reviewer: str = "Opus 4.6",
    ) -> Dict:
        """创建审查请求"""
        review_id = f"REVIEW-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"

        properties = {
            self.field_map.get("id", "Review ID"): {
                "title": [{"text": {"content": review_id}}]
            },
            self.field_map.get("status", "Review Status"): {
                "select": {"name": "Pending"}
            },
            self.field_map.get("type", "Review Type"): {
                "select": {"name": review_type}
            },
            self.field_map.get("decision", "Decision"): {
                "select": {"name": "Pending"}
            },
        }

        if artifact_link:
            properties[self.field_map.get("artifact_link", "Review Artifact Link")] = {
                "url": artifact_link
            }

        if blocking_issues:
            properties[self.field_map.get("blocking_issues", "Blocking Issues")] = {
                "rich_text": [{"text": {"content": blocking_issues}}]
            }

        if reviewer:
            properties[self.field_map.get("reviewer", "Reviewer Model")] = {
                "rich_text": [{"text": {"content": reviewer}}]
            }

        page = self.api.create_page(self.config.reviews_db_id, properties)

        # 添加审查说明
        self.api.append_text(
            page["id"],
            f"\n🛑 GSD Critical Review\n请 @Opus 4.6 进行审查。\n创建时间: {datetime.now().isoformat()}",
        )

        return page

    def update_review_decision(self, page_id: str, decision: str) -> Dict:
        """更新审查决定"""
        return self.api.update_page(
            page_id,
            {
                self.field_map.get("decision", "Decision"): {"select": {"name": decision}},
                self.field_map.get("status", "Review Status"): {
                    "select": {"name": "Completed" if decision == "Approved" else "Changes Required"}
                },
            },
        )


def get_current_branch() -> str:
    """获取当前 Git 分支"""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def get_current_commit() -> str:
    """获取当前 commit SHA"""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def get_commit_message() -> str:
    """获取最后一条 commit 消息"""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def parse_task_from_commit(msg: str) -> Optional[str]:
    """从 commit 消息解析任务 ID"""
    # 支持 #P2-79, #TASK-123, TASK-123: 或 [TASK-123] 格式
    match = re.search(r"#?([A-Z0-9]+-\d+)", msg)
    return match.group(1) if match else None


def get_pr_info(pr_number: int) -> Optional[Dict]:
    """获取 PR 信息"""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "title,body,url,state,headRefName"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def trigger_codex_review(pr_number: int, scope: str = "") -> Dict:
    """触发 Codex Review"""
    import os

    pr_info = get_pr_info(pr_number)
    if not pr_info:
        print(f"错误: 无法获取 PR #{pr_number} 信息")
        sys.exit(1)

    print(f"🤖 触发 Codex Review for PR #{pr_number}: {pr_info.get('title')}")

    # 构建审查命令
    cmd = [
        "node",
        os.path.expanduser("~/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs"),
        "task",
        "--model", "gpt-5.3-codex",
        "--effort", "high",
    ]

    if scope:
        cmd.extend(["--", f"Review PR #{pr_number}: {pr_info.get('title')}. Focus on: {scope}"])
    else:
        cmd.extend(["--", f"Review PR #{pr_number}: {pr_info.get('title')}"])

    print(f"命令: {' '.join(cmd)}")

    # 返回命令信息，由用户手动执行或通过其他方式触发
    return {
        "pr_number": pr_number,
        "pr_url": pr_info.get("url"),
        "pr_title": pr_info.get("title"),
        "review_command": " ".join(cmd),
    }


def check_review_status(pr_number: int) -> str:
    """检查 Review 状态"""
    pr_info = get_pr_info(pr_number)
    if not pr_info:
        return "Unknown"

    state = pr_info.get("state", "open")
    if state == "closed":
        # 检查是否合并
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "merged", "-q", ".merged"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip() == "true":
            return "Merged"
        return "Closed"

    # 检查是否有审查评论
    result = subprocess.run(
        ["gh", "pr", "checks", str(pr_number), "--json", "name,conclusion", "-q", "."],
        capture_output=True,
        text=True,
    )

    # 简化：如果 PR 开放，返回 "Pending"
    return "Pending"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Notion 同步工具")
    parser.add_argument("command", choices=[
        "status",
        "create-task",
        "update-status",
        "create-review",
        "sync-commit",
        "sync-branch",
        # GitHub 集成命令
        "trigger-codex-review",
        "check-review",
        "sync-pr",
        "check-task",
    ], help="命令")
    parser.add_argument("--task-id", help="任务 ID (如 P2-P1)")
    parser.add_argument("--task-type", help="任务类型", default="Implementation")
    parser.add_argument("--priority", help="优先级", default="Medium")
    parser.add_argument("--status", help="状态")
    parser.add_argument("--review-type", help="审查类型")
    parser.add_argument("--reason", help="审查原因")
    parser.add_argument("--phase", help="关联阶段")
    parser.add_argument("--project", help="关联项目")
    # GitHub 集成参数
    parser.add_argument("--pr-number", type=int, help="PR 号码")
    parser.add_argument("--scope", help="Codex Review 范围")

    args = parser.parse_args()

    try:
        config = NotionConfig()
        api = NotionAPI(config)
        task_sync = TaskSync(api, config)
        review_sync = ReviewSync(api, config)

        if args.command == "status":
            print("Notion 配置状态:")
            print(f"  Tasks DB: {config.tasks_db_id}")
            print(f"  Reviews DB: {config.reviews_db_id}")
            print(f"  Projects DB: {config.projects_db_id}")
            print(f"\n可用任务状态: {task_sync.get_available_statuses()}")

        elif args.command == "create-task":
            if not args.task_id:
                # 从分支名生成任务 ID
                branch = get_current_branch()
                if branch:
                    args.task_id = f"TASK-{branch.replace('/', '-').upper()}"
                else:
                    args.task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"

            task = task_sync.create_task(
                task_id=args.task_id,
                task_type=args.task_type,
                priority=args.priority,
                linked_phase=args.phase or "",
                linked_project=args.project or "",
            )
            print(f"✓ 已创建任务: {task['id']}")
            print(f"  Task ID: {args.task_id}")

            # 更新分支
            branch = get_current_branch()
            if branch:
                task_sync.update_task_branch(task["id"], branch)
                print(f"  分支: {branch}")

        elif args.command == "update-status":
            if not args.task_id:
                # 从 commit 消息解析
                msg = get_commit_message()
                args.task_id = parse_task_from_commit(msg)

            if not args.task_id:
                print("错误: 无法确定任务 ID，请使用 --task-id 指定")
                sys.exit(1)

            if not args.status:
                print("错误: 请使用 --status 指定状态")
                sys.exit(1)

            task = task_sync.find_task_by_id(args.task_id)
            if not task:
                print(f"错误: 未找到任务 {args.task_id}")
                sys.exit(1)

            task_sync.update_task_status(task["id"], args.status)
            print(f"✓ 已更新任务 {args.task_id} 状态为 {args.status}")

        elif args.command == "create-review":
            if not args.review_type:
                args.review_type = "GSD Critical Review"

            blocking_issues = args.reason or "需要 Opus 4.6 审查"

            review = review_sync.create_review(
                review_type=args.review_type,
                blocking_issues=blocking_issues,
            )
            print(f"✓ 已创建审查请求: {review['id']}")
            print(f"  审查类型: {args.review_type}")
            print(f"  原因: {blocking_issues}")
            print(f"\n请在 Notion 中 @Opus 4.6 进行审查")

        elif args.command == "sync-commit":
            msg = get_commit_message()
            task_id = parse_task_from_commit(msg)

            if task_id:
                task = task_sync.find_task_by_id(task_id)
                if task:
                    # 推断状态 (映射到有效的 Task Status 选项)
                    if any(w in msg.lower() for w in ["complete", "finish", "done", "fix", "success"]):
                        status = "Succeeded"
                    elif any(w in msg.lower() for w in ["start", "begin", "wip", "progress"]):
                        status = "Running"
                    elif any(w in msg.lower() for w in ["fail", "error", "bug"]):
                        status = "Failed"
                    else:
                        status = "Queued"

                    task_sync.update_task_status(task["id"], status)
                    print(f"✓ 已同步任务 {task_id} 状态为 {status}")
                else:
                    print(f"⚠️  未找到任务 {task_id}")
            else:
                print("ℹ️  Commit 消息中没有任务 ID")

        elif args.command == "sync-branch":
            branch = get_current_branch()
            task_id = parse_task_from_commit(branch)

            if task_id:
                task = task_sync.find_task_by_id(task_id)
                if task:
                    task_sync.update_task_branch(task["id"], branch)
                    print(f"✓ 已更新任务 {task_id} 分支为 {branch}")
                else:
                    print(f"⚠️  未找到任务 {task_id}")

        # ========== GitHub 集成命令 ==========

        elif args.command == "trigger-codex-review":
            # 触发 Codex Review
            pr_number = getattr(args, "pr_number", None)
            if not pr_number:
                # 尝试从当前分支获取 PR
                branch = get_current_branch()
                result = subprocess.run(
                    ["gh", "pr", "list", "--head", branch, "--json", "number", "-q", ".number"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    pr_number = int(result.stdout.strip())
                else:
                    print("错误: 无法确定 PR 号码，请使用 --pr-number 指定")
                    sys.exit(1)

            scope = getattr(args, "scope", "")
            review_info = trigger_codex_review(pr_number, scope)

            print(f"✓ Codex Review 已准备")
            print(f"  PR: {review_info['pr_url']}")
            print(f"\n执行以下命令开始审查:")
            print(f"  {review_info['review_command']}")

        elif args.command == "check-review":
            # 检查 Review 状态
            pr_number = getattr(args, "pr_number", None)
            if not pr_number:
                print("错误: 请使用 --pr-number 指定 PR 号码")
                sys.exit(1)

            status = check_review_status(pr_number)
            print(f"PR #{pr_number} 状态: {status}")

        elif args.command == "sync-pr":
            # 同步 PR 到 Notion
            pr_number = getattr(args, "pr_number", None)
            if not pr_number:
                print("错误: 请使用 --pr-number 指定 PR 号码")
                sys.exit(1)

            pr_info = get_pr_info(pr_number)
            if not pr_info:
                print(f"错误: 无法获取 PR #{pr_number} 信息")
                sys.exit(1)

            # 从 PR 标题解析任务 ID
            pr_title = pr_info.get("title", "")
            task_id = parse_task_from_commit(pr_title)

            if task_id:
                task = task_sync.find_task_by_id(task_id)
                if task:
                    # 更新 PR 链接
                    task_sync.update_task_pr(task["id"], pr_info["url"])
                    # 更新状态为 Running (因为 PR 已创建表示任务正在执行)
                    task_sync.update_task_status(task["id"], "Running")
                    print(f"✓ 已同步 PR #{pr_number} 到任务 {task_id}")
                    print(f"  PR URL: {pr_info['url']}")
                else:
                    print(f"⚠️  未找到任务 {task_id}")
            else:
                print(f"ℹ️  无法从 PR 标题解析任务 ID: {pr_title}")

        elif args.command == "check-task":
            # 检查任务是否存在
            task_id = getattr(args, "task_id", None)
            if not task_id:
                print("错误: 请使用 --task-id 指定任务 ID")
                sys.exit(1)

            task = task_sync.find_task_by_id(task_id)
            if task:
                print("true")
            else:
                print("false")

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
