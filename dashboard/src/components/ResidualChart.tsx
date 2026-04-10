/**
 * ResidualChart - Real-time convergence residual plot component
 *
 * Displays Ux, Uy, Uz, p residuals as separate colored lines using Recharts.
 * Maintains a 500-point sliding window (FIFO) and uses log-scale Y-axis.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import wsService, { ResidualMessage } from '../services/websocket';
import './ResidualChart.css';

interface ResidualChartProps {
  jobId: string;
  onClose?: () => void;
}

interface ResidualDataPoint {
  iteration: number;
  time: number;
  Ux?: number;
  Uy?: number;
  Uz?: number;
  p?: number;
}

const MAX_DATA_POINTS = 500;

// Custom tooltip formatter for scientific notation
const formatTooltipValue = (value: number | undefined): string => {
  if (value === undefined || value === null) return '-';
  if (value === 0) return '0';
  return value.toExponential(2);
};

// Custom Y-axis tick formatter for scientific notation
const formatYTick = (value: number): string => {
  if (value === 0) return '0';
  return value.toExponential(0);
};

export default function ResidualChart({ jobId, onClose }: ResidualChartProps) {
  const [residualData, setResidualData] = useState<ResidualDataPoint[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const dataRef = useRef<ResidualDataPoint[]>([]);

  // Handle incoming residual messages
  const handleResidualMessage = useCallback((message: ResidualMessage) => {
    if (message.type !== 'residual') return;

    // Parse all residual values as numbers (T-13-01: prevent XSS)
    const newPoint: ResidualDataPoint = {
      iteration: Number(message.iteration) || 0,
      time: Number(message.time_value) || 0,
    };

    // Extract residual values safely
    const residuals = message.residuals || {};
    if (residuals.Ux !== undefined) newPoint.Ux = Number(residuals.Ux);
    if (residuals.Uy !== undefined) newPoint.Uy = Number(residuals.Uy);
    if (residuals.Uz !== undefined) newPoint.Uz = Number(residuals.Uz);
    if (residuals.p !== undefined) newPoint.p = Number(residuals.p);

    // Maintain 500-point sliding window (T-13-03: prevent DoS)
    dataRef.current = [...dataRef.current, newPoint].slice(-MAX_DATA_POINTS);
    setResidualData([...dataRef.current]);
  }, []);

  // Connect to WebSocket and subscribe to residual messages
  useEffect(() => {
    // Connect to the job's WebSocket channel
    wsService.connect(jobId);
    setIsConnected(true);

    // Subscribe to residual messages
    const unsubscribe = wsService.subscribe(jobId, (message) => {
      if (message.type === 'residual') {
        handleResidualMessage(message as ResidualMessage);
      }
    });

    // Cleanup on unmount
    return () => {
      unsubscribe();
      wsService.disconnect(jobId);
      setIsConnected(false);
    };
  }, [jobId, handleResidualMessage]);

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: {
    active?: boolean;
    payload?: Array<{ name: string; value: number; color: string }>;
    label?: number;
  }) => {
    if (!active || !payload || !payload.length) return null;

    const dataPoint = residualData.find((d) => d.iteration === label);

    return (
      <div className="residual-tooltip">
        <p className="tooltip-header">Iteration {label}</p>
        {payload.map((entry) => (
          <p key={entry.name} style={{ color: entry.color }}>
            {entry.name}: {formatTooltipValue(entry.value)}
          </p>
        ))}
        {dataPoint && (
          <p className="tooltip-time">Time: {dataPoint.time.toFixed(4)}</p>
        )}
      </div>
    );
  };

  return (
    <div className="residual-chart-container">
      <div className="residual-chart-header">
        <h3>Live Convergence Chart</h3>
        <div className="residual-chart-controls">
          <div className="connection-status">
            <span
              className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}
            />
            <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
          {onClose && (
            <button className="btn-close" onClick={onClose} aria-label="Close chart">
              &times;
            </button>
          )}
        </div>
      </div>

      <div className="chart-area">
        <ResponsiveContainer width="100%" height={400}>
          <LineChart
            data={residualData}
            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <ReferenceLine
              y={1e-5}
              stroke="#f59e0b"
              strokeDasharray="5 5"
              label={{
                value: "Convergence (1e-5)",
                position: "right",
                fill: "#f59e0b",
                fontSize: 10,
              }}
            />
            <XAxis
              dataKey="iteration"
              label={{ value: 'Iteration', position: 'bottom', offset: 0 }}
              tick={{ fontSize: 12 }}
            />
            <YAxis
              type="number"
              scale="log"
              domain={[1e-8, 1e-1]}
              tickFormatter={formatYTick}
              label={{ value: 'Residual', angle: -90, position: 'insideLeft' }}
              tick={{ fontSize: 11 }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              formatter={(value) => <span style={{ color: 'inherit' }}>{value}</span>}
            />
            <Line
              type="monotone"
              dataKey="Ux"
              name="Ux"
              stroke="#ef4444"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="Uy"
              name="Uy"
              stroke="#22c55e"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="Uz"
              name="Uz"
              stroke="#3b82f6"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="p"
              name="p"
              stroke="#a855f7"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-footer">
        <span className="data-points-count">
          {residualData.length} / {MAX_DATA_POINTS} points
        </span>
      </div>
    </div>
  );
}
