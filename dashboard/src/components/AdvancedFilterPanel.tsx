import { useState, useCallback } from 'react';

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

interface AdvancedFilterPanelProps {
  activeFilters: FilterInfo[];
  selectedField: string;
  onFiltersChange: (filters: FilterInfo[]) => void;
  // Direct bridge callbacks — no more sendProtocolMessage / paraviewProtocol
  onCreateClip: (insideOut: boolean, scalarValue: number) => void;
  onCreateContour: (isovalues: number[]) => void;
  onCreateStreamTracer: (direction: 'FORWARD' | 'BACKWARD', maxSteps: number) => void;
  onDeleteFilter: (filterId: string) => void;
}

export default function AdvancedFilterPanel({
  activeFilters,
  selectedField,
  onFiltersChange,
  onCreateClip,
  onCreateContour,
  onCreateStreamTracer,
  onDeleteFilter,
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
    onCreateClip(clipInsideOut, scalarValue);
  }, [clipInsideOut, clipScalarValue, onCreateClip]);

  const handleCreateContour = useCallback(() => {
    const values = contourIsovalues
      .split(',')
      .map((v) => parseFloat(v.trim()))
      .filter((v) => !isNaN(v));
    if (values.length === 0) return;
    onCreateContour(values);
  }, [contourIsovalues, onCreateContour]);

  const handleCreateStreamTracer = useCallback(() => {
    const maxSteps = parseInt(streamMaxSteps, 10);
    if (isNaN(maxSteps) || maxSteps <= 0) return;
    onCreateStreamTracer(streamDirection, maxSteps);
  }, [streamDirection, streamMaxSteps, onCreateStreamTracer]);

  const handleDeleteFilter = useCallback(
    (filterId: string) => {
      onDeleteFilter(filterId);
      onFiltersChange(activeFilters.filter((f) => f.id !== filterId));
    },
    [activeFilters, onFiltersChange, onDeleteFilter]
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
