/**
 * CaseList Component - Displays cases with search and filter
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type {
  CaseDefinition,
  CaseListFilter,
  GeometryType,
} from '../services/caseTypes';
import { GEOMETRY_TYPE_LABELS } from '../services/caseTypes';
import {
  loadCases,
  deleteCase,
  exportCase,
  cloneCase,
  saveCase,
} from '../services/caseStorage';

interface CaseListProps {
  onSelectCase?: (caseId: string) => void;
}

const STATUS_COLORS: Record<CaseDefinition['status'], string> = {
  draft: 'var(--color-draft)',
  validated: 'var(--color-validated)',
  running: 'var(--color-running)',
  completed: 'var(--color-completed)',
  failed: 'var(--color-failed)',
};

export default function CaseList({ onSelectCase }: CaseListProps) {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseDefinition[]>(() => loadCases());
  const [filter, setFilter] = useState<CaseListFilter>({
    search: '',
    geometryType: '',
    status: '',
  });
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);

  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      if (filter.search) {
        const search = filter.search.toLowerCase();
        const match =
          c.name.toLowerCase().includes(search) ||
          c.description.toLowerCase().includes(search) ||
          c.id.toLowerCase().includes(search);
        if (!match) return false;
      }
      if (filter.geometryType && c.geometry.geometry_type !== filter.geometryType) {
        return false;
      }
      if (filter.status && c.status !== filter.status) {
        return false;
      }
      return true;
    });
  }, [cases, filter]);

  const handleRefresh = () => {
    setCases(loadCases());
  };

  const handleDelete = (id: string) => {
    deleteCase(id);
    setCases(loadCases());
    setShowDeleteConfirm(null);
  };

  const handleClone = (caseDef: CaseDefinition) => {
    const cloned = cloneCase(caseDef, `${caseDef.name} (Copy)`);
    saveCase(cloned);
    setCases(loadCases());
  };

  const handleExport = (caseDef: CaseDefinition) => {
    exportCase(caseDef);
  };

  const handleEdit = (caseId: string) => {
    if (onSelectCase) {
      onSelectCase(caseId);
    } else {
      navigate(`/cases/edit/${caseId}`);
    }
  };

  const handleCreateNew = () => {
    navigate(`/cases/new`);
  };

  return (
    <div className="case-list">
      {/* Header */}
      <div className="case-list-header">
        <div className="case-list-title">
          <h2>Cases ({filteredCases.length})</h2>
          <button className="btn btn-primary" onClick={handleCreateNew}>
            + New Case
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="case-list-filters">
        <input
          type="text"
          className="filter-input"
          placeholder="Search cases..."
          value={filter.search}
          onChange={(e) => setFilter((f) => ({ ...f, search: e.target.value }))}
        />
        <select
          className="filter-select"
          value={filter.geometryType}
          onChange={(e) =>
            setFilter((f) => ({
              ...f,
              geometryType: e.target.value as GeometryType | '',
            }))
          }
        >
          <option value="">All Geometry Types</option>
          {Object.entries(GEOMETRY_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          className="filter-select"
          value={filter.status}
          onChange={(e) =>
            setFilter((f) => ({
              ...f,
              status: e.target.value as CaseDefinition['status'] | '',
            }))
          }
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="validated">Validated</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
        <button className="btn btn-secondary" onClick={handleRefresh}>
          Refresh
        </button>
      </div>

      {/* Case Table */}
      {filteredCases.length === 0 ? (
        <div className="case-list-empty">
          <p>No cases found.</p>
          <button className="btn btn-primary" onClick={handleCreateNew}>
            Create your first case
          </button>
        </div>
      ) : (
        <table className="case-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>ID</th>
              <th>Geometry</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredCases.map((c) => (
              <tr key={c.id}>
                <td>
                  <div className="case-name-cell">
                    <span className="case-name">{c.name}</span>
                    {c.description && (
                      <span className="case-desc">{c.description}</span>
                    )}
                  </div>
                </td>
                <td>
                  <code className="case-id">{c.id}</code>
                </td>
                <td>
                  {GEOMETRY_TYPE_LABELS[c.geometry.geometry_type] ||
                    c.geometry.geometry_type}
                </td>
                <td>
                  <span
                    className="status-badge"
                    style={{ backgroundColor: STATUS_COLORS[c.status] }}
                  >
                    {c.status}
                  </span>
                </td>
                <td>
                  {new Date(c.created_at).toLocaleDateString()}
                </td>
                <td>
                  <div className="case-actions">
                    <button
                      className="btn btn-small"
                      onClick={() => handleEdit(c.id)}
                      title="Edit case"
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn-small"
                      onClick={() => handleClone(c)}
                      title="Clone case"
                    >
                      Clone
                    </button>
                    <button
                      className="btn btn-small"
                      onClick={() => handleExport(c)}
                      title="Export case"
                    >
                      Export
                    </button>
                    {showDeleteConfirm === c.id ? (
                      <>
                        <button
                          className="btn btn-small btn-danger"
                          onClick={() => handleDelete(c.id)}
                        >
                          Confirm
                        </button>
                        <button
                          className="btn btn-small"
                          onClick={() => setShowDeleteConfirm(null)}
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button
                        className="btn btn-small btn-danger"
                        onClick={() => setShowDeleteConfirm(c.id)}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
