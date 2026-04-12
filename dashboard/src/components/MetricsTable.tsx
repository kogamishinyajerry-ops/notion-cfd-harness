/**
 * MetricsTable - Sortable comparison metrics table
 *
 * Displays case metrics with diff% highlighting.
 * Supports CSV and JSON download.
 */

import { useState, useMemo, useCallback } from 'react';
import { apiClient } from '../services/api';
import type { MetricsRow, ComparisonResponse } from '../services/types';
import './MetricsTable.css';

type SortKey = 'case_id' | 'final_residual' | 'execution_time' | 'openfoam_version' | 'diff_percent';
type SortDir = 'asc' | 'desc';

interface MetricsTableProps {
  metrics: MetricsRow[];
  referenceCaseId: string;
  comparisonId?: string;
}

export default function MetricsTable({
  metrics,
  referenceCaseId,
  comparisonId,
}: MetricsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('case_id');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [downloading, setDownloading] = useState(false);

  // Sort metrics
  const sortedMetrics = useMemo(() => {
    return [...metrics].sort((a, b) => {
      let aVal: string | number | undefined;
      let bVal: string | number | undefined;

      switch (sortKey) {
        case 'case_id':
          aVal = a.case_id;
          bVal = b.case_id;
          break;
        case 'final_residual':
          aVal = a.final_residual;
          bVal = b.final_residual;
          break;
        case 'execution_time':
          aVal = a.execution_time;
          bVal = b.execution_time;
          break;
        case 'openfoam_version':
          aVal = a.openfoam_version;
          bVal = b.openfoam_version;
          break;
        case 'diff_percent':
          aVal = a.diff_percent;
          bVal = b.diff_percent;
          break;
      }

      if (aVal === undefined) return 1;
      if (bVal === undefined) return -1;

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      const aNum = Number(aVal);
      const bNum = Number(bVal);
      return sortDir === 'asc' ? aNum - bNum : bNum - aNum;
    });
  }, [metrics, sortKey, sortDir]);

  // Handle sort click
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  // Download CSV
  const downloadCSV = useCallback(() => {
    const headers = ['Case ID', 'Params', 'Final Residual', 'Execution Time', 'OpenFOAM Version', 'Diff%'];
    const rows = sortedMetrics.map((row) => [
      row.case_id,
      JSON.stringify(row.params),
      row.final_residual?.toExponential(4) || '—',
      row.execution_time ? `${row.execution_time.toFixed(2)}s` : '—',
      row.openfoam_version || '—',
      row.diff_percent !== undefined ? `${row.diff_percent.toFixed(2)}%` : '—',
    ]);

    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `comparison-metrics-${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [sortedMetrics]);

  // Download JSON
  const downloadJSON = useCallback(async () => {
    if (!comparisonId) {
      // Download local data if no comparison ID
      const json = JSON.stringify(sortedMetrics, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `comparison-metrics-${Date.now()}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      return;
    }

    try {
      setDownloading(true);
      const fullComparison = await apiClient.getComparison(comparisonId);
      const json = JSON.stringify(fullComparison, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `comparison-${comparisonId}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }, [comparisonId, sortedMetrics]);

  // Render sort indicator
  const renderSortIndicator = (key: SortKey) => {
    if (sortKey !== key) return <span className="sort-indicator"> </span>;
    return (
      <span className="sort-indicator">
        {sortDir === 'asc' ? ' \u2191' : ' \u2193'}
      </span>
    );
  };

  // Format value for display
  const formatValue = (value: string | number | undefined): string => {
    if (value === undefined) return '—';
    if (typeof value === 'number') {
      if (value < 0.001 || value > 10000) {
        return value.toExponential(4);
      }
      return value.toFixed(4);
    }
    return value;
  };

  if (metrics.length === 0) {
    return (
      <div className="metrics-table">
        <div className="metrics-empty">
          <p>No metrics available</p>
        </div>
      </div>
    );
  }

  return (
    <div className="metrics-table">
      <div className="metrics-controls">
        <button
          className="btn-download"
          onClick={downloadCSV}
          disabled={downloading}
        >
          Download CSV
        </button>
        <button
          className="btn-download"
          onClick={downloadJSON}
          disabled={downloading}
        >
          {downloading ? 'Downloading...' : 'Download JSON'}
        </button>
      </div>

      <div className="metrics-table-wrapper">
        <table>
          <thead>
            <tr>
              <th onClick={() => handleSort('case_id')}>
                Case ID{renderSortIndicator('case_id')}
              </th>
              <th>Params</th>
              <th onClick={() => handleSort('final_residual')}>
                Final Residual{renderSortIndicator('final_residual')}
              </th>
              <th onClick={() => handleSort('execution_time')}>
                Execution Time{renderSortIndicator('execution_time')}
              </th>
              <th onClick={() => handleSort('openfoam_version')}>
                OpenFOAM Version{renderSortIndicator('openfoam_version')}
              </th>
              <th onClick={() => handleSort('diff_percent')}>
                Diff%{renderSortIndicator('diff_percent')}
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedMetrics.map((row) => {
              const isReference = row.case_id === referenceCaseId;
              const hasHighDiff = row.diff_percent !== undefined && row.diff_percent > 10;

              return (
                <tr
                  key={row.case_id}
                  className={isReference ? 'row-reference' : ''}
                >
                  <td className="cell-case-id">
                    {isReference && <span className="ref-badge">ref</span>}
                    {row.case_id.slice(0, 12)}
                  </td>
                  <td className="cell-params">
                    {Object.entries(JSON.parse(row.params))
                      .map(([k, v]) => `${k}=${v}`)
                      .join(', ')}
                  </td>
                  <td className="cell-number">
                    {formatValue(row.final_residual)}
                  </td>
                  <td className="cell-number">
                    {row.execution_time !== undefined
                      ? `${row.execution_time.toFixed(2)}s`
                      : '—'}
                  </td>
                  <td>{row.openfoam_version || '—'}</td>
                  <td
                    className={`cell-diff ${hasHighDiff ? 'diff-high' : ''}`}
                  >
                    {row.diff_percent !== undefined
                      ? `${row.diff_percent.toFixed(2)}%`
                      : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
