"""
Pydantic Models for API Request/Response Schemas

Defines the core data structures used across all API endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class ProblemType(str, Enum):
    """CFD problem types"""
    INTERNAL_FLOW = "InternalFlow"
    EXTERNAL_FLOW = "ExternalFlow"
    HEAT_TRANSFER = "HeatTransfer"
    MULTIPHASE = "Multiphase"
    FSI = "FSI"


class JobStatus(str, Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PermissionLevel(str, Enum):
    """Permission levels for knowledge operations (L0-L3)"""
    L0 = "L0"  # Guest - read-only
    L1 = "L1"  # User - basic operations
    L2 = "L2"  # Editor - full operations
    L3 = "L3"  # Admin - system administration


# =============================================================================
# Case Models
# =============================================================================


class CaseSpec(BaseModel):
    """Specification for creating a new case"""
    name: str = Field(..., description="Case name", min_length=1, max_length=200)
    problem_type: ProblemType = Field(default=ProblemType.EXTERNAL_FLOW, description="CFD problem type")
    description: Optional[str] = Field(default=None, description="Case description")
    geometry_config: Optional[Dict[str, Any]] = Field(default=None, description="Geometry configuration")
    physics_models: List[str] = Field(default=["RANS"], description="Physics models to use")
    permission_level: PermissionLevel = Field(default=PermissionLevel.L1, description="Required permission level")


class CaseUpdate(BaseModel):
    """Specification for updating an existing case"""
    name: Optional[str] = Field(default=None, description="Case name", min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, description="Case description")
    status: Optional[str] = Field(default=None, description="Case status")


class CaseResponse(BaseModel):
    """Response model for case data"""
    case_id: str = Field(..., description="Unique case identifier")
    name: str = Field(..., description="Case name")
    problem_type: ProblemType = Field(..., description="CFD problem type")
    description: Optional[str] = Field(default=None, description="Case description")
    status: str = Field(..., description="Case status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    permission_level: PermissionLevel = Field(..., description="Required permission level")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CaseListResponse(BaseModel):
    """Response model for listing cases"""
    cases: List[CaseResponse] = Field(..., description="List of cases")
    total: int = Field(..., description="Total number of cases")
    offset: int = Field(default=0, description="Offset for pagination")
    limit: int = Field(default=50, description="Limit for pagination")


# =============================================================================
# GoldStandard Models (GS-02)
# =============================================================================


class GoldStandardMeshInfo(BaseModel):
    """Mesh metadata for a GoldStandard case."""
    mesh_strategy: str = Field(..., description='"A" for ready mesh, "B" for script-built')
    mesh_file_path: Optional[str] = Field(None, description="Path to mesh file if strategy A")
    mesh_hash: Optional[str] = Field(None, description="SHA256 of mesh file for provenance")
    mesh_details: Optional[str] = Field(None, description="Description of mesh setup")


class GoldStandardSolverConfig(BaseModel):
    """Solver configuration for a GoldStandard case."""
    solver_name: str = Field(..., description="Solver executable name (e.g., icoFoam, simpleFoam)")
    turbulence_model: Optional[str] = Field(None, description="Turbulence model if applicable")
    discretization_schemes: Dict[str, str] = Field(default_factory=dict, description="Scheme selections")
    convergence_criteria: Dict[str, float] = Field(default_factory=dict, description="Convergence tolerances")


class GoldStandardCaseSummary(BaseModel):
    """Summary of a GoldStandard case for list endpoint."""
    id: str = Field(..., description="Case ID (e.g., 'OF-01', 'SU2-02')")
    case_name: str = Field(..., description="Human-readable case name")
    platform: str = Field(..., description="Platform: OpenFOAM or SU2")
    tier: str = Field(..., description="Tier: core_seed, bridge, breadth")
    dimension: str = Field(..., description="Dimension: 2D, 3D, 2D_or_quasi_2D")
    difficulty: str = Field(..., description="Difficulty: basic, intermediate, advanced")
    mesh_strategy: str = Field(..., description="Mesh strategy: A or B")
    solver_command: str = Field(..., description="Solver execution command")
    has_gold_standard: bool = Field(..., description="True if GoldStandard module is registered")
    has_reference_data: bool = Field(..., description="True if reference data is available")
    has_mesh_info: bool = Field(..., description="True if mesh info function is registered")
    has_solver_config: bool = Field(..., description="True if solver config function is registered")


class GoldStandardListResponse(BaseModel):
    """Response for listing GoldStandard cases."""
    cases: List[GoldStandardCaseSummary] = Field(..., description="List of GoldStandard case summaries")
    total: int = Field(..., description="Total number of cases")
    platform_filter: Optional[str] = Field(None, description="Applied platform filter")


class GoldStandardCaseDetail(BaseModel):
    """Detailed GoldStandard case including ReportSpec and metadata."""
    id: str = Field(..., description="Case ID")
    case_name: str = Field(..., description="Human-readable case name")
    platform: str = Field(..., description="Platform")
    tier: str = Field(..., description="Tier")
    dimension: str = Field(..., description="Dimension")
    difficulty: str = Field(..., description="Difficulty")
    mesh_strategy: str = Field(..., description="Mesh strategy")
    has_ready_mesh: bool = Field(..., description="True if mesh is pre-provided")
    solver_command: str = Field(..., description="Solver command")
    success_criteria: str = Field(..., description="Success criteria")
    source_provenance: str = Field(..., description="Source provenance string")
    mesh_info: Optional[GoldStandardMeshInfo] = Field(None, description="Mesh metadata")
    solver_config: Optional[GoldStandardSolverConfig] = Field(None, description="Solver configuration")
    report_spec: Optional[Dict[str, Any]] = Field(None, description="ReportSpec as dict if registered")
    problem_type: Optional[str] = Field(None, description="ReportSpec problem type")


class ValidationResultDetail(BaseModel):
    """Detailed result of a single validation check."""
    metric: str = Field(..., description="Metric or plot name")
    status: str = Field(..., description="PASS, FAIL, WARN, or SKIPPED")
    message: Optional[str] = Field(None, description="Detail message")
    value: Optional[float] = Field(None, description="Simulated value")
    reference_value: Optional[float] = Field(None, description="Reference value")
    error_pct: Optional[float] = Field(None, description="Error percentage")


class ValidationResultResponse(BaseModel):
    """Response for gold standard validation endpoint."""
    case_id: str = Field(..., description="Case ID that was validated")
    passed: bool = Field(..., description="Overall pass/fail")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    details: List[ValidationResultDetail] = Field(default_factory=list, description="Per-metric results")
    plot_coverage: Optional[float] = Field(None, description="Fraction of required plots present")
    metric_coverage: Optional[float] = Field(None, description="Fraction of required metrics present")


# =============================================================================
# Job Models
# =============================================================================


class JobSubmission(BaseModel):
    """Specification for submitting a new job"""
    case_id: str = Field(..., description="Case ID to execute")
    job_type: str = Field(..., description="Job type (e.g., 'run', 'verify', 'report')")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Job parameters")
    async_mode: bool = Field(default=False, description="Run job asynchronously if True")


class JobResponse(BaseModel):
    """Response model for job data"""
    job_id: str = Field(..., description="Unique job identifier")
    case_id: str = Field(..., description="Associated case ID")
    job_type: str = Field(..., description="Job type")
    status: JobStatus = Field(..., description="Job status")
    submitted_at: datetime = Field(..., description="Submission timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    progress: float = Field(default=0.0, description="Progress percentage (0-100)")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Job result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class JobListResponse(BaseModel):
    """Response model for listing jobs"""
    jobs: List[JobResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")


# =============================================================================
# Status Models
# =============================================================================


class SystemStatus(BaseModel):
    """System status information"""
    version: str = Field(..., description="API version")
    status: str = Field(..., description="Overall system status")
    uptime_seconds: float = Field(..., description="Uptime in seconds")
    active_jobs: int = Field(..., description="Number of active jobs")
    total_cases: int = Field(..., description="Total number of cases")
    knowledge_units: int = Field(..., description="Number of registered knowledge units")


# =============================================================================
# Knowledge Models
# =============================================================================


class KnowledgeUnit(BaseModel):
    """Knowledge unit reference"""
    unit_id: str = Field(..., description="Unit identifier")
    unit_type: str = Field(..., description="Unit type (chapter/formula/data_point/chart_rule/evidence)")
    source_file: str = Field(..., description="Source file")
    version: str = Field(..., description="Version")


class KnowledgeSearchRequest(BaseModel):
    """Request model for knowledge search"""
    query: str = Field(..., description="Search query", min_length=1)
    unit_type: Optional[str] = Field(default=None, description="Filter by unit type")
    limit: int = Field(default=20, description="Maximum results")


class KnowledgeSearchResponse(BaseModel):
    """Response model for knowledge search"""
    results: List[KnowledgeUnit] = Field(..., description="Search results")
    total: int = Field(..., description="Total matching units")


# =============================================================================
# Health Models
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="API version")


# =============================================================================
# Auth Models
# =============================================================================


class LoginRequest(BaseModel):
    """Login request credentials"""
    username: str = Field(..., description="Username", min_length=1, max_length=100)
    password: str = Field(..., description="Password", min_length=1)


class TokenResponse(BaseModel):
    """Token response after successful login"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class RefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., description="JWT refresh token")


class UserInfo(BaseModel):
    """Current user information"""
    user_id: str = Field(..., description="User identifier")
    username: str = Field(..., description="Username")
    role: str = Field(..., description="User role")
    permission_level: PermissionLevel = Field(..., description="Permission level (L0-L3)")
    session_count: int = Field(default=1, description="Number of active sessions")


class LogoutResponse(BaseModel):
    """Logout response"""
    message: str = Field(..., description="Logout status message")
    sessions_terminated: int = Field(default=0, description="Number of sessions terminated")


# =============================================================================
# Convergence Models
# =============================================================================

class ConvergenceMessage(BaseModel):
    """Real-time convergence data streamed during job execution."""
    type: Literal["residual"] = "residual"
    job_id: str
    iteration: int
    time_value: float
    residuals: Dict[str, float]  # e.g., {"p": 1.23e-5, "Ux": 4.56e-6, "Uy": 3.21e-6}
    status: str  # running | converged | diverged | stalled
    timestamp: datetime


# =============================================================================
# ParaView Web Models
# =============================================================================


class ParaViewWebSession(BaseModel):
    """ParaView Web session state."""
    session_id: str = Field(..., description="Unique session identifier")
    job_id: Optional[str] = Field(default=None, description="Associated job ID")
    container_id: str = Field(..., description="Docker container ID")
    port: int = Field(..., description="Host port for WebSocket connection")
    case_dir: str = Field(..., description="Case directory mounted in container")
    auth_key: str = Field(..., description="Session authentication key")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last activity timestamp")
    status: Literal["launching", "ready", "active", "stopping", "stopped"] = Field(
        default="launching", description="Session lifecycle status"
    )

    class Config:
        use_enum_values = True


class TrameSession(BaseModel):
    """Trame session state (replaces ParaViewWebSession for v1.6.0)."""
    session_id: str = Field(..., description="Unique session identifier")
    job_id: Optional[str] = Field(default=None, description="Associated job ID")
    container_id: str = Field(..., description="Docker container ID")
    port: int = Field(..., description="Host port for HTTP connection")
    case_dir: str = Field(..., description="Case directory mounted in container")
    auth_key: str = Field(..., description="Session authentication key")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last activity timestamp")
    status: Literal["launching", "ready", "active", "stopping", "stopped"] = Field(
        default="launching", description="Session lifecycle status"
    )

    class Config:
        use_enum_values = True


# =============================================================================
# Pipeline Models
# =============================================================================


class PipelineStatus(str, Enum):
    """Pipeline execution status"""
    PENDING = "pending"
    RUNNING = "running"
    MONITORING = "monitoring"
    VISUALIZING = "visualizing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class StepStatus(str, Enum):
    """Individual step execution status within a pipeline."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepResultStatus(str, Enum):
    """Result status of a completed step."""
    SUCCESS = "success"
    DIVERGED = "diverged"
    VALIDATION_FAILED = "validation_failed"
    ERROR = "error"


class StepType(str, Enum):
    """Pipeline step types"""
    GENERATE = "generate"
    RUN = "run"
    MONITOR = "monitor"
    VISUALIZE = "visualize"
    REPORT = "report"


class StepResult(BaseModel):
    """Structured result object returned by each pipeline step.

    The `status` field (StepResultStatus enum) is the primary signal for pipeline
    continuation — NOT exit_code. This allows monitor steps to report `DIVERGED`
    without halting the pipeline.
    """
    status: StepResultStatus
    exit_code: int = 0
    validation_checks: Dict[str, bool] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class PipelineStep(BaseModel):
    """A single step within a pipeline DAG."""
    step_id: str = Field(..., description="Unique step identifier within the pipeline")
    step_type: StepType = Field(..., description="Type of step")
    step_order: int = Field(..., description="Execution order (0-indexed)")
    depends_on: List[str] = Field(default_factory=list, description="List of step_ids this step depends on")
    params: Dict[str, Any] = Field(default_factory=dict, description="Step-specific parameters")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Step execution status")


class Pipeline(BaseModel):
    """Pipeline definition with DAG steps."""
    id: str = Field(..., description="Unique pipeline identifier")
    name: str = Field(..., description="Pipeline name", min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, description="Pipeline description")
    status: PipelineStatus = Field(default=PipelineStatus.PENDING, description="Overall pipeline status")
    steps: List[PipelineStep] = Field(default_factory=list, description="Ordered list of DAG steps")
    config: Dict[str, Any] = Field(default_factory=dict, description="Pipeline-level configuration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        use_enum_values = True


class PipelineCreate(BaseModel):
    """Request model for creating a pipeline."""
    name: str = Field(..., description="Pipeline name", min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, description="Pipeline description")
    steps: List[PipelineStep] = Field(default_factory=list, description="DAG steps")
    config: Dict[str, Any] = Field(default_factory=dict, description="Pipeline-level configuration")


class PipelineUpdate(BaseModel):
    """Request model for updating a pipeline."""
    name: Optional[str] = Field(default=None, description="Pipeline name", min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, description="Pipeline description")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Pipeline-level configuration")
    status: Optional[PipelineStatus] = Field(default=None, description="Pipeline status (PENDING only)")


class PipelineResponse(BaseModel):
    """Response model for pipeline data."""
    id: str
    name: str
    description: Optional[str]
    status: PipelineStatus
    steps: List[PipelineStep]
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        use_enum_values = True


class PipelineListResponse(BaseModel):
    """Response model for listing pipelines."""
    pipelines: List[PipelineResponse]
    total: int


# =============================================================================
# Sweep Models (PIPE-10 — Parametric Sweep)
# =============================================================================


class SweepStatus(str, Enum):
    """Sweep execution status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SweepCaseStatus(str, Enum):
    """Status of a single combination case within a sweep"""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SweepCreate(BaseModel):
    """Request model for creating a sweep."""
    name: str = Field(..., description="Sweep name", min_length=1, max_length=64)
    description: Optional[str] = Field(default=None, description="Optional description", max_length=256)
    base_pipeline_id: str = Field(..., description="ID of the base pipeline template")
    param_grid: Dict[str, List[Any]] = Field(..., description="Parameter grid, e.g. {'velocity': [1, 2, 5], 'resolution': [50, 100]}")
    max_concurrent: int = Field(default=2, ge=1, le=10, description="Max concurrent Docker containers")


class SweepCaseResponse(BaseModel):
    """Response model for a single combination case."""
    id: str
    sweep_id: str
    param_combination: Dict[str, Any]  # e.g. {'velocity': 1, 'resolution': 50}
    combination_hash: str  # first 8 chars of hash for display
    pipeline_id: Optional[str] = None
    status: SweepCaseStatus
    result_summary: Optional[Dict[str, Any]] = None  # final_residual, execution_time, etc.
    created_at: datetime
    updated_at: datetime
    convergence_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Per-iteration convergence history from solver log")
    provenance: Optional["ProvenanceMetadata"] = Field(default=None, description="Solver provenance metadata")

    class Config:
        use_enum_values = True


class SweepResponse(BaseModel):
    """Response model for a sweep."""
    id: str
    name: str
    description: Optional[str]
    base_pipeline_id: str
    param_grid: Dict[str, List[Any]]
    max_concurrent: int
    status: SweepStatus
    total_combinations: int
    completed_combinations: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        use_enum_values = True


class SweepListResponse(BaseModel):
    """Response model for listing sweeps."""
    sweeps: List[SweepResponse]
    total: int


# =============================================================================
# Provenance & Comparison Models (PIPE-11, PIPE-12)
# =============================================================================


class ProvenanceMetadata(BaseModel):
    """Provenance metadata for a sweep case."""
    openfoam_version: Optional[str] = Field(default=None, description="OpenFOAM version (e.g. v10)")
    compiler_version: Optional[str] = Field(default=None, description="Compiler version")
    mesh_seed_hash: Optional[str] = Field(default=None, description="Deterministic hash of mesh configuration")
    solver_config_hash: Optional[str] = Field(default=None, description="Deterministic hash of solver control parameters")


class ConvergenceDataPoint(BaseModel):
    """Single iteration data point from convergence log."""
    iteration: int
    Ux: Optional[float] = None
    Uy: Optional[float] = None
    Uz: Optional[float] = None
    p: Optional[float] = None


class MetricsRow(BaseModel):
    """Single row in the comparison metrics table."""
    case_id: str
    params: str  # human-readable: "velocity=1, resolution=50"
    final_residual: Optional[float] = None
    execution_time: Optional[float] = None  # seconds
    diff_pct: Optional[float] = None  # percentage vs reference case


class ProvenanceMismatchItem(BaseModel):
    """Describes a provenance field that differs across compared cases."""
    field: str  # openfoam_version | compiler_version | mesh_seed_hash | solver_config_hash
    values: List[str]


class ComparisonCreate(BaseModel):
    """Request to create a new comparison."""
    name: Optional[str] = Field(default=None, description="Optional human-readable name")
    reference_case_id: str = Field(..., description="Case ID to use as reference for diff_pct")
    case_ids: List[str] = Field(..., description="All case IDs to include (must include reference_case_id)", min_length=2)
    delta_case_a_id: Optional[str] = Field(default=None, description="Case A for delta field (CaseB - CaseA)")
    delta_case_b_id: Optional[str] = Field(default=None, description="Case B for delta field (CaseB - CaseA)")
    delta_field_name: str = Field(default="p", description="Scalar field name for delta computation")


class ComparisonResponse(BaseModel):
    """Response for a single comparison result."""
    id: str
    name: Optional[str]
    reference_case_id: str
    case_ids: List[str]
    provenance_mismatch: List[ProvenanceMismatchItem]
    convergence_data: Dict[str, List[Dict[str, Any]]]  # case_id -> list of data points
    metrics_table: List[MetricsRow]
    delta_case_a_id: Optional[str]
    delta_case_b_id: Optional[str]
    delta_field_name: Optional[str]
    delta_vtu_url: Optional[str]  # set if delta was computed
    created_at: datetime
    updated_at: datetime


class ComparisonListResponse(BaseModel):
    """List of comparisons."""
    comparisons: List[ComparisonResponse]
