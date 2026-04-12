import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../services/api';
import type { Pipeline, PipelineStatus } from '../services/types';
import './PipelinesPage.css';

const STATUS_FILTERS: Array<{ label: string; value: PipelineStatus | 'ALL' }> = [
  { label: 'All', value: 'ALL' },
  { label: 'PENDING', value: 'PENDING' },
  { label: 'RUNNING', value: 'RUNNING' },
  { label: 'COMPLETED', value: 'COMPLETED' },
  { label: 'FAILED', value: 'FAILED' },
];

function formatDateTime(isoString?: string): string {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleString();
}

function getStatusClassName(status: PipelineStatus): string {
  const map: Record<PipelineStatus, string> = {
    PENDING: 'status-pending',
    RUNNING: 'status-running',
    MONITORING: 'status-running',
    VISUALIZING: 'status-running',
    REPORTING: 'status-running',
    COMPLETED: 'status-completed',
    FAILED: 'status-failed',
    CANCELLED: 'status-cancelled',
    PAUSED: 'status-paused',
  };
  return map[status] || 'status-pending';
}

export default function PipelinesPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<PipelineStatus | 'ALL'>('ALL');

  const loadPipelines = useCallback(async () => {
    try {
      const data = await apiClient.getPipelines();
      setPipelines(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load pipelines');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPipelines();
  }, [loadPipelines]);

  // Polling: refetch every 10s
  useEffect(() => {
    const interval = setInterval(loadPipelines, 10000);
    return () => clearInterval(interval);
  }, [loadPipelines]);

  const handleDelete = async (pipeline: Pipeline) => {
    if (!window.confirm(`Delete pipeline '${pipeline.name}'? This cannot be undone.`)) {
      return;
    }
    try {
      await apiClient.deletePipeline(pipeline.id);
      setPipelines((prev) => prev.filter((p) => p.id !== pipeline.id));
    } catch (e) {
      alert(`Failed to delete pipeline: ${e instanceof Error ? e.message : e}`);
    }
  };

  const filtered = filter === 'ALL' ? pipelines : pipelines.filter((p) => p.status === filter);

  if (loading && pipelines.length === 0) {
    return (
      <div className="page pipelines loading">
        <div className="loading-spinner" />
        <p>Loading pipelines...</p>
      </div>
    );
  }

  return (
    <div className="page pipelines">
      <div className="pipelines-header">
        <h1>Pipelines</h1>
        <Link to="/pipelines/new" className="btn btn-primary">
          New Pipeline
        </Link>
      </div>

      <div className="pipelines-filter-bar">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            className={`filter-btn ${filter === f.value ? 'active' : ''}`}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon" />
          <h2>No pipelines yet</h2>
          <p>Create your first pipeline to automate your CFD workflow.</p>
          <Link to="/pipelines/new" className="btn btn-primary">
            Create Pipeline
          </Link>
        </div>
      ) : (
        <div className="pipeline-list">
          {filtered.map((pipeline) => (
            <div key={pipeline.id} className={`pipeline-card border-left-${pipeline.status.toLowerCase()}`}>
              <div className="pipeline-card-header">
                <span className="pipeline-name">{pipeline.name}</span>
                <span className={`status-badge ${getStatusClassName(pipeline.status)}`}>
                  {pipeline.status}
                </span>
              </div>
              <div className="pipeline-card-meta">
                <span className="pipeline-id">{pipeline.id}</span>
                {pipeline.description && <span className="pipeline-description">{pipeline.description}</span>}
              </div>
              <div className="pipeline-card-footer">
                <span className="pipeline-created">{formatDateTime(pipeline.created_at)}</span>
                <span className="pipeline-steps">{pipeline.steps?.length ?? 0} steps</span>
              </div>
              <div className="pipeline-card-actions">
                <Link to={`/pipelines/${pipeline.id}`} className="btn-link">
                  View Details
                </Link>
                <button
                  className="btn-text btn-danger"
                  onClick={() => handleDelete(pipeline)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
