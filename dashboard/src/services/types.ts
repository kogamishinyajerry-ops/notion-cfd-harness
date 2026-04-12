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

// Pipeline types
export interface Pipeline {
  id: string;
  name: string;
  description?: string;
  status: PipelineStatus;
  steps: PipelineStep[];
  config: PipelineConfig;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
}

export type PipelineStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'MONITORING'
  | 'VISUALIZING'
  | 'REPORTING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'PAUSED';

export interface PipelineStep {
  id: string;
  pipeline_id: string;
  step_type: StepType;
  step_order: number;
  depends_on: string[];
  params: Record<string, unknown>;
  status: StepStatus;
  result?: StepResult;
  started_at?: string;
  completed_at?: string;
}

export type StepType = 'generate' | 'run' | 'monitor' | 'visualize' | 'report';
export type StepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';

export interface StepResult {
  status: 'success' | 'diverged' | 'validation_failed' | 'error';
  exit_code: number;
  validation_checks?: Record<string, boolean>;
  diagnostics?: Record<string, unknown>;
}

export interface PipelineConfig {
  dag: Record<string, string[]>;
}

export interface PipelineEvent {
  sequence: number;
  type:
    | 'pipeline_started'
    | 'step_started'
    | 'step_completed'
    | 'step_failed'
    | 'pipeline_completed'
    | 'pipeline_failed'
    | 'pipeline_cancelled'
    | 'pipeline_paused'
    | 'pipeline_resumed';
  pipeline_id: string;
  step_id?: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

export interface PipelineListResponse {
  pipelines: Pipeline[];
  total: number;
}

// Sweep types (PIPE-10)
export type SweepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
export type SweepCaseStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface Sweep {
  id: string;
  name: string;
  description?: string;
  base_pipeline_id: string;
  param_grid: Record<string, (string | number)[]>;
  max_concurrent: number;
  status: SweepStatus;
  total_combinations: number;
  completed_combinations: number;
  created_at: string;
  updated_at: string;
}

export interface SweepCase {
  id: string;
  sweep_id: string;
  param_combination: Record<string, string | number>;
  combination_hash: string;
  pipeline_id?: string;
  status: SweepCaseStatus;
  result_summary?: {
    final_residual?: number;
    execution_time?: number;
    pipeline_status?: string;
    error?: string;
  };
  created_at: string;
  updated_at: string;
}

export interface SweepListResponse {
  sweeps: Sweep[];
  total: number;
}
