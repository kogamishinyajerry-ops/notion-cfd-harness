#!/usr/bin/env python3
"""
Well-Harness M2 G1 认知门实现。

职责：
1. 从 v1 Tasks DB 读取任务上下文（Linked Phase / Task Type）
2. 在 v1 Artifacts DB 中检索 Component / Baseline 资产
3. 为每个 G1 子检查写入 Evidence DB
4. 汇总 G1 全量审查结果
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

TASKS_DB_ID = "33bc6894-2bed-8196-8e2c-d1d66e631c31"
ARTIFACTS_DB_ID = "33bc6894-2bed-81c0-983f-d5eb1f5b6f4c"
EVIDENCE_DB_ID = "33ac6894-2bed-8188-ba53-e80fb7920398"


@dataclass
class TaskContext:
    page_id: str
    task_title: str
    linked_phase: str
    task_type: str


@dataclass
class G1ReviewResult:
    knowledge_binding_pass: bool
    component_coverage_pass: bool
    baseline_availability_pass: bool
    overall_pass: bool
    evidence_ids: List[str]
    blockers: List[str]


@dataclass
class _CheckOutcome:
    passed: bool
    evidence_id: str
    blockers: List[str]
    evidence: Dict[str, Any]


class CognitiveGateValidator:
    """G1 认知门校验器。"""

    GATE_NAME = "认知门"
    GENERIC_TASK_TYPES = {"指令", "分析", "审查", "学习", "任务"}
    ARTIFACT_TYPE_COMPONENT = "Component"
    ARTIFACT_TYPE_BASELINE = "Baseline"

    def __init__(self, notion_api_key: Optional[str] = None):
        self.api_key = notion_api_key or NOTION_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def validate_knowledge_binding(self, task_id: str) -> tuple[bool, str]:
        outcome = self._run_check(task_id, "knowledge_binding", self._evaluate_knowledge_binding)
        return outcome.passed, outcome.evidence_id

    def validate_component_coverage(self, task_id: str) -> tuple[bool, str]:
        outcome = self._run_check(task_id, "component_coverage", self._evaluate_component_coverage)
        return outcome.passed, outcome.evidence_id

    def validate_baseline_availability(self, task_id: str) -> tuple[bool, str]:
        outcome = self._run_check(task_id, "baseline_availability", self._evaluate_baseline_availability)
        return outcome.passed, outcome.evidence_id

    def run_full_g1_review(self, task_id: str) -> G1ReviewResult:
        knowledge = self._run_check(task_id, "knowledge_binding", self._evaluate_knowledge_binding)
        component = self._run_check(task_id, "component_coverage", self._evaluate_component_coverage)
        baseline = self._run_check(task_id, "baseline_availability", self._evaluate_baseline_availability)

        evidence_ids = [eid for eid in [knowledge.evidence_id, component.evidence_id, baseline.evidence_id] if eid]
        blockers: List[str] = []
        for outcome in (knowledge, component, baseline):
            blockers.extend(outcome.blockers)

        overall_pass = all([knowledge.passed, component.passed, baseline.passed])
        return G1ReviewResult(
            knowledge_binding_pass=knowledge.passed,
            component_coverage_pass=component.passed,
            baseline_availability_pass=baseline.passed,
            overall_pass=overall_pass,
            evidence_ids=evidence_ids,
            blockers=blockers,
        )

    def _run_check(self, task_id: str, review_type: str, evaluator) -> _CheckOutcome:
        blockers: List[str] = []
        evidence: Dict[str, Any]
        passed = False

        try:
            context = self._get_task_context(task_id)
            passed, evidence = evaluator(context)
        except Exception as exc:
            blockers.append(str(exc))
            evidence = self._build_error_evidence(task_id, review_type, str(exc))
            passed = False

        evidence_id = self._deposit_evidence(
            task_page_id=task_id,
            passed=passed,
            evidence=evidence,
            created_by=f"Claude Code / CognitiveGateValidator::{review_type}",
        )

        if not evidence_id:
            blockers.append(f"{review_type} evidence deposit failed")
            passed = False

        if not passed and not blockers:
            blockers.append(evidence.get("message", f"{review_type} failed"))

        return _CheckOutcome(
            passed=passed,
            evidence_id=evidence_id,
            blockers=blockers,
            evidence=evidence,
        )

    def _evaluate_knowledge_binding(self, context: TaskContext) -> tuple[bool, Dict[str, Any]]:
        checks = [
            {
                "check": "linked_phase_present",
                "pass": bool(context.linked_phase),
                "detail": context.linked_phase or "Linked Phase 为空",
            },
            {
                "check": "task_type_present",
                "pass": bool(context.task_type),
                "detail": context.task_type or "Task Type 为空",
            },
        ]
        passed = all(check["pass"] for check in checks)
        message = "G1 知识绑定通过" if passed else "G1 知识绑定缺失 Linked Phase / Task Type"
        evidence = self._build_evidence(
            review_type="knowledge_binding",
            task_id=context.page_id,
            task_context=context,
            checks=checks,
            message=message,
            extra={
                "binding_fields": {
                    "linked_phase": context.linked_phase,
                    "task_type": context.task_type,
                }
            },
        )
        return passed, evidence

    def _evaluate_component_coverage(self, context: TaskContext) -> tuple[bool, Dict[str, Any]]:
        keyword = self._primary_artifact_keyword(context)
        checks = [
            {
                "check": "context_query_ready",
                "pass": bool(keyword),
                "detail": keyword or "缺少可用于检索构件库的 Linked Phase / Task Type",
            }
        ]

        matched_ids: List[str] = []
        total_components = 0

        if keyword:
            matched = self._query_artifacts(self.ARTIFACT_TYPE_COMPONENT, keyword)
            matched_ids = [self._artifact_identity(page) for page in matched]
            total_components = len(matched)

        checks.append(
            {
                "check": "component_match_found",
                "pass": bool(matched_ids),
                "detail": f"匹配到 {len(matched_ids)} 个 Component 资产",
            }
        )

        passed = all(check["pass"] for check in checks)
        message = "G1 构件覆盖通过" if passed else "G1 构件覆盖不足"
        evidence = self._build_evidence(
            review_type="component_coverage",
            task_id=context.page_id,
            task_context=context,
            checks=checks,
            message=message,
            extra={
                "artifact_type": self.ARTIFACT_TYPE_COMPONENT,
                "query_keyword": keyword,
                "matched_artifacts": matched_ids,
                "matched_count": total_components,
            },
        )
        return passed, evidence

    def _evaluate_baseline_availability(self, context: TaskContext) -> tuple[bool, Dict[str, Any]]:
        keyword = self._primary_artifact_keyword(context)
        checks = [
            {
                "check": "context_query_ready",
                "pass": bool(keyword),
                "detail": keyword or "缺少可用于检索基线库的 Linked Phase / Task Type",
            }
        ]

        matched_ids: List[str] = []
        total_baselines = 0

        if keyword:
            matched = self._query_artifacts(self.ARTIFACT_TYPE_BASELINE, keyword)
            matched_ids = [self._artifact_identity(page) for page in matched]
            total_baselines = len(matched)

        checks.append(
            {
                "check": "baseline_match_found",
                "pass": bool(matched_ids),
                "detail": f"匹配到 {len(matched_ids)} 个 Baseline 资产",
            }
        )

        passed = all(check["pass"] for check in checks)
        message = "G1 基线可用性通过" if passed else "G1 基线缺失"
        evidence = self._build_evidence(
            review_type="baseline_availability",
            task_id=context.page_id,
            task_context=context,
            checks=checks,
            message=message,
            extra={
                "artifact_type": self.ARTIFACT_TYPE_BASELINE,
                "query_keyword": keyword,
                "matched_artifacts": matched_ids,
                "matched_count": total_baselines,
            },
        )
        return passed, evidence

    def _get_task_context(self, task_id: str) -> TaskContext:
        page = self._notion_get(f"pages/{task_id}")
        parent_database_id = (page.get("parent") or {}).get("database_id", "")
        if parent_database_id and parent_database_id != TASKS_DB_ID:
            raise ValueError(f"Task {task_id} 不在 v1 Tasks DB 中")

        props = page.get("properties", {})
        linked_phase = self._rich_text_plain(props.get("Linked Phase", {})).strip()
        task_type = ((props.get("Task Type", {}) or {}).get("select") or {}).get("name", "").strip()
        task_title = self._title_plain(props.get("Task ID", {})).strip() or task_id

        return TaskContext(
            page_id=task_id,
            task_title=task_title,
            linked_phase=linked_phase,
            task_type=task_type,
        )

    def _query_artifacts(self, artifact_type: str, keyword: str) -> List[Dict[str, Any]]:
        query = {
            "database_id": ARTIFACTS_DB_ID,
            "page_size": 20,
            "filter": {
                "and": [
                    {"property": "Artifact Type", "select": {"equals": artifact_type}},
                    {
                        "or": [
                            {"property": "Linked Task / Phase / Review", "rich_text": {"contains": keyword}},
                            {"property": "Summary", "rich_text": {"contains": keyword}},
                        ]
                    },
                ]
            },
        }
        result = self._notion_post("databases/query", query)
        return result.get("results", [])

    def _notion_get(self, endpoint: str) -> Dict[str, Any]:
        self._require_api_key()
        response = requests.get(
            f"{NOTION_BASE_URL}/{endpoint}",
            headers=self.headers,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def _notion_post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        self._require_api_key()
        response = requests.post(
            f"{NOTION_BASE_URL}/{endpoint}",
            headers=self.headers,
            json=data,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def _deposit_evidence(
        self,
        task_page_id: str,
        passed: bool,
        evidence: Dict[str, Any],
        created_by: str,
    ) -> str:
        if not self.api_key:
            return ""

        evidence_id = self._generate_evidence_id()
        content_hash = self._compute_hash(evidence)
        now = datetime.now().isoformat()
        status = "Deposited" if passed else "RuleViolation"
        evidence_type = "GateCheck" if passed else "RuleViolation"

        payload = {
            "parent": {"database_id": EVIDENCE_DB_ID},
            "properties": {
                "evidence_id": {"title": [{"text": {"content": evidence_id}}]},
                "task_id": {"relation": [{"id": task_page_id}]},
                "gate": {"select": {"name": "G1"}},
                "evidence_type": {"select": {"name": evidence_type}},
                "content": {"rich_text": [{"text": {"content": json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:1900]}}]},
                "immutable_hash": {"rich_text": [{"text": {"content": content_hash}}]},
                "status": {"select": {"name": status}},
                "created_at": {"date": {"start": evidence.get("timestamp", now)}},
                "deposited_at": {"date": {"start": now}},
                "created_by": {"rich_text": [{"text": {"content": created_by[:1900]}}]},
                "modified_at": {"date": {"start": now}},
                "version": {"number": 1},
            },
        }

        response = requests.post(
            f"{NOTION_BASE_URL}/pages",
            headers=self.headers,
            json=payload,
            timeout=20,
        )
        if response.status_code != 200:
            return ""
        return evidence_id

    def _build_evidence(
        self,
        review_type: str,
        task_id: str,
        task_context: TaskContext,
        checks: List[Dict[str, Any]],
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "gate": "G1",
            "gate_name": self.GATE_NAME,
            "review_type": review_type,
            "task_id": task_id,
            "task_title": task_context.task_title,
            "timestamp": datetime.now().isoformat(),
            "linked_phase": task_context.linked_phase,
            "task_type": task_context.task_type,
            "checks": deepcopy(checks),
            "result": "PASS" if all(check["pass"] for check in checks) else "FAIL",
            "message": message,
        }
        if extra:
            payload.update(extra)
        return payload

    def _build_error_evidence(self, task_id: str, review_type: str, error_message: str) -> Dict[str, Any]:
        return {
            "gate": "G1",
            "gate_name": self.GATE_NAME,
            "review_type": review_type,
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "checks": [
                {
                    "check": "task_context_fetch",
                    "pass": False,
                    "detail": error_message,
                }
            ],
            "result": "FAIL",
            "message": error_message,
        }

    def _primary_artifact_keyword(self, context: TaskContext) -> str:
        if context.linked_phase:
            return context.linked_phase
        if context.task_type and context.task_type not in self.GENERIC_TASK_TYPES:
            return context.task_type
        return ""

    @staticmethod
    def _rich_text_plain(prop: Dict[str, Any]) -> str:
        values = []
        for item in prop.get("rich_text", []):
            plain_text = item.get("plain_text")
            if plain_text is not None:
                values.append(plain_text)
            else:
                values.append(item.get("text", {}).get("content", ""))
        return "".join(values)

    @staticmethod
    def _title_plain(prop: Dict[str, Any]) -> str:
        values = []
        for item in prop.get("title", []):
            plain_text = item.get("plain_text")
            if plain_text is not None:
                values.append(plain_text)
            else:
                values.append(item.get("text", {}).get("content", ""))
        return "".join(values)

    @staticmethod
    def _artifact_identity(page: Dict[str, Any]) -> str:
        props = page.get("properties", {})
        artifact_id = CognitiveGateValidator._title_plain(props.get("Artifact ID", {})).strip()
        return artifact_id or page.get("id", "")

    @staticmethod
    def _generate_evidence_id() -> str:
        return f"EV-{str(uuid.uuid4())[:6].upper()}"

    @staticmethod
    def _compute_hash(content: Dict[str, Any]) -> str:
        payload = json.dumps(content, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("NOTION_API_KEY 未配置，无法执行 G1 认知门 Notion 校验")
