# AI-CFD Knowledge Harness — Project

**Version:** v1.2.0 (Next)
**Status:** Planning

---

## Overview

AI-CFD Knowledge Harness is an intelligent system for Computational Fluid Dynamics knowledge management, case generation, solver execution, and report automation. It uses natural language parsing, analogical reasoning, and literature-validated results.

## Architecture

- **PermissionLevel L0-L3**: Gate-based access control for knowledge operations
- **E1-E6 Analogical Reasoning**: Case similarity and transfer learning
- **Notion SSOT**: Single source of truth for project state and specifications
- **OpenFOAM Docker Executor**: Real solver integration with validation
- **Generic CaseGenerator v2**: Programmatic blockMeshDict generation
- **Report Generator**: Multi-format (HTML/PDF/JSON) with literature comparison

## Milestones

| Milestone | Phases | Status | Ship Date |
|-----------|--------|--------|-----------|
| M1 | 1-7 | ✅ Shipped | 2026-04-07 |
| v1.1.0 | 8-9 | ✅ Shipped | 2026-04-10 |
| v1.2.0 | 10-11 | 🔄 Planning | TBD |

## v1.2.0 — API & Web Interface

**Goal:** Expose harness capabilities via REST API and add web dashboard for case management, job monitoring, and report viewing.

### Proposed Phases

- **Phase 10**: REST API Server — FastAPI-based API exposing all CLI functionality
- **Phase 11**: Web Dashboard — React-based UI for case management, job monitoring, visualization

### Key Features

1. **API Server (Phase 10)**
   - REST endpoints for case creation, job submission, status monitoring
   - JWT authentication with PermissionLevel enforcement
   - WebSocket support for real-time job progress
   - OpenAPI/Swagger documentation

2. **Web Dashboard (Phase 11)**
   - Case builder with geometry visualization
   - Job queue management and real-time status
   - Report viewer with interactive charts
   - Gold standard comparison visualization

## Tech Stack

- **API**: FastAPI + Uvicorn
- **Auth**: JWT tokens, RBAC
- **Dashboard**: React + TypeScript
- **Real-time**: WebSocket
- **Database**: SQLite (local), PostgreSQL (production)

---

## History

<details>
<summary>v1.1.0 — Report Automation & CaseGenerator v2 (2026-04-10)</summary>

- GenericOpenFOAMCaseGenerator: programmatic blockMeshDict generation
- ReportGenerator: HTML + PDF + JSON multi-format output
- GoldStandardLoader: literature comparison (Ghia 1982, Armaly 1983)
- ReportTeachMode: inline correction auto-apply
- 14 passing tests in test_phase9_report_generator.py

</details>

<details>
<summary>M1 — Well-Harness AI-CFD OS (2026-04-07)</summary>

- Phase 1-7: Core knowledge compilation and execution
- PermissionLevel L0-L3 gate system
- E1-E6 analogical reasoning engine
- Notion SSOT integration
- OpenFOAM Docker executor
- 1823 tests passing

</details>
