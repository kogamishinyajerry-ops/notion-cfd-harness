import { useState, useCallback } from 'react';
import {
  createClipFilterMessage,
  createContourFilterMessage,
  createStreamTracerFilterMessage,
  createDeleteFilterMessage,
  FilterInfo,
} from '../services/paraviewProtocol';

interface AdvancedFilterPanelProps {
  sendProtocolMessage: (message: object) => void;
  activeFilters: FilterInfo[];
  selectedField: string;
  onFiltersChange: (filters: FilterInfo[]) => void;
}

export default function AdvancedFilterPanel({
  sendProtocolMessage,
  activeFilters,
  selectedField,
  onFiltersChange,
}: AdvancedFilterPanelProps) {
  const [activeTab, setActiveTab] = useState<'clip' | 'contour' | 'streamlines'>('clip');

  // Clip state
  const [clipInsideOut, setClipInsideOut] = useState(false);
  const [clipScalarValue, setClipScalarValue] = useState('0');

  // Contour state
  const [contourIsovalues, setContourIsovalues] = useState('0.5');

  // StreamTracer state
  const [streamDirection, setStreamDirection] = useState<'FORWARD' | 'BACKWARD'>('FORWARD');
  const [streamMaxSteps, setStreamMaxSteps] = useState('1000');

  const handleCreateClip = useCallback(() => {
    const scalarValue = parseFloat(clipScalarValue);
    if (isNaN(scalarValue)) return;
    sendProtocolMessage(createClipFilterMessage(clipInsideOut, scalarValue));
  }, [clipInsideOut, clipScalarValue, sendProtocolMessage]);

  const handleCreateContour = useCallback(() => {
    const values = contourIsovalues
      .split(',')
      .map((v) => parseFloat(v.trim()))
      .filter((v) => !isNaN(v));
    if (values.length === 0) return;
    sendProtocolMessage(createContourFilterMessage(values));
  }, [contourIsovalues, sendProtocolMessage]);

  const handleCreateStreamTracer = useCallback(() => {
    const maxSteps = parseInt(streamMaxSteps, 10);
    if (isNaN(maxSteps) || maxSteps <= 0) return;
    sendProtocolMessage(createStreamTracerFilterMessage(streamDirection, maxSteps));
  }, [streamDirection, streamMaxSteps, sendProtocolMessage]);

  const handleDeleteFilter = useCallback(
    (filterId: number) => {
      sendProtocolMessage(createDeleteFilterMessage(filterId));
      onFiltersChange(activeFilters.filter((f) => f.id !== filterId));
    },
    [activeFilters, onFiltersChange, sendProtocolMessage]
  );

  const renderClipTab = () => (
    <div className="filter-panel">
      <div className="filter-row">
        <label className="filter-label">Inside Out</label>
        <input
          type="checkbox"
          className="filter-checkbox"
          checked={clipInsideOut}
          onChange={(e) => setClipInsideOut(e.target.checked)}
        />
      </div>
      <div className="filter-row">
        <label className="filter-label">Threshold</label>
        <input
          type="number"
          className="filter-number-input"
          value={clipScalarValue}
          onChange={(e) => setClipScalarValue(e.target.value)}
          step="0.1"
        />
      </div>
      <button className="filter-apply-btn" onClick={handleCreateClip}>
        Apply Clip
      </button>
    </div>
  );

  const renderContourTab = () => (
    <div className="filter-panel">
      <div className="filter-row">
        <label className="filter-label">Isovalues</label>
        <input
          type="text"
          className="filter-text-input"
          value={contourIsovalues}
          onChange={(e) => setContourIsovalues(e.target.value)}
          placeholder="0.1, 0.3, 0.5"
        />
      </div>
      <button className="filter-apply-btn" onClick={handleCreateContour}>
        Apply Contour
      </button>
    </div>
  );

  const renderStreamlinesTab = () => (
    <div className="filter-panel">
      <div className="filter-row">
        <label className="filter-label">Direction</label>
        <div className="filter-direction-btns">
          <button
            className={`filter-direction-btn ${streamDirection === 'FORWARD' ? 'active' : ''}`}
            onClick={() => setStreamDirection('FORWARD')}
          >
            Forward
          </button>
          <button
            className={`filter-direction-btn ${streamDirection === 'BACKWARD' ? 'active' : ''}`}
            onClick={() => setStreamDirection('BACKWARD')}
          >
            Backward
          </button>
        </div>
      </div>
      <div className="filter-row">
        <label className="filter-label">Max Steps</label>
        <input
          type="number"
          className="filter-number-input"
          value={streamMaxSteps}
          onChange={(e) => setStreamMaxSteps(e.target.value)}
          min="1"
          max="10000"
        />
      </div>
      <button className="filter-apply-btn" onClick={handleCreateStreamTracer}>
        Apply Streamlines
      </button>
    </div>
  );

  const renderActiveFilters = () => {
    if (activeFilters.length === 0) return null;
    return (
      <div className="active-filters-list">
        {activeFilters.map((filter) => (
          <div key={filter.id} className="active-filter-row">
            <span className="active-filter-info">
              {filter.type === 'clip' &&
                `Clip: ${filter.parameters.insideOut ? 'inside' : 'outside'}, threshold=${filter.parameters.scalarValue}`}
              {filter.type === 'contour' &&
                `Contour: isovalues=[${filter.parameters.isovalues?.join(', ')}]`}
              {filter.type === 'streamtracer' &&
                `Streamlines: ${filter.parameters.integrationDirection}, maxSteps=${filter.parameters.maxSteps}`}
            </span>
            <button
              className="filter-delete-btn"
              onClick={() => handleDeleteFilter(filter.id)}
              title="Delete filter"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="advanced-filter-panel">
      <div className="filter-tabs">
        <button
          className={`filter-tab ${activeTab === 'clip' ? 'active' : ''}`}
          onClick={() => setActiveTab('clip')}
        >
          Clip
        </button>
        <button
          className={`filter-tab ${activeTab === 'contour' ? 'active' : ''}`}
          onClick={() => setActiveTab('contour')}
        >
          Contour
        </button>
        <button
          className={`filter-tab ${activeTab === 'streamlines' ? 'active' : ''}`}
          onClick={() => setActiveTab('streamlines')}
        >
          Streamlines
        </button>
      </div>

      {activeTab === 'clip' && renderClipTab()}
      {activeTab === 'contour' && renderContourTab()}
      {activeTab === 'streamlines' && renderStreamlinesTab()}

      {renderActiveFilters()}
    </div>
  );
}
