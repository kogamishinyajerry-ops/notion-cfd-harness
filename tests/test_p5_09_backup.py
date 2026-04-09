#!/usr/bin/env python3
"""
P5-09: Backup & Recovery tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.operations.backup import (
    BackupMetadata,
    BackupData,
    BackupManager,
    IncrementalBackupManager,
)
from knowledge_compiler.performance import PerformanceManager


class TestBackupMetadata:
    def test_metadata_creation(self):
        """BackupMetadata should initialize"""
        metadata = BackupMetadata(
            backup_id="backup_123",
            timestamp=time.time(),
            node_count=10,
            version_count=5,
            checksum="abc123",
            is_incremental=False,
        )

        assert metadata.backup_id == "backup_123"
        assert metadata.is_incremental is False

    def test_metadata_to_dict(self):
        """BackupMetadata should convert to dictionary"""
        metadata = BackupMetadata(
            backup_id="backup_123",
            timestamp=time.time(),
            node_count=10,
            version_count=5,
            checksum="abc123",
            is_incremental=False,
        )

        data = metadata.to_dict()

        assert data["backup_id"] == "backup_123"
        assert data["node_count"] == 10
        assert "timestamp_iso" in data


class TestBackupData:
    def test_backup_data_creation(self):
        """BackupData should initialize"""
        metadata = BackupMetadata(
            backup_id="backup_123",
            timestamp=time.time(),
            node_count=0,
            version_count=0,
            checksum="",
            is_incremental=False,
        )

        backup = BackupData(
            metadata=metadata,
            nodes={},
            versions=[],
        )

        assert backup.metadata is metadata
        assert len(backup.nodes) == 0
        assert len(backup.versions) == 0

    def test_backup_data_calculate_checksum(self):
        """BackupData should calculate checksum"""
        metadata = BackupMetadata(
            backup_id="backup_123",
            timestamp=time.time(),
            node_count=0,
            version_count=0,
            checksum="",
            is_incremental=False,
        )

        backup = BackupData(
            metadata=metadata,
            nodes={"key": "value"},
            versions=[],
        )

        checksum = backup.calculate_checksum()

        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 hex length


class TestBackupManager:
    def test_backup_manager_creation(self):
        """BackupManager should initialize"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            assert bm.pm is pm
            assert bm.backup_dir == Path(tmpdir)

    def test_create_backup_empty(self):
        """BackupManager should create backup of empty state"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            backup = bm.create_backup()

            assert backup.metadata.node_count == 0
            assert backup.metadata.version_count == 0
            assert backup.metadata.is_incremental is False
            assert backup.metadata.backup_id is not None

    def test_create_backup_with_data(self):
        """BackupManager should create backup with data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()

            # Add some data
            pm.index_version({
                "unit_id": "FORM-009",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash1",
                "lineage_hash": "lineage1",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {},
            })

            pm.cache.l1._cache["FORM-009:v1.0"] = {"data": "test"}

            bm = BackupManager(pm, backup_dir=tmpdir)
            backup = bm.create_backup()

            assert backup.metadata.node_count >= 1
            assert backup.metadata.version_count >= 1

    def test_save_and_load_backup(self):
        """BackupManager should save and load backup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            backup = bm.create_backup()
            file_path = bm.save_backup(backup)

            assert file_path.exists()

            loaded = bm.load_backup(file_path)

            assert loaded.metadata.backup_id == backup.metadata.backup_id
            assert loaded.metadata.checksum == backup.metadata.checksum

    def test_verify_backup(self):
        """BackupManager should verify backup checksum"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            backup = bm.create_backup()

            assert bm.verify_backup(backup) is True

            # Tamper with checksum
            original_checksum = backup.metadata.checksum
            backup.metadata.checksum = "wrong"

            assert bm.verify_backup(backup) is False

            backup.metadata.checksum = original_checksum

    def test_restore_backup(self):
        """BackupManager should restore backup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            # Create original data
            pm.index_version({
                "unit_id": "FORM-009",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash1",
                "lineage_hash": "lineage1",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {},
            })

            # Create backup
            backup = bm.create_backup()

            # Clear PM
            pm2 = PerformanceManager()
            bm2 = BackupManager(pm2, backup_dir=tmpdir)

            # Restore
            stats = bm2.restore_backup(backup)

            assert stats["versions_restored"] == 1

            # Verify restored
            chain = pm2.index.get_unit_chain("FORM-009")
            assert len(chain) == 1

    def test_restore_backup_clear_existing(self):
        """BackupManager should clear existing data on restore"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            # Create initial backup (empty)
            backup = bm.create_backup(backup_id="initial")

            # Add data to PM (not in backup)
            pm.index_version({
                "unit_id": "FORM-OLD",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "old_hash",
                "lineage_hash": "old_lineage",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {},
            })

            # Restore with clear (should remove FORM-OLD, keep empty backup data)
            stats = bm.restore_backup(backup, clear_existing=True)

            # Should only have backed up versions (none)
            versions = list(pm.index.by_unit.keys())
            assert "FORM-OLD" not in versions

    def test_list_backups(self):
        """BackupManager should list backups"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            # Create multiple backups
            backup1 = bm.create_backup(backup_id="backup1")
            bm.save_backup(backup1)
            backup2 = bm.create_backup(backup_id="backup2")
            bm.save_backup(backup2)

            backups = bm.list_backups()

            assert len(backups) == 2
            assert any(b["backup_id"] == "backup1" for b in backups)
            assert any(b["backup_id"] == "backup2" for b in backups)

    def test_delete_backup(self):
        """BackupManager should delete backup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            backup = bm.create_backup(backup_id="to_delete")
            file_path = bm.save_backup(backup)

            assert file_path.exists()

            result = bm.delete_backup("to_delete")

            assert result is True
            assert not file_path.exists()

    def test_delete_nonexistent_backup(self):
        """BackupManager should return False for nonexistent backup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            result = bm.delete_backup("nonexistent")

            assert result is False

    def test_export_version_history(self):
        """BackupManager should export version history"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()

            pm.index_version({
                "unit_id": "FORM-009",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash1",
                "lineage_hash": "lineage1",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {},
            })

            bm = BackupManager(pm, backup_dir=tmpdir)
            output_file = Path(tmpdir) / "export.json"

            count = bm.export_version_history(output_file)

            assert count == 1
            assert output_file.exists()

            data = json.loads(output_file.read_text())
            assert data["count"] == 1
            assert len(data["versions"]) == 1

    def test_export_version_history_unit_filter(self):
        """BackupManager should export version history for specific unit"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()

            pm.index_version({
                "unit_id": "FORM-009",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash1",
                "lineage_hash": "lineage1",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {},
            })

            pm.index_version({
                "unit_id": "FORM-010",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash2",
                "lineage_hash": "lineage2",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {},
            })

            bm = BackupManager(pm, backup_dir=tmpdir)
            output_file = Path(tmpdir) / "export.json"

            count = bm.export_version_history(output_file, unit_id="FORM-009")

            assert count == 1

            data = json.loads(output_file.read_text())
            assert data["unit_id"] == "FORM-009"
            assert data["count"] == 1

    def test_create_checkpoint(self):
        """BackupManager should create named checkpoint"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            backup_id = bm.create_checkpoint("my_checkpoint")

            assert backup_id == "my_checkpoint"

            # Verify file exists
            file_path = bm.backup_dir / "my_checkpoint.json"
            assert file_path.exists()

    def test_create_checkpoint_auto_name(self):
        """BackupManager should auto-generate checkpoint name"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            backup_id = bm.create_checkpoint()

            assert backup_id.startswith("checkpoint_")

            # Verify file exists
            file_path = bm.backup_dir / f"{backup_id}.json"
            assert file_path.exists()

    def test_restore_checkpoint(self):
        """BackupManager should restore from checkpoint"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm1 = PerformanceManager()

            pm1.index_version({
                "unit_id": "FORM-009",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash1",
                "lineage_hash": "lineage1",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {},
            })

            bm1 = BackupManager(pm1, backup_dir=tmpdir)
            backup_id = bm1.create_checkpoint("test_checkpoint")

            # Create new PM and restore
            pm2 = PerformanceManager()
            bm2 = BackupManager(pm2, backup_dir=tmpdir)

            stats = bm2.restore_checkpoint("test_checkpoint")

            assert stats["versions_restored"] == 1

            # Verify data restored
            chain = pm2.index.get_unit_chain("FORM-009")
            assert len(chain) == 1

    def test_restore_checkpoint_invalid_checksum(self):
        """BackupManager should reject checkpoint with invalid checksum"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = BackupManager(pm, backup_dir=tmpdir)

            backup = bm.create_checkpoint("bad_checkpoint")

            # Tamper with backup file
            file_path = bm.backup_dir / "bad_checkpoint.json"
            data = json.loads(file_path.read_text())
            data["metadata"]["checksum"] = "tampered"
            file_path.write_text(json.dumps(data))

            # Should raise error
            try:
                bm.restore_checkpoint("bad_checkpoint")
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "checksum" in str(e).lower()


class TestIncrementalBackupManager:
    def test_incremental_backup_creation(self):
        """IncrementalBackupManager should create incremental backup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = IncrementalBackupManager(pm, backup_dir=tmpdir)

            backup = bm.create_incremental_backup()

            assert backup.metadata.is_incremental is True
            assert backup.metadata.parent_backup_id is None  # First backup

    def test_incremental_backup_tracks_changes(self):
        """IncrementalBackupManager should track changes between backups"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PerformanceManager()
            bm = IncrementalBackupManager(pm, backup_dir=tmpdir)

            # First backup (empty)
            backup1 = bm.create_incremental_backup()
            assert backup1.metadata.version_count == 0

            # Add data
            pm.index_version({
                "unit_id": "FORM-009",
                "version": "v1.0",
                "parent_hash": None,
                "content_hash": "hash1",
                "lineage_hash": "lineage1",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {},
            })

            # Second incremental backup
            backup2 = bm.create_incremental_backup()

            assert backup2.metadata.version_count == 1  # Only the new version
            assert backup2.metadata.parent_backup_id == backup1.metadata.backup_id


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
