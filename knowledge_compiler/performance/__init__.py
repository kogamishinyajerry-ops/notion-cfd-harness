#!/usr/bin/env python3
"""
P5-01: Performance Manager - Performance optimization layer

Integrates CacheLayer, IndexManager, and ConnectionPool to provide
performance optimizations for MemoryNetwork operations.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from pathlib import Path

# Import from cache_layer
from knowledge_compiler.performance.cache_layer import (
    CacheLayer,
    create_cache_layer,
    DEFAULT_TTL,
    DEFAULT_MAX_SIZE,
)

logger = logging.getLogger(__name__)


class PerformanceManager:
    """
    Performance optimization manager for MemoryNetwork

    Provides:
    - Caching layer (L1 in-memory, L2 optional Redis)
    - Cached node retrieval
    - Cache statistics
    """

    def __init__(
        self,
        cache_ttl: int = DEFAULT_TTL,
        cache_maxsize: int = DEFAULT_MAX_SIZE,
        redis_url: str | None = None,
    ):
        """
        Initialize PerformanceManager

        Args:
            cache_ttl: Cache time-to-live in seconds
            cache_maxsize: Maximum L1 cache size
            redis_url: Optional Redis URL (defaults to NOTION_REDIS_URL env var)
        """
        self.cache = create_cache_layer(
            maxsize=cache_maxsize,
            ttl=cache_ttl,
            l2_url=redis_url,
        )
        logger.info(
            f"PerformanceManager initialized: "
            f"L1 cache (maxsize={cache_maxsize}, ttl={cache_ttl}s)"
        )

    def get_cached_node(
        self, unit_id: str, version: str
    ) -> Optional[dict]:
        """
        Get cached MemoryNode dict

        Args:
            unit_id: Knowledge unit ID
            version: Version string

        Returns:
            Cached MemoryNode dict or None if not found
        """
        return self.cache.get(unit_id, version)

    def set_cached_node(
        self, unit_id: str, version: str, node: dict
    ) -> bool:
        """
        Cache a MemoryNode dict

        Args:
            unit_id: Knowledge unit ID
            version: Version string
            node: MemoryNode dict (asdict from MemoryNode dataclass)

        Returns:
            True if cached successfully
        """
        return self.cache.set(unit_id, version, node)

    def invalidate_node(self, unit_id: str, version: str) -> bool:
        """
        Invalidate cached node

        Args:
            unit_id: Knowledge unit ID
            version: Version string

        Returns:
            True if invalidated successfully
        """
        return self.cache.delete(unit_id, version)

    def clear_cache(self) -> bool:
        """
        Clear all cached entries

        Returns:
            True if cleared successfully
        """
        return self.cache.clear()

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics

        Returns:
            Dict with cache stats (l1_size, l2_enabled, ttl)
        """
        return self.cache.get_stats()

    def warm_up_cache(self, entries: list[tuple[str, str, dict]]) -> int:
        """
        Warm up cache with multiple entries

        Args:
            entries: List of (unit_id, version, value) tuples

        Returns:
            Number of entries successfully cached
        """
        return self.cache.warm_up(entries)


def create_performance_manager(
    cache_ttl: int = DEFAULT_TTL,
    cache_maxsize: int = DEFAULT_MAX_SIZE,
    redis_url: str | None = None,
) -> PerformanceManager:
    """
    Factory function to create PerformanceManager

    Args:
        cache_ttl: Cache time-to-live in seconds
        cache_maxsize: Maximum L1 cache size
        redis_url: Optional Redis URL

    Returns:
        Configured PerformanceManager instance
    """
    return PerformanceManager(
        cache_ttl=cache_ttl,
        cache_maxsize=cache_maxsize,
        redis_url=redis_url,
    )


# Export main classes
__all__ = [
    "PerformanceManager",
    "create_performance_manager",
    "CacheLayer",
    "create_cache_layer",
]
