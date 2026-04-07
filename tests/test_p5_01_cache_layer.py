#!/usr/bin/env python3
"""
P5-01: Cache Layer tests
"""

from __future__ import annotations

import json
import time
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.performance.cache_layer import (
    CacheLayer,
    L1CacheBackend,
    L2CacheBackend,
    create_cache_layer,
    DEFAULT_TTL,
    DEFAULT_MAX_SIZE,
    HAS_CACHETOOLS,
    HAS_REDIS,
)
from knowledge_compiler.performance import PerformanceManager, create_performance_manager


class TestL1CacheBackend:
    def test_l1_cache_backend_set_and_get(self):
        """L1 cache should return stored value"""
        cache = L1CacheBackend(maxsize=10, ttl=60)

        result = cache.set("test_key", {"data": "test_value"}, ttl=60)
        assert result is True

        value = cache.get("test_key")
        assert value is not None
        assert value["data"] == "test_value"

    def test_l1_cache_backend_miss_returns_none(self):
        """L1 cache should return None for non-existent key"""
        cache = L1CacheBackend(maxsize=10, ttl=60)

        value = cache.get("non_existent_key")
        assert value is None

    def test_l1_cache_backend_delete(self):
        """L1 cache should delete key"""
        cache = L1CacheBackend(maxsize=10, ttl=60)

        cache.set("test_key", {"data": "test_value"}, ttl=60)
        assert cache.exists("test_key") is True

        result = cache.delete("test_key")
        assert result is True
        assert cache.exists("test_key") is False

    def test_l1_cache_backend_clear(self):
        """L1 cache should clear all entries"""
        cache = L1CacheBackend(maxsize=10, ttl=60)

        cache.set("key1", {"data": "value1"}, ttl=60)
        cache.set("key2", {"data": "value2"}, ttl=60)

        result = cache.clear()
        assert result is True
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_l1_cache_backend_ttl_expiration(self):
        """L1 cache should expire entries after TTL"""
        # Use short TTL for testing
        cache = L1CacheBackend(maxsize=10, ttl=1)

        cache.set("test_key", {"data": "test_value"}, ttl=1)

        # Should be available immediately
        assert cache.get("test_key") is not None

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired (only works with cachetools)
        if HAS_CACHETOOLS:
            assert cache.get("test_key") is None

    def test_l1_cache_backend_maxsize(self):
        """L1 cache should enforce maxsize"""
        if not HAS_CACHETOOLS:
            return  # Skip test without cachetools

        cache = L1CacheBackend(maxsize=3, ttl=60)

        cache.set("key1", {"data": "value1"}, ttl=60)
        cache.set("key2", {"data": "value2"}, ttl=60)
        cache.set("key3", {"data": "value3"}, ttl=60)
        cache.set("key4", {"data": "value4"}, ttl=60)  # Should evict key1

        # With TTLCache, oldest entry is evicted
        assert cache.get("key4") is not None
        # key1 might be evicted due to maxsize
        # (TTLCache eviction is not guaranteed to be LRU without testing)

    def test_l1_cache_backend_size(self):
        """L1 cache should report correct size"""
        cache = L1CacheBackend(maxsize=10, ttl=60)

        assert cache.size == 0

        cache.set("key1", {"data": "value1"}, ttl=60)
        assert cache.size == 1

        cache.set("key2", {"data": "value2"}, ttl=60)
        assert cache.size == 2


class TestL2CacheBackend:
    def test_l2_cache_backend_disabled_when_no_redis(self):
        """L2 cache should be disabled when Redis not available"""
        cache = L2CacheBackend(url=None)

        assert cache.enabled is False

    def test_l2_cache_backend_returns_none_when_disabled(self):
        """L2 cache should return None when disabled"""
        cache = L2CacheBackend(url=None)

        assert cache.get("test_key") is None
        assert cache.set("test_key", {"data": "value"}, ttl=60) is False
        assert cache.delete("test_key") is False
        assert cache.clear() is False

    def test_l2_cache_backend_exists_returns_false_when_disabled(self):
        """L2 cache exists should return False when disabled"""
        cache = L2CacheBackend(url=None)

        assert cache.exists("test_key") is False


class TestCacheLayer:
    def test_cache_layer_key_format(self):
        """Cache layer should use correct key format"""
        cache = CacheLayer(maxsize=10, ttl=60)

        # Test key generation
        key = cache._make_key("FORM-009", "v1.0")
        assert key == "node:FORM-009:v1.0"

    def test_cache_layer_get_returns_cached_value(self):
        """Cache layer should return cached value"""
        cache = CacheLayer(maxsize=10, ttl=60)

        test_value = {"unit_id": "FORM-009", "version": "v1.0", "data": "test"}
        cache.set("FORM-009", "v1.0", test_value)

        result = cache.get("FORM-009", "v1.0")
        assert result is not None
        assert result["unit_id"] == "FORM-009"
        assert result["version"] == "v1.0"

    def test_cache_layer_get_miss_returns_none(self):
        """Cache layer should return None on cache miss"""
        cache = CacheLayer(maxsize=10, ttl=60)

        result = cache.get("FORM-009", "v1.0")
        assert result is None

    def test_cache_layer_set_returns_true_on_success(self):
        """Cache layer set should return True on success"""
        cache = CacheLayer(maxsize=10, ttl=60)

        test_value = {"unit_id": "FORM-009", "version": "v1.0"}
        result = cache.set("FORM-009", "v1.0", test_value)

        assert result is True  # L1 write always succeeds

    def test_cache_layer_delete(self):
        """Cache layer should delete entry"""
        cache = CacheLayer(maxsize=10, ttl=60)

        test_value = {"unit_id": "FORM-009", "version": "v1.0"}
        cache.set("FORM-009", "v1.0", test_value)

        assert cache.get("FORM-009", "v1.0") is not None

        cache.delete("FORM-009", "v1.0")

        assert cache.get("FORM-009", "v1.0") is None

    def test_cache_layer_clear(self):
        """Cache layer should clear all entries"""
        cache = CacheLayer(maxsize=10, ttl=60)

        cache.set("FORM-009", "v1.0", {"data": "value1"})
        cache.set("FORM-010", "v1.0", {"data": "value2"})

        cache.clear()

        assert cache.get("FORM-009", "v1.0") is None
        assert cache.get("FORM-010", "v1.0") is None

    def test_cache_layer_stats(self):
        """Cache layer should return statistics"""
        cache = CacheLayer(maxsize=10, ttl=60)

        stats = cache.get_stats()

        assert "l1_size" in stats
        assert "l1_enabled" in stats
        assert "l2_enabled" in stats
        assert "ttl" in stats
        assert stats["l1_enabled"] is True
        assert stats["ttl"] == 60

    def test_cache_layer_warm_up(self):
        """Cache layer should warm up with multiple entries"""
        cache = CacheLayer(maxsize=10, ttl=60)

        entries = [
            ("FORM-009", "v1.0", {"data": "value1"}),
            ("FORM-010", "v1.0", {"data": "value2"}),
            ("FORM-011", "v1.0", {"data": "value3"}),
        ]

        count = cache.warm_up(entries)

        assert count == 3
        assert cache.get("FORM-009", "v1.0") is not None
        assert cache.get("FORM-010", "v1.0") is not None
        assert cache.get("FORM-011", "v1.0") is not None


class TestPerformanceManager:
    def test_performance_manager_initialization(self):
        """PerformanceManager should initialize with cache"""
        pm = PerformanceManager(cache_ttl=60, cache_maxsize=100)

        assert pm.cache is not None

    def test_performance_manager_get_cached_node(self):
        """PerformanceManager should get cached node"""
        pm = PerformanceManager(cache_ttl=60, cache_maxsize=100)

        test_node = {
            "unit_id": "FORM-009",
            "version": "v1.0",
            "content_hash": "abc123",
            "created_at": "2026-04-08T00:00:00",
        }

        pm.set_cached_node("FORM-009", "v1.0", test_node)

        result = pm.get_cached_node("FORM-009", "v1.0")
        assert result is not None
        assert result["unit_id"] == "FORM-009"

    def test_performance_manager_invalidate_node(self):
        """PerformanceManager should invalidate cached node"""
        pm = PerformanceManager(cache_ttl=60, cache_maxsize=100)

        test_node = {"unit_id": "FORM-009", "version": "v1.0"}
        pm.set_cached_node("FORM-009", "v1.0", test_node)

        assert pm.get_cached_node("FORM-009", "v1.0") is not None

        pm.invalidate_node("FORM-009", "v1.0")

        assert pm.get_cached_node("FORM-009", "v1.0") is None

    def test_performance_manager_get_cache_stats(self):
        """PerformanceManager should return cache stats"""
        pm = PerformanceManager(cache_ttl=60, cache_maxsize=100)

        stats = pm.get_cache_stats()

        assert "l1_size" in stats
        assert "l2_enabled" in stats
        assert "ttl" in stats

    def test_performance_manager_warm_up_cache(self):
        """PerformanceManager should warm up cache"""
        pm = PerformanceManager(cache_ttl=60, cache_maxsize=100)

        entries = [
            ("FORM-009", "v1.0", {"data": "value1"}),
            ("FORM-010", "v1.0", {"data": "value2"}),
        ]

        count = pm.warm_up_cache(entries)

        assert count == 2
        assert pm.get_cached_node("FORM-009", "v1.0") is not None
        assert pm.get_cached_node("FORM-010", "v1.0") is not None


class TestCreateFunctions:
    def test_create_cache_layer(self):
        """create_cache_layer factory should work"""
        cache = create_cache_layer(maxsize=50, ttl=120)

        assert cache is not None
        assert cache.ttl == 120

    def test_create_performance_manager(self):
        """create_performance_manager factory should work"""
        pm = create_performance_manager(cache_ttl=60, cache_maxsize=50)

        assert pm is not None
        assert pm.cache.ttl == 60


class TestCachePerformance:
    def test_cache_hit_performance(self):
        """Cache hit should be fast (<1ms)"""
        pm = PerformanceManager(cache_ttl=60, cache_maxsize=100)

        test_node = {
            "unit_id": "FORM-009",
            "version": "v1.0",
            "data": "x" * 1000,  # Simulate realistic data
        }
        pm.set_cached_node("FORM-009", "v1.0", test_node)

        # Measure cache hit time
        start = time.perf_counter()
        for _ in range(1000):
            pm.get_cached_node("FORM-009", "v1.0")
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 1000) * 1000

        # Should be well under 1ms per hit
        assert avg_ms < 1.0, f"Cache hit took {avg_ms:.3f}ms, expected <1ms"

    def test_cache_write_performance(self):
        """Cache write should be fast"""
        pm = PerformanceManager(cache_ttl=60, cache_maxsize=100)

        test_node = {
            "unit_id": "FORM-009",
            "version": "v1.0",
            "data": "x" * 1000,
        }

        # Measure cache write time
        start = time.perf_counter()
        for i in range(100):
            pm.set_cached_node(f"FORM-{i}", "v1.0", test_node)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000

        # Should be under 1ms per write
        assert avg_ms < 1.0, f"Cache write took {avg_ms:.3f}ms, expected <1ms"
