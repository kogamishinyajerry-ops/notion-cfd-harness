#!/usr/bin/env python3
"""
Phase 1 Module 3: Teach Mode Engine (CORE)

捕获工程师交互，记录为TeachRecord，支持Teach Mode工作流。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from knowledge_compiler.phase1.schema import (
    TeachRecord,
    TeachOperation,
    ReportSpec,
    ReportDraft,
    ProblemType,
    KnowledgeLayer,
    KnowledgeStatus,
    create_teach_record_id,
)


# ============================================================================
# Operation Types
# ============================================================================

OperationType = Literal[
    "add_plot",
    "remove_plot",
    "modify_plot",
    "add_metric",
    "remove_metric",
    "modify_metric",
    "adjust_section",
    "add_explanation",
    "modify_structure",
]


# ============================================================================
# Teach Context
# ============================================================================

@dataclass
class TeachContext:
    """
    Context for a teach operation

    Captures the state when an engineer makes a correction.
    """
    draft_id: str
    case_id: str
    timestamp: float
    previous_state: Dict[str, Any]
    operation_type: OperationType
    session_id: Optional[str] = None  # For grouping related operations


@dataclass
class TeachResponse:
    """
    Response from processing a teach operation
    """
    teach_record_id: str
    success: bool
    message: str
    applied_to_draft: bool
    generalizable: bool
    warnings: List[str] = field(default_factory=list)


# ============================================================================
# Evidence Bundle Linkage
# ============================================================================

@dataclass
class EvidenceReference:
    """
    Reference to evidence supporting a teach operation
    """
    evidence_type: Literal["experimental", "analytical", "literature", "simulation"]
    source_id: str  # DOI, report ID, etc.
    description: str
    confidence: float  # 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Teach Mode Engine (CORE)
# ============================================================================

class TeachModeEngine:
    """
    Teach Mode Engine - CORE of Phase 1

    Captures engineer interactions during report generation and records them
    as TeachRecords in the Raw knowledge layer.

    Key Principles:
    - Engineer input ALWAYS enters at Raw layer (never directly to Canonical)
    - Each operation is recorded with full context and rationale
    - Generalizable operations are marked for potential promotion
    - Links to EvidenceBundle for traceability
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize Teach Mode Engine

        Args:
            storage_path: Path to store teach records (defaults to ./teach_records/)
        """
        self.storage_path = storage_path or Path("./teach_records")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._active_session: Optional[str] = None
        self._session_records: List[str] = []

    def start_session(self, session_id: Optional[str] = None) -> str:
        """
        Start a new teach session

        A session groups related teach operations.

        Args:
            session_id: Optional session ID (auto-generated if not provided)

        Returns:
            The session ID
        """
        self._active_session = session_id or f"SESSION-{uuid.uuid4().hex[:8].upper()}"
        self._session_records = []
        return self._active_session

    def end_session(self) -> List[str]:
        """
        End the current teach session

        Returns:
            List of teach record IDs in this session
        """
        records = self._session_records.copy()
        self._active_session = None
        self._session_records = []
        return records

    def record_operation(
        self,
        context: TeachContext,
        description: str,
        reason: str,
        is_generalizable: bool,
        metadata: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[EvidenceReference]] = None,
    ) -> TeachResponse:
        """
        Record a teach operation

        This is the CORE method - all engineer corrections flow through here.

        Args:
            context: Teach context with operation details
            description: What was changed
            reason: Why (engineer explanation)
            is_generalizable: Whether this applies to all similar cases
            metadata: Optional additional metadata
            evidence: Optional supporting evidence references

        Returns:
            TeachResponse with record ID and status
        """
        # Validate operation type
        if context.operation_type not in OperationType.__args__:
            return TeachResponse(
                teach_record_id="",
                success=False,
                message=f"Invalid operation type: {context.operation_type}",
                applied_to_draft=False,
                generalizable=False,
            )

        # Create teach record
        record_id = create_teach_record_id()

        # Set session if active
        session_id = context.session_id or self._active_session

        # Build metadata
        record_metadata = metadata or {}
        record_metadata.update({
            "session_id": session_id,
            "draft_id": context.draft_id,
        })

        # Add evidence references if provided
        if evidence:
            record_metadata["evidence"] = [
                {
                    "type": ev.evidence_type,
                    "source_id": ev.source_id,
                    "description": ev.description,
                    "confidence": ev.confidence,
                }
                for ev in evidence
            ]

        # Create the record
        record = TeachRecord(
            teach_record_id=record_id,
            case_id=context.case_id,
            timestamp=context.timestamp,
            operations=[],  # Will add operation below
            evidence_bundle_id=session_id,
        )

        # Add the operation
        record.add_operation(
            operation_type=context.operation_type,
            description=description,
            reason=reason,
            is_generalizable=is_generalizable,
            metadata=record_metadata,
        )

        # Save record
        self._save_record(record)

        # Track in session
        if self._active_session:
            self._session_records.append(record_id)

        return TeachResponse(
            teach_record_id=record_id,
            success=True,
            message=f"Recorded {context.operation_type} operation",
            applied_to_draft=False,  # Application is separate from recording
            generalizable=is_generalizable,
        )

    def apply_to_draft(
        self,
        draft: ReportDraft,
        operation: TeachOperation,
    ) -> ReportDraft:
        """
        Apply a teach operation to a report draft

        This modifies the draft in-place and returns it.

        Args:
            draft: The report draft to modify
            operation: The operation to apply

        Returns:
            Modified draft
        """
        if operation.operation_type == "add_plot":
            self._apply_add_plot(draft, operation)
        elif operation.operation_type == "remove_plot":
            self._apply_remove_plot(draft, operation)
        elif operation.operation_type == "modify_plot":
            self._apply_modify_plot(draft, operation)
        elif operation.operation_type == "add_metric":
            self._apply_add_metric(draft, operation)
        elif operation.operation_type == "remove_metric":
            self._apply_remove_metric(draft, operation)
        elif operation.operation_type == "modify_metric":
            self._apply_modify_metric(draft, operation)
        elif operation.operation_type == "adjust_section":
            self._apply_adjust_section(draft, operation)
        elif operation.operation_type == "add_explanation":
            self._apply_add_explanation(draft, operation)
        elif operation.operation_type == "modify_structure":
            self._apply_modify_structure(draft, operation)

        return draft

    def _apply_add_plot(self, draft: ReportDraft, operation: TeachOperation) -> None:
        """Apply add_plot operation"""
        plot_spec = operation.metadata.get("plot_spec", {})
        draft.plots.append(plot_spec)

    def _apply_remove_plot(self, draft: ReportDraft, operation: TeachOperation) -> None:
        """Apply remove_plot operation"""
        plot_name = operation.metadata.get("plot_name")
        draft.plots = [p for p in draft.plots if p.get("name") != plot_name]

    def _apply_modify_plot(self, draft: ReportDraft, operation: TeachOperation) -> None:
        """Apply modify_plot operation"""
        plot_name = operation.metadata.get("plot_name")
        modifications = operation.metadata.get("modifications", {})

        for plot in draft.plots:
            if plot.get("name") == plot_name:
                plot.update(modifications)
                break

    def _apply_add_metric(self, draft: ReportDraft, operation: TeachOperation) -> None:
        """Apply add_metric operation"""
        metric_spec = operation.metadata.get("metric_spec", {})
        draft.metrics.append(metric_spec)

    def _apply_remove_metric(self, draft: ReportDraft, operation: TeachOperation) -> None:
        """Apply remove_metric operation"""
        metric_name = operation.metadata.get("metric_name")
        draft.metrics = [m for m in draft.metrics if m.get("name") != metric_name]

    def _apply_modify_metric(self, draft: ReportDraft, operation: TeachOperation) -> None:
        """Apply modify_metric operation"""
        metric_name = operation.metadata.get("metric_name")
        modifications = operation.metadata.get("modifications", {})

        for metric in draft.metrics:
            if metric.get("name") == metric_name:
                metric.update(modifications)
                break

    def _apply_adjust_section(self, draft: ReportDraft, operation: TeachOperation) -> None:
        """Apply adjust_section operation"""
        section_id = operation.metadata.get("section_id")
        adjustments = operation.metadata.get("adjustments", {})

        if "structure" not in draft.structure:
            draft.structure["sections"] = {}

        draft.structure["sections"][section_id] = adjustments

    def _apply_add_explanation(self, draft: ReportDraft, operation: TeachOperation) -> None:
        """Apply add_explanation operation"""
        if "explanations" not in draft.structure:
            draft.structure["explanations"] = []

        draft.structure["explanations"].append({
            "content": operation.description,
            "reason": operation.reason,
            "timestamp": time.time(),
        })

    def _apply_modify_structure(self, draft: ReportDraft, operation: TeachOperation) -> None:
        """Apply modify_structure operation"""
        modifications = operation.metadata.get("structure_changes", {})
        draft.structure.update(modifications)

    def _save_record(self, record: TeachRecord) -> None:
        """Save teach record to storage"""
        file_path = self.storage_path / f"{record.teach_record_id}.json"
        record.save(file_path)

    def load_record(self, record_id: str) -> Optional[TeachRecord]:
        """Load teach record from storage"""
        file_path = self.storage_path / f"{record_id}.json"
        if file_path.exists():
            return TeachRecord.load(file_path)
        return None

    def list_records(
        self,
        case_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[TeachRecord]:
        """
        List teach records with optional filtering

        Args:
            case_id: Filter by case ID
            session_id: Filter by session ID

        Returns:
            List of matching teach records
        """
        records = []

        for file_path in self.storage_path.glob("TEACH-*.json"):
            try:
                record = TeachRecord.load(file_path)

                # Apply filters
                if case_id and record.case_id != case_id:
                    continue
                if session_id and record.operations:
                    # Check session_id in first operation's metadata
                    op_session = record.operations[0].metadata.get("session_id")
                    if op_session != session_id:
                        continue

                records.append(record)
            except Exception:
                # Skip invalid records
                continue

        # Sort by timestamp
        records.sort(key=lambda r: r.timestamp)
        return records

    def promote_to_report_spec(
        self,
        teach_records: List[TeachRecord],
        name: str,
        problem_type: ProblemType,
    ) -> ReportSpec:
        """
        Promote generalizable teach operations to a ReportSpec

        This moves knowledge from Raw → Parsed layer.

        Args:
            teach_records: List of teach records to promote
            name: Name for the new ReportSpec
            problem_type: Problem type for the ReportSpec

        Returns:
            New ReportSpec at Parsed layer
        """
        from knowledge_compiler.phase1.schema import (
            PlotSpec,
            MetricSpec,
            create_report_spec_id,
            ComparisonType,
        )

        spec_id = create_report_spec_id()

        # Collect generalizable operations
        required_plots = []
        required_metrics = []

        for record in teach_records:
            for operation in record.operations:
                if not operation.is_generalizable:
                    continue

                if operation.operation_type == "add_plot":
                    plot_data = operation.metadata.get("plot_spec", {})
                    required_plots.append(PlotSpec(
                        name=plot_data.get("name", "unnamed"),
                        plane=plot_data.get("plane", "xy"),
                        colormap=plot_data.get("colormap", "viridis"),
                        range=plot_data.get("range", "auto"),
                    ))

                elif operation.operation_type == "add_metric":
                    metric_data = operation.metadata.get("metric_spec", {})
                    comparison_type = ComparisonType.DIRECT
                    if "comparison" in metric_data:
                        try:
                            comparison_type = ComparisonType(metric_data["comparison"])
                        except ValueError:
                            pass

                    required_metrics.append(MetricSpec(
                        name=metric_data.get("name", "unnamed"),
                        unit=metric_data.get("unit", "-"),
                        comparison=comparison_type,
                    ))

        # Create ReportSpec at Parsed layer
        spec = ReportSpec(
            report_spec_id=spec_id,
            name=name,
            problem_type=problem_type,
            required_plots=required_plots,
            required_metrics=required_metrics,
            knowledge_layer=KnowledgeLayer.PARSED,  # Promoted from Raw
            knowledge_status=KnowledgeStatus.CANDIDATE,
            source_cases=list({r.case_id for r in teach_records}),
            teach_records=[r.teach_record_id for r in teach_records],
        )

        return spec


# ============================================================================
# Convenience Functions
# ============================================================================

def record_teach_operation(
    case_id: str,
    draft_id: str,
    operation_type: OperationType,
    description: str,
    reason: str,
    is_generalizable: bool,
    engine: Optional[TeachModeEngine] = None,
    storage_path: Optional[Path] = None,
) -> TeachResponse:
    """
    Convenience function to record a teach operation

    Args:
        case_id: Case identifier
        draft_id: Report draft identifier
        operation_type: Type of operation
        description: What was changed
        reason: Why (engineer explanation)
        is_generalizable: Whether this applies to similar cases
        engine: Optional existing TeachModeEngine
        storage_path: Optional storage path

    Returns:
        TeachResponse
    """
    if engine is None:
        engine = TeachModeEngine(storage_path)

    context = TeachContext(
        draft_id=draft_id,
        case_id=case_id,
        timestamp=time.time(),
        previous_state={},
        operation_type=operation_type,
    )

    return engine.record_operation(
        context=context,
        description=description,
        reason=reason,
        is_generalizable=is_generalizable,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OperationType",
    "TeachContext",
    "TeachResponse",
    "EvidenceReference",
    "TeachModeEngine",
    "record_teach_operation",
]
