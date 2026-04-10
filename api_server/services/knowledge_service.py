"""
Knowledge Service

Business logic for knowledge registry queries.
"""

import logging
from typing import Any, Dict, List, Optional

from api_server.models import KnowledgeUnit

logger = logging.getLogger(__name__)


class KnowledgeService:
    """
    Service for querying the knowledge registry.

    Provides read-only access to the knowledge units stored in the system.
    """

    def __init__(self):
        """Initialize the knowledge service."""
        self._registry = None

    def _get_registry(self):
        """Lazy-load the knowledge registry."""
        if self._registry is None:
            try:
                from knowledge_compiler.runtime import KnowledgeRegistry
                self._registry = KnowledgeRegistry()
            except ImportError as e:
                logger.warning(f"Failed to import KnowledgeRegistry: {e}")
                self._registry = None
        return self._registry

    def search(
        self,
        query: str,
        unit_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[KnowledgeUnit]:
        """
        Search knowledge units by query string.

        Args:
            query: Search query
            unit_type: Optional filter by unit type
            limit: Maximum results

        Returns:
            List of matching knowledge units
        """
        registry = self._get_registry()
        if not registry:
            return []

        try:
            results = registry.search(query)

            if unit_type:
                results = [r for r in results if r.unit_type == unit_type]

            return [
                KnowledgeUnit(
                    unit_id=r.unit_id,
                    unit_type=r.unit_type,
                    source_file=r.source_file,
                    version=r.version,
                )
                for r in results[:limit]
            ]
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return []

    def get_unit(self, unit_id: str) -> Optional[KnowledgeUnit]:
        """
        Get a specific knowledge unit by ID.

        Args:
            unit_id: Unit identifier

        Returns:
            Knowledge unit or None if not found
        """
        registry = self._get_registry()
        if not registry:
            return None

        try:
            unit_ref = registry.get(unit_id)
            if not unit_ref:
                return None

            return KnowledgeUnit(
                unit_id=unit_ref.unit_id,
                unit_type=unit_ref.unit_type,
                source_file=unit_ref.source_file,
                version=unit_ref.version,
            )
        except Exception as e:
            logger.error(f"Failed to get unit {unit_id}: {e}")
            return None

    def query_by_type(self, unit_type: str, limit: int = 50) -> List[KnowledgeUnit]:
        """
        Query all units of a specific type.

        Args:
            unit_type: Unit type (chapter/formula/data_point/chart_rule/evidence)
            limit: Maximum results

        Returns:
            List of knowledge units
        """
        registry = self._get_registry()
        if not registry:
            return []

        try:
            results = registry.query_by_type(unit_type)
            return [
                KnowledgeUnit(
                    unit_id=r.unit_id,
                    unit_type=r.unit_type,
                    source_file=r.source_file,
                    version=r.version,
                )
                for r in results[:limit]
            ]
        except Exception as e:
            logger.error(f"Failed to query by type {unit_type}: {e}")
            return []

    def get_trace(self, unit_id: str) -> List[str]:
        """
        Get trace chain for a knowledge unit.

        Args:
            unit_id: Unit identifier

        Returns:
            List of trace information [unit_id, source_file, line_range]
        """
        registry = self._get_registry()
        if not registry:
            return []

        try:
            return registry.get_trace(unit_id)
        except Exception as e:
            logger.error(f"Failed to get trace for {unit_id}: {e}")
            return []

    def get_dependencies(self, unit_id: str) -> List[str]:
        """
        Get dependencies for a knowledge unit.

        Args:
            unit_id: Unit identifier

        Returns:
            List of dependent unit IDs
        """
        registry = self._get_registry()
        if not registry:
            return []

        try:
            deps = registry.get_dependencies(unit_id)
            return list(deps) if deps else []
        except Exception as e:
            logger.error(f"Failed to get dependencies for {unit_id}: {e}")
            return []

    def get_unit_count(self) -> int:
        """
        Get total count of registered knowledge units.

        Returns:
            Total number of units
        """
        registry = self._get_registry()
        if not registry:
            return 0

        try:
            return len(registry.units)
        except Exception as e:
            logger.error(f"Failed to get unit count: {e}")
            return 0
