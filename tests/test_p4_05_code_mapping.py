#!/usr/bin/env python3
"""
P4-05: CodeMappingRegistry Tests
Phase 4: Governed Memory Network
"""

from datetime import datetime
from pathlib import Path

import pytest

from knowledge_compiler.memory_network import (
    CodeMapping,
    CodeMappingRegistry,
    VersionedKnowledgeRegistry,
)


class TestCodeMappingRegistry:
    """Test bidirectional code mapping behavior."""

    def test_add_mapping_supports_bidirectional_queries(self):
        registry = CodeMappingRegistry()

        mapping = registry.add_mapping(
            unit_id="CH-001",
            file_path="src/rules/ch_001.py",
            mapping_type="implements",
            confidence=0.95,
        )
        registry.add_mapping(
            unit_id="CH-001",
            file_path="tests/test_ch_001.py",
            mapping_type="validates",
            confidence=0.85,
        )
        registry.add_mapping(
            unit_id="FORM-001",
            file_path="src/rules/ch_001.py",
            mapping_type="references",
            confidence=0.60,
        )

        assert mapping.verified_at is None
        assert registry.get_files_for_unit("CH-001") == [
            "src/rules/ch_001.py",
            "tests/test_ch_001.py",
        ]
        assert registry.get_units_for_file("src/rules/ch_001.py") == [
            "CH-001",
            "FORM-001",
        ]

    def test_remove_mapping_updates_both_indexes(self):
        registry = CodeMappingRegistry()
        registry.add_mapping("CH-001", "src/rules/ch_001.py", "implements", 0.95)
        registry.add_mapping("FORM-001", "src/rules/ch_001.py", "references", 0.60)

        assert registry.remove_mapping("CH-001", "src/rules/ch_001.py") is True
        assert registry.get_files_for_unit("CH-001") == []
        assert registry.get_units_for_file("src/rules/ch_001.py") == ["FORM-001"]
        assert registry.remove_mapping("CH-001", "src/rules/ch_001.py") is False

    def test_find_units_by_pattern_supports_glob_and_substring(self):
        registry = CodeMappingRegistry()
        registry.add_mapping("CH-001", "src/rules/ch_001.py", "implements", 0.95)
        registry.add_mapping("CH-002", "src/rules/ch_002.py", "implements", 0.90)
        registry.add_mapping("VAL-001", "src/validators/chapter_validator.py", "validates", 0.88)

        assert registry.find_units_by_pattern("src/rules/*.py") == ["CH-001", "CH-002"]
        assert registry.find_units_by_pattern("validators") == ["VAL-001"]

    def test_verify_mapping_marks_mapping_as_verified(self):
        registry = CodeMappingRegistry()
        registry.add_mapping("CH-001", "src/rules/ch_001.py", "implements", 0.95)

        verified = registry.verify_mapping("CH-001", "src/rules/ch_001.py")

        assert verified.verified_at is not None
        file_mappings = registry.get_mappings_for_file("src/rules/ch_001.py")
        assert len(file_mappings) == 1
        assert file_mappings[0].verified_at == verified.verified_at

    def test_duplicate_add_updates_existing_mapping_without_duplication(self):
        registry = CodeMappingRegistry()
        registry.add_mapping("CH-001", "src/rules/ch_001.py", "references", 0.40)
        registry.verify_mapping("CH-001", "src/rules/ch_001.py")

        updated = registry.add_mapping("CH-001", "src/rules/ch_001.py", "implements", 0.92)

        assert updated.mapping_type == "implements"
        assert updated.confidence == 0.92
        assert updated.verified_at is None
        assert registry.get_statistics()["total_mappings"] == 1

    def test_load_mappings_preserves_verification_state(self):
        verified_at = datetime(2026, 4, 7, 12, 0, 0)
        registry = CodeMappingRegistry(
            {
                "CH-001": [
                    CodeMapping(
                        unit_id="CH-001",
                        file_path="src/rules/ch_001.py",
                        mapping_type="implements",
                        confidence=1.0,
                        verified_at=verified_at,
                    )
                ]
            }
        )

        mappings = registry.get_mappings_for_unit("CH-001")
        assert len(mappings) == 1
        assert mappings[0].verified_at == verified_at

    def test_get_statistics_reports_counts_and_confidence(self):
        registry = CodeMappingRegistry()
        registry.add_mapping("CH-001", "src/rules/ch_001.py", "implements", 0.90)
        registry.add_mapping("CH-001", "tests/test_ch_001.py", "validates", 0.80)
        registry.add_mapping("FORM-001", "src/rules/ch_001.py", "references", 0.70)
        registry.verify_mapping("CH-001", "src/rules/ch_001.py")

        stats = registry.get_statistics()

        assert stats["total_mappings"] == 3
        assert stats["total_units"] == 2
        assert stats["total_files"] == 2
        assert stats["mapping_type_counts"] == {
            "implements": 1,
            "validates": 1,
            "references": 1,
        }
        assert stats["verified_mappings"] == 1
        assert stats["unverified_mappings"] == 2
        assert stats["average_confidence"] == pytest.approx(0.80)

    def test_invalid_mapping_type_raises_error(self):
        registry = CodeMappingRegistry()

        with pytest.raises(ValueError, match="mapping_type"):
            registry.add_mapping("CH-001", "src/rules/ch_001.py", "invalid", 0.90)

    def test_invalid_confidence_raises_error(self):
        registry = CodeMappingRegistry()

        with pytest.raises(ValueError, match="confidence"):
            registry.add_mapping("CH-001", "src/rules/ch_001.py", "implements", 1.10)

    def test_verify_missing_mapping_raises_error(self):
        registry = CodeMappingRegistry()

        with pytest.raises(ValueError, match="Mapping not found"):
            registry.verify_mapping("CH-404", "missing.py")


class TestVersionedKnowledgeRegistryIntegration:
    """Test VersionedKnowledgeRegistry delegation to CodeMappingRegistry."""

    def test_versioned_registry_delegates_mapping_apis(self, tmp_path):
        kc_path = Path(__file__).parent.parent / "knowledge_compiler"
        registry = VersionedKnowledgeRegistry(
            base_path=kc_path,
            version_db_path=tmp_path / ".versions.json",
        )

        mapping = registry.add_code_mapping(
            unit_id="CH-001",
            file_path="knowledge_compiler/units/chapters.yaml",
            mapping_type="implements",
            confidence=0.93,
        )

        assert isinstance(registry.code_mapping_registry, CodeMappingRegistry)
        assert mapping.unit_id == "CH-001"
        assert registry.get_code_mappings("CH-001")[0].file_path == "knowledge_compiler/units/chapters.yaml"
        assert registry.find_units_by_file("knowledge_compiler/units/chapters.yaml") == ["CH-001"]
        assert registry.code_mappings["CH-001"][0].confidence == 0.93
