#!/usr/bin/env python3
"""
P4-09: Gate result sync to Notion Reviews DB tests.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import notion_cfd_loop


def _reviews_db_schema() -> dict:
    return {
        "properties": {
            "Review ID": {"title": {}},
            "Linked Phase": {"rich_text": {}},
            "Review Type": {"select": {}},
            "Reviewer Model": {"rich_text": {}},
            "Review Status": {"select": {}},
            "Decision": {"select": {}},
            "Blocking Issues": {"rich_text": {}},
            "Conditional Pass Items": {"rich_text": {}},
            "Required Fixes": {"rich_text": {}},
            "Suggested Next Phase": {"rich_text": {}},
            "Review Artifact Link": {"url": {}},
            "Reviewed At": {"date": {}},
        }
    }


def _gate_result(
    gate: str = "G4",
    passed: bool = True,
    status: str = "PASS",
    blockers: list[str] | None = None,
    detail: str = "Propagation contracts verified",
    include_record_path: bool = True,
) -> dict:
    result = {
        "gate": gate,
        "passed": passed,
        "status": status,
        "timestamp": "2026-04-07T00:00:00+00:00",
        "checks": [
            {
                "check": "check_dependency_propagation",
                "passed": passed,
                "detail": detail,
            }
        ],
        "blockers": blockers if blockers is not None else ([] if passed else [detail]),
        "next_action": "Ready for next gate" if passed else "Resolve blockers and re-run",
    }
    if include_record_path:
        result["record_path"] = f"/tmp/{gate.lower()}_gate_result.json"
    return result


def _rich_text_content(prop: dict) -> str:
    return "".join(item["text"]["content"] for item in prop.get("rich_text", []))


def _children_text(children: list[dict]) -> str:
    lines = []
    for block in children:
        block_type = block["type"]
        for item in block[block_type]["rich_text"]:
            lines.append(item["text"]["content"])
    return "\n".join(lines)


def test_sync_gate_result_to_notion_queries_reviews_db_and_creates_review_page(monkeypatch, tmp_path):
    gate_result_path = tmp_path / "g4_gate_result.json"
    gate_result_path.write_text(
        json.dumps(_gate_result(gate="G4", include_record_path=False), ensure_ascii=False),
        encoding="utf-8",
    )

    get_calls: list[str] = []
    post_call: dict = {}

    def fake_get(endpoint: str) -> dict:
        get_calls.append(endpoint)
        return _reviews_db_schema()

    def fake_post(endpoint: str, data: dict) -> dict:
        post_call["endpoint"] = endpoint
        post_call["data"] = data
        return {"id": "review-page-123"}

    monkeypatch.setattr(notion_cfd_loop, "notion_get", fake_get)
    monkeypatch.setattr(notion_cfd_loop, "notion_post", fake_post)

    sync_result = notion_cfd_loop.sync_gate_result_to_notion(gate_result_path)

    assert sync_result["success"] is True
    assert sync_result["page_id"] == "review-page-123"
    assert get_calls == [f"databases/{notion_cfd_loop.REVIEWS_DB_ID}"]
    assert post_call["endpoint"] == "pages"

    payload = post_call["data"]
    props = payload["properties"]
    assert payload["parent"] == {"database_id": notion_cfd_loop.REVIEWS_DB_ID}
    assert props["Review ID"]["title"][0]["text"]["content"].startswith("GATE-REV-G4-")
    assert _rich_text_content(props["Linked Phase"]) == "G4"
    assert props["Review Type"]["select"]["name"] == "Gate Review"
    assert _rich_text_content(props["Reviewer Model"]) == "automatic"
    assert props["Review Status"]["select"]["name"] == "Completed"
    assert props["Decision"]["select"]["name"] == "PASS"
    assert props["Reviewed At"]["date"]["start"] == "2026-04-07T00:00:00+00:00"
    assert "check_dependency_propagation" in _rich_text_content(props["Required Fixes"])
    assert "Ready for next gate" in _rich_text_content(props["Suggested Next Phase"])

    children_text = _children_text(payload["children"])
    assert "Gate Review Summary" in children_text
    assert "Record Path:" in children_text
    assert str(gate_result_path.resolve()) in children_text


@pytest.mark.parametrize(
    ("gate", "expected_reviewer"),
    [
        ("G3", "automatic"),
        ("G4", "automatic"),
        ("G5", "Opus"),
        ("G6", "Opus"),
    ],
)
def test_sync_gate_result_to_notion_mock_mode_assigns_expected_default_reviewer(
    monkeypatch,
    gate: str,
    expected_reviewer: str,
):
    def fake_get(endpoint: str) -> dict:
        assert endpoint == f"databases/{notion_cfd_loop.REVIEWS_DB_ID}"
        return _reviews_db_schema()

    def fake_post(endpoint: str, data: dict) -> dict:
        raise AssertionError("notion_post should not be called in mock_mode")

    monkeypatch.setattr(notion_cfd_loop, "notion_get", fake_get)
    monkeypatch.setattr(notion_cfd_loop, "notion_post", fake_post)

    sync_result = notion_cfd_loop.sync_gate_result_to_notion(
        _gate_result(gate=gate),
        mock_mode=True,
    )

    assert sync_result["success"] is True
    assert sync_result["mock_mode"] is True
    props = sync_result["payload"]["properties"]
    assert _rich_text_content(props["Reviewer Model"]) == expected_reviewer


def test_sync_gate_result_to_notion_records_failed_gate_details_and_blockers(monkeypatch):
    monkeypatch.setattr(notion_cfd_loop, "notion_get", lambda endpoint: _reviews_db_schema())

    sync_result = notion_cfd_loop.sync_gate_result_to_notion(
        _gate_result(
            gate="G5",
            passed=False,
            status="FAIL",
            blockers=["Manual approval missing", "Acceptance checklist incomplete"],
            detail="Manual approval requirements not satisfied",
        ),
        mock_mode=True,
    )

    assert sync_result["success"] is True
    props = sync_result["payload"]["properties"]
    assert props["Decision"]["select"]["name"] == "FAIL"
    assert _rich_text_content(props["Reviewer Model"]) == "Opus"
    assert "Manual approval missing" in _rich_text_content(props["Blocking Issues"])
    assert "FAIL" in _rich_text_content(props["Required Fixes"])
    assert "Manual approval requirements not satisfied" in _rich_text_content(props["Required Fixes"])


def test_sync_gate_result_to_notion_returns_error_on_reviews_db_query_failure(monkeypatch):
    def fake_get(endpoint: str) -> dict:
        raise RuntimeError(f"schema lookup failed for {endpoint}")

    monkeypatch.setattr(notion_cfd_loop, "notion_get", fake_get)

    sync_result = notion_cfd_loop.sync_gate_result_to_notion(
        _gate_result(gate="G3"),
        mock_mode=True,
    )

    assert sync_result["success"] is False
    assert "schema lookup failed" in sync_result["error"]
