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
  ApiResponse,
  PaginatedResponse,
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
}

export const apiClient = new ApiClient();
export default ApiClient;
