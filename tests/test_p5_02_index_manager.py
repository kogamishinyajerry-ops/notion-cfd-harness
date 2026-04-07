#!/usr/bin/env python3
"""
P5-02: Index Manager tests
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.performance.index_manager import (
    IndexManager,
    create_index_manager,
    VersionIndexEntry,
    LineageIndex,
    UnitIndex,
)
from knowledge_compiler.performance import PerformanceManager, create_performance_manager


class TestVersionIndexEntry:
    def test_version_index_entry_creation(self):
        """VersionIndexEntry should store all fields"""
        entry = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="abc123",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 12, 0),
            metadata={"author": "system"},
        )

        assert entry.unit_id == "FORM-009"
        assert entry.version == "v1.0"
        assert entry.parent_hash is None
        assert entry.content_hash == "abc123"
        assert entry.lineage_hash == "lineage1"


class TestLineageIndex:
    def test_lineage_index_add_version(self):
        """LineageIndex should add and store versions"""
        lineage = LineageIndex(lineage_hash="lineage1")

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        entry2 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.1",
            parent_hash="hash1",
            content_hash="hash2",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 11, 0),
        )

        lineage.add_version(entry1)
        lineage.add_version(entry2)

        assert len(lineage.versions) == 2

    def test_lineage_index_keeps_sorted(self):
        """LineageIndex should keep versions sorted by timestamp"""
        lineage = LineageIndex(lineage_hash="lineage1")

        # Add out of order
        entry2 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.1",
            parent_hash="hash1",
            content_hash="hash2",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 11, 0),
        )

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        lineage.add_version(entry2)
        lineage.add_version(entry1)

        # Should be sorted
        assert lineage.versions[0].version == "v1.0"
        assert lineage.versions[1].version == "v1.1"

    def test_lineage_index_get_version(self):
        """LineageIndex should get version by name"""
        lineage = LineageIndex(lineage_hash="lineage1")

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        lineage.add_version(entry1)

        result = lineage.get_version("v1.0")
        assert result is not None
        assert result.version == "v1.0"

        result = lineage.get_version("v1.1")
        assert result is None

    def test_lineage_index_get_latest(self):
        """LineageIndex should get latest version"""
        lineage = LineageIndex(lineage_hash="lineage1")

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        entry2 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.1",
            parent_hash="hash1",
            content_hash="hash2",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 11, 0),
        )

        lineage.add_version(entry1)
        lineage.add_version(entry2)

        latest = lineage.get_latest()
        assert latest is not None
        assert latest.version == "v1.1"

    def test_lineage_index_get_chain(self):
        """LineageIndex should get version chain"""
        lineage = LineageIndex(lineage_hash="lineage1")

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        entry2 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.1",
            parent_hash="hash1",
            content_hash="hash2",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 11, 0),
        )

        entry3 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.2",
            parent_hash="hash2",
            content_hash="hash3",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 12, 0),
        )

        lineage.add_version(entry1)
        lineage.add_version(entry2)
        lineage.add_version(entry3)

        # Get full chain
        chain = lineage.get_chain()
        assert len(chain) == 3

        # Get chain from v1.1
        chain = lineage.get_chain(from_version="v1.1")
        assert len(chain) == 2
        assert chain[0].version == "v1.1"
        assert chain[1].version == "v1.2"


class TestUnitIndex:
    def test_unit_index_add_version(self):
        """UnitIndex should add versions"""
        unit = UnitIndex(unit_id="FORM-009")

        entry = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        unit.add_version(entry)

        assert "v1.0" in unit.versions

    def test_unit_index_get_latest(self):
        """UnitIndex should get latest version"""
        unit = UnitIndex(unit_id="FORM-009")

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        entry2 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.1",
            parent_hash="hash1",
            content_hash="hash2",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 11, 0),
        )

        unit.add_version(entry1)
        unit.add_version(entry2)

        latest = unit.get_latest()
        assert latest is not None
        assert latest.version == "v1.1"

    def test_unit_index_get_versions_in_range(self):
        """UnitIndex should get versions in time range"""
        unit = UnitIndex(unit_id="FORM-009")

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        entry2 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.1",
            parent_hash="hash1",
            content_hash="hash2",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 12, 0),
        )

        entry3 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.2",
            parent_hash="hash2",
            content_hash="hash3",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 14, 0),
        )

        unit.add_version(entry1)
        unit.add_version(entry2)
        unit.add_version(entry3)

        # Get versions in range
        start = datetime(2026, 4, 8, 11, 0)
        end = datetime(2026, 4, 8, 13, 0)

        result = unit.get_versions_in_range(start, end)
        assert len(result) == 1
        assert result[0].version == "v1.1"


class TestIndexManager:
    def test_index_manager_initialization(self):
        """IndexManager should initialize empty"""
        manager = IndexManager()

        assert len(manager.by_lineage) == 0
        assert len(manager.by_unit) == 0
        assert len(manager.by_hash) == 0

    def test_index_manager_add_version(self):
        """IndexManager should add version to all indexes"""
        manager = IndexManager()

        entry = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        manager.add_version(entry)

        # Check all indexes
        assert "lineage1" in manager.by_lineage
        assert "FORM-009" in manager.by_unit
        assert "hash1" in manager.by_hash

    def test_index_manager_get_version_by_hash(self):
        """IndexManager should get version by content hash"""
        manager = IndexManager()

        entry = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        manager.add_version(entry)

        result = manager.get_version_by_hash("hash1")
        assert result is not None
        assert result.version == "v1.0"

        result = manager.get_version_by_hash("nonexistent")
        assert result is None

    def test_index_manager_get_lineage_chain(self):
        """IndexManager should get lineage chain"""
        manager = IndexManager()

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        entry2 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.1",
            parent_hash="hash1",
            content_hash="hash2",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 11, 0),
        )

        manager.add_version(entry1)
        manager.add_version(entry2)

        chain = manager.get_lineage_chain("lineage1")
        assert len(chain) == 2

        chain = manager.get_lineage_chain("lineage1", from_version="v1.1")
        assert len(chain) == 1
        assert chain[0].version == "v1.1"

    def test_index_manager_get_unit_chain(self):
        """IndexManager should get unit chain"""
        manager = IndexManager()

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        entry2 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.1",
            parent_hash="hash1",
            content_hash="hash2",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 11, 0),
        )

        manager.add_version(entry1)
        manager.add_version(entry2)

        chain = manager.get_unit_chain("FORM-009")
        assert len(chain) == 2

    def test_index_manager_get_latest_version(self):
        """IndexManager should get latest version"""
        manager = IndexManager()

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        entry2 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.1",
            parent_hash="hash1",
            content_hash="hash2",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 11, 0),
        )

        manager.add_version(entry1)
        manager.add_version(entry2)

        latest = manager.get_latest_version("FORM-009")
        assert latest is not None
        assert latest.version == "v1.1"

    def test_index_manager_get_statistics(self):
        """IndexManager should return statistics"""
        manager = IndexManager()

        entry1 = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        manager.add_version(entry1)

        stats = manager.get_statistics()
        assert stats["total_versions"] == 1
        assert stats["total_lineages"] == 1
        assert stats["total_units"] == 1
        assert stats["avg_versions_per_unit"] == 1.0

    def test_index_manager_clear(self):
        """IndexManager should clear all indexes"""
        manager = IndexManager()

        entry = VersionIndexEntry(
            unit_id="FORM-009",
            version="v1.0",
            parent_hash=None,
            content_hash="hash1",
            lineage_hash="lineage1",
            timestamp=datetime(2026, 4, 8, 10, 0),
        )

        manager.add_version(entry)
        assert manager._total_versions == 1

        manager.clear()
        assert manager._total_versions == 0
        assert len(manager.by_lineage) == 0

    def test_index_manager_rebuild_from_versions(self):
        """IndexManager should rebuild from version list"""
        manager = IndexManager()

        versions = [
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

        count = manager.rebuild_from_versions(versions)
        assert count == 2
        assert manager.get_statistics()["total_versions"] == 2


class TestPerformanceManagerIndexIntegration:
    def test_performance_manager_has_index(self):
        """PerformanceManager should have index"""
        pm = create_performance_manager()

        assert pm.index is not None

    def test_performance_manager_index_version(self):
        """PerformanceManager should index version"""
        pm = create_performance_manager()

        version_dict = {
            "unit_id": "FORM-009",
            "version": "v1.0",
            "parent_hash": None,
            "content_hash": "hash1",
            "lineage_hash": "lineage1",
            "timestamp": "2026-04-08T10:00:00",
            "metadata": {"author": "system"},
        }

        pm.index_version(version_dict)

        stats = pm.get_index_stats()
        assert stats["total_versions"] == 1

    def test_performance_manager_get_version_chain(self):
        """PerformanceManager should get version chain as dicts"""
        pm = create_performance_manager()

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

        chain = pm.get_version_chain("FORM-009")
        assert len(chain) == 2
        assert chain[0]["version"] == "v1.0"
        assert chain[1]["version"] == "v1.1"

    def test_performance_manager_get_latest_version(self):
        """PerformanceManager should get latest version as dict"""
        pm = create_performance_manager()

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

        latest = pm.get_latest_version("FORM-009")
        assert latest is not None
        assert latest["version"] == "v1.1"

    def test_performance_manager_find_version_by_hash(self):
        """PerformanceManager should find version by content hash"""
        pm = create_performance_manager()

        version_dict = {
            "unit_id": "FORM-009",
            "version": "v1.0",
            "parent_hash": None,
            "content_hash": "hash1",
            "lineage_hash": "lineage1",
            "timestamp": "2026-04-08T10:00:00",
            "metadata": {},
        }

        pm.index_version(version_dict)

        result = pm.find_version_by_hash("hash1")
        assert result is not None
        assert result["unit_id"] == "FORM-009"

        result = pm.find_version_by_hash("nonexistent")
        assert result is None

    def test_performance_manager_rebuild_index(self):
        """PerformanceManager should rebuild index"""
        pm = create_performance_manager()

        versions = [
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
                "unit_id": "FORM-010",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash2",
                "lineage_hash": "lineage2",
                "timestamp": "2026-04-08T10:00:00",
                "metadata": {},
            },
        ]

        count = pm.rebuild_index(versions)
        assert count == 2

    def test_performance_manager_get_full_stats(self):
        """PerformanceManager should return full stats"""
        pm = create_performance_manager()

        pm.set_cached_node("FORM-009", "v1.0", {"data": "test"})

        version_dict = {
            "unit_id": "FORM-009",
            "version": "v1.0",
            "parent_hash": None,
            "content_hash": "hash1",
            "lineage_hash": "lineage1",
            "timestamp": "2026-04-08T10:00:00",
            "metadata": {},
        }
        pm.index_version(version_dict)

        stats = pm.get_full_stats()
        assert "cache" in stats
        assert "index" in stats
        assert stats["cache"]["l1_size"] == 1
        assert stats["index"]["total_versions"] == 1


class TestCreateFunctions:
    def test_create_index_manager(self):
        """create_index_manager factory should work"""
        manager = create_index_manager()
        assert manager is not None
