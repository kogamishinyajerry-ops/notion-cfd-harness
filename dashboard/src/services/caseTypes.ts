/**
 * Case Builder Types - Reused from Phase 8 Generic CaseGenerator specs
 * Mirrors GeometrySpec, MeshSpec, PhysicsSpec, BoundarySpec from
 * knowledge_compiler/phase2/execution_layer/case_generator_specs.py
 */

// Geometry types supported by the generic case generator
export type GeometryType =
  | 'simple_grid'
  | 'backward_facing_step'
  | 'body_in_channel';

// OpenFOAM boundary condition types
export type BCType =
  | 'fixedValue'
  | 'zeroGradient'
  | 'symmetryPlane'
  | 'wall'
  | 'empty'
  | 'patch';

// OpenFOAM solver types
export type SolverType = 'icoFoam' | 'simpleFoam' | 'pimpleFoam';

// Boundary patch specification
export interface BoundaryPatchSpec {
  name: string;
  bc_type: BCType;
  value: string;
}

// Geometry specification for the computational domain
export interface GeometrySpec {
  geometry_type: GeometryType;
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  thickness: number;
  // BODY_IN_CHANNEL only
  body_x_min?: number;
  body_x_max?: number;
  body_y_min?: number;
  body_y_max?: number;
}

// Mesh specification
export interface MeshSpec {
  nx: number;
  ny: number;
  // BACKWARD_FACING_STEP
  nx_inlet?: number;
  nx_outlet?: number;
  ny_lower?: number;
  ny_upper?: number;
  // BODY_IN_CHANNEL
  nx_left?: number;
  nx_body?: number;
  nx_right?: number;
  ny_outer?: number;
  ny_body?: number;
}

// Physics specification
export interface PhysicsSpec {
  solver: SolverType;
  reynolds_number: number;
  u_inlet: number;
  u_lid: number;
  k_inlet?: number;
  epsilon_inlet?: number;
  nu?: number;
  end_time: number;
  delta_t: number;
  write_interval: number;
  max_co?: number;
}

// Boundary condition specification
export interface BoundarySpec {
  patches: Record<string, BoundaryPatchSpec>;
}

// Complete case definition for the builder
export interface CaseDefinition {
  id: string;
  name: string;
  description: string;
  geometry: GeometrySpec;
  mesh: MeshSpec;
  physics: PhysicsSpec;
  boundary: BoundarySpec;
  status: 'draft' | 'validated' | 'running' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
}

// Case list filter state
export interface CaseListFilter {
  search: string;
  geometryType: GeometryType | '';
  status: CaseDefinition['status'] | '';
}

// Validation error type
export interface ValidationError {
  field: string;
  message: string;
}

// Default geometry for a new case
export const DEFAULT_GEOMETRY: GeometrySpec = {
  geometry_type: 'simple_grid',
  x_min: 0,
  x_max: 1,
  y_min: 0,
  y_max: 1,
  thickness: 0.01,
};

// Default mesh
export const DEFAULT_MESH: MeshSpec = {
  nx: 40,
  ny: 40,
};

// Default physics for icoFoam
export const DEFAULT_PHYSICS: PhysicsSpec = {
  solver: 'icoFoam',
  reynolds_number: 100,
  u_inlet: 1.0,
  u_lid: 1.0,
  end_time: 10.0,
  delta_t: 0.001,
  write_interval: 1.0,
};

// Default boundary patches
export const DEFAULT_BOUNDARY: BoundarySpec = {
  patches: {
    inlet: { name: 'inlet', bc_type: 'fixedValue', value: '(1 0 0)' },
    outlet: { name: 'outlet', bc_type: 'zeroGradient', value: '' },
    walls: { name: 'walls', bc_type: 'wall', value: '' },
  },
};

// Create a new empty case definition
export function createNewCase(id: string, name: string): CaseDefinition {
  const now = new Date().toISOString();
  return {
    id,
    name,
    description: '',
    geometry: { ...DEFAULT_GEOMETRY },
    mesh: { ...DEFAULT_MESH },
    physics: { ...DEFAULT_PHYSICS },
    boundary: { patches: { ...DEFAULT_BOUNDARY.patches } },
    status: 'draft',
    created_at: now,
    updated_at: now,
  };
}

// Geometry type display labels
export const GEOMETRY_TYPE_LABELS: Record<GeometryType, string> = {
  simple_grid: 'Simple Grid',
  backward_facing_step: 'Backward Facing Step',
  body_in_channel: 'Body in Channel',
};

// Solver type display labels
export const SOLVER_TYPE_LABELS: Record<SolverType, string> = {
  icoFoam: 'icoFoam (Laminar)',
  simpleFoam: 'simpleFoam (RANS)',
  pimpleFoam: 'pimpleFoam (LES)',
};

// BC type display labels
export const BC_TYPE_LABELS: Record<BCType, string> = {
  fixedValue: 'Fixed Value',
  zeroGradient: 'Zero Gradient',
  symmetryPlane: 'Symmetry Plane',
  wall: 'Wall',
  empty: 'Empty',
  patch: 'Patch',
};
