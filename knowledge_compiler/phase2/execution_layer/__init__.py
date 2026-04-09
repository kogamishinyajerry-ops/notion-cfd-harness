#!/usr/bin/env python3
"""
Phase 2 Execution Layer

执行层 - 物理规划、求解器配置、作业调度、结果验证、失败处理、后处理。
"""

# Schema
from knowledge_compiler.phase2.execution_layer.schema import (
    # Enums
    FlowType,
    TurbulenceModel,
    TimeTreatment,
    Compressibility,
    BCType,
    SolverType,
    ProblemType,
    ConvergenceType,
    # Core classes
    PhysicsModel,
    BoundaryCondition,
    ConvergenceCriterion,
    PhysicsPlan,
    # Decision matrix
    SolverSelectionMatrix,
    select_solver_by_matrix,
    # Validation
    BCCombinationRule,
    BC_VALIDATION_RULES,
    validate_boundary_conditions,
    # Convergence
    is_converged,
    get_default_convergence_criteria,
    # Factory
    create_physics_plan,
    infer_physics_from_params,
)

# Planner
from knowledge_compiler.phase2.execution_layer.planner import (
    PhysicsPlanner,
    plan_from_case,
)

# Result Validator
from knowledge_compiler.phase2.execution_layer.result_validator import (
    ValidationStatus,
    AnomalyType,
    Anomaly,
    ValidationResult,
    ResultValidator,
    validate_solver_result,
    validate_field_data,
    validate_mesh_quality,
)

# Failure Handler
from knowledge_compiler.phase2.execution_layer.failure_handler import (
    PermissionLevel,
    FailureAction,
    FailureCategory,
    FailureContext,
    FailureHandlingResult,
    FailureAnalyzer,
    FailureHandler,
    RetryHandler,
    GateReporter,
    CorrectionSpecGenerator,
    handle_failure,
    should_retry,
)

# Postprocess Runner
from knowledge_compiler.phase2.execution_layer.postprocess_runner import (
    FieldType,
    FieldData,
    ResidualSummary,
    DerivedQuantity,
    StandardPostprocessResult,
    PostprocessStatus,
    FieldDataExtractor,
    ResidualParser,
    DerivedQuantityCalculator,
    PostprocessRunner,
    run_postprocess,
    extract_field_data,
)

# Postprocess Adapter
from knowledge_compiler.phase2.execution_layer.postprocess_adapter import (
    VisualizationType,
    PlotData,
    ComparisonData,
    NLPostprocessInput,
    PostprocessAdapter,
    VisualizationTemplate,
    TemplateRegistry,
    TemplatePostprocessAdapter,
    adapt_for_nl_postprocess,
    apply_template,
)

# Solver Execution
from knowledge_compiler.phase2.execution_layer.solver_protocol import (
    SolverExecutor,
    SolverResult,
)
from knowledge_compiler.phase2.execution_layer.mock_solver import (
    MockSolverExecutor,
    simulate_benchmark_output,
)
from knowledge_compiler.phase2.execution_layer.executor_factory import (
    ExecutorFactory,
)
from knowledge_compiler.phase2.execution_layer.case_generator import (
    OpenFOAMCaseGenerator,
)
from knowledge_compiler.phase2.execution_layer.openfoam_docker import (
    OpenFOAMDockerExecutor,
)

__all__ = [
    # Schema
    "FlowType",
    "TurbulenceModel",
    "TimeTreatment",
    "Compressibility",
    "BCType",
    "SolverType",
    "ProblemType",
    "ConvergenceType",
    "PhysicsModel",
    "BoundaryCondition",
    "ConvergenceCriterion",
    "PhysicsPlan",
    "SolverSelectionMatrix",
    "select_solver_by_matrix",
    "BCCombinationRule",
    "BC_VALIDATION_RULES",
    "validate_boundary_conditions",
    "is_converged",
    "get_default_convergence_criteria",
    "create_physics_plan",
    "infer_physics_from_params",
    # Planner
    "PhysicsPlanner",
    "plan_from_case",
    # Result Validator
    "ValidationStatus",
    "AnomalyType",
    "Anomaly",
    "ValidationResult",
    "ResultValidator",
    "validate_solver_result",
    "validate_field_data",
    "validate_mesh_quality",
    # Failure Handler
    "PermissionLevel",
    "FailureAction",
    "FailureCategory",
    "FailureContext",
    "FailureHandlingResult",
    "FailureAnalyzer",
    "FailureHandler",
    "RetryHandler",
    "GateReporter",
    "CorrectionSpecGenerator",
    "handle_failure",
    "should_retry",
    # Postprocess Runner
    "FieldType",
    "FieldData",
    "ResidualSummary",
    "DerivedQuantity",
    "StandardPostprocessResult",
    "PostprocessStatus",
    "FieldDataExtractor",
    "ResidualParser",
    "DerivedQuantityCalculator",
    "PostprocessRunner",
    "run_postprocess",
    "extract_field_data",
    # Postprocess Adapter
    "VisualizationType",
    "PlotData",
    "ComparisonData",
    "NLPostprocessInput",
    "PostprocessAdapter",
    "VisualizationTemplate",
    "TemplateRegistry",
    "TemplatePostprocessAdapter",
    "adapt_for_nl_postprocess",
    "apply_template",
    # Solver Execution
    "SolverExecutor",
    "SolverResult",
    "MockSolverExecutor",
    "simulate_benchmark_output",
    "ExecutorFactory",
    "OpenFOAMCaseGenerator",
    "OpenFOAMDockerExecutor",
]
