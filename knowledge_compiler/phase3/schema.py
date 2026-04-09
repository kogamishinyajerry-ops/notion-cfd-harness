#!/usr/bin/env python3
"""
Phase 3 Schema: Orchestrator Data Models

定义 Phase 3 的核心数据结构，包括编排器、求解器、网格生成等。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

# Import Phase 2 types
from knowledge_compiler.phase2.schema import (
    CanonicalSpec,
    CompiledKnowledge,
    KnowledgeStatus,
)


# ============================================================================
# Enums
# ============================================================================

class SolverType(Enum):
    """求解器类型"""
    OPENFOAM = "openfoam"
    SU2 = "su2"
    STARCCM = "starccm"
    FLUENT = "fluent"


class SolverStatus(Enum):
    """求解器状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MeshFormat(Enum):
    """网格格式"""
    STL = "stl"
    STEP = "step"
    IGES = "iges"
    OBJ = "obj"
    TRI_SURFACE = "tri_surface"


class MeshQuality(Enum):
    """网格质量等级"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class JobPriority(Enum):
    """作业优先级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================================================
# Solver Runner Schema
# ============================================================================

@dataclass
class SolverConfig:
    """求解器配置"""
    solver_type: SolverType
    executable_path: str
    version: str = ""
    parallel: bool = False
    n_procs: int = 1
    additional_args: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BoundaryCondition:
    """边界条件"""
    name: str
    type: str  # wall, inlet, outlet, symmetry, etc.
    values: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SolverInput:
    """求解器输入"""
    case_dir: str
    mesh_dir: str = ""
    boundary_conditions: List[BoundaryCondition] = field(default_factory=list)
    solver_config: Optional[SolverConfig] = None
    control_dict: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SolverResult:
    """求解器结果"""
    job_id: str
    status: SolverStatus
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    output_files: List[str] = field(default_factory=list)
    runtime_seconds: float = 0.0
    error_message: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def is_success(self) -> bool:
        return self.status == SolverStatus.COMPLETED and self.exit_code == 0

@dataclass
class SolverJob:
    """求解器作业"""
    job_id: str = field(default_factory=lambda: f"SOLVER-{uuid.uuid4().hex[:8]}")
    input: Optional[SolverInput] = None
    result: Optional[SolverResult] = None
    status: SolverStatus = SolverStatus.PENDING
    priority: JobPriority = JobPriority.MEDIUM
    created_at: float = field(default_factory=time.time)

    def start(self) -> None:
        """启动作业"""
        self.status = SolverStatus.RUNNING
        if self.result is None:
            self.result = SolverResult(job_id=self.job_id, status=SolverStatus.RUNNING)
        else:
            self.result.status = SolverStatus.RUNNING
        self.result.started_at = time.time()

    def complete(self, exit_code: int, stdout: str = "", stderr: str = "") -> None:
        """完成作业"""
        self.status = SolverStatus.COMPLETED if exit_code == 0 else SolverStatus.FAILED
        if self.result:
            self.result.status = self.status
            self.result.exit_code = exit_code
            self.result.stdout = stdout
            self.result.stderr = stderr
            self.result.completed_at = time.time()
            self.result.runtime_seconds = self.result.completed_at - self.result.started_at

    def fail(self, error: str) -> None:
        """作业失败"""
        self.status = SolverStatus.FAILED
        if self.result:
            self.result.status = SolverStatus.FAILED
            self.result.error_message = error
            self.result.completed_at = time.time()

# ============================================================================
# Mesh Builder Schema
# ============================================================================

@dataclass
class MeshConfig:
    """网格配置"""
    format: MeshFormat
    base_geometry: str  # Path to geometry file
    target_element_size: float = 1.0
    refinement_levels: int = 0
    boundary_layer: bool = True
    n_boundary_layers: int = 3
    min_quality: float = 0.3
    additional_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MeshStatistics:
    """网格统计"""
    n_cells: int = 0
    n_faces: int = 0
    n_points: int = 0
    min_quality: float = 0.0
    avg_quality: float = 0.0
    max_non_orthogonality: float = 0.0
    max_aspect_ratio: float = 0.0

@dataclass
class MeshResult:
    """网格生成结果"""
    mesh_id: str = field(default_factory=lambda: f"MESH-{uuid.uuid4().hex[:8]}")
    status: SolverStatus = SolverStatus.PENDING
    output_dir: str = ""
    mesh_files: List[str] = field(default_factory=list)
    statistics: Optional[MeshStatistics] = None
    quality: MeshQuality = MeshQuality.FAIR
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """检查网格是否有效"""
        return self.status == SolverStatus.COMPLETED and self.statistics is not None

# ============================================================================
# Physics Planner Schema
# ============================================================================

@dataclass
class PhysicsModel:
    """物理模型配置"""
    solver_type: SolverType
    flow_type: str  # laminar, turbulent, etc.
    turbulence_model: str = "kEpsilon"
    energy_model: bool = False
    species_model: bool = False
    multiphase_model: bool = False

@dataclass
class PhysicsPlan:
    """物理规划方案"""
    plan_id: str = field(default_factory=lambda: f"PHYSICS-{uuid.uuid4().hex[:8]}")
    problem_type: str = ""  # internal_flow, external_flow, etc.
    physics_model: Optional[PhysicsModel] = None
    recommended_solver: Optional[SolverType] = None
    boundary_conditions: List[BoundaryCondition] = field(default_factory=list)
    solver_settings: Dict[str, Any] = field(default_factory=dict)
    convergence_criteria: Dict[str, float] = field(default_factory=dict)

# ============================================================================
# CAD Parser Schema
# ============================================================================

@dataclass
class GeometryFeature:
    """几何特征"""
    type: str  # face, edge, vertex, volume
    id: str = ""
    name: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ParsedGeometry:
    """解析后的几何"""
    geometry_id: str = field(default_factory=lambda: f"GEOM-{uuid.uuid4().hex[:8]}")
    source_file: str = ""
    format: MeshFormat = MeshFormat.STL
    features: List[GeometryFeature] = field(default_factory=list)
    bounding_box: Optional[Dict[str, float]] = None
    surface_area: float = 0.0
    volume: float = 0.0
    is_watertight: bool = True
    repair_needed: List[str] = field(default_factory=list)

# ============================================================================
# Job Scheduler Schema
# ============================================================================

@dataclass
class ScheduledJob:
    """已调度的作业"""
    job_id: str
    priority: JobPriority
    estimated_duration: float = 0.0  # seconds
    dependencies: List[str] = field(default_factory=list)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    status: SolverStatus = SolverStatus.PENDING
    scheduled_at: float = 0.0
    started_at: float = 0.0

@dataclass
class SchedulerState:
    """调度器状态"""
    running_jobs: List[str] = field(default_factory=list)
    pending_jobs: List[str] = field(default_factory=list)
    completed_jobs: List[str] = field(default_factory=list)
    failed_jobs: List[str] = field(default_factory=list)
    max_concurrent: int = 2

    def can_schedule(self) -> bool:
        """检查是否可以调度新作业"""
        return len(self.running_jobs) < self.max_concurrent

# ============================================================================
# Postprocess Runner Schema
# ============================================================================

class PostprocessStatus(Enum):
    """后处理状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class PostprocessFormat(Enum):
    """后处理输出格式"""
    JSON = "json"
    CSV = "csv"
    VTK = "vtk"
    PNG = "png"
    HTML_REPORT = "html_report"

@dataclass
class PostprocessArtifact:
    """后处理产物"""
    artifact_id: str = field(default_factory=lambda: f"ARTIFACT-{uuid.uuid4().hex[:8]}")
    format: PostprocessFormat = PostprocessFormat.JSON
    file_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

@dataclass
class PostprocessResult:
    """后处理结果"""
    result_id: str = field(default_factory=lambda: f"PP-RESULT-{uuid.uuid4().hex[:8]}")
    status: PostprocessStatus = PostprocessStatus.PENDING
    artifacts: List[PostprocessArtifact] = field(default_factory=list)
    field_data: Dict[str, Any] = field(default_factory=dict)  # 残差、场数据等
    convergence_info: Dict[str, Any] = field(default_factory=dict)  # 收敛信息
    error_message: str = ""
    processing_time: float = 0.0
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def add_artifact(self, artifact: PostprocessArtifact) -> None:
        """添加产物"""
        self.artifacts.append(artifact)

    def is_success(self) -> bool:
        """检查是否成功"""
        return self.status == PostprocessStatus.COMPLETED

@dataclass
class PostprocessRequest:
    """后处理请求"""
    request_id: str = field(default_factory=lambda: f"PP-REQ-{uuid.uuid4().hex[:8]}")
    solver_result: Optional[SolverResult] = None
    result_directory: str = ""  # OpenFOAM 结果目录路径
    output_formats: List[PostprocessFormat] = field(default_factory=lambda: list)
    extract_fields: List[str] = field(default_factory=list)  # 要提取的场变量
    generate_report: bool = True
    visualize: bool = False

@dataclass
class PostprocessJob:
    """后处理作业"""
    job_id: str = field(default_factory=lambda: f"PP-JOB-{uuid.uuid4().hex[:8]}")
    request: Optional[PostprocessRequest] = None
    result: Optional[PostprocessResult] = None
    status: PostprocessStatus = PostprocessStatus.PENDING
    created_at: float = field(default_factory=time.time)

    def start(self) -> None:
        """启动作业"""
        self.status = PostprocessStatus.RUNNING
        if self.result is None:
            self.result = PostprocessResult(status=PostprocessStatus.RUNNING)
        else:
            self.result.status = PostprocessStatus.RUNNING

    def complete(self, result: PostprocessResult) -> None:
        """完成作业"""
        self.status = PostprocessStatus.COMPLETED
        self.result = result
        result.status = PostprocessStatus.COMPLETED
        result.completed_at = time.time()
        result.processing_time = result.completed_at - result.created_at

    def fail(self, error: str) -> None:
        """作业失败"""
        self.status = PostprocessStatus.FAILED
        if self.result:
            self.result.status = PostprocessStatus.FAILED
            self.result.error_message = error
            self.result.completed_at = time.time()

# ============================================================================
# Phase 3 Output
# ============================================================================

@dataclass
class Phase3Output:
    """Phase 3 输出"""
    output_id: str = field(default_factory=lambda: f"P3-OUTPUT-{uuid.uuid4().hex[:8]}")
    input_knowledge: Optional[CompiledKnowledge] = None
    physics_plan: Optional[PhysicsPlan] = None
    mesh_result: Optional[MeshResult] = None
    solver_jobs: List[SolverJob] = field(default_factory=list)
    postprocess_job: Optional[PostprocessJob] = None
    scheduler_state: Optional[SchedulerState] = None
    created_at: float = field(default_factory=time.time)

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        summary = {
            "output_id": self.output_id,
            "n_jobs": len(self.solver_jobs),
            "completed": sum(1 for j in self.solver_jobs if j.status == SolverStatus.COMPLETED),
            "failed": sum(1 for j in self.solver_jobs if j.status == SolverStatus.FAILED),
            "running": sum(1 for j in self.solver_jobs if j.status == SolverStatus.RUNNING),
            "pending": sum(1 for j in self.solver_jobs if j.status == SolverStatus.PENDING),
        }
        if self.postprocess_job:
            summary["postprocess_status"] = self.postprocess_job.status.value
            if self.postprocess_job.result:
                summary["n_artifacts"] = len(self.postprocess_job.result.artifacts)
        return summary


# ============================================================================
# Factory Functions
# ============================================================================

def create_phase3_output(
    input_knowledge: CompiledKnowledge,
) -> Phase3Output:
    """创建 Phase 3 输出"""
    return Phase3Output(input_knowledge=input_knowledge)


def create_solver_job(
    case_dir: str,
    solver_type: SolverType = SolverType.OPENFOAM,
    priority: JobPriority = JobPriority.MEDIUM,
) -> SolverJob:
    """创建求解器作业"""
    config = SolverConfig(
        solver_type=solver_type,
        executable_path=get_solver_executable(solver_type),
    )
    input_data = SolverInput(
        case_dir=case_dir,
        mesh_dir=f"{case_dir}/constant/polyMesh",
        solver_config=config,
    )
    return SolverJob(input=input_data, priority=priority)


def get_solver_executable(solver_type: SolverType) -> str:
    """获取求解器可执行文件路径"""
    executables = {
        SolverType.OPENFOAM: "simpleFoam",
        SolverType.SU2: "SU2_CFD",
    }
    return executables.get(solver_type, "")


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Enums
    "SolverType",
    "SolverStatus",
    "MeshFormat",
    "MeshQuality",
    "JobPriority",
    # Solver Runner
    "SolverConfig",
    "BoundaryCondition",
    "SolverInput",
    "SolverResult",
    "SolverJob",
    # Mesh Builder
    "MeshConfig",
    "MeshStatistics",
    "MeshResult",
    # Physics Planner
    "PhysicsModel",
    "PhysicsPlan",
    # CAD Parser
    "GeometryFeature",
    "ParsedGeometry",
    # Job Scheduler
    "ScheduledJob",
    "SchedulerState",
    # Postprocess Runner
    "PostprocessStatus",
    "PostprocessFormat",
    "PostprocessArtifact",
    "PostprocessResult",
    "PostprocessRequest",
    "PostprocessJob",
    # Phase 3 Output
    "Phase3Output",
    # Factory functions
    "create_phase3_output",
    "create_solver_job",
    "get_solver_executable",
]
