#!/usr/bin/env python3
"""里程碑查询与同步 - GSD Phase 管理"""

import argparse
import json
import sys
from pathlib import Path
import requests


class MilestoneTracker:
    """里程碑跟踪器"""

    BASE_URL = "https://api.notion.com/v1"

    def __init__(self):
        self.config = self._load_config()
        self.headers = {
            "Authorization": f"Bearer {self.config['token']}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

    def _load_config(self):
        config_path = Path.cwd() / ".claude" / "notion" / "config.json"
        with open(config_path) as f:
            data = json.load(f)
        return {
            "token": data["notion"]["integration_token"],
            "phases_db_id": data["notion"]["phases_db_id"],
            "tasks_db_id": data["notion"]["tasks_db_id"],
        }

    def get_phases(self):
        """获取所有阶段"""
        response = requests.post(
            f"{self.BASE_URL}/databases/{self.config['phases_db_id']}/query",
            headers=self.headers,
            json={},
        )
        response.raise_for_status()
        return response.json().get("results", [])

    def get_current_phase(self):
        """获取当前执行中的阶段"""
        phases = self.get_phases()
        for phase in phases:
            status = phase.get("properties", {}).get("Status", {})
            if status.get("status", {}).get("name") == "Executing":
                return phase
        return None

    def get_phase_tasks(self, phase_id):
        """获取阶段关联的任务"""
        response = requests.post(
            f"{self.BASE_URL}/databases/{self.config['tasks_db_id']}/query",
            headers=self.headers,
            json={
                "filter": {
                    "property": "Linked Phase",
                    "relation": {"contains": phase_id}
                }
            }
        )
        response.raise_for_status()
        return response.json().get("results", [])

    def print_phase_status(self):
        """打印阶段状态"""
        phases = self.get_phases()
        phases.sort(key=lambda p: p.get("properties", {}).get("Sequence", {}).get("number", 999))

        print("\n🎯 GSD 里程碑状态")
        print("=" * 60)

        for phase in phases:
            props = phase.get("properties", {})
            name = ""
            if "Phase Name" in props:
                titles = props["Phase Name"].get("title", [])
                if titles:
                    name = titles[0].get("text", {}).get("content", "")

            sequence = props.get("Sequence", {}).get("number", "?")

            status = ""
            if "Status" in props:
                status = props["Status"].get("status", {}).get("name", "Unknown")

            status_icon = {
                "Draft": "📋",
                "Ready for Execution": "🔵",
                "Executing": "🔄",
                "Ready for Review": "🟡",
                "Under Review": "🟣",
                "Pass": "✅",
                "Conditional Pass": "⚠️",
                "Blocked": "🔴",
            }.get(status, "❓")

            print(f"{status_icon} Phase {sequence}: {name}")
            print(f"   状态: {status}")

            if status == "Executing":
                print(f"   >>> 当前执行中 <<<")

        print("=" * 60)

    def print_current_phase_detail(self):
        """打印当前阶段详情"""
        phase = self.get_current_phase()
        if not phase:
            print("⚠️  没有执行中的阶段")
            return

        props = phase.get("properties", {})
        name = ""
        if "Phase Name" in props:
            titles = props["Phase Name"].get("title", [])
            if titles:
                name = titles[0].get("text", {}).get("content", "")

        print(f"\n🔄 当前执行: {name}")
        print("=" * 60)

        # 获取阶段关联的任务
        tasks = self.get_phase_tasks(phase["id"])

        if not tasks:
            print("   (暂无关联任务)")
        else:
            print(f"\n📋 关联任务 ({len(tasks)}):")
            for task in tasks:
                t_props = task.get("properties", {})
                t_name = ""
                if "Task Name" in t_props:
                    titles = t_props["Task Name"].get("title", [])
                    if titles:
                        t_name = titles[0].get("text", {}).get("content", "")

                t_status = ""
                if "Task Status" in t_props:
                    t_status = t_props["Task Status"].get("status", {}).get("name", "Unknown")

                status_icon = {
                    "Queued": "⏳",
                    "Running": "🔄",
                    "Succeeded": "✅",
                    "Failed": "❌",
                }.get(t_status, "❓")

                print(f"  {status_icon} {t_name}: {t_status}")

        print("=" * 60)


def main():
    tracker = MilestoneTracker()

    parser = argparse.ArgumentParser(description="里程碑查询")
    parser.add_argument("--current", "-c", action="store_true", help="显示当前阶段详情")
    parser.add_argument("--status", "-s", action="store_true", help="显示所有阶段状态")

    args = parser.parse_args()

    if args.status or not any([args.current]):
        tracker.print_phase_status()

    if args.current:
        tracker.print_current_phase_detail()


if __name__ == "__main__":
    main()
