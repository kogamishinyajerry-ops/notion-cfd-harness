#!/usr/bin/env python3
"""
全链路同步：Local ←→ Notion

定期执行此脚本以确保本地任务状态与 Notion 同步。
"""

import subprocess
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from knowledge_compiler.phase3.schema import SolverJob, JobPriority
    from knowledge_compiler.phase2.execution_layer.schema import PhysicsPlan
    # 尝试导入任务系统
    TASKS_AVAILABLE = True
except ImportError:
    TASKS_AVAILABLE = False


def sync_tasks_to_notion():
    """同步本地任务到 Notion"""
    print("📤 同步本地任务 → Notion...")

    # 获取当前任务列表
    result = subprocess.run(
        ["claude", "tasks"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        # 解析任务列表
        lines = result.stdout.split("\n")
        for line in lines:
            if line.strip() and "[" in line:
                # 提取任务信息
                parts = line.split("]")
                if len(parts) >= 2:
                    status_part = parts[0].strip("[]")
                    rest = parts[1].strip()

                    # 推断 Notion 状态
                    if "pending" in status_part.lower():
                        notion_status = "待领取" if "待领取" in get_available_statuses() else "Todo"
                    elif "in_progress" in status_part.lower():
                        notion_status = "执行中" if "执行中" in get_available_statuses() else "In Progress"
                    elif "completed" in status_part.lower():
                        notion_status = "已完成" if "已完成" in get_available_statuses() else "Completed"
                    else:
                        notion_status = "Todo"

                    print(f"  - {rest[:50]}... → {notion_status}")

        print("✓ 本地任务列表已显示")
        print("⚠️  注意: 自动同步需要 Notion 数据库授权")
    else:
        print(f"⚠️  无法获取任务列表: {result.stderr}")


def get_available_statuses() -> list:
    """获取 Notion 可用状态"""
    result = subprocess.run(
        ["python3", ".claude/notion/sync.py", "status"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )

    if result.returncode == 0:
        # 解析可用状态
        for line in result.stdout.split("\n"):
            if "可用任务状态:" in line:
                statuses = line.split("可用任务状态:")[1].strip("[]").split(", ")
                return [s.strip().strip("'\"") for s in statuses]
    return []


def sync_notion_to_local():
    """从 Notion 拉取最新状态"""
    print("📥 同步 Notion → 本地...")
    print("⚠️  此功能需要 Notion API 完整授权，目前暂未实现")


def check_sync_status():
    """检查同步状态"""
    import os

    print("\n🔍 同步状态检查:")
    print("=" * 50)

    # 检查 Notion 配置（使用当前工作目录）
    config_path = Path.cwd() / ".claude" / "notion" / "config.json"
    if config_path.exists():
        print("✓ Notion 配置文件存在")
    else:
        print("✗ Notion 配置文件不存在")

    # 检查 post-commit hook
    hook_path = Path.cwd() / ".git" / "hooks" / "post-commit"
    if hook_path.exists():
        print("✓ post-commit hook 已安装")
    else:
        print("✗ post-commit hook 未安装")

    # 测试 Notion 连接
    result = subprocess.run(
        ["python3", ".claude/notion/sync.py", "status"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )

    if "Tasks DB:" in result.stdout:
        print("✓ Notion API 连接正常")
    else:
        print("✗ Notion API 连接失败")
        if "404" in result.stderr or "object_not_found" in result.stderr:
            print("  → 数据库未与集成共享，请在 Notion 中:")
            print("    1. 打开数据库设置")
            print("    2. 点击 'Add connections'")
            print("    3. 选择 'Claude Dev Workflow' 集成")

    print("=" * 50)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="全链路同步工具")
    parser.add_argument("--check", "-c", action="store_true", help="检查同步状态")
    parser.add_argument("--push", "-p", action="store_true", help="推送本地状态到 Notion")
    parser.add_argument("--pull", action="store_true", help="从 Notion 拉取状态")
    parser.add_argument("--full", "-f", action="store_true", help="完整同步（双向）")

    args = parser.parse_args()

    if args.check or not any([args.push, args.pull, args.full]):
        check_sync_status()

    if args.push or args.full:
        sync_tasks_to_notion()

    if args.pull or args.full:
        sync_notion_to_local()


if __name__ == "__main__":
    main()
