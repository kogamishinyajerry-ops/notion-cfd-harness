"""
GoldStandardRegistry — Thread-safe singleton registry for all GoldStandard cases.

GS-01: Provides auto-discovery of all GoldStandard modules and thread-safe access
to spec factories, validators, reference data, mesh info, and solver configs.

Thread-safety: PipelineExecutor uses threading.Thread; concurrent access to the
registry must be safe via threading.Lock.

Circular import avoidance: _register_all_cases() uses lazy imports to avoid
import cycles between knowledge_compiler and api_server.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional


class GoldStandardRegistry:
    """
    Thread-safe registry mapping case_id -> (spec_factory, validator_class,
    reference_fn, mesh_info_fn, solver_config_fn).

    Auto-discovers all gold_standard modules via lazy import at first access.
    """

    _instance: Optional["GoldStandardRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._spec_factories: Dict[str, Callable] = {}
        self._validator_classes: Dict[str, type] = {}
        self._reference_fns: Dict[str, Optional[Callable]] = {}
        self._mesh_info_fns: Dict[str, Optional[Callable]] = {}
        self._solver_config_fns: Dict[str, Optional[Callable]] = {}
        # Maps whitelist_id (e.g., "OF-01") -> module case_id (e.g., "lid_driven_cavity")
        self._whitelist_id_map: Dict[str, str] = {}
        self._whitelist = None
        self._initialized = True

    def register(
        self,
        case_id: str,
        whitelist_id: Optional[str] = None,
        spec_factory: Optional[Callable] = None,
        validator_class: Optional[type] = None,
        reference_fn: Optional[Callable] = None,
        mesh_info_fn: Optional[Callable] = None,
        solver_config_fn: Optional[Callable] = None,
    ) -> None:
        """Register a GoldStandard case. Thread-safe."""
        with self._lock:
            self._spec_factories[case_id] = spec_factory
            self._validator_classes[case_id] = validator_class
            self._reference_fns[case_id] = reference_fn
            self._mesh_info_fns[case_id] = mesh_info_fn
            self._solver_config_fns[case_id] = solver_config_fn
            if whitelist_id:
                self._whitelist_id_map[whitelist_id] = case_id

    def is_case_registered(self, whitelist_id: str) -> bool:
        """Check if a whitelist case ID has a GoldStandard module registered."""
        module_id = self._whitelist_id_map.get(whitelist_id)
        if not module_id:
            return False
        return module_id in self._spec_factories

    def get_module_case_id(self, whitelist_id: str) -> Optional[str]:
        """Get the module-level case_id for a whitelist ID, or None."""
        return self._whitelist_id_map.get(whitelist_id)

    def get_case_ids(self) -> List[str]:
        """Return all registered case IDs (from whitelist + local registry)."""
        whitelist_ids = [c.id for c in self._get_whitelist().cases]
        registered_ids = list(self._spec_factories.keys())
        return sorted(set(whitelist_ids))

    def get_whitelist_case(self, case_id: str):
        """Get ColdStartCase metadata from whitelist YAML."""
        return self._get_whitelist().get_by_id(case_id)

    def get_spec(self, case_id: str, **kwargs) -> "ReportSpec":
        """Create ReportSpec for case_id. Raises KeyError if not registered."""
        factory = self._spec_factories.get(case_id)
        if not factory:
            # Try whitelist ID lookup
            module_id = self._whitelist_id_map.get(case_id)
            if module_id:
                factory = self._spec_factories.get(module_id)
        if not factory:
            raise KeyError(
                f"No GoldStandard spec factory for {case_id}. "
                f"Available: {list(self._spec_factories.keys())}"
            )
        return factory(**kwargs)

    def get_validator(self, case_id: str):
        """Instantiate and return validator for case_id. Returns None if not registered."""
        cls = self._validator_classes.get(case_id)
        if not cls:
            # Try whitelist ID lookup
            module_id = self._whitelist_id_map.get(case_id)
            if module_id:
                cls = self._validator_classes.get(module_id)
        if not cls:
            return None
        return cls()

    def get_reference_data(self, case_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Get literature reference data. Returns None if not registered."""
        fn = self._reference_fns.get(case_id)
        if not fn:
            # Try whitelist ID lookup
            module_id = self._whitelist_id_map.get(case_id)
            if module_id:
                fn = self._reference_fns.get(module_id)
        if not fn:
            return None
        return fn(**kwargs)

    def get_mesh_info(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get mesh metadata (strategy, file path, hash). Returns None if not registered."""
        fn = self._mesh_info_fns.get(case_id)
        if not fn:
            # Try whitelist ID lookup
            module_id = self._whitelist_id_map.get(case_id)
            if module_id:
                fn = self._mesh_info_fns.get(module_id)
        if not fn:
            return None
        return fn()

    def get_solver_config(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get solver config (solver name, turbulence model, discretization). Returns None if not registered."""
        fn = self._solver_config_fns.get(case_id)
        if not fn:
            # Try whitelist ID lookup
            module_id = self._whitelist_id_map.get(case_id)
            if module_id:
                fn = self._solver_config_fns.get(module_id)
        if not fn:
            return None
        return fn()

    def _get_whitelist(self):
        if self._whitelist is None:
            from knowledge_compiler.phase1.gold_standards.cold_start import load_cold_start_whitelist
            self._whitelist = load_cold_start_whitelist()
        return self._whitelist


# Module-level singleton accessor
_registry: Optional[GoldStandardRegistry] = None
_registry_lock = threading.Lock()


def get_gold_standard_registry() -> GoldStandardRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = GoldStandardRegistry()
                _register_all_cases(_registry)
    return _registry


def _register_all_cases(registry: GoldStandardRegistry):
    """
    Import all existing GoldStandard modules to trigger auto-registration.
    Uses lazy import to avoid circular import (GS-2.1 pitfall).
    """
    # Lazy import — avoid circular import between knowledge_compiler sub-packages
    from knowledge_compiler.phase1.gold_standards import (
        lid_driven_cavity,
        backward_facing_step,
        inviscid_bump,
        inviscid_wedge,
        laminar_flat_plate,
        supersonic_wedge,
        cylinder_compressible,
        turbulent_flat_plate,
        von_karman_vortex,
        onera_m6,
        dam_break_vof,
    )
    # Each module exposes a register(registry) function
    if hasattr(lid_driven_cavity, "register"):
        lid_driven_cavity.register(registry)
    if hasattr(backward_facing_step, "register"):
        backward_facing_step.register(registry)
    if hasattr(inviscid_bump, "register"):
        inviscid_bump.register(registry)
    if hasattr(inviscid_wedge, "register"):
        inviscid_wedge.register(registry)
    if hasattr(laminar_flat_plate, "register"):
        laminar_flat_plate.register(registry)
    if hasattr(supersonic_wedge, "register"):
        supersonic_wedge.register(registry)
    if hasattr(cylinder_compressible, "register"):
        cylinder_compressible.register(registry)
    if hasattr(turbulent_flat_plate, "register"):
        turbulent_flat_plate.register(registry)
    if hasattr(von_karman_vortex, "register"):
        von_karman_vortex.register(registry)
    if hasattr(onera_m6, "register"):
        onera_m6.register(registry)
    if hasattr(dam_break_vof, "register"):
        dam_break_vof.register(registry)
