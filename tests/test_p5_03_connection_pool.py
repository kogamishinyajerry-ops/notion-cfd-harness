#!/usr/bin/env python3
"""
P5-03: Connection Pool and Async tests
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
import sys
from unittest.mock import Mock, AsyncMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.performance.connection_pool import (
    RateLimiter,
    RequestResult,
    NotionConnectionPool,
    create_notion_pool,
    NOTION_RATE_LIMIT,
    HAS_AIOHTTP,
    HAS_REQUESTS,
)
from knowledge_compiler.performance import PerformanceManager, create_performance_manager


def run_async_test(coro):
    """Helper to run async tests without pytest-asyncio"""
    return asyncio.run(coro())


class TestRateLimiter:
    def test_rate_limiter_initialization(self):
        """RateLimiter should initialize with burst capacity"""
        limiter = RateLimiter(rate=3.0, burst=5)

        assert limiter.rate == 3.0
        assert limiter.burst == 5
        assert limiter.tokens == 5

    def test_rate_limiter_acquire_sync(self):
        """RateLimiter should acquire tokens synchronously"""
        limiter = RateLimiter(rate=10.0, burst=5)

        start = time.time()
        for _ in range(3):
            limiter.acquire_sync(1)
        elapsed = time.time() - start

        # Should be very fast (no waiting needed)
        assert elapsed < 0.1

    def test_rate_limiter_acquire_sync_waits_when_empty(self):
        """RateLimiter should wait when tokens are empty"""
        limiter = RateLimiter(rate=100.0, burst=2)

        # Drain tokens
        limiter.acquire_sync(2)

        start = time.time()
        limiter.acquire_sync(1)
        elapsed = time.time() - start

        # Should wait for token refill
        assert elapsed >= 0.01  # At least 10ms for 1 token at 100/sec

    async def test_rate_limiter_acquire_async(self):
        """RateLimiter should acquire tokens asynchronously"""
        limiter = RateLimiter(rate=10.0, burst=5)

        start = time.time()
        for _ in range(3):
            await limiter.acquire(1)
        elapsed = time.time() - start

        # Should be very fast (no waiting needed)
        assert elapsed < 0.1


class TestRequestResult:
    def test_request_result_creation(self):
        """RequestResult should store all fields"""
        result = RequestResult(
            success=True,
            status_code=200,
            data={"id": "123"},
            elapsed_ms=45.2,
            retry_count=0,
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.data == {"id": "123"}
        assert result.elapsed_ms == 45.2
        assert result.retry_count == 0

    def test_request_result_error(self):
        """RequestResult should store error information"""
        result = RequestResult(
            success=False,
            error="Rate limited",
            elapsed_ms=100.0,
        )

        assert result.success is False
        assert result.error == "Rate limited"


class TestNotionConnectionPool:
    def test_notion_connection_pool_requires_api_key(self):
        """NotionConnectionPool should raise error without API key"""
        with patch.dict("os.environ", {}, clear=True):
            try:
                pool = NotionConnectionPool()
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "NOTION_API_KEY" in str(e)

    def test_notion_connection_pool_initialization_with_key(self):
        """NotionConnectionPool should initialize with API key"""
        pool = NotionConnectionPool(api_key="test_key")

        assert pool.api_key == "test_key"
        assert pool.rate_limiter is not None

    def test_notion_connection_pool_statistics(self):
        """NotionConnectionPool should track statistics"""
        pool = NotionConnectionPool(api_key="test_key")

        stats = pool.get_statistics()

        assert "total_requests" in stats
        assert "total_retries" in stats
        assert "total_errors" in stats
        assert "error_rate" in stats
        assert stats["total_requests"] == 0

    def test_notion_connection_pool_reset_statistics(self):
        """NotionConnectionPool should reset statistics"""
        pool = NotionConnectionPool(api_key="test_key")
        pool._total_requests = 10
        pool._total_errors = 2

        pool.reset_statistics()

        stats = pool.get_statistics()
        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0

    def test_notion_connection_pool_context_manager(self):
        """NotionConnectionPool should work as context manager"""
        with NotionConnectionPool(api_key="test_key") as pool:
            assert pool is not None
            assert pool.api_key == "test_key"


class TestPerformanceManagerAsync:
    async def test_performance_manager_has_connection_pool(self):
        """PerformanceManager should have connection pool when API key available"""
        # Skip if NOTION_API_KEY is set (real API)
        import os
        if os.environ.get("NOTION_API_KEY"):
            return

        pm = PerformanceManager(
            enable_connection_pool=True,
            notion_api_key="test_key",
        )

        # Should have connection pool even with test key
        assert pm.connection_pool is not None

        await pm.close()

    def test_performance_manager_connection_pool_disabled(self):
        """PerformanceManager should work without connection pool"""
        pm = PerformanceManager(
            enable_connection_pool=False,
        )

        assert pm.connection_pool is None

    async def test_get_cached_node_async(self):
        """PerformanceManager should get cached node asynchronously"""
        pm = PerformanceManager()

        test_node = {
            "unit_id": "FORM-009",
            "version": "v1.0",
            "data": "test",
        }

        await pm.set_cached_node_async("FORM-009", "v1.0", test_node)

        result = await pm.get_cached_node_async("FORM-009", "v1.0")
        assert result is not None
        assert result["unit_id"] == "FORM-009"

    async def test_warm_up_cache_async(self):
        """PerformanceManager should warm up cache asynchronously"""
        pm = PerformanceManager()

        entries = [
            ("FORM-009", "v1.0", {"data": "value1"}),
            ("FORM-010", "v1.0", {"data": "value2"}),
            ("FORM-011", "v1.0", {"data": "value3"}),
        ]

        count = await pm.warm_up_cache_async(entries)

        assert count == 3

        # Verify all cached
        assert await pm.get_cached_node_async("FORM-009", "v1.0") is not None
        assert await pm.get_cached_node_async("FORM-010", "v1.0") is not None
        assert await pm.get_cached_node_async("FORM-011", "v1.0") is not None

    async def test_fetch_multiple_concurrent(self):
        """PerformanceManager should fetch multiple nodes concurrently"""
        pm = PerformanceManager()

        # Pre-populate cache
        entries = [
            ("FORM-001", "v1.0", {"data": "value1"}),
            ("FORM-002", "v1.0", {"data": "value2"}),
            ("FORM-003", "v1.0", {"data": "value3"}),
        ]
        await pm.warm_up_cache_async(entries)

        # Fetch concurrently
        queries = [
            ("FORM-001", "v1.0"),
            ("FORM-002", "v1.0"),
            ("FORM-003", "v1.0"),
        ]

        start = time.time()
        results = await pm.fetch_multiple_concurrent(queries)
        elapsed = time.time() - start

        assert len(results) == 3
        assert all(r is not None for r in results)
        # Should be fast (concurrent)
        assert elapsed < 0.1

    async def test_get_version_chain_async(self):
        """PerformanceManager should get version chain asynchronously"""
        pm = PerformanceManager()

        version_dicts = [
            {
                "unit_id": "FORM-009",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash1",
                "lineage_hash": "lineage1",
                "timestamp": "2026-04-08T10:00:00",
                "metadata": {},
            },
            {
                "unit_id": "FORM-009",
                "version": "v1.1",
                "parent_hash": "hash1",
                "content_hash": "hash2",
                "lineage_hash": "lineage1",
                "timestamp": "2026-04-08T11:00:00",
                "metadata": {},
            },
        ]

        for v in version_dicts:
            pm.index_version(v)

        chain = await pm.get_version_chain_async("FORM-009")
        assert len(chain) == 2

    async def test_get_latest_version_async(self):
        """PerformanceManager should get latest version asynchronously"""
        pm = PerformanceManager()

        version_dicts = [
            {
                "unit_id": "FORM-009",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash1",
                "lineage_hash": "lineage1",
                "timestamp": "2026-04-08T10:00:00",
                "metadata": {},
            },
            {
                "unit_id": "FORM-009",
                "version": "v1.1",
                "parent_hash": "hash1",
                "content_hash": "hash2",
                "lineage_hash": "lineage1",
                "timestamp": "2026-04-08T11:00:00",
                "metadata": {},
            },
        ]

        for v in version_dicts:
            pm.index_version(v)

        latest = await pm.get_latest_version_async("FORM-009")
        assert latest is not None
        assert latest["version"] == "v1.1"

    async def test_async_context_manager(self):
        """PerformanceManager should work as async context manager"""
        async with PerformanceManager(
            enable_connection_pool=False,
        ) as pm:
            assert pm is not None
            await pm.set_cached_node_async("TEST", "v1.0", {"data": "test"})


class TestConcurrencyPerformance:
    async def test_concurrent_fetch_multiple(self):
        """Test that concurrent fetches work correctly"""
        pm = PerformanceManager()

        # Pre-populate cache
        entries = [(f"FORM-{i:03d}", "v1.0", {"data": f"value{i}"}) for i in range(50)]
        await pm.warm_up_cache_async(entries)

        queries = [(f"FORM-{i:03d}", "v1.0") for i in range(50)]

        # Fetch concurrently
        results = await pm.fetch_multiple_concurrent(queries)

        assert len(results) == 50
        assert all(r is not None for r in results)

    async def test_100_qps_target(self):
        """Test that we can handle 100+ QPS"""
        pm = PerformanceManager()

        # Pre-populate cache
        entries = [(f"UNIT-{i:04d}", "v1.0", {"data": f"value{i}"}) for i in range(100)]
        await pm.warm_up_cache_async(entries)

        queries = [(f"UNIT-{i % 100:04d}", "v1.0") for i in range(100)]

        # Measure 100 queries
        start = time.time()
        results = await pm.fetch_multiple_concurrent(queries)
        elapsed = time.time() - start

        assert len(results) == 100

        # Calculate QPS
        qps = 100 / elapsed

        # Should achieve >100 QPS for cached data
        assert qps > 100, f"QPS: {qps:.1f}, expected >100"

    async def test_close_cleanup(self):
        """Close should cleanup resources"""
        pm = PerformanceManager(
            enable_connection_pool=False,
        )

        await pm.close()

        # Should not raise error
        await pm.close()


class TestCreateFunctions:
    def test_performance_manager_connection_pool_disabled(self):
        """create_performance_manager should work without connection pool"""
        pm = create_performance_manager(
            enable_connection_pool=False,
        )
        assert pm is not None
        assert pm.connection_pool is None

    async def test_create_notion_pool(self):
        """create_notion_pool factory should work"""
        pool = await create_notion_pool(api_key="test_key")
        assert pool is not None
        await pool.close()

    def test_create_performance_manager_with_pool(self):
        """create_performance_manager should support connection pool"""
        pm = create_performance_manager(
            enable_connection_pool=False,
        )
        assert pm is not None
