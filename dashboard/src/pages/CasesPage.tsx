/**
 * CasesPage - Main cases management page
 * Displays case list and handles case creation/editing
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import CaseList from '../components/CaseList';
import CaseWizard from '../components/CaseWizard';
import { loadCase } from '../services/caseStorage';
import type { CaseDefinition } from '../services/caseTypes';

export default function CasesPage() {
  const { mode, caseId } = useParams();
  const navigate = useNavigate();
  const [, setEditingCase] = useState<CaseDefinition | null>(null);

  // Handle new case
  if (mode === 'new') {
    return (
      <div className="page cases-page">
        <CaseWizard
          onSave={(c) => {
            setEditingCase(c);
          }}
          onCancel={() => navigate('/cases')}
        />
      </div>
    );
  }

  // Handle edit case
  if (mode === 'edit' && caseId) {
    const caseToEdit = loadCase(caseId);
    if (!caseToEdit) {
      return (
        <div className="page cases-page">
          <div className="error-message">
            Case not found: {caseId}
          </div>
          <button className="btn btn-secondary" onClick={() => navigate('/cases')}>
            Back to Cases
          </button>
        </div>
      );
    }
    return (
      <div className="page cases-page">
        <CaseWizard
          initialCase={caseToEdit}
          onSave={(c) => {
            setEditingCase(c);
          }}
          onCancel={() => navigate('/cases')}
        />
      </div>
    );
  }

  // Default: show case list
  return (
    <div className="page cases-page">
      <CaseList />
    </div>
  );
}
