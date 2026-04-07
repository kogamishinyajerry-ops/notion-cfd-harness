#!/usr/bin/env python3
"""
Knowledge Compiler Orchestrator Contract Definitions
Phase 3: Knowledge-Driven Orchestrator

Core data structures for orchestrating CFD workflow execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, Protocol
from pathlib import Path


# =============================================================================
# 1. Execution Context
# =============================================================================

@dataclass
class RunContext:
    """
    Execution context for a single orchestrator run.

    Attributes:
        baseline_ref: Git commit hash or baseline manifest path
        config: Configuration overrides
        state: Current execution state
        start_time: Run start timestamp
    """
    baseline_ref: str
    config: Dict[str, Any] = field(default_factory=dict)
    state: str = "initialized"  # initialized | running | completed | failed
    start_time: datetime = field(default_factory=datetime.now)
    workspace_root: Path = field(default_factory=lambda: Path.cwd())


# =============================================================================
# 2. Task Intent
# =============================================================================

@dataclass
class TaskIntent:
    """
    Parsed user task intent.

    Attributes:
        user_query: Original natural language query
        parsed_goals: Extracted execution goals
        constraints: User-specified constraints
        priority: Task priority (P0/P1/P2/P3)
    """
    user_query: str
    parsed_goals: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    priority: str = "P1"

    # References to knowledge units
    required_chapters: List[str] = field(default_factory=list)  # From chapters.yaml
    required_formulas: List[str] = field(default_factory=list)  # From formulas.yaml
    required_cases: List[str] = field(default_factory=list)     # From data_points.yaml


# =============================================================================
# 3. Geometry Semantic Model
# =============================================================================

@dataclass
class BoundaryCondition:
    """Boundary condition definition."""
    name: str
    type: str  # wall/inlet/outlet/symmetry/periodic
    value: Optional[float] = None
    profile: Optional[str] = None  # e.g. "uniform", "parabolic"


@dataclass
class Region:
    """Geometric region definition."""
    name: str
    shape: str  # box/cylinder/sphere/custom
    bounds: Dict[str, float]  # x_min, x_max, etc.
    mesh_refinement: str = "medium"  # coarse/medium/fine


@dataclass
class CoordinateSystem:
    """Coordinate system definition."""
    origin: List[float]  # [x, y, z]
    axes: Dict[str, List[float]]  # {"x": [1,0,0], "y": [0,1,0], ...}
    unit: str = "m"


@dataclass
class GeometrySemanticModel:
    """
    Semantic model of CFD geometry.

    References chapters.yaml (CH-001: Geometry, CH-003-1: Boundary Conditions)
    """
    name: str
    dimensions: Dict[str, float]  # Characteristic lengths: L, H, D, etc.
    coordinate_system: CoordinateSystem
    regions: List[Region] = field(default_factory=list)
    boundaries: List[BoundaryCondition] = field(default_factory=list)

    # Reference to knowledge units
    chapter_ref: str = "CH-001"
    boundary_ref: str = "CH-003-1"


# =============================================================================
# 4. Physics Plan
# =============================================================================

class TurbulenceModel(Enum):
    """Common turbulence models."""
    K_EPSILON = "k-epsilon"
    K_OMEGA_SST = "k-omega SST"
    SPALART_ALLMARAS = "Spalart-Allmaras"
    LES = "LES"
    DNS = "DNS"
    LAMINAR = "laminar"


@dataclass
class MonitorPoint:
    """Point/region to monitor during simulation."""
    name: str
    type: str  # point/line/surface/volume
    location: List[float]  # [x, y, z]
    target_quantity: str  # pressure/velocity/temperature/etc.


@dataclass
class PhysicsPlan:
    """
    CFD physics simulation plan.

    References formulas.yaml and data_points.yaml for validation.
    """
    model: str  # Solver name: icoFoam, simpleFoam, pimpleFoam, etc.
    turbulence: TurbulenceModel
    fluid_properties: Dict[str, float] = field(default_factory=dict)  # rho, mu, etc.

    # Initial and boundary conditions
    initial_conditions: Dict[str, float] = field(default_factory=dict)
    boundary_conditions: Dict[str, BoundaryCondition] = field(default_factory=dict)

    # Monitoring
    monitors: List[MonitorPoint] = field(default_factory=list)
    convergence_criteria: Dict[str, float] = field(default_factory=dict)

    # Validation references
    validation_case_id: Optional[str] = None  # CASE-001, CASE-002
    validation_ref: Optional[str] = None  # Reference to data_points.yaml
    acceptance_threshold: float = 5.0  # %


# =============================================================================
# 5. Mesh Plan
# =============================================================================

@dataclass
class MeshLevel:
    """Single mesh level definition."""
    name: str  # Coarse/Medium/Fine
    cell_count: int
    max_skewness: float
    aspect_ratio_limit: float
    refinement_factor: float = 2.0


@dataclass
class GCIPlan:
    """Grid Convergence Index plan."""
    target_gci: float = 5.0  # %
    refinement_factor: float = 2.0
    order_of_accuracy: float = 2.0
    monitor_quantity: str = "torque"  # or drag, lift, etc.


@dataclass
class MeshPlan:
    """
    Mesh generation plan.

    References GCI formula (FORM-009) from formulas.yaml.
    """
    base_geometry: str  # Path to CAD or definition
    levels: List[MeshLevel] = field(default_factory=list)
    local_refinements: List[Region] = field(default_factory=list)

    # Grid independence
    gci_plan: GCIPlan = field(default_factory=GCIPlan)

    # Quality targets
    target_cell_count: Optional[int] = None
    max_non_orthogonality: float = 70.0
    max_aspect_ratio: float = 1000.0


# =============================================================================
# 6. Solver Plan
# =============================================================================

class TimeStepping(Enum):
    """Time stepping scheme."""
    STEADY_STATE = "steady"
    TRANSIENT = "transient"
    PISO = "PISO"
    SIMPLE = "SIMPLE"
    PIMPLE = "PIMPLE"


@dataclass
class SolverPlan:
    """
    Solver execution plan.
    """
    solver: str  # OpenFOAM solver name
    scheme: TimeStepping = TimeStepping.STEADY_STATE

    # Time control (for transient)
    time_step: Optional[float] = None
    end_time: Optional[float] = None
    write_interval: Optional[int] = None

    # Numerical schemes
    divergence_scheme: str = "Gauss linear"
    gradient_scheme: str = "Gauss linear"
    interpolation_schemes: Dict[str, str] = field(default_factory=dict)

    # Parallel execution
    num_cores: int = 1
    decompose_method: str = "scotch"


# =============================================================================
# 7. Monitor Report
# =============================================================================

class ConvergenceStatus(Enum):
    """Convergence status."""
    CONVERGED = "converged"
    STALLED = "stalled"
    DIVERGED = "diverged"
    RUNNING = "running"
    FAILED = "failed"


@dataclass
class ConvergenceEvent:
    """Significant convergence event."""
    timestamp: datetime
    iteration: int
    event_type: str  # residual_drop/oscillation/divergence/etc
    quantity: str
    value: float
    message: str = ""


@dataclass
class MonitorReport:
    """
    Simulation monitoring report.
    """
    status: ConvergenceStatus
    iterations: int
    final_residuals: Dict[str, float]
    events: List[ConvergenceEvent] = field(default_factory=list)

    # Monitor quantities
    monitor_values: Dict[str, List[float]] = field(default_factory=dict)

    # Timing
    cpu_time: float = 0.0
    wall_time: float = 0.0


# =============================================================================
# 8. Verification Report
# =============================================================================

class ChartType(Enum):
    """Standard chart types from chart_standards.md."""
    VELOCITY_PROFILE = "velocity_profile"
    PRESSURE_CONTOUR = "pressure_contour"
    GCI_CONVERGENCE = "gci_convergence"


@dataclass
class BenchmarkResult:
    """Benchmark validation result."""
    benchmark_id: str  # CASE-001, CASE-002
    validator_used: str  # bench_ghia1982.py, bench_naca.py
    is_passed: bool
    error_metrics: Dict[str, float] = field(default_factory=dict)
    notes: str = ""


@dataclass
class VerificationReport:
    """
    Result verification report.

    Calls Phase2 executables: formula_validator.py, chart_template.py,
    bench_ghia1982.py, bench_naca.py
    """
    case_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Charts generated
    charts: Dict[ChartType, str] = field(default_factory=dict)  # Chart type -> file path

    # Benchmark validation
    benchmarks: List[BenchmarkResult] = field(default_factory=list)

    # Overall conclusion
    overall_pass: bool = False
    conclusion: str = ""

    # Review flag for Opus
    requires_review: bool = False
    review_reason: str = ""


# =============================================================================
# 9. Component Interface
# =============================================================================

class IOrchestratorComponent(Protocol):
    """Base interface for all orchestrator components."""

    def initialize(self, context: RunContext) -> None:
        """Initialize the component with execution context."""
        ...

    def execute(self, intent: TaskIntent) -> Any:
        """Execute the component's primary function."""
        ...

    def validate(self) -> bool:
        """Validate component state."""
        ...

    def cleanup(self) -> None:
        """Clean up resources."""
        ...


# =============================================================================
# 10. Orchestrator State Machine
# =============================================================================

class OrchestratorState(Enum):
    """Orchestrator execution state."""
    IDLE = "idle"
    PLANNING = "planning"
    PARSING_CAD = "parsing_cad"
    PLANNING_PHYSICS = "planning_physics"
    GENERATING_MESH = "generating_mesh"
    RUNNING_SOLVER = "running_solver"
    MONITORING = "monitoring"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OrchestratorStatus:
    """Current orchestrator status."""
    state: OrchestratorState
    current_task: Optional[str] = None
    progress: float = 0.0  # 0.0 to 1.0
    message: str = ""
    error: Optional[str] = None
