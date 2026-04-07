#!/usr/bin/env python3
"""
P5-01: Performance Manager - Performance optimization layer

Integrates CacheLayer, IndexManager, and ConnectionPool to provide
performance optimizations for MemoryNetwork operations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

# Import from cache_layer
from knowledge_compiler.performance.cache_layer import (
    CacheLayer,
    create_cache_layer,
    DEFAULT_TTL,
    DEFAULT_MAX_SIZE,
)

# Import from index_manager
from knowledge_compiler.performance.index_manager import (
    IndexManager,
    create_index_manager,
    VersionIndexEntry,
    LineageIndex,
    UnitIndex,
)

logger = logging.getLogger(__name__)


class PerformanceManager:
    """
    Performance optimization manager for MemoryNetwork

    Provides:
    - Caching layer (L1 in-memory, L2 optional Redis)
    - Version history indexing (fast lineage queries)
    - Cached node retrieval
    - Cache and index statistics
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
        self.index = create_index_manager()
        logger.info(
            f"PerformanceManager initialized: "
            f"L1 cache (maxsize={cache_maxsize}, ttl={cache_ttl}s), "
            f"version index enabled"
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

    # Index methods

    def index_version(self, version_dict: dict) -> None:
        """
        Add a version to the index

        Args:
            version_dict: Version dict from VersionedKnowledgeRegistry
        """
        from knowledge_compiler.performance.index_manager import VersionIndexEntry

        entry = VersionIndexEntry(
            unit_id=version_dict.get("unit_id", ""),
            version=version_dict.get("version", ""),
            parent_hash=version_dict.get("parent_hash"),
            content_hash=version_dict.get("content_hash", ""),
            lineage_hash=version_dict.get("lineage_hash", ""),
            timestamp=datetime.fromisoformat(
                version_dict.get("timestamp", datetime.now().isoformat())
            ),
            metadata=version_dict.get("metadata", {}),
        )
        self.index.add_version(entry)

    def get_version_chain(
        self, unit_id: str, from_version: str | None = None
    ) -> list[dict]:
        """
        Get version chain for a unit (O(1) lookup)

        Args:
            unit_id: Unit ID
            from_version: Starting version (None = from beginning)

        Returns:
            List of version dicts in chain
        """
        entries = self.index.get_unit_chain(unit_id, from_version)
        return [
            {
                "unit_id": e.unit_id,
                "version": e.version,
                "parent_hash": e.parent_hash,
                "content_hash": e.content_hash,
                "lineage_hash": e.lineage_hash,
                "timestamp": e.timestamp.isoformat(),
                "metadata": e.metadata,
            }
            for e in entries
        ]

    def get_latest_version(self, unit_id: str) -> dict | None:
        """
        Get latest version for a unit

        Args:
            unit_id: Unit ID

        Returns:
            Latest version dict or None
        """
        entry = self.index.get_latest_version(unit_id)
        if entry is None:
            return None
        return {
            "unit_id": entry.unit_id,
            "version": entry.version,
            "parent_hash": entry.parent_hash,
            "content_hash": entry.content_hash,
            "lineage_hash": entry.lineage_hash,
            "timestamp": entry.timestamp.isoformat(),
            "metadata": entry.metadata,
        }

    def find_version_by_hash(self, content_hash: str) -> dict | None:
        """
        Find version by content hash

        Args:
            content_hash: Content hash to search

        Returns:
            Version dict or None
        """
        entry = self.index.get_version_by_hash(content_hash)
        if entry is None:
            return None
        return {
            "unit_id": entry.unit_id,
            "version": entry.version,
            "parent_hash": entry.parent_hash,
            "content_hash": entry.content_hash,
            "lineage_hash": entry.lineage_hash,
            "timestamp": entry.timestamp.isoformat(),
            "metadata": entry.metadata,
        }

    def rebuild_index(self, versions: list[dict]) -> int:
        """
        Rebuild index from version list

        Args:
            versions: List of version dicts

        Returns:
            Number of versions indexed
        """
        return self.index.rebuild_from_versions(versions)

    def get_index_stats(self) -> dict:
        """
        Get index statistics

        Returns:
            Dict with index stats
        """
        return self.index.get_statistics()

    def clear_index(self) -> None:
        """Clear all indexes"""
        self.index.clear()

    def get_full_stats(self) -> dict:
        """
        Get full statistics (cache + index)

        Returns:
            Dict with all stats
        """
        cache_stats = self.get_cache_stats()
        index_stats = self.get_index_stats()

        return {
            "cache": cache_stats,
            "index": index_stats,
        }


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
