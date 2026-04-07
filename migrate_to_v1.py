#!/usr/bin/env python3
"""
Well-Harness v1 架构迁移脚本
将现有单一SSOT拆分为7个专业数据库

现有DB → 新DB映射:
- SSOT → Projects (项目主记录)
- M1-1~M1-6子页面 → Tasks
- M1-1~M1-6执行记录 → Reviews
- Component Library → Artifacts (构件库)
- Case Library → Artifacts (案例库)
- Baseline Library → Artifacts (基线库)
- Rule Database → Constraints
- Evidence Library → 保持(Evidence格式不变)
"""

import os
import json
import requests
from datetime import datetime

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json"
}

# 现有DB IDs
SSOT_DB_ID = "33ac6894-2bed-8125-97af-e9b90b245e58"
# 项目根页面ID (用于创建子数据库)
PROJECT_PAGE_ID = "33ac6894-2bed-817a-b755-e574f2a79c77"  # AI-CFD-001

def notion_post(endpoint: str, data: dict) -> dict:
    resp = requests.post(f"{NOTION_BASE_URL}/{endpoint}", headers=HEADERS, json=data, timeout=120)
    resp.raise_for_status()
    return resp.json()

def notion_get(endpoint: str) -> dict:
    resp = requests.get(f"{NOTION_BASE_URL}/{endpoint}", headers=HEADERS, timeout=120)
    resp.raise_for_status()
    return resp.json()

def create_database(parent_id: str, title: str, schema: dict) -> dict:
    """在parent_id下创建数据库"""
    payload = {
        "parent": {"type": "page_id", "page_id": parent_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": schema
    }
    resp = requests.post(f"{NOTION_BASE_URL}/databases", headers=HEADERS, json=payload, timeout=120)
    if not resp.ok:
        print(f"    ❌ 错误: {resp.status_code} - {resp.text}")
        resp.raise_for_status()
    return resp.json()

# ============ 1. Projects Schema ============
PROJECTS_SCHEMA = {
    "Project ID": {"title": {}},
    "Project Name": {"rich_text": {}},
    "Domain": {"select": {"options": [{"name": "AI-CFD", "color": "blue"}, {"name": "Harness-OS", "color": "green"}]}},
    "Repo URL": {"url": {}},
    "Active Spec Version": {"rich_text": {}},
    "Active Constraint Version": {"rich_text": {}},
    "Current Phase": {"rich_text": {}},
    "Project Status": {"select": {"options": [{"name": "Active", "color": "green"}, {"name": "Completed", "color": "gray"}, {"name": "Archived", "color": "red"}]}},
    "Owner": {"rich_text": {}},
    "Chief Reviewer": {"rich_text": {}},
    "Routing Policy": {"rich_text": {}},
    "Dashboard Link": {"url": {}},
}

# ============ 2. Specs Schema ============
SPECS_SCHEMA = {
    "Spec ID": {"title": {}},
    "Title": {"rich_text": {}},
    "Version": {"rich_text": {}},
    "Scope Type": {"select": {"options": [{"name": "项目规范", "color": "blue"}, {"name": "技术Spec", "color": "green"}, {"name": "接口规范", "color": "purple"}]}},
    "Status": {"select": {"options": [{"name": "Draft", "color": "gray"}, {"name": "Active", "color": "green"}, {"name": "Superseded", "color": "red"}]}},
    "Effective Date": {"date": {}},
    "Supersedes": {"rich_text": {}},
    "Linked Project": {"rich_text": {}},
    "Change Summary": {"rich_text": {}},
    "Risk Notes": {"rich_text": {}},
}

# ============ 3. Constraints Schema ============
CONSTRAINTS_SCHEMA = {
    "Constraint ID": {"title": {}},
    "Constraint Name": {"rich_text": {}},
    "Version": {"rich_text": {}},
    "Constraint Type": {"select": {"options": [{"name": "强制", "color": "red"}, {"name": "禁止", "color": "orange"}, {"name": "记录/接口/规则机/资源限制", "color": "yellow"}, {"name": "不合规示例", "color": "pink"}, {"name": "合规示例", "color": "green"}]}},
    "Severity": {"select": {"options": [{"name": "Blocker", "color": "red"}, {"name": "Critical", "color": "orange"}, {"name": "Warning", "color": "yellow"}]}},
    "Applies To": {"rich_text": {}},
    "Blocking Rule": {"rich_text": {}},
    "Validation Rule": {"rich_text": {}},
    "Last Updated": {"date": {}},
    "Linked Project": {"rich_text": {}},
}

# ============ 4. Phases Schema ============
PHASES_SCHEMA = {
    "Phase ID": {"title": {}},
    "Linked Project": {"rich_text": {}},
    "Phase Name": {"rich_text": {}},
    "Sequence": {"number": {"format": "number"}},
    "Input Spec Version": {"rich_text": {}},
    "Input Constraint Version": {"rich_text": {}},
    "Status": {"select": {"options": [{"name": "Pending", "color": "gray"}, {"name": "In Progress", "color": "blue"}, {"name": "Completed", "color": "green"}, {"name": "Blocked", "color": "red"}]}},
    "Assigned Executor": {"rich_text": {}},
    "Assigned Reviewer": {"rich_text": {}},
    "Review Decision": {"select": {"options": [{"name": "PASS", "color": "green"}, {"name": "FAIL", "color": "red"}, {"name": "Conditional", "color": "yellow"}]}},
    "Review Priority": {"select": {"options": [{"name": "P1", "color": "red"}, {"name": "P2", "color": "orange"}, {"name": "P3", "color": "yellow"}]}},
    "Start Time": {"date": {}},
    "End Time": {"date": {}},
    "Artifact Index": {"rich_text": {}},
    "Next Phase Pointer": {"rich_text": {}},
}

# ============ 5. Tasks Schema ============
TASKS_SCHEMA = {
    "Task ID": {"title": {}},
    "Linked Phase": {"rich_text": {}},
    "Linked Project": {"rich_text": {}},
    "Task Type": {"select": {"options": [{"name": "指令", "color": "blue"}, {"name": "分析", "color": "purple"}, {"name": "审查", "color": "orange"}, {"name": "学习", "color": "green"}, {"name": "任务", "color": "default"}]}},
    "Priority": {"select": {"options": [{"name": "P1", "color": "red"}, {"name": "P2", "color": "orange"}, {"name": "P3", "color": "yellow"}]}},
    "Executor Model": {"rich_text": {}},
    "Fallback Model": {"rich_text": {}},
    "Task Status": {"select": {"options": [{"name": "待领取", "color": "gray"}, {"name": "执行中", "color": "blue"}, {"name": "已完成", "color": "green"}, {"name": "失败", "color": "red"}]}},
    "Git Branch": {"rich_text": {}},
    "PR Link": {"url": {}},
    "Artifact Link": {"url": {}},
    "Failure Reason": {"rich_text": {}},
    "Retry Count": {"number": {"format": "number"}},
    "Last Run Summary": {"rich_text": {}},
}

# ============ 6. Reviews Schema ============
REVIEWS_SCHEMA = {
    "Review ID": {"title": {}},
    "Linked Phase": {"rich_text": {}},
    "Review Type": {"select": {"options": [{"name": "Gate Review", "color": "blue"}, {"name": "Code Review", "color": "green"}, {"name": "Spec Review", "color": "purple"}]}},
    "Reviewer Model": {"rich_text": {}},
    "Review Status": {"select": {"options": [{"name": "Pending", "color": "gray"}, {"name": "In Progress", "color": "blue"}, {"name": "Completed", "color": "green"}]}},
    "Decision": {"select": {"options": [{"name": "PASS", "color": "green"}, {"name": "FAIL", "color": "red"}, {"name": "Conditional", "color": "yellow"}]}},
    "Blocking Issues": {"rich_text": {}},
    "Conditional Pass Items": {"rich_text": {}},
    "Required Fixes": {"rich_text": {}},
    "Suggested Next Phase": {"rich_text": {}},
    "Review Artifact Link": {"url": {}},
    "Reviewed At": {"date": {}},
}

# ============ 7. Artifacts Schema ============
ARTIFACTS_SCHEMA = {
    "Artifact ID": {"title": {}},
    "Linked Task / Phase / Review": {"rich_text": {}},
    "Artifact Type": {"select": {"options": [{"name": "Component", "color": "blue"}, {"name": "Case", "color": "green"}, {"name": "Baseline", "color": "purple"}, {"name": "Evidence", "color": "yellow"}, {"name": "Code", "color": "orange"}, {"name": "Report", "color": "pink"}]}},
    "Storage URL": {"url": {}},
    "Provenance": {"rich_text": {}},
    "Generated By": {"rich_text": {}},
    "Timestamp": {"date": {}},
    "Retention Policy": {"select": {"options": [{"name": "永久", "color": "green"}, {"name": "项目周期", "color": "yellow"}, {"name": "临时", "color": "gray"}]}},
    "Summary": {"rich_text": {}},
}


def main():
    print("=" * 60)
    print("Well-Harness v1 架构迁移")
    print("=" * 60)

    if not NOTION_API_KEY:
        print("❌ NOTION_API_KEY 未设置")
        return

    # 1. 创建Projects数据库 (使用项目根页面作为parent)
    print("\n[1/7] 创建Projects数据库...")
    projects_db = create_database(PROJECT_PAGE_ID, "v1-Projects", PROJECTS_SCHEMA)
    print(f"    ✅ Projects DB创建成功: {projects_db.get('id')}")

    # 2. 创建Specs数据库
    print("\n[2/7] 创建Specs数据库...")
    specs_db = create_database(PROJECT_PAGE_ID, "v1-Specs", SPECS_SCHEMA)
    print(f"    ✅ Specs DB创建成功: {specs_db.get('id')}")

    # 3. 创建Constraints数据库
    print("\n[3/7] 创建Constraints数据库...")
    constraints_db = create_database(PROJECT_PAGE_ID, "v1-Constraints", CONSTRAINTS_SCHEMA)
    print(f"    ✅ Constraints DB创建成功: {constraints_db.get('id')}")

    # 4. 创建Phases数据库
    print("\n[4/7] 创建Phases数据库...")
    phases_db = create_database(PROJECT_PAGE_ID, "v1-Phases", PHASES_SCHEMA)
    print(f"    ✅ Phases DB创建成功: {phases_db.get('id')}")

    # 5. 创建Tasks数据库
    print("\n[5/7] 创建Tasks数据库...")
    tasks_db = create_database(PROJECT_PAGE_ID, "v1-Tasks", TASKS_SCHEMA)
    print(f"    ✅ Tasks DB创建成功: {tasks_db.get('id')}")

    # 6. 创建Reviews数据库
    print("\n[6/7] 创建Reviews数据库...")
    reviews_db = create_database(PROJECT_PAGE_ID, "v1-Reviews", REVIEWS_SCHEMA)
    print(f"    ✅ Reviews DB创建成功: {reviews_db.get('id')}")

    # 7. 创建Artifacts数据库
    print("\n[7/7] 创建Artifacts数据库...")
    artifacts_db = create_database(PROJECT_PAGE_ID, "v1-Artifacts", ARTIFACTS_SCHEMA)
    print(f"    ✅ Artifacts DB创建成功: {artifacts_db.get('id')}")

    # 打印汇总
    print("\n" + "=" * 60)
    print("v1数据库创建完成!")
    print("=" * 60)
    print(f"Projects DB:   {projects_db.get('id')}")
    print(f"Specs DB:     {specs_db.get('id')}")
    print(f"Constraints DB: {constraints_db.get('id')}")
    print(f"Phases DB:     {phases_db.get('id')}")
    print(f"Tasks DB:      {tasks_db.get('id')}")
    print(f"Reviews DB:    {reviews_db.get('id')}")
    print(f"Artifacts DB:  {artifacts_db.get('id')}")
    print("\n注意: Evidence Library保持现有ID不变")
    print("      Component/Case/Baseline库需迁移到Artifacts")

    # 保存DB IDs到本地文件
    db_ids = {
        "projects_db": projects_db.get('id'),
        "specs_db": specs_db.get('id'),
        "constraints_db": constraints_db.get('id'),
        "phases_db": phases_db.get('id'),
        "tasks_db": tasks_db.get('id'),
        "reviews_db": reviews_db.get('id'),
        "artifacts_db": artifacts_db.get('id'),
        "evidence_db": "33ac6894-2bed-8188-ba53-e80fb7920398",
    }
    with open("v1_db_ids.json", "w") as f:
        json.dump(db_ids, f, indent=2)
    print("\n✅ DB IDs已保存到 v1_db_ids.json")


if __name__ == "__main__":
    main()
