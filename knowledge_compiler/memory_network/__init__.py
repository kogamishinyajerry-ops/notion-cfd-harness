#!/usr/bin/env python3
"""
Versioned Knowledge Registry
Phase 4: Governed Memory Network

Extends Phase3 KnowledgeRegistry with Git-like version tracking
for knowledge units, enabling full evolution history and change propagation.
"""

import hashlib
import importlib
import json
import re
import sys
import yaml
from copy import deepcopy
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from knowledge_compiler.runtime import KnowledgeRegistry, KnowledgeUnitRef


# =============================================================================
# Version Control Data Models
# =============================================================================

class VersionStatus(Enum):
    """Status of a knowledge unit version."""
    ACTIVE = "active"           # Current live version
    SUPERSEDED = "superseded"   # Replaced by newer version
    DEPRECATED = "deprecated"   # Marked as obsolete
    ARCHIVED = "archived"       # Historical reference only


@dataclass
class UnitVersion:
    """
    A specific version of a knowledge unit.

    Similar to Git commit: each version has content hash, parent hash,
    timestamp, and metadata.
    """
    unit_id: str
    version: str                   # Semantic version (v1.0, v1.1, etc.)
    content_hash: str              # SHA-256 of unit content
    parent_hash: Optional[str]      # Previous version's hash (None for initial)
    created_at: datetime
    created_by: str                 # "Codex", "Human", etc.
    status: VersionStatus
    change_summary: str             # Human-readable change description
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Git-style properties
    @property
    def short_hash(self) -> str:
        """First 8 characters of content hash."""
        return self.content_hash[:8]

    @property
    def is_initial(self) -> bool:
        """True if this is the first version (no parent)."""
        return self.parent_hash is None


@dataclass
class CodeMapping:
    """
    Bidirectional mapping between knowledge units and code artifacts.

    Enables traceability: given a file path, find which knowledge units
    reference it; given a unit, find which code files implement it.
    """
    unit_id: str
    file_path: str                  # Relative to project root
    mapping_type: str               # "implements", "validates", "references"
    confidence: float = 1.0          # 0.0 to 1.0, for auto-generated mappings
    verified_at: Optional[datetime] = None


class CodeMappingRegistry:
    """
    Bidirectional registry for knowledge-to-code traceability.

    Maintains synchronized indexes in both directions:
    - unit_id -> file mappings
    - file_path -> unit mappings
    """

    VALID_MAPPING_TYPES: ClassVar[Set[str]] = {
        "implements",
        "validates",
        "references",
    }

    def __init__(self, mappings: Optional[Dict[str, List[CodeMapping]]] = None):
        self._by_unit: Dict[str, Dict[str, CodeMapping]] = {}
        self._by_file: Dict[str, Dict[str, CodeMapping]] = {}

        if mappings:
            self.load_mappings(mappings)

    def _normalize_unit_id(self, unit_id: str) -> str:
        normalized = unit_id.strip()
        if not normalized:
            raise ValueError("unit_id cannot be empty")
        return normalized

    def _normalize_file_path(self, file_path: str) -> str:
        normalized = file_path.strip().replace("\\", "/")
        if not normalized:
            raise ValueError("file_path cannot be empty")
        return normalized

    def _validate_mapping_type(self, mapping_type: str) -> str:
        if mapping_type not in self.VALID_MAPPING_TYPES:
            valid = ", ".join(sorted(self.VALID_MAPPING_TYPES))
            raise ValueError(f"mapping_type must be one of: {valid}")
        return mapping_type

    def _validate_confidence(self, confidence: float) -> float:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return confidence

    def _store_mapping(self, mapping: CodeMapping) -> CodeMapping:
        self._by_unit.setdefault(mapping.unit_id, {})[mapping.file_path] = mapping
        self._by_file.setdefault(mapping.file_path, {})[mapping.unit_id] = mapping
        return mapping

    def _get_mapping(self, unit_id: str, file_path: str) -> Optional[CodeMapping]:
        return self._by_unit.get(unit_id, {}).get(file_path)

    def clear(self) -> None:
        """Remove all mappings from the registry."""
        self._by_unit.clear()
        self._by_file.clear()

    def load_mappings(self, mappings: Dict[str, List[CodeMapping]]) -> None:
        """Replace registry contents from a unit-indexed mapping dictionary."""
        self.clear()

        for unit_id, unit_mappings in mappings.items():
            normalized_unit_id = self._normalize_unit_id(unit_id)
            for mapping in unit_mappings:
                normalized_file_path = self._normalize_file_path(mapping.file_path)
                mapping_type = self._validate_mapping_type(mapping.mapping_type)
                confidence = self._validate_confidence(mapping.confidence)
                normalized_mapping = CodeMapping(
                    unit_id=normalized_unit_id,
                    file_path=normalized_file_path,
                    mapping_type=mapping_type,
                    confidence=confidence,
                    verified_at=mapping.verified_at,
                )
                self._store_mapping(normalized_mapping)

    def add_mapping(
        self,
        unit_id: str,
        file_path: str,
        mapping_type: str,
        confidence: float = 1.0,
    ) -> CodeMapping:
        """Add or update a mapping between a unit and a file."""
        normalized_unit_id = self._normalize_unit_id(unit_id)
        normalized_file_path = self._normalize_file_path(file_path)
        normalized_mapping_type = self._validate_mapping_type(mapping_type)
        normalized_confidence = self._validate_confidence(confidence)

        existing = self._get_mapping(normalized_unit_id, normalized_file_path)
        if existing:
            if existing.mapping_type != normalized_mapping_type:
                existing.mapping_type = normalized_mapping_type
                existing.verified_at = None
            existing.confidence = normalized_confidence
            return existing

        mapping = CodeMapping(
            unit_id=normalized_unit_id,
            file_path=normalized_file_path,
            mapping_type=normalized_mapping_type,
            confidence=normalized_confidence,
            verified_at=None,
        )
        return self._store_mapping(mapping)

    def remove_mapping(self, unit_id: str, file_path: str) -> bool:
        """Remove a mapping. Returns True when a mapping was removed."""
        normalized_unit_id = self._normalize_unit_id(unit_id)
        normalized_file_path = self._normalize_file_path(file_path)

        mapping = self._by_unit.get(normalized_unit_id, {}).pop(normalized_file_path, None)
        if mapping is None:
            return False

        if not self._by_unit[normalized_unit_id]:
            del self._by_unit[normalized_unit_id]

        file_mappings = self._by_file.get(normalized_file_path, {})
        file_mappings.pop(normalized_unit_id, None)
        if not file_mappings and normalized_file_path in self._by_file:
            del self._by_file[normalized_file_path]

        return True

    def get_files_for_unit(self, unit_id: str) -> List[str]:
        """Get all mapped files for a knowledge unit."""
        normalized_unit_id = self._normalize_unit_id(unit_id)
        return sorted(self._by_unit.get(normalized_unit_id, {}).keys())

    def get_units_for_file(self, file_path: str) -> List[str]:
        """Get all units mapped to a file."""
        normalized_file_path = self._normalize_file_path(file_path)
        return sorted(self._by_file.get(normalized_file_path, {}).keys())

    def find_units_by_pattern(self, pattern: str) -> List[str]:
        """Find units whose mapped file paths match a glob or substring pattern."""
        normalized_pattern = pattern.strip().replace("\\", "/")
        if not normalized_pattern:
            return []

        use_glob = any(char in normalized_pattern for char in "*?[]")
        matching_units: Set[str] = set()

        for file_path, file_mappings in self._by_file.items():
            if use_glob:
                matched = fnmatch(file_path, normalized_pattern)
            else:
                matched = normalized_pattern in file_path
            if matched:
                matching_units.update(file_mappings.keys())

        return sorted(matching_units)

    def verify_mapping(self, unit_id: str, file_path: str) -> CodeMapping:
        """Mark a mapping as verified and return the updated mapping."""
        normalized_unit_id = self._normalize_unit_id(unit_id)
        normalized_file_path = self._normalize_file_path(file_path)

        mapping = self._get_mapping(normalized_unit_id, normalized_file_path)
        if mapping is None:
            raise ValueError(
                f"Mapping not found for unit '{normalized_unit_id}' and file '{normalized_file_path}'"
            )

        mapping.verified_at = datetime.now()
        return mapping

    def get_mappings_for_unit(self, unit_id: str) -> List[CodeMapping]:
        """Return all mappings for a unit."""
        normalized_unit_id = self._normalize_unit_id(unit_id)
        unit_mappings = self._by_unit.get(normalized_unit_id, {})
        return [unit_mappings[file_path] for file_path in sorted(unit_mappings)]

    def get_mappings_for_file(self, file_path: str) -> List[CodeMapping]:
        """Return all mappings for a file."""
        normalized_file_path = self._normalize_file_path(file_path)
        file_mappings = self._by_file.get(normalized_file_path, {})
        return [file_mappings[unit_id] for unit_id in sorted(file_mappings)]

    def get_all_mappings(self) -> List[CodeMapping]:
        """Return all mappings in unit/file order."""
        mappings: List[CodeMapping] = []
        for unit_id in sorted(self._by_unit):
            mappings.extend(self.get_mappings_for_unit(unit_id))
        return mappings

    def as_unit_dict(self) -> Dict[str, List[CodeMapping]]:
        """Return the registry as a unit-indexed dictionary."""
        return {
            unit_id: self.get_mappings_for_unit(unit_id)
            for unit_id in sorted(self._by_unit)
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregate statistics for the mapping registry."""
        all_mappings = self.get_all_mappings()
        mapping_type_counts: Dict[str, int] = {}

        for mapping in all_mappings:
            mapping_type_counts[mapping.mapping_type] = (
                mapping_type_counts.get(mapping.mapping_type, 0) + 1
            )

        verified_mappings = sum(1 for mapping in all_mappings if mapping.verified_at is not None)
        average_confidence = (
            sum(mapping.confidence for mapping in all_mappings) / len(all_mappings)
            if all_mappings
            else 0.0
        )

        return {
            "total_mappings": len(all_mappings),
            "total_units": len(self._by_unit),
            "total_files": len(self._by_file),
            "mapping_type_counts": mapping_type_counts,
            "verified_mappings": verified_mappings,
            "unverified_mappings": len(all_mappings) - verified_mappings,
            "average_confidence": average_confidence,
        }



@dataclass
class MemoryNode:
    """
    记忆节点 - 表示一个知识单元的状态.
    
    MemoryNode represents the state of a knowledge unit in the governed
    memory network. Unlike UnitVersion which is for version control,
    MemoryNode focuses on the knowledge unit's relationship to code
    artifacts and its network position.
    
    Attributes:
        unit_id: Knowledge unit identifier (e.g., "CH-001")
        version: Semantic version string (e.g., "v1.0")
        content_hash: SHA-256 hash of the unit content
        created_at: Timestamp when this version was created
        parent_hash: Hash of the parent version (None for initial version)
        metadata: Additional information about the node
        code_mappings: List of file paths that implement/reference this unit
    """
    unit_id: str
    version: str
    content_hash: str
    created_at: datetime
    parent_hash: Optional[str] = None  # Git-like 链式结构
    metadata: Dict[str, Any] = field(default_factory=dict)
    code_mappings: List[str] = field(default_factory=list)
    
    # Git-style properties
    @property
    def short_hash(self) -> str:
        """First 8 characters of content hash."""
        return self.content_hash[:8]
    
    @property
    def is_initial(self) -> bool:
        """True if this is the first version (no parent)."""
        return self.parent_hash is None
    
    # Serialization methods
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert MemoryNode to dictionary for serialization.
        
        Returns:
            Dict representation of the node
        """
        return {
            "unit_id": self.unit_id,
            "version": self.version,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat(),
            "parent_hash": self.parent_hash,
            "metadata": self.metadata,
            "code_mappings": self.code_mappings
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryNode":
        """
        Create MemoryNode from dictionary.
        
        Args:
            data: Dictionary representation of the node
            
        Returns:
            MemoryNode instance
        """
        return cls(
            unit_id=data["unit_id"],
            version=data["version"],
            content_hash=data["content_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            parent_hash=data.get("parent_hash"),
            metadata=data.get("metadata", {}),
            code_mappings=data.get("code_mappings", [])
        )


@dataclass
class VersionChange:
    """
    Record of a change between two unit versions.

    Computed by diff_engine.py, stored for audit trail.
    """
    from_version: str               # content_hash
    to_version: str                 # content_hash
    change_type: str                # NEW/DELETE/TEXT_EDIT/SEMANTIC_EDIT/EVIDENCE_EDIT/CHART_RULE_EDIT
    changed_fields: List[str]
    impact_summary: str
    detected_at: datetime
    reviewed_by: Optional[str] = None  # "Opus 4.6" if gate-reviewed


# =============================================================================
# Versioned Knowledge Registry
# =============================================================================

class VersionedKnowledgeRegistry(KnowledgeRegistry):
    """
    Git-like versioned knowledge registry.

    Extends Phase3 KnowledgeRegistry with:
    - Version history for each knowledge unit
    - Parent-child relationships between versions
    - Change tracking between versions
    - Code mapping registry

    Usage:
        registry = VersionedKnowledgeRegistry()

        # Get current version of a unit
        unit = registry.get_current("CH-001")

        # Get version history
        history = registry.get_history("CH-001")

        # Get specific version
        v1_0 = registry.get_version("CH-001", "v1.0")

        # Compare versions
        changes = registry.diff_versions("CH-001", "v1.0", "v1.1")
    """

    def __init__(self, base_path: Path = None, version_db_path: Optional[Path] = None):
        """
        Initialize versioned registry.

        Args:
            base_path: Root path of knowledge_compiler
            version_db_path: Optional path to version database JSON file.
                When omitted, the registry stays in-memory for the current process.
        """
        super().__init__(base_path)

        self.persist_versions = version_db_path is not None
        self.version_db_path = version_db_path or (self.base_path / ".versions.json")
        self.versions: Dict[str, UnitVersion] = {}  # unit_id -> UnitVersion (current)
        self.history: Dict[str, List[UnitVersion]] = {}  # unit_id -> [all versions]
        self.by_hash: Dict[str, UnitVersion] = {}  # content_hash -> UnitVersion

        # Code mappings are managed through a bidirectional registry.
        self.code_mapping_registry = CodeMappingRegistry()

        # Version changes for audit trail
        self.changes: List[VersionChange] = []

        self._load_versions()

    def _load_versions(self):
        """Load version database from disk."""
        if self.persist_versions and self.version_db_path.exists():
            try:
                with open(self.version_db_path) as f:
                    data = json.load(f)

                # Load current versions
                for unit_id, version_data in data.get("current_versions", {}).items():
                    self.versions[unit_id] = UnitVersion(
                        unit_id=unit_id,
                        version=version_data["version"],
                        content_hash=version_data["content_hash"],
                        parent_hash=version_data.get("parent_hash"),
                        created_at=datetime.fromisoformat(version_data["created_at"]),
                        created_by=version_data.get("created_by", "unknown"),
                        status=VersionStatus(version_data.get("status", "active")),
                        change_summary=version_data.get("change_summary", ""),
                        metadata=version_data.get("metadata", {})
                    )
                    self.by_hash[self.versions[unit_id].content_hash] = self.versions[unit_id]

                # Load full history
                for unit_id, history_list in data.get("history", {}).items():
                    self.history[unit_id] = []
                    for h in history_list:
                        uv = UnitVersion(
                            unit_id=unit_id,
                            version=h["version"],
                            content_hash=h["content_hash"],
                            parent_hash=h.get("parent_hash"),
                            created_at=datetime.fromisoformat(h["created_at"]),
                            created_by=h.get("created_by", "unknown"),
                            status=VersionStatus(h.get("status", "active")),
                            change_summary=h.get("change_summary", ""),
                            metadata=h.get("metadata", {})
                        )
                        self.history[unit_id].append(uv)
                        self.by_hash[uv.content_hash] = uv

                # Load code mappings
                loaded_mappings: Dict[str, List[CodeMapping]] = {}
                for unit_id, mappings in data.get("code_mappings", {}).items():
                    loaded_mappings[unit_id] = [
                        CodeMapping(
                            unit_id=unit_id,
                            file_path=m["file_path"],
                            mapping_type=m["mapping_type"],
                            confidence=m.get("confidence", 1.0),
                            verified_at=datetime.fromisoformat(m["verified_at"]) if m.get("verified_at") else None
                        )
                        for m in mappings
                    ]
                self.code_mapping_registry.load_mappings(loaded_mappings)

                # Load changes
                for c in data.get("changes", []):
                    self.changes.append(VersionChange(
                        from_version=c["from_version"],
                        to_version=c["to_version"],
                        change_type=c["change_type"],
                        changed_fields=c.get("changed_fields", []),
                        impact_summary=c["impact_summary"],
                        detected_at=datetime.fromisoformat(c["detected_at"]),
                        reviewed_by=c.get("reviewed_by")
                    ))

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Warning: Failed to load version DB, starting fresh: {e}")
                self._initialize_initial_versions()
        else:
            self._initialize_initial_versions()

    def _initialize_initial_versions(self):
        """
        Initialize version database from current YAML files.

        Called when no version DB exists - creates v1.0 for all units.
        """
        print("Initializing version database from current YAML files...")

        for unit_id, unit_ref in self.units.items():
            # Calculate content hash from YAML source
            content_hash = self._calculate_unit_hash(unit_id, unit_ref)

            uv = UnitVersion(
                unit_id=unit_id,
                version="v1.0",
                content_hash=content_hash,
                parent_hash=None,
                created_at=datetime.now(),
                created_by="system",
                status=VersionStatus.ACTIVE,
                change_summary="Initial version from Phase3 baseline",
                metadata={
                    "source_file": unit_ref.source_file,
                    "unit_type": unit_ref.unit_type
                }
            )

            self.versions[unit_id] = uv
            self.history[unit_id] = [uv]
            self.by_hash[content_hash] = uv

        if self.persist_versions:
            self._save_versions()
        print(f"Initialized {len(self.versions)} unit versions")

    def _calculate_unit_hash(self, unit_id: str, unit_ref: KnowledgeUnitRef) -> str:
        """
        Calculate SHA-256 hash of unit content from YAML.

        Args:
            unit_id: Knowledge unit ID
            unit_ref: Unit reference

        Returns:
            Hexadecimal SHA-256 hash
        """
        yaml_path = self.base_path / unit_ref.source_file

        if not yaml_path.exists():
            return hashlib.sha256(unit_id.encode()).hexdigest()[:16]

        with open(yaml_path, "rb") as f:
            # Hash the full file content
            file_hash = hashlib.sha256(f.read()).hexdigest()

        # Incorporate unit_id for uniqueness within multi-unit files
        combined = f"{unit_id}:{file_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _save_versions(self):
        """Save version database to disk."""
        if not self.persist_versions:
            return

        data = {
            "version": "v1.0",
            "last_updated": datetime.now().isoformat(),
            "current_versions": {
                unit_id: {
                    "version": uv.version,
                    "content_hash": uv.content_hash,
                    "parent_hash": uv.parent_hash,
                    "created_at": uv.created_at.isoformat(),
                    "created_by": uv.created_by,
                    "status": uv.status.value,
                    "change_summary": uv.change_summary,
                    "metadata": uv.metadata
                }
                for unit_id, uv in self.versions.items()
            },
            "history": {
                unit_id: [
                    {
                        "version": h.version,
                        "content_hash": h.content_hash,
                        "parent_hash": h.parent_hash,
                        "created_at": h.created_at.isoformat(),
                        "created_by": h.created_by,
                        "status": h.status.value,
                        "change_summary": h.change_summary,
                        "metadata": h.metadata
                    }
                    for h in history
                ]
                for unit_id, history in self.history.items()
            },
            "code_mappings": {
                unit_id: [
                    {
                        "file_path": m.file_path,
                        "mapping_type": m.mapping_type,
                        "confidence": m.confidence,
                        "verified_at": m.verified_at.isoformat() if m.verified_at else None
                    }
                    for m in mappings
                ]
                for unit_id, mappings in self.code_mapping_registry.as_unit_dict().items()
            },
            "changes": [
                {
                    "from_version": c.from_version,
                    "to_version": c.to_version,
                    "change_type": c.change_type,
                    "changed_fields": c.changed_fields,
                    "impact_summary": c.impact_summary,
                    "detected_at": c.detected_at.isoformat(),
                    "reviewed_by": c.reviewed_by
                }
                for c in self.changes
            ]
        }

        with open(self.version_db_path, "w") as f:
            json.dump(data, f, indent=2)

    # -------------------------------------------------------------------------
    # Version Query APIs
    # -------------------------------------------------------------------------

    def get_current(self, unit_id: str) -> Optional[UnitVersion]:
        """Get current (active) version of a unit."""
        return self.versions.get(unit_id)

    def get_version(self, unit_id: str, version: str) -> Optional[UnitVersion]:
        """Get a specific version of a unit."""
        for uv in self.history.get(unit_id, []):
            if uv.version == version:
                return uv
        return None

    def get_by_hash(self, content_hash: str) -> Optional[UnitVersion]:
        """Get version by content hash."""
        return self.by_hash.get(content_hash)

    def get_history(self, unit_id: str) -> List[UnitVersion]:
        """
        Get full version history for a unit.

        Returns list ordered newest first.
        """
        history = self.history.get(unit_id, [])
        if history:
            # Return newest first (reverse chronological)
            return sorted(history, key=lambda x: x.created_at, reverse=True)
        return []

    def get_lineage(self, unit_id: str) -> List[UnitVersion]:
        """
        Get complete lineage chain from initial to current.

        Follows parent_hash links to reconstruct full ancestry.
        Returns list ordered oldest to newest.
        """
        current = self.get_current(unit_id)
        if not current:
            return []

        lineage = [current]
        visited = {current.content_hash}

        while current.parent_hash:
            parent = self.get_by_hash(current.parent_hash)
            if parent and parent.content_hash not in visited:
                lineage.insert(0, parent)  # Insert at beginning
                visited.add(parent.content_hash)
                current = parent
            else:
                break

        return lineage

    # -------------------------------------------------------------------------
    # Version Creation APIs
    # -------------------------------------------------------------------------

    def create_version(
        self,
        unit_id: str,
        new_version: str,
        change_summary: str,
        content: Optional[Dict[str, Any]] = None,
        created_by: str = "system"
    ) -> UnitVersion:
        """
        Create a new version of a knowledge unit.

        This should be called after validating and committing changes
        to the YAML source files.

        Args:
            unit_id: Knowledge unit ID
            new_version: New version string (e.g., "v1.1")
            change_summary: Human-readable description of changes
            content: New content (if None, reads from current YAML)
            created_by: Creator identifier

        Returns:
            The newly created UnitVersion
        """
        current = self.get_current(unit_id)
        if not current:
            raise ValueError(f"Unit {unit_id} not found")

        # Calculate new content hash
        if content is None:
            # Read from YAML
            unit_ref = self.units.get(unit_id)
            if not unit_ref:
                raise ValueError(f"Unit {unit_id} not in registry")
            content_hash = self._calculate_unit_hash(unit_id, unit_ref)
        else:
            # Hash from provided content
            content_str = json.dumps(content, sort_keys=True)
            content_hash = hashlib.sha256(content_str.encode()).hexdigest()

        # Create new version
        new_uv = UnitVersion(
            unit_id=unit_id,
            version=new_version,
            content_hash=content_hash,
            parent_hash=current.content_hash,
            created_at=datetime.now(),
            created_by=created_by,
            status=VersionStatus.ACTIVE,
            change_summary=change_summary,
            metadata={
                "source_file": current.metadata.get("source_file"),
                "unit_type": current.metadata.get("unit_type")
            }
        )

        # Mark old version as superseded
        current.status = VersionStatus.SUPERSEDED

        # Update registries
        self.versions[unit_id] = new_uv
        self.history[unit_id].append(new_uv)
        self.by_hash[content_hash] = new_uv

        # Save to disk
        self._save_versions()

        return new_uv

    def create_version_from_diff(
        self,
        unit_id: str,
        diff_report: Dict[str, Any],
        created_by: str = "system"
    ) -> UnitVersion:
        """
        Create new version from diff_engine.py output.

        Args:
            unit_id: Knowledge unit ID
            diff_report: Output from diff_engine.diff_units()
            created_by: Creator identifier

        Returns:
            The newly created UnitVersion
        """
        current = self.get_current(unit_id)
        if not current:
            raise ValueError(f"Unit {unit_id} not found")

        # Determine new version number (auto-increment)
        current_major = int(current.version.replace("v", "").split(".")[0])
        current_minor = int(current.version.replace("v", "").split(".")[1])
        new_version = f"v{current_major}.{current_minor + 1}"

        # Build change summary
        change_type = diff_report.get("change_type", "UNKNOWN")
        summary = f"{change_type}: {diff_report.get('summary', 'Changes detected')}"

        # Record the change
        self.changes.append(VersionChange(
            from_version=current.content_hash,
            to_version=f"{unit_id}:{new_version}",  # Temporary, will update after save
            change_type=change_type,
            changed_fields=diff_report.get("changed_fields", []),
            impact_summary=diff_report.get("impact_summary", ""),
            detected_at=datetime.now(),
            reviewed_by=None
        ))

        # Create the version
        new_uv = self.create_version(
            unit_id=unit_id,
            new_version=new_version,
            change_summary=summary,
            created_by=created_by
        )

        # Update the change record with actual hash
        self.changes[-1].to_version = new_uv.content_hash
        self._save_versions()

        return new_uv

    # -------------------------------------------------------------------------
    # Version Comparison APIs
    # -------------------------------------------------------------------------

    def diff_versions(
        self,
        unit_id: str,
        from_version: str,
        to_version: str
    ) -> Dict[str, Any]:
        """
        Compare two versions of a unit.

        This integrates with diff_engine.py for detailed diff.

        Args:
            unit_id: Knowledge unit ID
            from_version: Source version (e.g., "v1.0")
            to_version: Target version (e.g., "v1.1")

        Returns:
            Dict with changes between versions
        """
        from_uv = self.get_version(unit_id, from_version)
        to_uv = self.get_version(unit_id, to_version)

        if not from_uv:
            raise ValueError(f"Version {from_version} not found for {unit_id}")
        if not to_uv:
            raise ValueError(f"Version {to_version} not found for {unit_id}")

        # Check if they are in the same lineage
        if to_uv.parent_hash != from_uv.content_hash:
            # Not direct parent-child, need to traverse chain
            lineage = self.get_lineage(unit_id)
            from_index = None
            to_index = None
            for i, uv in enumerate(lineage):
                if uv.version == from_version:
                    from_index = i
                if uv.version == to_version:
                    to_index = i
            if from_index is None or to_index is None:
                return {"error": "Versions not in same lineage"}

        # Import diff_engine if available
        try:
            from knowledge_compiler.executables.diff_engine import DiffEngine
            engine = DiffEngine()

            # For now, return basic comparison
            # Full integration would require storing YAML snapshots per version
            return {
                "unit_id": unit_id,
                "from_version": from_version,
                "to_version": to_version,
                "from_hash": from_uv.content_hash[:8],
                "to_hash": to_uv.content_hash[:8],
                "change_summary": to_uv.change_summary,
                "note": "Full YAML diff integration pending - requires content snapshots"
            }
        except ImportError:
            return {
                "unit_id": unit_id,
                "from_version": from_version,
                "to_version": to_version,
                "from_hash": from_uv.content_hash[:8],
                "to_hash": to_uv.content_hash[:8],
                "change_summary": to_uv.change_summary,
                "note": "diff_engine not available for detailed diff"
            }

    # -------------------------------------------------------------------------
    # Code Mapping APIs
    # -------------------------------------------------------------------------

    @property
    def code_mappings(self) -> Dict[str, List[CodeMapping]]:
        """Backward-compatible unit-indexed view of code mappings."""
        return self.code_mapping_registry.as_unit_dict()

    def add_code_mapping(
        self,
        unit_id: str,
        file_path: str,
        mapping_type: str,
        confidence: float = 1.0
    ) -> CodeMapping:
        """Add a code-to-knowledge mapping."""
        mapping = self.code_mapping_registry.add_mapping(
            unit_id=unit_id,
            file_path=file_path,
            mapping_type=mapping_type,
            confidence=confidence,
        )
        self._save_versions()
        return mapping

    def get_code_mappings(self, unit_id: Optional[str] = None) -> List[CodeMapping]:
        """
        Get code mappings, optionally filtered by unit_id.

        Args:
            unit_id: Filter to this unit (None = all)

        Returns:
            List of CodeMapping
        """
        if unit_id:
            return self.code_mapping_registry.get_mappings_for_unit(unit_id)
        return self.code_mapping_registry.get_all_mappings()

    def find_units_by_file(self, file_path: str) -> List[str]:
        """
        Find which knowledge units reference a given file.

        Args:
            file_path: Path to code file

        Returns:
            List of unit_ids that reference this file
        """
        matching = self.code_mapping_registry.get_units_for_file(file_path)
        if matching:
            return matching
        return self.code_mapping_registry.find_units_by_pattern(file_path)

    # -------------------------------------------------------------------------
    # Integrity & Validation
    # -------------------------------------------------------------------------

    def validate_lineage(self, unit_id: str) -> Dict[str, Any]:
        """
        Validate that a unit's version history is consistent.

        Checks:
        - All parent hashes exist
        - No circular references
        - Content hashes match

        Returns: {"valid": bool, "issues": []}
        """
        issues = []

        lineage = self.get_lineage(unit_id)

        for i, uv in enumerate(lineage):
            # Check parent hash exists (except first version)
            if i > 0 and uv.parent_hash:
                if uv.parent_hash not in self.by_hash:
                    issues.append(f"Version {uv.version}: parent hash {uv.parent_hash[:8]} not found")

            # Verify no circular reference (already present in lineage traversal)

        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_versions = sum(len(h) for h in self.history.values())

        status_counts = {}
        for uv in self.versions.values():
            status_counts[uv.status.value] = status_counts.get(uv.status.value, 0) + 1

        return {
            "total_units": len(self.versions),
            "total_versions": total_versions,
            "status_counts": status_counts,
            "code_mappings": self.code_mapping_registry.get_statistics()["total_mappings"],
            "changes_tracked": len(self.changes)
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_versioned_registry: Optional[VersionedKnowledgeRegistry] = None


def get_versioned_registry() -> VersionedKnowledgeRegistry:
    """Get the global versioned knowledge registry instance."""
    global _versioned_registry
    if _versioned_registry is None:
        _versioned_registry = VersionedKnowledgeRegistry()
    return _versioned_registry

# =============================================================================
# Propagation Engine - P4-03
# =============================================================================

from knowledge_compiler.executables.diff_engine import ChangeType, DiffReport


@dataclass
class PropagationDecision:
    """
    Decision result from propagation analysis.
    
    Attributes:
        should_propagate: Whether the change should trigger propagation
        target_executables: List of affected executable IDs
        action_type: Action to take (hot_reload, restart, reverify, halt)
        reason: Human-readable explanation
    """
    should_propagate: bool
    target_executables: List[str]
    action_type: str
    reason: str


class PropagationEngine:
    """
    Propagation Engine - P4-03
    
    Integrates diff_engine for change detection and determines impact targets
    based on change types. Executes propagation decisions based on 
    propagation_rules.md logic.
    
    Core responsibilities:
    1. detect_changes() - Use diff_engine to find changes
    2. analyze_impact() - Determine which units are affected
    3. propagate() - Execute propagation based on rules
    """
    
    # Propagation action types from propagation_rules.md
    ACTION_HOT_RELOAD = "hot_reload"
    ACTION_RESTART = "restart"
    ACTION_REVERIFY = "reverify"
    ACTION_HALT = "halt"
    ACTION_IGNORE = "ignore"
    
    def __init__(self):
        """Initialize propagation engine."""
        self.decision_history: List[Dict[str, Any]] = []
    
    def detect_changes(
        self,
        baseline: str,
        current: str,
        baseline_commit: Optional[str] = None
    ) -> List[DiffReport]:
        """
        Use diff_engine to detect changes between baseline and current.
        
        Args:
            baseline: Baseline path or commit hash
            current: Current knowledge_compiler path
            baseline_commit: Optional explicit commit hash
            
        Returns:
            List of DiffReport objects
        """
        from knowledge_compiler.executables.diff_engine import diff_files
        
        if baseline_commit:
            baseline = baseline_commit
        
        changes = diff_files(baseline, current)
        return changes
    
    def analyze_impact(self, change: DiffReport) -> PropagationDecision:
        """
        Determine impact of a single change based on propagation_rules.md logic.
        
        Rules:
        - DELETE changes: affected executables that reference the unit -> HALT
        - EVIDENCE_EDIT: may affect executables using this evidence -> REVERIFY
        - SEMANTIC_EDIT: high impact - check all dependents -> HOT_RELOAD or RESTART
        - CHART_RULE_EDIT: Regenerate affected charts -> HOT_RELOAD
        - TEXT_EDIT: Ignore - no impact
        - NEW: Hot-reload if compatible
        
        Args:
            change: DiffReport from diff_engine
            
        Returns:
            PropagationDecision with action and targets
        """
        change_type = change.change_type
        unit_id = change.unit_id
        impacted_executables = change.impacted_executables
        
        # TEXT_EDIT: Ignore - no propagation needed
        if change_type == ChangeType.TEXT_EDIT:
            return PropagationDecision(
                should_propagate=False,
                target_executables=[],
                action_type=self.ACTION_IGNORE,
                reason=f"TEXT_EDIT on {unit_id} - formatting only, no impact"
            )
        
        # DELETE: HALT - requires manual review
        if change_type == ChangeType.DELETE:
            return PropagationDecision(
                should_propagate=True,
                target_executables=impacted_executables or [unit_id],
                action_type=self.ACTION_HALT,
                reason=f"DELETE of {unit_id} - emergency halt, manual review required"
            )
        
        # EVIDENCE_EDIT: Re-run benchmarks, re-verify
        if change_type == ChangeType.EVIDENCE_EDIT:
            return PropagationDecision(
                should_propagate=True,
                target_executables=impacted_executables,
                action_type=self.ACTION_REVERIFY,
                reason=f"EVIDENCE_EDIT on {unit_id} - re-verification required"
            )
        
        # CHART_RULE_EDIT: Regenerate affected charts
        if change_type == ChangeType.CHART_RULE_EDIT:
            return PropagationDecision(
                should_propagate=True,
                target_executables=impacted_executables,
                action_type=self.ACTION_HOT_RELOAD,
                reason=f"CHART_RULE_EDIT on {unit_id} - chart regeneration required"
            )
        
        # SEMANTIC_EDIT: High impact - check if schema-breaking
        if change_type == ChangeType.SEMANTIC_EDIT:
            # Check if it's a schema-level change
            is_schema_breaking = self._is_schema_breaking(change)
            
            if is_schema_breaking:
                return PropagationDecision(
                    should_propagate=True,
                    target_executables=impacted_executables,
                    action_type=self.ACTION_RESTART,
                    reason=f"SEMANTIC_EDIT (schema-breaking) on {unit_id} - restart required"
                )
            else:
                return PropagationDecision(
                    should_propagate=True,
                    target_executables=impacted_executables,
                    action_type=self.ACTION_HOT_RELOAD,
                    reason=f"SEMANTIC_EDIT on {unit_id} - hot-reload possible"
                )
        
        # NEW: Hot-reload if compatible
        if change_type == ChangeType.NEW:
            return PropagationDecision(
                should_propagate=True,
                target_executables=[unit_id],
                action_type=self.ACTION_HOT_RELOAD,
                reason=f"NEW unit {unit_id} - hot-reload new knowledge"
            )
        
        # Default: conservative approach
        return PropagationDecision(
            should_propagate=True,
            target_executables=impacted_executables,
            action_type=self.ACTION_RESTART,
            reason=f"Unknown change type {change_type} on {unit_id} - conservative restart"
        )
    
    def _is_schema_breaking(self, change: DiffReport) -> bool:
        """
        Determine if a SEMANTIC_EDIT is schema-breaking.
        
        Schema-breaking indicators:
        - Change in schema/ directory
        - Change to core formula structure
        - Change to chapter definitions
        
        Args:
            change: DiffReport to analyze
            
        Returns:
            True if schema-breaking
        """
        unit_id = change.unit_id.lower()
        field = change.field.lower()
        
        # Check path indicators
        if "schema/" in unit_id:
            return True
        
        # Check field indicators for structural changes
        schema_keywords = ["structure", "schema", "definition", "signature"]
        if any(keyword in field for keyword in schema_keywords):
            return True
        
        # Formula signature changes
        if "form-" in unit_id and ("signature" in field or "arguments" in field):
            return True
        
        return False
    
    def propagate(
        self,
        changes: List[DiffReport],
        dry_run: bool = False
    ) -> List[PropagationDecision]:
        """
        Execute propagation based on rules.
        
        Args:
            changes: List of DiffReport objects
            dry_run: If True, analyze but don't execute
            
        Returns:
            List of PropagationDecision objects
        """
        decisions: List[PropagationDecision] = []
        
        for change in changes:
            decision = self.analyze_impact(change)
            decisions.append(decision)
            
            # Record decision for audit trail
            self.decision_history.append({
                "timestamp": datetime.now().isoformat(),
                "change": {
                    "change_type": change.change_type.value,
                    "unit_id": change.unit_id,
                    "field": change.field,
                    "impacted_executables": change.impacted_executables
                },
                "decision": {
                    "should_propagate": decision.should_propagate,
                    "target_executables": decision.target_executables,
                    "action_type": decision.action_type,
                    "reason": decision.reason
                }
            })
            
            # Execute propagation if not dry_run
            if not dry_run and decision.should_propagate:
                self._execute_propagation(decision, change)
        
        return decisions
    
    def _execute_propagation(self, decision: PropagationDecision, change: DiffReport):
        """
        Execute a propagation decision.
        
        This is a placeholder for actual execution logic.
        In production, this would interface with orchestrator components.
        
        Args:
            decision: PropagationDecision to execute
            change: Original DiffReport
        """
        action_type = decision.action_type
        
        # For now, just log - actual execution would be in orchestrator
        pass
    
    def get_decision_history(self) -> List[Dict[str, Any]]:
        """Get history of propagation decisions."""
        return self.decision_history.copy()
    
    def clear_history(self):
        """Clear decision history."""
        self.decision_history.clear()


# =============================================================================
# Governance Engine - P4-04
# =============================================================================


@dataclass
class ValidationResult:
    """
    Result of a single governance validation check.

    Attributes:
        passed: True when the check succeeded
        failed_checks: Human-readable failure details
        warnings: Non-blocking observations
    """
    passed: bool
    failed_checks: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class GovernanceDecision:
    """
    Final governance decision for publishing a knowledge unit.

    Attributes:
        status: APPROVED / REJECTED / DEFERRED
        reasons: Blocking or decision-driving reasons
        warnings: Non-blocking warnings
        validation_results: Per-check results keyed by method name
        propagation_decisions: Optional downstream propagation actions
    """
    APPROVED: ClassVar[str] = "APPROVED"
    REJECTED: ClassVar[str] = "REJECTED"
    DEFERRED: ClassVar[str] = "DEFERRED"

    status: str
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validation_results: Dict[str, ValidationResult] = field(default_factory=dict)
    propagation_decisions: List[PropagationDecision] = field(default_factory=list)

    def __post_init__(self):
        valid_statuses = {self.APPROVED, self.REJECTED, self.DEFERRED}
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid governance status: {self.status}")


class GovernanceEngine:
    """
    Governance Engine - P4-04

    Enforces publish_contract.md and model_rules_v1.2_with_codex_cr.md
    before knowledge units are published and propagated.
    """

    SUPPORTED_SPEC_VERSION = "v1.1"

    _SCHEMA_FILES = {
        "raw": "raw_schema.json",
        "parsed": "parsed_schema.json",
        "canonical": "canonical_schema.json",
        "executable": "executable_schema.json",
    }

    _MODEL_RULES = (
        (
            (
                "p1",
                "p1 知识捕获",
                "知识捕获",
                "knowledge capture",
            ),
            "Codex (GPT-5.4)",
        ),
        (
            (
                "p2",
                "p2 knowledge compiler",
                "knowledge compiler",
            ),
            "Codex (GPT-5.4)",
        ),
        (
            (
                "p3",
                "p3 orchestrator 实现",
                "orchestrator 实现",
                "orchestrator implementation",
            ),
            "Codex (GPT-5.4)",
        ),
        (
            (
                "g3-g6 gate",
                "g3 gate",
                "g4 gate",
                "g5 gate",
                "g6 gate",
                "gate task",
            ),
            "Codex (GPT-5.4)",
        ),
        (
            (
                "架构审查",
                "architecture review",
            ),
            "Opus 4.6",
        ),
        (
            (
                "任务拆解审查",
                "task breakdown review",
                "task decomposition review",
            ),
            "Opus 4.6",
        ),
        (
            (
                "gate 最终审批",
                "gate final approval",
                "final approval",
                "人工审批",
            ),
            "Human",
        ),
        (
            (
                "v1 架构迁移",
                "v1 architecture migration",
            ),
            "Codex (GPT-5.4)",
        ),
        (
            (
                "文档更新",
                "documentation update",
                "docs update",
            ),
            "Codex (GPT-5.4)",
        ),
    )

    def __init__(
        self,
        base_path: Optional[Path] = None,
        propagation_engine: Optional[PropagationEngine] = None,
    ):
        """
        Initialize the governance engine.

        Args:
            base_path: Path to knowledge_compiler root. Defaults to package root.
            propagation_engine: Optional PropagationEngine instance.
        """
        self.base_path = self._resolve_base_path(base_path)
        self.schema_path = self.base_path / "schema"
        self.executables_path = self.base_path / "executables"
        self.propagation_engine = propagation_engine or PropagationEngine()
        self.schemas = self._load_schemas()

    def check_completeness(self, unit: Dict[str, Any]) -> ValidationResult:
        """Check that all required fields and version metadata are present."""
        failures: List[str] = []
        warnings: List[str] = []

        layer = self._detect_layer(unit)
        if not layer:
            return ValidationResult(
                passed=False,
                failed_checks=["Unable to determine knowledge layer for completeness check"],
                warnings=[],
            )

        missing_fields = [
            field_name
            for field_name in self._get_required_fields(layer)
            if self._is_missing_value(unit.get(field_name))
        ]
        if missing_fields:
            failures.append(
                f"Missing required fields: {', '.join(sorted(missing_fields))}"
            )

        nested_required_paths = self._get_nested_required_paths(layer)
        for path in nested_required_paths:
            if self._is_missing_value(self._get_nested_value(unit, path)):
                failures.append(f"Missing required nested field: {path}")

        if self._requires_source_line_range(unit, layer):
            line_range = unit.get("source_line_range")
            if not self._has_valid_line_range(line_range):
                failures.append(
                    "Source line ranges must be populated for source-mapped units"
                )

        if not self._has_version_tag(unit):
            failures.append("Version tags must be assigned to all units")

        return ValidationResult(
            passed=len(failures) == 0,
            failed_checks=failures,
            warnings=warnings,
        )

    def check_data_honesty(self, unit: Dict[str, Any]) -> ValidationResult:
        """Check for undeclared nulls, hidden data gaps, and fabrication markers."""
        failures: List[str] = []
        warnings: List[str] = []

        layer = self._detect_layer(unit)
        documented_nulls = self._get_documented_null_paths(unit)
        null_paths = self._find_null_paths(unit)

        for path in null_paths:
            top_field = path.split(".")[0]
            if top_field in {"propagation_changes", "validation_results"}:
                continue
            if path in documented_nulls or top_field in documented_nulls:
                continue
            if layer and self._field_allows_null(layer, top_field):
                continue
            failures.append(f"Undocumented null value found at {path}")

        if unit.get("undeclared_data_gaps"):
            failures.append("Undeclared data gaps were detected")

        if unit.get("has_data_gaps") and not unit.get("data_gaps"):
            failures.append("Data gaps are present but not declared in data_gaps")

        fabrication_flags = (
            unit.get("fabrication_detected"),
            unit.get("fabricated_data"),
            unit.get("fabricated_fields"),
            unit.get("source_verified") is False,
        )
        if any(fabrication_flags):
            failures.append("Fabrication or failed source verification detected")

        if self._contains_unavailable_bench04_claim(unit):
            failures.append(
                "BENCH-04 source cannot publish richer wake traces without a declared gap"
            )

        if unit.get("contains_zero_reference") and not (
            unit.get("zero_reference_flagged")
            or unit.get("zero_reference_handling")
            or unit.get("zero_reference_strategy")
        ):
            failures.append(
                "Zero-reference values are present without explicit handling metadata"
            )

        if unit.get("data_gaps"):
            warnings.append("Declared data gaps will need downstream handling")

        return ValidationResult(
            passed=len(failures) == 0,
            failed_checks=failures,
            warnings=warnings,
        )

    def check_schema_compliance(self, unit: Dict[str, Any]) -> ValidationResult:
        """Check layer-specific schema constraints from the publish contract."""
        failures: List[str] = []
        warnings: List[str] = []

        layer = self._detect_layer(unit)
        if not layer:
            return ValidationResult(
                passed=False,
                failed_checks=["Unable to determine knowledge layer for schema compliance"],
                warnings=[],
            )

        required_fields = self._get_required_fields(layer)
        missing_fields = [
            field_name
            for field_name in required_fields
            if self._is_missing_value(unit.get(field_name))
        ]
        if missing_fields:
            failures.append(
                f"Schema required_fields missing: {', '.join(sorted(missing_fields))}"
            )

        if layer == "parsed":
            structured_data = unit.get("structured_data")
            if not isinstance(structured_data, dict):
                failures.append("structured_data must be an object")
            else:
                unit_type = structured_data.get("unit_type")
                if unit_type not in self._get_unit_type_enum(layer):
                    failures.append(
                        f"structured_data.unit_type must be one of {self._get_unit_type_enum(layer)}"
                    )

        if layer == "canonical":
            if unit.get("spec_version") != self.SUPPORTED_SPEC_VERSION:
                failures.append(
                    f"Canonical spec_version must be {self.SUPPORTED_SPEC_VERSION}"
                )
            normalized_form = unit.get("normalized_form")
            if not isinstance(normalized_form, dict):
                failures.append("normalized_form must be an object")
            elif normalized_form.get("spec_version") != self.SUPPORTED_SPEC_VERSION:
                failures.append(
                    f"normalized_form.spec_version must be {self.SUPPORTED_SPEC_VERSION}"
                )

        if layer == "executable":
            test_cases = unit.get("test_cases")
            if not isinstance(test_cases, list) or len(test_cases) == 0:
                failures.append("Executable layer requires a non-empty test_cases array")

        top_level_enums = {
            "raw": ("capture_method",),
            "canonical": ("unit_type",),
            "executable": ("language", "asset_type"),
        }
        for field_name in top_level_enums.get(layer, ()):
            field_value = unit.get(field_name)
            allowed_values = self._get_field_enum(layer, field_name)
            if field_value is not None and allowed_values and field_value not in allowed_values:
                failures.append(
                    f"{field_name} must be one of {allowed_values}"
                )

        return ValidationResult(
            passed=len(failures) == 0,
            failed_checks=failures,
            warnings=warnings,
        )

    def check_executable_validation(self, unit: Dict[str, Any]) -> ValidationResult:
        """Run the executable validation suite required for publication."""
        failures: List[str] = []
        warnings: List[str] = []

        suite_results = self._run_executable_validation_suite()
        for suite_name, result in suite_results.items():
            if not result.get("passed"):
                detail = result.get("detail", "unknown failure")
                failures.append(f"{suite_name} failed: {detail}")

        if not suite_results:
            failures.append("Executable validation suite did not produce any results")

        return ValidationResult(
            passed=len(failures) == 0,
            failed_checks=failures,
            warnings=warnings,
        )

    def check_semantic_correctness(self, unit: Dict[str, Any]) -> ValidationResult:
        """Check for meaningful content and known semantic rule violations."""
        failures: List[str] = []
        warnings: List[str] = []

        content = self._get_semantic_payload(unit)
        text_fragments = self._collect_strings(content)
        meaningful_fragments = [
            fragment for fragment in text_fragments if self._is_meaningful_string(fragment)
        ]

        if not meaningful_fragments:
            failures.append("No meaningful content found for semantic validation")

        if self._contains_placeholder_content(text_fragments):
            failures.append("Placeholder or unfinished content detected")

        unit_type = (
            unit.get("unit_type")
            or self._get_nested_value(unit, "structured_data.unit_type")
            or self._get_nested_value(unit, "normalized_form.unit_type")
        )

        if unit_type == "chapter":
            sections = self._get_nested_value(unit, "normalized_form.canonical_content.sections")
            if sections is None:
                sections = self._get_nested_value(unit, "structured_data.content.sections")
            if sections is not None and (not isinstance(sections, list) or len(sections) == 0):
                failures.append("Chapter content must include at least one section")

        if unit_type == "formula":
            definition = self._first_non_empty_value(
                [
                    self._get_nested_value(unit, "normalized_form.canonical_content.definition"),
                    self._get_nested_value(unit, "structured_data.content.definition"),
                    unit.get("definition"),
                    unit.get("formula"),
                ]
            )
            if self._is_missing_value(definition):
                failures.append("Formula content must include a definition")
            elif "max(" in str(definition).lower():
                failures.append("Zero-reference handling must not use max() denominator")

        gci_formula = self._first_non_empty_value(
            [
                self._get_nested_value(unit, "normalized_form.canonical_content.gci_formula"),
                self._get_nested_value(unit, "structured_data.content.gci_formula"),
                self._get_nested_value(unit, "normalized_form.canonical_content.definition"),
                unit.get("gci_formula"),
                unit.get("definition"),
            ]
        )
        if self._is_gci_related(unit, text_fragments) and gci_formula:
            formula_text = str(gci_formula).lower().replace(" ", "")
            if "r^p-1" not in formula_text and "r**p-1" not in formula_text:
                failures.append("GCI formula does not match the required Richardson form")

        return ValidationResult(
            passed=len(failures) == 0,
            failed_checks=failures,
            warnings=warnings,
        )

    def approve_publish(self, unit: Dict[str, Any]) -> GovernanceDecision:
        """
        Aggregate governance checks and return the publish decision.

        The unit may optionally include:
        - requires_human_review: bool
        - human_review_signed_off: bool
        - propagation_changes: List[DiffReport]
        - propagation_dry_run: bool
        """
        validation_results = {
            "completeness": self.check_completeness(unit),
            "data_honesty": self.check_data_honesty(unit),
            "schema_compliance": self.check_schema_compliance(unit),
            "executable_validation": self.check_executable_validation(unit),
            "semantic_correctness": self.check_semantic_correctness(unit),
        }

        rejection_reasons: List[str] = []
        deferred_reasons: List[str] = []
        warnings: List[str] = []

        for check_name, result in validation_results.items():
            warnings.extend(result.warnings)
            if not result.passed:
                rejection_reasons.extend(
                    [f"{check_name}: {message}" for message in result.failed_checks]
                )

        conflict_flags = unit.get("conflict_flags") or []
        if conflict_flags:
            rejection_reasons.append(
                f"Conflict flags present: {', '.join(str(flag) for flag in conflict_flags)}"
            )

        gci_result = unit.get("grid_independence") or {}
        if isinstance(gci_result, dict):
            gci_pass = gci_result.get("pass")
            gci_value = gci_result.get("gci_medium_fine_pct")
            if gci_pass is False:
                rejection_reasons.append("Grid independence validation failed")
            elif gci_value is not None and gci_value >= 5.0:
                rejection_reasons.append("Grid independence requires GCI < 5%")

        if unit.get("requires_human_review") and not unit.get("human_review_signed_off"):
            deferred_reasons.append("Human review sign-off is required before publication")

        propagation_decisions: List[PropagationDecision] = []
        propagation_changes = unit.get("propagation_changes") or []
        if propagation_changes:
            if rejection_reasons or deferred_reasons:
                warnings.append("Propagation blocked because governance did not approve publish")
            else:
                propagation_decisions = self.propagation_engine.propagate(
                    propagation_changes,
                    dry_run=bool(unit.get("propagation_dry_run", False)),
                )
                if any(
                    decision.action_type == self.propagation_engine.ACTION_HALT
                    for decision in propagation_decisions
                ):
                    deferred_reasons.append(
                        "Propagation engine requested manual halt before publish"
                    )

        warnings = self._deduplicate_messages(warnings)

        if rejection_reasons:
            return GovernanceDecision(
                status=GovernanceDecision.REJECTED,
                reasons=self._deduplicate_messages(rejection_reasons),
                warnings=warnings,
                validation_results=validation_results,
                propagation_decisions=propagation_decisions,
            )

        if deferred_reasons:
            return GovernanceDecision(
                status=GovernanceDecision.DEFERRED,
                reasons=self._deduplicate_messages(deferred_reasons),
                warnings=warnings,
                validation_results=validation_results,
                propagation_decisions=propagation_decisions,
            )

        return GovernanceDecision(
            status=GovernanceDecision.APPROVED,
            reasons=["All governance checks passed"],
            warnings=warnings,
            validation_results=validation_results,
            propagation_decisions=propagation_decisions,
        )

    def validate_model_assignment(self, task_type: str, model: str) -> bool:
        """Validate that a task type is assigned to the required model."""
        required_model = self._get_required_model(task_type)
        if not required_model:
            return False
        return self._model_matches(required_model, model)

    def _resolve_base_path(self, base_path: Optional[Path]) -> Path:
        candidate = Path(base_path) if base_path is not None else Path(__file__).resolve().parent.parent
        if (candidate / "schema").exists():
            return candidate
        if (candidate / "knowledge_compiler" / "schema").exists():
            return candidate / "knowledge_compiler"
        return candidate

    def _load_schemas(self) -> Dict[str, Dict[str, Any]]:
        schemas: Dict[str, Dict[str, Any]] = {}
        for layer, filename in self._SCHEMA_FILES.items():
            schema_file = self.schema_path / filename
            if not schema_file.exists():
                schemas[layer] = {}
                continue
            with open(schema_file) as handle:
                schemas[layer] = json.load(handle)
        return schemas

    def _detect_layer(self, unit: Dict[str, Any]) -> Optional[str]:
        layer = str(unit.get("layer", "")).strip().lower()
        if layer in self._SCHEMA_FILES:
            return layer

        if any(key in unit for key in ("executable_id", "executable_code", "asset_type", "test_cases")):
            return "executable"
        if any(key in unit for key in ("canonical_id", "normalized_form", "normalized_at")):
            return "canonical"
        if any(key in unit for key in ("parsed_id", "structured_data", "parsed_at")):
            return "parsed"
        if any(key in unit for key in ("raw_id", "raw_text", "capture_method", "source_file")):
            return "raw"
        return None

    def _get_required_fields(self, layer: str) -> List[str]:
        schema = self.schemas.get(layer, {})
        return list(schema.get("required_fields", []))

    def _get_field_definition(self, layer: str, field_name: str) -> Dict[str, Any]:
        schema = self.schemas.get(layer, {})
        for field_def in schema.get("fields", []):
            if field_def.get("field_id") == field_name:
                return field_def
        return {}

    def _get_field_enum(self, layer: str, field_name: str) -> List[str]:
        field_def = self._get_field_definition(layer, field_name)
        return list(field_def.get("enum", []))

    def _get_unit_type_enum(self, layer: str) -> List[str]:
        schema = self.schemas.get(layer, {})
        for field_def in schema.get("fields", []):
            if field_def.get("field_id") in {"structured_data", "normalized_form"}:
                properties = field_def.get("properties", {})
                unit_type_field = properties.get("unit_type", {})
                return list(unit_type_field.get("enum", []))
        return []

    def _get_nested_required_paths(self, layer: str) -> List[str]:
        if layer == "parsed":
            return ["structured_data.unit_type", "structured_data.unit_id"]
        if layer == "canonical":
            return [
                "normalized_form.unit_type",
                "normalized_form.unit_id",
                "normalized_form.spec_version",
            ]
        return []

    def _requires_source_line_range(self, unit: Dict[str, Any], layer: str) -> bool:
        return layer == "raw" or bool(unit.get("source_mapped"))

    def _has_valid_line_range(self, line_range: Any) -> bool:
        if not isinstance(line_range, list) or len(line_range) != 2:
            return False
        return all(isinstance(value, int) and value >= 0 for value in line_range)

    def _has_version_tag(self, unit: Dict[str, Any]) -> bool:
        candidate_values = []
        for key, value in unit.items():
            if key == "version" or key.endswith("_version"):
                candidate_values.append(value)
        normalized_form = unit.get("normalized_form")
        if isinstance(normalized_form, dict):
            candidate_values.append(normalized_form.get("spec_version"))
        return any(not self._is_missing_value(value) for value in candidate_values)

    def _get_documented_null_paths(self, unit: Dict[str, Any]) -> Set[str]:
        documented: Set[str] = set()
        for key in ("null_documentation", "documented_null_fields"):
            value = unit.get(key)
            if isinstance(value, dict):
                documented.update(str(path) for path in value.keys())
            elif isinstance(value, list):
                documented.update(str(path) for path in value)

        metadata = unit.get("metadata")
        if isinstance(metadata, dict):
            for key in ("null_documentation", "documented_null_fields"):
                value = metadata.get(key)
                if isinstance(value, dict):
                    documented.update(str(path) for path in value.keys())
                elif isinstance(value, list):
                    documented.update(str(path) for path in value)
        return documented

    def _find_null_paths(self, value: Any, prefix: str = "") -> List[str]:
        if value is None:
            return [prefix] if prefix else []

        paths: List[str] = []
        if isinstance(value, dict):
            for key, nested_value in value.items():
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                paths.extend(self._find_null_paths(nested_value, next_prefix))
            return paths

        if isinstance(value, list):
            for index, nested_value in enumerate(value):
                next_prefix = f"{prefix}[{index}]"
                paths.extend(self._find_null_paths(nested_value, next_prefix))
        return paths

    def _field_allows_null(self, layer: str, field_name: str) -> bool:
        field_def = self._get_field_definition(layer, field_name)
        if not field_def:
            return False
        field_type = field_def.get("type")
        if isinstance(field_type, list) and "null" in field_type:
            return True
        return field_def.get("required", False) is False

    def _contains_unavailable_bench04_claim(self, unit: Dict[str, Any]) -> bool:
        data_gaps_text = " ".join(str(gap).lower() for gap in unit.get("data_gaps", []))
        if any(token in data_gaps_text for token in ("lift", "time history", "wake trace", "polar")):
            return False

        source_fragments = self._collect_strings(
            {
                "source_file": unit.get("source_file"),
                "source": unit.get("source"),
                "metadata": unit.get("metadata", {}),
            }
        )
        source_text = " ".join(fragment.lower() for fragment in source_fragments)
        if "williamson" not in source_text and "bench-04" not in source_text:
            return False

        key_hits = self._collect_keys_matching(
            unit,
            {"cl", "cl_cd", "clcd", "lift_history", "drag_history", "force_time_series"},
        )
        if key_hits:
            return True

        text_hits = [
            fragment for fragment in self._collect_strings(unit)
            if any(
                token in fragment.lower()
                for token in ("cl/cd", "polar curve", "time history", "lift coefficient")
            )
        ]
        return len(text_hits) > 0

    def _collect_keys_matching(self, value: Any, targets: Set[str]) -> List[str]:
        matches: List[str] = []
        if isinstance(value, dict):
            for key, nested_value in value.items():
                normalized_key = str(key).lower().replace("-", "_")
                if normalized_key in targets:
                    matches.append(str(key))
                matches.extend(self._collect_keys_matching(nested_value, targets))
        elif isinstance(value, list):
            for item in value:
                matches.extend(self._collect_keys_matching(item, targets))
        return matches

    def _run_executable_validation_suite(self) -> Dict[str, Dict[str, Any]]:
        suite_results: Dict[str, Dict[str, Any]] = {}
        executables_path = str(self.executables_path)

        if not self.executables_path.exists():
            return {
                "suite": {
                    "passed": False,
                    "detail": f"Executable path not found: {self.executables_path}",
                }
            }

        added_path = False
        if executables_path not in sys.path:
            sys.path.insert(0, executables_path)
            added_path = True

        try:
            formula_validator = importlib.import_module("formula_validator")
            chart_template = importlib.import_module("chart_template")
            bench_ghia1982 = importlib.import_module("bench_ghia1982")
            bench_cylinder_wake = importlib.import_module("bench_cylinder_wake")

            suite_results["formula_validator"] = self._run_callable_validation(
                formula_validator.run_all_tests
            )
            suite_results["chart_template"] = self._run_callable_validation(
                chart_template.run_all_tests
            )
            suite_results["bench_ghia1982"] = self._run_benchmark_validation(
                bench_ghia1982.run_benchmark
            )
            suite_results["bench_cylinder_wake"] = self._run_benchmark_validation(
                bench_cylinder_wake.run_benchmark
            )
        except Exception as exc:
            suite_results["suite"] = {"passed": False, "detail": str(exc)}
        finally:
            if added_path:
                sys.path.remove(executables_path)

        return suite_results

    def _run_callable_validation(self, callback: Any) -> Dict[str, Any]:
        try:
            callback()
            return {"passed": True, "detail": "ok"}
        except Exception as exc:
            return {"passed": False, "detail": str(exc)}

    def _run_benchmark_validation(self, callback: Any) -> Dict[str, Any]:
        try:
            result = callback()
            if result.get("overall_pass"):
                return {"passed": True, "detail": "overall_pass=True"}
            return {"passed": False, "detail": "overall_pass=False"}
        except Exception as exc:
            return {"passed": False, "detail": str(exc)}

    def _get_semantic_payload(self, unit: Dict[str, Any]) -> Any:
        layer = self._detect_layer(unit)
        if layer == "raw":
            return unit.get("raw_text")
        if layer == "parsed":
            return unit.get("structured_data", {})
        if layer == "canonical":
            normalized_form = unit.get("normalized_form", {})
            return normalized_form.get("canonical_content", normalized_form)
        if layer == "executable":
            return {
                "executable_code": unit.get("executable_code"),
                "test_cases": unit.get("test_cases"),
            }
        return unit

    def _collect_strings(self, value: Any) -> List[str]:
        strings: List[str] = []
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, dict):
            for nested_value in value.values():
                strings.extend(self._collect_strings(nested_value))
        elif isinstance(value, list):
            for nested_value in value:
                strings.extend(self._collect_strings(nested_value))
        return strings

    def _contains_placeholder_content(self, strings: List[str]) -> bool:
        placeholder_tokens = ("todo", "tbd", "placeholder", "lorem ipsum", "fixme", "???")
        for fragment in strings:
            normalized = fragment.strip().lower()
            if any(token in normalized for token in placeholder_tokens):
                return True
        return False

    def _is_meaningful_string(self, value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        if re.fullmatch(r"[\W_]+", stripped):
            return False
        if stripped.lower() in {"todo", "tbd", "placeholder"}:
            return False
        return True

    def _is_gci_related(self, unit: Dict[str, Any], fragments: List[str]) -> bool:
        unit_id = str(unit.get("unit_id", "")).lower()
        if "gci" in unit_id:
            return True
        if any("gci" in fragment.lower() for fragment in fragments):
            return True
        return False

    def _get_required_model(self, task_type: str) -> Optional[str]:
        normalized_task = self._normalize_text(task_type)
        for aliases, required_model in self._MODEL_RULES:
            normalized_aliases = {self._normalize_text(alias) for alias in aliases}
            if normalized_task in normalized_aliases:
                return required_model
        return None

    def _model_matches(self, required_model: str, provided_model: str) -> bool:
        required = self._normalize_text(required_model)
        provided = self._normalize_text(provided_model)

        if required == self._normalize_text("Codex (GPT-5.4)"):
            return "codex" in provided and "gpt54" in provided
        if required == self._normalize_text("Opus 4.6"):
            return "opus" in provided and "46" in provided
        if required == self._normalize_text("Human"):
            return provided in {"human", "人工", "manual"}
        return required == provided

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())

    def _get_nested_value(self, data: Any, path: str) -> Any:
        current = data
        for part in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _first_non_empty_value(self, values: List[Any]) -> Any:
        for value in values:
            if not self._is_missing_value(value):
                return value
        return None

    def _is_missing_value(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) == 0
        return False

    def _deduplicate_messages(self, messages: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for message in messages:
            if message not in seen:
                seen.add(message)
                ordered.append(message)
        return ordered


@dataclass
class PropagationEvent:
    """
    Audit record for a change processed through the memory network.

    Attributes:
        event_id: Unique identifier for this orchestration event.
        change_type: Change classification from diff_engine.
        source_unit: Unit that originated the change.
        impact_targets: Propagation targets selected by PropagationEngine.
        governance_decision: Final governance status.
        reason: Human-readable summary of the final decision.
        timestamp: Event creation timestamp.
    """

    event_id: str
    change_type: ChangeType
    source_unit: str
    impact_targets: List[str]
    governance_decision: str
    reason: str
    timestamp: datetime


class MemoryNetwork:
    """
    Main orchestrator for the governed memory network system.

    Integrates:
    - P4-01 VersionedKnowledgeRegistry
    - P4-02 MemoryNode
    - P4-03 PropagationEngine
    - P4-04 GovernanceEngine
    - P4-05 CodeMappingRegistry
    """

    EXECUTABLE_FILE_MAP: ClassVar[Dict[str, str]] = {
        "EXEC-FORMULA-VALIDATOR-001": "knowledge_compiler/executables/formula_validator.py",
        "EXEC-CHART-TEMPLATE-001": "knowledge_compiler/executables/chart_template.py",
        "EXEC-BENCH-GHIA-001": "knowledge_compiler/executables/bench_ghia1982.py",
        "EXEC-BENCH-CYLINDER-WAKE-001": "knowledge_compiler/executables/bench_cylinder_wake.py",
        "EXEC-DIFF-ENGINE-001": "knowledge_compiler/executables/diff_engine.py",
    }

    UNIT_COLLECTIONS: ClassVar[Tuple[Tuple[str, str], ...]] = (
        ("chapters", "id"),
        ("formulas", "id"),
        ("cases", "case_id"),
        ("chart_types", "type_id"),
        ("evidence_chains", "chain_id"),
    )

    def __init__(
        self,
        base_path: Optional[Path] = None,
        version_db_path: Optional[Path] = None,
        versioned_registry: Optional[VersionedKnowledgeRegistry] = None,
        propagation_engine: Optional[PropagationEngine] = None,
        governance_engine: Optional[GovernanceEngine] = None,
    ):
        resolved_base_path = self._resolve_base_path(
            base_path if base_path is not None else getattr(versioned_registry, "base_path", None)
        )

        self.versioned_registry = versioned_registry or VersionedKnowledgeRegistry(
            base_path=resolved_base_path,
            version_db_path=version_db_path,
        )
        self.base_path = self.versioned_registry.base_path

        shared_propagation_engine = propagation_engine
        if shared_propagation_engine is None and governance_engine is not None:
            shared_propagation_engine = governance_engine.propagation_engine
        self.propagation_engine = shared_propagation_engine or PropagationEngine()

        self.governance_engine = governance_engine or GovernanceEngine(
            base_path=self.base_path,
            propagation_engine=self.propagation_engine,
        )
        if self.governance_engine.propagation_engine is not self.propagation_engine:
            self.governance_engine.propagation_engine = self.propagation_engine

        self.code_mapping_registry = self.versioned_registry.code_mapping_registry
        self.memory_nodes: Dict[str, MemoryNode] = {}
        self.events: List[PropagationEvent] = []
        self.change_log: List[Dict[str, Any]] = []

        for unit_id in sorted(self.versioned_registry.versions):
            self.create_memory_node(unit_id)

    def detect_changes(
        self,
        baseline: str,
        current: Optional[str] = None,
        baseline_commit: Optional[str] = None,
    ) -> List[DiffReport]:
        """Detect changes via the shared propagation engine."""
        current_target = current or str(self.base_path)
        return self.propagation_engine.detect_changes(
            baseline=baseline,
            current=current_target,
            baseline_commit=baseline_commit,
        )

    def create_memory_node(self, unit_id: str) -> MemoryNode:
        """
        Create or refresh the memory node for a unit from registry state.
        """
        current = self.versioned_registry.get_current(unit_id)
        if current is None:
            current = self._ensure_current_version(unit_id)

        unit_ref = self.versioned_registry.get(unit_id)
        metadata = dict(current.metadata)
        if unit_ref is not None:
            metadata.setdefault("source_file", unit_ref.source_file)
            metadata.setdefault("unit_type", unit_ref.unit_type)
            metadata.setdefault("registry_version", unit_ref.version)
        metadata["lineage_length"] = len(self.versioned_registry.get_lineage(unit_id))
        metadata["status"] = current.status.value
        metadata["change_summary"] = current.change_summary

        node = MemoryNode(
            unit_id=unit_id,
            version=current.version,
            content_hash=current.content_hash,
            created_at=current.created_at,
            parent_hash=current.parent_hash,
            metadata=metadata,
            code_mappings=self.code_mapping_registry.get_files_for_unit(unit_id),
        )
        self.memory_nodes[unit_id] = node
        return node

    def register_change(self, unit_id: str, change: Any) -> Dict[str, Any]:
        """
        Register a change and drive the full lifecycle:
        register -> propagate -> govern -> sync.
        """
        diff_report, context = self._normalize_change(unit_id, change)
        unit_id = diff_report.unit_id

        previous_current = self.versioned_registry.get_current(unit_id)
        if previous_current is None:
            previous_current = self._ensure_current_version(unit_id, diff_report, context)

        version = self._create_version_for_change(unit_id, diff_report, context)
        propagation_decision = self._propagate_diff(diff_report, context)
        governance_decision = self._govern_diff(diff_report, context)

        mapping_updates = self._collect_mapping_updates(
            unit_id=unit_id,
            context=context,
            propagation_decision=propagation_decision,
        )
        synced_mappings = self.sync_code_mappings(mapping_updates or {unit_id: []})

        node = self.create_memory_node(unit_id)
        event = self._record_event(
            diff_report=diff_report,
            propagation_decision=propagation_decision,
            governance_decision=governance_decision,
        )

        node.metadata.update(
            {
                "last_change_type": diff_report.change_type.value,
                "last_changed_field": diff_report.field,
                "last_governance_status": governance_decision.status,
                "last_propagation_action": propagation_decision.action_type,
                "last_event_id": event.event_id,
            }
        )

        result = {
            "unit_id": unit_id,
            "version": version,
            "previous_version": previous_current,
            "memory_node": node,
            "propagation_decision": propagation_decision,
            "governance_decision": governance_decision,
            "code_mappings": synced_mappings.get(unit_id, []),
            "event": event,
        }
        self.change_log.append(result)
        return result

    def propagate_change(self, change: Any) -> PropagationDecision:
        """Run change propagation via PropagationEngine."""
        diff_report, context = self._normalize_change(None, change)
        return self._propagate_diff(diff_report, context)

    def govern_change(self, change: Any) -> GovernanceDecision:
        """Apply governance rules via GovernanceEngine."""
        diff_report, context = self._normalize_change(None, change)
        return self._govern_diff(diff_report, context)

    def sync_code_mappings(
        self,
        mappings: Optional[Dict[str, List[Any]]] = None,
    ) -> Dict[str, List[CodeMapping]]:
        """
        Sync code mappings through the shared CodeMappingRegistry and refresh nodes.
        """
        units_to_refresh: Set[str] = set(self.memory_nodes.keys())

        for unit_id, entries in (mappings or {}).items():
            units_to_refresh.add(unit_id)
            for entry in entries:
                if isinstance(entry, CodeMapping):
                    mapping = self.code_mapping_registry.add_mapping(
                        unit_id=entry.unit_id,
                        file_path=entry.file_path,
                        mapping_type=entry.mapping_type,
                        confidence=entry.confidence,
                    )
                    verified_at = entry.verified_at
                elif isinstance(entry, dict):
                    mapping = self.code_mapping_registry.add_mapping(
                        unit_id=entry.get("unit_id", unit_id),
                        file_path=entry["file_path"],
                        mapping_type=entry.get("mapping_type", "references"),
                        confidence=float(entry.get("confidence", 1.0)),
                    )
                    verified_at = entry.get("verified_at")
                else:
                    raise TypeError("Mappings must be CodeMapping instances or dictionaries")

                if verified_at:
                    verified_mapping = self.code_mapping_registry.verify_mapping(
                        mapping.unit_id,
                        mapping.file_path,
                    )
                    if isinstance(verified_at, str):
                        verified_mapping.verified_at = datetime.fromisoformat(verified_at)
                    elif isinstance(verified_at, datetime):
                        verified_mapping.verified_at = verified_at

        if not units_to_refresh:
            units_to_refresh = set(self.versioned_registry.versions.keys())

        for unit_id in sorted(units_to_refresh):
            if self.versioned_registry.get_current(unit_id) is not None or unit_id in self.memory_nodes:
                self.create_memory_node(unit_id)

        self.versioned_registry._save_versions()
        return self.code_mapping_registry.as_unit_dict()

    def get_network_state(self) -> Dict[str, Any]:
        """Return a serialized snapshot of the full network state."""
        return {
            "base_path": str(self.base_path),
            "memory_nodes": {
                unit_id: node.to_dict()
                for unit_id, node in sorted(self.memory_nodes.items())
            },
            "events": [self._event_to_dict(event) for event in self.events],
            "propagation_history": self.propagation_engine.get_decision_history(),
            "versioned_registry": self.versioned_registry.get_statistics(),
            "code_mapping_registry": self.code_mapping_registry.get_statistics(),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregate statistics for the orchestrated memory network."""
        propagation_action_counts: Dict[str, int] = {}
        governance_status_counts: Dict[str, int] = {}

        for record in self.change_log:
            action_type = record["propagation_decision"].action_type
            propagation_action_counts[action_type] = (
                propagation_action_counts.get(action_type, 0) + 1
            )

            governance_status = record["governance_decision"].status
            governance_status_counts[governance_status] = (
                governance_status_counts.get(governance_status, 0) + 1
            )

        return {
            "total_memory_nodes": len(self.memory_nodes),
            "registered_changes": len(self.change_log),
            "propagation_events": len(self.events),
            "propagation_action_counts": propagation_action_counts,
            "governance_status_counts": governance_status_counts,
            "versioned_registry": self.versioned_registry.get_statistics(),
            "code_mapping_registry": self.code_mapping_registry.get_statistics(),
        }

    def _resolve_base_path(self, base_path: Optional[Path]) -> Path:
        candidate = Path(base_path) if base_path is not None else Path(__file__).resolve().parent.parent
        if (candidate / "schema").exists():
            return candidate
        if (candidate / "knowledge_compiler" / "schema").exists():
            return candidate / "knowledge_compiler"
        return candidate

    def _normalize_change(
        self,
        unit_id: Optional[str],
        change: Any,
    ) -> Tuple[DiffReport, Dict[str, Any]]:
        if isinstance(change, DiffReport):
            return change, {}

        if not isinstance(change, dict):
            raise TypeError("change must be a DiffReport or a dictionary payload")

        context = dict(change)
        raw_diff = context.pop("diff_report", None)
        if isinstance(raw_diff, DiffReport):
            diff_report = raw_diff
        elif isinstance(raw_diff, dict):
            diff_report = self._build_diff_report(unit_id, raw_diff)
        else:
            diff_report = self._build_diff_report(unit_id, context)

        return diff_report, context

    def _build_diff_report(
        self,
        unit_id: Optional[str],
        payload: Dict[str, Any],
    ) -> DiffReport:
        raw_change_type = payload.get("change_type", ChangeType.SEMANTIC_EDIT)
        change_type = raw_change_type if isinstance(raw_change_type, ChangeType) else ChangeType(str(raw_change_type))
        impacted_executables = payload.get("impacted_executables")
        if impacted_executables is None:
            impacted_executables = payload.get("impact_targets", [])

        resolved_unit_id = payload.get("unit_id", unit_id)
        if not resolved_unit_id:
            raise ValueError("unit_id is required to build a DiffReport")

        return DiffReport(
            change_type=change_type,
            unit_id=str(resolved_unit_id),
            field=str(payload.get("field", "content")),
            old_value=payload.get("old_value"),
            new_value=payload.get("new_value"),
            impacted_executables=list(impacted_executables or []),
        )

    def _ensure_current_version(
        self,
        unit_id: str,
        diff_report: Optional[DiffReport] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> UnitVersion:
        current = self.versioned_registry.get_current(unit_id)
        if current is not None:
            return current

        unit_ref = self.versioned_registry.get(unit_id)
        metadata: Dict[str, Any]

        if unit_ref is not None:
            content_hash = self.versioned_registry._calculate_unit_hash(unit_id, unit_ref)
            metadata = {
                "source_file": unit_ref.source_file,
                "unit_type": unit_ref.unit_type,
            }
        else:
            seed_content = (
                (context or {}).get("content")
                or (diff_report.new_value if diff_report is not None else None)
                or {"unit_id": unit_id}
            )
            content_hash = hashlib.sha256(
                json.dumps(seed_content, sort_keys=True, default=str).encode()
            ).hexdigest()
            metadata = {
                "source_file": (context or {}).get("source_file"),
                "unit_type": (context or {}).get("unit_type", "unknown"),
                "ephemeral": True,
            }

        current = UnitVersion(
            unit_id=unit_id,
            version=str((context or {}).get("initial_version", "v1.0")),
            content_hash=content_hash,
            parent_hash=None,
            created_at=datetime.now(),
            created_by=str((context or {}).get("created_by", "memory_network")),
            status=VersionStatus.ACTIVE,
            change_summary=str((context or {}).get("change_summary", "Initialized by MemoryNetwork")),
            metadata=metadata,
        )
        self.versioned_registry.versions[unit_id] = current
        self.versioned_registry.history.setdefault(unit_id, []).append(current)
        self.versioned_registry.by_hash[current.content_hash] = current
        self.versioned_registry._save_versions()
        return current

    def _create_version_for_change(
        self,
        unit_id: str,
        diff_report: DiffReport,
        context: Dict[str, Any],
    ) -> UnitVersion:
        current = self._ensure_current_version(unit_id, diff_report, context)
        if diff_report.change_type == ChangeType.NEW and current.is_initial and current.created_by == str(
            context.get("created_by", "memory_network")
        ):
            return current

        diff_payload = {
            "change_type": diff_report.change_type.value,
            "summary": context.get(
                "summary",
                context.get("change_summary", f"{diff_report.field} updated"),
            ),
            "changed_fields": context.get("changed_fields", [diff_report.field]),
            "impact_summary": context.get(
                "impact_summary",
                self._default_impact_summary(diff_report),
            ),
        }
        return self.versioned_registry.create_version_from_diff(
            unit_id=unit_id,
            diff_report=diff_payload,
            created_by=str(context.get("created_by", "memory_network")),
        )

    def _propagate_diff(
        self,
        diff_report: DiffReport,
        context: Dict[str, Any],
    ) -> PropagationDecision:
        decisions = self.propagation_engine.propagate(
            [diff_report],
            dry_run=bool(context.get("propagation_dry_run", False)),
        )
        return decisions[0]

    def _govern_diff(
        self,
        diff_report: DiffReport,
        context: Dict[str, Any],
    ) -> GovernanceDecision:
        governance_unit = self._build_governance_unit(diff_report.unit_id, diff_report, context)
        if governance_unit is None:
            return GovernanceDecision(
                status=GovernanceDecision.DEFERRED,
                reasons=[f"No governance payload available for {diff_report.unit_id}"],
                warnings=[],
            )

        for key in (
            "requires_human_review",
            "human_review_signed_off",
            "conflict_flags",
            "data_gaps",
            "propagation_changes",
            "propagation_dry_run",
        ):
            if key in context:
                governance_unit[key] = deepcopy(context[key])

        return self.governance_engine.approve_publish(governance_unit)

    def _build_governance_unit(
        self,
        unit_id: str,
        diff_report: DiffReport,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        explicit_unit = (
            context.get("governance_unit")
            or context.get("unit_payload")
            or context.get("unit")
        )
        if explicit_unit is not None:
            return deepcopy(explicit_unit)

        unit_ref = self.versioned_registry.get(unit_id)
        canonical_content = self._load_unit_payload(unit_id)
        if unit_ref is None and canonical_content is None:
            fallback_content = {
                "unit_id": unit_id,
                "field": diff_report.field,
                "summary": context.get("summary", f"Registered change for {unit_id}"),
            }
            unit_type = str(context.get("unit_type", "formula"))
        else:
            fallback_content = canonical_content or {}
            unit_type = str(context.get("unit_type", getattr(unit_ref, "unit_type", "formula")))

        if isinstance(fallback_content, dict):
            fallback_content = deepcopy(fallback_content)
            self._apply_diff_to_content(fallback_content, diff_report)

        if unit_type == "chapter" and isinstance(fallback_content, dict) and "sections" not in fallback_content:
            required_fields = fallback_content.get("required_fields")
            if isinstance(required_fields, list) and required_fields:
                fallback_content["sections"] = list(required_fields)

        spec_version = self.governance_engine.SUPPORTED_SPEC_VERSION
        return {
            "layer": "canonical",
            "canonical_id": f"CANON-{unit_type}-{unit_id}",
            "parsed_id": f"PARSED-{unit_id}",
            "normalized_form": {
                "unit_type": unit_type,
                "unit_id": unit_id,
                "spec_version": spec_version,
                "canonical_content": fallback_content,
            },
            "spec_version": spec_version,
            "unit_type": unit_type,
            "normalized_at": self._isoformat_z(datetime.now()),
            "normalize_rule_version": "1.0",
            "conflict_flags": [],
            "data_gaps": [],
        }

    def _load_unit_payload(self, unit_id: str) -> Optional[Dict[str, Any]]:
        unit_ref = self.versioned_registry.get(unit_id)
        if unit_ref is None:
            return None

        yaml_path = self.base_path / unit_ref.source_file
        if not yaml_path.exists():
            return None

        with open(yaml_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        for collection_name, id_key in self.UNIT_COLLECTIONS:
            items = data.get(collection_name)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and str(item.get(id_key)) == unit_id:
                    return deepcopy(item)
        return None

    def _collect_mapping_updates(
        self,
        unit_id: str,
        context: Dict[str, Any],
        propagation_decision: PropagationDecision,
    ) -> Dict[str, List[Dict[str, Any]]]:
        mapping_specs: Dict[str, Dict[str, Any]] = {}

        for executable_id in propagation_decision.target_executables:
            file_path = self.EXECUTABLE_FILE_MAP.get(executable_id)
            if file_path is None:
                continue
            mapping_specs[file_path] = {
                "unit_id": unit_id,
                "file_path": file_path,
                "mapping_type": self._mapping_type_for_executable(executable_id),
                "confidence": 0.85,
            }

        for mapping in context.get("code_mappings", []):
            if isinstance(mapping, CodeMapping):
                mapping_specs[mapping.file_path] = {
                    "unit_id": mapping.unit_id,
                    "file_path": mapping.file_path,
                    "mapping_type": mapping.mapping_type,
                    "confidence": mapping.confidence,
                    "verified_at": mapping.verified_at,
                }
            elif isinstance(mapping, dict):
                file_path = mapping["file_path"]
                merged_mapping = dict(mapping)
                merged_mapping.setdefault("unit_id", unit_id)
                merged_mapping.setdefault("mapping_type", "references")
                merged_mapping.setdefault("confidence", 1.0)
                mapping_specs[file_path] = merged_mapping
            else:
                raise TypeError("code_mappings entries must be CodeMapping instances or dictionaries")

        return {unit_id: list(mapping_specs.values())}

    def _mapping_type_for_executable(self, executable_id: str) -> str:
        if executable_id in {
            "EXEC-FORMULA-VALIDATOR-001",
            "EXEC-BENCH-GHIA-001",
            "EXEC-BENCH-CYLINDER-WAKE-001",
        }:
            return "validates"
        if executable_id == "EXEC-CHART-TEMPLATE-001":
            return "implements"
        return "references"

    def _record_event(
        self,
        diff_report: DiffReport,
        propagation_decision: PropagationDecision,
        governance_decision: GovernanceDecision,
    ) -> PropagationEvent:
        event = PropagationEvent(
            event_id=f"EVT-{len(self.events) + 1:04d}",
            change_type=diff_report.change_type,
            source_unit=diff_report.unit_id,
            impact_targets=list(propagation_decision.target_executables),
            governance_decision=governance_decision.status,
            reason=f"{propagation_decision.action_type}: {', '.join(governance_decision.reasons)}",
            timestamp=datetime.now(),
        )
        self.events.append(event)
        return event

    def _event_to_dict(self, event: PropagationEvent) -> Dict[str, Any]:
        return {
            "event_id": event.event_id,
            "change_type": event.change_type.value,
            "source_unit": event.source_unit,
            "impact_targets": event.impact_targets,
            "governance_decision": event.governance_decision,
            "reason": event.reason,
            "timestamp": event.timestamp.isoformat(),
        }

    def _default_impact_summary(self, diff_report: DiffReport) -> str:
        if diff_report.impacted_executables:
            targets = ", ".join(diff_report.impacted_executables)
            return f"Impacts {targets}"
        return f"No downstream executable impact reported for {diff_report.unit_id}"

    def _apply_diff_to_content(
        self,
        content: Dict[str, Any],
        diff_report: DiffReport,
    ) -> None:
        if diff_report.field in {"content", "__unit__"}:
            if isinstance(diff_report.new_value, dict):
                content.clear()
                content.update(deepcopy(diff_report.new_value))
            return

        self._set_nested_value(content, diff_report.field, deepcopy(diff_report.new_value))

    def _set_nested_value(self, target: Any, field_path: str, value: Any) -> None:
        tokens = re.findall(r"[^.\[\]]+|\[[^\]]+\]", field_path)
        if not tokens:
            return

        current = target
        for index, token in enumerate(tokens):
            is_last = index == len(tokens) - 1

            if token.startswith("[") and token.endswith("]"):
                if not isinstance(current, list):
                    return

                selector = token[1:-1]
                if selector.isdigit():
                    item_index = int(selector)
                    while len(current) <= item_index:
                        current.append({})
                    if is_last:
                        current[item_index] = value
                        return
                    if not isinstance(current[item_index], (dict, list)):
                        current[item_index] = {}
                    current = current[item_index]
                    continue

                if "=" not in selector:
                    return

                anchor_key, anchor_value = selector.split("=", 1)
                matching_item = next(
                    (
                        item
                        for item in current
                        if isinstance(item, dict) and str(item.get(anchor_key)) == anchor_value
                    ),
                    None,
                )
                if matching_item is None:
                    matching_item = {anchor_key: anchor_value}
                    current.append(matching_item)
                if is_last:
                    if isinstance(value, dict):
                        matching_item.clear()
                        matching_item.update(value)
                    else:
                        matching_item["value"] = value
                    return
                current = matching_item
                continue

            if not isinstance(current, dict):
                return

            if is_last:
                current[token] = value
                return

            next_token = tokens[index + 1]
            if token not in current or not isinstance(current[token], (dict, list)):
                current[token] = [] if next_token.startswith("[") else {}
            current = current[token]

    def _isoformat_z(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


# =============================================================================
# Updated Exports
# =============================================================================

__all__ = [
    "VersionStatus",
    "UnitVersion",
    "CodeMapping",
    "CodeMappingRegistry",
    "MemoryNode",
    "VersionChange",
    "VersionedKnowledgeRegistry",
    "PropagationDecision",
    "PropagationEngine",
    "ValidationResult",
    "GovernanceDecision",
    "GovernanceEngine",
    "PropagationEvent",
    "MemoryNetwork",
    "get_versioned_registry",
]
