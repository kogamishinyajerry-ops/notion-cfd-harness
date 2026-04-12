/**
 * ConvergenceOverlay - Multi-case convergence residual plot
 *
 * Recharts LineChart with logarithmic Y-axis showing convergence history
 * for multiple cases simultaneously. Each case is a separate series.
 */

import { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { ConvergencePoint } from '../services/types';
import './ConvergenceOverlay.css';

// 8-case palette from UI-SPEC
const CASE_COLORS = [
  '#3B82F6', // blue
  '#10B981', // emerald
  '#F59E0B', // amber
  '#EF4444', // red
  '#8B5CF6', // violet
  '#EC4899', // pink
  '#06B6D4', // cyan
  '#84CC16', // lime
];

interface ConvergenceOverlayProps {
  convergenceData: Record<string, ConvergencePoint[]>;
  caseIds: string[];
}

interface ChartDataPoint {
  iteration: number;
  [key: string]: number | undefined;
}

// Format scientific notation for tooltips
const formatTooltipValue = (value: number | undefined): string => {
  if (value === undefined || value === null) return '-';
  if (value === 0) return '0';
  return value.toExponential(2);
};

// Custom tooltip component
const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: number;
}) => {
  if (!active || !payload || !payload.length) return null;

  return (
    <div className="convergence-tooltip">
      <p className="tooltip-header">Iteration {label}</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }}>
          {entry.name}: {formatTooltipValue(entry.value)}
        </p>
      ))}
    </div>
  );
};

export default function ConvergenceOverlay({
  convergenceData,
  caseIds,
}: ConvergenceOverlayProps) {
  const [visibleCases, setVisibleCases] = useState<Set<string>>(
    new Set(caseIds)
  );
  const [selectedField, setSelectedField] = useState<'Ux' | 'Uy' | 'Uz' | 'p'>(
    'Ux'
  );

  // Merge convergence data into chart format
  const chartData = useMemo(() => {
    const dataMap = new Map<number, ChartDataPoint>();

    caseIds.forEach((caseId) => {
      const caseData = convergenceData[caseId] || [];
      caseData.forEach((point) => {
        const iteration = point.iteration;
        const existing = dataMap.get(iteration) || { iteration };
        existing[`${caseId}_${selectedField}`] = point[selectedField];
        dataMap.set(iteration, existing);
      });
    });

    return Array.from(dataMap.values()).sort((a, b) => a.iteration - b.iteration);
  }, [convergenceData, caseIds, selectedField]);

  // Toggle case visibility
  const handleLegendClick = (dataKey: string) => {
    const caseId = dataKey.replace(`_${selectedField}`, '');
    setVisibleCases((prev) => {
      const next = new Set(prev);
      if (next.has(caseId)) {
        next.delete(caseId);
      } else {
        next.add(caseId);
      }
      return next;
    });
  };

  // Legend formatter
  const formatLegend = (value: string) => {
    const caseId = value.replace(`_${selectedField}`, '');
    return caseId.slice(0, 8);
  };

  if (!convergenceData || caseIds.length === 0) {
    return (
      <div className="convergence-empty">
        <p>No convergence data available</p>
      </div>
    );
  }

  return (
    <div className="convergence-overlay">
      <div className="convergence-controls">
        <div className="field-selector">
          <label>Field:</label>
          <select
            value={selectedField}
            onChange={(e) =>
              setSelectedField(e.target.value as 'Ux' | 'Uy' | 'Uz' | 'p')
            }
          >
            <option value="Ux">Ux (Velocity X)</option>
            <option value="Uy">Uy (Velocity Y)</option>
            <option value="Uz">Uz (Velocity Z)</option>
            <option value="p">p (Pressure)</option>
          </select>
        </div>
      </div>

      <div className="convergence-chart">
        <ResponsiveContainer width="100%" height={400}>
          <LineChart
            data={chartData}
            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="iteration"
              label={{ value: 'Iteration', position: 'bottom', offset: 0 }}
              tick={{ fontSize: 12 }}
            />
            <YAxis
              type="number"
              scale="log"
              domain={['auto', 'auto']}
              tickFormatter={(value) => value.toExponential(0)}
              label={{ value: selectedField, angle: -90, position: 'insideLeft' }}
              tick={{ fontSize: 11 }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              formatter={formatLegend}
              onClick={(e) => handleLegendClick(e.dataKey)}
            />
            {caseIds.map((caseId, index) => (
              <Line
                key={caseId}
                type="monotone"
                dataKey={`${caseId}_${selectedField}`}
                name={`${caseId}_${selectedField}`}
                stroke={CASE_COLORS[index % CASE_COLORS.length]}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
                hide={!visibleCases.has(caseId)}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="convergence-legend-custom">
        <span className="legend-hint">Click legend to toggle series</span>
      </div>
    </div>
  );
}
