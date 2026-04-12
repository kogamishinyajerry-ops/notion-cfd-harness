/**
 * API Client - Handles all HTTP requests to the Phase 10 FastAPI server
 */

import { API_BASE_URL, API_PREFIX } from './config';
import type {
  LoginRequest,
  LoginResponse,
  User,
  Case,
  Job,
  Report,
  KnowledgeEntry,
  KnowledgeQueryRequest,
  SystemStatus,
  PaginatedResponse,
  Pipeline,
  PipelineListResponse,
} from './types';

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  setToken(token: string | null) {
    this.token = token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${API_PREFIX}${endpoint}`;
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Auth
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await this.request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
    this.token = response.access_token;
    return response;
  }

  async logout(): Promise<void> {
    await this.request('/auth/logout', { method: 'POST' });
    this.token = null;
  }

  async getCurrentUser(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  // Status
  async getHealth(): Promise<SystemStatus> {
    return this.request<SystemStatus>('/health');
  }

  // Cases
  async getCases(): Promise<Case[]> {
    const response = await this.request<PaginatedResponse<Case>>('/cases');
    return response.data;
  }

  async getCase(id: string): Promise<Case> {
    return this.request<Case>(`/cases/${id}`);
  }

  async createCase(data: Partial<Case>): Promise<Case> {
    return this.request<Case>('/cases', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateCase(id: string, data: Partial<Case>): Promise<Case> {
    return this.request<Case>(`/cases/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteCase(id: string): Promise<void> {
    await this.request(`/cases/${id}`, { method: 'DELETE' });
  }

  // Jobs
  async getJobs(): Promise<Job[]> {
    const response = await this.request<PaginatedResponse<Job>>('/jobs');
    return response.data;
  }

  async getJob(id: string): Promise<Job> {
    return this.request<Job>(`/jobs/${id}`);
  }

  async submitJob(caseId: string): Promise<Job> {
    return this.request<Job>('/jobs', {
      method: 'POST',
      body: JSON.stringify({ case_id: caseId }),
    });
  }

  async cancelJob(id: string): Promise<Job> {
    return this.request<Job>(`/jobs/${id}/cancel`, { method: 'POST' });
  }

  // Reports
  async getReports(): Promise<Report[]> {
    const response = await this.request<PaginatedResponse<Report>>('/reports');
    return response.data;
  }

  async getReport(id: string): Promise<Report> {
    return this.request<Report>(`/reports/${id}`);
  }

  async generateReport(jobId: string, format: 'html' | 'pdf' | 'json'): Promise<Report> {
    return this.request<Report>('/reports', {
      method: 'POST',
      body: JSON.stringify({ job_id: jobId, format }),
    });
  }

  // Knowledge
  async queryKnowledge(request: KnowledgeQueryRequest): Promise<KnowledgeEntry[]> {
    const response = await this.request<{ data: KnowledgeEntry[] }>('/knowledge/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
    return response.data;
  }

  // Pipelines
  async getPipelines(): Promise<Pipeline[]> {
    const response = await this.request<PipelineListResponse>('/pipelines');
    return response.pipelines;
  }

  async getPipeline(id: string): Promise<Pipeline> {
    return this.request<Pipeline>(`/pipelines/${id}`);
  }

  async createPipeline(data: {
    name: string;
    description?: string;
    steps: Array<{
      step_id: string;
      step_type: string;
      step_order: number;
      depends_on: string[];
      params: Record<string, unknown>;
    }>;
    config?: Record<string, unknown>;
  }): Promise<Pipeline> {
    return this.request<Pipeline>('/pipelines', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updatePipeline(id: string, data: Partial<{
    name: string;
    description: string;
    config: Record<string, unknown>;
  }>): Promise<Pipeline> {
    return this.request<Pipeline>(`/pipelines/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deletePipeline(id: string): Promise<void> {
    await this.request(`/pipelines/${id}`, { method: 'DELETE' });
  }

  async startPipeline(id: string): Promise<{ status: string; pipeline_id: string }> {
    return this.request<{ status: string; pipeline_id: string }>(`/pipelines/${id}/start`, {
      method: 'POST',
    });
  }

  async pausePipeline(id: string): Promise<{ status: string; pipeline_id: string }> {
    return this.request<{ status: string; pipeline_id: string }>(`/pipelines/${id}/pause`, {
      method: 'POST',
    });
  }

  async resumePipeline(id: string): Promise<{ status: string; pipeline_id: string }> {
    return this.request<{ status: string; pipeline_id: string }>(`/pipelines/${id}/resume`, {
      method: 'POST',
    });
  }

  async cancelPipeline(id: string): Promise<{ status: string; pipeline_id: string }> {
    return this.request<{ status: string; pipeline_id: string }>(`/pipelines/${id}/cancel`, {
      method: 'POST',
    });
  }

  async getPipelineSteps(id: string): Promise<unknown[]> {
    return this.request<unknown[]>(`/pipelines/${id}/steps`);
  }

  async getPipelineEvents(id: string): Promise<unknown[]> {
    return this.request<unknown[]>(`/pipelines/${id}/events`);
  }
}

export const apiClient = new ApiClient();
export default ApiClient;
