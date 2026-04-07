#!/usr/bin/env python3
"""
Phase 1 Module 4: ReportSpec Manager

管理ReportSpec生命周期：draft → candidate → approved → deprecated
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from knowledge_compiler.phase1.schema import (
    ProblemType,
    KnowledgeLayer,
    KnowledgeStatus,
    ReportSpec,
    TeachRecord,
    PlotSpec,
    MetricSpec,
    ComparisonType,
    create_report_spec_id,
)


# ============================================================================
# Validation Results
# ============================================================================

@dataclass
class ValidationResult:
    """Result of validating a ReportSpec"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: float = 0.0  # 0-100
    required_fields: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)


@dataclass
class PromotionResult:
    """Result of promoting a ReportSpec"""
    success: bool
    from_status: KnowledgeStatus
    to_status: KnowledgeStatus
    message: str
    validation_result: Optional[ValidationResult] = None


# ============================================================================
# ReportSpec Manager
# ============================================================================

class ReportSpecManager:
    """
    Manage ReportSpec lifecycle and operations

    Handles:
    - CRUD operations for ReportSpec
    - Status transitions (draft → candidate → approved → deprecated)
    - Validation before promotion
    - Discovery and matching
    - Replay pass rate tracking
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize ReportSpec Manager

        Args:
            storage_path: Path to store ReportSpec files
        """
        self.storage_path = storage_path or Path("./report_specs")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, ReportSpec] = {}
        self._build_index()

    def _build_index(self) -> None:
        """Build in-memory index from storage"""
        self._index = {}

        for file_path in self.storage_path.glob("RSPEC-*.json"):
            try:
                spec = ReportSpec.load(file_path)
                self._index[spec.report_spec_id] = spec
            except Exception:
                # Skip invalid files
                continue

    def _save_to_index(self, spec: ReportSpec) -> None:
        """Save spec to storage and update index"""
        file_path = self.storage_path / f"{spec.report_spec_id}.json"
        spec.save(file_path)
        self._index[spec.report_spec_id] = spec

    # ========================================================================
    # CRUD Operations
    # ========================================================================

    def create(
        self,
        name: str,
        problem_type: ProblemType,
        required_plots: Optional[List[PlotSpec]] = None,
        required_metrics: Optional[List[MetricSpec]] = None,
        knowledge_layer: KnowledgeLayer = KnowledgeLayer.RAW,
    ) -> ReportSpec:
        """
        Create a new ReportSpec

        Args:
            name: Name for the ReportSpec
            problem_type: Problem type
            required_plots: Optional list of required plots
            required_metrics: Optional list of required metrics
            knowledge_layer: Knowledge layer (default: Raw)

        Returns:
            Created ReportSpec
        """
        spec_id = create_report_spec_id()

        spec = ReportSpec(
            report_spec_id=spec_id,
            name=name,
            problem_type=problem_type,
            required_plots=required_plots or [],
            required_metrics=required_metrics or [],
            knowledge_layer=knowledge_layer,
            knowledge_status=KnowledgeStatus.DRAFT,
        )

        self._save_to_index(spec)
        return spec

    def get(self, spec_id: str) -> Optional[ReportSpec]:
        """
        Get ReportSpec by ID

        Args:
            spec_id: ReportSpec ID

        Returns:
            ReportSpec or None if not found
        """
        return self._index.get(spec_id)

    def list(
        self,
        problem_type: Optional[ProblemType] = None,
        knowledge_layer: Optional[KnowledgeLayer] = None,
        knowledge_status: Optional[KnowledgeStatus] = None,
    ) -> List[ReportSpec]:
        """
        List ReportSpecs with optional filtering

        Args:
            problem_type: Filter by problem type
            knowledge_layer: Filter by knowledge layer
            knowledge_status: Filter by status

        Returns:
            List of matching ReportSpecs
        """
        results = list(self._index.values())

        if problem_type:
            results = [s for s in results if s.problem_type == problem_type]
        if knowledge_layer:
            results = [s for s in results if s.knowledge_layer == knowledge_layer]
        if knowledge_status:
            results = [s for s in results if s.knowledge_status == knowledge_status]

        return results

    def update(self, spec: ReportSpec) -> ReportSpec:
        """
        Update an existing ReportSpec

        Args:
            spec: ReportSpec with updated values

        Returns:
            Updated ReportSpec
        """
        if spec.report_spec_id not in self._index:
            raise ValueError(f"ReportSpec {spec.report_spec_id} not found")

        spec.updated_at = time.time()
        self._save_to_index(spec)
        return spec

    def delete(self, spec_id: str) -> bool:
        """
        Delete a ReportSpec

        Args:
            spec_id: ReportSpec ID

        Returns:
            True if deleted, False if not found
        """
        if spec_id not in self._index:
            return False

        # Delete file
        file_path = self.storage_path / f"{spec_id}.json"
        if file_path.exists():
            file_path.unlink()

        # Remove from index
        del self._index[spec_id]
        return True

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    def promote(
        self,
        spec_id: str,
        to_status: KnowledgeStatus,
        validate: bool = True,
    ) -> PromotionResult:
        """
        Promote ReportSpec to new status

        Transition rules:
        - draft → candidate: Requires validation pass
        - candidate → approved: Requires replay pass rate >= 70%
        - approved → deprecated: Always allowed

        Args:
            spec_id: ReportSpec ID
            to_status: Target status
            validate: Whether to validate before promotion

        Returns:
            PromotionResult
        """
        spec = self.get(spec_id)
        if not spec:
            return PromotionResult(
                success=False,
                from_status=KnowledgeStatus.DRAFT,
                to_status=to_status,
                message=f"ReportSpec {spec_id} not found",
            )

        from_status = spec.knowledge_status

        # Validate transition
        validation_result = None
        if validate:
            validation_result = self._validate_for_promotion(spec, to_status)

            if not validation_result.is_valid:
                # Include first error in message
                error_msg = validation_result.errors[0] if validation_result.errors else "Validation failed"
                return PromotionResult(
                    success=False,
                    from_status=from_status,
                    to_status=to_status,
                    message=f"Validation failed: {error_msg}",
                    validation_result=validation_result,
                )

        # Apply transition
        spec.transition_to(to_status)
        self.update(spec)

        return PromotionResult(
            success=True,
            from_status=from_status,
            to_status=to_status,
            message=f"Promoted from {from_status.value} to {to_status.value}",
            validation_result=validation_result,
        )

    def _validate_for_promotion(
        self,
        spec: ReportSpec,
        to_status: KnowledgeStatus,
    ) -> ValidationResult:
        """
        Validate ReportSpec before promotion

        Args:
            spec: ReportSpec to validate
            to_status: Target status

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        score = 100.0

        # Base required fields
        required_fields = ["name", "problem_type"]
        missing_fields = []

        if not spec.name:
            missing_fields.append("name")
        if not spec.required_plots and not spec.required_metrics:
            missing_fields.append("required_plots or required_metrics")

        # Status-specific validation
        if to_status == KnowledgeStatus.CANDIDATE:
            # Candidate needs at least some plots/metrics
            if len(spec.required_plots) == 0 and len(spec.required_metrics) == 0:
                errors.append("Candidate ReportSpec must have at least plots or metrics")
                score -= 50.0

            # Check for source cases
            if len(spec.source_cases) == 0:
                warnings.append("Candidate ReportSpec has no source cases")
                score -= 10.0

        elif to_status == KnowledgeStatus.APPROVED:
            # Approved needs replay pass rate
            if spec.replay_pass_rate < 70.0:
                errors.append(f"Replay pass rate {spec.replay_pass_rate}% < 70% required for approval")
                score -= (70.0 - spec.replay_pass_rate)

            # Must have teach records
            if len(spec.teach_records) == 0:
                warnings.append("Approved ReportSpec has no teach records")

        # Calculate score
        score = max(0.0, min(100.0, score))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            score=score,
            required_fields=required_fields,
            missing_fields=missing_fields,
        )

    # ========================================================================
    # Discovery and Matching
    # ========================================================================

    def find_best_match(
        self,
        problem_type: ProblemType,
        preferred_layers: Optional[List[KnowledgeLayer]] = None,
    ) -> Optional[ReportSpec]:
        """
        Find the best matching ReportSpec for a problem type

        Prefers: Canonical > Parsed > Raw
        Filters by: Approved > Candidate > Draft

        Args:
            problem_type: Problem type to match
            preferred_layers: Optional layer preference order

        Returns:
            Best matching ReportSpec or None
        """
        if preferred_layers is None:
            preferred_layers = [
                KnowledgeLayer.CANONICAL,
                KnowledgeLayer.PARSED,
                KnowledgeLayer.RAW,
            ]

        # Get all specs for problem type
        candidates = self.list(problem_type=problem_type)

        if not candidates:
            return None

        # Sort by preference
        def sort_key(spec: ReportSpec) -> tuple:
            # Layer priority (lower is better)
            try:
                layer_priority = preferred_layers.index(spec.knowledge_layer)
            except ValueError:
                layer_priority = len(preferred_layers)

            # Status priority (approved > candidate > draft)
            status_priority = {
                KnowledgeStatus.APPROVED: 0,
                KnowledgeStatus.CANDIDATE: 1,
                KnowledgeStatus.DRAFT: 2,
                KnowledgeStatus.DEPRECATED: 3,
            }.get(spec.knowledge_status, 99)

            # Replay pass rate (higher is better)
            pass_rate = -spec.replay_pass_rate  # Negate for ascending sort

            return (layer_priority, status_priority, pass_rate)

        candidates.sort(key=sort_key)
        return candidates[0]

    # ========================================================================
    # Replay Pass Rate Management
    # ========================================================================

    def update_replay_pass_rate(
        self,
        spec_id: str,
        replay_results: List[bool],
    ) -> ReportSpec:
        """
        Update replay pass rate for a ReportSpec

        Args:
            spec_id: ReportSpec ID
            replay_results: List of boolean replay results

        Returns:
            Updated ReportSpec
        """
        spec = self.get(spec_id)
        if not spec:
            raise ValueError(f"ReportSpec {spec_id} not found")

        spec.calculate_replay_pass_rate(replay_results)
        self.update(spec)
        return spec

    # ========================================================================
    # Teach Record Integration
    # ========================================================================

    def add_teach_record(
        self,
        spec_id: str,
        teach_record_id: str,
    ) -> ReportSpec:
        """
        Link a teach record to a ReportSpec

        Args:
            spec_id: ReportSpec ID
            teach_record_id: TeachRecord ID

        Returns:
            Updated ReportSpec
        """
        spec = self.get(spec_id)
        if not spec:
            raise ValueError(f"ReportSpec {spec_id} not found")

        spec.add_teach_record(teach_record_id)
        self.update(spec)
        return spec

    def add_source_case(
        self,
        spec_id: str,
        case_id: str,
    ) -> ReportSpec:
        """
        Link a source case to a ReportSpec

        Args:
            spec_id: ReportSpec ID
            case_id: Source case ID

        Returns:
            Updated ReportSpec
        """
        spec = self.get(spec_id)
        if not spec:
            raise ValueError(f"ReportSpec {spec_id} not found")

        spec.add_source_case(case_id)
        self.update(spec)
        return spec

    # ========================================================================
    # Batch Operations
    # ========================================================================

    def promote_to_approved(
        self,
        spec_ids: List[str],
        min_replay_rate: float = 70.0,
    ) -> Dict[str, PromotionResult]:
        """
        Batch promote multiple specs to approved status

        Args:
            spec_ids: List of ReportSpec IDs
            min_replay_rate: Minimum replay pass rate required

        Returns:
            Dict mapping spec_id to PromotionResult
        """
        results = {}

        for spec_id in spec_ids:
            spec = self.get(spec_id)
            if not spec:
                results[spec_id] = PromotionResult(
                    success=False,
                    from_status=KnowledgeStatus.DRAFT,
                    to_status=KnowledgeStatus.APPROVED,
                    message=f"ReportSpec {spec_id} not found",
                )
                continue

            # Check replay rate
            if spec.replay_pass_rate < min_replay_rate:
                results[spec_id] = PromotionResult(
                    success=False,
                    from_status=spec.knowledge_status,
                    to_status=KnowledgeStatus.APPROVED,
                    message=f"Replay pass rate {spec.replay_pass_rate}% < {min_replay_rate}% required",
                )
                continue

            # Promote
            results[spec_id] = self.promote(spec_id, KnowledgeStatus.APPROVED)

        return results

    def validate_all(
        self,
        knowledge_status: Optional[KnowledgeStatus] = None,
    ) -> Dict[str, ValidationResult]:
        """
        Validate all ReportSpecs

        Args:
            knowledge_status: Optional status filter

        Returns:
            Dict mapping spec_id to ValidationResult
        """
        results = {}

        for spec in self.list(knowledge_status=knowledge_status):
            # Validate against current status requirements
            validation = self._validate_for_promotion(
                spec,
                spec.knowledge_status,
            )
            results[spec.report_spec_id] = validation

        return results


# ============================================================================
# Convenience Functions
# ============================================================================

def create_report_spec(
    name: str,
    problem_type: ProblemType,
    plots: Optional[List[Dict[str, Any]]] = None,
    metrics: Optional[List[Dict[str, Any]]] = None,
    manager: Optional[ReportSpecManager] = None,
    storage_path: Optional[Path] = None,
) -> ReportSpec:
    """
    Convenience function to create a ReportSpec

    Args:
        name: Name for the ReportSpec
        problem_type: Problem type
        plots: Optional list of plot specs (as dicts)
        metrics: Optional list of metric specs (as dicts)
        manager: Optional existing ReportSpecManager
        storage_path: Optional storage path

    Returns:
        Created ReportSpec
    """
    if manager is None:
        manager = ReportSpecManager(storage_path)

    # Convert dicts to specs
    required_plots = []
    if plots:
        for p in plots:
            required_plots.append(PlotSpec(
                name=p.get("name", "unnamed"),
                plane=p.get("plane", "xy"),
                colormap=p.get("colormap", "viridis"),
                range=p.get("range", "auto"),
            ))

    required_metrics = []
    if metrics:
        for m in metrics:
            comparison = ComparisonType.DIRECT
            if "comparison" in m:
                try:
                    comparison = ComparisonType(m["comparison"])
                except ValueError:
                    pass

            required_metrics.append(MetricSpec(
                name=m.get("name", "unnamed"),
                unit=m.get("unit", "-"),
                comparison=comparison,
            ))

    return manager.create(
        name=name,
        problem_type=problem_type,
        required_plots=required_plots,
        required_metrics=required_metrics,
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "ValidationResult",
    "PromotionResult",
    "ReportSpecManager",
    "create_report_spec",
]
