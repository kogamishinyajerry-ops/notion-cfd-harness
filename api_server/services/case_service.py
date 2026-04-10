"""
Case Service

Business logic for case management operations.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from api_server.config import DATA_DIR
from api_server.models import CaseResponse, CaseSpec, PermissionLevel, ProblemType

logger = logging.getLogger(__name__)

# In-memory case storage (in production, use a database)
_CASES: Dict[str, CaseResponse] = {}


class CaseService:
    """
    Service for managing CFD cases.

    Provides CRUD operations for cases stored in the system.
    In production, this would interface with a database.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize the case service.

        Args:
            storage_path: Path to case storage directory
        """
        self.storage_path = storage_path or DATA_DIR / "cases"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._load_cases()

    def _load_cases(self) -> None:
        """Load cases from storage."""
        index_file = self.storage_path / "cases_index.json"
        if index_file.exists():
            try:
                with open(index_file) as f:
                    data = json.load(f)
                    for case_data in data.get("cases", []):
                        case = CaseResponse(**case_data)
                        _CASES[case.case_id] = case
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cases index: {e}")

    def _save_cases(self) -> None:
        """Save cases to storage."""
        index_file = self.storage_path / "cases_index.json"
        try:
            with open(index_file, "w") as f:
                json.dump({
                    "cases": [case.model_dump(mode="json") for case in _CASES.values()]
                }, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"Failed to save cases index: {e}")

    def create_case(self, spec: CaseSpec) -> CaseResponse:
        """
        Create a new case.

        Args:
            spec: Case specification

        Returns:
            Created case response
        """
        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()

        case = CaseResponse(
            case_id=case_id,
            name=spec.name,
            problem_type=spec.problem_type,
            description=spec.description,
            status="created",
            created_at=now,
            updated_at=now,
            permission_level=spec.permission_level,
            metadata={
                "geometry_config": spec.geometry_config,
                "physics_models": spec.physics_models,
            },
        )

        _CASES[case_id] = case
        self._save_cases()

        logger.info(f"Created case: {case_id}")
        return case

    def get_case(self, case_id: str) -> Optional[CaseResponse]:
        """
        Get a case by ID.

        Args:
            case_id: Case identifier

        Returns:
            Case response or None if not found
        """
        return _CASES.get(case_id)

    def list_cases(
        self,
        offset: int = 0,
        limit: int = 50,
        problem_type: Optional[ProblemType] = None,
        status: Optional[str] = None,
    ) -> List[CaseResponse]:
        """
        List cases with optional filtering.

        Args:
            offset: Pagination offset
            limit: Maximum results
            problem_type: Filter by problem type
            status: Filter by status

        Returns:
            List of matching cases
        """
        results = list(_CASES.values())

        if problem_type:
            results = [c for c in results if c.problem_type == problem_type]
        if status:
            results = [c for c in results if c.status == status]

        # Sort by creation date (newest first)
        results.sort(key=lambda c: c.created_at, reverse=True)

        return results[offset:offset + limit]

    def update_case(
        self,
        case_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[CaseResponse]:
        """
        Update an existing case.

        Args:
            case_id: Case identifier
            name: New name (optional)
            description: New description (optional)
            status: New status (optional)
            metadata: New metadata (optional)

        Returns:
            Updated case response or None if not found
        """
        case = _CASES.get(case_id)
        if not case:
            return None

        if name is not None:
            case.name = name
        if description is not None:
            case.description = description
        if status is not None:
            case.status = status
        if metadata is not None:
            case.metadata.update(metadata)

        case.updated_at = datetime.utcnow()
        _CASES[case_id] = case
        self._save_cases()

        logger.info(f"Updated case: {case_id}")
        return case

    def delete_case(self, case_id: str) -> bool:
        """
        Delete a case.

        Args:
            case_id: Case identifier

        Returns:
            True if deleted, False if not found
        """
        if case_id in _CASES:
            del _CASES[case_id]
            self._save_cases()
            logger.info(f"Deleted case: {case_id}")
            return True
        return False

    def get_total_count(self) -> int:
        """Get total number of cases."""
        return len(_CASES)
