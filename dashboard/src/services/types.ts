/**
 * TypeScript types for API responses from Phase 10 FastAPI server
 */

// Auth types
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: string;
  username: string;
  email: string;
  permission_level: PermissionLevel;
  created_at: string;
}

export type PermissionLevel = 'L0' | 'L1' | 'L2' | 'L3';

// Case types
export interface Case {
  id: string;
  name: string;
  description: string;
  geometry_type: GeometryType;
  boundary_conditions: BoundaryConditions;
  solver_config: SolverConfig;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
}

export type GeometryType = 'pipe' | 'elbow' | 'channel' | 'airfoil' | 'custom';
export type CaseStatus = 'draft' | 'validated' | 'running' | 'completed' | 'failed';

export interface BoundaryConditions {
  inlet_velocity?: number;
  outlet_pressure?: number;
  wall_condition?: string;
  fluid_properties?: Record<string, number>;
}

export interface SolverConfig {
  turbulence_model?: string;
  resolution?: string;
  max_iterations?: number;
}

// Job types
export interface Job {
  id: string;
  case_id: string;
  case_name?: string;
  status: JobStatus;
  progress: number;
  submitted_at?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  result?: Record<string, unknown>;
  job_type?: string;
}

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobLog {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR';
  message: string;
}

// Report types
export interface Report {
  id: string;
  job_id: string;
  case_id: string;
  case_name: string;
  format: ReportFormat;
  status: ReportStatus;
  created_at: string;
  download_url?: string;
}

export type ReportFormat = 'html' | 'pdf' | 'json';
export type ReportStatus = 'pending' | 'generating' | 'completed' | 'failed';

// Knowledge types
export interface KnowledgeEntry {
  id: string;
  title: string;
  content: string;
  category: string;
  tags: string[];
  source?: string;
  relevance_score?: number;
}

export interface KnowledgeQueryRequest {
  query: string;
  category?: string;
  limit?: number;
}

// API response wrapper
export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
}

// Status types
export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  uptime_seconds: number;
  services: ServiceStatus[];
}

export interface ServiceStatus {
  name: string;
  status: 'up' | 'down';
  latency_ms?: number;
}
