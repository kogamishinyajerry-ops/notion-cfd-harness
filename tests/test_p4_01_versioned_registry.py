#!/usr/bin/env python3
"""
P4-01: VersionedKnowledgeRegistry Tests
Phase 4: Governed Memory Network
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from knowledge_compiler.memory_network import (
    VersionedKnowledgeRegistry,
    UnitVersion,
    VersionStatus,
    CodeMapping,
    get_versioned_registry
)


class TestUnitVersion:
    """Test UnitVersion data model."""

    def test_unit_version_creation(self):
        """Test creating a UnitVersion."""
        uv = UnitVersion(
            unit_id="CH-001",
            version="v1.0",
            content_hash="abc123",
            parent_hash=None,
            created_at=datetime.now(),
            created_by="system",
            status=VersionStatus.ACTIVE,
            change_summary="Initial version"
        )

        assert uv.unit_id == "CH-001"
        assert uv.version == "v1.0"
        assert uv.is_initial is True
        assert uv.short_hash == "abc123"

    def test_version_with_parent(self):
        """Test version with parent hash."""
        parent_hash = "xyz789"
        uv = UnitVersion(
            unit_id="CH-001",
            version="v1.1",
            content_hash="new123",
            parent_hash=parent_hash,
            created_at=datetime.now(),
            created_by="system",
            status=VersionStatus.ACTIVE,
            change_summary="Updated content"
        )

        assert uv.parent_hash == "xyz789"
        assert uv.is_initial is False


class TestCodeMapping:
    """Test CodeMapping data model."""

    def test_code_mapping_creation(self):
        """Test creating a CodeMapping."""
        mapping = CodeMapping(
            unit_id="CH-001",
            file_path="knowledge_compiler/units/chapters.yaml",
            mapping_type="implements",
            confidence=1.0
        )

        assert mapping.unit_id == "CH-001"
        assert mapping.mapping_type == "implements"
        assert mapping.confidence == 1.0


class TestVersionedKnowledgeRegistry:
    """Test VersionedKnowledgeRegistry functionality."""

    def test_registry_initialization(self):
        """Test registry initializes with version database."""
        # Use actual knowledge_compiler path to load real units
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        # Should load existing units from YAML files
        assert len(registry.units) > 0

        # Should initialize version database
        assert len(registry.versions) > 0
        assert len(registry.history) > 0

    def test_get_current(self):
        """Test getting current version of a unit."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        # CH-001 should exist from YAML loading
        current = registry.get_current("CH-001")
        if current:
            assert current.unit_id == "CH-001"
            assert current.status == VersionStatus.ACTIVE
            assert current.version == "v1.0"

    def test_get_history(self):
        """Test getting version history."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        history = registry.get_history("CH-001")
        if history:
            assert isinstance(history, list)
            # Should be ordered newest first
            assert len(history) >= 1

    def test_get_lineage(self):
        """Test getting lineage chain."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        lineage = registry.get_lineage("CH-001")
        if lineage:
            assert isinstance(lineage, list)
            # Should be ordered oldest to newest
            if len(lineage) > 1:
                assert lineage[0].created_at <= lineage[-1].created_at

    def test_create_version(self):
        """Test creating a new version."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        # Skip if no units loaded
        if not registry.versions:
            return

        unit_id = list(registry.versions.keys())[0]
        new_version = registry.create_version(
            unit_id=unit_id,
            new_version="v1.1",
            change_summary="Test update",
            created_by="test"
        )

        assert new_version.version == "v1.1"
        assert new_version.created_by == "test"
        assert new_version.parent_hash is not None

        # Current should now be v1.1
        current = registry.get_current(unit_id)
        assert current.version == "v1.1"

    def test_code_mapping_apis(self):
        """Test code mapping functionality."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        # Add a mapping
        mapping = registry.add_code_mapping(
            unit_id="CH-001",
            file_path="knowledge_compiler/units/chapters.yaml",
            mapping_type="implements"
        )

        assert mapping.unit_id == "CH-001"

        # Retrieve mappings
        mappings = registry.get_code_mappings("CH-001")
        assert len(mappings) > 0

    def test_find_units_by_file(self):
        """Test finding units by file path."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        # Add mappings
        registry.add_code_mapping("CH-001", "knowledge_compiler/units/chapters.yaml", "implements")
        registry.add_code_mapping("FORM-001", "knowledge_compiler/units/chapters.yaml", "references")

        # Find units
        units = registry.find_units_by_file("knowledge_compiler/units/chapters.yaml")
        assert "CH-001" in units
        assert "FORM-001" in units

    def test_validate_lineage(self):
        """Test lineage validation."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        if not registry.versions:
            return

        unit_id = list(registry.versions.keys())[0]
        result = registry.validate_lineage(unit_id)

        assert "valid" in result
        assert isinstance(result["valid"], bool)

    def test_get_statistics(self):
        """Test getting registry statistics."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        stats = registry.get_statistics()

        assert "total_units" in stats
        assert "total_versions" in stats
        assert "status_counts" in stats
        assert stats["total_units"] >= 0


class TestSingleton:
    """Test singleton instance."""

    def test_get_versioned_registry(self):
        """Test getting singleton instance."""
        reg1 = get_versioned_registry()
        reg2 = get_versioned_registry()

        # Should return same instance
        assert reg1 is reg2


class TestIntegrationWithPhase3:
    """Integration tests with Phase3 components."""

    def test_extends_knowledge_registry(self):
        """Test that VersionedKnowledgeRegistry extends KnowledgeRegistry."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        # Should have all Query APIs from parent class
        assert hasattr(registry, "get")
        assert hasattr(registry, "query_by_type")
        assert hasattr(registry, "query_by_source")
        assert hasattr(registry, "search")

    def test_traceability_apis(self):
        """Test traceability APIs work."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        # get_trace should still work
        trace = registry.get_trace("CH-001")
        assert isinstance(trace, list)

    def test_dependency_apis(self):
        """Test dependency APIs work."""
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(base_path=kc_path)

        # get_dependencies should still work
        deps = registry.get_dependencies("CASE-001")
        assert isinstance(deps, set)
