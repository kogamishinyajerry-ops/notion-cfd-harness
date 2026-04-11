/**
 * JobDetailPage - Detailed job view with logs and output
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiClient } from '../services/api';
import wsService from '../services/websocket';
import type { ResidualMessage, WebSocketMessage } from '../services/websocket';
import type { Job, JobLog, JobStatus } from '../services/types';
import ResultSummaryPanel from '../components/ResultSummaryPanel';
import TrameViewer from '../components/TrameViewer';
import './JobDetailPage.css';

const STATUS_CONFIG: Record<JobStatus, { label: string; className: string }> = {
  queued: { label: 'Queued', className: 'status-queued' },
  running: { label: 'Running', className: 'status-running' },
  completed: { label: 'Completed', className: 'status-completed' },
  failed: { label: 'Failed', className: 'status-failed' },
  cancelled: { label: 'Cancelled', className: 'status-cancelled' },
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

// Mock logs for demonstration - in production these would come from the API
function generateMockLogs(job: Job): JobLog[] {
  const logs: JobLog[] = [
    { timestamp: job.submitted_at || new Date().toISOString(), level: 'INFO', message: 'Job submitted successfully' },
  ];
  if (job.started_at) {
    logs.push({ timestamp: job.started_at, level: 'INFO', message: 'Job started processing' });
  }
  if (job.progress && job.progress > 0) {
    logs.push({ timestamp: new Date().toISOString(), level: 'INFO', message: `Progress: ${job.progress}%` });
  }
  if (job.completed_at && job.status === 'completed') {
    logs.push({ timestamp: job.completed_at, level: 'INFO', message: 'Job completed successfully' });
  }
  if (job.error_message) {
    logs.push({ timestamp: job.completed_at || new Date().toISOString(), level: 'ERROR', message: job.error_message });
  }
  return logs;
}

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<JobLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'logs' | 'output' | 'config' | 'viewer'>('logs');
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [showResultSummary, setShowResultSummary] = useState(false);
  const [finalResiduals, setFinalResiduals] = useState<{
    Ux?: number;
    Uy?: number;
    Uz?: number;
    p?: number;
  } | null>(null);
  const [residualHistory, setResidualHistory] = useState<ResidualMessage[]>([]);

  // Load job from API
  const loadJob = useCallback(async () => {
    if (!jobId) return;
    try {
      setLoading(true);
      setError(null);
      const jobData = await apiClient.getJob(jobId);
      setJob(jobData);
      setLogs(generateMockLogs(jobData));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load job');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  // Initial load
  useEffect(() => {
    loadJob();
  }, [loadJob]);

  // Subscribe to WebSocket updates
  useEffect(() => {
    if (!jobId || !job) return;

    const isActive = job.status === 'queued' || job.status === 'running';
    if (!isActive) return;

    wsService.connect(jobId);

    const unsubscribe = wsService.subscribe(jobId, (message: WebSocketMessage) => {
      if (message.type === 'progress' && message.progress !== undefined) {
        setJob((prev) => (prev ? { ...prev, progress: message.progress! } : prev));
        setLogs((prev) => [
          ...prev,
          {
            timestamp: new Date().toISOString(),
            level: 'INFO' as const,
            message: `Progress: ${message.progress}%`,
          },
        ]);
      } else if (message.type === 'status' && message.job) {
        setJob(message.job);
      } else if (message.type === 'completion') {
        setJob((prev) =>
          prev
            ? {
                ...prev,
                status: 'completed',
                progress: 100,
                completed_at: new Date().toISOString(),
              }
            : prev
        );
        setLogs((prev) => [
          ...prev,
          {
            timestamp: new Date().toISOString(),
            level: 'INFO',
            message: 'Job completed',
          },
        ]);
      } else if (message.type === 'error') {
        setJob((prev) =>
          prev
            ? {
                ...prev,
                status: 'failed',
                error_message: message.error,
              }
            : prev
        );
        setLogs((prev) => [
          ...prev,
          {
            timestamp: new Date().toISOString(),
            level: 'ERROR',
            message: message.error || 'Unknown error',
          },
        ]);
      } else if (message.type === 'residual') {
        const residualMsg = message as ResidualMessage;
        setResidualHistory((prev) => {
          const updated = [...prev, residualMsg];
          return updated.slice(-10);
        });
        // Trigger result summary on convergence (MON-04)
        if (residualMsg.status === 'converged' && !showResultSummary) {
          setFinalResiduals(residualMsg.residuals);
          setShowResultSummary(true);
        }
      }
    });

    return () => {
      unsubscribe();
      wsService.disconnect(jobId);
    };
  }, [jobId, job?.status, showResultSummary]);

  // Auto-scroll logs
  useEffect(() => {
    if (activeTab === 'logs') {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, activeTab]);

  if (loading && !job) {
    return (
      <div className="page job-detail loading">
        <div className="loading-spinner" />
        <p>Loading job details...</p>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="page job-detail error">
        <p className="error-message">{error || 'Job not found'}</p>
        <Link to="/jobs" className="btn btn-secondary">
          Back to Jobs
        </Link>
      </div>
    );
  }

  const config = STATUS_CONFIG[job.status];
  const isActive = job.status === 'queued' || job.status === 'running';

  return (
    <div className="page job-detail">
      <div className="job-detail-header">
        <div className="header-top">
          <Link to="/jobs" className="back-link">
            &larr; Back to Jobs
          </Link>
          <span className={`status-badge ${config.className}`}>{config.label}</span>
        </div>
        <h1>Job: {job.id}</h1>
        <p className="job-case">Case: {job.case_name || job.case_id}</p>
      </div>

      <div className="job-meta-grid">
        <div className="meta-item">
          <span className="meta-label">Status</span>
          <span className={`meta-value status-text ${config.className}`}>{config.label}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Progress</span>
          <span className="meta-value">{Math.round(job.progress)}%</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Duration</span>
          <span className="meta-value">
            {formatDuration(job.started_at, job.completed_at)}
          </span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Submitted</span>
          <span className="meta-value">{formatDateTime(job.started_at)}</span>
        </div>
        {job.started_at && (
          <div className="meta-item">
            <span className="meta-label">Started</span>
            <span className="meta-value">{formatDateTime(job.started_at)}</span>
          </div>
        )}
        {job.completed_at && (
          <div className="meta-item">
            <span className="meta-label">Completed</span>
            <span className="meta-value">{formatDateTime(job.completed_at)}</span>
          </div>
        )}
      </div>

      {isActive && (
        <div className="progress-section">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${job.progress}%` }}
            />
          </div>
          <span className="progress-text">{Math.round(job.progress)}%</span>
        </div>
      )}

      {job.error_message && (
        <div className="error-banner">
          <span className="error-icon">!</span>
          <div>
            <strong>Error:</strong> {job.error_message}
          </div>
        </div>
      )}

      {showResultSummary && finalResiduals && (
        <div className="result-summary-wrapper">
          <ResultSummaryPanel
            iteration={residualHistory[residualHistory.length - 1]?.iteration ?? 0}
            executionTime={
              job.completed_at && job.started_at
                ? (new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000
                : 0
            }
            caseId={job.case_id}
            solver={(job as Record<string, unknown>).solver as string || 'simpleFoam'}
            finalResiduals={finalResiduals}
            onClose={() => setShowResultSummary(false)}
          />
        </div>
      )}

      <div className="job-content-tabs">
        <button
          className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
          onClick={() => setActiveTab('logs')}
        >
          Logs
        </button>
        <button
          className={`tab-btn ${activeTab === 'output' ? 'active' : ''}`}
          onClick={() => setActiveTab('output')}
        >
          Output
        </button>
        <button
          className={`tab-btn ${activeTab === 'config' ? 'active' : ''}`}
          onClick={() => setActiveTab('config')}
        >
          Configuration
        </button>
        {job.status === 'completed' && (
          <button
            className={`tab-btn ${activeTab === 'viewer' ? 'active' : ''}`}
            onClick={() => setActiveTab('viewer')}
          >
            Viewer
          </button>
        )}
      </div>

      <div className="tab-content">
        {activeTab === 'logs' && (
          <div className="logs-view">
            <div className="logs-container">
              {logs.map((log, index) => (
                <div key={index} className={`log-entry log-${log.level.toLowerCase()}`}>
                  <span className="log-time">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className={`log-level ${log.level.toLowerCase()}`}>
                    {log.level}
                  </span>
                  <span className="log-message">{log.message}</span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </div>
        )}

        {activeTab === 'output' && (
          <div className="output-view">
            {job.result ? (
              <pre className="output-json">{JSON.stringify(job.result, null, 2)}</pre>
            ) : (
              <div className="empty-output">
                <p>No output available yet.</p>
                {isActive && <p>Output will appear when the job completes.</p>}
              </div>
            )}
          </div>
        )}

        {activeTab === 'config' && (
          <div className="config-view">
            <div className="config-item">
              <span className="config-label">Job ID</span>
              <span className="config-value">{job.id}</span>
            </div>
            <div className="config-item">
              <span className="config-label">Case ID</span>
              <span className="config-value">{job.case_id}</span>
            </div>
            <div className="config-item">
              <span className="config-label">Case Name</span>
              <span className="config-value">{job.case_name || '-'}</span>
            </div>
          </div>
        )}

        {activeTab === 'viewer' && (
          <div className="viewer-view">
            {job.result?.output_dir ? (
              <TrameViewer
                jobId={job.id}
                caseDir={job.result.output_dir}
                onError={(reason) => console.error('Viewer error:', reason)}
                onConnected={() => {}}
              />
            ) : (
              <div className="viewer-empty">
                <p>No case directory available. Run a job to generate visualization data.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
