#!/usr/bin/env python3
"""
Well-Harness M2 四库 Schema 测试。
"""

from unittest.mock import MagicMock, patch

from four_library_schema import (
    FourLibrarySchema,
    create_four_library_databases,
)


def _response(payload):
    resp = MagicMock(status_code=200)
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


class TestFourLibrarySchema:
    def test_component_schema_has_17_standard_and_4_specific_fields(self):
        schema = FourLibrarySchema().init_component_library()
        properties = schema.build_full_properties(
            {
                "component_library": "db-component",
                "case_library": "db-case",
                "baseline_library": "db-baseline",
                "rule_library": "db-rule",
            }
        )

        assert len(properties) == 21
        for field_name in [
            "name",
            "version",
            "created_at",
            "related_components",
            "content_hash",
            "status",
            "immutable_hash",
            "gate",
            "geometry_type",
            "mesh_count",
        ]:
            assert field_name in properties

    def test_case_schema_uses_v1_url_property_format(self):
        schema = FourLibrarySchema().init_case_library()
        properties = schema.build_create_properties()
        assert properties["reference_data"] == {"url": {}}

    def test_create_four_library_databases_creates_then_patches_relations(self):
        created_ids = iter(
            [
                "db-component",
                "db-case",
                "db-baseline",
                "db-rule",
            ]
        )
        create_payloads = []
        patch_payloads = []

        def fake_post(url, headers=None, json=None, timeout=None):
            create_payloads.append(json)
            return _response({"id": next(created_ids), "title": json["title"]})

        def fake_patch(url, headers=None, json=None, timeout=None):
            patch_payloads.append((url, json))
            return _response({"id": url.rsplit("/", 1)[-1], "properties": json["properties"]})

        with patch("four_library_schema.requests.post", side_effect=fake_post), \
             patch("four_library_schema.requests.patch", side_effect=fake_patch):
            result = create_four_library_databases(notion_api_key="test-key")

        assert set(result.keys()) == {
            "component_library",
            "case_library",
            "baseline_library",
            "rule_library",
        }
        assert len(create_payloads) == 4
        assert len(patch_payloads) == 4

        first_create = create_payloads[0]
        assert first_create["parent"] == {"type": "page_id", "page_id": "33bc6894-2bed-819d-822a-c2144bb95e97"}
        assert len(first_create["properties"]) == 17

        component_patch = patch_payloads[0][1]["properties"]
        assert component_patch["related_cases"]["relation"]["database_id"] == "db-case"
        assert component_patch["related_components"]["relation"]["database_id"] == "db-component"
        assert component_patch["related_baselines"]["relation"]["database_id"] == "db-baseline"
        assert component_patch["related_rules"]["relation"]["database_id"] == "db-rule"
