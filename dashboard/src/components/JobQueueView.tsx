/**
 * JobQueueView - Displays job queue with status indicators and real-time updates
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../services/api';
import wsService from '../services/websocket';
import type { WebSocketMessage } from '../services/websocket';
import type { Job, JobStatus } from '../services/types';
import './JobQueueView.css';

interface JobQueueViewProps {
  caseId?: string;
  onJobSelect?: (job: Job) => void;
}

const STATUS_CONFIG: Record<JobStatus, { label: string; className: string }> = {
  queued: { label: 'Queued', className: 'status-queued' },
  running: { label: 'Running', className: 'status-running' },
  completed: { label: 'Completed', className: 'status-completed' },
  failed: { label: 'Failed', className: 'status-failed' },
  cancelled: { label: 'Cancelled', className: 'status-cancelled' },
};

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

function formatTime(isoString?: string): string {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleTimeString();
}

export default function JobQueueView({ caseId, onJobSelect }: JobQueueViewProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<JobStatus | 'all'>('all');

  // Load jobs from API
  const loadJobs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const allJobs = await apiClient.getJobs();
      const filtered = caseId ? allJobs.filter((j) => j.case_id === caseId) : allJobs;
      setJobs(filtered);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  // Initial load
  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  // Subscribe to WebSocket updates for all active jobs
  useEffect(() => {
    const unsubscribers: (() => void)[] = [];

    jobs.forEach((job) => {
      if (job.status === 'queued' || job.status === 'running') {
        // Connect to WebSocket
        wsService.connect(job.id);

        // Subscribe to updates
        const unsubscribe = wsService.subscribe(job.id, (message: WebSocketMessage) => {
          if (message.type === 'progress' && message.progress !== undefined) {
            setJobs((prev) =>
              prev.map((j) =>
                j.id === job.id ? { ...j, progress: message.progress! } : j
              )
            );
          } else if (message.type === 'status' && message.job) {
            setJobs((prev) =>
              prev.map((j) => (j.id === job.id ? { ...j, ...message.job! } : j))
            );
          } else if (message.type === 'completion' || message.type === 'error') {
            // Job finished, reload full state
            loadJobs();
          }
        });

        unsubscribers.push(unsubscribe);
      }
    });

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }, [jobs, loadJobs]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsService.disconnectAll();
    };
  }, []);

  const filteredJobs = filter === 'all' ? jobs : jobs.filter((j) => j.status === filter);

  const statusCounts = jobs.reduce(
    (acc, job) => {
      acc[job.status] = (acc[job.status] || 0) + 1;
      return acc;
    },
    {} as Record<JobStatus, number>
  );

  if (loading && jobs.length === 0) {
    return (
      <div className="job-queue loading">
        <div className="loading-spinner" />
        <p>Loading jobs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="job-queue error">
        <p className="error-message">{error}</p>
        <button className="btn btn-secondary" onClick={loadJobs}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="job-queue">
      <div className="job-queue-header">
        <h2>Job Queue</h2>
        <div className="job-stats">
          {Object.entries(statusCounts).map(([status, count]) => (
            <span
              key={status}
              className={`stat-badge ${STATUS_CONFIG[status as JobStatus].className}`}
            >
              {STATUS_CONFIG[status as JobStatus].label}: {count}
            </span>
          ))}
        </div>
      </div>

      <div className="job-filters">
        <button
          className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({jobs.length})
        </button>
        <button
          className={`filter-btn ${filter === 'running' ? 'active' : ''}`}
          onClick={() => setFilter('running')}
        >
          Running ({statusCounts.running || 0})
        </button>
        <button
          className={`filter-btn ${filter === 'queued' ? 'active' : ''}`}
          onClick={() => setFilter('queued')}
        >
          Queued ({statusCounts.queued || 0})
        </button>
        <button
          className={`filter-btn ${filter === 'completed' ? 'active' : ''}`}
          onClick={() => setFilter('completed')}
        >
          Completed ({statusCounts.completed || 0})
        </button>
        <button
          className={`filter-btn ${filter === 'failed' ? 'active' : ''}`}
          onClick={() => setFilter('failed')}
        >
          Failed ({statusCounts.failed || 0})
        </button>
      </div>

      {filteredJobs.length === 0 ? (
        <div className="empty-state">
          <p>No jobs found</p>
        </div>
      ) : (
        <div className="job-list">
          {filteredJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onClick={() => onJobSelect?.(job)}
            />
          ))}
        </div>
      )}

      <button className="btn btn-secondary refresh-btn" onClick={loadJobs}>
        Refresh
      </button>
    </div>
  );
}

interface JobCardProps {
  job: Job;
  onClick?: () => void;
}

function JobCard({ job, onClick }: JobCardProps) {
  const config = STATUS_CONFIG[job.status];
  const isActive = job.status === 'queued' || job.status === 'running';

  return (
    <div
      className={`job-card ${config.className} ${isActive ? 'active' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick?.()}
    >
      <div className="job-header">
        <span className="job-id">{job.id}</span>
        <span className={`status-badge ${config.className}`}>{config.label}</span>
      </div>

      <div className="job-details">
        <span className="job-case">Case: {job.case_name || job.case_id}</span>
        <span className="job-time">
          {isActive ? 'Running' : 'Duration'}:{' '}
          {formatDuration(job.started_at, job.completed_at)}
        </span>
      </div>

      {isActive && (
        <div className="progress-container">
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
        <div className="job-error">
          <span className="error-label">Error:</span> {job.error_message}
        </div>
      )}

      <div className="job-footer">
        <span className="job-submitted">
          Submitted: {formatTime(job.started_at)}
        </span>
        <Link to={`/jobs/${job.id}`} className="view-details-link">
          View Details
        </Link>
      </div>
    </div>
  );
}
