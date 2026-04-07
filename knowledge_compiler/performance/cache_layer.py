#!/usr/bin/env python3
"""
P5-01: Cache Layer - Two-tier caching system

L1: In-memory cache using cachetools.TTLCache (always enabled)
L2: Optional Redis cache (enabled via NOTION_REDIS_URL environment variable)

Cache key format: "node:{unit_id}:{version}"
"""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Optional, Protocol
from pathlib import Path

try:
    from cachetools import TTLCache
    HAS_CACHETOOLS = True
except ImportError:
    # Fallback to functools.lru_cache
    from functools import lru_cache
    HAS_CACHETOOLS = False

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


logger = logging.getLogger(__name__)


# Default cache configuration
DEFAULT_TTL = 3600  # 1 hour
DEFAULT_MAX_SIZE = 1000


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: dict  # Serialized MemoryNode
    timestamp: datetime
    ttl: int
    source: str  # "L1" or "L2"


class CacheBackend(Protocol):
    """Cache backend protocol"""

    def get(self, key: str) -> Optional[dict]:
        """Get value from cache"""
        ...

    def set(self, key: str, value: dict, ttl: int) -> bool:
        """Set value in cache"""
        ...

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        ...

    def clear(self) -> bool:
        """Clear all cache entries"""
        ...

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        ...


class L1CacheBackend:
    """L1: In-memory cache using cachetools.TTLCache"""

    def __init__(self, maxsize: int = DEFAULT_MAX_SIZE, ttl: int = DEFAULT_TTL):
        self.ttl = ttl
        if HAS_CACHETOOLS:
            self._cache: TTLCache[str, dict] = TTLCache(maxsize=maxsize, ttl=ttl)
        else:
            # Simple dict-based cache with manual expiration
            self._cache: dict[str, tuple[dict, datetime]] = {}
            self._maxsize = maxsize

    def get(self, key: str) -> Optional[dict]:
        if HAS_CACHETOOLS:
            return self._cache.get(key)
        else:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if datetime.now() > expiry:
                del self._cache[key]
                return None
            return value

    def set(self, key: str, value: dict, ttl: int | None = None) -> bool:
        try:
            if HAS_CACHETOOLS:
                self._cache[key] = value
            else:
                ttl = ttl or self.ttl
                expiry = datetime.now() + timedelta(seconds=ttl)
                self._cache[key] = (value, expiry)
                # Enforce maxsize
                if len(self._cache) > self._maxsize:
                    # Remove oldest entry
                    oldest = min(self._cache.items(), key=lambda x: x[1][1])
                    del self._cache[oldest[0]]
            return True
        except Exception as e:
            logger.warning(f"L1 cache set failed: {e}")
            return False

    def delete(self, key: str) -> bool:
        try:
            if HAS_CACHETOOLS:
                self._cache.pop(key, None)
            else:
                self._cache.pop(key, None)
            return True
        except Exception as e:
            logger.warning(f"L1 cache delete failed: {e}")
            return False

    def clear(self) -> bool:
        try:
            if HAS_CACHETOOLS:
                self._cache.clear()
            else:
                self._cache.clear()
            return True
        except Exception as e:
            logger.warning(f"L1 cache clear failed: {e}")
            return False

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    @property
    def size(self) -> int:
        if HAS_CACHETOOLS:
            return len(self._cache)
        else:
            return len(self._cache)


class L2CacheBackend:
    """L2: Optional Redis cache"""

    def __init__(self, url: str | None = None):
        self._client: Any = None
        self._enabled = False

        if not HAS_REDIS:
            logger.warning("redis package not installed, L2 cache disabled")
            return

        url = url or os.environ.get("NOTION_REDIS_URL")
        if not url:
            logger.info("NOTION_REDIS_URL not set, L2 cache disabled")
            return

        try:
            self._client = redis.from_url(url, decode_responses=True)
            self._client.ping()
            self._enabled = True
            logger.info(f"L2 Redis cache enabled: {url}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, L2 cache disabled")
            self._client = None

    def get(self, key: str) -> Optional[dict]:
        if not self._enabled or self._client is None:
            return None

        try:
            data = self._client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"L2 cache get failed: {e}")
        return None

    def set(self, key: str, value: dict, ttl: int | None = None) -> bool:
        if not self._enabled or self._client is None:
            return False

        try:
            data = json.dumps(value)
            ttl = ttl or DEFAULT_TTL
            self._client.setex(key, ttl, data)
            return True
        except Exception as e:
            logger.warning(f"L2 cache set failed: {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self._enabled or self._client is None:
            return False

        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"L2 cache delete failed: {e}")
            return False

    def clear(self) -> bool:
        if not self._enabled or self._client is None:
            return False

        try:
            # Only clear keys with our prefix to avoid affecting other data
            for key in self._client.scan_iter(match="node:*"):
                self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"L2 cache clear failed: {e}")
            return False

    def exists(self, key: str) -> bool:
        if not self._enabled or self._client is None:
            return False

        try:
            return self._client.exists(key) > 0
        except Exception as e:
            logger.warning(f"L2 cache exists check failed: {e}")
            return False

    @property
    def enabled(self) -> bool:
        return self._enabled


class CacheLayer:
    """
    Two-tier cache layer with L1 (in-memory) and L2 (optional Redis)

    Cache key format: "node:{unit_id}:{version}"

    Read path: L1 → (miss) → L2 → (miss) → None
    Write path: L1 + L2 (if enabled)
    """

    def __init__(
        self,
        maxsize: int = DEFAULT_MAX_SIZE,
        ttl: int = DEFAULT_TTL,
        l2_url: str | None = None,
    ):
        self.l1 = L1CacheBackend(maxsize=maxsize, ttl=ttl)
        self.l2 = L2CacheBackend(url=l2_url)
        self.ttl = ttl

    def _make_key(self, unit_id: str, version: str) -> str:
        """Generate cache key"""
        return f"node:{unit_id}:{version}"

    def get(self, unit_id: str, version: str) -> Optional[dict]:
        """
        Get from cache, checking L1 then L2

        Returns cached MemoryNode dict or None
        """
        key = self._make_key(unit_id, version)

        # Try L1 first
        value = self.l1.get(key)
        if value is not None:
            logger.debug(f"L1 cache hit: {key}")
            return value

        # Try L2
        value = self.l2.get(key)
        if value is not None:
            logger.debug(f"L2 cache hit: {key}")
            # Populate L1
            self.l1.set(key, value, self.ttl)
            return value

        logger.debug(f"Cache miss: {key}")
        return None

    def set(self, unit_id: str, version: str, value: dict) -> bool:
        """
        Set value in both L1 and L2

        Returns True if at least L1 write succeeded
        """
        key = self._make_key(unit_id, version)

        # Always write to L1
        l1_ok = self.l1.set(key, value, self.ttl)

        # Write to L2 if enabled
        l2_ok = self.l2.set(key, value, self.ttl)

        return l1_ok  # Success if L1 worked

    def delete(self, unit_id: str, version: str) -> bool:
        """Delete from both L1 and L2"""
        key = self._make_key(unit_id, version)
        l1_ok = self.l1.delete(key)
        l2_ok = self.l2.delete(key)
        return l1_ok or l2_ok

    def clear(self) -> bool:
        """Clear both L1 and L2"""
        l1_ok = self.l1.clear()
        l2_ok = self.l2.clear()
        return l1_ok or l2_ok

    def get_stats(self) -> dict:
        """Get cache statistics"""
        return {
            "l1_size": self.l1.size,
            "l1_enabled": True,
            "l2_enabled": self.l2.enabled,
            "ttl": self.ttl,
        }

    def warm_up(self, entries: list[tuple[str, str, dict]]) -> int:
        """
        Warm up cache with multiple entries

        Args:
            entries: List of (unit_id, version, value) tuples

        Returns:
            Number of entries successfully cached
        """
        count = 0
        for unit_id, version, value in entries:
            if self.set(unit_id, version, value):
                count += 1
        return count


def create_cache_layer(
    maxsize: int = DEFAULT_MAX_SIZE,
    ttl: int = DEFAULT_TTL,
    l2_url: str | None = None,
) -> CacheLayer:
    """
    Factory function to create CacheLayer

    Args:
        maxsize: Maximum L1 cache size
        ttl: Time-to-live in seconds
        l2_url: Optional Redis URL (defaults to NOTION_REDIS_URL env var)

    Returns:
        Configured CacheLayer instance
    """
    return CacheLayer(maxsize=maxsize, ttl=ttl, l2_url=l2_url)
