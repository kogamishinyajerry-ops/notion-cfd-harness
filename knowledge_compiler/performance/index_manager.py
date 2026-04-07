#!/usr/bin/env python3
"""
P5-02: Index Manager - Version history index optimization

Builds and maintains indexes for fast version history queries:
- lineage_hash → versions mapping
- unit_id → versions by time
- version lookup by hash

Optimizes get_version_chain() queries from O(n) to O(1) for indexed lookups.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VersionIndexEntry:
    """Index entry for a single version"""
    unit_id: str
    version: str
    parent_hash: str | None
    content_hash: str
    lineage_hash: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)


@dataclass
class LineageIndex:
    """
    Index for fast lineage-based lookups

    Maps lineage_hash → list of versions in chronological order
    """
    lineage_hash: str
    versions: list[VersionIndexEntry] = field(default_factory=list)

    def add_version(self, entry: VersionIndexEntry) -> None:
        """Add a version to this lineage"""
        self.versions.append(entry)
        # Keep sorted by timestamp
        self.versions.sort(key=lambda v: v.timestamp)

    def get_version(self, version: str) -> VersionIndexEntry | None:
        """Get specific version by name"""
        for v in self.versions:
            if v.version == version:
                return v
        return None

    def get_latest(self) -> VersionIndexEntry | None:
        """Get latest version in this lineage"""
        return self.versions[-1] if self.versions else None

    def get_chain(self, from_version: str | None = None) -> list[VersionIndexEntry]:
        """
        Get version chain from a specific version (or from start)

        Args:
            from_version: Starting version (None = from beginning)

        Returns:
            List of versions from from_version to latest
        """
        if not self.versions:
            return []

        if from_version is None:
            return list(self.versions)

        # Find starting point
        start_idx = None
        for i, v in enumerate(self.versions):
            if v.version == from_version:
                start_idx = i
                break

        if start_idx is None:
            return []

        return self.versions[start_idx:]


@dataclass
class UnitIndex:
    """
    Index for fast unit-based lookups

    Maps unit_id → versions by time
    """
    unit_id: str
    versions: dict[str, VersionIndexEntry] = field(default_factory=dict)
    by_timestamp: list[tuple[datetime, str]] = field(default_factory=list)

    def add_version(self, entry: VersionIndexEntry) -> None:
        """Add a version for this unit"""
        self.versions[entry.version] = entry
        # Maintain sorted by timestamp
        self.by_timestamp.append((entry.timestamp, entry.version))
        self.by_timestamp.sort(key=lambda x: x[0])

    def get_version(self, version: str) -> VersionIndexEntry | None:
        """Get specific version"""
        return self.versions.get(version)

    def get_latest(self) -> VersionIndexEntry | None:
        """Get latest version"""
        if not self.by_timestamp:
            return None
        _, latest_version = self.by_timestamp[-1]
        return self.versions.get(latest_version)

    def get_versions_in_range(
        self, start: datetime, end: datetime
    ) -> list[VersionIndexEntry]:
        """Get versions within time range"""
        result = []
        for ts, version in self.by_timestamp:
            if start <= ts <= end:
                result.append(self.versions[version])
        return result

    def get_all_versions(self) -> list[VersionIndexEntry]:
        """Get all versions sorted by timestamp"""
        return [
            self.versions[version]
            for _, version in self.by_timestamp
        ]


class IndexManager:
    """
    Index manager for fast version history queries

    Maintains multiple indexes:
    - by_lineage: lineage_hash → LineageIndex
    - by_unit: unit_id → UnitIndex
    - by_hash: content_hash → VersionIndexEntry

    Enables O(1) lookups for common queries.
    """

    def __init__(self):
        # Indexes
        self.by_lineage: dict[str, LineageIndex] = {}
        self.by_unit: dict[str, UnitIndex] = {}
        self.by_hash: dict[str, VersionIndexEntry] = {}

        # Statistics
        self._total_versions = 0
        self._total_lineages = 0
        self._total_units = 0
        self._last_updated: datetime | None = None

    def add_version(self, entry: VersionIndexEntry) -> None:
        """
        Add a version to all indexes

        Args:
            entry: Version index entry
        """
        # Add to lineage index
        if entry.lineage_hash not in self.by_lineage:
            self.by_lineage[entry.lineage_hash] = LineageIndex(
                lineage_hash=entry.lineage_hash
            )
            self._total_lineages += 1

        self.by_lineage[entry.lineage_hash].add_version(entry)

        # Add to unit index
        if entry.unit_id not in self.by_unit:
            self.by_unit[entry.unit_id] = UnitIndex(unit_id=entry.unit_id)
            self._total_units += 1

        self.by_unit[entry.unit_id].add_version(entry)

        # Add to hash index
        self.by_hash[entry.content_hash] = entry

        self._total_versions += 1
        self._last_updated = datetime.now()

    def get_version_by_hash(
        self, content_hash: str
    ) -> VersionIndexEntry | None:
        """
        Get version by content hash (O(1))

        Args:
            content_hash: Content hash to look up

        Returns:
            Version entry or None
        """
        return self.by_hash.get(content_hash)

    def get_lineage_chain(
        self, lineage_hash: str, from_version: str | None = None
    ) -> list[VersionIndexEntry]:
        """
        Get version chain for a lineage (O(1) + chain length)

        Args:
            lineage_hash: Lineage hash
            from_version: Starting version (None = from beginning)

        Returns:
            List of versions in chain
        """
        lineage = self.by_lineage.get(lineage_hash)
        if lineage is None:
            return []

        return lineage.get_chain(from_version)

    def get_unit_chain(
        self, unit_id: str, from_version: str | None = None
    ) -> list[VersionIndexEntry]:
        """
        Get version chain for a unit

        Args:
            unit_id: Unit ID
            from_version: Starting version (None = from beginning)

        Returns:
            List of versions in chain
        """
        unit_index = self.by_unit.get(unit_id)
        if unit_index is None:
            return []

        if from_version is None:
            return unit_index.get_all_versions()

        # Build chain from from_version
        result = []
        found = False
        for v in unit_index.get_all_versions():
            if found or v.version == from_version:
                result.append(v)
                found = True
        return result if found else []

    def get_latest_version(self, unit_id: str) -> VersionIndexEntry | None:
        """
        Get latest version for a unit (O(log n)))

        Args:
            unit_id: Unit ID

        Returns:
            Latest version entry or None
        """
        unit_index = self.by_unit.get(unit_id)
        if unit_index is None:
            return None

        return unit_index.get_latest()

    def get_versions_in_range(
        self,
        unit_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[VersionIndexEntry]:
        """
        Get versions within time range

        Args:
            unit_id: Filter by unit (None = all units)
            start: Start time (None = beginning)
            end: End time (None = now)

        Returns:
            List of matching versions
        """
        if unit_id:
            unit_index = self.by_unit.get(unit_id)
            if unit_index is None:
                return []

            start = start or datetime.min
            end = end or datetime.max
            return unit_index.get_versions_in_range(start, end)

        # Search all units
        result = []
        start = start or datetime.min
        end = end or datetime.max

        for unit_index in self.by_unit.values():
            result.extend(unit_index.get_versions_in_range(start, end))

        # Sort by timestamp
        result.sort(key=lambda v: v.timestamp)
        return result

    def find_lineage_root(self, unit_id: str) -> VersionIndexEntry | None:
        """
        Find the root version (first version) of a unit's lineage

        Args:
            unit_id: Unit ID

        Returns:
            Root version entry or None
        """
        unit_index = self.by_unit.get(unit_id)
        if unit_index is None or not unit_index.by_timestamp:
            return None

        _, first_version = unit_index.by_timestamp[0]
        return unit_index.get_version(first_version)

    def get_statistics(self) -> dict:
        """
        Get index statistics

        Returns:
            Dict with index stats
        """
        return {
            "total_versions": self._total_versions,
            "total_lineages": self._total_lineages,
            "total_units": self._total_units,
            "last_updated": self._last_updated.isoformat() if self._last_updated else None,
            "avg_versions_per_unit": (
                self._total_versions / self._total_units if self._total_units > 0 else 0
            ),
            "avg_versions_per_lineage": (
                self._total_versions / self._total_lineages if self._total_lineages > 0 else 0
            ),
        }

    def clear(self) -> None:
        """Clear all indexes"""
        self.by_lineage.clear()
        self.by_unit.clear()
        self.by_hash.clear()
        self._total_versions = 0
        self._total_lineages = 0
        self._total_units = 0
        self._last_updated = None

    def rebuild_from_versions(self, versions: list[dict]) -> int:
        """
        Rebuild indexes from a list of version dicts

        Args:
            versions: List of version dicts (from VersionedKnowledgeRegistry)

        Returns:
            Number of versions indexed
        """
        self.clear()

        for v_dict in versions:
            entry = VersionIndexEntry(
                unit_id=v_dict.get("unit_id", ""),
                version=v_dict.get("version", ""),
                parent_hash=v_dict.get("parent_hash"),
                content_hash=v_dict.get("content_hash", ""),
                lineage_hash=v_dict.get("lineage_hash", ""),
                timestamp=datetime.fromisoformat(
                    v_dict.get("timestamp", datetime.now().isoformat())
                ),
                metadata=v_dict.get("metadata", {}),
            )
            self.add_version(entry)

        return self._total_versions


def create_index_manager() -> IndexManager:
    """Factory function to create IndexManager"""
    return IndexManager()


# Export main classes
__all__ = [
    "IndexManager",
    "create_index_manager",
    "VersionIndexEntry",
    "LineageIndex",
    "UnitIndex",
]
