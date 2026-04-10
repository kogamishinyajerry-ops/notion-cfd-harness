/**
 * CaseWizard Component - Multi-step case creation wizard
 * Steps: 1. Basic Info -> 2. Geometry/Mesh -> 3. Physics/BC -> 4. Preview -> 5. Save
 */

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type {
  CaseDefinition,
  GeometrySpec,
  MeshSpec,
  PhysicsSpec,
  BoundarySpec,
  ValidationError,
} from '../services/caseTypes';
import { createNewCase } from '../services/caseTypes';
import { saveCase, generateCaseId, importCase } from '../services/caseStorage';
import GeometryForm from './GeometryForm';
import GeometryPreview from './GeometryPreview';

interface CaseWizardProps {
  initialCase?: CaseDefinition;
  onSave?: (caseDef: CaseDefinition) => void;
  onCancel?: () => void;
}

type WizardStep = 'info' | 'geometry' | 'physics' | 'preview' | 'save';

const STEPS: { key: WizardStep; label: string }[] = [
  { key: 'info', label: 'Basic Info' },
  { key: 'geometry', label: 'Geometry & Mesh' },
  { key: 'physics', label: 'Physics & BC' },
  { key: 'preview', label: 'Preview' },
  { key: 'save', label: 'Save' },
];

export default function CaseWizard({
  initialCase,
  onSave,
  onCancel,
}: CaseWizardProps) {
  const navigate = useNavigate();

  const [step, setStep] = useState<WizardStep>('info');
  const [caseDef, setCaseDef] = useState<CaseDefinition>(
    initialCase ??
      createNewCase(generateCaseId(), '')
  );
  const [errors, setErrors] = useState<ValidationError[]>([]);
  const [importError, setImportError] = useState<string | null>(null);

  const currentStepIndex = STEPS.findIndex((s) => s.key === step);

  const handleChange = useCallback(
    (updates: {
      name?: string;
      description?: string;
      geometry?: Partial<GeometrySpec>;
      mesh?: Partial<MeshSpec>;
      physics?: Partial<PhysicsSpec>;
      boundary?: Partial<BoundarySpec>;
    }) => {
      setCaseDef((prev) => {
        const next = { ...prev };
        if ('name' in updates) {
          next.name = updates.name ?? prev.name;
        }
        if ('description' in updates) {
          next.description = updates.description ?? prev.description;
        }
        if ('geometry' in updates && updates.geometry) {
          next.geometry = { ...prev.geometry, ...updates.geometry };
        }
        if ('mesh' in updates && updates.mesh) {
          next.mesh = { ...prev.mesh, ...updates.mesh };
        }
        if ('physics' in updates && updates.physics) {
          next.physics = { ...prev.physics, ...updates.physics };
        }
        if ('boundary' in updates && updates.boundary) {
          next.boundary = {
            ...prev.boundary,
            patches: { ...prev.boundary.patches },
            ...updates.boundary.patches,
          };
        }
        return next;
      });
      // Clear errors on change
      setErrors([]);
    },
    []
  );

  const validateStep = (): boolean => {
    const newErrors: ValidationError[] = [];

    if (step === 'info') {
      if (!caseDef.name.trim()) {
        newErrors.push({ field: 'name', message: 'Case name is required' });
      }
    }

    if (step === 'geometry') {
      // Validate domain
      if (caseDef.geometry.x_min >= caseDef.geometry.x_max) {
        newErrors.push({
          field: 'x_min',
          message: 'x_min must be less than x_max',
        });
      }
      if (caseDef.geometry.y_min >= caseDef.geometry.y_max) {
        newErrors.push({
          field: 'y_min',
          message: 'y_min must be less than y_max',
        });
      }
      if (caseDef.geometry.thickness <= 0) {
        newErrors.push({
          field: 'thickness',
          message: 'thickness must be positive',
        });
      }
      // Body in channel validation
      if (caseDef.geometry.geometry_type === 'body_in_channel') {
        if (
          caseDef.geometry.body_x_min == null ||
          caseDef.geometry.body_x_max == null
        ) {
          newErrors.push({
            field: 'body_x_min',
            message: 'body_x bounds required for body_in_channel',
          });
        }
        if (
          caseDef.geometry.body_y_min == null ||
          caseDef.geometry.body_y_max == null
        ) {
          newErrors.push({
            field: 'body_y_min',
            message: 'body_y bounds required for body_in_channel',
          });
        }
      }
      // Backward facing step validation
      if (caseDef.geometry.geometry_type === 'backward_facing_step') {
        if (
          caseDef.mesh.nx_inlet == null ||
          caseDef.mesh.nx_outlet == null ||
          caseDef.mesh.ny_lower == null ||
          caseDef.mesh.ny_upper == null
        ) {
          newErrors.push({
            field: 'nx_inlet',
            message: 'Step mesh parameters required',
          });
        }
      }
    }

    if (step === 'physics') {
      if (caseDef.physics.end_time <= 0) {
        newErrors.push({
          field: 'end_time',
          message: 'end_time must be positive',
        });
      }
      if (caseDef.physics.delta_t <= 0) {
        newErrors.push({
          field: 'delta_t',
          message: 'delta_t must be positive',
        });
      }
      if (
        caseDef.physics.solver === 'simpleFoam' &&
        (caseDef.physics.k_inlet == null ||
          caseDef.physics.epsilon_inlet == null)
      ) {
        newErrors.push({
          field: 'k_inlet',
          message: 'k and epsilon required for simpleFoam',
        });
      }
    }

    setErrors(newErrors);
    return newErrors.length === 0;
  };

  const handleNext = () => {
    if (validateStep()) {
      const idx = currentStepIndex;
      if (idx < STEPS.length - 1) {
        setStep(STEPS[idx + 1].key);
      }
    }
  };

  const handleBack = () => {
    const idx = currentStepIndex;
    if (idx > 0) {
      setStep(STEPS[idx - 1].key);
    }
  };

  const handleSave = () => {
    if (validateStep()) {
      const finalCase = {
        ...caseDef,
        updated_at: new Date().toISOString(),
      };
      saveCase(finalCase);
      onSave?.(finalCase);
      navigate('/cases');
    }
  };

  const handleImport = async (file: File) => {
    try {
      setImportError(null);
      const imported = await importCase(file);
      setCaseDef(imported);
      setStep('info');
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Import failed');
    }
  };

  const renderStepContent = () => {
    switch (step) {
      case 'info':
        return (
          <div className="wizard-step-content">
            <h2>Basic Information</h2>
            <div className="form-field">
              <label htmlFor="case-name">Case Name *</label>
              <input
                id="case-name"
                type="text"
                value={caseDef.name}
                onChange={(e) => handleChange({ name: e.target.value })}
                placeholder="e.g., Laminar Pipe Flow"
                autoFocus
              />
              {errors.find((e) => e.field === 'name') && (
                <span className="error">
                  {errors.find((e) => e.field === 'name')?.message}
                </span>
              )}
            </div>
            <div className="form-field">
              <label htmlFor="case-description">Description</label>
              <textarea
                id="case-description"
                value={caseDef.description}
                onChange={(e) => handleChange({ description: e.target.value })}
                placeholder="Describe the case..."
                rows={3}
              />
            </div>
            <div className="import-section">
              <h3>Or import from file</h3>
              <input
                type="file"
                accept=".json"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleImport(file);
                }}
              />
              {importError && (
                <span className="error import-error">{importError}</span>
              )}
            </div>
          </div>
        );

      case 'geometry':
        return (
          <div className="wizard-step-content">
            <h2>Geometry & Mesh Specification</h2>
            <GeometryForm
              geometry={caseDef.geometry}
              mesh={caseDef.mesh}
              physics={caseDef.physics}
              boundary={caseDef.boundary}
              onChange={handleChange}
              errors={errors}
            />
          </div>
        );

      case 'physics':
        return (
          <div className="wizard-step-content">
            <h2>Physics & Boundary Conditions</h2>
            <GeometryForm
              geometry={caseDef.geometry}
              mesh={caseDef.mesh}
              physics={caseDef.physics}
              boundary={caseDef.boundary}
              onChange={handleChange}
              errors={errors}
            />
          </div>
        );

      case 'preview':
        return (
          <div className="wizard-step-content">
            <h2>Case Preview</h2>
            <div className="preview-layout">
              <div className="preview-panel">
                <h3>Geometry Preview</h3>
                <GeometryPreview geometry={caseDef.geometry} width={400} height={300} />
              </div>
              <div className="summary-panel">
                <h3>Case Summary</h3>
                <dl className="summary-list">
                  <dt>Name</dt>
                  <dd>{caseDef.name || '(unnamed)'}</dd>
                  <dt>Description</dt>
                  <dd>{caseDef.description || '—'}</dd>
                  <dt>Geometry Type</dt>
                  <dd>{caseDef.geometry.geometry_type}</dd>
                  <dt>Domain</dt>
                  <dd>
                    [{caseDef.geometry.x_min}, {caseDef.geometry.x_max}] x [
                    {caseDef.geometry.y_min}, {caseDef.geometry.y_max}]
                  </dd>
                  <dt>Thickness</dt>
                  <dd>{caseDef.geometry.thickness}</dd>
                  <dt>Mesh</dt>
                  <dd>
                    {caseDef.mesh.nx} x {caseDef.mesh.ny}
                  </dd>
                  <dt>Solver</dt>
                  <dd>{caseDef.physics.solver}</dd>
                  <dt>Re</dt>
                  <dd>{caseDef.physics.reynolds_number}</dd>
                  <dt>End Time</dt>
                  <dd>{caseDef.physics.end_time}</dd>
                  <dt>Patches</dt>
                  <dd>{Object.keys(caseDef.boundary.patches).join(', ')}</dd>
                </dl>
              </div>
            </div>
          </div>
        );

      case 'save':
        return (
          <div className="wizard-step-content">
            <h2>Save Case</h2>
            <div className="save-confirmation">
              <p>
                Ready to save <strong>{caseDef.name || 'this case'}</strong>?
              </p>
              <div className="case-id-display">
                <span className="label">Case ID:</span>
                <code>{caseDef.id}</code>
              </div>
              {errors.length > 0 && (
                <div className="errors-summary">
                  <h4>Please fix the following issues:</h4>
                  <ul>
                    {errors.map((err) => (
                      <li key={err.field}>
                        <strong>{err.field}:</strong> {err.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        );
    }
  };

  return (
    <div className="case-wizard">
      {/* Step Indicator */}
      <div className="wizard-steps">
        {STEPS.map((s, idx) => (
          <div
            key={s.key}
            className={`wizard-step-item ${
              idx === currentStepIndex
                ? 'active'
                : idx < currentStepIndex
                ? 'completed'
                : ''
            }`}
          >
            <span className="step-number">{idx + 1}</span>
            <span className="step-label">{s.label}</span>
          </div>
        ))}
      </div>

      {/* Content */}
      <div className="wizard-content">{renderStepContent()}</div>

      {/* Navigation */}
      <div className="wizard-nav">
        <button
          className="btn btn-secondary"
          onClick={onCancel ?? (() => navigate('/cases'))}
        >
          Cancel
        </button>
        <div className="nav-right">
          {currentStepIndex > 0 && (
            <button className="btn btn-secondary" onClick={handleBack}>
              Back
            </button>
          )}
          {step === 'save' ? (
            <button className="btn btn-primary" onClick={handleSave}>
              Save Case
            </button>
          ) : (
            <button className="btn btn-primary" onClick={handleNext}>
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
