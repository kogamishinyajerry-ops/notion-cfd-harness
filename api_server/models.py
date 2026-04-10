"""
Pydantic Models for API Request/Response Schemas

Defines the core data structures used across all API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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
