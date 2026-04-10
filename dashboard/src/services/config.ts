/**
 * API Client Configuration
 * Points to the Phase 10 FastAPI server
 */

export const API_BASE_URL = 'http://localhost:8000';
export const API_PREFIX = '/api/v1';

export const API_ENDPOINTS = {
  // Status
  health: '/health',

  // Auth
  login: '/auth/login',
  logout: '/auth/logout',
  refresh: '/auth/refresh',
  me: '/auth/me',

  // Cases
  cases: '/cases',
  caseById: (id: string) => `/cases/${id}`,

  // Jobs
  jobs: '/jobs',
  jobById: (id: string) => `/jobs/${id}`,
  jobLogs: (id: string) => `/jobs/${id}/logs`,

  // Knowledge
  knowledge: '/knowledge',
  knowledgeQuery: '/knowledge/query',

  // Reports
  reports: '/reports',
  reportById: (id: string) => `/reports/${id}`,

  // WebSocket
  websocket: '/ws',
} as const;
