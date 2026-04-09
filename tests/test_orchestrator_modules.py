#!/usr/bin/env python3
"""
Tests for untested orchestrator modules:
- task_builder.py: ExecutableDAG, DAGNode
- verify_console.py: VerifyConsole
- interfaces.py: Protocol interfaces
"""

import pytest
from knowledge_compiler.orchestrator.task_builder import DAGNode, ExecutableDAG, TaskBuilder
from knowledge_compiler.orchestrator.interfaces import (
    ITaskBuilder,
    ICADParser,
    IPhysicsPlanner,
    IMeshBuilder,
    ISolverRunner,
    IMonitor,
)
from knowledge_compiler.orchestrator.verify_console import VerifyConsole, ChartType, BenchmarkResult


# ============================================================================
# task_builder: ExecutableDAG and DAGNode Tests
# ============================================================================

class TestDAGNode:
    """Tests for DAGNode dataclass"""

    def test_node_creation(self):
        """Node can be created with required fields"""
        node = DAGNode(id="node1", name="CAD Parser", component="ICADParser")
        assert node.id == "node1"
        assert node.name == "CAD Parser"
        assert node.component == "ICADParser"

    def test_node_with_dependencies(self):
        """Node can include dependencies"""
        node = DAGNode(
            id="node2",
            name="Physics Planner",
            component="IPhysicsPlanner",
            dependencies=["node1"],
        )
        assert node.dependencies == ["node1"]

    def test_node_with_parameters(self):
        """Node can include parameters"""
        node = DAGNode(
            id="node3",
            name="Solver",
            component="ISolverRunner",
            parameters={"solver": "simpleFoam", "n_iterations": 500},
        )
        assert node.parameters["solver"] == "simpleFoam"
        assert node.parameters["n_iterations"] == 500


class TestExecutableDAG:
    """Tests for ExecutableDAG"""

    def test_empty_dag(self):
        """Empty DAG can be created"""
        dag = ExecutableDAG()
        assert dag.nodes == []
        assert dag.edges == []

    def test_add_node(self):
        """Nodes can be added to DAG"""
        dag = ExecutableDAG()
        node = DAGNode(id="n1", name="Step 1", component="Test")
        dag.add_node(node)
        assert len(dag.nodes) == 1
        assert dag.nodes[0].id == "n1"

    def test_add_edge(self):
        """Edges can be added to DAG"""
        dag = ExecutableDAG()
        dag.add_edge("n1", "n2")
        assert ("n1", "n2") in dag.edges

    def test_linear_order(self):
        """Linear DAG (1->2->3) produces correct topological order"""
        dag = ExecutableDAG()
        dag.add_node(DAGNode(id="n1", name="First", component="A"))
        dag.add_node(DAGNode(id="n2", name="Second", component="B"))
        dag.add_node(DAGNode(id="n3", name="Third", component="C"))
        dag.add_edge("n1", "n2")
        dag.add_edge("n2", "n3")

        order = dag.topological_sort()
        ids = [n.id for n in order]
        assert ids == ["n1", "n2", "n3"]

    def test_parallel_branches(self):
        """Parallel DAG produces correct topological order"""
        dag = ExecutableDAG()
        dag.add_node(DAGNode(id="root", name="Root", component="A"))
        dag.add_node(DAGNode(id="branch1", name="Branch 1", component="B"))
        dag.add_node(DAGNode(id="branch2", name="Branch 2", component="C"))
        dag.add_node(DAGNode(id="merge", name="Merge", component="D"))
        dag.add_edge("root", "branch1")
        dag.add_edge("root", "branch2")
        dag.add_edge("branch1", "merge")
        dag.add_edge("branch2", "merge")

        order = dag.topological_sort()
        ids = [n.id for n in order]
        assert ids[0] == "root"
        assert ids[-1] == "merge"
        assert ids.index("branch1") < ids.index("merge")
        assert ids.index("branch2") < ids.index("merge")

    def test_get_node(self):
        """_get_node retrieves correct node"""
        dag = ExecutableDAG()
        dag.add_node(DAGNode(id="node1", name="N1", component="A"))
        dag.add_node(DAGNode(id="node2", name="N2", component="B"))

        retrieved = dag._get_node("node1")
        assert retrieved.name == "N1"

    def test_get_node_not_found_raises(self):
        """_get_node raises ValueError for unknown node"""
        dag = ExecutableDAG()
        dag.add_node(DAGNode(id="node1", name="N1", component="A"))

        with pytest.raises(ValueError, match="not found"):
            dag._get_node("nonexistent")


# ============================================================================
# verify_console: VerifyConsole Tests
# ============================================================================

class TestVerifyConsole:
    """Tests for VerifyConsole"""

    def test_verify_console_creation(self):
        """VerifyConsole can be created"""
        console = VerifyConsole()
        assert console is not None

    def test_chart_type_values(self):
        """ChartType enum has expected values"""
        assert ChartType.VELOCITY_PROFILE in ChartType
        assert ChartType.PRESSURE_CONTOUR in ChartType
        assert ChartType.GCI_CONVERGENCE in ChartType

    def test_benchmark_result_creation(self):
        """BenchmarkResult can be created"""
        result = BenchmarkResult(
            benchmark_id="CASE-001",
            validator_used="test_validator",
            is_passed=True,
        )
        assert result.benchmark_id == "CASE-001"
        assert result.is_passed is True

    def test_benchmark_result_with_errors(self):
        """BenchmarkResult supports error metrics"""
        result = BenchmarkResult(
            benchmark_id="BENCH-04",
            validator_used="test",
            is_passed=False,
            error_metrics={"velocity_error": 0.15},
        )
        assert result.error_metrics["velocity_error"] == 0.15


# ============================================================================
# interfaces: Protocol Tests
# ============================================================================

class TestInterfaces:
    """Tests for orchestrator Protocol interfaces"""

    def test_task_builder_protocol_exists(self):
        """ITaskBuilder protocol is defined"""
        assert ITaskBuilder is not None

    def test_cad_parser_protocol_exists(self):
        """ICADParser protocol is defined"""
        assert ICADParser is not None

    def test_physics_planner_protocol_exists(self):
        """IPhysicsPlanner protocol is defined"""
        assert IPhysicsPlanner is not None

    def test_mesh_builder_protocol_exists(self):
        """IMeshBuilder protocol is defined"""
        assert IMeshBuilder is not None

    def test_solver_runner_protocol_exists(self):
        """ISolverRunner protocol is defined"""
        assert ISolverRunner is not None

    def test_monitor_protocol_exists(self):
        """IMonitor protocol is defined"""
        assert IMonitor is not None

    def test_protocols_are_protocols(self):
        """All interfaces are actual Protocol types"""
        for proto in [ITaskBuilder, ICADParser, IPhysicsPlanner]:
            assert getattr(proto, "_is_protocol", False) is True


# ============================================================================
# TaskBuilder Tests
# ============================================================================

class TestTaskBuilder:
    """Tests for TaskBuilder class"""

    def test_task_builder_creation(self):
        """TaskBuilder can be created"""
        builder = TaskBuilder()
        assert builder is not None
        assert builder.wizard_path is not None

    def test_wizard_path_is_path(self):
        """TaskBuilder wizard_path is a valid Path"""
        builder = TaskBuilder()
        assert str(builder.wizard_path).endswith("task_wizard.py")
