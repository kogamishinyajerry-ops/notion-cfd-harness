"""
GoldStandardService — Bridge between GoldStandardRegistry and FastAPI.

GS-02: Exposes GoldStandardRegistry via REST API.
Follows the bridge pattern: domain dataclasses in knowledge_compiler ->
Pydantic DTO at API boundary. Prevents GS-2.1 (circular import) by using
lazy import in _get_registry().
"""

import threading
from typing import Any, Dict, List, Optional

from api_server.models import (
    GoldStandardCaseDetail,
    GoldStandardCaseSummary,
    GoldStandardListResponse,
    GoldStandardMeshInfo,
    GoldStandardSolverConfig,
    ValidationResultDetail,
    ValidationResultResponse,
)


class GoldStandardService:
    """
    API-facing service wrapping GoldStandardRegistry.

    All methods are thread-safe (registry uses threading.Lock).
    Returns Pydantic DTOs, never raw knowledge_compiler domain classes.
    """

    def __init__(self):
        self._registry = _get_registry()

    def list_cases(
        self,
        platform: Optional[str] = None,
        tier: Optional[str] = None,
        difficulty: Optional[str] = None,
        has_gold_standard: Optional[bool] = None,
    ) -> GoldStandardListResponse:
        """
        List all GoldStandard case summaries, optionally filtered.

        Args:
            platform: Filter by platform (OpenFOAM or SU2)
            tier: Filter by tier (core_seed, bridge, breadth)
            difficulty: Filter by difficulty (basic, intermediate, advanced)
            has_gold_standard: Filter by whether GoldStandard module is registered

        Returns:
            GoldStandardListResponse with list of case summaries
        """
        whitelist = self._registry._get_whitelist()
        cases = whitelist.cases

        if platform:
            cases = [c for c in cases if c.platform.lower() == platform.lower()]
        if tier:
            cases = [c for c in cases if c.tier == tier]
        if difficulty:
            cases = [c for c in cases if c.difficulty == difficulty]

        summaries = []
        for c in cases:
            # Map whitelist ID (OF-01) to module case_id (lid_driven_cavity) for registry lookups
            module_case_id = self._registry.get_module_case_id(c.id)
            has_gs = module_case_id is not None and module_case_id in self._registry._spec_factories
            has_ref = (
                module_case_id is not None
                and module_case_id in self._registry._reference_fns
                and self._registry._reference_fns[module_case_id] is not None
            )
            has_mesh = (
                module_case_id is not None
                and module_case_id in self._registry._mesh_info_fns
                and self._registry._mesh_info_fns[module_case_id] is not None
            )
            has_solver = (
                module_case_id is not None
                and module_case_id in self._registry._solver_config_fns
                and self._registry._solver_config_fns[module_case_id] is not None
            )

            if has_gold_standard is not None and has_gs != has_gold_standard:
                continue

            summaries.append(GoldStandardCaseSummary(
                id=c.id,
                case_name=c.case_name,
                platform=c.platform,
                tier=c.tier,
                dimension=c.dimension,
                difficulty=c.difficulty,
                mesh_strategy=c.mesh_strategy,
                solver_command=c.solver_command,
                has_gold_standard=has_gs,
                has_reference_data=has_ref,
                has_mesh_info=has_mesh,
                has_solver_config=has_solver,
            ))

        return GoldStandardListResponse(
            cases=summaries,
            total=len(summaries),
            platform_filter=platform,
        )

    def get_case_detail(self, case_id: str) -> Optional[GoldStandardCaseDetail]:
        """
        Get detailed GoldStandard case including ReportSpec and metadata.

        Args:
            case_id: Case ID (e.g., 'OF-01', 'SU2-02')

        Returns:
            GoldStandardCaseDetail or None if case not found in whitelist
        """
        whitelist_case = self._registry.get_whitelist_case(case_id)
        if not whitelist_case:
            return None

        # Map whitelist ID to module case_id for registry lookups
        module_case_id = self._registry.get_module_case_id(case_id)

        mesh_info = self._registry.get_mesh_info(module_case_id) if module_case_id else None
        solver_config = self._registry.get_solver_config(module_case_id) if module_case_id else None

        report_spec_dict = None
        problem_type = None
        if module_case_id:
            try:
                spec = self._registry.get_spec(module_case_id)
                report_spec_dict = spec.to_dict()
                problem_type = spec.problem_type.value
            except KeyError:
                pass

        return GoldStandardCaseDetail(
            id=whitelist_case.id,
            case_name=whitelist_case.case_name,
            platform=whitelist_case.platform,
            tier=whitelist_case.tier,
            dimension=whitelist_case.dimension,
            difficulty=whitelist_case.difficulty,
            mesh_strategy=whitelist_case.mesh_strategy,
            has_ready_mesh=whitelist_case.has_ready_mesh,
            solver_command=whitelist_case.solver_command,
            success_criteria=whitelist_case.success_criteria,
            source_provenance=whitelist_case.source_provenance,
            mesh_info=GoldStandardMeshInfo(**mesh_info) if mesh_info else None,
            solver_config=GoldStandardSolverConfig(**solver_config) if solver_config else None,
            report_spec=report_spec_dict,
            problem_type=problem_type,
        )

    def get_reference_data(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Get literature reference data for a case.

        Args:
            case_id: Case ID (whitelist ID, e.g., 'OF-01')

        Returns:
            Reference data dict or None if not available
        """
        module_case_id = self._registry.get_module_case_id(case_id)
        return self._registry.get_reference_data(module_case_id) if module_case_id else None

    def validate_result(self, case_id: str, result_spec: Dict[str, Any]) -> ValidationResultResponse:
        """
        Validate a ReportSpec against the GoldStandard for a case.

        Args:
            case_id: Case ID
            result_spec: ReportSpec dict to validate

        Returns:
            ValidationResultResponse with per-metric results
        """
        from knowledge_compiler.phase1.schema import ReportSpec

        module_case_id = self._registry.get_module_case_id(case_id)
        if not module_case_id:
            return ValidationResultResponse(
                case_id=case_id,
                passed=False,
                errors=[f"No GoldStandard module registered for {case_id}"],
            )

        validator = self._registry.get_validator(module_case_id)
        if not validator:
            return ValidationResultResponse(
                case_id=case_id,
                passed=False,
                errors=[f"No validator registered for {case_id}"],
            )

        try:
            spec = ReportSpec.from_dict(result_spec)
        except Exception as e:
            return ValidationResultResponse(
                case_id=case_id,
                passed=False,
                errors=[f"Failed to parse ReportSpec: {str(e)}"],
            )

        validation_result = validator.validate_report_spec(spec)

        details = []
        for detail_key, detail_val in validation_result.get("details", {}).items():
            if isinstance(detail_val, dict):
                details.append(ValidationResultDetail(
                    metric=detail_key,
                    status="PASS" if detail_val.get("passed", False) else "FAIL",
                    message=detail_val.get("message"),
                ))

        return ValidationResultResponse(
            case_id=case_id,
            passed=validation_result.get("passed", False),
            errors=validation_result.get("errors", []),
            warnings=validation_result.get("warnings", []),
            details=details,
            plot_coverage=validation_result.get("details", {}).get("plot_coverage"),
            metric_coverage=validation_result.get("details", {}).get("metric_coverage"),
        )


# Lazy singleton accessor — avoids circular import (GS-2.1 pitfall)
_service: Optional[GoldStandardService] = None
_service_lock = threading.Lock()


def _get_registry():
    """Lazy import to avoid circular import between knowledge_compiler and api_server."""
    from knowledge_compiler.phase1.gold_standards.registry import get_gold_standard_registry
    return get_gold_standard_registry()


def get_gold_standard_service() -> GoldStandardService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = GoldStandardService()
    return _service
