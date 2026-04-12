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

  // Pipelines
  pipelines: '/pipelines',
  pipelineById: (id: string) => `/pipelines/${id}`,
  pipelineSteps: (id: string) => `/pipelines/${id}/steps`,
  pipelineEvents: (id: string) => `/pipelines/${id}/events`,
  pipelineStart: (id: string) => `/pipelines/${id}/start`,
  pipelinePause: (id: string) => `/pipelines/${id}/pause`,
  pipelineResume: (id: string) => `/pipelines/${id}/resume`,
  pipelineCancel: (id: string) => `/pipelines/${id}/cancel`,
  pipelineWs: (id: string) => `/ws/pipelines/${id}`,
} as const;

export const WS_PIPELINE_URL = (id: string) =>
  `${API_BASE_URL.replace('http', 'ws')}${API_PREFIX}/ws/pipelines/${id}`;
