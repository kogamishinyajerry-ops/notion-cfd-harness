#!/usr/bin/env python3
"""
P5-09: Backup & Recovery - State persistence and restoration

Provides:
- Memory Network state backup
- Version history export
- Incremental backups
- Backup verification and restoration
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import shutil

from knowledge_compiler.performance import PerformanceManager


# ============================================================================
# Backup Metadata
# ============================================================================

@dataclass
class BackupMetadata:
    """Metadata about a backup"""
    backup_id: str
    timestamp: float
    node_count: int
    version_count: int
    checksum: str
    is_incremental: bool
    parent_backup_id: Optional[str] = None
    compression: str = "none"
    format_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "backup_id": self.backup_id,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.utcfromtimestamp(self.timestamp).isoformat() + "Z",
            "node_count": self.node_count,
            "version_count": self.version_count,
            "checksum": self.checksum,
            "is_incremental": self.is_incremental,
            "parent_backup_id": self.parent_backup_id,
            "compression": self.compression,
            "format_version": self.format_version,
        }


# ============================================================================
# Backup Data
# ============================================================================

@dataclass
class BackupData:
    """Backup data containing nodes and versions"""
    metadata: BackupMetadata
    nodes: Dict[str, Dict[str, Any]]  # unit_id:version -> node data
    versions: List[Dict[str, Any]]  # Version index entries

    def calculate_checksum(self) -> str:
        """Calculate checksum of backup data"""
        # Create a deterministic string representation
        data_str = json.dumps({
            "nodes": sorted(self.nodes.items()),
            "versions": sorted(
                self.versions,
                key=lambda v: (v.get("unit_id"), v.get("version", "")),
            ),
        }, sort_keys=True, default=str)

        return hashlib.sha256(data_str.encode()).hexdigest()


# ============================================================================
# Backup Manager
# ============================================================================

class BackupManager:
    """
    Backup and restore Memory Network state

    Features:
    - Full and incremental backups
    - JSON format export
    - Checksum verification
    - Backup restoration
    """

    def __init__(
        self,
        performance_manager: PerformanceManager | None = None,
        backup_dir: Path | str | None = None,
    ):
        """
        Initialize backup manager

        Args:
            performance_manager: PerformanceManager instance
            backup_dir: Directory to store backups
        """
        self.pm = performance_manager or PerformanceManager()
        self.backup_dir = Path(backup_dir) if backup_dir else Path("./backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create_backup(
        self,
        backup_id: Optional[str] = None,
        incremental: bool = False,
        parent_backup_id: Optional[str] = None,
    ) -> BackupData:
        """
        Create a backup of current state

        Args:
            backup_id: Custom backup ID (auto-generated if None)
            incremental: Create incremental backup
            parent_backup_id: Parent backup for incremental

        Returns:
            BackupData instance
        """
        import uuid

        backup_id = backup_id or f"backup_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        # Collect data from PerformanceManager
        nodes = {}
        versions = []

        # Get version index
        for unit_id, unit_idx in self.pm.index.by_unit.items():
            for entry in unit_idx.versions.values():
                versions.append({
                    "unit_id": entry.unit_id,
                    "version": entry.version,
                    "parent_hash": entry.parent_hash,
                    "content_hash": entry.content_hash,
                    "lineage_hash": entry.lineage_hash,
                    "timestamp": entry.timestamp.isoformat(),
                    "metadata": entry.metadata,
                })

        # Get cached nodes
        l1_cache = self.pm.cache.l1._cache
        for key, node in l1_cache.items():
            # Handle both TTLCache (dict directly) and fallback (tuple with expiry)
            if isinstance(node, tuple):
                node = node[0]  # Extract value from (value, expiry) tuple
            nodes[key] = node

        # Create metadata
        metadata = BackupMetadata(
            backup_id=backup_id,
            timestamp=time.time(),
            node_count=len(nodes),
            version_count=len(versions),
            checksum="",  # Will be calculated
            is_incremental=incremental,
            parent_backup_id=parent_backup_id,
        )

        backup = BackupData(
            metadata=metadata,
            nodes=nodes,
            versions=versions,
        )

        # Calculate checksum
        metadata.checksum = backup.calculate_checksum()

        return backup

    def save_backup(
        self,
        backup: BackupData,
        file_path: Path | str | None = None,
    ) -> Path:
        """
        Save backup to file

        Args:
            backup: Backup data to save
            file_path: Output file path (default: backup_dir/{backup_id}.json)

        Returns:
            Path to saved file
        """
        if file_path is None:
            file_path = self.backup_dir / f"{backup.metadata.backup_id}.json"
        else:
            file_path = Path(file_path)

        # Prepare data
        data = {
            "metadata": backup.metadata.to_dict(),
            "nodes": backup.nodes,
            "versions": backup.versions,
        }

        # Write to file
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )

        return file_path

    def load_backup(
        self,
        file_path: Path | str,
    ) -> BackupData:
        """
        Load backup from file

        Args:
            file_path: Path to backup file

        Returns:
            BackupData instance
        """
        file_path = Path(file_path)

        data = json.loads(file_path.read_text(encoding="utf-8"))

        # Reconstruct metadata
        meta_dict = data["metadata"]
        metadata = BackupMetadata(
            backup_id=meta_dict["backup_id"],
            timestamp=meta_dict["timestamp"],
            node_count=meta_dict["node_count"],
            version_count=meta_dict["version_count"],
            checksum=meta_dict["checksum"],
            is_incremental=meta_dict["is_incremental"],
            parent_backup_id=meta_dict.get("parent_backup_id"),
            compression=meta_dict.get("compression", "none"),
            format_version=meta_dict.get("format_version", "1.0"),
        )

        return BackupData(
            metadata=metadata,
            nodes=data["nodes"],
            versions=data["versions"],
        )

    def verify_backup(
        self,
        backup: BackupData,
    ) -> bool:
        """
        Verify backup checksum

        Args:
            backup: Backup to verify

        Returns:
            True if checksum matches
        """
        calculated = backup.calculate_checksum()
        return calculated == backup.metadata.checksum

    def restore_backup(
        self,
        backup: BackupData,
        clear_existing: bool = False,
    ) -> Dict[str, int]:
        """
        Restore backup to PerformanceManager

        Args:
            backup: Backup data to restore
            clear_existing: Clear existing data before restore

        Returns:
            Dict with restore statistics
        """
        if clear_existing:
            # Clear cache and index
            self.pm.cache.l1._cache.clear()
            self.pm.index.by_unit.clear()
            self.pm.index.by_lineage.clear()
            self.pm.index.by_hash.clear()

        # Restore versions
        for v in backup.versions:
            self.pm.index_version(v)

        # Restore nodes to cache
        for key, node in backup.nodes.items():
            self.pm.cache.l1._cache[key] = node

        return {
            "nodes_restored": len(backup.nodes),
            "versions_restored": len(backup.versions),
        }

    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all backups in backup directory

        Returns:
            List of backup metadata
        """
        backups = []

        for file_path in self.backup_dir.glob("*.json"):
            try:
                backup = self.load_backup(file_path)
                backups.append({
                    "backup_id": backup.metadata.backup_id,
                    "file": str(file_path),
                    "timestamp": backup.metadata.timestamp,
                    "node_count": backup.metadata.node_count,
                    "version_count": backup.metadata.version_count,
                    "is_incremental": backup.metadata.is_incremental,
                })
            except Exception:
                # Skip invalid backup files
                continue

        # Sort by timestamp (newest first)
        backups.sort(key=lambda b: b["timestamp"], reverse=True)

        return backups

    def delete_backup(
        self,
        backup_id: str,
    ) -> bool:
        """
        Delete a backup file

        Args:
            backup_id: ID of backup to delete

        Returns:
            True if deleted, False if not found
        """
        file_path = self.backup_dir / f"{backup_id}.json"

        if file_path.exists():
            file_path.unlink()
            return True

        return False

    def export_version_history(
        self,
        file_path: Path | str,
        unit_id: Optional[str] = None,
    ) -> int:
        """
        Export version history to JSON

        Args:
            file_path: Output file path
            unit_id: Filter by unit ID (None for all)

        Returns:
            Number of versions exported
        """
        versions = []

        if unit_id:
            # Export single unit
            unit_idx = self.pm.index.by_unit.get(unit_id)
            if unit_idx:
                versions = [self._version_entry_to_dict(v) for v in unit_idx.versions.values()]
        else:
            # Export all units
            for unit_idx in self.pm.index.by_unit.values():
                for v in unit_idx.versions.values():
                    versions.append(self._version_entry_to_dict(v))

        data = {
            "export_time": datetime.utcnow().isoformat() + "Z",
            "unit_id": unit_id,
            "count": len(versions),
            "versions": versions,
        }

        Path(file_path).write_text(
            json.dumps(data, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )

        return len(versions)

    def _version_entry_to_dict(self, entry) -> Dict[str, Any]:
        """Convert version index entry to dictionary"""
        return {
            "unit_id": entry.unit_id,
            "version": entry.version,
            "parent_hash": entry.parent_hash,
            "content_hash": entry.content_hash,
            "lineage_hash": entry.lineage_hash,
            "timestamp": entry.timestamp.isoformat() if isinstance(entry.timestamp, datetime) else entry.timestamp,
            "metadata": entry.metadata,
        }

    def create_checkpoint(self, name: Optional[str] = None) -> str:
        """
        Create a named checkpoint (full backup)

        Args:
            name: Checkpoint name

        Returns:
            Backup ID
        """
        import uuid
        backup_id = name or f"checkpoint_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        backup = self.create_backup(
            backup_id=backup_id,
            incremental=False,
        )

        self.save_backup(backup)

        return backup_id

    def restore_checkpoint(
        self,
        backup_id: str,
    ) -> Dict[str, int]:
        """
        Restore from a checkpoint

        Args:
            backup_id: Backup ID to restore

        Returns:
            Restore statistics
        """
        file_path = self.backup_dir / f"{backup_id}.json"

        if not file_path.exists():
            raise ValueError(f"Backup not found: {backup_id}")

        backup = self.load_backup(file_path)

        if not self.verify_backup(backup):
            raise ValueError(f"Backup checksum mismatch: {backup_id}")

        return self.restore_backup(backup, clear_existing=True)


# ============================================================================
# Incremental Backup Support
# ============================================================================

class IncrementalBackupManager(BackupManager):
    """
    Extended backup manager with incremental backup support

    Tracks changes since last backup to create smaller incremental backups.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_backup_state: Dict[str, str] = {}  # unit_id:version -> checksum
        self._last_backup_id: Optional[str] = None

    def create_incremental_backup(
        self,
        backup_id: Optional[str] = None,
    ) -> BackupData:
        """
        Create an incremental backup (only changed data since last backup)

        Args:
            backup_id: Custom backup ID

        Returns:
            BackupData instance
        """
        # Find changed versions
        changed_versions = []
        current_state = {}

        for unit_id, unit_idx in self.pm.index.by_unit.items():
            for entry in unit_idx.versions.values():
                key = f"{entry.unit_id}:{entry.version}"
                state_key = f"{entry.unit_id}:{entry.content_hash}"

                current_state[state_key] = entry.content_hash

                # Check if changed (new or different hash)
                if key not in self._last_backup_state or self._last_backup_state.get(key) != entry.content_hash:
                    changed_versions.append(entry)

        # Create backup with only changed versions
        import uuid
        backup_id = backup_id or f"incremental_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        backup = BackupData(
            metadata=BackupMetadata(
                backup_id=backup_id,
                timestamp=time.time(),
                node_count=0,  # Incremental doesn't include full node cache
                version_count=len(changed_versions),
                checksum="",
                is_incremental=True,
                parent_backup_id=self._last_backup_id,
            ),
            nodes={},  # Incremental doesn't include full cache
            versions=[
                {
                    "unit_id": v.unit_id,
                    "version": v.version,
                    "parent_hash": v.parent_hash,
                    "content_hash": v.content_hash,
                    "lineage_hash": v.lineage_hash,
                    "timestamp": v.timestamp.isoformat(),
                    "metadata": v.metadata,
                }
                for v in changed_versions
            ],
        )

        backup.metadata.checksum = backup.calculate_checksum()

        # Update state
        self._last_backup_state = current_state
        self._last_backup_id = backup_id

        return backup


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "BackupMetadata",
    "BackupData",
    "BackupManager",
    "IncrementalBackupManager",
]
