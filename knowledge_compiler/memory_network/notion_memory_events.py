#!/usr/bin/env python3
from __future__ import annotations

"""
P4-10: Notion API integration for Memory Events.

Adds:
1. A normalized memory-event model for knowledge-unit, gate, propagation,
   and code-mapping lifecycle tracking.
2. Notion payload builders that reuse the P4-09 database/property patterns.
3. A MemoryNetwork subclass that records P4-10 events without modifying P4-06.
"""

import json
import os
from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional

import notion_cfd_loop

from knowledge_compiler.executables.diff_engine import ChangeType, DiffReport
from knowledge_compiler.memory_network import (
    CodeMapping,
    GovernanceDecision,
    MemoryNetwork,
    PropagationDecision,
    PropagationEvent,
    UnitVersion,
)


MEMORY_EVENTS_DB_ID = os.environ.get("MEMORY_EVENTS_DB_ID", "")

MEMORY_EVENT_DB_PROPERTY_ALIASES = {
    "title": ("Name", "Title", "Event ID"),
    "event_type": ("Event Type", "Type"),
    "unit_id": ("Unit ID", "Knowledge Unit ID", "Unit"),
    "timestamp": ("Timestamp", "Occurred At", "Time"),
    "details": ("Details", "Event Details", "Payload"),
}
MEMORY_EVENT_DB_PROPERTY_TYPES = {
    "title": ("title",),
    "event_type": ("select", "status"),
    "unit_id": ("rich_text", "title"),
    "timestamp": ("date",),
    "details": ("rich_text", "title"),
}


class MemoryEventType(str, Enum):
    """Supported P4-10 memory event types."""

    UNIT_CREATED = "UnitCreated"
    UNIT_UPDATED = "UnitUpdated"
    VERSION_CREATED = "VersionCreated"
    GATE_TRIGGERED = "GateTriggered"
    PROPAGATION_EXECUTED = "PropagationExecuted"
    CODE_MAPPING_CHANGED = "CodeMappingChanged"


@dataclass
class MemoryEvent:
    """Normalized audit event ready for Notion sync."""

    event_id: str
    event_type: MemoryEventType
    unit_id: str
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "unit_id": self.unit_id,
            "timestamp": self.timestamp.isoformat(),
            "details": deepcopy(self.details),
        }


def _coerce_timestamp(value: Any = None) -> datetime:
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise TypeError("timestamp must be None, datetime, or ISO-8601 string")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, CodeMapping):
        return _mapping_to_dict(value)
    if isinstance(value, UnitVersion):
        return _unit_version_to_dict(value)
    if isinstance(value, PropagationDecision):
        return _propagation_decision_to_dict(value)
    if isinstance(value, GovernanceDecision):
        return _governance_decision_to_dict(value)
    if isinstance(value, PropagationEvent):
        return _propagation_event_to_dict(value)
    if isinstance(value, DiffReport):
        return _diff_report_to_dict(value)
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def _serialize_details(details: Mapping[str, Any]) -> str:
    return json.dumps(
        details,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )


def _unit_version_to_dict(version: Optional[UnitVersion]) -> Optional[dict[str, Any]]:
    if version is None:
        return None
    return {
        "unit_id": version.unit_id,
        "version": version.version,
        "content_hash": version.content_hash,
        "parent_hash": version.parent_hash,
        "created_at": version.created_at.isoformat(),
        "created_by": version.created_by,
        "status": version.status.value,
        "change_summary": version.change_summary,
        "metadata": deepcopy(version.metadata),
    }


def _mapping_to_dict(mapping: Any) -> dict[str, Any]:
    if isinstance(mapping, dict):
        data = dict(mapping)
        verified_at = data.get("verified_at")
        if isinstance(verified_at, datetime):
            data["verified_at"] = verified_at.isoformat()
        return data
    if isinstance(mapping, CodeMapping):
        return {
            "unit_id": mapping.unit_id,
            "file_path": mapping.file_path,
            "mapping_type": mapping.mapping_type,
            "confidence": mapping.confidence,
            "verified_at": mapping.verified_at.isoformat() if mapping.verified_at else None,
        }
    raise TypeError("mapping must be a CodeMapping or dict")


def _mapping_snapshot_to_index(snapshot: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(mapping["file_path"]): deepcopy(mapping)
        for mapping in snapshot
    }


def _diff_report_to_dict(diff_report: Optional[DiffReport]) -> Optional[dict[str, Any]]:
    if diff_report is None:
        return None
    return {
        "change_type": diff_report.change_type.value,
        "unit_id": diff_report.unit_id,
        "field": diff_report.field,
        "old_value": diff_report.old_value,
        "new_value": diff_report.new_value,
        "impacted_executables": list(diff_report.impacted_executables),
    }


def _propagation_decision_to_dict(
    decision: Optional[PropagationDecision],
) -> Optional[dict[str, Any]]:
    if decision is None:
        return None
    return {
        "should_propagate": decision.should_propagate,
        "target_executables": list(decision.target_executables),
        "action_type": decision.action_type,
        "reason": decision.reason,
    }


def _governance_decision_to_dict(
    decision: Optional[GovernanceDecision],
) -> Optional[dict[str, Any]]:
    if decision is None:
        return None
    return {
        "status": decision.status,
        "reasons": list(decision.reasons),
        "warnings": list(decision.warnings),
        "propagation_decisions": [
            _propagation_decision_to_dict(item)
            for item in decision.propagation_decisions
        ],
    }


def _propagation_event_to_dict(
    event: Optional[PropagationEvent],
) -> Optional[dict[str, Any]]:
    if event is None:
        return None
    return {
        "event_id": event.event_id,
        "change_type": event.change_type.value,
        "source_unit": event.source_unit,
        "impact_targets": list(event.impact_targets),
        "governance_decision": event.governance_decision,
        "reason": event.reason,
        "timestamp": event.timestamp.isoformat(),
    }


def _resolve_memory_events_db_property_map(
    database_properties: Mapping[str, Any],
) -> dict[str, str]:
    property_map: dict[str, str] = {}
    for key, aliases in MEMORY_EVENT_DB_PROPERTY_ALIASES.items():
        property_map[key] = notion_cfd_loop._resolve_database_property_name(
            database_properties,
            aliases=aliases,
            expected_types=MEMORY_EVENT_DB_PROPERTY_TYPES.get(key, ()),
            allow_type_fallback=(key in {"title", "unit_id", "details"}),
        )

    if not property_map.get("title"):
        raise ValueError("Memory Events DB 缺少可写 title 属性，无法创建事件页面")
    if not property_map.get("event_type"):
        raise ValueError("Memory Events DB 缺少 Event Type 属性")
    if not property_map.get("timestamp"):
        raise ValueError("Memory Events DB 缺少 Timestamp 属性")

    return {key: value for key, value in property_map.items() if value}


def _build_event_children(event: MemoryEvent) -> list[dict]:
    summary = "\n".join(
        [
            f"Event ID: {event.event_id}",
            f"Event Type: {event.event_type.value}",
            f"Unit ID: {event.unit_id}",
            f"Timestamp: {event.timestamp.isoformat()}",
        ]
    )
    details_text = _serialize_details(event.details)

    children = [notion_cfd_loop._heading_block("Memory Event Summary")]
    children.extend(notion_cfd_loop._paragraph_blocks(summary))
    children.append(notion_cfd_loop._heading_block("Details"))
    children.extend(notion_cfd_loop._paragraph_blocks(details_text))
    return children


class MemoryEventTracker:
    """Collects, formats, and syncs memory events."""

    def __init__(self, events_db_id: str = MEMORY_EVENTS_DB_ID):
        self.events_db_id = events_db_id
        self.events: list[MemoryEvent] = []

    def record_event(
        self,
        event_type: MemoryEventType,
        unit_id: str,
        details: Optional[Mapping[str, Any]] = None,
        timestamp: Any = None,
    ) -> MemoryEvent:
        event = MemoryEvent(
            event_id=f"MEM-EVT-{len(self.events) + 1:04d}",
            event_type=event_type,
            unit_id=str(unit_id),
            timestamp=_coerce_timestamp(timestamp),
            details=deepcopy(dict(details or {})),
        )
        self.events.append(event)
        return event

    def record_unit_created(
        self,
        unit_id: str,
        version: Optional[UnitVersion] = None,
        diff_report: Optional[DiffReport] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> MemoryEvent:
        details = {
            "version": _unit_version_to_dict(version),
            "diff_report": _diff_report_to_dict(diff_report),
            "context": deepcopy(dict(context or {})),
        }
        return self.record_event(MemoryEventType.UNIT_CREATED, unit_id, details)

    def record_unit_updated(
        self,
        unit_id: str,
        previous_version: Optional[UnitVersion] = None,
        new_version: Optional[UnitVersion] = None,
        diff_report: Optional[DiffReport] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> MemoryEvent:
        details = {
            "previous_version": _unit_version_to_dict(previous_version),
            "new_version": _unit_version_to_dict(new_version),
            "diff_report": _diff_report_to_dict(diff_report),
            "context": deepcopy(dict(context or {})),
        }
        return self.record_event(MemoryEventType.UNIT_UPDATED, unit_id, details)

    def record_version_created(
        self,
        unit_id: str,
        version: UnitVersion,
        previous_version: Optional[UnitVersion] = None,
        diff_report: Optional[DiffReport] = None,
    ) -> MemoryEvent:
        details = {
            "previous_version": _unit_version_to_dict(previous_version),
            "version": _unit_version_to_dict(version),
            "diff_report": _diff_report_to_dict(diff_report),
        }
        return self.record_event(
            MemoryEventType.VERSION_CREATED,
            unit_id,
            details,
            timestamp=version.created_at,
        )

    def record_propagation(
        self,
        propagation_event: PropagationEvent,
        propagation_decision: Optional[PropagationDecision] = None,
        governance_decision: Optional[GovernanceDecision] = None,
    ) -> MemoryEvent:
        impact_targets = list(propagation_event.impact_targets)
        propagation_chain = [propagation_event.source_unit, *impact_targets]
        details = {
            "propagation_event": _propagation_event_to_dict(propagation_event),
            "propagation_decision": _propagation_decision_to_dict(propagation_decision),
            "governance_decision": _governance_decision_to_dict(governance_decision),
            "impact_targets": impact_targets,
            "propagation_chain": propagation_chain,
        }
        return self.record_event(
            MemoryEventType.PROPAGATION_EXECUTED,
            propagation_event.source_unit,
            details,
            timestamp=propagation_event.timestamp,
        )

    def record_gate_trigger(
        self,
        gate_result: Mapping[str, Any],
        unit_id: Optional[str] = None,
    ) -> MemoryEvent:
        payload = dict(gate_result)
        gate_name = str(payload.get("gate") or payload.get("gate_name") or "").strip().upper()
        if gate_name not in notion_cfd_loop.SUPPORTED_REVIEW_GATES:
            supported = ", ".join(sorted(notion_cfd_loop.SUPPORTED_REVIEW_GATES))
            raise ValueError(f"仅支持 {supported} Gate 事件，收到: {gate_name or 'UNKNOWN'}")

        timestamp = payload.get("timestamp") or datetime.now().isoformat()
        payload["gate"] = gate_name
        payload.setdefault("status", notion_cfd_loop._normalize_review_decision(payload))
        resolved_unit_id = str(unit_id or payload.get("unit_id") or f"GATE:{gate_name}")
        return self.record_event(
            MemoryEventType.GATE_TRIGGERED,
            resolved_unit_id,
            payload,
            timestamp=timestamp,
        )

    def record_code_mapping_change(
        self,
        unit_id: str,
        before_snapshot: list[dict[str, Any]],
        after_snapshot: list[dict[str, Any]],
    ) -> Optional[MemoryEvent]:
        before_index = _mapping_snapshot_to_index(before_snapshot)
        after_index = _mapping_snapshot_to_index(after_snapshot)

        added = [
            deepcopy(after_index[path])
            for path in sorted(set(after_index) - set(before_index))
        ]
        removed = [
            deepcopy(before_index[path])
            for path in sorted(set(before_index) - set(after_index))
        ]
        updated = [
            {
                "before": deepcopy(before_index[path]),
                "after": deepcopy(after_index[path]),
            }
            for path in sorted(set(before_index) & set(after_index))
            if before_index[path] != after_index[path]
        ]

        if not added and not removed and not updated:
            return None

        details = {
            "before": deepcopy(before_snapshot),
            "after": deepcopy(after_snapshot),
            "added_mappings": added,
            "removed_mappings": removed,
            "updated_mappings": updated,
            "mapping_count_before": len(before_snapshot),
            "mapping_count_after": len(after_snapshot),
        }
        return self.record_event(MemoryEventType.CODE_MAPPING_CHANGED, unit_id, details)

    def record_mapping_sync_delta(
        self,
        before_snapshots: Mapping[str, list[dict[str, Any]]],
        after_snapshots: Mapping[str, list[dict[str, Any]]],
        requested_units: Optional[set[str]] = None,
    ) -> list[MemoryEvent]:
        events: list[MemoryEvent] = []
        candidate_units = set(before_snapshots) | set(after_snapshots)
        if requested_units:
            candidate_units |= set(requested_units)

        for unit_id in sorted(candidate_units):
            event = self.record_code_mapping_change(
                unit_id,
                before_snapshot=before_snapshots.get(unit_id, []),
                after_snapshot=after_snapshots.get(unit_id, []),
            )
            if event is not None:
                events.append(event)
        return events

    def record_change_result(
        self,
        result: Mapping[str, Any],
        *,
        diff_report: Optional[DiffReport] = None,
        context: Optional[Mapping[str, Any]] = None,
        unit_existed_before: bool,
    ) -> list[MemoryEvent]:
        events: list[MemoryEvent] = []
        unit_id = str(result["unit_id"])
        previous_version = result.get("previous_version")
        version = result.get("version")

        if unit_existed_before:
            events.append(
                self.record_unit_updated(
                    unit_id,
                    previous_version=previous_version,
                    new_version=version,
                    diff_report=diff_report,
                    context=context,
                )
            )
        else:
            events.append(
                self.record_unit_created(
                    unit_id,
                    version=version,
                    diff_report=diff_report,
                    context=context,
                )
            )

        if isinstance(version, UnitVersion):
            should_record_version = (
                not unit_existed_before
                or not isinstance(previous_version, UnitVersion)
                or version.version != previous_version.version
                or version.content_hash != previous_version.content_hash
            )
            if should_record_version:
                events.append(
                    self.record_version_created(
                        unit_id,
                        version=version,
                        previous_version=previous_version,
                        diff_report=diff_report,
                    )
                )

        propagation_event = result.get("event")
        if isinstance(propagation_event, PropagationEvent):
            events.append(
                self.record_propagation(
                    propagation_event,
                    propagation_decision=result.get("propagation_decision"),
                    governance_decision=result.get("governance_decision"),
                )
            )

        return events

    def prepare_event_sync_payload(
        self,
        event: MemoryEvent,
        *,
        events_db_id: Optional[str] = None,
        database_properties: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        resolved_db_id = events_db_id or self.events_db_id
        if not resolved_db_id:
            raise ValueError("events_db_id is required for Memory Events Notion sync")

        db_properties = dict(
            database_properties or notion_cfd_loop.get_database_properties(resolved_db_id)
        )
        property_map = _resolve_memory_events_db_property_map(db_properties)
        details_text = _serialize_details(event.details)

        property_values: list[tuple[str, Any]] = []
        title_prop = property_map.get("title")
        unit_id_prop = property_map.get("unit_id")
        if title_prop and title_prop != unit_id_prop:
            property_values.append(("title", event.event_id))

        property_values.extend(
            [
                ("event_type", event.event_type.value),
                ("unit_id", event.unit_id),
                ("timestamp", event.timestamp.isoformat()),
            ]
        )
        if details_text:
            property_values.append(("details", details_text))

        properties: dict[str, Any] = {}
        for key, value in property_values:
            prop_name = property_map.get(key)
            if not prop_name:
                continue
            prop_type = notion_cfd_loop._get_notion_property_type(
                db_properties.get(prop_name, {})
            )
            prop_value = notion_cfd_loop._build_notion_property_value(prop_type, value)
            if prop_value is not None:
                properties[prop_name] = prop_value

        payload = {
            "parent": {"database_id": resolved_db_id},
            "properties": properties,
            "children": _build_event_children(event),
        }
        return {
            "events_db_id": resolved_db_id,
            "property_map": property_map,
            "payload": payload,
        }

    def sync_event_to_notion(
        self,
        event: MemoryEvent,
        *,
        events_db_id: Optional[str] = None,
        mock_mode: bool = False,
    ) -> dict[str, Any]:
        prepared = self.prepare_event_sync_payload(event, events_db_id=events_db_id)
        payload = prepared["payload"]

        if mock_mode:
            return {
                "success": True,
                "mock_mode": True,
                "page_id": None,
                "event_id": event.event_id,
                "property_map": prepared["property_map"],
                "payload": payload,
            }

        page = notion_cfd_loop.notion_post("pages", payload)
        return {
            "success": True,
            "mock_mode": False,
            "page_id": page.get("id"),
            "event_id": event.event_id,
            "property_map": prepared["property_map"],
            "payload": payload,
        }

    def sync_events_to_notion(
        self,
        events: Optional[list[MemoryEvent]] = None,
        *,
        events_db_id: Optional[str] = None,
        mock_mode: bool = False,
    ) -> list[dict[str, Any]]:
        return [
            self.sync_event_to_notion(
                event,
                events_db_id=events_db_id,
                mock_mode=mock_mode,
            )
            for event in (events or self.events)
        ]


class MemoryNetworkWithEvents(MemoryNetwork):
    """MemoryNetwork variant that emits P4-10 events via composition."""

    def __init__(
        self,
        *args: Any,
        event_tracker: Optional[MemoryEventTracker] = None,
        events_db_id: str = MEMORY_EVENTS_DB_ID,
        auto_sync_notion: bool = False,
        notion_mock_mode: bool = False,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.event_tracker = event_tracker or MemoryEventTracker(events_db_id=events_db_id)
        self.auto_sync_notion = auto_sync_notion
        self.notion_mock_mode = notion_mock_mode
        self.notion_sync_log: list[dict[str, Any]] = []
        self._suspend_event_autosync = False

    @property
    def memory_events(self) -> list[MemoryEvent]:
        return self.event_tracker.events

    def sync_code_mappings(
        self,
        mappings: Optional[dict[str, list[Any]]] = None,
    ) -> dict[str, list[CodeMapping]]:
        start_index = len(self.event_tracker.events)
        before_snapshots = self._snapshot_code_mappings()
        synced = super().sync_code_mappings(mappings)
        after_snapshots = self._snapshot_code_mappings()

        requested_units = set(before_snapshots) | set(after_snapshots)
        if mappings:
            requested_units |= set(mappings.keys())
        self.event_tracker.record_mapping_sync_delta(
            before_snapshots,
            after_snapshots,
            requested_units=requested_units,
        )

        if not self._suspend_event_autosync:
            self._sync_new_events(self.event_tracker.events[start_index:])
        return synced

    def register_change(self, unit_id: str, change: Any) -> dict[str, Any]:
        start_index = len(self.event_tracker.events)
        diff_report, context = self._normalize_change(unit_id, change)
        unit_existed_before = self.versioned_registry.get_current(diff_report.unit_id) is not None

        self._suspend_event_autosync = True
        try:
            result = super().register_change(unit_id, change)
        finally:
            self._suspend_event_autosync = False

        self.event_tracker.record_change_result(
            result,
            diff_report=diff_report,
            context=context,
            unit_existed_before=unit_existed_before,
        )
        new_events = self.event_tracker.events[start_index:]
        sync_results = self._sync_new_events(new_events)

        result["memory_events"] = new_events
        if sync_results:
            result["notion_sync_results"] = sync_results
        return result

    def record_gate_trigger_event(
        self,
        gate_result: Mapping[str, Any],
        *,
        unit_id: Optional[str] = None,
    ) -> dict[str, Any]:
        start_index = len(self.event_tracker.events)
        event = self.event_tracker.record_gate_trigger(gate_result, unit_id=unit_id)
        new_events = self.event_tracker.events[start_index:]
        sync_results = self._sync_new_events(new_events)
        response = {
            "event": event,
            "memory_events": new_events,
        }
        if sync_results:
            response["notion_sync_results"] = sync_results
        return response

    def sync_recorded_events_to_notion(
        self,
        events: Optional[list[MemoryEvent]] = None,
        *,
        mock_mode: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        return self.event_tracker.sync_events_to_notion(
            events=events,
            mock_mode=self.notion_mock_mode if mock_mode is None else mock_mode,
        )

    def _sync_new_events(self, events: list[MemoryEvent]) -> list[dict[str, Any]]:
        if not self.auto_sync_notion or not events:
            return []
        results = self.event_tracker.sync_events_to_notion(
            events=events,
            mock_mode=self.notion_mock_mode,
        )
        self.notion_sync_log.extend(results)
        return results

    def _snapshot_code_mappings(self) -> dict[str, list[dict[str, Any]]]:
        return {
            unit_id: [
                _mapping_to_dict(mapping)
                for mapping in self.code_mapping_registry.get_mappings_for_unit(unit_id)
            ]
            for unit_id in sorted(self.code_mapping_registry.as_unit_dict())
        }


__all__ = [
    "MEMORY_EVENTS_DB_ID",
    "MemoryEventType",
    "MemoryEvent",
    "MemoryEventTracker",
    "MemoryNetworkWithEvents",
]
