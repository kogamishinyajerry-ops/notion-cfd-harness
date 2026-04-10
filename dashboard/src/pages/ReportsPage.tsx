/**
 * ReportsPage - Main reports listing page
 * Displays all available reports and links to detailed viewer
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../services/api';
import type { Report, ReportFormat, ReportStatus } from '../services/types';
import './ReportsPage.css';

const STATUS_CONFIG: Record<ReportStatus, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'status-pending' },
  generating: { label: 'Generating', className: 'status-generating' },
  completed: { label: 'Completed', className: 'status-completed' },
  failed: { label: 'Failed', className: 'status-failed' },
};

const FORMAT_LABELS: Record<ReportFormat, string> = {
  html: 'HTML',
  pdf: 'PDF',
  json: 'JSON',
};

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ReportStatus | 'all'>('all');

  const loadReports = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getReports();
      setReports(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load reports');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const filteredReports = filter === 'all' ? reports : reports.filter((r) => r.status === filter);

  const statusCounts = reports.reduce(
    (acc, report) => {
      acc[report.status] = (acc[report.status] || 0) + 1;
      return acc;
    },
    {} as Record<ReportStatus, number>
  );

  if (loading && reports.length === 0) {
    return (
      <div className="page reports-page loading">
        <div className="loading-spinner" />
        <p>Loading reports...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page reports-page error">
        <p className="error-message">{error}</p>
        <button className="btn btn-secondary" onClick={loadReports}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="page reports-page">
      <div className="reports-header">
        <h1>Reports</h1>
        <div className="report-stats">
          {Object.entries(statusCounts).map(([status, count]) => (
            <span
              key={status}
              className={`stat-badge ${STATUS_CONFIG[status as ReportStatus].className}`}
            >
              {STATUS_CONFIG[status as ReportStatus].label}: {count}
            </span>
          ))}
        </div>
      </div>

      <div className="report-filters">
        <button
          className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({reports.length})
        </button>
        <button
          className={`filter-btn ${filter === 'completed' ? 'active' : ''}`}
          onClick={() => setFilter('completed')}
        >
          Completed ({statusCounts.completed || 0})
        </button>
        <button
          className={`filter-btn ${filter === 'generating' ? 'active' : ''}`}
          onClick={() => setFilter('generating')}
        >
          Generating ({statusCounts.generating || 0})
        </button>
        <button
          className={`filter-btn ${filter === 'failed' ? 'active' : ''}`}
          onClick={() => setFilter('failed')}
        >
          Failed ({statusCounts.failed || 0})
        </button>
      </div>

      {filteredReports.length === 0 ? (
        <div className="empty-state">
          <p>No reports found</p>
        </div>
      ) : (
        <div className="report-list">
          {filteredReports.map((report) => (
            <div key={report.id} className="report-card">
              <div className="report-header">
                <span className="report-id">{report.id}</span>
                <span className={`status-badge ${STATUS_CONFIG[report.status].className}`}>
                  {STATUS_CONFIG[report.status].label}
                </span>
              </div>
              <div className="report-details">
                <span className="report-case">Case: {report.case_name || report.case_id}</span>
                <span className="report-format">Format: {FORMAT_LABELS[report.format]}</span>
              </div>
              <div className="report-footer">
                <span className="report-date">
                  Created: {new Date(report.created_at).toLocaleDateString()}
                </span>
                {report.status === 'completed' && (
                  <Link to={`/reports/${report.id}`} className="view-link">
                    View Report
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <button className="btn btn-secondary refresh-btn" onClick={loadReports}>
        Refresh
      </button>
    </div>
  );
}
