/**
 * GeometryForm Component - Geometry specification form
 * Reuses GeometrySpec, MeshSpec from Phase 8 case_generator_specs.py
 */

import type {
  GeometrySpec,
  MeshSpec,
  PhysicsSpec,
  BoundarySpec,
  GeometryType,
  SolverType,
  BCType,
  ValidationError,
} from '../services/caseTypes';
import {
  GEOMETRY_TYPE_LABELS,
  SOLVER_TYPE_LABELS,
  BC_TYPE_LABELS,
} from '../services/caseTypes';

interface GeometryFormProps {
  geometry: GeometrySpec;
  mesh: MeshSpec;
  physics: PhysicsSpec;
  boundary: BoundarySpec;
  onChange: (updates: {
    geometry?: Partial<GeometrySpec>;
    mesh?: Partial<MeshSpec>;
    physics?: Partial<PhysicsSpec>;
    boundary?: Partial<BoundarySpec>;
  }) => void;
  errors?: ValidationError[];
}

export default function GeometryForm({
  geometry,
  mesh,
  physics,
  boundary,
  onChange,
  errors = [],
}: GeometryFormProps) {
  const getError = (field: string): string | undefined =>
    errors.find((e) => e.field === field)?.message;

  const handleGeometryChange = (updates: Partial<GeometrySpec>) => {
    onChange({ geometry: updates });
  };

  const handleMeshChange = (updates: Partial<MeshSpec>) => {
    onChange({ mesh: updates });
  };

  const handlePhysicsChange = (updates: Partial<PhysicsSpec>) => {
    onChange({ physics: updates });
  };

  const handlePatchChange = (name: string, updates: Partial<{ bc_type: BCType; value: string }>) => {
    const newPatches = {
      ...boundary.patches,
      [name]: {
        ...boundary.patches[name],
        ...updates,
      },
    };
    onChange({ boundary: { patches: newPatches } });
  };

  const addPatch = () => {
    const name = prompt('Enter patch name:');
    if (name && !boundary.patches[name]) {
      onChange({
        boundary: {
          patches: {
            ...boundary.patches,
            [name]: { name, bc_type: 'patch', value: '' },
          },
        },
      });
    }
  };

  const removePatch = (name: string) => {
    const newPatches = { ...boundary.patches };
    delete newPatches[name];
    onChange({ boundary: { patches: newPatches } });
  };

  const showBodyFields = geometry.geometry_type === 'body_in_channel';
  const showStepFields = geometry.geometry_type === 'backward_facing_step';
  const showTurbulent = physics.solver === 'simpleFoam';

  return (
    <div className="geometry-form">
      {/* Geometry Section */}
      <section className="form-section">
        <h3>Geometry</h3>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="geometry_type">Geometry Type</label>
            <select
              id="geometry_type"
              value={geometry.geometry_type}
              onChange={(e) =>
                handleGeometryChange({
                  geometry_type: e.target.value as GeometryType,
                })
              }
            >
              {Object.entries(GEOMETRY_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="x_min">X Min</label>
            <input
              id="x_min"
              type="number"
              step="0.01"
              value={geometry.x_min}
              onChange={(e) =>
                handleGeometryChange({ x_min: parseFloat(e.target.value) })
              }
            />
            {getError('x_min') && (
              <span className="error">{getError('x_min')}</span>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="x_max">X Max</label>
            <input
              id="x_max"
              type="number"
              step="0.01"
              value={geometry.x_max}
              onChange={(e) =>
                handleGeometryChange({ x_max: parseFloat(e.target.value) })
              }
            />
            {getError('x_max') && (
              <span className="error">{getError('x_max')}</span>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="y_min">Y Min</label>
            <input
              id="y_min"
              type="number"
              step="0.01"
              value={geometry.y_min}
              onChange={(e) =>
                handleGeometryChange({ y_min: parseFloat(e.target.value) })
              }
            />
            {getError('y_min') && (
              <span className="error">{getError('y_min')}</span>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="y_max">Y Max</label>
            <input
              id="y_max"
              type="number"
              step="0.01"
              value={geometry.y_max}
              onChange={(e) =>
                handleGeometryChange({ y_max: parseFloat(e.target.value) })
              }
            />
            {getError('y_max') && (
              <span className="error">{getError('y_max')}</span>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="thickness">Thickness (z)</label>
            <input
              id="thickness"
              type="number"
              step="0.001"
              value={geometry.thickness}
              onChange={(e) =>
                handleGeometryChange({ thickness: parseFloat(e.target.value) })
              }
            />
          </div>
        </div>

        {/* Body in Channel fields */}
        {showBodyFields && (
          <div className="form-grid body-fields">
            <h4>Body Parameters</h4>
            <div className="form-field">
              <label htmlFor="body_x_min">Body X Min</label>
              <input
                id="body_x_min"
                type="number"
                step="0.01"
                value={geometry.body_x_min ?? ''}
                onChange={(e) =>
                  handleGeometryChange({
                    body_x_min: parseFloat(e.target.value),
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="body_x_max">Body X Max</label>
              <input
                id="body_x_max"
                type="number"
                step="0.01"
                value={geometry.body_x_max ?? ''}
                onChange={(e) =>
                  handleGeometryChange({
                    body_x_max: parseFloat(e.target.value),
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="body_y_min">Body Y Min</label>
              <input
                id="body_y_min"
                type="number"
                step="0.01"
                value={geometry.body_y_min ?? ''}
                onChange={(e) =>
                  handleGeometryChange({
                    body_y_min: parseFloat(e.target.value),
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="body_y_max">Body Y Max</label>
              <input
                id="body_y_max"
                type="number"
                step="0.01"
                value={geometry.body_y_max ?? ''}
                onChange={(e) =>
                  handleGeometryChange({
                    body_y_max: parseFloat(e.target.value),
                  })
                }
              />
            </div>
          </div>
        )}
      </section>

      {/* Mesh Section */}
      <section className="form-section">
        <h3>Mesh</h3>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="nx">Cells X (nx)</label>
            <input
              id="nx"
              type="number"
              min="1"
              value={mesh.nx}
              onChange={(e) =>
                handleMeshChange({ nx: parseInt(e.target.value) || 1 })
              }
            />
          </div>
          <div className="form-field">
            <label htmlFor="ny">Cells Y (ny)</label>
            <input
              id="ny"
              type="number"
              min="1"
              value={mesh.ny}
              onChange={(e) =>
                handleMeshChange({ ny: parseInt(e.target.value) || 1 })
              }
            />
          </div>
        </div>

        {/* Backward Facing Step mesh fields */}
        {showStepFields && (
          <div className="form-grid mesh-fields">
            <h4>Step Mesh Parameters</h4>
            <div className="form-field">
              <label htmlFor="nx_inlet">Inlet Cells X</label>
              <input
                id="nx_inlet"
                type="number"
                min="1"
                value={mesh.nx_inlet ?? ''}
                onChange={(e) =>
                  handleMeshChange({
                    nx_inlet: parseInt(e.target.value) || undefined,
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="nx_outlet">Outlet Cells X</label>
              <input
                id="nx_outlet"
                type="number"
                min="1"
                value={mesh.nx_outlet ?? ''}
                onChange={(e) =>
                  handleMeshChange({
                    nx_outlet: parseInt(e.target.value) || undefined,
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="ny_lower">Lower Cells Y</label>
              <input
                id="ny_lower"
                type="number"
                min="1"
                value={mesh.ny_lower ?? ''}
                onChange={(e) =>
                  handleMeshChange({
                    ny_lower: parseInt(e.target.value) || undefined,
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="ny_upper">Upper Cells Y</label>
              <input
                id="ny_upper"
                type="number"
                min="1"
                value={mesh.ny_upper ?? ''}
                onChange={(e) =>
                  handleMeshChange({
                    ny_upper: parseInt(e.target.value) || undefined,
                  })
                }
              />
            </div>
          </div>
        )}

        {/* Body in Channel mesh fields */}
        {showBodyFields && (
          <div className="form-grid mesh-fields">
            <h4>Body Channel Mesh Parameters</h4>
            <div className="form-field">
              <label htmlFor="nx_left">Left Cells X</label>
              <input
                id="nx_left"
                type="number"
                min="1"
                value={mesh.nx_left ?? ''}
                onChange={(e) =>
                  handleMeshChange({
                    nx_left: parseInt(e.target.value) || undefined,
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="nx_body">Body Cells X</label>
              <input
                id="nx_body"
                type="number"
                min="1"
                value={mesh.nx_body ?? ''}
                onChange={(e) =>
                  handleMeshChange({
                    nx_body: parseInt(e.target.value) || undefined,
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="nx_right">Right Cells X</label>
              <input
                id="nx_right"
                type="number"
                min="1"
                value={mesh.nx_right ?? ''}
                onChange={(e) =>
                  handleMeshChange({
                    nx_right: parseInt(e.target.value) || undefined,
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="ny_outer">Outer Cells Y</label>
              <input
                id="ny_outer"
                type="number"
                min="1"
                value={mesh.ny_outer ?? ''}
                onChange={(e) =>
                  handleMeshChange({
                    ny_outer: parseInt(e.target.value) || undefined,
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="ny_body">Body Cells Y</label>
              <input
                id="ny_body"
                type="number"
                min="1"
                value={mesh.ny_body ?? ''}
                onChange={(e) =>
                  handleMeshChange({
                    ny_body: parseInt(e.target.value) || undefined,
                  })
                }
              />
            </div>
          </div>
        )}
      </section>

      {/* Physics Section */}
      <section className="form-section">
        <h3>Physics</h3>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="solver">Solver</label>
            <select
              id="solver"
              value={physics.solver}
              onChange={(e) =>
                handlePhysicsChange({ solver: e.target.value as SolverType })
              }
            >
              {Object.entries(SOLVER_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="reynolds_number">Reynolds Number</label>
            <input
              id="reynolds_number"
              type="number"
              min="1"
              value={physics.reynolds_number}
              onChange={(e) =>
                handlePhysicsChange({
                  reynolds_number: parseFloat(e.target.value),
                })
              }
            />
          </div>
          <div className="form-field">
            <label htmlFor="u_inlet">Inlet Velocity</label>
            <input
              id="u_inlet"
              type="number"
              step="0.1"
              value={physics.u_inlet}
              onChange={(e) =>
                handlePhysicsChange({ u_inlet: parseFloat(e.target.value) })
              }
            />
          </div>
          <div className="form-field">
            <label htmlFor="u_lid">Lid Velocity</label>
            <input
              id="u_lid"
              type="number"
              step="0.1"
              value={physics.u_lid}
              onChange={(e) =>
                handlePhysicsChange({ u_lid: parseFloat(e.target.value) })
              }
            />
          </div>
        </div>

        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="end_time">End Time</label>
            <input
              id="end_time"
              type="number"
              step="0.1"
              value={physics.end_time}
              onChange={(e) =>
                handlePhysicsChange({ end_time: parseFloat(e.target.value) })
              }
            />
          </div>
          <div className="form-field">
            <label htmlFor="delta_t">Time Step</label>
            <input
              id="delta_t"
              type="number"
              step="0.0001"
              value={physics.delta_t}
              onChange={(e) =>
                handlePhysicsChange({ delta_t: parseFloat(e.target.value) })
              }
            />
          </div>
          <div className="form-field">
            <label htmlFor="write_interval">Write Interval</label>
            <input
              id="write_interval"
              type="number"
              step="0.1"
              value={physics.write_interval}
              onChange={(e) =>
                handlePhysicsChange({
                  write_interval: parseFloat(e.target.value),
                })
              }
            />
          </div>
          {physics.max_co !== undefined && (
            <div className="form-field">
              <label htmlFor="max_co">Max Co Number</label>
              <input
                id="max_co"
                type="number"
                step="0.01"
                value={physics.max_co}
                onChange={(e) =>
                  handlePhysicsChange({
                    max_co: parseFloat(e.target.value) || undefined,
                  })
                }
              />
            </div>
          )}
        </div>

        {/* Turbulent fields */}
        {showTurbulent && (
          <div className="form-grid turbulent-fields">
            <h4>Turbulent Parameters</h4>
            <div className="form-field">
              <label htmlFor="k_inlet">k (Turbulent Kinetic Energy)</label>
              <input
                id="k_inlet"
                type="number"
                step="0.001"
                value={physics.k_inlet ?? ''}
                onChange={(e) =>
                  handlePhysicsChange({
                    k_inlet: parseFloat(e.target.value) || undefined,
                  })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="epsilon_inlet">
                epsilon (Dissipation Rate)
              </label>
              <input
                id="epsilon_inlet"
                type="number"
                step="0.001"
                value={physics.epsilon_inlet ?? ''}
                onChange={(e) =>
                  handlePhysicsChange({
                    epsilon_inlet: parseFloat(e.target.value) || undefined,
                  })
                }
              />
            </div>
          </div>
        )}
      </section>

      {/* Boundary Conditions Section */}
      <section className="form-section">
        <div className="section-header">
          <h3>Boundary Conditions</h3>
          <button type="button" className="btn btn-small" onClick={addPatch}>
            + Add Patch
          </button>
        </div>
        <div className="boundary-patches">
          {Object.entries(boundary.patches).map(([name, patch]) => (
            <div key={name} className="patch-row">
              <div className="patch-name">
                <strong>{name}</strong>
              </div>
              <div className="form-field">
                <label htmlFor={`bc_type_${name}`}>Type</label>
                <select
                  id={`bc_type_${name}`}
                  value={patch.bc_type}
                  onChange={(e) =>
                    handlePatchChange(name, {
                      bc_type: e.target.value as BCType,
                    })
                  }
                >
                  {Object.entries(BC_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor={`value_${name}`}>Value</label>
                <input
                  id={`value_${name}`}
                  type="text"
                  value={patch.value}
                  onChange={(e) =>
                    handlePatchChange(name, { value: e.target.value })
                  }
                  placeholder="e.g., (1 0 0)"
                />
              </div>
              <button
                type="button"
                className="btn btn-small btn-danger"
                onClick={() => removePatch(name)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
