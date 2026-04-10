# Phase 11 Plan 02: Case Builder & Visualization - Summary

## Metadata

- **Plan ID:** 11-02
- **Phase:** 11 — Web Dashboard
- **Milestone:** v1.2.0
- **Status:** Completed
- **Completion Date:** 2026-04-10

## One-liner

Interactive case builder with 5-step wizard, SVG geometry preview (simple_grid, backward_facing_step, body_in_channel), and localStorage persistence mirroring Phase 8 Generic CaseGenerator specs.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create case list view with filtering | fee7c17 | CaseList.tsx, caseBuilder.css |
| 2 | Implement case creation wizard | fee7c17 | CaseWizard.tsx, CasesPage.tsx, router.tsx |
| 3 | Add geometry specification form | fee7c17 | GeometryForm.tsx, caseTypes.ts |
| 4 | Integrate 2D geometry preview | fee7c17 | GeometryPreview.tsx, caseBuilder.css |
| 5 | Add case save/load functionality | fee7c17 | caseStorage.ts, caseTypes.ts |

## Deliverables

- CaseList component with search, geometry type, and status filters
- CaseWizard multi-step wizard (info -> geometry -> physics -> preview -> save)
- GeometryForm with all Phase 8 specs (GeometrySpec, MeshSpec, PhysicsSpec, BoundarySpec)
- SVG-based GeometryPreview 2D visualization for all 3 geometry types
- caseStorage service with localStorage persistence, JSON import/export, clone
- caseTypes with full TypeScript types mirroring Python specs

## Key Files Created

```
dashboard/src/
├── components/
│   ├── CaseList.tsx        # Case list with filtering UI
│   ├── CaseWizard.tsx     # Multi-step case creation wizard
│   ├── GeometryForm.tsx    # Geometry/Mesh/Physics/BC form
│   └── GeometryPreview.tsx # SVG 2D geometry visualization
├── services/
│   ├── caseTypes.ts       # TypeScript types for Phase 8 specs
│   └── caseStorage.ts      # localStorage save/load/import/export
├── pages/
│   └── CasesPage.tsx      # Updated to use wizard
├── caseBuilder.css         # Styles for case builder components
├── main.tsx               # Added caseBuilder.css import
├── router.tsx             # Added /cases/new and /cases/edit/:caseId routes
└── theme.css              # Added case status colors and preview colors
```

## Tech Stack

- **Framework:** React 19 + TypeScript
- **Routing:** React Router v7 (BrowserRouter)
- **Storage:** localStorage for case persistence
- **Geometry Specs:** Mirrors Phase 8 `case_generator_specs.py` types

## Commits

| Hash | Message |
|------|---------|
| fee7c17 | feat(11-web-dashboard): implement case builder UI with wizard |

## Verification

- Build passes: `npm run build` completes successfully
- TypeScript compiles with no errors
- All components render correctly

## Dependencies

- Phase 11-01 (Dashboard Core) must be complete
- Phase 8 Generic CaseGenerator specs (case_generator_specs.py) as source of truth for types

## Notes

- Geometry types: simple_grid, backward_facing_step, body_in_channel
- Solver types: icoFoam, simpleFoam, pimpleFoam
- BC types: fixedValue, zeroGradient, symmetryPlane, wall, empty, patch
- Cases are persisted to localStorage under `cfd_harness_cases` key
- Import creates new case ID to avoid conflicts
- SVG preview shows domain, grid lines, body/flow indicators

## Deviations from Plan

None - plan executed exactly as written.
