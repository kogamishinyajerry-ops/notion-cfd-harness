/**
 * ReportViewerPage - Interactive report viewer with charts
 * Replaces static HTML with interactive Recharts-based visualization
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
} from 'recharts';
import { apiClient } from '../services/api';
import type { Report, ReportFormat, ReportStatus } from '../services/types';
import './ReportViewerPage.css';

interface ResidualData {
  iteration: number;
  ux: number;
  uy: number;
  p: number;
  continuity: number;
}

interface VelocityProfileData {
  y: number;
  velocity: number;
  goldStandard?: number;
}

interface ComparisonData {
  name: string;
  computed: number;
  literature: number;
  difference: number;
}

const FORMAT_LABELS: Record<ReportFormat, string> = {
  html: 'HTML',
  pdf: 'PDF',
  json: 'JSON',
};

const STATUS_LABELS: Record<ReportStatus, string> = {
  pending: 'Pending',
  generating: 'Generating',
  completed: 'Completed',
  failed: 'Failed',
};

export default function ReportViewerPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'residuals' | 'profiles' | 'comparison'>('overview');

  // Load report
  const loadReport = useCallback(async () => {
    if (!reportId) return;
    try {
      setLoading(true);
      setError(null);
      const reportData = await apiClient.getReport(reportId);
      setReport(reportData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load report');
    } finally {
      setLoading(false);
    }
  }, [reportId]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  if (loading && !report) {
    return (
      <div className="page report-viewer loading">
        <div className="loading-spinner" />
        <p>Loading report...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="page report-viewer error">
        <p className="error-message">{error || 'Report not found'}</p>
        <Link to="/reports" className="btn btn-secondary">
          Back to Reports
        </Link>
      </div>
    );
  }

  return (
    <div className="page report-viewer">
      <div className="report-header">
        <div className="header-top">
          <Link to="/reports" className="back-link">
            &larr; Back to Reports
          </Link>
          <span className={`status-badge status-${report.status}`}>
            {STATUS_LABELS[report.status]}
          </span>
        </div>
        <h1>Report: {report.id}</h1>
        <p className="report-meta">
          Case: {report.case_name || report.case_id} | Format: {FORMAT_LABELS[report.format]}
        </p>
      </div>

      <div className="report-tabs">
        <button
          className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={`tab-btn ${activeTab === 'residuals' ? 'active' : ''}`}
          onClick={() => setActiveTab('residuals')}
        >
          Residuals
        </button>
        <button
          className={`tab-btn ${activeTab === 'profiles' ? 'active' : ''}`}
          onClick={() => setActiveTab('profiles')}
        >
          Velocity Profiles
        </button>
        <button
          className={`tab-btn ${activeTab === 'comparison' ? 'active' : ''}`}
          onClick={() => setActiveTab('comparison')}
        >
          Gold Standard Comparison
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'overview' && <OverviewTab report={report} />}
        {activeTab === 'residuals' && <ResidualsTab />}
        {activeTab === 'profiles' && <ProfilesTab />}
        {activeTab === 'comparison' && <ComparisonTab />}
      </div>
    </div>
  );
}

function OverviewTab({ report }: { report: Report }) {
  return (
    <div className="overview-tab">
      <div className="overview-grid">
        <div className="overview-card">
          <h3>Report Information</h3>
          <dl className="info-list">
            <dt>Report ID</dt>
            <dd>{report.id}</dd>
            <dt>Case</dt>
            <dd>{report.case_name || report.case_id}</dd>
            <dt>Format</dt>
            <dd>{FORMAT_LABELS[report.format]}</dd>
            <dt>Created</dt>
            <dd>{new Date(report.created_at).toLocaleString()}</dd>
            <dt>Status</dt>
            <dd>{STATUS_LABELS[report.status]}</dd>
          </dl>
        </div>

        {report.download_url && (
          <div className="overview-card">
            <h3>Downloads</h3>
            <a
              href={report.download_url}
              className="btn btn-primary download-btn"
              target="_blank"
              rel="noopener noreferrer"
            >
              Download {FORMAT_LABELS[report.format]}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

// Mock residual data - in production this would come from report data
const MOCK_RESIDUAL_DATA: ResidualData[] = Array.from({ length: 100 }, (_, i) => ({
  iteration: i + 1,
  ux: Math.max(1e-6, 1e-2 * Math.exp(-i / 20) + Math.random() * 1e-4),
  uy: Math.max(1e-6, 8e-3 * Math.exp(-i / 25) + Math.random() * 1e-4),
  p: Math.max(1e-6, 5e-3 * Math.exp(-i / 15) + Math.random() * 1e-4),
  continuity: Math.max(1e-6, 2e-2 * Math.exp(-i / 30) + Math.random() * 5e-4),
}));

function ResidualsTab() {
  return (
    <div className="residuals-tab">
      <div className="chart-container">
        <h3>Solver Residuals</h3>
        <p className="chart-description">
          Convergence history of momentum and continuity equations
        </p>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={MOCK_RESIDUAL_DATA} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
            <XAxis
              dataKey="iteration"
              stroke="var(--text-secondary)"
              fontSize={12}
              tickFormatter={(v) => v.toString()}
            />
            <YAxis
              stroke="var(--text-secondary)"
              fontSize={12}
              scale="log"
              domain={['auto', 'auto']}
              tickFormatter={(v) => v.toExponential(1)}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
              }}
              formatter={(value: number) => value.toExponential(2)}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="ux"
              name="Ux Residual"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="uy"
              name="Uy Residual"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="p"
              name="Pressure Residual"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="continuity"
              name="Continuity Residual"
              stroke="#ef4444"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// Mock velocity profile data
const MOCK_VELOCITY_DATA: VelocityProfileData[] = [
  { y: 0, velocity: 0, goldStandard: 0 },
  { y: 0.1, velocity: 0.45, goldStandard: 0.42 },
  { y: 0.2, velocity: 0.72, goldStandard: 0.70 },
  { y: 0.3, velocity: 0.89, goldStandard: 0.88 },
  { y: 0.4, velocity: 0.98, goldStandard: 0.97 },
  { y: 0.5, velocity: 1.02, goldStandard: 1.01 },
  { y: 0.6, velocity: 0.99, goldStandard: 0.98 },
  { y: 0.7, velocity: 0.88, goldStandard: 0.89 },
  { y: 0.8, velocity: 0.71, goldStandard: 0.72 },
  { y: 0.9, velocity: 0.44, goldStandard: 0.43 },
  { y: 1.0, velocity: 0.01, goldStandard: 0 },
];

function ProfilesTab() {
  return (
    <div className="profiles-tab">
      <div className="chart-container">
        <h3>Velocity Profile</h3>
        <p className="chart-description">
          Centerline velocity distribution along flow direction (normalized)
        </p>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={MOCK_VELOCITY_DATA} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
            <XAxis
              dataKey="y"
              stroke="var(--text-secondary)"
              fontSize={12}
              label={{ value: 'Normalized Position (y/L)', position: 'bottom', offset: 0 }}
            />
            <YAxis
              stroke="var(--text-secondary)"
              fontSize={12}
              label={{ value: 'Velocity (m/s)', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="velocity"
              name="Computed"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ fill: '#3b82f6', r: 3 }}
            />
            <Line
              type="monotone"
              dataKey="goldStandard"
              name="Literature (Ghia 1982)"
              stroke="#10b981"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={{ fill: '#10b981', r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// LiteratureComparison data structure matching GoldStandardLoader LiteratureComparison
interface LiteratureComparisonData {
  metric_name: string;
  simulated_value: number;
  reference_value: number;
  error_pct: number;
  unit: string;
  reference_source: string;
  reynolds_number: number;
  status: 'PASS' | 'WARN' | 'FAIL';
}

// Mock comparison data with PASS/WARN/FAIL status
const MOCK_LITERATURE_COMPARISONS: LiteratureComparisonData[] = [
  {
    metric_name: 'Max Centerline Velocity',
    simulated_value: 1.02,
    reference_value: 1.01,
    error_pct: 0.99,
    unit: 'm/s',
    reference_source: 'Ghia 1982',
    reynolds_number: 100,
    status: 'PASS',
  },
  {
    metric_name: 'Pressure Drop (dP)',
    simulated_value: 0.12,
    reference_value: 0.11,
    error_pct: 9.1,
    unit: 'Pa',
    reference_source: 'Armaly 1983',
    reynolds_number: 100,
    status: 'WARN',
  },
  {
    metric_name: 'Recirculation Length (Xr/H)',
    simulated_value: 0.35,
    reference_value: 0.34,
    error_pct: 2.94,
    unit: '-',
    reference_source: 'Armaly 1983',
    reynolds_number: 100,
    status: 'PASS',
  },
  {
    metric_name: 'Wall Shear Stress',
    simulated_value: 0.048,
    reference_value: 0.047,
    error_pct: 2.13,
    unit: 'Pa',
    reference_source: 'Ghia 1982',
    reynolds_number: 100,
    status: 'PASS',
  },
  {
    metric_name: 'Secondary Peak Location',
    simulated_value: 0.82,
    reference_value: 0.75,
    error_pct: 9.33,
    unit: 'y/H',
    reference_source: 'Ghia 1982',
    reynolds_number: 100,
    status: 'FAIL',
  },
];

// Mock comparison data for bar charts
const MOCK_COMPARISON_DATA: ComparisonData[] = MOCK_LITERATURE_COMPARISONS.map((c) => ({
  name: c.metric_name,
  computed: c.simulated_value,
  literature: c.reference_value,
  difference: c.error_pct,
}));

function ComparisonTab() {
  const passCount = MOCK_LITERATURE_COMPARISONS.filter((c) => c.status === 'PASS').length;
  const warnCount = MOCK_LITERATURE_COMPARISONS.filter((c) => c.status === 'WARN').length;
  const failCount = MOCK_LITERATURE_COMPARISONS.filter((c) => c.status === 'FAIL').length;

  return (
    <div className="comparison-tab">
      <div className="gold-standard-header">
        <div className="gs-summary">
          <h3>Literature Validation Summary</h3>
          <div className="gs-status-counts">
            <span className="gs-count pass">{passCount} PASS</span>
            <span className="gs-count warn">{warnCount} WARN</span>
            <span className="gs-count fail">{failCount} FAIL</span>
          </div>
        </div>
        <div className="gs-sources">
          <span className="source-label">Reference Sources:</span>
          <span className="source-badge">Ghia 1982</span>
          <span className="source-badge">Armaly 1983</span>
        </div>
      </div>

      <div className="comparison-section">
        <h4>Detailed Literature Comparison</h4>
        <div className="literature-comparison-table">
          <div className="table-header">
            <span>Metric</span>
            <span>Computed</span>
            <span>Reference</span>
            <span>Error (%)</span>
            <span>Status</span>
          </div>
          {MOCK_LITERATURE_COMPARISONS.map((comparison, idx) => (
            <div key={idx} className={`table-row ${comparison.status.toLowerCase()}`}>
              <span className="metric-name" title={comparison.reference_source}>
                {comparison.metric_name}
                <span className="re-info">Re={comparison.reynolds_number}</span>
              </span>
              <span className="value computed">{comparison.simulated_value.toFixed(4)}</span>
              <span className="value reference">
                {comparison.reference_value.toFixed(4)}
                <span className="unit"> {comparison.unit}</span>
              </span>
              <span className={`value error ${comparison.status.toLowerCase()}`}>
                {comparison.error_pct.toFixed(2)}%
              </span>
              <span className={`status-indicator ${comparison.status.toLowerCase()}`}>
                {comparison.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="chart-container">
        <div className="comparison-section">
          <h4>Quantitative Comparison</h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={MOCK_COMPARISON_DATA} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis
                dataKey="name"
                stroke="var(--text-secondary)"
                fontSize={11}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis
                stroke="var(--text-secondary)"
                fontSize={12}
                label={{ value: 'Value (normalized)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                }}
              />
              <Legend />
              <Bar dataKey="computed" name="Computed" fill="#3b82f6" />
              <Bar dataKey="literature" name="Literature" fill="#10b981" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="comparison-section">
          <h4>Error Analysis</h4>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={MOCK_COMPARISON_DATA} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis
                dataKey="name"
                stroke="var(--text-secondary)"
                fontSize={11}
                angle={-45}
                textAnchor="end"
                height={60}
              />
              <YAxis
                stroke="var(--text-secondary)"
                fontSize={12}
                label={{ value: 'Error (%)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                }}
                formatter={(value: number) => `${value.toFixed(2)}%`}
              />
              <Bar
                dataKey="difference"
                name="Error %"
                fill="#f59e0b"
                background="#f0f0f0"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="comparison-info">
        <h4>Validation Criteria</h4>
        <ul>
          <li><span className="status-indicator pass">PASS</span> Error within threshold (&lt;5%)</li>
          <li><span className="status-indicator warn">WARN</span> Error 5-10% - review recommended</li>
          <li><span className="status-indicator fail">FAIL</span> Error &gt;10% - investigation required</li>
        </ul>
      </div>
    </div>
  );
}
