#!/usr/bin/env python3
"""
Well-Harness M2 G1 认知门测试。
"""

from unittest.mock import MagicMock, patch

from g1_cognitive_gate import (
    ARTIFACTS_DB_ID,
    EVIDENCE_DB_ID,
    TASKS_DB_ID,
    CognitiveGateValidator,
)


def _response(payload, status_code=200):
    resp = MagicMock(status_code=status_code)
    resp.json.return_value = payload
    if status_code >= 400:
        resp.raise_for_status.side_effect = RuntimeError(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


def _task_page(linked_phase="Phase-A", task_type="分析"):
    return {
        "id": "task-page-123",
        "parent": {"database_id": TASKS_DB_ID},
        "properties": {
            "Task ID": {"title": [{"text": {"content": "Task-001"}}]},
            "Linked Phase": {"rich_text": [{"text": {"content": linked_phase}}]} if linked_phase else {"rich_text": []},
            "Task Type": {"select": {"name": task_type}} if task_type else {"select": None},
        },
    }


def _artifact_page(artifact_id):
    return {
        "id": f"page-{artifact_id}",
        "properties": {
            "Artifact ID": {"title": [{"text": {"content": artifact_id}}]}
        },
    }


class TestCognitiveGateValidator:
    def test_validate_knowledge_binding_passes_and_deposits_evidence(self):
        validator = CognitiveGateValidator(notion_api_key="test-key")

        with patch("g1_cognitive_gate.requests.get", return_value=_response(_task_page())), \
             patch("g1_cognitive_gate.requests.post", return_value=_response({"id": "evidence-page-1"})) as mock_post:
            passed, evidence_id = validator.validate_knowledge_binding("task-page-123")

        assert passed is True
        assert evidence_id.startswith("EV-")
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["parent"] == {"database_id": EVIDENCE_DB_ID}
        assert payload["properties"]["gate"]["select"]["name"] == "G1"

    def test_run_full_g1_review_passes_with_component_and_baseline_matches(self):
        validator = CognitiveGateValidator(notion_api_key="test-key")

        def fake_post(url, headers=None, json=None, timeout=None):
            if url.endswith("/databases/query"):
                assert json["database_id"] == ARTIFACTS_DB_ID
                artifact_type = json["filter"]["and"][0]["select"]["equals"]
                if artifact_type == "Component":
                    return _response({"results": [_artifact_page("COMP-001")]})
                if artifact_type == "Baseline":
                    return _response({"results": [_artifact_page("BASE-001")]})
                return _response({"results": []})
            return _response({"id": "evidence-page"})

        with patch("g1_cognitive_gate.requests.get", return_value=_response(_task_page())), \
             patch("g1_cognitive_gate.requests.post", side_effect=fake_post):
            result = validator.run_full_g1_review("task-page-123")

        assert result.knowledge_binding_pass is True
        assert result.component_coverage_pass is True
        assert result.baseline_availability_pass is True
        assert result.overall_pass is True
        assert len(result.evidence_ids) == 3
        assert result.blockers == []

    def test_run_full_g1_review_returns_blockers_when_binding_missing(self):
        validator = CognitiveGateValidator(notion_api_key="test-key")

        with patch("g1_cognitive_gate.requests.get", return_value=_response(_task_page(linked_phase="", task_type=""))), \
             patch("g1_cognitive_gate.requests.post", return_value=_response({"id": "evidence-page"})):
            result = validator.run_full_g1_review("task-page-123")

        assert result.knowledge_binding_pass is False
        assert result.component_coverage_pass is False
        assert result.baseline_availability_pass is False
        assert result.overall_pass is False
        assert len(result.evidence_ids) == 3
        assert any("知识绑定" in blocker or "Linked Phase" in blocker for blocker in result.blockers)
