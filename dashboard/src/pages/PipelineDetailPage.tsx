import { useState, useEffect, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiClient } from '../services/api';
import pipelineWs from '../services/pipelineWs';
import type { Pipeline, PipelineStatus, PipelineEvent, PipelineStep } from '../services/types';
import type { StepStatus } from '../services/types';
import DAGCanvas from '../components/DAGCanvas';
import './PipelineDetailPage.css';

type ActiveTab = 'dag' | 'events' | 'config';

const STATUS_CLASS_MAP: Record<PipelineStatus, string> = {
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

function formatDateTime(isoString?: string): string {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleString();
}

function formatDuration(startedAt?: string, completedAt?: string): string {
  if (!startedAt) return '-';
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const seconds = Math.floor((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function getStepStatusClass(status: string): string {
  const map: Record<string, string> = {
    PENDING: 'status-pending',
    RUNNING: 'status-running',
    COMPLETED: 'status-completed',
    FAILED: 'status-failed',
    SKIPPED: 'status-skipped',
  };
  return map[status] || 'status-pending';
}

export default function PipelineDetailPage() {
  const { pipelineId } = useParams<{ pipelineId: string }>();
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('dag');
  const [wsState, setWsState] = useState<'connected' | 'reconnecting' | 'polling'>('reconnecting');
  const [controlLoading, setControlLoading] = useState<string | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  const loadPipeline = useCallback(async () => {
    if (!pipelineId) return;
    try {
      const data = await apiClient.getPipeline(pipelineId);
      setPipeline(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load pipeline');
    } finally {
      setLoading(false);
    }
  }, [pipelineId]);

  const loadEvents = useCallback(async () => {
    if (!pipelineId) return;
    try {
      const evts = await apiClient.getPipelineEvents(pipelineId);
      setEvents(evts as PipelineEvent[]);
    } catch {
      // events are non-critical
    }
  }, [pipelineId]);

  useEffect(() => {
    loadPipeline();
    loadEvents();
  }, [loadPipeline, loadEvents]);

  // WebSocket subscription
  useEffect(() => {
    if (!pipelineId || !pipeline) return;

    const terminalStates: PipelineStatus[] = ['COMPLETED', 'FAILED', 'CANCELLED'];
    if (terminalStates.includes(pipeline.status)) {
      setWsState('connected');
      return;
    }

    pipelineWs.connect(pipelineId);

    const unsubscribe = pipelineWs.subscribe(pipelineId, (event: PipelineEvent) => {
      setWsState(pipelineWs.getReconnectState(pipelineId));

      // Update step statuses from events
      if (event.type === 'step_started' || event.type === 'step_completed' || event.type === 'step_failed') {
        setPipeline((prev) => {
          if (!prev) return prev;
          const updatedSteps = prev.steps.map((s) => {
            if (s.id === event.step_id) {
              return {
                ...s,
                status: event.type === 'step_started' ? 'RUNNING' as StepStatus
                  : event.type === 'step_completed' ? 'COMPLETED' as StepStatus
                  : 'FAILED' as StepStatus,
              };
            }
            return s;
          });
          return { ...prev, steps: updatedSteps };
        });
      }

      // Update pipeline status from pipeline events
      if (event.type.startsWith('pipeline_')) {
        setPipeline((prev) => {
          if (!prev) return prev;
          const statusMap: Record<string, PipelineStatus> = {
            pipeline_started: 'RUNNING',
            pipeline_completed: 'COMPLETED',
            pipeline_failed: 'FAILED',
            pipeline_cancelled: 'CANCELLED',
            pipeline_paused: 'PAUSED',
            pipeline_resumed: 'RUNNING',
          };
          if (statusMap[event.type]) {
            return { ...prev, status: statusMap[event.type] };
          }
          return prev;
        });
      }

      // Append to events list
      setEvents((prev) => [...prev.slice(-99), event]);
    });

    setWsState(pipelineWs.getReconnectState(pipelineId));

    return () => {
      unsubscribe();
      pipelineWs.disconnect(pipelineId);
    };
  }, [pipelineId, pipeline?.status]);

  // Polling fallback
  useEffect(() => {
    if (!pipelineId) return;
    const terminalStates: PipelineStatus[] = ['COMPLETED', 'FAILED', 'CANCELLED'];
    if (terminalStates.includes(pipeline?.status as PipelineStatus)) return;

    if (wsState === 'polling') {
      const interval = setInterval(loadPipeline, 5000);
      return () => clearInterval(interval);
    }
  }, [pipelineId, pipeline?.status, wsState, loadPipeline]);

  const handleNodeClick = useCallback((step: PipelineStep) => {
    setSelectedStepId(step.id);
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setSelectedStepId(null);
  }, []);

  const handleControl = async (action: 'start' | 'pause' | 'resume' | 'cancel') => {
    if (!pipelineId) return;
    setControlLoading(action);
    try {
      if (action === 'start') await apiClient.startPipeline(pipelineId);
      else if (action === 'pause') await apiClient.pausePipeline(pipelineId);
      else if (action === 'resume') await apiClient.resumePipeline(pipelineId);
      else if (action === 'cancel') await apiClient.cancelPipeline(pipelineId);
      await loadPipeline();
    } catch (e) {
      alert(`Failed to ${action} pipeline: ${e instanceof Error ? e.message : e}`);
    } finally {
      setControlLoading(null);
    }
  };

  if (loading && !pipeline) {
    return (
      <div className="page pipeline-detail loading">
        <div className="loading-spinner" />
        <p>Loading pipeline...</p>
      </div>
    );
  }

  if (error || !pipeline) {
    return (
      <div className="page pipeline-detail error">
        <p className="error-message">{error || 'Pipeline not found'}</p>
        <Link to="/pipelines" className="btn btn-secondary">Back to Pipelines</Link>
      </div>
    );
  }

  const statusClass = STATUS_CLASS_MAP[pipeline.status] || 'status-pending';
  const isRunning = ['RUNNING', 'MONITORING', 'VISUALIZING', 'REPORTING'].includes(pipeline.status);
  const completedSteps = pipeline.steps.filter((s) => s.status === 'COMPLETED').length;
  const totalSteps = pipeline.steps.length;
  const progressPct = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  return (
    <div className="page pipeline-detail">
      <div className="pipeline-detail-header">
        <Link to="/pipelines" className="back-link">&larr; Back to Pipelines</Link>
        <div className="header-top">
          <h1>{pipeline.name}</h1>
          <span className={`status-badge ${statusClass}`}>{pipeline.status}</span>
          {wsState === 'reconnecting' && <span className="ws-indicator reconnecting">Reconnecting...</span>}
          {wsState === 'polling' && <span className="ws-indicator polling">Polling</span>}
        </div>
        {pipeline.description && <p className="pipeline-description">{pipeline.description}</p>}
      </div>

      <div className="pipeline-meta-grid">
        <div className="meta-item">
          <span className="meta-label">ID</span>
          <span className="meta-value meta-mono">{pipeline.id}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Status</span>
          <span className={`meta-value ${statusClass}`}>{pipeline.status}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Created</span>
          <span className="meta-value">{formatDateTime(pipeline.created_at)}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Updated</span>
          <span className="meta-value">{formatDateTime(pipeline.updated_at)}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Steps</span>
          <span className="meta-value">{totalSteps}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Duration</span>
          <span className="meta-value">{formatDuration(pipeline.started_at, pipeline.completed_at)}</span>
        </div>
      </div>

      <div className="pipeline-control-bar">
        {pipeline.status === 'PENDING' && (
          <button className="btn btn-success" onClick={() => handleControl('start')} disabled={!!controlLoading}>
            {controlLoading === 'start' ? 'Starting...' : 'Start'}
          </button>
        )}
        {(isRunning) && (
          <button className="btn btn-warning" onClick={() => handleControl('pause')} disabled={!!controlLoading}>
            {controlLoading === 'pause' ? 'Pausing...' : 'Pause'}
          </button>
        )}
        {pipeline.status === 'PAUSED' && (
          <button className="btn btn-info" onClick={() => handleControl('resume')} disabled={!!controlLoading}>
            {controlLoading === 'resume' ? 'Resuming...' : 'Resume'}
          </button>
        )}
        {(isRunning || pipeline.status === 'PAUSED') && (
          <button className="btn btn-outline-danger" onClick={() => handleControl('cancel')} disabled={!!controlLoading}>
            {controlLoading === 'cancel' ? 'Cancelling...' : 'Cancel Pipeline'}
          </button>
        )}
        {(pipeline.status === 'FAILED' || pipeline.status === 'CANCELLED') && (
          <button className="btn btn-secondary" onClick={() => {/* re-run: create new */}}>
            Re-run
          </button>
        )}
      </div>

      {isRunning && (
        <div className="pipeline-progress">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <span className="progress-text">{progressPct}%</span>
        </div>
      )}

      <div className="job-content-tabs">
        <button className={`tab-btn ${activeTab === 'dag' ? 'active' : ''}`} onClick={() => setActiveTab('dag')}>DAG</button>
        <button className={`tab-btn ${activeTab === 'events' ? 'active' : ''}`} onClick={() => setActiveTab('events')}>Events</button>
        <button className={`tab-btn ${activeTab === 'config' ? 'active' : ''}`} onClick={() => setActiveTab('config')}>Config</button>
      </div>

      <div className="tab-content">
        {activeTab === 'dag' && (
          <DAGCanvas
            steps={pipeline.steps}
            config={pipeline.config}
            selectedStepId={selectedStepId}
            onNodeClick={handleNodeClick}
            onCloseDrawer={handleCloseDrawer}
          />
        )}

        {activeTab === 'events' && (
          <div className="events-view">
            {events.length === 0 ? (
              <p className="empty-text">No events recorded yet.</p>
            ) : (
              events.map((ev, i) => (
                <div key={i} className="event-row">
                  <span className="event-time">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                  <span className="event-type">{ev.type}</span>
                  <span className="event-seq">seq={ev.sequence}</span>
                  {ev.step_id && <span className="event-step">step={ev.step_id}</span>}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'config' && (
          <div className="config-view">
            <div className="config-item">
              <span className="config-label">Pipeline ID</span>
              <span className="config-value">{pipeline.id}</span>
            </div>
            <div className="config-item">
              <span className="config-label">Name</span>
              <span className="config-value">{pipeline.name}</span>
            </div>
            <div className="config-item">
              <span className="config-label">Description</span>
              <span className="config-value">{pipeline.description || '-'}</span>
            </div>
            <div className="config-item">
              <span className="config-label">DAG</span>
              <pre className="config-value config-mono">{JSON.stringify(pipeline.config, null, 2)}</pre>
            </div>
            <div className="config-item">
              <span className="config-label">Created</span>
              <span className="config-value">{pipeline.created_at}</span>
            </div>
            <div className="config-item">
              <span className="config-label">Updated</span>
              <span className="config-value">{pipeline.updated_at}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
