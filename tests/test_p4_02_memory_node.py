#!/usr/bin/env python3
"""
Test P4-02: MemoryNode 数据模型

Tests the MemoryNode dataclass which represents knowledge unit states
in the governed memory network.
"""

import pytest
from datetime import datetime
from knowledge_compiler.memory_network import MemoryNode


class TestMemoryNodeBasics:
    """测试 MemoryNode 基本功能"""

    def test_create_memory_node(self):
        """测试创建基本的 MemoryNode"""
        node = MemoryNode(
            unit_id="CH-001",
            version="v1.0",
            content_hash="abc123def4567890",
            created_at=datetime(2026, 4, 7, 12, 0, 0),
            parent_hash=None,
            metadata={"source": "human"},
            code_mappings=["src/rules/ch_001.py"]
        )

        assert node.unit_id == "CH-001"
        assert node.version == "v1.0"
        assert node.content_hash == "abc123def4567890"
        assert node.parent_hash is None
        assert node.metadata == {"source": "human"}
        assert node.code_mappings == ["src/rules/ch_001.py"]

    def test_memory_node_with_parent(self):
        """测试带有父节点的 MemoryNode"""
        node = MemoryNode(
            unit_id="CH-001",
            version="v1.1",
            content_hash="newhash4567890123",
            created_at=datetime(2026, 4, 7, 14, 0, 0),
            parent_hash="abc123def4567890",
            metadata={"source": "ai_review"},
            code_mappings=["src/rules/ch_001.py", "tests/test_ch_001.py"]
        )

        assert node.parent_hash == "abc123def4567890"
        assert not node.is_initial
        assert len(node.code_mappings) == 2


class TestMemoryNodeProperties:
    """测试 MemoryNode 属性"""

    def test_short_hash(self):
        """测试 short_hash 属性"""
        node = MemoryNode(
            unit_id="CH-001",
            version="v1.0",
            content_hash="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            created_at=datetime.now(),
            parent_hash=None,
            metadata={},
            code_mappings=[]
        )

        assert node.short_hash == "abcdef12"
        assert len(node.short_hash) == 8

    def test_is_initial_true(self):
        """测试 is_initial 属性 - 初始版本"""
        node = MemoryNode(
            unit_id="CH-001",
            version="v1.0",
            content_hash="hash123",
            created_at=datetime.now(),
            parent_hash=None,
            metadata={},
            code_mappings=[]
        )

        assert node.is_initial is True

    def test_is_initial_false(self):
        """测试 is_initial 属性 - 非初始版本"""
        node = MemoryNode(
            unit_id="CH-001",
            version="v1.1",
            content_hash="hash456",
            created_at=datetime.now(),
            parent_hash="hash123",
            metadata={},
            code_mappings=[]
        )

        assert node.is_initial is False


class TestMemoryNodeSerialization:
    """测试 MemoryNode 序列化"""

    def test_to_dict(self):
        """测试 to_dict 方法"""
        created_at = datetime(2026, 4, 7, 12, 30, 45)
        node = MemoryNode(
            unit_id="CH-002",
            version="v2.0",
            content_hash="xyz789abc456def123",
            created_at=created_at,
            parent_hash="oldhash123",
            metadata={"reviewer": "Opus 4.6", "confidence": 0.95},
            code_mappings=["src/core/engine.py"]
        )

        result = node.to_dict()

        assert result["unit_id"] == "CH-002"
        assert result["version"] == "v2.0"
        assert result["content_hash"] == "xyz789abc456def123"
        assert result["parent_hash"] == "oldhash123"
        assert result["created_at"] == "2026-04-07T12:30:45"
        assert result["metadata"] == {"reviewer": "Opus 4.6", "confidence": 0.95}
        assert result["code_mappings"] == ["src/core/engine.py"]

    def test_from_dict(self):
        """测试 from_dict 方法"""
        data = {
            "unit_id": "CH-003",
            "version": "v1.5",
            "content_hash": "987fedcba6543210",
            "created_at": "2026-04-07T15:20:10",
            "parent_hash": "previoushash",
            "metadata": {"source": "codex"},
            "code_mappings": ["src/validators.py", "src/models.py"]
        }

        node = MemoryNode.from_dict(data)

        assert node.unit_id == "CH-003"
        assert node.version == "v1.5"
        assert node.content_hash == "987fedcba6543210"
        assert node.parent_hash == "previoushash"
        assert node.metadata == {"source": "codex"}
        assert node.code_mappings == ["src/validators.py", "src/models.py"]
        assert isinstance(node.created_at, datetime)

    def test_roundtrip_serialization(self):
        """测试序列化往返"""
        original = MemoryNode(
            unit_id="CH-004",
            version="v3.0",
            content_hash="roundtrip123",
            created_at=datetime(2026, 4, 7, 10, 15, 30),
            parent_hash="prevhash",
            metadata={"key": "value"},
            code_mappings=["a.py", "b.py"]
        )

        # Serialize
        data = original.to_dict()

        # Deserialize
        restored = MemoryNode.from_dict(data)

        # Verify equality
        assert restored.unit_id == original.unit_id
        assert restored.version == original.version
        assert restored.content_hash == original.content_hash
        assert restored.parent_hash == original.parent_hash
        assert restored.metadata == original.metadata
        assert restored.code_mappings == original.code_mappings


class TestMemoryNodeEdgeCases:
    """测试边缘情况"""

    def test_empty_code_mappings(self):
        """测试空的代码映射列表"""
        node = MemoryNode(
            unit_id="CH-EMPTY",
            version="v1.0",
            content_hash="empty123",
            created_at=datetime.now(),
            parent_hash=None,
            metadata={},
            code_mappings=[]
        )

        assert node.code_mappings == []
        assert len(node.code_mappings) == 0

    def test_empty_metadata(self):
        """测试空的元数据字典"""
        node = MemoryNode(
            unit_id="CH-NOMETA",
            version="v1.0",
            content_hash="nometa123",
            created_at=datetime.now(),
            parent_hash=None,
            metadata={},
            code_mappings=["src/test.py"]
        )

        assert node.metadata == {}

    def test_complex_metadata(self):
        """测试复杂的嵌套元数据"""
        complex_meta = {
            "review": {
                "reviewer": "Opus 4.6",
                "timestamp": "2026-04-07T12:00:00",
                "comments": ["Good", "Needs improvement"]
            },
            "metrics": {
                "accuracy": 0.95,
                "coverage": 0.87
            },
            "tags": ["critical", "chapter-1"]
        }

        node = MemoryNode(
            unit_id="CH-COMPLEX",
            version="v1.0",
            content_hash="complex123",
            created_at=datetime.now(),
            parent_hash=None,
            metadata=complex_meta,
            code_mappings=[]
        )

        assert node.metadata == complex_meta


class TestMemoryNodeDefaults:
    """测试默认值和可选字段"""

    def test_parent_hash_defaults_to_none(self):
        """测试 parent_hash 默认为 None"""
        node = MemoryNode(
            unit_id="CH-DEFAULT",
            version="v1.0",
            content_hash="default123",
            created_at=datetime.now(),
            parent_hash=None,
            metadata={},
            code_mappings=[]
        )

        assert node.parent_hash is None
        assert node.is_initial is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
