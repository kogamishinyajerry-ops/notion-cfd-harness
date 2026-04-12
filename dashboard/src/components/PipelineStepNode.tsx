import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { PipelineStep } from '../services/types';

interface PipelineStepNodeData {
  step: PipelineStep;
  isStale: boolean;
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

export default function PipelineStepNode({ data, selected }: NodeProps) {
  const { step, isStale } = data as PipelineStepNodeData;

  const statusClass = `status-${step.status.toLowerCase()}`;
  const duration = formatDuration(step.started_at, step.completed_at);

  return (
    <div className={`pipeline-step-node ${statusClass}${selected ? ' selected' : ''}`}>
      {/* Top handle for incoming edges */}
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: 'var(--border-color)' }}
      />

      <div className="node-header">
        <span className="node-step-id" title={step.id}>{step.id}</span>
        <span className="node-step-type-badge">{step.step_type}</span>
      </div>

      <div className="node-footer">
        <span className="node-status-text">{step.status}</span>
        <span className="node-duration">{duration}</span>
      </div>

      {/* Warning badge for stale RUNNING steps */}
      {isStale && (
        <div className="node-warning-badge" title="Step exceeds expected duration">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M5 1L9 9H1L5 1Z" fill="currentColor"/>
            <rect x="4.5" y="4" width="1" height="2.5" rx="0.5" fill="currentColor"/>
            <rect x="4.5" y="7" width="1" height="1" rx="0.5" fill="currentColor"/>
          </svg>
        </div>
      )}

      {/* Bottom handle for outgoing edges */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: 'var(--border-color)' }}
      />
    </div>
  );
}
