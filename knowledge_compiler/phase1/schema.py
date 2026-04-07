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
# Export
# ============================================================================

__all__ = [
    # Enums
    "ProblemType",
    "KnowledgeLayer",
    "KnowledgeStatus",
    "ComparisonType",
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
    "ResultManifest",
    "ResultAsset",
    "ReportDraft",
    # Factory functions
    "create_report_spec_id",
    "create_teach_record_id",
]
