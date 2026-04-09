#!/usr/bin/env python3
"""
Phase 1: Core Schema Definitions

Defines the six core objects for the knowledge compiler:
- TaskSpec (existing, reused)
- ComponentSpec (existing, reused)
- ProcedureSpec (existing, reused)
- ReportSpec (NEW, Phase 1 core)
- EvidenceBundle (existing, enhanced)
- KnowledgeVersion (NEW, tracks knowledge state)
"""

from __future__ import annotations

import dataclasses
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


# ============================================================================
# Enums
# ============================================================================

class ProblemType(Enum):
    """CFD problem types"""
    INTERNAL_FLOW = "InternalFlow"
    EXTERNAL_FLOW = "ExternalFlow"
    HEAT_TRANSFER = "HeatTransfer"
    MULTIPHASE = "Multiphase"
    FSI = "FSI"


class KnowledgeLayer(Enum):
    """Four-layer knowledge model"""
    RAW = "Raw"           # Engineer direct input (teach records)
    PARSED = "Parsed"       # Structured but not validated
    CANONICAL = "Canonical" # Validated, reusable template
    EXECUTABLE = "Executable" # Ready for automated generation


class KnowledgeStatus(Enum):
    """Knowledge state machine"""
    DRAFT = "draft"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class ComparisonType(Enum):
    """Comparison methods for results"""
    DIRECT = "direct"           # Side-by-side overlay
    DIFF = "diff"               # Difference plot
    RATIO = "ratio"             # Ratio/profiling plot
    PROBE = "probe"             # Line/rake comparison


class ErrorType(Enum):
    """Types of errors that trigger corrections"""
    # Data errors
    MISSING_DATA = "missing_data"           # Required data is missing
    INCORRECT_DATA = "incorrect_data"       # Data is wrong/inaccurate
    INCONSISTENT_DATA = "inconsistent_data"  # Data conflicts across sources

    # Process errors
    WRONG_PLOT = "wrong_plot"               # Incorrect plot type/parameters
    WRONG_METRIC = "wrong_metric"           # Wrong metric calculation
    WRONG_SECTION = "wrong_section"         # Wrong section location

    # Logic errors
    MISINTERPRETATION = "misinterpretation" # System misunderstood intent
    MISSING_EXPLANATION = "missing_explanation"  # Explanation not provided
    INCORRECT_INFERENCE = "incorrect_inference"  # Wrong conclusion drawn

    # Structural errors
    INVALID_ORDER = "invalid_order"         # Plot/metric in wrong order
    MISSING_COMPONENT = "missing_component" # Required component omitted
    DUPLICATE_CONTENT = "duplicate_content" # Unnecessary duplication

    # Other
    OTHER = "other"                         # Catch-all for other errors


class ImpactScope(Enum):
    """Scope of correction impact"""
    SINGLE_CASE = "single_case"             # Affects only this case
    SIMILAR_CASES = "similar_cases"         # Affects cases with similar problem_type
    ALL_CASES = "all_cases"                 # Affects all cases (global change)
    REPORT_SPEC = "report_spec"             # Affects the ReportSpec template
    GATE_DEFINITION = "gate_definition"     # Affects Gate logic


# ============================================================================
# Plot and Metric Specifications
# ============================================================================

@dataclass
class PlotSpec:
    """Specification for a single plot"""
    name: str
    plane: str  # xy, xz, yz, wall slice, etc.
    colormap: str  # jet, viridis, coolwarm, etc.
    range: str  # auto, [min, max], or specific range like "[0, 1]"


@dataclass
class MetricSpec:
    """Specification for a single metric"""
    name: str
    unit: str  # Pa, m/s, K, etc.
    comparison: ComparisonType  # How to compare multiple cases


@dataclass
class SectionSpec:
    """Specification for a critical section (visualization location)"""
    name: str
    type: str  # midplane, wall, centerline, iso-surface, etc.
    position: Dict[str, float]  # {"x": 0.5, "z": 0.1} for normalized position


@dataclass
class AnomalyRule:
    """Rule for explaining anomalies"""
    pattern: str  # Regex or pattern to match
    required_explanation: str  # What explanation is required when pattern matches


# ============================================================================
# ReportSpec (Phase 1 Core Output)
# ============================================================================

@dataclass
class ReportSpec:
    """
    Report Specification - Reusable reporting template

    This is the CORE output of Phase 1 knowledge collection.
    Represents accumulated wisdom from engineer teach-in sessions.

    Schema (strictly follows instruction):
    {
        "report_spec_id": "RSPEC-XXX",
        "name": "string",
        "problem_type": "InternalFlow|ExternalFlow|HeatTransfer|Multiphase|FSI",
        "required_plots": [{"name": "...", "plane": "...", "colormap": "...", "range": "..."}],
        "required_metrics": [{"name": "...", "unit": "...", "comparison": "..."}],
        "critical_sections": [{"name": "...", "type": "...", "position": {...}}],
        "plot_order": ["..."],
        "anomaly_explanation_rules": [{"pattern": "...", "required_explanation": "..."}],
        "comparison_method": {"type": "...", "tolerance_display": true},
        "knowledge_layer": "Raw|Parsed|Canonical|Executable",
        "knowledge_status": "draft|candidate|approved|deprecated",
        "source_cases": ["..."],
        "teach_records": ["..."],
        "replay_pass_rate": 0-100,
        "version": 1
    }
    """

    report_spec_id: str
    name: str
    problem_type: ProblemType
    required_plots: List[PlotSpec] = field(default_factory=list)
    required_metrics: List[MetricSpec] = field(default_factory=list)
    critical_sections: List[SectionSpec] = field(default_factory=list)
    plot_order: List[str] = field(default_factory=list)
    anomaly_explanation_rules: List[AnomalyRule] = field(default_factory=list)
    comparison_method: Dict[str, Any] = field(default_factory=lambda: {
        "type": "direct",
        "tolerance_display": True,
    })
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.RAW
    knowledge_status: KnowledgeStatus = KnowledgeStatus.DRAFT
    source_cases: List[str] = field(default_factory=list)  # Case IDs that contributed
    teach_records: List[str] = field(default_factory=list)  # TeachRecord IDs
    replay_pass_rate: float = 0.0  # 0-100, required for candidate/approved
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_source_case(self, case_id: str) -> None:
        """Add a source case ID"""
        if case_id not in self.source_cases:
            self.source_cases.append(case_id)
        self.updated_at = time.time()

    def add_teach_record(self, record_id: str) -> None:
        """Add a teach record ID"""
        if record_id not in self.teach_records:
            self.teach_records.append(record_id)
        self.updated_at = time.time()

    def calculate_replay_pass_rate(self, replay_results: List[bool]) -> None:
        """Calculate replay pass rate from validation results"""
        if not replay_results:
            self.replay_pass_rate = 0.0
            return

        passed = sum(1 for r in replay_results if r)
        self.replay_pass_rate = (passed / len(replay_results)) * 100
        self.updated_at = time.time()

    def transition_to(self, status: KnowledgeStatus) -> None:
        """Transition knowledge status"""
        self.knowledge_status = status
        self.updated_at = time.time()

    def increment_version(self) -> None:
        """Increment version for major updates"""
        self.version += 1
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "report_spec_id": self.report_spec_id,
            "name": self.name,
            "problem_type": self.problem_type.value,
            "required_plots": [
                {
                    "name": p.name,
                    "plane": p.plane,
                    "colormap": p.colormap,
                    "range": p.range,
                }
                for p in self.required_plots
            ],
            "required_metrics": [
                {
                    "name": m.name,
                    "unit": m.unit,
                    "comparison": m.comparison.value,
                }
                for m in self.required_metrics
            ],
            "critical_sections": [
                {
                    "name": s.name,
                    "type": s.type,
                    "position": s.position,
                }
                for s in self.critical_sections
            ],
            "plot_order": self.plot_order,
            "anomaly_explanation_rules": [
                {
                    "pattern": r.pattern,
                    "required_explanation": r.required_explanation,
                }
                for r in self.anomaly_explanation_rules
            ],
            "comparison_method": self.comparison_method,
            "knowledge_layer": self.knowledge_layer.value,
            "knowledge_status": self.knowledge_status.value,
            "source_cases": self.source_cases,
            "teach_records": self.teach_records,
            "replay_pass_rate": self.replay_pass_rate,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportSpec":
        """Load from dictionary"""
        return cls(
            report_spec_id=data["report_spec_id"],
            name=data["name"],
            problem_type=ProblemType(data["problem_type"]),
            required_plots=[
                PlotSpec(**p) for p in data.get("required_plots", [])
            ],
            required_metrics=[
                MetricSpec(
                    name=m["name"],
                    unit=m["unit"],
                    comparison=ComparisonType(m["comparison"]),
                )
                for m in data.get("required_metrics", [])
            ],
            critical_sections=[
                SectionSpec(
                    name=s["name"],
                    type=s["type"],
                    position=s["position"],
                )
                for s in data.get("critical_sections", [])
            ],
            plot_order=data.get("plot_order", []),
            anomaly_explanation_rules=[
                AnomalyRule(
                    pattern=r["pattern"],
                    required_explanation=r["required_explanation"],
                )
                for r in data.get("anomaly_explanation_rules", [])
            ],
            comparison_method=data.get("comparison_method", {}),
            knowledge_layer=KnowledgeLayer(data.get("knowledge_layer", "Raw")),
            knowledge_status=KnowledgeStatus(data.get("knowledge_status", "draft")),
            source_cases=data.get("source_cases", []),
            teach_records=data.get("teach_records", []),
            replay_pass_rate=data.get("replay_pass_rate", 0.0),
            version=data.get("version", 1),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ReportSpec":
        """Load from JSON"""
        return cls.from_dict(json.loads(json_str))

    def save(self, file_path: Path | str) -> None:
        """Save to file"""
        Path(file_path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, file_path: Path | str) -> "ReportSpec":
        """Load from file"""
        return cls.from_json(Path(file_path).read_text(encoding="utf-8"))


def create_report_spec_id() -> str:
    """Generate unique ReportSpec ID"""
    return f"RSPEC-{uuid.uuid4().hex[:12].upper()}"


# ============================================================================
# TeachRecord (Phase 1 Knowledge Raw Material)
# ============================================================================

@dataclass
class TeachOperation:
    """
    A single teach operation (engineer correction)

    Tracks what the engineer changed and why.
    """
    operation_type: Literal["add_plot", "remove_plot", "modify_plot",
                              "add_metric", "remove_metric", "modify_metric",
                              "adjust_section", "add_explanation", "modify_structure"]
    description: str  # What was changed
    reason: str  # Why (engineer explanation)
    is_generalizable: bool  # Can this apply to all similar cases?
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TeachRecord:
    """
    Teach Record - Raw layer knowledge from engineer interactions

    Captures engineer corrections and rationale during report generation.
    """
    teach_record_id: str
    case_id: str  # Which task/case this teaches about
    timestamp: float
    operations: List[TeachOperation] = field(default_factory=list)
    evidence_bundle_id: Optional[str] = None  # Linked EvidenceBundle

    def add_operation(
        self,
        operation_type: str,
        description: str,
        reason: str,
        is_generalizable: bool = False,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        """Add a teach operation"""
        op = TeachOperation(
            operation_type=operation_type,
            description=description,
            reason=reason,
            is_generalizable=is_generalizable,
            metadata=metadata or {},
        )
        self.operations.append(op)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "teach_record_id": self.teach_record_id,
            "case_id": self.case_id,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.utcfromtimestamp(self.timestamp).isoformat() + "Z",
            "operations": [
                {
                    "operation_type": op.operation_type,
                    "description": op.description,
                    "reason": op.reason,
                    "is_generalizable": op.is_generalizable,
                    "metadata": op.metadata,
                }
                for op in self.operations
            ],
            "evidence_bundle_id": self.evidence_bundle_id,
        }

    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeachRecord":
        """Load from dictionary"""
        ops = []
        for op_data in data.get("operations", []):
            ops.append(TeachOperation(**op_data))

        return cls(
            teach_record_id=data["teach_record_id"],
            case_id=data["case_id"],
            timestamp=data["timestamp"],
            operations=ops,
            evidence_bundle_id=data.get("evidence_bundle_id"),
        )

    def save(self, file_path: Path | str) -> None:
        """Save to file"""
        Path(file_path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, file_path: Path | str) -> "TeachRecord":
        """Load from file"""
        return cls.from_json(Path(file_path).read_text(encoding="utf-8"))

    @classmethod
    def from_json(cls, json_str: str) -> "TeachRecord":
        """Load from JSON"""
        return cls.from_dict(json.loads(json_str))


def create_teach_record_id() -> str:
    """Generate unique TeachRecord ID"""
    return f"TEACH-{uuid.uuid4().hex[:12].upper()}"


# ============================================================================
# CorrectionSpec (Learning Channel - Phase 1 Core)
# ============================================================================

@dataclass
class CorrectionSpec:
    """
    Correction Specification - The Primary Learning Channel

    When an engineer modifies system output, a CorrectionSpec MUST be generated.
    This ensures all corrections are traceable, replayable, and can improve
    future system behavior.

    Lifecycle:
    1. Engineer modifies output → CorrectionSpec created
    2. System analyzes pattern → linked to ReportSpec/TeachRecord
    3. Replay validation → correction verified
    4. Approved → becomes part of knowledge base

    Critical Rule: NEVER bypass CorrectionSpec to directly change results.
    """

    correction_id: str
    error_type: ErrorType
    wrong_output: Dict[str, Any]  # What the system produced (incorrect)
    correct_output: Dict[str, Any]  # What the engineer specified (correct)
    human_reason: str  # Why the correction was needed

    # Evidence traceability
    evidence: List[str] = field(default_factory=list)  # IDs of related evidence
    linked_teach_record_id: Optional[str] = None  # Related TeachRecord
    linked_report_spec_id: Optional[str] = None  # Related ReportSpec

    # Impact analysis
    impact_scope: ImpactScope = ImpactScope.SINGLE_CASE
    affected_components: List[str] = field(default_factory=list)  # Component names affected

    # Root cause analysis
    root_cause: Optional[str] = None  # Why the system made this error
    fix_action: Optional[str] = None  # What change prevents recurrence

    # Validation
    needs_replay: bool = True  # Whether this correction requires replay validation
    replay_status: Literal["pending", "passed", "failed", "skipped"] = "pending"
    replay_case_ids: List[str] = field(default_factory=list)  # Cases used for validation

    # Metadata
    timestamp: float = field(default_factory=time.time)
    author: str = "engineer"  # Who made the correction
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "correction_id": self.correction_id,
            "error_type": self.error_type.value,
            "wrong_output": self.wrong_output,
            "correct_output": self.correct_output,
            "human_reason": self.human_reason,
            "evidence": self.evidence,
            "linked_teach_record_id": self.linked_teach_record_id,
            "linked_report_spec_id": self.linked_report_spec_id,
            "impact_scope": self.impact_scope.value,
            "affected_components": self.affected_components,
            "root_cause": self.root_cause,
            "fix_action": self.fix_action,
            "needs_replay": self.needs_replay,
            "replay_status": self.replay_status,
            "replay_case_ids": self.replay_case_ids,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.utcfromtimestamp(self.timestamp).isoformat() + "Z",
            "author": self.author,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def mark_replay_passed(self) -> None:
        """Mark replay as passed"""
        self.replay_status = "passed"

    def mark_replay_failed(self, reason: str) -> None:
        """Mark replay as failed with reason"""
        self.replay_status = "failed"
        self.metadata["replay_failure_reason"] = reason

    def link_to_teach_record(self, teach_record_id: str) -> None:
        """Link to a TeachRecord"""
        self.linked_teach_record_id = teach_record_id

    def link_to_report_spec(self, report_spec_id: str) -> None:
        """Link to a ReportSpec"""
        self.linked_report_spec_id = report_spec_id

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CorrectionSpec":
        """Load from dictionary"""
        return cls(
            correction_id=data["correction_id"],
            error_type=ErrorType(data["error_type"]),
            wrong_output=data["wrong_output"],
            correct_output=data["correct_output"],
            human_reason=data["human_reason"],
            evidence=data.get("evidence", []),
            linked_teach_record_id=data.get("linked_teach_record_id"),
            linked_report_spec_id=data.get("linked_report_spec_id"),
            impact_scope=ImpactScope(data.get("impact_scope", "single_case")),
            affected_components=data.get("affected_components", []),
            root_cause=data.get("root_cause"),
            fix_action=data.get("fix_action"),
            needs_replay=data.get("needs_replay", True),
            replay_status=data.get("replay_status", "pending"),
            replay_case_ids=data.get("replay_case_ids", []),
            timestamp=data.get("timestamp", time.time()),
            author=data.get("author", "engineer"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "CorrectionSpec":
        """Load from JSON"""
        return cls.from_dict(json.loads(json_str))

    def save(self, file_path: Path | str) -> None:
        """Save to file"""
        Path(file_path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, file_path: Path | str) -> "CorrectionSpec":
        """Load from file"""
        return cls.from_json(Path(file_path).read_text(encoding="utf-8"))


def create_correction_id() -> str:
    """Generate unique CorrectionSpec ID"""
    return f"CORRECT-{uuid.uuid4().hex[:12].upper()}"


# ============================================================================
# KnowledgeVersion (Tracks knowledge artifacts)
# ============================================================================

@dataclass
class KnowledgeVersion:
    """
    Knowledge Version - Tracks version of knowledge artifacts

    Maps ReportSpec and TeachRecord versions to content hashes.
    """
    version_id: str
    artifact_type: Literal["report_spec", "teach_record"]
    content_hash: str  # SHA256 of content
    previous_version_id: Optional[str] = None  # For version chain
    knowledge_status: KnowledgeStatus = KnowledgeStatus.DRAFT
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "version_id": self.version_id,
            "artifact_type": self.artifact_type,
            "content_hash": self.content_hash,
            "previous_version_id": self.previous_version_id,
            "knowledge_status": self.knowledge_status.value,
            "created_at": self.created_at,
            "created_at_iso": datetime.utcfromtimestamp(self.created_at).isoformat() + "Z",
        }


# ============================================================================
# ResultManifest (Module 1 Output)
# ============================================================================

@dataclass
class ResultAsset:
    """A single asset in the result directory"""
    asset_type: Literal["field", "line_plot", "contour_plot", "mesh",
                      "surface_plot", "monitor_point", "residual_file",
                      "log_file", "geometry", "snapshot"]
    path: str  # Relative path from result root
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultManifest:
    """
    Result Manifest - Parsed result directory structure

    Output of Module 1 (Result Directory Parser).
    Lists all available assets for report generation.
    """
    solver_type: str  # openfoam, fluent, starccm+, etc.
    case_name: str
    result_root: str
    assets: List[ResultAsset] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_assets_by_type(self, asset_type: str) -> List[ResultAsset]:
        """Filter assets by type"""
        return [a for a in self.assets if a.asset_type == asset_type]

    def has_field_data(self) -> bool:
        """Check if field data (probes) are available"""
        return any(a.asset_type == "monitor_point" for a in self.assets)

    def has_residuals(self) -> bool:
        """Check if residual convergence data is available"""
        return any(a.asset_type == "residual_file" for a in self.assets)

    def get_plot_assets(self) -> List[ResultAsset]:
        """Get all plot assets"""
        return [
            a for a in self.assets
            if a.asset_type in ["line_plot", "contour_plot", "surface_plot"]
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "solver_type": self.solver_type,
            "case_name": self.case_name,
            "result_root": self.result_root,
            "assets": [
                {
                    "asset_type": a.asset_type,
                    "path": a.path,
                    "description": a.description,
                    "metadata": a.metadata,
                }
                for a in self.assets
            ],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResultManifest":
        """Load from dictionary"""
        assets = []
        for a_data in data.get("assets", []):
            assets.append(ResultAsset(
                asset_type=a_data["asset_type"],
                path=a_data["path"],
                description=a_data.get("description", ""),
                metadata=a_data.get("metadata", {}),
            ))

        return cls(
            solver_type=data["solver_type"],
            case_name=data["case_name"],
            result_root=data["result_root"],
            assets=assets,
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ResultManifest":
        """Load from JSON"""
        return cls.from_dict(json.loads(json_str))

    def save(self, file_path: Path | str) -> None:
        """Save to file"""
        Path(file_path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, file_path: Path | str) -> "ResultManifest":
        """Load from file"""
        return cls.from_json(Path(file_path).read_text(encoding="utf-8"))


# ============================================================================
# ReportDraft (Module 2 Output)
# ============================================================================

@dataclass
class ReportDraft:
    """
    Report Draft - Skeleton report ready for engineer Teach Mode

    Output of Module 2 (Report Skeleton Generator).
    Contains plot slots and metric slots populated from ResultManifest.
    """
    draft_id: str
    case_id: str
    task_spec_id: str
    report_spec_id: Optional[str] = None  # If using existing ReportSpec
    plots: List[Dict[str, Any]] = field(default_factory=list)  # Plot specifications
    metrics: List[Dict[str, Any]] = field(default_factory=list)  # Metric specifications
    structure: Dict[str, Any] = field(default_factory=dict)  # Report structure
    gates_status: Dict[str, bool] = field(default_factory=dict)  # Gate checks

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "draft_id": self.draft_id,
            "case_id": self.case_id,
            "task_spec_id": self.task_spec_id,
            "report_spec_id": self.report_spec_id,
            "plots": self.plots,
            "metrics": self.metrics,
            "structure": self.structure,
            "gates_status": self.gates_status,
        }


# ============================================================================
# Phase1Output (Phase 1 → Phase 2 Aggregation Interface)
# ============================================================================

@dataclass
class Phase1Output:
    """
    Phase 1 Output - Aggregation Interface for Phase 2 Integration

    This is the CONTRACT between Phase 1 and Phase 2.
    Defines all deliverables that Phase 1 provides to Phase 2.

    Contract:
    - Phase 2 consumes ONLY this interface from Phase 1
    - All Phase 1 outputs are aggregated here
    - Format versioning ensures backward compatibility

    Version: 1.0
    Last Updated: 2026-04-08
    """

    # Metadata
    output_id: str
    version: str = "1.0"
    generated_at: float = field(default_factory=time.time)

    # === Core Knowledge Artifacts ===
    # ReportSpec candidates ready for Phase 2 processing
    report_specs: List[ReportSpec] = field(default_factory=list)

    # CorrectionSpecs from engineer corrections
    correction_specs: List[CorrectionSpec] = field(default_factory=list)

    # TeachRecords from teach-in sessions
    teach_records: List[TeachRecord] = field(default_factory=list)

    # === Gold Standards ===
    # Gold standard references for validation
    gold_standards: Dict[str, ReportSpec] = field(default_factory=dict)

    # === Replay Results ===
    # Validation results from replay engine
    replay_results: List[Dict[str, Any]] = field(default_factory=list)

    # === Visualization Outputs ===
    # Generated plots and visualizations (from F2/F3)
    visualization_outputs: List[Dict[str, Any]] = field(default_factory=list)

    # === Gate Status ===
    # Aggregate gate check results
    gate_summary: Dict[str, Any] = field(default_factory=dict)

    # === Statistics ===
    # Phase 1 performance metrics
    stats: Dict[str, Any] = field(default_factory=dict)

    def add_report_spec(self, spec: ReportSpec) -> None:
        """Add a ReportSpec to output"""
        self.report_specs.append(spec)

    def add_correction_spec(self, correction: CorrectionSpec) -> None:
        """Add a CorrectionSpec to output"""
        self.correction_specs.append(correction)

    def add_teach_record(self, record: TeachRecord) -> None:
        """Add a TeachRecord to output"""
        self.teach_records.append(record)

    def add_gold_standard(self, name: str, spec: ReportSpec) -> None:
        """Add a gold standard reference"""
        self.gold_standards[name] = spec

    def add_replay_result(self, result: Dict[str, Any]) -> None:
        """Add a replay validation result"""
        self.replay_results.append(result)

    def add_visualization_output(self, output: Dict[str, Any]) -> None:
        """Add a visualization output"""
        self.visualization_outputs.append(output)

    def get_candidate_specs(self) -> List[ReportSpec]:
        """Get ReportSpecs with CANDIDATE or APPROVED status"""
        return [
            spec for spec in self.report_specs
            if spec.knowledge_status in [KnowledgeStatus.CANDIDATE, KnowledgeStatus.APPROVED]
        ]

    def get_pending_corrections(self) -> List[CorrectionSpec]:
        """Get CorrectionSpecs pending replay validation"""
        return [
            c for c in self.correction_specs
            if c.replay_status == "pending"
        ]

    def calculate_stats(self) -> None:
        """Calculate summary statistics"""
        self.stats = {
            "total_report_specs": len(self.report_specs),
            "candidate_specs": len(self.get_candidate_specs()),
            "total_corrections": len(self.correction_specs),
            "pending_corrections": len(self.get_pending_corrections()),
            "total_teach_records": len(self.teach_records),
            "gold_standards": len(self.gold_standards),
            "replay_pass_rate": self._calculate_replay_pass_rate(),
        }

    def _calculate_replay_pass_rate(self) -> float:
        """Calculate overall replay pass rate"""
        if not self.replay_results:
            return 0.0

        passed = sum(1 for r in self.replay_results if r.get("passed", False))
        return (passed / len(self.replay_results)) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Phase 2 consumption"""
        return {
            "output_id": self.output_id,
            "version": self.version,
            "generated_at": self.generated_at,
            "generated_at_iso": datetime.utcfromtimestamp(self.generated_at).isoformat() + "Z",
            "report_specs": [
                {
                    "spec_id": spec.report_spec_id,
                    "name": spec.name,
                    "problem_type": spec.problem_type.value,
                    "status": spec.knowledge_status.value,
                    "layer": spec.knowledge_layer.value,
                    "version": spec.version,
                }
                for spec in self.report_specs
            ],
            "correction_specs": [
                {
                    "correction_id": c.correction_id,
                    "error_type": c.error_type.value,
                    "impact_scope": c.impact_scope.value,
                    "replay_status": c.replay_status,
                }
                for c in self.correction_specs
            ],
            "teach_records": [
                {
                    "record_id": r.teach_record_id,
                    "case_id": r.case_id,
                    "operations_count": len(r.operations),
                }
                for r in self.teach_records
            ],
            "gold_standards": list(self.gold_standards.keys()),
            "replay_results": self.replay_results,
            "visualization_outputs": self.visualization_outputs,
            "gate_summary": self.gate_summary,
            "stats": self.stats,
        }

    def to_json(self) -> str:
        """Convert to JSON for Phase 2 consumption"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def save(self, file_path: Path | str) -> None:
        """Save to file for Phase 2 pickup"""
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Phase1Output":
        """Load from dictionary (Phase 2 perspective)"""
        return cls(
            output_id=data["output_id"],
            version=data.get("version", "1.0"),
            generated_at=data.get("generated_at", time.time()),
            stats=data.get("stats", {}),
            gate_summary=data.get("gate_summary", {}),
        )

    @classmethod
    def load(cls, file_path: Path | str) -> "Phase1Output":
        """Load from file (Phase 2 pickup)"""
        return cls.from_dict(json.loads(Path(file_path).read_text(encoding="utf-8")))


def create_phase1_output_id() -> str:
    """Generate unique Phase1Output ID"""
    return f"P1OUT-{uuid.uuid4().hex[:12].upper()}"


# ============================================================================
# AnalogySpec (Phase 3 Reserved)
# ============================================================================

@dataclass
class AnalogySpec:
    """
    Analogy Specification - Phase 3 Reserved

    Placeholder for Phase 3 analogy-based reasoning.
    Ensures schema stability when Phase 3 is implemented.

    NOTE: This is a stub definition. Full implementation in Phase 3.
    """
    analogy_id: str
    source_case_id: str
    target_case_id: str
    similarity_score: float  # 0-1
    analogy_type: Optional[str] = None  # To be defined in Phase 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "analogy_id": self.analogy_id,
            "source_case_id": self.source_case_id,
            "target_case_id": self.target_case_id,
            "similarity_score": self.similarity_score,
            "analogy_type": self.analogy_type,
            "metadata": self.metadata,
        }


# ============================================================================
# Export
# ============================================================================

__all__ = [
    # Enums
    "ProblemType",
    "KnowledgeLayer",
    "KnowledgeStatus",
    "ComparisonType",
    "ErrorType",
    "ImpactScope",
    # Specs
    "PlotSpec",
    "MetricSpec",
    "SectionSpec",
    "AnomalyRule",
    # Core objects
    "ReportSpec",
    "TeachRecord",
    "TeachOperation",
    "KnowledgeVersion",
    "CorrectionSpec",
    "ResultManifest",
    "ResultAsset",
    "ReportDraft",
    # Phase 1 → Phase 2 Interface
    "Phase1Output",
    # Phase 3 Reserved
    "AnalogySpec",
    # Factory functions
    "create_report_spec_id",
    "create_teach_record_id",
    "create_correction_id",
    "create_phase1_output_id",
]
