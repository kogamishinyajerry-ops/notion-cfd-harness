#!/usr/bin/env python3
"""
Add Phase 2 Component List Content
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path('.claude/notion')))
from api import NotionAPI, NotionConfig


def add_phase2_content():
    config = NotionConfig.from_file()
    api = NotionAPI(config)

    page_id = '33cc6894-2bed-81ac-a681-ee33bbf6bcd8'

    content = """## 8 Core Components

### 1. Schema (schema.py)
Enums: FlowType, TurbulenceModel, TimeTreatment, Compressibility, BCType
PhysicsModel, BoundaryCondition, ConvergenceCriterion, PhysicsPlan
SolverSelectionMatrix (2D decision matrix)

### 2. Physics Planner (planner.py)
plan_from_spec(): Generate physics plan from CanonicalSpec
plan_from_case_params(): Generate from Re, Ma parameters
validate_plan(): Validate physics configuration

### 3. CAD Parser (cad_parser.py)
Parse CAD geometry from STL/OBJ files
Extract surface information and boundaries

### 4. Job Scheduler (job_scheduler.py)
Queue management for solver jobs
Resource allocation and priority handling

### 5. Result Validator (result_validator.py)
validate_solver_result(): Check convergence
validate_field_data(): Detect NaN, Inf
validate_mesh_quality(): Check aspect ratio

### 6. Failure Handler (failure_handler.py)
FailureAnalyzer: Categorize failures
RetryHandler: Retry with permission levels (suggest_only/dry_run/execute)
GateReporter: Generate G4-P2 gate reports

### 7. Postprocess Runner (postprocess_runner.py)
FieldDataExtractor, ResidualParser, DerivedQuantityCalculator
StandardPostprocessResult with multi-case and transient support

### 8. Postprocess Adapter (postprocess_adapter.py)
PostprocessAdapter: Convert D layer to B layer format
TemplatePostprocessAdapter: Template-based visualization

## Test Coverage
311 tests (all passing)
- 295 unit tests
- 12 E2E integration tests
- 4 multi-case/transient tests"""

    blocks = []
    for line in content.split("\n"):
        if line.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": line[3:]}}]
                }
            })
        elif line.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"text": {"content": line[4:]}}]
                }
            })
        elif line.strip() == "":
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": []}
            })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": line}}]
                }
            })

    api.append_blocks(page_id, blocks)
    print("✅ Added Phase 2 content")
    print(f"🔗 https://www.notion.so/Phase-2-Execution-Layer-33cc68942bed81aca681ee33bbf6bcd8")


if __name__ == "__main__":
    add_phase2_content()
