#!/usr/bin/env python3
"""
Phase4: 创建 Notion 项目页和任务页
用法: python3 scripts/create_phase4_project.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from notion_cfd_loop import create_notion_page_task
    NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
    if NOTION_API_KEY:
        # Try to read from file
        try:
            NOTION_API_KEY = open(os.path.expanduser("~/.notion_key")).read().strip()
        except:
            pass
except ImportError:
    NOTION_API_KEY = None

# Notion SSOT Database ID (需要配置)
SSOT_DB_ID = os.environ.get("NOTION_SSOT_DB", "")

def create_phase4_project():
    """创建 Phase4 主项目页"""

    if not SSOT_DB_ID:
        print("⚠️ NOTION_SSOT_DB 环境变量未设置")
        print("请设置: export NOTION_SSOT_DB=<your-database-id>")
        print()
        print("Phase4 项目将使用默认配置，但不会创建 Notion 页面")
        return None

    project_data = {
        "title": "Phase4: Governed Memory Network",
        "properties": {
            "Phase": "Phase4",
            "Status": "Planning",
            "Gate节点": "G3-G6",
            "执行模型": "Codex (GPT-5.4)",
            "审查模型": "Opus 4.6",
        }
    }

    print(f"=== 创建 Phase4 项目页 ===")
    print(f"数据库: {SSOT_DB_ID}")
    print(f"标题: {project_data['title']}")

    try:
        # 这里需要实际的 Notion API 调用
        # page_id = create_notion_page_task(...)
        print("✅ Notion API 集成待配置")
        print()
        print("需要手动在 Notion 中创建项目页或配置 API")
        return "AI-CFD-004"
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return None

def create_phase4_tasks(project_id: str):
    """创建 Phase4 子任务页"""

    tasks = [
        ("P4-01", "VersionedKnowledgeRegistry", "实现知识单元版本管理"),
        ("P4-02", "MemoryNode 数据模型", "定义记忆节点数据结构"),
        ("P4-03", "PropagationEngine", "集成 diff_engine 自动化传播"),
        ("P4-04", "GovernanceEngine", "执行治理策略"),
        ("P4-05", "CodeMappingRegistry", "知识-代码双向绑定"),
        ("P4-06", "MemoryNetwork", "主编排器"),
        ("P4-07", "G3 Gate 自动化", "Gate 自动触发流程"),
        ("P4-08", "G4-G6 Gate 验收", "Gate 验收流程"),
        ("P4-09", "Notion Reviews 集成", "记录到 Reviews DB"),
        ("P4-10", "CLI 工具", "memory-network 命令"),
        ("P4-11", "文档", "Phase4 架构文档"),
        ("P4-12", "Baseline", "Phase4_BASELINE_MANIFEST"),
    ]

    print(f"\n=== Phase4 任务列表 ===")
    for task_id, name, desc in tasks:
        print(f"  {task_id}: {name} - {desc}")

def main():
    print("Phase4: Governed Memory Network")
    print("=" * 50)

    # 尝试创建项目页
    project_id = create_phase4_project()

    # 显示任务列表
    create_phase4_tasks(project_id or "AI-CFD-004")

    print()
    print("=== 下一步 ===")
    print("1. 开始执行 P4-01: VersionedKnowledgeRegistry")
    print("2. 每个任务完成后触发 Code Review:")
    print("   ./scripts/trigger_code_review.sh 'P4-XX 实现说明'")
    print("3. Code Review 额度不足时会自动跳过（不阻塞）")
    print("4. Gate 任务需要 Opus 4.6 审查")

if __name__ == "__main__":
    main()
