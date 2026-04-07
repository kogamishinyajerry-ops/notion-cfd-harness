#!/usr/bin/env python3
"""
Knowledge Runtime Adapter
Phase 3: Knowledge-Driven Orchestrator

Provides unified query and traceability API across all four knowledge layers.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from knowledge_compiler.units import chapters, formulas, data_points, chart_rules, evidence
from knowledge_compiler.schema import raw_schema, parsed_schema, canonical_schema, executable_schema


# =============================================================================
# Knowledge Unit References
# =============================================================================

@dataclass
class KnowledgeUnitRef:
    """Reference to a knowledge unit."""
    unit_id: str
    unit_type: str  # chapter/formula/data_point/chart_rule/evidence
    source_file: str
    version: str
    canonical_id: Optional[str] = None  # For Canonical/Executable layers


# =============================================================================
# Runtime Registry
# =============================================================================

class KnowledgeRegistry:
    """
    Unified registry for all four knowledge layers.

    Provides:
    - Query by unit_id, unit_type, source_file
    - Traceability: raw → parsed → canonical → executable
    - Version management
    - Integrity verification
    """

    def __init__(self, base_path: Path = None):
        self.base_path = base_path or Path(__file__).parent.parent
        self.units: Dict[str, KnowledgeUnitRef] = {}
        self._load_all_units()

    def _load_all_units(self):
        """Load all knowledge units from YAML files."""
        # Chapters
        for i, ch in enumerate(chapters.CHAPTERS):
            self.units[f"CH-{i+1:03d}"] = KnowledgeUnitRef(
                unit_id=f"CH-{i+1:03d}",
                unit_type="chapter",
                source_file="units/chapters.yaml",
                version="v1.1"
            )

        # Formulas
        for key in formulas.FORMULAS:
            self.units[f"FORM-{key}"] = KnowledgeUnitRef(
                unit_id=f"FORM-{key}",
                unit_type="formula",
                source_file="units/formulas.yaml",
                version="v1.1"
            )

        # Data points
        for case_id in data_points.CASES:
            self.units[f"CASE-{case_id}"] = KnowledgeUnitRef(
                unit_id=f"CASE-{case_id}",
                unit_type="data_point",
                source_file="units/data_points.yaml",
                version="v1.1"
            )

        # Chart rules
        self.units["CHART-001"] = KnowledgeUnitRef(
            unit_id="CHART-001",
            unit_type="chart_rule",
            source_file="units/chart_rules.yaml",
            version="v1.0"
        )

        # Evidence chains
        for i, chain in enumerate(evidence.EVIDENCE_CHAINS):
            self.units[f"EVID-CHAIN-{i+1:03d}"] = KnowledgeUnitRef(
                unit_id=f"EVID-CHAIN-{i+1:03d}",
                unit_type="evidence",
                source_file="units/evidence.yaml",
                version="v1.0"
            )

    # -------------------------------------------------------------------------
    # Query APIs
    # -------------------------------------------------------------------------

    def get(self, unit_id: str) -> Optional[KnowledgeUnitRef]:
        """Get unit reference by ID."""
        return self.units.get(unit_id)

    def query_by_type(self, unit_type: str) -> List[KnowledgeUnitRef]:
        """Query all units of a given type."""
        return [u for u in self.units.values() if u.unit_type == unit_type]

    def query_by_source(self, source_file: str) -> List[KnowledgeUnitRef]:
        """Query all units from a source file."""
        return [u for u in self.units.values() if u.source_file == source_file]

    def search(self, query: str) -> List[KnowledgeUnitRef]:
        """Free-text search across unit IDs."""
        query_lower = query.lower()
        return [u for u in self.units.values() if query_lower in u.unit_id.lower()]

    # -------------------------------------------------------------------------
    # Traceability APIs
    # -------------------------------------------------------------------------

    def get_trace(self, unit_id: str) -> List[str]:
        """
        Get trace chain for a unit.

        Returns: [unit_id, source_file, source_line_range]
        """
        unit = self.get(unit_id)
        if not unit:
            return []

        # Load source_mapping.json
        mapping_path = self.base_path / "source_mapping.json"
        if not mapping_path.exists():
            return [unit_id, unit.source_file]

        with open(mapping_path) as f:
            mapping = json.load(f)

        for entry in mapping.get("unit_to_source", []):
            if entry["unit_id"] == unit_id:
                return [
                    unit_id,
                    entry["source_file"],
                    f\"lines {entry['source_line_range'][0]}-{entry['source_line_range'][1]}\"
                ]

        return [unit_id, unit.source_file]

    def get_dependencies(self, unit_id: str) -> Set[str]:
        """
        Get dependent units for a given unit.

        Example: CASE-001 depends on FORM-006, FORM-007, CHART-001
        """
        deps = set()
        unit = self.get(unit_id)

        if unit.unit_type == "data_point":
            deps.update(["FORM-006", "FORM-007", "FORM-008", "CHART-001"])
        elif unit.unit_type == "formula":
            deps.add("CH-001")  # Formulas defined in Geometry chapter

        return deps

    # -------------------------------------------------------------------------
    # Integrity Verification
    # -------------------------------------------------------------------------

    def verify_baseline_integrity(self, baseline_manifest: Dict) -> Dict[str, Any]:
        """
        Verify current state against baseline manifest.

        Returns: {"valid": bool, "missing": [], "extra": [], "mismatched": []}
        """
        baseline_files = baseline_manifest.get("baseline_files", {})
        expected_count = baseline_files.get("total", 0)

        # Count current files by type
        current_files = {
            "root": [],
            "units": [],
            "schema": [],
            "executables": []
        }

        for path in self.base_path.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(self.base_path)
                path_str = str(rel_path)

                if "orchestrator" in path_str:
                    continue  # Phase3 files not in baseline

                if "units/" in path_str:
                    current_files["units"].append(path_str)
                elif "schema/" in path_str:
                    current_files["schema"].append(path_str)
                elif "executables/" in path_str:
                    current_files["executables"].append(path_str)
                else:
                    current_files["root"].append(path_str)

        result = {
            "valid": True,
            "missing": [],
            "extra": [],
            "mismatched": []
        }

        for category, expected_list in baseline_files.items():
            if category == "total":
                continue
            current_set = set(current_files.get(category, []))
            expected_set = set(expected_list)

            missing = expected_set - current_set
            extra = current_set - expected_set

            if missing:
                result["missing"].extend(list(missing))
                result["valid"] = False
            if extra:
                result["extra"].extend(list(extra))
                # Extra files are OK if they're additions

        return result


# =============================================================================
# Singleton Instance
# =============================================================================

_registry: Optional[KnowledgeRegistry] = None


def get_registry() -> KnowledgeRegistry:
    """Get the global knowledge registry instance."""
    global _registry
    if _registry is None:
        _registry = KnowledgeRegistry()
    return _registry


# =============================================================================
# Utility Functions
# =============================================================================

def resolve_formula(formula_id: str) -> Dict[str, Any]:
    """
    Resolve formula definition from formulas.yaml.

    Returns: {"name", "symbol", "definition", "variables", "error_type"}
    """
    registry = get_registry()
    unit = registry.get(formula_id)

    # This would load from the actual YAML
    # For now, return placeholder
    return {
        "unit_id": formula_id,
        "name": "Formula from formulas.yaml",
        "definition": "See formulas.yaml"
    }


def resolve_case_data(case_id: str) -> Dict[str, Any]:
    """
    Resolve benchmark case data from data_points.yaml.

    Returns: {"benchmark", "data_points", "validation_refs"}
    """
    registry = get_registry()
    unit = registry.get(case_id)

    return {
        "unit_id": case_id,
        "data_points": "See data_points.yaml"
    }


def get_executable_path(executable_name: str) -> Optional[Path]:
    """
    Get path to Phase2 executable.
    """
    base_path = Path(__file__).parent.parent
    exe_path = base_path / "executables" / executable_name
    return exe_path if exe_path.exists() else None
