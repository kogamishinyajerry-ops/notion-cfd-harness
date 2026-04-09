#!/usr/bin/env python3
"""
Test GitHub + Notion + Codex Review Workflow

This test file demonstrates the integrated workflow.
"""

import pytest


class TestGitHubWorkflow:
    """测试 GitHub 集成工作流"""

    def test_task_id_parsing(self):
        """测试任务 ID 解析"""
        commit_msg = "#P2-79: Add GitHub integration"
        import re
        task_id = re.search(r"#([A-Z0-9]+-[0-9]+)", commit_msg)
        assert task_id is not None
        assert task_id.group(1) == "P2-79"

    def test_branch_naming_convention(self):
        """测试分支命名规范"""
        branch = "feature/test-github-workflow"
        assert branch.startswith("feature/")
        assert "/" in branch

    def test_commit_message_format(self):
        """测试 commit 消息格式"""
        msg = "#TASK-123: Brief description\n\nDetails here."
        assert "#TASK-123" in msg
        assert "Brief description" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
