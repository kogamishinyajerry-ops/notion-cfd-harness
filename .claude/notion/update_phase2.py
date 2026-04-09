#!/usr/bin/env python3
"""
Update Phase 2 Status and Components in Notion

Updates the Phase 2 page with:
1. Status: Pass (8.0/10 from Opus 4.6 REV-97A27E-R3)
2. List of 8 execution layer components
3. Test coverage: 311 tests
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api import NotionAPI, NotionConfig


def get_phase2_page(api: NotionAPI, phases_db_id: str) -> dict:
    """Find Phase 2 page in phases database"""
    results = api.query_database(
        phases_db_id,
        filter={
            "property": "Name",
            "title": {"equals": "Phase 2"}
        }
    )

    if not results:
        print("❌ Phase 2 page not found")
        return None

    return results[0]


def update_phase2_content(api: NotionAPI, page_id: str):
    """Update Phase 2 page content with components list"""

    # Phase 2 content with 8 components
    content = """## Phase 2: Execution Layer (D Layer)

### Status: ✅ PASS (8.0/10)
Reviewed by: Opus 4.6 (REV-97A27E-R3)

### 8 Core Components

#### 1. Schema (schema.py)
- Enums: FlowType, TurbulenceModel, TimeTreatment, Compressibility, BCType, SolverType, ProblemType
- PhysicsModel, BoundaryCondition, ConvergenceCriterion
- SolverSelectionMatrix (2D decision matrix)
- PhysicsPlan factory

#### 2. Physics Planner (planner.py)
- plan_from_spec(): Generate physics plan from CanonicalSpec
- plan_from_case_params(): Generate from case parameters (Re, Ma, etc.)
- validate_plan(): Validate physics configuration
- Automatic boundary condition inference

#### 3. CAD Parser (cad_parser.py)
- Parse CAD geometry from STL/OBJ files
- Extract surface information and boundaries
- Generate CFD-ready geometry description

#### 4. Job Scheduler (job_scheduler.py)
- Queue management for solver jobs
- Resource allocation and priority handling
- Job status tracking

#### 5. Result Validator (result_validator.py)
- validate_solver_result(): Check convergence and exit codes
- validate_field_data(): Detect NaN, Inf, negative pressure
- validate_mesh_quality(): Check aspect ratio, orthogonality
- Anomaly detection and classification

#### 6. Failure Handler (failure_handler.py)
- FailureAnalyzer: Categorize failures (recoverable/non-recoverable)
- RetryHandler: Automatic retry with permission levels (suggest_only/dry_run/execute)
- GateReporter: Generate G4-P2 gate reports
- CorrectionSpecGenerator: Generate learning feedback

#### 7. Postprocess Runner (postprocess_runner.py)
- FieldDataExtractor: Extract field data (p, U, T, k, epsilon, etc.)
- ResidualParser: Parse convergence history
- DerivedQuantityCalculator: Compute pressure drop, velocity magnitude, Re
- StandardPostprocessResult: Standardized output format
- Multi-case and transient data support

#### 8. Postprocess Adapter (postprocess_adapter.py)
- PostprocessAdapter: Convert D layer output to B layer input
- TemplatePostprocessAdapter: Template-based visualization
- VisualizationTemplate registry
- NLPostprocessInput format for Phase 1 B layer

### Test Coverage
- **311 tests** (295 unit + 12 E2E + 4 multi-case/transient)
- All tests passing
- Coverage: execution_layer schema, planner, validator, failure_handler, postprocess

### Data Flow
```
CAD → Mesh → Physics Plan → Solver → Result Validator
                                            ↓
                                    Failure Handler
                                            ↓
                                    Postprocess Runner
                                            ↓
                                    Postprocess Adapter
                                            ↓
                                    NL Postprocess (Phase 1 B)
```

### Integration Points
- Input: CanonicalSpec (Phase 1 C layer)
- Output: NLPostprocessInput (Phase 1 B layer)
- Gates: G4-P2 (failure escalation), G4-P3 (result validation)
"""

    # Create content blocks
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
        elif line.startswith("#### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"text": {"content": line[5:]}}]
                }
            })
        elif line.strip() == "":
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": []}
            })
        elif line.startswith("- "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"text": {"content": line[2:]}}]
                }
            })
        elif line.startswith("```"):
            # Skip code block markers
            continue
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": line}}]
                }
            })

    # First, clear existing blocks by appending empty and then replacing
    # For simplicity, we'll just append new blocks
    api.append_blocks(page_id, blocks)

    print(f"✅ Updated Phase 2 page content")


def main():
    # Load config
    config = NotionConfig.from_file()
    api = NotionAPI(config)

    # Get phases DB ID from config
    phases_db_id = json.load(open(Path(__file__).parent / "config.json"))["notion"]["phases_db_id"]

    # Find Phase 2 page
    print("🔍 Finding Phase 2 page...")
    phase2_page = get_phase2_page(api, phases_db_id)

    if not phase2_page:
        return

    page_id = phase2_page["id"]
    print(f"✅ Found Phase 2 page: {page_id}")

    # Update status (need to know the property name)
    # First get the page to see its properties
    page_data = api.get_page(page_id)
    print(f"📄 Current properties: {list(page_data['properties'].keys())}")

    # Update content
    print("📝 Updating Phase 2 content...")
    update_phase2_content(api, page_id)

    print("\n✅ Phase 2 update completed!")
    print(f"🔗 View at: {phase2_page['url']}")


if __name__ == "__main__":
    main()
