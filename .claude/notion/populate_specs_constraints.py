#!/usr/bin/env python3
"""
Populate Specs and Constraints tables in Notion (Phase 2c T0)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path('.claude/notion')))
from api import NotionAPI, NotionConfig


def populate_specs(api: NotionAPI, specs_db_id: str, project_id: str):
    """Populate Specs database"""

    specs = [
        {
            "title": "AI-CFD-001: Core Architecture",
            "spec_id": "AI-CFD-001",
            "version": "v1.0",
            "scope_type": "Architecture",
            "status": "Approved",
            "change_summary": "Initial architecture definition - 5-phase structure with Phase 1 complete",
            "effective_date": "2026-03-01",
        },
        {
            "title": "MODEL-ROUTING-001: Model Assignment Rules",
            "spec_id": "MODEL-ROUTING-001",
            "version": "v1.0",
            "scope_type": "Requirements",
            "status": "Approved",
            "change_summary": "GLM-5.1 for coordination/testing, Codex for core logic, Opus 4.6 for reviews",
            "effective_date": "2026-03-29",
        },
        {
            "title": "GSD-001: Notion-Controlled Workflow",
            "spec_id": "GSD-001",
            "version": "v2.1",
            "scope_type": "Business Rules",
            "status": "Approved",
            "change_summary": "Single Source of Truth: Notion controls all task states and project decisions",
            "effective_date": "2026-04-08",
        },
        {
            "title": "PHASE2-SCHEMA-001: Execution Layer Data Contracts",
            "spec_id": "PHASE2-SCHEMA-001",
            "version": "v1.0",
            "scope_type": "API Contract",
            "status": "Approved",
            "change_summary": "8 component schemas: FlowType, PhysicsModel, BoundaryCondition, ConvergenceCriterion, SolverType, PermissionLevel",
            "effective_date": "2026-04-08",
        },
        {
            "title": "PHASE2-ADAPTER-001: D→B Layer Interface",
            "spec_id": "PHASE2-ADAPTER-001",
            "version": "v1.0",
            "scope_type": "API Contract",
            "status": "Approved",
            "change_summary": "StandardPostprocessResult → NLPostprocessInput conversion with TemplateRegistry",
            "effective_date": "2026-04-08",
        },
        {
            "title": "PHASE2-FAILURE-001: Permission Level Constraints",
            "spec_id": "PHASE2-FAILURE-001",
            "version": "v1.0",
            "scope_type": "Security",
            "status": "Approved",
            "change_summary": "Three-tier permission: SUGGEST_ONLY/DRY_RUN/EXECUTE for automation safety",
            "effective_date": "2026-04-08",
        },
        {
            "title": "GATE-001: Quality Gate Interface",
            "spec_id": "GATE-001",
            "version": "v1.0",
            "scope_type": "API Contract",
            "status": "Approved",
            "change_summary": "All gates must implement check() returning GateResult with PASS/WARN/FAIL",
            "effective_date": "2026-03-15",
        },
        {
            "title": "KNOWLEDGE-HIERARCHY-001: Knowledge Levels",
            "spec_id": "KNOWLEDGE-HIERARCHY-001",
            "version": "v1.0",
            "scope_type": "Requirements",
            "status": "Approved",
            "change_summary": "L1 (case-specific) → L2 (generalizable) → L3 (canonical) knowledge tiers",
            "effective_date": "2026-03-01",
        },
    ]

    created = []
    for spec in specs:
        result = api.create_page(
            specs_db_id,
            title=spec["title"],
            properties={
                "Spec ID": {"unique_id": {"prefix": "SPEC", "number": 1}},
                "Version": {"rich_text": [{"text": {"content": spec["version"]}}]},
                "Scope Type": {"select": {"name": spec["scope_type"]}},
                "Status": {"status": {"name": spec["status"]}},
                "Change Summary": {"rich_text": [{"text": {"content": spec["change_summary"]}}]},
                "Effective Date": {"date": {"start": spec["effective_date"]}},
                "Linked Project": {"relation": [{"id": project_id}]},
            }
        )
        created.append(result["id"])
        print(f"✅ Created Spec: {spec['title']}")

    return created


def populate_constraints(api: NotionAPI, constraints_db_id: str, project_id: str):
    """Populate Constraints database"""

    constraints = [
        {
            "title": "No String Types - Use Enums Only",
            "constraint_id": "CONST-ENUM-001",
            "version": "v1.0",
            "constraint_type": "Interface",
            "severity": "Critical",
            "validation_rule": "All type definitions must use enum classes, not string literals",
            "blocking_rule": "Code review must reject any string-based type checking",
            "enabled": True,
            "applies_to": ["Phase 2", "Phase 3"],
        },
        {
            "title": "Dataclass Consistency Requirement",
            "constraint_id": "CONST-DATACLASS-001",
            "version": "v1.0",
            "constraint_type": "Architecture",
            "severity": "Critical",
            "validation_rule": "All core structures must use @dataclass decorator with type hints",
            "blocking_rule": "PR cannot merge without dataclass consistency",
            "enabled": True,
            "applies_to": ["All Phases"],
        },
        {
            "title": "Minimum 80% Test Coverage",
            "constraint_id": "CONST-COVERAGE-001",
            "version": "v1.0",
            "constraint_type": "Testing",
            "severity": "Critical",
            "validation_rule": "pytest coverage must be ≥80% before phase transition",
            "blocking_rule": "Phase gate requires coverage check",
            "enabled": True,
            "applies_to": ["All Phases"],
        },
        {
            "title": "No Data Fabrication - Honesty Constraint",
            "constraint_id": "CONST-HONESTY-001",
            "version": "v1.0",
            "constraint_type": "Security",
            "severity": "Critical",
            "validation_rule": "Missing data must be flagged as data_gap, never invented",
            "blocking_rule": "Any fabricated data in output blocks phase gate",
            "enabled": True,
            "applies_to": ["Phase 1", "Phase 2"],
        },
        {
            "title": "Core Logic Requires Codex Model",
            "constraint_id": "CONST-ROUTING-CODEX-001",
            "version": "v1.0",
            "constraint_type": "Dependency",
            "severity": "High",
            "validation_rule": "Core business logic and algorithms must use Codex (GPT-5.4), not GLM-5.1",
            "blocking_rule": "Model routing table must enforce this assignment",
            "enabled": True,
            "applies_to": ["Phase 2", "Phase 3"],
        },
        {
            "title": "Phase 1 Interface Stability",
            "constraint_id": "CONST-STABILITY-001",
            "version": "v1.0",
            "constraint_type": "Interface",
            "severity": "Critical",
            "validation_rule": "Phase 1 interfaces (ReportSpec, CorrectionSpec, GateResult) cannot break",
            "blocking_rule": "Any interface change requires Opus 4.6 review",
            "enabled": True,
            "applies_to": ["Phase 2", "Phase 3", "Phase 4"],
        },
        {
            "title": "Notion SSOT Sync Within 5 Minutes",
            "constraint_id": "CONST-SSOT-SYNC-001",
            "version": "v1.0",
            "constraint_type": "State Machine",
            "severity": "High",
            "validation_rule": "All task state changes must write to Notion within 5 minutes",
            "blocking_rule": "Git pre-push hook checks Notion sync status",
            "enabled": True,
            "applies_to": ["All Phases"],
        },
        {
            "title": "Python 3.9+ Minimum Version",
            "constraint_id": "CONST-PYTHON-001",
            "version": "v1.0",
            "constraint_type": "Dependency",
            "severity": "High",
            "validation_rule": "All code must support Python 3.9+ (dataclasses require 3.7+)",
            "blocking_rule": "CI/CD pipeline checks Python version compatibility",
            "enabled": True,
            "applies_to": ["All Phases"],
        },
        {
            "title": "Gate Method Interface Requirement",
            "constraint_id": "CONST-GATE-001",
            "version": "v1.0",
            "constraint_type": "Interface",
            "severity": "Critical",
            "validation_rule": "All gates must implement check() method returning GateResult",
            "blocking_rule": "Gate inheritance enforced via abstract base class",
            "enabled": True,
            "applies_to": ["Phase 1", "Phase 2"],
        },
        {
            "title": "Architecture Changes Require Opus Review",
            "constraint_id": "CONST-REVIEW-001",
            "version": "v1.0",
            "constraint_type": "State Machine",
            "severity": "Critical",
            "validation_rule": "Any architecture change must pause for Opus 4.6 review",
            "blocking_rule": "Create Notion review before committing architecture changes",
            "enabled": True,
            "applies_to": ["All Phases"],
        },
        {
            "title": "Phase Transition Gate Requirement",
            "constraint_id": "CONST-PHASE-GATE-001",
            "version": "v1.0",
            "constraint_type": "State Machine",
            "severity": "Critical",
            "validation_rule": "Cannot enter next phase until current phase Opus review passes",
            "blocking_rule": "Phase status in Notion must be Pass before starting next phase",
            "enabled": True,
            "applies_to": ["All Phases"],
        },
        {
            "title": "StandardPostprocessResult Multi-Case Support",
            "constraint_id": "CONST-MULTI-CASE-001",
            "version": "v1.0",
            "constraint_type": "Interface",
            "severity": "High",
            "validation_rule": "PostprocessResult must support related_case_paths for comparison scenarios",
            "blocking_rule": "D→B adapter must handle multi-case results",
            "enabled": True,
            "applies_to": ["Phase 2"],
        },
    ]

    created = []
    for constraint in constraints:
        # Build multi_select for applies_to
        applies_to_select = [{"name": tag} for tag in constraint["applies_to"]]

        result = api.create_page(
            constraints_db_id,
            title=constraint["title"],
            properties={
                "Constraint ID": {"unique_id": {"prefix": "CONST", "number": 1}},
                "Version": {"rich_text": [{"text": {"content": constraint["version"]}}]},
                "Constraint Type": {"select": {"name": constraint["constraint_type"]}},
                "Severity": {"select": {"name": constraint["severity"]}},
                "Validation Rule": {"rich_text": [{"text": {"content": constraint["validation_rule"]}}]},
                "Blocking Rule": {"rich_text": [{"text": {"content": constraint["blocking_rule"]}}]},
                "Enabled": {"checkbox": constraint["enabled"]},
                "Applies To": {"multi_select": applies_to_select},
                "Linked Project": {"relation": [{"id": project_id}]},
            }
        )
        created.append(result["id"])
        print(f"✅ Created Constraint: {constraint['title']}")

    return created


def main():
    config = NotionConfig.from_file()
    api = NotionAPI(config)

    specs_db_id = 'b121995f-7789-41d6-ab0c-8f94c10d829a'
    constraints_db_id = '534ab0aa-42ba-42a8-88f3-5a3e233e65cc'
    project_id = '33cc6894-2bed-8184-a94e-ed5169156638'

    print("🔧 Phase 2c T0: Populating Specs and Constraints tables\n")

    print("📋 Creating Specs...")
    spec_ids = populate_specs(api, specs_db_id, project_id)
    print(f"\n✅ Created {len(spec_ids)} Specs\n")

    print("📋 Creating Constraints...")
    constraint_ids = populate_constraints(api, constraints_db_id, project_id)
    print(f"\n✅ Created {len(constraint_ids)} Constraints\n")

    # Link to project
    print("🔗 Linking to project...")
    # Relations are bidirectional, already set during creation

    print(f"\n✅ Phase 2c T0 Complete!")
    print(f"   - {len(spec_ids)} Specs created")
    print(f"   - {len(constraint_ids)} Constraints created")


if __name__ == "__main__":
    main()
