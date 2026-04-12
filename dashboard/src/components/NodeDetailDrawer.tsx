import { useEffect, useRef } from 'react';
import type { PipelineStep } from '../services/types';

interface NodeDetailDrawerProps {
  step: PipelineStep | null;
  onClose: () => void;
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

const STATUS_BADGE_COLOR: Record<string, string> = {
  PENDING: 'var(--color-pending)',
  RUNNING: 'var(--color-running)',
  COMPLETED: 'var(--color-completed)',
  FAILED: 'var(--color-failed)',
  SKIPPED: 'var(--color-skipped)',
};

export default function NodeDetailDrawer({ step, onClose }: NodeDetailDrawerProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose();
  };

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  if (!step) return null;

  const badgeColor = STATUS_BADGE_COLOR[step.status] ?? 'var(--color-pending)';

  return (
    <>
      {/* Overlay */}
      <div className="node-drawer-overlay" ref={overlayRef} onClick={handleOverlayClick} />

      {/* Drawer panel */}
      <div className="node-drawer" role="dialog" aria-label={`Step: ${step.id}`}>
        <div className="node-drawer-header">
          <span className="node-drawer-title">Step: {step.id}</span>
          <button className="node-drawer-close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <div className="node-drawer-body">
          {/* Status */}
          <div className="node-detail-section">
            <span className="node-detail-section-label">Status</span>
            <span
              className="node-detail-badge"
              style={{ background: badgeColor, color: '#fff' }}
            >
              {step.status}
            </span>
          </div>

          {/* Step type */}
          <div className="node-detail-section">
            <span className="node-detail-section-label">Type</span>
            <span className="node-detail-section-value">{step.step_type}</span>
          </div>

          {/* Duration */}
          <div className="node-detail-section">
            <span className="node-detail-section-label">Duration</span>
            <span className="node-detail-section-value">
              {formatDuration(step.started_at, step.completed_at)}
            </span>
          </div>

          {/* Depends on */}
          <div className="node-detail-section">
            <span className="node-detail-section-label">Depends on</span>
            <span className="node-detail-section-value">
              {step.depends_on.length > 0 ? step.depends_on.join(', ') : 'none'}
            </span>
          </div>

          {/* Parameters */}
          <div className="node-detail-section">
            <span className="node-detail-section-label">Parameters</span>
            <pre className="node-detail-params">
              {JSON.stringify(step.params, null, 2)}
            </pre>
          </div>

          {/* Result summary */}
          {step.result && (
            <div className="node-detail-section">
              <span className="node-detail-section-label">Result</span>
              <div className="node-detail-section-value">
                <div>Status: {step.result.status}</div>
                <div>Exit code: {step.result.exit_code}</div>
                {step.result.validation_checks && (
                  <div>
                    Validation:{' '}
                    {Object.entries(step.result.validation_checks)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(', ')}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Diagnostics */}
          {step.result?.diagnostics && (
            <div className="node-detail-section">
              <span className="node-detail-section-label">Diagnostics</span>
              <pre className="node-detail-diagnostics">
                {JSON.stringify(step.result.diagnostics, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
