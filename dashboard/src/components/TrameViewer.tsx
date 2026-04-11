/**
 * TrameViewer — React iframe viewer that embeds the Vue.js trame 3D viewer.
 * Replaces ParaViewViewer.tsx; communicates exclusively via CFDViewerBridge
 * postMessage (no WebSocket, no ParaView Web protocol).
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { launchVisualizationSession, sendHeartbeat } from '../services/paraview';
import CFDViewerBridge from '../services/CFDViewerBridge';
import AdvancedFilterPanel from './AdvancedFilterPanel';
import './TrameViewer.css';

// =============================================================================
// Types
// =============================================================================

export type ViewerState = 'idle' | 'launching' | 'connected' | 'disconnected' | 'error';

export interface ParaViewViewerProps {
  jobId: string;
  caseDir: string;
  onError?: (reason: string) => void;
  onConnected?: () => void;
}

interface FilterInfo {
  id: string; // UUID hex string from trame backend
  type: 'clip' | 'contour' | 'streamtracer';
  parameters: {
    insideOut?: boolean;
    scalarValue?: number;
    isovalues?: number[];
    integrationDirection?: 'FORWARD' | 'BACKWARD';
    maxSteps?: number;
  };
}
export type { FilterInfo }; // Re-export for AdvancedFilterPanel

// =============================================================================
// Constants
// =============================================================================

const HEARTBEAT_INTERVAL_MS = 60000; // 60s

const COPY = {
  launchCta: 'Launch 3D Viewer',
  initializingHeading: 'Initializing viewer',
  initializingBody: 'Connecting to trame session...',
  disconnectedBanner: 'Connection lost. Reconnecting...',
  emptyState: 'No completed job. 3D visualization is available for completed jobs only.',
  tryAgain: 'Try Again',
} as const;

// =============================================================================
// Component
// =============================================================================

export default function TrameViewer({ jobId, caseDir, onError, onConnected }: ParaViewViewerProps) {
  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const [viewerState, setViewerState] = useState<ViewerState>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [sessionUrl, setSessionUrl] = useState<string>('');
  const [sessionId, setSessionId] = useState<string>('');

  // Field selection
  const [availableFields, setAvailableFields] = useState<string[]>([]);
  const [selectedField, setSelectedField] = useState<string>('');

  // Slice
  const [sliceAxis, setSliceAxis] = useState<'X' | 'Y' | 'Z' | null>(null);
  const [sliceOrigin, setSliceOrigin] = useState<[number, number, number]>([0, 0, 0]);

  // Color preset
  const [colorPreset, setColorPreset] = useState<'Viridis' | 'BlueRed' | 'Grayscale'>('Viridis');

  // Scalar range
  const [scalarRangeMode, setScalarRangeMode] = useState<'auto' | 'manual'>('auto');
  const [scalarMin, setScalarMin] = useState<number>(0);
  const [scalarMax, setScalarMax] = useState<number>(1);

  // Scalar bar
  const [showScalarBar, setShowScalarBar] = useState<boolean>(true);

  // Volume
  const [volumeEnabled, setVolumeEnabled] = useState<boolean>(false);
  const [volumeWarning, setVolumeWarning] = useState<string | null>(null);

  // Screenshot
  const [screenshotCapturing, setScreenshotCapturing] = useState<boolean>(false);

  // Filters
  const [activeFilters, setActiveFilters] = useState<FilterInfo[]>([]);

  // Time steps
  const [availableTimeSteps, setAvailableTimeSteps] = useState<number[]>([0, 1, 2, 3, 4]);
  const [currentTimeStepIndex, setCurrentTimeStepIndex] = useState<number>(0);

  // Camera
  const [cameraPosition, setCameraPosition] = useState<[number, number, number] | null>(null);
  const [cameraFocalPoint, setCameraFocalPoint] = useState<[number, number, number] | null>(null);

  // ---------------------------------------------------------------------------
  // Refs
  // ---------------------------------------------------------------------------
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const bridgeRef = useRef<CFDViewerBridge | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const screenshotTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  // ---------------------------------------------------------------------------
  // Bridge lifecycle
  // ---------------------------------------------------------------------------
  const handleBridgeMessage = useCallback((msg: import('../services/CFDViewerBridge').BridgeInboundMessage) => {
    switch (msg.type) {
      case 'ready':
        setViewerState('connected');
        onConnected?.();
        break;

      case 'fields':
        setAvailableFields(msg.fields);
        if (!selectedField && msg.fields.length > 0) {
          setSelectedField(msg.fields[0]);
        }
        break;

      case 'volume_status': {
        setVolumeEnabled(msg.enabled);
        const warnings: string[] = [];
        if (!msg.gpu_available && msg.gpu_vendor === 'Mesa') {
          warnings.push('Apple Silicon detected: volume rendering uses Mesa software (slow). Enable GPU for hardware acceleration.');
        }
        if (msg.gpu_vendor === 'unknown' && !msg.gpu_available) {
          warnings.push('No GPU detected: volume rendering unavailable.');
        }
        if (msg.cell_count_warning) {
          warnings.push(`Large dataset (${(msg.cell_count / 1e6).toFixed(1)}M cells): may cause memory issues.`);
        }
        setVolumeWarning(warnings.length > 0 ? warnings.join(' ') : null);
        break;
      }

      case 'filter_response':
        if (msg.success && msg.filterId) {
          // filter added; list will be refreshed via filter_list
        }
        break;

      case 'filter_list':
        setActiveFilters(
          msg.filters.map((f) => ({
            id: f.id,
            type: f.type as 'clip' | 'contour' | 'streamtracer',
            parameters: f.parameters as FilterInfo['parameters'],
          }))
        );
        break;

      case 'screenshot_data': {
        const base64Data = msg.image;
        if (base64Data) {
          const byteString = atob(base64Data);
          const ab = new ArrayBuffer(byteString.length);
          const ia = new Uint8Array(ab);
          for (let i = 0; i < byteString.length; i++) {
            ia[i] = byteString.charCodeAt(i);
          }
          const blob = new Blob([ab], { type: 'image/png' });
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
          link.download = `cfd-screenshot-${timestamp}.png`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(url);
        }
        if (screenshotTimeoutRef.current) {
          clearTimeout(screenshotTimeoutRef.current);
        }
        screenshotTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) setScreenshotCapturing(false);
          screenshotTimeoutRef.current = null;
        }, 500);
        break;
      }

      case 'camera':
        setCameraPosition(msg.position);
        setCameraFocalPoint(msg.focalPoint);
        break;
    }
  }, [onConnected, selectedField]);

  // Create/destroy bridge when iframe becomes available
  useEffect(() => {
    if (!iframeRef.current) return;

    const bridge = new CFDViewerBridge(iframeRef.current);
    bridgeRef.current = bridge;

    const unsubscribe = bridge.onMessage(handleBridgeMessage);

    return () => {
      unsubscribe();
      bridge.destroy();
      bridgeRef.current = null;
    };
  }, [handleBridgeMessage, sessionUrl]);

  // ---------------------------------------------------------------------------
  // Heartbeat
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!sessionId) return;
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);

    heartbeatRef.current = setInterval(async () => {
      try {
        await sendHeartbeat(sessionId);
      } catch (err) {
        console.warn('[TrameViewer] heartbeat failed:', err);
      }
    }, HEARTBEAT_INTERVAL_MS);

    return () => {
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    };
  }, [sessionId]);

  // ---------------------------------------------------------------------------
  // Cleanup on unmount
  // ---------------------------------------------------------------------------
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
      if (screenshotTimeoutRef.current) clearTimeout(screenshotTimeoutRef.current);
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Launch session
  // ---------------------------------------------------------------------------
  const handleLaunch = useCallback(async () => {
    setViewerState('launching');
    setErrorMessage('');
    try {
      const result = await launchVisualizationSession(jobId, caseDir);
      setSessionUrl(result.session_url);
      setSessionId(result.session_id);
      setViewerState('idle'); // iframe not yet loaded
      // Heartbeat started via useEffect once sessionId is set
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Launch failed');
      setViewerState('error');
      if (onError) onError(err instanceof Error ? err.message : 'Launch failed');
    }
  }, [jobId, caseDir, onError]);

  // ---------------------------------------------------------------------------
  // Retry
  // ---------------------------------------------------------------------------
  const handleRetry = useCallback(() => {
    setViewerState('idle');
    setErrorMessage('');
    handleLaunch();
  }, [handleLaunch]);

  // ---------------------------------------------------------------------------
  // Control handlers
  // ---------------------------------------------------------------------------
  const handleFieldChange = useCallback((field: string) => {
    setSelectedField(field);
    bridgeRef.current?.send({ type: 'field', field });
  }, []);

  const handleSliceAxis = useCallback((axis: 'X' | 'Y' | 'Z') => {
    setSliceAxis(axis);
    bridgeRef.current?.send({ type: 'slice', axis, origin: sliceOrigin });
  }, [sliceOrigin]);

  const handleSliceOff = useCallback(() => {
    setSliceAxis(null);
    bridgeRef.current?.send({ type: 'slice_off' });
  }, []);

  const handleColorPreset = useCallback((preset: 'Viridis' | 'BlueRed' | 'Grayscale') => {
    setColorPreset(preset);
    bridgeRef.current?.send({ type: 'color_preset', preset });
  }, []);

  const handleScalarRange = useCallback((mode: 'auto' | 'manual', min?: number, max?: number) => {
    setScalarRangeMode(mode);
    bridgeRef.current?.send({ type: 'scalar_range', mode, min, max });
  }, []);

  const handleVolumeToggle = useCallback((enabled: boolean) => {
    setVolumeEnabled(enabled);
    bridgeRef.current?.send({ type: 'volume_toggle', enabled });
  }, []);

  const handleTimestep = useCallback((index: number) => {
    setCurrentTimeStepIndex(index);
    bridgeRef.current?.send({ type: 'timestep', index });
  }, []);

  const handleScreenshot = useCallback(() => {
    if (screenshotCapturing || screenshotTimeoutRef.current) return;
    setScreenshotCapturing(true);
    const viewportEl = document.getElementById('trame-viewport');
    if (!viewportEl) {
      setScreenshotCapturing(false);
      return;
    }
    const { offsetWidth, offsetHeight } = viewportEl;
    bridgeRef.current?.send({ type: 'screenshot', width: offsetWidth, height: offsetHeight });
  }, [screenshotCapturing]);

  // ---------------------------------------------------------------------------
  // Direct filter handlers — no more paraviewProtocol / bridgeSend wrapper
  // ---------------------------------------------------------------------------
  const handleCreateClip = useCallback((insideOut: boolean, scalarValue: number) => {
    bridgeRef.current?.send({ type: 'clip_create', insideOut, scalarValue });
  }, []);

  const handleCreateContour = useCallback((isovalues: number[]) => {
    bridgeRef.current?.send({ type: 'contour_create', isovalues });
  }, []);

  const handleCreateStreamTracer = useCallback((direction: 'FORWARD' | 'BACKWARD', maxSteps: number) => {
    bridgeRef.current?.send({ type: 'streamtracer_create', direction, maxSteps });
  }, []);

  const handleDeleteFilter = useCallback((filterId: string) => {
    bridgeRef.current?.send({ type: 'filter_delete', filterId });
  }, []);

  // ---------------------------------------------------------------------------
  // Slice origin change
  // ---------------------------------------------------------------------------
  const handleSliceOriginChange = useCallback(
    (val: number) => {
      const newOrigin: [number, number, number] = [val, 0, 0];
      setSliceOrigin(newOrigin);
      if (sliceAxis) {
        bridgeRef.current?.send({ type: 'slice', axis: sliceAxis, origin: newOrigin });
      }
    },
    [sliceAxis]
  );

  // ---------------------------------------------------------------------------
  // Iframe onLoad
  // ---------------------------------------------------------------------------
  const handleIframeLoad = useCallback(() => {
    setViewerState('connected');
    // Request initial state from Vue
    bridgeRef.current?.send({ type: 'volume_status' });
    bridgeRef.current?.send({ type: 'filter_list' });
  }, []);

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------
  const renderIdleState = () => (
    <div className="viewer-idle">
      <button className="viewer-launch-btn" onClick={handleLaunch}>
        {COPY.launchCta}
      </button>
    </div>
  );

  const renderLaunchingState = () => (
    <div className="viewer-launching">
      <div className="viewer-spinner" />
      <p className="viewer-status">{COPY.initializingHeading}</p>
    </div>
  );

  const renderErrorState = () => (
    <div className="viewer-error">
      <p className="error-message">{errorMessage}</p>
      <button className="viewer-retry-btn" onClick={handleRetry}>
        {COPY.tryAgain}
      </button>
    </div>
  );

  const renderScreenshotButton = () => (
    <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 10 }}>
      <button
        className="screenshot-btn"
        disabled={screenshotCapturing}
        onClick={handleScreenshot}
        title="Capture viewport as PNG"
      >
        {screenshotCapturing ? <span className="screenshot-spinner" /> : 'Screenshot'}
      </button>
    </div>
  );

  const renderFieldSelector = () => {
    const fields = availableFields.length > 0 ? availableFields : [
      'U (Velocity)', 'p (Pressure)', 'Ux', 'Uy', 'Uz', 'k (Turbulent Kinetic Energy)', 'epsilon (Dissipation Rate)',
    ];
    return (
      <div className="field-selector">
        <label className="selector-label">Field</label>
        <select
          className="field-select"
          value={selectedField}
          disabled={availableFields.length === 0}
          onChange={(e) => handleFieldChange(e.target.value)}
        >
          {!selectedField && <option value="">Select field...</option>}
          {fields.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </div>
    );
  };

  const renderSliceControls = () => (
    <div className="slice-controls">
      <div className="slice-row">
        <label className="selector-label">Slice</label>
        <div className="axis-buttons">
          {(['X', 'Y', 'Z'] as const).map((axis) => (
            <button
              key={axis}
              className={`axis-btn ${sliceAxis === axis ? 'active' : ''}`}
              onClick={() => handleSliceAxis(axis)}
            >
              {axis}
            </button>
          ))}
          <button
            className={`axis-btn ${sliceAxis === null ? 'active' : ''}`}
            onClick={handleSliceOff}
          >
            Off
          </button>
        </div>
      </div>
      {sliceAxis !== null && (
        <div className="slice-origin-row">
          <label className="selector-label">Origin</label>
          <input
            type="range"
            className="origin-slider"
            min="-5"
            max="5"
            step="0.1"
            value={sliceOrigin[0]}
            onChange={(e) => handleSliceOriginChange(parseFloat(e.target.value))}
          />
          <span className="origin-value">{sliceOrigin[0].toFixed(1)}</span>
        </div>
      )}
    </div>
  );

  const renderColorPresetControls = () => {
    const presets: Array<'Viridis' | 'BlueRed' | 'Grayscale'> = ['Viridis', 'BlueRed', 'Grayscale'];
    return (
      <div className="color-preset-row">
        <label className="selector-label">Color</label>
        <div className="preset-buttons">
          {presets.map((preset) => (
            <button
              key={preset}
              className={`preset-btn ${colorPreset === preset ? 'active' : ''}`}
              onClick={() => handleColorPreset(preset)}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>
    );
  };

  const renderVolumeControls = () => (
    <div className="volume-controls">
      {volumeWarning && (
        <div className="volume-warning-banner">
          <span className="warning-icon">!</span>
          <span className="warning-text">{volumeWarning}</span>
        </div>
      )}
      <div className="volume-row">
        <label className="selector-label">Volume</label>
        <div className="volume-toggle-wrapper">
          <button
            className={`volume-toggle-btn ${volumeEnabled ? 'active' : ''}`}
            disabled={selectedField === ''}
            onClick={() => handleVolumeToggle(!volumeEnabled)}
          >
            {volumeEnabled ? 'On' : 'Off'}
          </button>
          <span className="volume-hint">
            {volumeEnabled ? 'Volume rendering active' : 'Surface rendering'}
          </span>
        </div>
      </div>
    </div>
  );

  const renderScalarRangeControls = () => (
    <div className="scalar-range-row">
      <label className="selector-label">Range</label>
      <div className="range-mode-toggle">
        <button
          className={`range-btn ${scalarRangeMode === 'auto' ? 'active' : ''}`}
          onClick={() => handleScalarRange('auto')}
        >
          Auto
        </button>
        <button
          className={`range-btn ${scalarRangeMode === 'manual' ? 'active' : ''}`}
          onClick={() => handleScalarRange('manual', scalarMin, scalarMax)}
        >
          Manual
        </button>
      </div>
      {scalarRangeMode === 'manual' && (
        <div className="manual-range-inputs">
          <input
            type="number"
            className="range-input"
            value={scalarMin}
            onChange={(e) => handleScalarRange('manual', parseFloat(e.target.value), scalarMax)}
            placeholder="Min"
          />
          <span className="range-separator">—</span>
          <input
            type="number"
            className="range-input"
            value={scalarMax}
            onChange={(e) => handleScalarRange('manual', scalarMin, parseFloat(e.target.value))}
            placeholder="Max"
          />
        </div>
      )}
    </div>
  );

  const renderTimeStepNavigator = () => {
    const total = availableTimeSteps.length;
    return (
      <div className="timestep-navigator">
        <button
          className="timestep-btn timestep-prev"
          disabled={currentTimeStepIndex === 0}
          onClick={() => handleTimestep(currentTimeStepIndex - 1)}
        >
          Previous
        </button>
        <span className="timestep-display">
          {total > 0 ? `Step ${currentTimeStepIndex + 1} / ${total}` : 'No time steps'}
        </span>
        <button
          className="timestep-btn timestep-next"
          disabled={currentTimeStepIndex >= total - 1}
          onClick={() => handleTimestep(currentTimeStepIndex + 1)}
        >
          Next
        </button>
      </div>
    );
  };

  const renderConnectedState = () => (
    <div className="viewer-canvas-container" style={{ position: 'relative' }}>
      {renderScreenshotButton()}
      {renderFieldSelector()}
      {renderSliceControls()}
      {renderColorPresetControls()}
      {renderVolumeControls()}
      <AdvancedFilterPanel
        activeFilters={activeFilters}
        selectedField={selectedField}
        onFiltersChange={setActiveFilters}
        onCreateClip={handleCreateClip}
        onCreateContour={handleCreateContour}
        onCreateStreamTracer={handleCreateStreamTracer}
        onDeleteFilter={handleDeleteFilter}
      />
      {renderScalarRangeControls()}
      {renderTimeStepNavigator()}
      <div
        id="trame-viewport"
        className="paraview-viewport"
        style={{ flex: 1, width: '100%', height: '100%', background: 'var(--bg-primary)' }}
      >
        {sessionUrl && (
          <iframe
            ref={iframeRef}
            src={sessionUrl}
            style={{ width: '100%', height: '100%', border: 'none' }}
            onLoad={handleIframeLoad}
          />
        )}
      </div>
    </div>
  );

  // ---------------------------------------------------------------------------
  // Main render — delegate to state renderers
  // ---------------------------------------------------------------------------
  const renderContent = () => {
    switch (viewerState) {
      case 'idle':
        return renderIdleState();
      case 'launching':
        return renderLaunchingState();
      case 'connected':
        return renderConnectedState();
      case 'error':
        return renderErrorState();
      default:
        return renderIdleState();
    }
  };

  return (
    <div className="paraview-viewer">
      {renderContent()}
    </div>
  );
}
