/**
 * ResultSummaryPanel - Post-convergence result summary component
 *
 * Displays final residuals, execution metrics, and Y+ placeholder.
 * Per MON-04: Display result summary (pressure, velocity, Y+) on convergence.
 * Note: Y+ requires OpenFOAM yPlus utility post-processing (Phase 15+).
 */

import React from 'react';
import './ResultSummaryPanel.css';

interface ResultSummaryPanelProps {
  /** Final iteration count */
  iteration: number;
  /** Execution time in seconds */
  executionTime: number;
  /** Case identifier */
  caseId?: string;
  /** Solver name */
  solver?: string;
  /** Final residual values */
  finalResiduals?: {
    Ux?: number;
    Uy?: number;
    Uz?: number;
    p?: number;
  };
  /** Optional close handler */
  onClose?: () => void;
}

/**
 * Formats a number in scientific notation with 4 decimal places.
 * Displays '-' if value is undefined or null.
 */
const formatSci = (v?: number): string => {
  if (v === undefined || v === null) return '-';
  return v.toExponential(4);
};

export default function ResultSummaryPanel({
  iteration,
  executionTime,
  caseId,
  solver,
  finalResiduals,
  onClose,
}: ResultSummaryPanelProps) {
  return (
    <div className="result-summary-panel">
      <div className="result-summary-header">
        <h3 className="result-summary-title">
          <svg
            className="check-icon"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              d="M16.6667 5L7.50001 14.1667L3.33334 10"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Simulation Complete
        </h3>
        {onClose && (
          <button className="summary-close" onClick={onClose} type="button" aria-label="Close summary">
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <path
                d="M12 4L4 12M4 4L12 12"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </div>

      <div className="result-summary-grid">
        <div className="summary-item">
          <span className="summary-label">Final Iteration</span>
          <span className="summary-value">{iteration}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Execution Time</span>
          <span className="summary-value">{executionTime.toFixed(1)}s</span>
        </div>
        {caseId && (
          <div className="summary-item">
            <span className="summary-label">Case ID</span>
            <span className="summary-value">{caseId}</span>
          </div>
        )}
        {solver && (
          <div className="summary-item">
            <span className="summary-label">Solver</span>
            <span className="summary-value">{solver}</span>
          </div>
        )}
      </div>

      <div className="result-summary-section">
        <h4 className="section-title">Final Residuals</h4>
        <div className="residual-grid">
          <div className="residual-item">
            <span className="residual-label">Pressure (p)</span>
            <span className="residual-value">{formatSci(finalResiduals?.p)}</span>
          </div>
          <div className="residual-item">
            <span className="residual-label">Velocity X (Ux)</span>
            <span className="residual-value">{formatSci(finalResiduals?.Ux)}</span>
          </div>
          <div className="residual-item">
            <span className="residual-label">Velocity Y (Uy)</span>
            <span className="residual-value">{formatSci(finalResiduals?.Uy)}</span>
          </div>
          <div className="residual-item">
            <span className="residual-label">Velocity Z (Uz)</span>
            <span className="residual-value">{formatSci(finalResiduals?.Uz)}</span>
          </div>
        </div>
      </div>

      <div className="result-summary-section">
        <h4 className="section-title">Wall Y+</h4>
        <p className="y-plus-placeholder">
          Y+ metrics require post-processing via OpenFOAM yPlus utility.
          This feature is planned for Phase 15+.
        </p>
      </div>
    </div>
  );
}
