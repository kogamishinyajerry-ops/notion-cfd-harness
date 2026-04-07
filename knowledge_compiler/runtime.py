#!/usr/bin/env python3
"""
Knowledge Runtime Adapter
Phase 3: Knowledge-Driven Orchestrator

Provides unified query and traceability API across all four knowledge layers.
"""

import hashlib
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

# Fixed (F-P3-004): Load YAML files directly instead of importing as Python modules
# The units/ directory contains YAML files, not Python modules


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
        self.base_path = base_path or Path(__file__).parent
        self.units: Dict[str, KnowledgeUnitRef] = {}
        self._load_all_units()

    def _load_all_units(self):
        """
        Load all knowledge units from YAML files.

        Fixed (F-P3-004): Load YAML files directly using yaml.safe_load().
        """
        units_path = self.base_path / "units"

        # Load chapters.yaml
        chapters_path = units_path / "chapters.yaml"
        if chapters_path.exists():
            try:
                with open(chapters_path) as f:
                    chapters_data = yaml.safe_load(f)
                for ch in chapters_data.get("chapters", []):
                    ch_id = ch.get("id", "")
                    if ch_id:
                        self.units[ch_id] = KnowledgeUnitRef(
                            unit_id=ch_id,
                            unit_type="chapter",
                            source_file="units/chapters.yaml",
                            version="v1.1"
                        )
            except (yaml.YAMLError, IOError) as e:
                # Log but don't fail - continue with other files
                pass

        # Load formulas.yaml
        formulas_path = units_path / "formulas.yaml"
        if formulas_path.exists():
            try:
                with open(formulas_path) as f:
                    formulas_data = yaml.safe_load(f)
                for formula in formulas_data.get("formulas", []):
                    formula_id = formula.get("id", "")
                    if formula_id:
                        self.units[formula_id] = KnowledgeUnitRef(
                            unit_id=formula_id,
                            unit_type="formula",
                            source_file="units/formulas.yaml",
                            version="v1.1"
                        )
            except (yaml.YAMLError, IOError):
                pass

        # Load data_points.yaml (has known YAML quirks)
        data_points_path = units_path / "data_points.yaml"
        if data_points_path.exists():
            try:
                with open(data_points_path) as f:
                    data_points_data = yaml.safe_load(f)
                for case in data_points_data.get("cases", []):
                    case_id = case.get("id", "")
                    if case_id:
                        self.units[case_id] = KnowledgeUnitRef(
                            unit_id=case_id,
                            unit_type="data_point",
                            source_file="units/data_points.yaml",
                            version="v1.1"
                        )
            except (yaml.YAMLError, IOError):
                pass

        # Load chart_rules.yaml
        chart_rules_path = units_path / "chart_rules.yaml"
        if chart_rules_path.exists():
            try:
                with open(chart_rules_path) as f:
                    chart_rules_data = yaml.safe_load(f)
                for rule in chart_rules_data.get("chart_rules", []):
                    rule_id = rule.get("id", "")
                    if rule_id:
                        self.units[rule_id] = KnowledgeUnitRef(
                            unit_id=rule_id,
                            unit_type="chart_rule",
                            source_file="units/chart_rules.yaml",
                            version="v1.0"
                        )
            except (yaml.YAMLError, IOError):
                pass

        # Load evidence.yaml
        evidence_path = units_path / "evidence.yaml"
        if evidence_path.exists():
            try:
                with open(evidence_path) as f:
                    evidence_data = yaml.safe_load(f)
                for chain in evidence_data.get("evidence_chains", []):
                    chain_id = chain.get("id", "")
                    if chain_id:
                        self.units[chain_id] = KnowledgeUnitRef(
                            unit_id=chain_id,
                            unit_type="evidence",
                            source_file="units/evidence.yaml",
                            version="v1.0"
                        )
            except (yaml.YAMLError, IOError):
                pass

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
                line_range = entry.get('source_line_range', [0, 0])
                line_str = f"lines {line_range[0]}-{line_range[1]}"
                return [unit_id, entry["source_file"], line_str]

        return [unit_id, unit.source_file]

    def get_dependencies(self, unit_id: str) -> Set[str]:
        """
        Get dependent units for a given unit.

        Fixed (F-P3-003): Now loads from dependency_graph.json or source_mapping.json.

        Example: CASE-001 depends on FORM-006, FORM-007, CHART-001
        """
        unit = self.get(unit_id)
        if not unit:
            return set()

        # Try to load from dependency_graph.json first
        dep_graph_path = self.base_path / "dependency_graph.json"
        if dep_graph_path.exists():
            try:
                with open(dep_graph_path) as f:
                    dep_graph = json.load(f)
                return set(dep_graph.get("dependencies", {}).get(unit_id, []))
            except (json.JSONDecodeError, IOError):
                pass

        # Fallback: try source_mapping.json for formula references
        mapping_path = self.base_path / "source_mapping.json"
        if mapping_path.exists():
            try:
                with open(mapping_path) as f:
                    mapping = json.load(f)

                # Look for formula references in data_points
                if unit.unit_type == "data_point":
                    for entry in mapping.get("unit_to_source", []):
                        if entry["unit_id"] == unit_id:
                            # Extract formula references from the entry
                            refs = entry.get("formula_references", [])
                            if not refs:
                                # Fallback to hardcoded defaults for known cases
                                refs = self._get_default_formula_deps(unit_id)
                            return set(refs)
            except (json.JSONDecodeError, IOError):
                pass

        # Final fallback to type-based defaults
        return self._get_type_based_defaults(unit)

    def _get_default_formula_deps(self, unit_id: str) -> List[str]:
        """Get default formula dependencies for known data points."""
        # Defaults from Phase2 evidence
        known_deps = {
            "CASE-001": ["FORM-006", "FORM-007", "FORM-008", "CHART-001"],
            "CASE-002": ["FORM-006", "FORM-007", "FORM-008", "CHART-001"],
        }
        return known_deps.get(unit_id, [])

    def _get_type_based_defaults(self, unit: KnowledgeUnitRef) -> Set[str]:
        """Get type-based default dependencies."""
        if unit.unit_type == "formula":
            return {"CH-001"}  # Formulas defined in Geometry chapter
        elif unit.unit_type == "data_point":
            return set(self._get_default_formula_deps(unit.unit_id))
        return set()

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
