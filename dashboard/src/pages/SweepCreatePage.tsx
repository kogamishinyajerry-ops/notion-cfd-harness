import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../services/api';
import type { Pipeline } from '../services/types';
import './SweepCreatePage.css';

interface ParamRow {
  key: string;
  values: string;  // comma-separated string input
}

function parseParamGrid(rows: ParamRow[]): Record<string, (string | number)[]> {
  const grid: Record<string, (string | number)[]> = {};
  for (const row of rows) {
    if (!row.key.trim()) continue;
    const vals = row.values.split(',').map((v) => {
      const trimmed = v.trim();
      // Try parse as number, fall back to string
      const num = Number(trimmed);
      return isNaN(num) ? trimmed : num;
    }).filter((v) => v !== '');
    if (vals.length > 0) {
      grid[row.key.trim()] = vals;
    }
  }
  return grid;
}

function computeCombinationCount(paramGrid: Record<string, (string | number)[]>): number {
  if (Object.keys(paramGrid).length === 0) return 0;
  let count = 1;
  for (const vals of Object.values(paramGrid)) {
    count *= vals.length;
  }
  return count;
}

function computeCombinationCountFromRows(rows: ParamRow[]): number {
  return computeCombinationCount(parseParamGrid(rows));
}

export default function SweepCreatePage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [basePipelineId, setBasePipelineId] = useState('');
  const [maxConcurrent, setMaxConcurrent] = useState(2);
  const [paramRows, setParamRows] = useState<ParamRow[]>([
    { key: '', values: '' },
  ]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiClient.getPipelines().then((data) => {
      setPipelines(data.filter((p) => p.status === 'PENDING'));
    }).catch(() => {});
  }, []);

  const combinationCount = computeCombinationCountFromRows(paramRows);

  const addRow = () => {
    setParamRows((prev) => [...prev, { key: '', values: '' }]);
  };

  const removeRow = (index: number) => {
    setParamRows((prev) => prev.filter((_, i) => i !== index));
  };

  const updateRow = (index: number, field: 'key' | 'values', value: string) => {
    setParamRows((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const handleSubmit = async () => {
    setFormError(null);

    if (!name.trim()) {
      setFormError('Sweep name is required.');
      return;
    }
    if (!basePipelineId) {
      setFormError('Base pipeline is required.');
      return;
    }
    if (Object.keys(parseParamGrid(paramRows)).length === 0) {
      setFormError('Define at least one parameter with values.');
      return;
    }

    const paramGrid = parseParamGrid(paramRows);
    for (const [key, vals] of Object.entries(paramGrid)) {
      if (vals.length === 0) {
        setFormError(`Parameter '${key}' has no values.`);
        return;
      }
    }

    if (combinationCount > 1000) {
      setFormError(`Sweep has ${combinationCount} combinations (max 1000). Reduce parameter values.`);
      return;
    }

    setSubmitting(true);
    try {
      const created = await apiClient.createSweep({
        name: name.trim(),
        description: description.trim() || undefined,
        base_pipeline_id: basePipelineId,
        param_grid: paramGrid,
        max_concurrent: maxConcurrent,
      });
      // Start the sweep immediately after creation
      await apiClient.startSweep(created.id);
      navigate(`/sweeps/${created.id}`);
    } catch (e) {
      setFormError(`Failed to create sweep: ${e instanceof Error ? e.message : e}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page sweep-create">
      <div className="create-header">
        <Link to="/sweeps" className="back-link">&larr; Back to Sweeps</Link>
        <h1>Create Sweep</h1>
      </div>

      <div className="create-form">
        <section className="form-section">
          <h2>Sweep Settings</h2>
          <div className="form-group">
            <label htmlFor="sweep-name">Sweep Name <span className="required">*</span></label>
            <input
              id="sweep-name"
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={64}
              placeholder="e.g. Velocity Sweep Study"
            />
          </div>
          <div className="form-group">
            <label htmlFor="sweep-desc">Description</label>
            <textarea
              id="sweep-desc"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={256}
              placeholder="Optional description..."
              rows={2}
            />
          </div>
          <div className="form-group">
            <label htmlFor="base-pipeline">Base Pipeline <span className="required">*</span></label>
            <select
              id="base-pipeline"
              className="form-select"
              value={basePipelineId}
              onChange={(e) => setBasePipelineId(e.target.value)}
            >
              <option value="">Select a pipeline template...</option>
              {pipelines.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.id})</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="max-concurrent">Max concurrent Docker containers</label>
            <input
              id="max-concurrent"
              type="number"
              className="form-input"
              value={maxConcurrent}
              onChange={(e) => setMaxConcurrent(Math.max(1, Math.min(10, Number(e.target.value))))}
              min={1}
              max={10}
            />
            <span className="form-hint">Default: 2. Each combination runs as an independent Docker container.</span>
          </div>
        </section>

        <section className="form-section">
          <h2>Parameter Grid</h2>
          <div className="param-grid-builder">
            {paramRows.map((row, index) => (
              <div key={index} className="param-row">
                <input
                  type="text"
                  className="form-input param-key"
                  value={row.key}
                  onChange={(e) => updateRow(index, 'key', e.target.value)}
                  placeholder="e.g. velocity"
                  maxLength={64}
                />
                <input
                  type="text"
                  className="form-input param-values"
                  value={row.values}
                  onChange={(e) => updateRow(index, 'values', e.target.value)}
                  placeholder="e.g. 1, 2, 5  — comma-separated"
                />
                {paramRows.length > 1 && (
                  <button
                    type="button"
                    className="btn-remove"
                    onClick={() => removeRow(index)}
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
            <button type="button" className="btn-add-step" onClick={addRow}>
              + Add Parameter
            </button>
          </div>

          <div className={`combination-count-chip ${combinationCount === 0 ? 'zero' : combinationCount > 50 ? 'warning' : ''}`}>
            {combinationCount === 0
              ? 'Define at least one parameter to run a sweep'
              : combinationCount > 50
                ? `${combinationCount} combinations will be run — this sweep may take a long time`
                : `${combinationCount} combinations will be run`
            }
          </div>
        </section>

        {formError && (
          <div className="form-error-banner">{formError}</div>
        )}

        <div className="form-actions">
          <Link to="/sweeps" className="btn btn-secondary">Cancel</Link>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? 'Creating...' : 'Run Sweep'}
          </button>
        </div>
      </div>
    </div>
  );
}
