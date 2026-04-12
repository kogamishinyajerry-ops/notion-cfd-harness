import { useState, useEffect, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiClient } from '../services/api';
import type { Sweep, SweepCase } from '../services/types';
import './SweepDetailPage.css';

type ActiveTab = 'combinations' | 'summary' | 'config';

function formatDateTime(isoString?: string): string {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleString();
}

function getCaseStatusClass(status: string): string {
  const map: Record<string, string> = {
    QUEUED: 'status-pending',
    RUNNING: 'status-running',
    COMPLETED: 'status-completed',
    FAILED: 'status-failed',
    CANCELLED: 'status-cancelled',
  };
  return map[status] || 'status-pending';
}

function formatSigFigs(val: number | undefined, sig: number = 4): string {
  if (val === undefined || val === null) return '—';
  if (val === 0) return '0';
  const magnitude = Math.floor(Math.log10(Math.abs(val)));
  const scaled = val / Math.pow(10, magnitude);
  return `${scaled.toFixed(sig)}e${magnitude >= 0 ? '+' : ''}${magnitude}`;
}

function downloadCSV(cases: SweepCase[], sweepName: string) {
  const headers = ['Case ID', 'Params', 'Final Residual', 'Status', 'Duration', 'Pipeline ID'];
  const rows = cases.map((c) => [
    c.id,
    Object.entries(c.param_combination).map(([k, v]) => `${k}=${v}`).join(', '),
    c.result_summary?.final_residual !== undefined ? formatSigFigs(c.result_summary.final_residual) : '—',
    c.status,
    c.result_summary?.execution_time !== undefined ? `${c.result_summary.execution_time.toFixed(1)}s` : '—',
    c.pipeline_id || '—',
  ]);
  const csv = [headers, ...rows].map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${sweepName.replace(/\s+/g, '_')}_summary.csv`;
  a.click();
  // Defer revocation so browser finishes reading the blob before URL is invalidated
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export default function SweepDetailPage() {
  const { sweepId } = useParams<{ sweepId: string }>();
  const [sweep, setSweep] = useState<Sweep | null>(null);
  const [cases, setCases] = useState<SweepCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('combinations');
  const [controlLoading, setControlLoading] = useState<string | null>(null);

  const loadSweep = useCallback(async () => {
    if (!sweepId) return;
    try {
      const data = await apiClient.getSweep(sweepId);
      setSweep(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load sweep');
    } finally {
      setLoading(false);
    }
  }, [sweepId]);

  const loadCases = useCallback(async () => {
    if (!sweepId) return;
    try {
      const data = await apiClient.getSweepCases(sweepId);
      setCases(data);
    } catch {
      // non-critical
    }
  }, [sweepId]);

  useEffect(() => {
    loadSweep();
    loadCases();
  }, [loadSweep, loadCases]);

  // Polling: refetch every 10s while not in terminal state
  useEffect(() => {
    if (!sweep) return;
    const terminal = ['COMPLETED', 'FAILED', 'CANCELLED'];
    if (terminal.includes(sweep.status)) return;
    const interval = setInterval(() => { loadSweep(); loadCases(); }, 10000);
    return () => clearInterval(interval);
  }, [sweep, loadSweep, loadCases]);

  const handleControl = async (action: 'start' | 'cancel') => {
    if (!sweepId) return;
    setControlLoading(action);
    try {
      if (action === 'start') await apiClient.startSweep(sweepId);
      else if (action === 'cancel') {
        if (!window.confirm('Cancel this sweep? Combinations already running will stop after their current step completes. Completed outputs are preserved.')) {
          setControlLoading(null);
          return;
        }
        await apiClient.cancelSweep(sweepId);
      }
      await loadSweep();
      await loadCases();
    } catch (e) {
      alert(`Failed to ${action} sweep: ${e instanceof Error ? e.message : e}`);
    } finally {
      setControlLoading(null);
    }
  };

  if (loading && !sweep) {
    return (
      <div className="page sweep-detail loading">
        <div className="loading-spinner" />
        <p>Loading sweep...</p>
      </div>
    );
  }

  if (error || !sweep) {
    return (
      <div className="page sweep-detail error">
        <p className="error-message">{error || 'Sweep not found'}</p>
        <Link to="/sweeps" className="btn btn-secondary">Back to Sweeps</Link>
      </div>
    );
  }

  const statusClass = `status-${sweep.status.toLowerCase()}`;
  const progressPct = sweep.total_combinations > 0
    ? Math.round((sweep.completed_combinations / sweep.total_combinations) * 100)
    : 0;

  const runningCases = cases.filter((c) => c.status === 'RUNNING');
  const queuedCases = cases.filter((c) => c.status === 'QUEUED');
  const completedCases = cases.filter((c) => ['COMPLETED', 'FAILED', 'CANCELLED'].includes(c.status));
  const sortedCases = [...runningCases, ...queuedCases, ...completedCases];

  return (
    <div className="page sweep-detail">
      <div className="sweep-detail-header">
        <Link to="/sweeps" className="back-link">&larr; Back to Sweeps</Link>
        <div className="header-top">
          <h1>{sweep.name}</h1>
          <span className={`status-badge ${statusClass}`}>{sweep.status}</span>
        </div>
        {sweep.description && <p className="sweep-description">{sweep.description}</p>}
      </div>

      <div className="sweep-meta-grid">
        <div className="meta-item">
          <span className="meta-label">Sweep ID</span>
          <span className="meta-value meta-mono">{sweep.id}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Status</span>
          <span className={`meta-value ${statusClass}`}>{sweep.status}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Base Pipeline</span>
          <Link to={`/pipelines/${sweep.base_pipeline_id}`} className="meta-value meta-link">
            {sweep.base_pipeline_id}
          </Link>
        </div>
        <div className="meta-item">
          <span className="meta-label">Created</span>
          <span className="meta-value">{formatDateTime(sweep.created_at)}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Combinations</span>
          <span className="meta-value">{sweep.completed_combinations} / {sweep.total_combinations}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Max Concurrent</span>
          <span className="meta-value">{sweep.max_concurrent}</span>
        </div>
      </div>

      <div className="sweep-control-bar">
        {sweep.status === 'PENDING' && (
          <button className="btn btn-primary" onClick={() => handleControl('start')} disabled={!!controlLoading}>
            {controlLoading === 'start' ? 'Starting...' : 'Start Sweep'}
          </button>
        )}
        {sweep.status === 'RUNNING' && (
          <button className="btn btn-outline-danger" onClick={() => handleControl('cancel')} disabled={!!controlLoading}>
            {controlLoading === 'cancel' ? 'Cancelling...' : 'Cancel Sweep'}
          </button>
        )}
      </div>

      {sweep.status === 'RUNNING' && (
        <div className="pipeline-progress">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <span className="progress-text">{sweep.completed_combinations} / {sweep.total_combinations} combinations complete ({progressPct}%)</span>
        </div>
      )}

      <div className="job-content-tabs">
        <button className={`tab-btn ${activeTab === 'combinations' ? 'active' : ''}`} onClick={() => setActiveTab('combinations')}>Combinations</button>
        <button className={`tab-btn ${activeTab === 'summary' ? 'active' : ''}`} onClick={() => setActiveTab('summary')}>Summary</button>
        <button className={`tab-btn ${activeTab === 'config' ? 'active' : ''}`} onClick={() => setActiveTab('config')}>Config</button>
      </div>

      <div className="tab-content">
        {activeTab === 'combinations' && (
          <div className="combinations-view">
            {sortedCases.length === 0 ? (
              <p className="empty-text">No combinations yet.</p>
            ) : (
              <div className="combination-grid">
                {sortedCases.map((c) => (
                  <div key={c.id} className={`combination-card border-left-${c.status.toLowerCase()}`}>
                    <div className="combination-card-header">
                      <span className="combination-hash">{c.combination_hash}</span>
                      <span className={`status-badge ${getCaseStatusClass(c.status)}`}>{c.status}</span>
                    </div>
                    <div className="combination-params">
                      {Object.entries(c.param_combination).map(([k, v]) => (
                        <span key={k} className="param-badge">{k}={v}</span>
                      ))}
                    </div>
                    <div className="combination-meta">
                      <span>{c.result_summary?.execution_time ? `${c.result_summary.execution_time.toFixed(1)}s` : '—'}</span>
                      {c.pipeline_id && (
                        <Link to={`/pipelines/${c.pipeline_id}`} className="case-pipeline-link">
                          {c.pipeline_id}
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'summary' && (
          <div className="summary-view">
            {sweep.status !== 'COMPLETED' && sweep.status !== 'FAILED' && sweep.status !== 'CANCELLED' ? (
              <p className="summary-unavailable">Summary available after sweep completes.</p>
            ) : cases.length === 0 ? (
              <p className="summary-unavailable">Summary available after sweep completes.</p>
            ) : (
              <>
                <div className="summary-actions">
                  <button className="btn btn-secondary" onClick={() => downloadCSV(cases, sweep.name)}>
                    Export CSV
                  </button>
                </div>
                <div className="summary-table-wrapper">
                  <table className="summary-table">
                    <thead>
                      <tr>
                        <th>Case ID</th>
                        <th>Params</th>
                        <th>Final Residual</th>
                        <th>Status</th>
                        <th>Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cases.map((c) => (
                        <tr key={c.id} className={`row-status-${c.status.toLowerCase()}`}>
                          <td>
                            {c.pipeline_id
                              ? <Link to={`/pipelines/${c.pipeline_id}`}>{c.id}</Link>
                              : c.id
                            }
                          </td>
                          <td className="params-cell">
                            {Object.entries(c.param_combination).map(([k, v]) => `${k}=${v}`).join(', ')}
                          </td>
                          <td>
                            {c.result_summary?.final_residual !== undefined
                              ? formatSigFigs(c.result_summary.final_residual)
                              : '—'
                            }
                          </td>
                          <td><span className={`status-badge ${getCaseStatusClass(c.status)}`}>{c.status}</span></td>
                          <td>
                            {c.result_summary?.execution_time !== undefined
                              ? `${c.result_summary.execution_time.toFixed(1)}s`
                              : '—'
                            }
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'config' && (
          <div className="config-view">
            <div className="config-item">
              <span className="config-label">Sweep ID</span>
              <span className="config-value">{sweep.id}</span>
            </div>
            <div className="config-item">
              <span className="config-label">Base Pipeline ID</span>
              <span className="config-value">{sweep.base_pipeline_id}</span>
            </div>
            <div className="config-item">
              <span className="config-label">Max Concurrent</span>
              <span className="config-value">{sweep.max_concurrent}</span>
            </div>
            <div className="config-item">
              <span className="config-label">Parameter Grid</span>
              <pre className="config-value config-mono">{JSON.stringify(sweep.param_grid, null, 2)}</pre>
            </div>
            <div className="config-item">
              <span className="config-label">Created</span>
              <span className="config-value">{sweep.created_at}</span>
            </div>
            <div className="config-item">
              <span className="config-label">Updated</span>
              <span className="config-value">{sweep.updated_at}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
