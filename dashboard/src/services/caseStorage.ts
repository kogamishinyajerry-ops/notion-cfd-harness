/**
 * Case Storage Service - LocalStorage-based case persistence
 * Provides save/load functionality for case definitions
 */

import type { CaseDefinition, CaseListFilter } from './caseTypes';

const STORAGE_KEY = 'cfd_harness_cases';

// Load all cases from localStorage
export function loadCases(): CaseDefinition[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (!data) return [];
    const parsed = JSON.parse(data);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

// Save all cases to localStorage
export function saveCases(cases: CaseDefinition[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(cases));
}

// Load a single case by ID
export function loadCase(id: string): CaseDefinition | null {
  const cases = loadCases();
  return cases.find((c) => c.id === id) ?? null;
}

// Save a single case (upsert)
export function saveCase(caseDef: CaseDefinition): void {
  const cases = loadCases();
  const idx = cases.findIndex((c) => c.id === caseDef.id);
  caseDef.updated_at = new Date().toISOString();
  if (idx >= 0) {
    cases[idx] = caseDef;
  } else {
    cases.push(caseDef);
  }
  saveCases(cases);
}

// Delete a case by ID
export function deleteCase(id: string): void {
  const cases = loadCases().filter((c) => c.id !== id);
  saveCases(cases);
}

// Filter cases based on filter criteria
export function filterCases(
  cases: CaseDefinition[],
  filter: CaseListFilter
): CaseDefinition[] {
  return cases.filter((c) => {
    // Search filter
    if (filter.search) {
      const search = filter.search.toLowerCase();
      const match =
        c.name.toLowerCase().includes(search) ||
        c.description.toLowerCase().includes(search) ||
        c.id.toLowerCase().includes(search);
      if (!match) return false;
    }
    // Geometry type filter
    if (filter.geometryType && c.geometry.geometry_type !== filter.geometryType) {
      return false;
    }
    // Status filter
    if (filter.status && c.status !== filter.status) {
      return false;
    }
    return true;
  });
}

// Generate a new case ID
export function generateCaseId(): string {
  const now = new Date();
  const date = now.toISOString().slice(0, 10).replace(/-/g, '');
  const time = now.getTime().toString().slice(-6);
  return `case_${date}_${time}`;
}

// Export case to JSON file download
export function exportCase(caseDef: CaseDefinition): void {
  const json = JSON.stringify(caseDef, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${caseDef.id}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// Import case from JSON file
export function importCase(file: File): Promise<CaseDefinition> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target?.result as string);
        // Assign new ID to avoid conflicts
        data.id = generateCaseId();
        data.created_at = new Date().toISOString();
        data.updated_at = new Date().toISOString();
        resolve(data as CaseDefinition);
      } catch (err) {
        reject(new Error('Invalid case file format'));
      }
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsText(file);
  });
}

// Clone a case with new ID
export function cloneCase(
  caseDef: CaseDefinition,
  newName: string
): CaseDefinition {
  const newId = generateCaseId();
  const now = new Date().toISOString();
  return {
    ...JSON.parse(JSON.stringify(caseDef)),
    id: newId,
    name: newName,
    status: 'draft',
    created_at: now,
    updated_at: now,
  };
}
