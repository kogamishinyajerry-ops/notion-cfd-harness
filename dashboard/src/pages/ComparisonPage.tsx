/**
 * ComparisonPage - Cross-case comparison view
 *
 * Two-panel layout: 320px left case selector (multi-select) + right tabbed viewer
 * Tabs: Convergence | Delta Field | Metrics
 */

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../services/api';
import type { SweepCase, ComparisonResponse } from '../services/types';
import ConvergenceOverlay from '../components/ConvergenceOverlay';
import DeltaFieldViewer from '../components/DeltaFieldViewer';
import MetricsTable from '../components/MetricsTable';
import './ComparisonPage.css';

type TabType = 'convergence' | 'delta' | 'metrics';

export default function ComparisonPage() {
  const [sweepCases, setSweepCases] = useState<SweepCase[]>([]);
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<TabType>('convergence');
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch sweep cases on mount
  useEffect(() => {
    const fetchCases = async () => {
      try {
        setLoading(true);
        const cases = await apiClient.getComparisonCases();
        // Filter to completed cases only
        const completedCases = cases.filter(
          (c) => c.status === 'COMPLETED' || c.status === 'completed'
        );
        setSweepCases(completedCases);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load cases');
      } finally {
        setLoading(false);
      }
    };
    fetchCases();
  }, []);

  // Toggle case selection
  const handleCaseToggle = useCallback((caseId: string) => {
    setSelectedCaseIds((prev) =>
      prev.includes(caseId)
        ? prev.filter((id) => id !== caseId)
        : [...prev, caseId]
    );
  }, []);

  // Create new comparison
  const handleCreateComparison = async () => {
    if (selectedCaseIds.length < 2) {
      setError('Please select at least 2 cases to compare');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const refId = selectedCaseIds[0];
      const newComparison = await apiClient.createComparison({
        name: `Comparison ${new Date().toLocaleDateString()}`,
        reference_case_id: refId,
        case_ids: selectedCaseIds,
      });
      setComparison(newComparison);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create comparison');
    } finally {
      setLoading(false);
    }
  };

  // Load existing comparison
  const handleLoadComparison = async (comparisonId: string) => {
    try {
      setLoading(true);
      setError(null);
      const comp = await apiClient.getComparison(comparisonId);
      setComparison(comp);
      setSelectedCaseIds(comp.case_ids);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load comparison');
    } finally {
      setLoading(false);
    }
  };

  // Render case selector
  const renderCaseSelector = () => (
    <div className="case-selector">
      <div className="case-selector-header">
        <h3>Select Cases</h3>
        <span className="case-count">{selectedCaseIds.length} selected</span>
      </div>
      <div className="case-list">
        {loading && sweepCases.length === 0 ? (
          <div className="loading">Loading cases...</div>
        ) : sweepCases.length === 0 ? (
          <div className="empty-state">No completed cases found</div>
        ) : (
          sweepCases.map((caseItem) => (
            <label key={caseItem.id} className="case-item">
              <input
                type="checkbox"
                checked={selectedCaseIds.includes(caseItem.id)}
                onChange={() => handleCaseToggle(caseItem.id)}
              />
              <div className="case-info">
                <span className="case-id">{caseItem.id.slice(0, 8)}</span>
                <span className="case-params">
                  {Object.entries(caseItem.param_combination)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(', ')}
                </span>
              </div>
            </label>
          ))
        )}
      </div>
      <div className="case-selector-footer">
        <button
          className="btn-primary"
          disabled={selectedCaseIds.length < 2 || loading}
          onClick={handleCreateComparison}
        >
          {loading ? 'Creating...' : 'New Comparison'}
        </button>
      </div>
    </div>
  );

  // Render tab bar
  const renderTabBar = () => (
    <div className="tab-bar">
      <button
        className={`tab-btn ${activeTab === 'convergence' ? 'active' : ''}`}
        onClick={() => setActiveTab('convergence')}
      >
        Convergence
      </button>
      <button
        className={`tab-btn ${activeTab === 'delta' ? 'active' : ''}`}
        onClick={() => setActiveTab('delta')}
      >
        Delta Field
      </button>
      <button
        className={`tab-btn ${activeTab === 'metrics' ? 'active' : ''}`}
        onClick={() => setActiveTab('metrics')}
      >
        Metrics
      </button>
    </div>
  );

  // Render tab content
  const renderTabContent = () => {
    if (!comparison) {
      return (
        <div className="empty-state">
          <h3>No Comparison Selected</h3>
          <p>Select cases and click "New Comparison" to begin</p>
        </div>
      );
    }

    switch (activeTab) {
      case 'convergence':
        return (
          <ConvergenceOverlay
            convergenceData={comparison.convergence_data}
            caseIds={comparison.case_ids}
          />
        );
      case 'delta':
        return (
          <DeltaFieldViewer
            comparison={comparison}
            onDeltaSessionCreate={async (_id, _field) => {
              // Handled internally by DeltaFieldViewer
            }}
          />
        );
      case 'metrics':
        return (
          <MetricsTable
            metrics={comparison.metrics_table}
            referenceCaseId={comparison.reference_case_id}
          />
        );
    }
  };

  return (
    <div className="comparison-page">
      {renderCaseSelector()}
      <div className="comparison-viewer">
        <div className="viewer-header">
          <h2>Cross-Case Comparison</h2>
          {error && <div className="error-message">{error}</div>}
        </div>
        {renderTabBar()}
        <div className="tab-content">{renderTabContent()}</div>
      </div>
    </div>
  );
}
