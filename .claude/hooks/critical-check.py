#!/usr/bin/env python3
"""
GSD Critical Point Check

当检测到关键情况时，停下来让用户手动介入。
"""

import os
import re
import subprocess
from typing import List, Optional
from pathlib import Path


class CriticalCheck:
    """关键点检查器"""

    # 关键触发条件
    TRIGGERS = {
        "architecture_change": {
            "patterns": [
                r"refactor.*core",
                r"change.*architecture",
                r"redesign.*system",
                r"new.*pattern",
            ],
            "files": [r".*__init__\.py$", r".*schema\.py$", r".*core\.py$"],
            "reason": "架构变更需要设计审查",
        },
        "performance_degradation": {
            "patterns": [
                r"#.*slow",
                r"#.*optimize",
                r"#.*performance",
            ],
            "reason": "性能问题需要性能审查",
        },
        "security_issue": {
            "patterns": [
                r"eval\(",
                r"exec\(",
                r"__import__",
                r"os\.system",
                r"subprocess.*shell=True",
            ],
            "reason": "安全漏洞需要安全审查",
        },
        "ambiguous_requirement": {
            "patterns": [
                r"#.*TODO.*clarify",
                r"#.*FIXME.*unclear",
                r"#.*ask.*user",
            ],
            "reason": "需求不明确需要澄清",
        },
    }

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path.cwd()

    def check_staged_changes(self) -> List[dict]:
        """检查暂存的变更"""
        critical_issues = []

        # 获取暂存的文件
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return []

        staged_files = result.stdout.strip().split("\n")
        staged_files = [f for f in staged_files if f]

        for file_path in staged_files:
            full_path = self.repo_root / file_path
            if not full_path.exists():
                continue

            issues = self._check_file(file_path, full_path)
            critical_issues.extend(issues)

        return critical_issues

    def check_test_failures(self) -> bool:
        """检查是否有多次测试失败"""
        # 这里可以读取测试历史或检查最近的结果
        test_results_dir = self.repo_root / ".pytest_cache"
        if not test_results_dir.exists():
            return False

        # 简化检查：查找最近的失败记录
        for log_file in test_results_dir.rglob("*.log"):
            if log_file.stat().st_size > 0:
                content = log_file.read_text()
                if "FAILED" in content and content.count("FAILED") >= 5:
                    return True

        return False

    def _check_file(self, file_path: str, full_path: Path) -> List[dict]:
        """检查单个文件"""
        issues = []

        try:
            content = full_path.read_text()
        except Exception:
            return issues

        for trigger_type, config in self.TRIGGERS.items():
            # 检查文件名模式
            if "files" in config:
                for pattern in config["files"]:
                    if re.match(pattern, file_path):
                        issues.append({
                            "type": trigger_type,
                            "file": file_path,
                            "reason": config["reason"],
                            "match": "filename_match",
                        })
                        continue

            # 检查内容模式
            if "patterns" in config:
                for pattern in config["patterns"]:
                    if re.search(pattern, content, re.IGNORECASE):
                        issues.append({
                            "type": trigger_type,
                            "file": file_path,
                            "reason": config["reason"],
                            "match": pattern,
                        })

        return issues

    def should_pause(self) -> Optional[dict]:
        """判断是否应该暂停"""
        # 检查暂存变更
        critical_issues = self.check_staged_changes()
        if critical_issues:
            return {
                "reason": "critical_change_detected",
                "issues": critical_issues,
                "action": "review_with_opus",
            }

        # 检查测试失败
        if self.check_test_failures():
            return {
                "reason": "multiple_test_failures",
                "action": "root_cause_analysis",
            }

        return None

    def format_critical_message(self, pause_info: dict) -> str:
        """格式化关键消息"""
        lines = [
            "",
            "🛑 CRITICAL: 需要人工介入",
            "",
        ]

        if pause_info["reason"] == "critical_change_detected":
            lines.append("检测到关键变更:")
            for issue in pause_info["issues"]:
                lines.append(f"  - {issue['reason']}")
                lines.append(f"    文件: {issue['file']}")
                if issue.get("match") and issue["match"] != "filename_match":
                    lines.append(f"    匹配: {issue['match']}")
            lines.append("")
            lines.append("请在 Notion 中 @Opus 4.6 进行审查:")
            lines.append("  1. 打开 Notion workspace")
            lines.append("  2. 找到对应的设计文档或任务")
            lines.append("  3. @Opus 4.6 请求审查")
            lines.append("")
            lines.append("审查通过后，使用 --skip-critical-check 继续")

        elif pause_info["reason"] == "multiple_test_failures":
            lines.append("检测到多次测试失败")
            lines.append("")
            lines.append("请进行根因分析:")
            lines.append("  1. 查看测试日志")
            lines.append("  2. 识别失败模式")
            lines.append("  3. 在 Notion 中记录分析结果")
            lines.append("")
            lines.append("修复后，使用 --skip-critical-check 继续")

        lines.extend([
            "",
            "如需跳过此检查（不推荐）:",
            "  git commit --no-verify",
            "",
        ])

        return "\n".join(lines)


def main():
    """主函数"""
    import sys

    check = CriticalCheck()
    pause_info = check.should_pause()

    if pause_info:
        message = check.format_critical_message(pause_info)
        print(message, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
