# AI-CFD Knowledge Harness

**AI-Driven CFD Knowledge Automation Platform**

[![Project Status](https://img.shields.io/badge/status-Accepted-brightgreen)](OPUS_REVIEW_PROJECT_ACCEPTANCE.md)
[![Opus 4.6 Review](https://img.shields.io/badge/Review-REV--PROJECT--001-brightgreen)](OPUS_REVIEW_PROJECT_ACCEPTANCE.md)
[![Tests](https://img.shields.io/badge/tests-1%2C736%20passed-blue)](tests/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## Overview

AI-CFD Knowledge Harness is a **knowledge-driven CFD automation platform** that captures, compiles, and applies engineering knowledge across CFD simulation workflows.

**Core capabilities:**
- **Knowledge Capture** — Teach Mode captures engineering decisions as reusable ReportSpec templates
- **Knowledge Compilation** — Phase 2 execution layer with governance and correction recording
- **Analogical Reasoning** — E1-E6 engine applies historical knowledge to new cases
- **Versioned Memory** — Memory Network tracks knowledge evolution with full provenance
- **Production Ready** — Phase 5 provides caching, auth, metrics, and backup

**Tech stack:** Python 3.9+ | pytest | Notion API | OpenFOAM (optional)

---

## Architecture

```
Phase 1: Knowledge Compiler    ← NL input, ReportSpec, Gates (G1/G2), Gold Standards
Phase 2: Execution Layer       ← Physics Planner, Result Validator, Failure Handler
Phase 3: Analogical Engine     ← E1 Similarity → E2 Decompose → E3 Plan → E4 Trial → E5 Evaluate → E6 Failure Handler
Phase 4: Memory Network        ← Versioned Registry, Propagation, Governance (G3-G6)
Phase 5: Production Ops        ← Cache, Auth, Metrics, Backup
```

See [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md) for full architecture details.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/kogamishinyajerry-ops/notion-cfd-harness.git
cd notion-cfd-harness
pip install -e .   # or: pip install -r requirements.txt
```

### 2. Configure Notion (optional, for SSOT sync)

```bash
# Set Notion integration token
export NOTION_API_KEY="ntn_..."

# Or place token in ~/.notion_key
echo "ntn_your_token_here" > ~/.notion_key
```

### 3. Run Tests

```bash
# All tests
python -m pytest tests/ -q

# With coverage
python -m pytest tests/ --cov=knowledge_compiler --cov-report=term-missing
```

### 4. Run a Benchmark

```bash
# Ghia 1982 lid-driven cavity benchmark
python -m knowledge_compiler.executables.bench_ghia1982

# NACA airfoil VAWT benchmark
python -m knowledge_compiler.executables.bench_naca
```

### 5. Use the Pipeline Orchestrator

```python
from knowledge_compiler.phase2d.pipeline_orchestrator import (
    PipelineOrchestrator,
    PipelineConfig,
    PipelineStage,
)

config = PipelineConfig(
    pipeline_id="demo-001",
    name="Demo Pipeline",
    description="End-to-end CFD workflow",
    enabled_stages=[
        PipelineStage.REPORT_SPEC_GENERATION,
        PipelineStage.PHYSICS_PLANNING,
        PipelineStage.EXECUTION,
    ],
)
orchestrator = PipelineOrchestrator(config)
result = orchestrator.execute({"problem_type": "external_flow"})
```

---

## Key Modules

| Module | Path | Description |
|--------|------|-------------|
| **Phase 1 Schema** | `knowledge_compiler/phase1/schema.py` | ReportSpec, TeachRecord, ProblemType |
| **NL Parser** | `knowledge_compiler/phase1/nl_postprocess.py` | Natural language → structured spec |
| **Gates (G1-G6)** | `knowledge_compiler/phase1/gates.py` | Quality validation gates |
| **Gold Standards** | `knowledge_compiler/phase1/gold_standards/` | Physical accuracy benchmarks |
| **Physics Planner** | `knowledge_compiler/phase3/physics_planner/planner.py` | Solver selection matrix |
| **Analogy Engine** | `knowledge_compiler/phase3/orchestrator/analogy_engine.py` | E1-E6 reasoning |
| **PermissionLevel** | `knowledge_compiler/phase2/execution_layer/failure_handler.py` | L0-L3 safety levels |
| **Memory Network** | `knowledge_compiler/memory_network/` | Version tracking |
| **Notion Events** | `knowledge_compiler/memory_network/notion_memory_events.py` | SSOT integration |
| **Connection Pool** | `knowledge_compiler/performance/connection_pool.py` | Notion API pooling |

---

## Safety Features

| Feature | Phase | Description |
|---------|-------|-------------|
| **PermissionLevel L0-L3** | Phase 2/3 | SUGGEST_ONLY → DRY_RUN → EXECUTE → EXPLORE |
| **Mock Data Protection** | Phase 3 E5 | Blocks mock data from production decisions |
| **RelaxationBoundary** | Phase 3 E6 | Prevents over-relaxation in analogical reasoning |
| **Gate G1/G2** | Phase 1 | ReportSpec completeness and quality gates |
| **Gate G3-G6** | Phase 4 | Memory Network propagation gates |
| **RBAC Auth** | Phase 5 | Role-based access control |

---

## Development

### Model Routing (current分工)

| Task Type | Primary | Secondary |
|-----------|---------|-----------|
| Core algorithms | Codex | GLM-5.1 |
| Gate implementation | Codex | GLM-5.1 |
| Tests | GLM-5.1 | MiniMax-M2.7 |
| Architecture / Gates | Opus 4.6 | — |
| Documentation | GLM-5.1 | — |

See [MODEL_ROUTING_TABLE_v3.md](MODEL_ROUTING_TABLE_v3.md) for full routing table.

### Adding a New Phase

1. Create `knowledge_compiler/phaseN/`
2. Implement components
3. Add gate integration in `gates/`
4. Write tests in `tests/test_phaseN_*.py`
5. Update Notion SSOT
6. Request Opus 4.6 review

### Running Specific Tests

```bash
# Phase 1 tests
python -m pytest tests/test_phase1*.py -v

# Phase 2 tests
python -m pytest tests/phase2*/ -v

# Phase 3 analogy engine tests
python -m pytest tests/phase3/ -v

# Gold standard tests
python -m pytest tests/test_gold_standards*.py -v

# PermissionLevel tests
python -m pytest tests/phase3/test_permission_level_l3.py -v
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md) | Full project plan with phase breakdown |
| [GSD.md](GSD.md) | Guided Software Development rules |
| [OPUS_REVIEW_PROJECT_ACCEPTANCE.md](OPUS_REVIEW_PROJECT_ACCEPTANCE.md) | Opus 4.6 acceptance review |
| [PHASE1_ARCHITECTURE_OVERVIEW.md](PHASE1_ARCHITECTURE_OVERVIEW.md) | Phase 1 architecture |
| [PHASE4_ARCHITECTURE.md](PHASE4_ARCHITECTURE.md) | Phase 4 architecture |
| [Phase4_PLAN.md](Phase4_PLAN.md) | Phase 4 implementation plan |
| [Phase5_PLAN.md](Phase5_PLAN.md) | Phase 5 implementation plan |
| [MODEL_ROUTING_TABLE_v3.md](MODEL_ROUTING_TABLE_v3.md) | Model task routing |

---

## Project Stats

| Metric | Value |
|--------|-------|
| **Total LOC** | ~19,885 |
| **Tests** | 1,736 passing |
| **Test Coverage** | ~80%+ |
| **Phase Count** | 5 (Phase 1–5) |
| **Review Rounds** | 8 |
| **Opus 4.6 Reviews** | 4 |

---

## Next Steps

Phase 6 is planned but not yet started. See [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md) for Phase 6 items:
- HTTP API Authentication
- Knowledge Base Data Encryption
- Notion API Token Rotation

To propose Phase 6 development, open a Notion task and request Opus 4.6 architecture review.

---

## License

MIT — See [LICENSE](LICENSE) file.
