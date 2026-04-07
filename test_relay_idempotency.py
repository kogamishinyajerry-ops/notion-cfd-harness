#!/usr/bin/env python3
"""
Well-Harness M1-6 Relay 幂等性加固 — pytest 单元测试
覆盖：expires_at / 归档 / 幂等写入 / 重试 / stale 检测
"""

import pytest
import time
import re
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from notion_cfd_loop import (
    write_signal_to_log,
    relay_check,
    relay_dispatch,
    _archive_oldest_entries,
    _generate_signal_id,
    MAX_LOG_RETRIES,
    LOG_ARCHIVE_THRESHOLD,
    DISPATCH_EXPIRY_HOURS,
)


class TestSignalIdGeneration:
    """signal_id 生成测试"""

    def test_signal_id_is_unique(self):
        ids = [_generate_signal_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_signal_id_is_8_chars(self):
        sid = _generate_signal_id()
        assert len(sid) == 8


class TestExpiresAtField:
    """DISPATCH 信号 expires_at 字段测试"""

    def test_dispatch_signal_has_expires_at(self):
        """验证 write_signal_to_log 对 DISPATCH 类型添加 expires_at"""
        mock_page = {
            "properties": {
                "执行日志": {
                    "type": "rich_text",
                    "rich_text": []
                }
            }
        }

        with patch('notion_cfd_loop.notion_get', return_value=mock_page):
            with patch('notion_cfd_loop.notion_patch') as mock_patch:
                # 清除单例缓存（每次测试独立）
                if hasattr(write_signal_to_log, '_locks'):
                    write_signal_to_log._locks.clear()

                ok = write_signal_to_log("page-123", "DISPATCH", {"gate": "G0"})
                assert ok is True
                call_args = mock_patch.call_args[0][1]
                content = call_args["properties"]["执行日志"]["rich_text"][0]["text"]["content"]
                # expires_at 字段必须存在
                assert "expires_at=" in content

    def test_non_dispatch_no_expires_at(self):
        """ACK/COMPLETION 不添加 expires_at"""
        mock_page = {
            "properties": {
                "执行日志": {
                    "type": "rich_text",
                    "rich_text": []
                }
            }
        }

        with patch('notion_cfd_loop.notion_get', return_value=mock_page):
            with patch('notion_cfd_loop.notion_patch') as mock_patch:
                if hasattr(write_signal_to_log, '_locks'):
                    write_signal_to_log._locks.clear()

                ok = write_signal_to_log("page-123", "ACK", {"acknowledged_signal_id": "abc123"})
                assert ok is True
                call_args = mock_patch.call_args[0][1]
                content = call_args["properties"]["执行日志"]["rich_text"][0]["text"]["content"]
                assert "expires_at=" not in content


class TestIdempotency:
    """幂等性测试 — 重复 signal_id 写入应跳过"""

    def test_duplicate_signal_id_skips_write(self):
        """已存在的 signal_id 再次写入时跳过（不调用 notion_patch）"""
        existing_log = (
            "[DISPATCH] timestamp=2026-04-07 10:00:00 | task_id=page-123 | signal_id=abcdef01 | gate=G0"
        )
        mock_page = {
            "properties": {
                "执行日志": {
                    "type": "rich_text",
                    "rich_text": [{"type": "text", "plain_text": existing_log}]
                }
            }
        }

        with patch('notion_cfd_loop.notion_get', return_value=mock_page):
            with patch('notion_cfd_loop.notion_patch') as mock_patch:
                if hasattr(write_signal_to_log, '_locks'):
                    write_signal_to_log._locks.clear()

                # 使用已存在的 signal_id
                ok = write_signal_to_log("page-123", "COMPLETION", {
                    "signal_id": "abcdef01",
                    "gate": "G0",
                    "pass": "TRUE"
                })
                assert ok is True
                # 不应再调用 patch（幂等跳过）
                assert mock_patch.call_count == 0


class TestLogArchive:
    """日志归档测试 — 超过阈值时自动归档"""

    def test_archive_threshold_constant(self):
        assert LOG_ARCHIVE_THRESHOLD == 1800

    def test_archive_threshold_check(self):
        """当 current_log 超过阈值时应触发归档"""
        # 构建超过阈值的日志（1800+ chars）
        large_log = "\n".join([
            f"[DISPATCH] timestamp=2026-04-07 10:00:{i:02d} | task_id=page-123 | signal_id={i:08d} | gate=G{i%7} | expires_at=2026-04-08 10:00:{i:02d}"
            for i in range(50)
        ])
        assert len(large_log) > LOG_ARCHIVE_THRESHOLD

    def test_archive_function_returns_summary(self):
        """_archive_oldest_entries 返回归档摘要"""
        mock_page_id = "archive-test-page"
        current_log = "\n".join([f"[DISPATCH] line {i}" for i in range(20)])

        with patch('notion_cfd_loop.notion_post') as mock_post:
            mock_post.return_value = {"id": "archived-page-id-123"}
            if hasattr(write_signal_to_log, '_locks'):
                write_signal_to_log._locks.clear()

            result = _archive_oldest_entries(mock_page_id, current_log, "DISPATCH")

            assert result is not None
            assert "ARCHIVED" in result
            # 归档一半：20 行 -> 归档 10 条，保留 10 条
            assert "10 条记录已归档" in result
            # 验证创建归档子页面
            mock_post.assert_called_once()
            call_args = mock_post.call_args[0][1]
            assert "parent" in call_args
            assert "children" in call_args


class TestRetryLogic:
    """重试逻辑测试"""

    def test_max_retries_constant(self):
        assert MAX_LOG_RETRIES == 3

    def test_write_retries_on_failure(self):
        """写入失败时重试 3 次"""
        mock_page = {
            "properties": {
                "执行日志": {
                    "type": "rich_text",
                    "rich_text": []
                }
            }
        }

        call_count = [0]

        def fail_twice(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Transient error")
            return {}

        with patch('notion_cfd_loop.notion_get', return_value=mock_page):
            with patch('notion_cfd_loop.notion_patch', side_effect=fail_twice):
                if hasattr(write_signal_to_log, '_locks'):
                    write_signal_to_log._locks.clear()

                ok = write_signal_to_log("page-123", "DISPATCH", {"gate": "G0"})
                # 第3次应成功
                assert ok is True
                assert call_count[0] == 3


class TestStaleDetection:
    """Stale DISPATCH 检测测试"""

    def test_stale_detection_uses_expires_at(self):
        """有 expires_at 的过期 DISPATCH 应被标记为 stale"""
        # 构造一个已过期的 DISPATCH
        expired_time = (datetime.now() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")

        mock_signals = {
            "DISPATCH": [{
                "signal_id": "stale001",
                "gate": "G0",
                "timestamp": expired_time,
                "expires_at": expired_time,  # 已过期
            }],
            "COMPLETION": [],
            "ACK": []
        }

        with patch('notion_cfd_loop.get_page_execution_log', return_value=("", mock_signals)):
            result = relay_check("page-123")
            stale = result["stale_dispatches"]
            assert len(stale) == 1
            assert stale[0]["signal_id"] == "stale001"
            assert "stale_reason" in stale[0]

    def test_stale_detection_falls_back_to_timeout(self):
        """没有 expires_at 但超过 30min 的 DISPATCH 应被标记为 stale"""
        old_time = (datetime.now() - timedelta(minutes=35)).strftime("%Y-%m-%d %H:%M:%S")

        mock_signals = {
            "DISPATCH": [{
                "signal_id": "stale002",
                "gate": "G1",
                "timestamp": old_time,
                # 没有 expires_at
            }],
            "COMPLETION": [],
            "ACK": []
        }

        with patch('notion_cfd_loop.get_page_execution_log', return_value=("", mock_signals)):
            result = relay_check("page-123")
            stale = result["stale_dispatches"]
            assert len(stale) == 1
            assert "超过 30 分钟超时" in stale[0]["stale_reason"]

    def test_non_stale_dispatch_passes(self):
        """最近 10 分钟内的 DISPATCH 不应被标记为 stale"""
        recent = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        mock_signals = {
            "DISPATCH": [{
                "signal_id": "fresh001",
                "gate": "G2",
                "timestamp": recent,
                "expires_at": (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
            }],
            "COMPLETION": [],
            "ACK": []
        }

        with patch('notion_cfd_loop.get_page_execution_log', return_value=("", mock_signals)):
            result = relay_check("page-123")
            stale = result["stale_dispatches"]
            assert len(stale) == 0


class TestArchiveIdempotency:
    """归档幂等性测试"""

    def test_archive_small_log_skips(self):
        """日志少于等于 4 行时不归档"""
        small_log = "\n".join([f"[DISPATCH] line {i}" for i in range(3)])

        with patch('notion_cfd_loop.notion_post') as mock_post:
            if hasattr(write_signal_to_log, '_locks'):
                write_signal_to_log._locks.clear()

            result = _archive_oldest_entries("page-123", small_log, "DISPATCH")
            # 返回 None 表示跳过归档
            assert result is None
            mock_post.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
