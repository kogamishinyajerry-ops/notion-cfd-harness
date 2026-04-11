"""
Pydantic Models for API Request/Response Schemas

Defines the core data structures used across all API endpoints.
"""

from __future__ import annotations

from datetime import datetime
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
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    status: Literal["launching", "ready", "active", "stopping", "stopped"] = Field(
        default="launching", description="Session lifecycle status"
    )

    class Config:
        use_enum_values = True
