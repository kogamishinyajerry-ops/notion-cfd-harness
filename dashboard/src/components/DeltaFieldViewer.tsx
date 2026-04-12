/**
 * DeltaFieldViewer - iframe viewer for delta field comparison
 *
 * Displays delta field visualization via trame iframe.
 * Field selector triggers POST to create new delta session.
 */

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../services/api';
import type { ComparisonResponse } from '../services/types';
import './DeltaFieldViewer.css';

type FieldName = 'Ux' | 'Uy' | 'Uz' | 'p';

interface DeltaFieldViewerProps {
  comparison: ComparisonResponse;
  onDeltaSessionCreate?: (
    comparisonId: string,
    field: string
  ) => Promise<{ trame_url: string }>;
}

export default function DeltaFieldViewer({
  comparison,
  onDeltaSessionCreate,
}: DeltaFieldViewerProps) {
  const [trameUrl, setTrameUrl] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<FieldName>('Ux');

  // Create delta session when field changes
  const createDeltaSession = useCallback(async (field: FieldName) => {
    if (!comparison.id) return;

    try {
      setLoading(true);
      setError(null);
      setTrameUrl('');

      let result: { trame_url: string };
      if (onDeltaSessionCreate) {
        result = await onDeltaSessionCreate(comparison.id, field);
      } else {
        result = await apiClient.createDeltaSession(comparison.id, field);
      }
      setTrameUrl(result.trame_url);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to create delta session'
      );
    } finally {
      setLoading(false);
    }
  }, [comparison.id, onDeltaSessionCreate]);

  // Create session on mount or field change
  useEffect(() => {
    if (comparison.id && comparison.delta_vtu_path) {
      createDeltaSession(selectedField);
    }
  }, [comparison.id, comparison.delta_vtu_path, selectedField, createDeltaSession]);

  // Handle field change
  const handleFieldChange = (field: FieldName) => {
    setSelectedField(field);
  };

  // Render placeholder when no comparison
  if (!comparison.id) {
    return (
      <div className="delta-field-viewer">
        <div className="delta-placeholder">
          <p>Select a comparison to view delta field</p>
        </div>
      </div>
    );
  }

  // Render loading state
  if (loading) {
    return (
      <div className="delta-field-viewer">
        <div className="delta-loading">
          <div className="delta-spinner" />
          <p>Creating delta session...</p>
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="delta-field-viewer">
        <div className="delta-error">
          <p className="error-message">{error}</p>
          <button className="btn-retry" onClick={() => createDeltaSession(selectedField)}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Render iframe viewer
  return (
    <div className="delta-field-viewer">
      <div className="delta-controls">
        <div className="field-selector">
          <label>Field:</label>
          <select
            value={selectedField}
            onChange={(e) => handleFieldChange(e.target.value as FieldName)}
          >
            <option value="Ux">Ux (Velocity X)</option>
            <option value="Uy">Uy (Velocity Y)</option>
            <option value="Uz">Uz (Velocity Z)</option>
            <option value="p">p (Pressure)</option>
          </select>
        </div>
      </div>

      <div className="delta-viewport">
        {trameUrl ? (
          <iframe
            src={trameUrl}
            title="Delta Field Viewer"
            className="delta-iframe"
          />
        ) : (
          <div className="delta-waiting">
            <p>Select a field to visualize</p>
          </div>
        )}
      </div>
    </div>
  );
}
