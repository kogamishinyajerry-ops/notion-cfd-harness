/**
 * GeometryPreview Component - SVG-based 2D visualization of geometry
 * Renders a top-down view of the computational domain
 */

import type { GeometrySpec } from '../services/caseTypes';

interface GeometryPreviewProps {
  geometry: GeometrySpec;
  width?: number;
  height?: number;
}

const PADDING = 40;

export default function GeometryPreview({
  geometry,
  width = 400,
  height = 300,
}: GeometryPreviewProps) {
  const drawWidth = width - PADDING * 2;
  const drawHeight = height - PADDING * 2;

  // Calculate scale to fit domain in view
  const domainWidth = geometry.x_max - geometry.x_min;
  const domainHeight = geometry.y_max - geometry.y_min;
  const scale = Math.min(drawWidth / domainWidth, drawHeight / domainHeight) * 0.9;

  // Center offset
  const offsetX = PADDING + (drawWidth - domainWidth * scale) / 2;
  const offsetY = PADDING + (drawHeight - domainHeight * scale) / 2;

  // Convert domain coords to SVG coords
  const toSvgX = (x: number) => offsetX + (x - geometry.x_min) * scale;
  const toSvgY = (y: number) => offsetY + (geometry.y_max - y) * scale;

  // Domain rectangle
  const x = toSvgX(geometry.x_min);
  const y = toSvgY(geometry.y_max);
  const w = domainWidth * scale;
  const h = domainHeight * scale;

  const renderSimpleGrid = () => (
    <g className="geometry-simple-grid">
      {/* Main domain */}
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        className="domain-rect"
      />
      {/* Grid lines */}
      <line x1={toSvgX(geometry.x_min + domainWidth * 0.25)} y1={y} x2={toSvgX(geometry.x_min + domainWidth * 0.25)} y2={y + h} className="grid-line" />
      <line x1={toSvgX(geometry.x_min + domainWidth * 0.5)} y1={y} x2={toSvgX(geometry.x_min + domainWidth * 0.5)} y2={y + h} className="grid-line" />
      <line x1={toSvgX(geometry.x_min + domainWidth * 0.75)} y1={y} x2={toSvgX(geometry.x_min + domainWidth * 0.75)} y2={y + h} className="grid-line" />
      <line x1={x} y1={toSvgY(geometry.y_min + domainHeight * 0.25)} x2={x + w} y2={toSvgY(geometry.y_min + domainHeight * 0.25)} className="grid-line" />
      <line x1={x} y1={toSvgY(geometry.y_min + domainHeight * 0.5)} x2={x + w} y2={toSvgY(geometry.y_min + domainHeight * 0.5)} className="grid-line" />
      <line x1={x} y1={toSvgY(geometry.y_min + domainHeight * 0.75)} x2={x + w} y2={toSvgY(geometry.y_min + domainHeight * 0.75)} className="grid-line" />
      {/* Labels */}
      <text x={x} y={y - 5} className="axis-label">Ymax</text>
      <text x={x} y={y + h + 15} className="axis-label">Ymin</text>
      <text x={x - 5} y={y + h / 2} className="axis-label" textAnchor="end">Xmin</text>
      <text x={x + w + 5} y={y + h / 2} className="axis-label">Xmax</text>
    </g>
  );

  const renderBackwardFacingStep = () => {
    const stepX = geometry.x_min + 0.4 * domainWidth;
    const stepY = geometry.y_min + 0.5 * domainHeight;

    return (
      <g className="geometry-step">
        {/* Main domain outline */}
        <rect
          x={x}
          y={y}
          width={w}
          height={h}
          className="domain-rect"
        />
        {/* Step indication */}
        <line
          x1={toSvgX(stepX)}
          y1={toSvgY(geometry.y_min)}
          x2={toSvgX(stepX)}
          y2={toSvgY(stepY)}
          className="step-line"
        />
        {/* Inlet label */}
        <text
          x={x - 25}
          y={toSvgY(geometry.y_min + domainHeight * 0.3)}
          className="patch-label"
          textAnchor="middle"
        >
          inlet
        </text>
        <line
          x1={x - 5}
          y1={toSvgY(geometry.y_min + domainHeight * 0.3)}
          x2={x}
          y2={toSvgY(geometry.y_min + domainHeight * 0.3)}
          className="flow-arrow"
        />
        {/* Outlet label */}
        <text
          x={x + w + 25}
          y={y + h / 2}
          className="patch-label"
          textAnchor="middle"
        >
          outlet
        </text>
        <line
          x1={x + w}
          y1={y + h / 2}
          x2={x + w + 5}
          y2={y + h / 2}
          className="flow-arrow"
        />
        {/* Step label */}
        <text
          x={toSvgX(stepX)}
          y={toSvgY(stepY) + 15}
          className="step-label"
          textAnchor="middle"
        >
          step
        </text>
      </g>
    );
  };

  const renderBodyInChannel = () => {
    const bodyXMin = geometry.body_x_min ?? geometry.x_min + 0.3 * domainWidth;
    const bodyXMax = geometry.body_x_max ?? geometry.x_min + 0.7 * domainWidth;
    const bodyYMin = geometry.body_y_min ?? geometry.y_min + 0.3 * domainHeight;
    const bodyYMax = geometry.body_y_max ?? geometry.y_min + 0.7 * domainHeight;

    return (
      <g className="geometry-body-channel">
        {/* Main domain */}
        <rect
          x={x}
          y={y}
          width={w}
          height={h}
          className="domain-rect"
        />
        {/* Body */}
        <rect
          x={toSvgX(bodyXMin)}
          y={toSvgY(bodyYMax)}
          width={(bodyXMax - bodyXMin) * scale}
          height={(bodyYMax - bodyYMin) * scale}
          className="body-rect"
        />
        {/* Channel flow arrows */}
        <line
          x1={x - 5}
          y1={toSvgY(geometry.y_min + domainHeight * 0.5)}
          x2={toSvgX(bodyXMin) - 10}
          y2={toSvgY(geometry.y_min + domainHeight * 0.5)}
          className="flow-arrow"
        />
        <line
          x1={toSvgX(bodyXMax) + 10}
          y1={toSvgY(geometry.y_min + domainHeight * 0.5)}
          x2={x + w + 5}
          y2={toSvgY(geometry.y_min + domainHeight * 0.5)}
          className="flow-arrow"
        />
        {/* Labels */}
        <text x={x - 25} y={toSvgY(geometry.y_min + domainHeight * 0.5)} className="patch-label" textAnchor="middle">inlet</text>
        <text x={x + w + 25} y={toSvgY(geometry.y_min + domainHeight * 0.5)} className="patch-label" textAnchor="middle">outlet</text>
        <text x={(toSvgX(bodyXMin) + toSvgX(bodyXMax)) / 2} y={toSvgY((bodyYMin + bodyYMax) / 2)} className="body-label" textAnchor="middle">body</text>
      </g>
    );
  };

  const renderGeometry = () => {
    switch (geometry.geometry_type) {
      case 'simple_grid':
        return renderSimpleGrid();
      case 'backward_facing_step':
        return renderBackwardFacingStep();
      case 'body_in_channel':
        return renderBodyInChannel();
      default:
        return (
          <rect x={x} y={y} width={w} height={h} className="domain-rect" />
        );
    }
  };

  return (
    <div className="geometry-preview">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="preview-svg"
      >
        <defs>
          <pattern id="grid-pattern" width="10" height="10" patternUnits="userSpaceOnUse">
            <path d="M 10 0 L 0 0 0 10" fill="none" stroke="var(--color-grid)" strokeWidth="0.5" />
          </pattern>
        </defs>

        {/* Background */}
        <rect
          x={PADDING}
          y={PADDING}
          width={drawWidth}
          height={drawHeight}
          fill="var(--color-preview-bg)"
          className="preview-bg"
        />

        {/* Geometry */}
        {renderGeometry()}

        {/* Axis labels */}
        <text x={width / 2} y={height - 5} className="x-axis-label" textAnchor="middle">
          X
        </text>
        <text x={10} y={height / 2} className="y-axis-label" textAnchor="middle" transform={`rotate(-90, 10, ${height / 2})`}>
          Y
        </text>
      </svg>

      <div className="preview-info">
        <span className="info-label">Domain:</span>
        <span className="info-value">
          [{geometry.x_min}, {geometry.x_max}] x [{geometry.y_min}, {geometry.y_max}]
        </span>
        <span className="info-label">Size:</span>
        <span className="info-value">
          {(domainWidth * 1000).toFixed(1)} x {(domainHeight * 1000).toFixed(1)} mm
        </span>
      </div>
    </div>
  );
}
