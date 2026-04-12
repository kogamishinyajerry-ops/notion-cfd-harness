import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../services/api';
import type { StepType } from '../services/types';
import './PipelineCreatePage.css';

interface StepDraft {
  id: string;
  name: string;
  step_type: StepType;
  depends_on: string[];
  params: string; // JSON string for textarea
}

const STEP_TYPES: StepType[] = ['generate', 'run', 'monitor', 'visualize', 'report'];

// Generate a short unique ID for a step
function makeStepId(name: string, index: number): string {
  const slug = name.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '') || `step_${index + 1}`;
  return `${slug}_${(index + 1).toString().padStart(2, '0')}`;
}

function detectCycle(steps: StepDraft[]): string | null {
  // Build adjacency: stepId -> [dependency stepIds]
  const adj: Record<string, string[]> = {};
  const nameToId: Record<string, string> = {};

  for (const s of steps) {
    nameToId[s.name] = s.id;
  }

  for (const s of steps) {
    adj[s.id] = s.depends_on
      .map((depName) => nameToId[depName])
      .filter(Boolean);
  }

  // DFS cycle detection
  const visited = new Set<string>();
  const stack = new Set<string>();

  function hasCycleFrom(node: string): boolean {
    if (stack.has(node)) return true;
    if (visited.has(node)) return false;
    visited.add(node);
    stack.add(node);
    for (const dep of adj[node] || []) {
      if (hasCycleFrom(dep)) return true;
    }
    stack.delete(node);
    return false;
  }

  for (const s of steps) {
    if (hasCycleFrom(s.id)) {
      return s.name;
    }
  }
  return null;
}

export default function PipelineCreatePage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [steps, setSteps] = useState<StepDraft[]>([
    { id: 'step_01', name: '', step_type: 'generate', depends_on: [], params: '{}' },
  ]);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const addStep = () => {
    setSteps((prev) => [
      ...prev,
      { id: makeStepId('', prev.length), name: '', step_type: 'generate', depends_on: [], params: '{}' },
    ]);
  };

  const removeStep = (index: number) => {
    if (steps.length <= 1) return;
    setSteps((prev) => {
      const updated = prev.filter((_, i) => i !== index);
      // Remove references to deleted step from depends_on
      return updated.map((s) => ({
        ...s,
        depends_on: s.depends_on.filter((dep) => {
          const depIndex = prev.findIndex((p) => p.name === dep);
          return depIndex !== index;
        }),
      }));
    });
  };

  const moveStep = (index: number, direction: 'up' | 'down') => {
    setSteps((prev) => {
      const newSteps = [...prev];
      const target = direction === 'up' ? index - 1 : index + 1;
      if (target < 0 || target >= newSteps.length) return prev;
      [newSteps[index], newSteps[target]] = [newSteps[target], newSteps[index]];
      return newSteps;
    });
  };

  const updateStep = (index: number, field: keyof StepDraft, value: unknown) => {
    setSteps((prev) => {
      const updated = [...prev];
      if (field === 'name') {
        updated[index] = { ...updated[index], name: value as string, id: makeStepId(value as string, index) };
      } else if (field === 'step_type') {
        updated[index] = { ...updated[index], step_type: value as StepType };
      } else if (field === 'params') {
        updated[index] = { ...updated[index], params: value as string };
      } else {
        updated[index] = { ...updated[index], [field]: value };
      }
      return updated;
    });
  };

  const toggleDependency = (stepIndex: number, depName: string) => {
    setSteps((prev) => {
      const updated = [...prev];
      const current = updated[stepIndex].depends_on;
      if (current.includes(depName)) {
        updated[stepIndex] = { ...updated[stepIndex], depends_on: current.filter((d) => d !== depName) };
      } else {
        updated[stepIndex] = { ...updated[stepIndex], depends_on: [...current, depName] };
      }
      return updated;
    });
  };

  const handleSubmit = async () => {
    setFormError(null);

    // Validate
    if (!name.trim()) {
      setFormError('Pipeline name is required.');
      return;
    }
    if (steps.some((s) => !s.name.trim())) {
      setFormError('All steps must have a name.');
      return;
    }

    const cycleStep = detectCycle(steps);
    if (cycleStep) {
      setFormError(`Circular dependency detected in step: "${cycleStep}".`);
      return;
    }

    // Validate JSON params
    for (const s of steps) {
      try {
        JSON.parse(s.params || '{}');
      } catch {
        setFormError(`Invalid JSON in params for step "${s.name}".`);
        return;
      }
    }

    setSubmitting(true);
    try {
      const dag: Record<string, string[]> = {};
      const nameToId: Record<string, string> = {};
      steps.forEach((s) => { nameToId[s.name] = s.id; });
      steps.forEach((s) => {
        dag[s.id] = s.depends_on.map((dep) => nameToId[dep]).filter(Boolean);
      });

      const payload = {
        name: name.trim(),
        description: description.trim() || undefined,
        steps: steps.map((s, i) => ({
          step_id: s.id,
          step_type: s.step_type,
          step_order: i,
          depends_on: dag[s.id] || [],
          params: JSON.parse(s.params || '{}'),
        })),
        config: { dag },
      };

      const created = await apiClient.createPipeline(payload);
      navigate(`/pipelines/${created.id}`);
    } catch (e) {
      setFormError(`Failed to create pipeline: ${e instanceof Error ? e.message : e}`);
    } finally {
      setSubmitting(false);
    }
  };

  const stepNames = steps.map((s) => s.name);

  return (
    <div className="page pipeline-create">
      <div className="create-header">
        <Link to="/pipelines" className="back-link">&larr; Back to Pipelines</Link>
        <h1>Create Pipeline</h1>
      </div>

      <div className="create-form">
        <section className="form-section">
          <h2>Basic Info</h2>
          <div className="form-group">
            <label htmlFor="pipeline-name">Pipeline Name <span className="required">*</span></label>
            <input
              id="pipeline-name"
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={64}
              placeholder="e.g. Standard CFD Workflow"
            />
          </div>
          <div className="form-group">
            <label htmlFor="pipeline-desc">Description</label>
            <textarea
              id="pipeline-desc"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={256}
              placeholder="Optional description..."
              rows={3}
            />
          </div>
        </section>

        <section className="form-section">
          <h2>Steps</h2>
          <div className="steps-builder">
            {steps.map((step, index) => (
              <div key={step.id} className="step-card">
                <div className="step-card-header">
                  <span className="step-number">Step {index + 1}</span>
                  <div className="step-card-actions">
                    {index > 0 && (
                      <button type="button" className="btn-move" onClick={() => moveStep(index, 'up')}>Move Up</button>
                    )}
                    {index < steps.length - 1 && (
                      <button type="button" className="btn-move" onClick={() => moveStep(index, 'down')}>Move Down</button>
                    )}
                    {steps.length > 1 && (
                      <button type="button" className="btn-remove" onClick={() => removeStep(index)}>Remove</button>
                    )}
                  </div>
                </div>
                <div className="form-group">
                  <label>Step Name <span className="required">*</span></label>
                  <input
                    type="text"
                    className="form-input"
                    value={step.name}
                    onChange={(e) => updateStep(index, 'name', e.target.value)}
                    placeholder="e.g. Generate Mesh"
                  />
                </div>
                <div className="form-group">
                  <label>Step Type</label>
                  <select
                    className="form-select"
                    value={step.step_type}
                    onChange={(e) => updateStep(index, 'step_type', e.target.value as StepType)}
                  >
                    {STEP_TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Depends On</label>
                  <div className="depends-on-checkboxes">
                    {stepNames
                      .map((n, i) => ({ name: n, index: i }))
                      .filter(({ index }) => index < index)
                      .map(({ name }) => (
                        <label key={name} className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={step.depends_on.includes(name)}
                            onChange={() => toggleDependency(index, name)}
                          />
                          {name}
                        </label>
                      ))}
                    {stepNames.filter((_, i) => i < index).length === 0 && (
                      <span className="no-deps-hint">No previous steps to depend on</span>
                    )}
                  </div>
                </div>
                <div className="form-group">
                  <label>Params (JSON)</label>
                  <textarea
                    className="form-textarea mono"
                    value={step.params}
                    onChange={(e) => updateStep(index, 'params', e.target.value)}
                    placeholder="{}"
                    rows={3}
                  />
                </div>
              </div>
            ))}
            <button type="button" className="btn-add-step" onClick={addStep}>
              + Add Step
            </button>
          </div>
        </section>

        {formError && (
          <div className="form-error-banner">{formError}</div>
        )}

        <div className="form-actions">
          <Link to="/pipelines" className="btn btn-secondary">Cancel</Link>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? 'Creating...' : 'Create Pipeline'}
          </button>
        </div>
      </div>
    </div>
  );
}
