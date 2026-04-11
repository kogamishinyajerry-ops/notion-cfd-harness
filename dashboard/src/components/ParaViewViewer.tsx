import { useState, useEffect, useRef, useCallback } from 'react';
import { launchVisualizationSession, sendHeartbeat } from '../services/paraview';
import {
  createOpenFOAMReaderMessage,
  createGetFieldsMessage,
  createFieldDisplayMessage,
  createGetTimeStepsMessage,
  createTimeStepMessage,
  createRenderMessage,
  parseAvailableFields,
  parseAvailableTimeSteps,
  createSliceMessage,
  createColorPresetMessage,
  createScalarRangeMessage,
  createScalarBarMessage,
  createVolumeRenderingToggle,
  createVolumeRenderingStatus,
  parseVolumeRenderingStatus,
  createScreenshotMessage,
} from '../services/paraviewProtocol';
import './ParaViewViewer.css';

// =============================================================================
// Types
// =============================================================================

export type ViewerState =
  | 'idle'
  | 'launching'
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'reconnect-exhausted'
  | 'error';

export interface ParaViewViewerProps {
  jobId: string;
  caseDir: string;
  onError?: (reason: string) => void;
  onConnected?: () => void;
}

interface ConnectionResult {
  sessionId: string;
  sessionUrl: string;
  authKey: string;
  port: number;
}

// =============================================================================
// State machine constants
// =============================================================================

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000]; // ms
const MAX_RECONNECT_ATTEMPTS = 5;
const HEARTBEAT_INTERVAL_MS = 60000; // 60s

// =============================================================================
// Copying strings from UI-SPEC
// =============================================================================

const COPY = {
  launchCta: 'Launch 3D Viewer',
  initializingHeading: 'Initializing viewer',
  initializingBody: 'Connecting to ParaView Web session...',
  errorConnectionRefused: (port: number) =>
    `Cannot connect to ParaView Web. Ensure Docker is running and port ${port} is available.`,
  errorAuthFailed:
    'Authentication failed. The session may have expired. Refresh to try again.',
  errorSessionNotFound:
    'Session not found. The viewer session may have timed out (30 min idle). Refresh to launch a new session.',
  disconnectedBanner: 'Connection lost. Reconnecting...',
  reconnectExhausted: (n: number) => `Viewer disconnected after ${n} attempts.`,
  emptyState: 'No completed job. 3D visualization is available for completed jobs only.',
  tryAgain: 'Try Again',
} as const;

// =============================================================================
// Component
// =============================================================================

export default function ParaViewViewer({ jobId, caseDir, onError, onConnected }: ParaViewViewerProps) {
  const [state, setState] = useState<ViewerState>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [sessionInfo, setSessionInfo] = useState<ConnectionResult | null>(null);

  // Field selection state
  const [availableFields, setAvailableFields] = useState<string[]>([]);
  const [selectedField, setSelectedField] = useState<string>('');

  // Time step navigation state
  const [availableTimeSteps, setAvailableTimeSteps] = useState<number[]>([0, 1, 2, 3, 4]);
  const [currentTimeStepIndex, setCurrentTimeStepIndex] = useState<number>(0);

  // Slice filter state (PV-04.3)
  const [sliceAxis, setSliceAxis] = useState<'X' | 'Y' | 'Z' | null>(null);
  const [sliceOrigin, setSliceOrigin] = useState<[number, number, number]>([0, 0, 0]);

  // Color preset state (PV-04.4)
  const [colorPreset, setColorPreset] = useState<'Viridis' | 'BlueRed' | 'Grayscale'>('Viridis');

  // Scalar range state (PV-04.6)
  const [scalarRangeMode, setScalarRangeMode] = useState<'auto' | 'manual'>('auto');
  const [scalarMin, setScalarMin] = useState<number>(0);
  const [scalarMax, setScalarMax] = useState<number>(1);

  // Scalar bar visibility state (PV-04.5)
  const [showScalarBar, setShowScalarBar] = useState<boolean>(true);

  // Volume rendering state (VOL-01.1/01.2/01.3)
  const [volumeEnabled, setVolumeEnabled] = useState<boolean>(false);
  const [volumeWarning, setVolumeWarning] = useState<string | null>(null);

  // Screenshot state (SHOT-01.3/SHOT-01.4)
  const [screenshotCapturing, setScreenshotCapturing] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pvProxyRef = useRef<unknown>(null); // ParaView Web proxy reference
  const screenshotTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // -------------------------------------------------------------------------
  // Cleanup on unmount
  // -------------------------------------------------------------------------
  const cleanup = useCallback(() => {
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    pvProxyRef.current = null;
    if (screenshotTimeoutRef.current) clearTimeout(screenshotTimeoutRef.current);
  }, []);

  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  // -------------------------------------------------------------------------
  // Start heartbeat
  // -------------------------------------------------------------------------
  const startHeartbeat = useCallback((sessionId: string) => {
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    heartbeatRef.current = setInterval(async () => {
      try {
        await sendHeartbeat(sessionId);
      } catch {
        // Non-fatal: swallow heartbeat errors
      }
    }, HEARTBEAT_INTERVAL_MS);
  }, []);

  // -------------------------------------------------------------------------
  // Send protocol message via WebSocket
  // -------------------------------------------------------------------------
  const sendProtocolMessage = useCallback((message: object) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  // -------------------------------------------------------------------------
  // Connect WebSocket
  // -------------------------------------------------------------------------
  const connectWebSocket = useCallback(
    (sessionUrl: string, authKey: string, attempt = 0) => {
      cleanup(); // Clean up any existing connection

      setState('connecting');

      const ws = new WebSocket(sessionUrl);
      wsRef.current = ws;

      const connectionTimeout = setTimeout(() => {
        ws.close();
        if (attempt < MAX_RECONNECT_ATTEMPTS - 1) {
          scheduleReconnect(sessionUrl, authKey, attempt + 1);
        } else {
          setState('reconnect-exhausted');
          setErrorMessage(COPY.reconnectExhausted(MAX_RECONNECT_ATTEMPTS));
        }
      }, 3000); // 3s connection timeout

      ws.onopen = () => {
        clearTimeout(connectionTimeout);
        // Send auth_key as first message per ParaView Web protocol
        ws.send(authKey);
        // After auth, open OpenFOAM reader and discover fields/time steps
        sendProtocolMessage(createOpenFOAMReaderMessage(caseDir));
        sendProtocolMessage(createGetFieldsMessage());
        sendProtocolMessage(createGetTimeStepsMessage());
        sendProtocolMessage(createVolumeRenderingStatus());
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          // Parse available fields response
          if (message.id === 'pv-fields' && message.result) {
            const fields = parseAvailableFields(message);
            if (fields.length > 0) {
              setAvailableFields(fields);
              if (!selectedField && fields.length > 0) {
                setSelectedField(fields[0]);
              }
            }
          }

          // Parse volume rendering status response
          if (message.id === 'pv-volume-status' && message.result) {
            const status = parseVolumeRenderingStatus(message);
            if (status) {
              setVolumeEnabled(status.enabled);
              // Build warning message
              const warnings: string[] = [];
              if (!status.gpu_available && status.gpu_vendor === 'Mesa') {
                warnings.push('Apple Silicon detected: volume rendering uses Mesa software (slow). Enable GPU for hardware acceleration.');
              }
              if (status.gpu_vendor === 'unknown' && !status.gpu_available) {
                warnings.push('No GPU detected: volume rendering unavailable.');
              }
              if (status.cell_count_warning) {
                warnings.push(`Large dataset (${(status.cell_count / 1e6).toFixed(1)}M cells): may cause memory issues.`);
              }
              setVolumeWarning(warnings.length > 0 ? warnings.join(' ') : null);
            }
          }

          // SHOT-01.1: Parse screenshot response and trigger download
          if (message.id === 'pv-screenshot' && message.result) {
            const r = message.result as Record<string, unknown>;
            const base64Data = typeof r.image === 'string' ? r.image : null;
            if (base64Data) {
              // Decode base64 to Blob and trigger download
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
            // SHOT-01.4: Re-enable after 500ms debounce window
            screenshotTimeoutRef.current = setTimeout(() => {
              setScreenshotCapturing(false);
              screenshotTimeoutRef.current = null;
            }, 500);
          }

          // Parse available time steps response
          if (message.id === 'pv-timesteps' && message.result) {
            const timeSteps = parseAvailableTimeSteps(message);
            if (timeSteps.length > 0) {
              setAvailableTimeSteps(timeSteps);
              setCurrentTimeStepIndex(0);
            }
          }
        } catch {
          // Non-JSON messages are normal ParaView Web protocol traffic
        }

        // Connection established check
        if (ws.readyState === WebSocket.OPEN && !pvProxyRef.current) {
          setState('connected');
          setSessionInfo((prev) => prev ? { ...prev, sessionId: prev?.sessionId || '' } : null);
          if (onConnected) onConnected();
        }
      };

      ws.onerror = () => {
        clearTimeout(connectionTimeout);
        // Connection refused or network error
        setErrorMessage(COPY.errorConnectionRefused(parseInt(sessionUrl.split(':')[2]) || 8081));
        setState('error');
        if (onError) onError(errorMessage);
      };

      ws.onclose = (event) => {
        clearTimeout(connectionTimeout);
        if (state !== 'connected' && state !== 'reconnect-exhausted') {
          // Unexpected close during connection or after connected
          if (state === 'connected') {
            setState('disconnected');
            scheduleReconnect(sessionUrl, authKey, 0);
          } else if (attempt < MAX_RECONNECT_ATTEMPTS - 1) {
            scheduleReconnect(sessionUrl, authKey, attempt + 1);
          } else {
            setState('reconnect-exhausted');
            setErrorMessage(COPY.reconnectExhausted(MAX_RECONNECT_ATTEMPTS));
          }
        }
      };
    },
    [cleanup, onConnected, onError, errorMessage, sessionInfo]
  );

  // -------------------------------------------------------------------------
  // Schedule reconnect with backoff
  // -------------------------------------------------------------------------
  const scheduleReconnect = useCallback(
    (sessionUrl: string, authKey: string, attempt: number) => {
      const delay = RECONNECT_DELAYS[attempt] ?? RECONNECT_DELAYS[RECONNECT_DELAYS.length - 1];
      setReconnectAttempt(attempt + 1);
      setState('disconnected');

      reconnectTimeoutRef.current = setTimeout(() => {
        connectWebSocket(sessionUrl, authKey, attempt);
      }, delay);
    },
    [connectWebSocket]
  );

  // -------------------------------------------------------------------------
  // Launch session and connect
  // -------------------------------------------------------------------------
  const handleLaunch = useCallback(async () => {
    setState('launching');
    setErrorMessage('');
    setReconnectAttempt(0);

    try {
      const result = await launchVisualizationSession(jobId, caseDir);
      setSessionInfo({
        sessionId: result.session_id,
        sessionUrl: result.session_url,
        authKey: result.auth_key,
        port: result.port,
      });

      // Start heartbeat for this session
      startHeartbeat(result.session_id);

      // Connect WebSocket
      connectWebSocket(result.session_url, result.auth_key, 0);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to launch session';
      setErrorMessage(msg);
      setState('error');
      if (onError) onError(msg);
    }
  }, [jobId, caseDir, startHeartbeat, connectWebSocket, onError]);

  // -------------------------------------------------------------------------
  // Retry from reconnect-exhausted
  // -------------------------------------------------------------------------
  const handleRetry = useCallback(() => {
    setState('idle');
    setErrorMessage('');
    setReconnectAttempt(0);
    handleLaunch();
  }, [handleLaunch]);

  // SHOT-01.1/SHOT-01.2/SHOT-01.3/SHOT-01.4: Screenshot capture with debounce
  const handleScreenshot = useCallback(() => {
    // SHOT-01.4: Debounce — ignore if already capturing or recently captured
    if (screenshotCapturing) return;
    if (screenshotTimeoutRef.current) return;

    // SHOT-01.3: Disable button immediately (non-blocking UX)
    setScreenshotCapturing(true);

    // SHOT-01.2: Get actual rendered viewport dimensions from the DOM element
    const viewportEl = document.getElementById('paraview-viewport');
    if (!viewportEl) {
      setScreenshotCapturing(false);
      return;
    }
    const { offsetWidth, offsetHeight } = viewportEl;

    // SHOT-01.1: Send viewport.image.render RPC
    sendProtocolMessage(createScreenshotMessage(offsetWidth, offsetHeight));
  }, [screenshotCapturing, sendProtocolMessage]);

  // -------------------------------------------------------------------------
  // Render states
  // -------------------------------------------------------------------------
  const renderContent = () => {
    switch (state) {
      case 'idle':
        return (
          <div className="viewer-idle">
            <button className="viewer-launch-btn" onClick={handleLaunch}>
              {COPY.launchCta}
            </button>
          </div>
        );

      case 'launching':
        return (
          <div className="viewer-launching">
            <div className="viewer-spinner" />
            <p className="viewer-status">{COPY.initializingHeading}</p>
          </div>
        );

      case 'connecting':
        return (
          <div className="viewer-connecting">
            <div className="viewer-skeleton" />
            <p className="viewer-status-heading">{COPY.initializingHeading}</p>
            <p className="viewer-status-body">{COPY.initializingBody}</p>
          </div>
        );

      case 'connected':
        return (
          <div className="viewer-canvas-container" style={{ position: 'relative' }}>
            {renderScreenshotButton()}
            {renderFieldSelector()}
            {renderSliceControls()}
            {renderColorPresetControls()}
            {renderVolumeControls()}
            {renderScalarRangeControls()}
            {renderTimeStepNavigator()}
            <div
              id="paraview-viewport"
              className="paraview-viewport"
              ref={(el) => {
                if (el && sessionInfo && !pvProxyRef.current) {
                  el.setAttribute('data-session-id', sessionInfo.sessionId);
                }
              }}
            />
          </div>
        );

      case 'disconnected':
        return (
          <div className="viewer-disconnected">
            <div className="viewer-disconnected-banner">
              <span className="disconnected-dot" />
              <span>{COPY.disconnectedBanner}</span>
              <span className="reconnect-count">Attempt {reconnectAttempt}/{MAX_RECONNECT_ATTEMPTS}</span>
            </div>
            <div className="viewer-canvas-container">
              <div id="paraview-viewport" className="paraview-viewport" />
            </div>
          </div>
        );

      case 'reconnect-exhausted':
        return (
          <div className="viewer-error">
            <p className="error-message">{errorMessage || COPY.reconnectExhausted(MAX_RECONNECT_ATTEMPTS)}</p>
            <button className="viewer-retry-btn" onClick={handleRetry}>
              {COPY.tryAgain}
            </button>
          </div>
        );

      case 'error':
        return (
          <div className="viewer-error">
            <p className="error-message">{errorMessage}</p>
            <button className="viewer-retry-btn" onClick={handleRetry}>
              {COPY.tryAgain}
            </button>
          </div>
        );
    }
  };

  // -------------------------------------------------------------------------
  // Slice controls (PV-04.3)
  // -------------------------------------------------------------------------
  const renderSliceControls = () => {
    return (
      <div className="slice-controls">
        <div className="slice-row">
          <label className="selector-label">Slice</label>
          <div className="axis-buttons">
            {(['X', 'Y', 'Z'] as const).map((axis) => (
              <button
                key={axis}
                className={`axis-btn ${sliceAxis === axis ? 'active' : ''}`}
                onClick={() => {
                  setSliceAxis(axis);
                  sendProtocolMessage(createSliceMessage(axis, sliceOrigin));
                  sendProtocolMessage(createRenderMessage());
                }}
              >
                {axis}
              </button>
            ))}
            <button
              className={`axis-btn ${sliceAxis === null ? 'active' : ''}`}
              onClick={() => {
                setSliceAxis(null);
                sendProtocolMessage(createRenderMessage());
              }}
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
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                const newOrigin: [number, number, number] = [val, 0, 0];
                setSliceOrigin(newOrigin);
                sendProtocolMessage(createSliceMessage(sliceAxis, newOrigin));
                sendProtocolMessage(createRenderMessage());
              }}
            />
            <span className="origin-value">{sliceOrigin[0].toFixed(1)}</span>
          </div>
        )}
      </div>
    );
  };

  // -------------------------------------------------------------------------
  // Color preset controls (PV-04.4)
  // -------------------------------------------------------------------------
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
              onClick={() => {
                setColorPreset(preset);
                sendProtocolMessage(createColorPresetMessage(preset));
                sendProtocolMessage(createRenderMessage());
              }}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>
    );
  };

  // -------------------------------------------------------------------------
  // Volume rendering controls (VOL-01.1/01.2/01.3)
  // -------------------------------------------------------------------------
  const renderVolumeControls = () => {
    return (
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
              onClick={() => {
                const newEnabled = !volumeEnabled;
                setVolumeEnabled(newEnabled);
                sendProtocolMessage(createVolumeRenderingToggle(selectedField, newEnabled));
                sendProtocolMessage(createRenderMessage());
              }}
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
  };

  // -------------------------------------------------------------------------
  // Screenshot button (SHOT-01.1/SHOT-01.3)
  // -------------------------------------------------------------------------
  const renderScreenshotButton = () => {
    return (
      <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 10 }}>
        <button
          className="screenshot-btn"
          disabled={screenshotCapturing}
          onClick={handleScreenshot}
          title="Capture viewport as PNG"
        >
          {screenshotCapturing ? (
            <span className="screenshot-spinner" />
          ) : (
            'Screenshot'
          )}
        </button>
      </div>
    );
  };

  // -------------------------------------------------------------------------
  // Scalar range controls (PV-04.6)
  // -------------------------------------------------------------------------
  const renderScalarRangeControls = () => {
    return (
      <div className="scalar-range-row">
        <label className="selector-label">Range</label>
        <div className="range-mode-toggle">
          <button
            className={`range-btn ${scalarRangeMode === 'auto' ? 'active' : ''}`}
            onClick={() => {
              setScalarRangeMode('auto');
              sendProtocolMessage(createScalarRangeMessage('auto'));
              sendProtocolMessage(createRenderMessage());
            }}
          >
            Auto
          </button>
          <button
            className={`range-btn ${scalarRangeMode === 'manual' ? 'active' : ''}`}
            onClick={() => {
              setScalarRangeMode('manual');
              sendProtocolMessage(createScalarRangeMessage('manual', scalarMin, scalarMax));
              sendProtocolMessage(createRenderMessage());
            }}
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
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setScalarMin(val);
                sendProtocolMessage(createScalarRangeMessage('manual', val, scalarMax));
                sendProtocolMessage(createRenderMessage());
              }}
              placeholder="Min"
            />
            <span className="range-separator">—</span>
            <input
              type="number"
              className="range-input"
              value={scalarMax}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setScalarMax(val);
                sendProtocolMessage(createScalarRangeMessage('manual', scalarMin, val));
                sendProtocolMessage(createRenderMessage());
              }}
              placeholder="Max"
            />
          </div>
        )}
      </div>
    );
  };

  // -------------------------------------------------------------------------
  // Field selector
  // -------------------------------------------------------------------------
  const renderFieldSelector = () => {
    const fields = availableFields.length > 0 ? availableFields : [
      'U (Velocity)', 'p (Pressure)', 'Ux', 'Uy', 'Uz', 'k (Turbulent Kinetic Energy)', 'epsilon (Dissipation Rate)'
    ];
    return (
      <div className="field-selector">
        <label className="selector-label">Field</label>
        <select
          className="field-select"
          value={selectedField}
          disabled={availableFields.length === 0}
          onChange={(e) => {
            const field = e.target.value;
            setSelectedField(field);
            sendProtocolMessage(createFieldDisplayMessage(field));
            sendProtocolMessage(createRenderMessage());
          }}
        >
          {!selectedField && <option value="">Select field...</option>}
          {fields.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </div>
    );
  };

  // -------------------------------------------------------------------------
  // Time step navigator
  // -------------------------------------------------------------------------
  const renderTimeStepNavigator = () => {
    const total = availableTimeSteps.length;
    const hasTimeSteps = total > 0;
    return (
      <div className="timestep-navigator">
        <button
          className="timestep-btn timestep-prev"
          disabled={currentTimeStepIndex === 0}
          onClick={() => {
            if (currentTimeStepIndex > 0) {
              const newIndex = currentTimeStepIndex - 1;
              setCurrentTimeStepIndex(newIndex);
              sendProtocolMessage(createTimeStepMessage(newIndex));
              sendProtocolMessage(createRenderMessage());
            }
          }}
        >
          Previous
        </button>
        <span className="timestep-display">
          {hasTimeSteps ? `Step ${currentTimeStepIndex + 1} / ${total}` : 'No time steps'}
        </span>
        <button
          className="timestep-btn timestep-next"
          disabled={currentTimeStepIndex >= total - 1}
          onClick={() => {
            if (currentTimeStepIndex < total - 1) {
              const newIndex = currentTimeStepIndex + 1;
              setCurrentTimeStepIndex(newIndex);
              sendProtocolMessage(createTimeStepMessage(newIndex));
              sendProtocolMessage(createRenderMessage());
            }
          }}
        >
          Next
        </button>
      </div>
    );
  };

  return (
    <div className="paraview-viewer">
      {renderContent()}
    </div>
  );
}
