#!/usr/bin/env python3
"""
Well-Harness M2 四库 Schema 初始化。

采用两阶段建库：
1. 先创建标准字段（不含 cross-library relation）
2. 拿到 4 个数据库 ID 后回填 relation 字段
"""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"
PROJECT_PAGE_ID = "33bc6894-2bed-819d-822a-c2144bb95e97"


@dataclass(frozen=True)
class BaseLibrarySchema:
    database_title: str
    specific_fields: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def build_standard_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "name": {"title": {}},
            "version": {"rich_text": {}},
            "created_at": {"date": {}},
            "created_by": {"rich_text": {}},
            "modified_at": {"date": {}},
            "archived_at": {"date": {}},
            "content_hash": {"rich_text": {}},
            "content": {"rich_text": {}},
            "status": {
                "select": {
                    "options": [
                        {"name": "Draft", "color": "gray"},
                        {"name": "Active", "color": "green"},
                        {"name": "Superseded", "color": "orange"},
                        {"name": "Archived", "color": "red"},
                    ]
                }
            },
            "superseded_by_id": {"rich_text": {}},
            "immutable_hash": {"rich_text": {}},
            "evidence_type": {
                "select": {
                    "options": [
                        {"name": "GateCheck", "color": "blue"},
                        {"name": "ValidationReport", "color": "green"},
                        {"name": "RuleViolation", "color": "red"},
                        {"name": "KnowledgeBinding", "color": "yellow"},
                    ]
                }
            },
            "gate": {
                "select": {
                    "options": [
                        {"name": "G0", "color": "gray"},
                        {"name": "G1", "color": "blue"},
                        {"name": "G2", "color": "green"},
                        {"name": "G3", "color": "yellow"},
                        {"name": "G4", "color": "orange"},
                        {"name": "G5", "color": "pink"},
                        {"name": "G6", "color": "red"},
                    ]
                }
            },
        }

    def build_relation_fields(self, relation_targets: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        return {
            "related_cases": self._relation_property(relation_targets["case_library"]),
            "related_components": self._relation_property(relation_targets["component_library"]),
            "related_baselines": self._relation_property(relation_targets["baseline_library"]),
            "related_rules": self._relation_property(relation_targets["rule_library"]),
        }

    def build_create_properties(self) -> Dict[str, Dict[str, Any]]:
        properties = self.build_standard_fields()
        properties.update(deepcopy(self.specific_fields))
        return properties

    def build_full_properties(self, relation_targets: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        properties = self.build_create_properties()
        properties.update(self.build_relation_fields(relation_targets))
        return properties

    @staticmethod
    def _relation_property(database_id: str) -> Dict[str, Any]:
        return {
            "relation": {
                "database_id": database_id,
                "type": "single_property",
                "single_property": {},
            }
        }


@dataclass(frozen=True)
class ComponentLibrarySchema(BaseLibrarySchema):
    database_title: str = "Well-Component-Library"
    specific_fields: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "geometry_type": {"rich_text": {}},
            "cfd_solver": {"rich_text": {}},
            "mesh_count": {"number": {"format": "number"}},
            "boundary_conditions": {"rich_text": {}},
        }
    )


@dataclass(frozen=True)
class CaseLibrarySchema(BaseLibrarySchema):
    database_title: str = "Well-Case-Library"
    specific_fields: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "case_type": {"rich_text": {}},
            "solver_config": {"rich_text": {}},
            "validation_status": {
                "select": {
                    "options": [
                        {"name": "Pending", "color": "gray"},
                        {"name": "Validated", "color": "green"},
                        {"name": "Rejected", "color": "red"},
                    ]
                }
            },
            "reference_data": {"url": {}},
        }
    )


@dataclass(frozen=True)
class BaselineLibrarySchema(BaseLibrarySchema):
    database_title: str = "Well-Baseline-Library"
    specific_fields: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "baseline_type": {"rich_text": {}},
            "pressure_range": {"rich_text": {}},
            "velocity_range": {"rich_text": {}},
            "turbulence_model": {"rich_text": {}},
        }
    )


@dataclass(frozen=True)
class RuleLibrarySchema(BaseLibrarySchema):
    database_title: str = "Well-Rule-Library"
    specific_fields: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "rule_type": {"rich_text": {}},
            "constraint_scope": {"rich_text": {}},
            "binding_strength": {
                "select": {
                    "options": [
                        {"name": "Required", "color": "red"},
                        {"name": "Recommended", "color": "yellow"},
                        {"name": "Informational", "color": "blue"},
                    ]
                }
            },
            "applicable_phases": {"rich_text": {}},
        }
    )


class FourLibrarySchema:
    """四库 Schema 工厂。"""

    @staticmethod
    def init_component_library() -> ComponentLibrarySchema:
        return ComponentLibrarySchema()

    @staticmethod
    def init_case_library() -> CaseLibrarySchema:
        return CaseLibrarySchema()

    @staticmethod
    def init_baseline_library() -> BaselineLibrarySchema:
        return BaselineLibrarySchema()

    @staticmethod
    def init_rule_library() -> RuleLibrarySchema:
        return RuleLibrarySchema()


def create_four_library_databases(notion_api_key: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    api_key = notion_api_key or NOTION_API_KEY
    if not api_key:
        raise RuntimeError("NOTION_API_KEY 未配置，无法初始化四库")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    factory = FourLibrarySchema()
    schemas = {
        "component_library": factory.init_component_library(),
        "case_library": factory.init_case_library(),
        "baseline_library": factory.init_baseline_library(),
        "rule_library": factory.init_rule_library(),
    }

    created: Dict[str, Dict[str, Any]] = {}

    for key, schema in schemas.items():
        response = requests.post(
            f"{NOTION_BASE_URL}/databases",
            headers=headers,
            json={
                "parent": {"type": "page_id", "page_id": PROJECT_PAGE_ID},
                "title": [{"type": "text", "text": {"content": schema.database_title}}],
                "properties": schema.build_create_properties(),
            },
            timeout=30,
        )
        response.raise_for_status()
        created[key] = response.json()

    relation_targets = {key: value["id"] for key, value in created.items()}

    for key, schema in schemas.items():
        response = requests.patch(
            f"{NOTION_BASE_URL}/databases/{created[key]['id']}",
            headers=headers,
            json={"properties": schema.build_relation_fields(relation_targets)},
            timeout=30,
        )
        response.raise_for_status()
        created[key] = response.json()

    return created
