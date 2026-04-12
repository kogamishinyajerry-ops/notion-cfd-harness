import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../services/api';
import type { Sweep, SweepStatus } from '../services/types';
import './SweepsPage.css';

const STATUS_FILTERS: Array<{ label: string; value: SweepStatus | 'ALL' }> = [
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

function getStatusClassName(status: SweepStatus): string {
  const map: Record<SweepStatus, string> = {
    PENDING: 'status-pending',
    RUNNING: 'status-running',
    COMPLETED: 'status-completed',
    FAILED: 'status-failed',
    CANCELLED: 'status-cancelled',
  };
  return map[status] || 'status-pending';
}

export default function SweepsPage() {
  const [sweeps, setSweeps] = useState<Sweep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<SweepStatus | 'ALL'>('ALL');

  const loadSweeps = useCallback(async () => {
    try {
      const data = await apiClient.getSweeps();
      setSweeps(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load sweeps');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSweeps();
  }, [loadSweeps]);

  // Polling: refetch every 10s
  useEffect(() => {
    const interval = setInterval(loadSweeps, 10000);
    return () => clearInterval(interval);
  }, [loadSweeps]);

  const handleDelete = async (sweep: Sweep) => {
    if (!window.confirm(`Delete sweep '${sweep.name}'? This cannot be undone.`)) {
      return;
    }
    try {
      await apiClient.deleteSweep(sweep.id);
      setSweeps((prev) => prev.filter((s) => s.id !== sweep.id));
    } catch (e) {
      alert(`Failed to delete sweep: ${e instanceof Error ? e.message : e}`);
    }
  };

  const filtered = filter === 'ALL' ? sweeps : sweeps.filter((s) => s.status === filter);

  if (loading && sweeps.length === 0) {
    return (
      <div className="page sweeps loading">
        <div className="loading-spinner" />
        <p>Loading sweeps...</p>
      </div>
    );
  }

  return (
    <div className="page sweeps">
      <div className="sweeps-header">
        <h1>Sweeps</h1>
        <Link to="/sweeps/new" className="btn btn-primary">
          New Sweep
        </Link>
      </div>

      <div className="sweeps-filter-bar">
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
          <h2>No sweeps yet</h2>
          <p>Select a base pipeline, define a parameter grid, and run all combinations automatically.</p>
          <Link to="/sweeps/new" className="btn btn-primary">
            Create Sweep
          </Link>
        </div>
      ) : (
        <div className="sweep-list">
          {filtered.map((sweep) => (
            <div key={sweep.id} className={`sweep-card border-left-${sweep.status.toLowerCase()}`}>
              <div className="sweep-card-header">
                <span className="sweep-name">{sweep.name}</span>
                <span className={`status-badge ${getStatusClassName(sweep.status)}`}>
                  {sweep.status}
                </span>
              </div>
              <div className="sweep-card-meta">
                <span className="sweep-id">{sweep.id}</span>
                <span className="sweep-base-pipeline">Base: {sweep.base_pipeline_id}</span>
                <span className="sweep-combinations">{sweep.total_combinations} combinations</span>
              </div>
              <div className="sweep-card-footer">
                <span className="sweep-created">{formatDateTime(sweep.created_at)}</span>
                {sweep.status === 'RUNNING' && (
                  <span className="sweep-progress-inline">
                    {sweep.completed_combinations}/{sweep.total_combinations} done
                  </span>
                )}
              </div>
              <div className="sweep-card-actions">
                <Link to={`/sweeps/${sweep.id}`} className="btn-link">
                  View Details
                </Link>
                <button
                  className="btn-text btn-danger"
                  onClick={() => handleDelete(sweep)}
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
