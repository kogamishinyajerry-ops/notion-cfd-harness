"""
GoldStandardLoader - Literature comparison via Gold Standards

D-03/D-04: Case vs Literature comparison using Gold Standards get_expected_* functions.
Loads reference data from Phase 1 gold_standards library and compares
against simulated values to produce LiteratureComparison results.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class LiteratureComparison:
    """Result of comparing simulated values against literature reference."""
    metric_name: str
    simulated_value: float
    reference_value: float
    error_pct: float
    unit: str
    reference_source: str
    reynolds_number: float
    status: str  # "PASS", "WARN", "FAIL"


class GoldStandardLoader:
    """
    Loads Gold Standards reference data and performs literature comparison.

    Maps case_type strings to gold_standards get_expected_* functions:
    - "lid_driven_cavity" -> get_expected_ghia_data()
    - "backward_facing_step" -> get_expected_reattachment_length()
    - "laminar_flat_plate" -> get_expected_blasius_cf()

    D-02: Returns empty dict for unknown case types (not an error).
    """

    def __init__(self) -> None:
        self._case_type_loaders: Dict[str, Callable[..., Optional[Dict[str, Any]]]] = {
            "lid_driven_cavity": self._load_lid_cavity,
            "backward_facing_step": self._load_backward_step,
            "laminar_flat_plate": self._load_flat_plate,
        }

    def get_reference_data(
        self,
        case_type: str,
        reynolds_number: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Query Gold Standards for reference data by case type and Re.

        Args:
            case_type: Case type string (e.g., "lid_driven_cavity")
            reynolds_number: Reynolds number for reference lookup

        Returns:
            Reference data dict for known case types, None for unknown types.
        """
        loader = self._case_type_loaders.get(case_type.lower())
        if loader:
            return loader(reynolds_number)
        return None

    def _load_lid_cavity(self, re: float) -> Dict[str, Any]:
        """Load lid-driven cavity reference data from Ghia 1982."""
        try:
            from knowledge_compiler.phase1.gold_standards.lid_driven_cavity import (
                get_expected_ghia_data,
            )
            return get_expected_ghia_data(re)
        except ValueError:
            # Re not in tabulated data
            return {}

    def _load_backward_step(self, re: float) -> Dict[str, Any]:
        """Load backward-facing step reference data from Armaly 1983."""
        try:
            from knowledge_compiler.phase1.gold_standards.backward_facing_step import (
                get_expected_reattachment_length,
            )
            xr_h = get_expected_reattachment_length(re)
            return {
                "reynolds_number": re,
                "reattachment_length_xr_h": xr_h,
                "source": "Armaly 1983",
            }
        except Exception:
            return {}

    def _load_flat_plate(self, re: float) -> Dict[str, Any]:
        """Load laminar flat plate reference data (placeholder)."""
        # Could be extended with get_expected_blasius_cf when needed
        return {}

    def compare_with_reference(
        self,
        simulated_value: float,
        reference_value: float,
        metric_name: str,
        unit: str,
        reference_source: str,
        reynolds_number: float,
        threshold_pct: float = 5.0,
    ) -> LiteratureComparison:
        """
        Compare simulated value against literature reference.

        Args:
            simulated_value: Value from simulation
            reference_value: Literature reference value
            metric_name: Name of the metric being compared
            unit: Unit of measurement
            reference_source: Citation for reference data
            reynolds_number: Reynolds number of the comparison
            threshold_pct: % error threshold for PASS/WARN/FAIL

        Returns:
            LiteratureComparison with PASS/WARN/FAIL status computed
            against threshold_pct:
            - error_pct <= threshold_pct -> PASS
            - error_pct <= threshold_pct * 2 -> WARN
            - error_pct > threshold_pct * 2 -> FAIL
        """
        if reference_value == 0:
            error_pct = 0.0 if simulated_value == 0 else 100.0
        else:
            error_pct = abs(simulated_value - reference_value) / abs(reference_value) * 100

        if error_pct <= threshold_pct:
            status = "PASS"
        elif error_pct <= threshold_pct * 2:
            status = "WARN"
        else:
            status = "FAIL"

        return LiteratureComparison(
            metric_name=metric_name,
            simulated_value=simulated_value,
            reference_value=reference_value,
            error_pct=error_pct,
            unit=unit,
            reference_source=reference_source,
            reynolds_number=reynolds_number,
            status=status,
        )
