#!/usr/bin/env python3
"""
Task Builder - Phase3 Task Decomposition
Phase 3: Knowledge-Driven Orchestrator

Converts natural language queries into executable CFD DAGs.
Extends task_wizard.py with DAG output capability.
"""

from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field

from knowledge_compiler.orchestrator.contract import TaskIntent, RunContext


@dataclass
class DAGNode:
    """A node in the executable DAG."""
    id: str
    name: str
    component: str  # ICADParser, IPhysicsPlanner, IMeshBuilder, etc.
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutableDAG:
    """
    Executable Directed Acyclic Graph representing CFD workflow.

    Example flow:
    1. Parse Geometry (CAD Parser)
    2. Plan Physics (Physics Planner)
    3. Generate Mesh (Mesh Builder)
    4. Run Solver (Solver Runner)
    5. Monitor (Monitor)
    6. Verify Results (Verify Console)
    """

    nodes: List[DAGNode] = field(default_factory=list)
    edges: List[tuple[str, str]] = field(default_factory=list)

    def add_node(self, node: DAGNode) -> None:
        """Add a node to the DAG."""
        self.nodes.append(node)

    def add_edge(self, from_id: str, to_id: str) -> None:
        """Add a dependency edge from_id -> to_id."""
        self.edges.append((from_id, to_id))

    def topological_sort(self) -> List[DAGNode]:
        """Return nodes in topological order."""
        # Simple Kahn's algorithm
        in_degree = {node.id: 0 for node in self.nodes}
        for frm, to in self.edges:
            in_degree[to] += 1

        queue = [node for node in self.nodes if in_degree[node.id] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for _, to in self.edges:
                if frm == node.id:
                    in_degree[to] -= 1
                    if in_degree[to] == 0:
                        queue.append(self._get_node(to))

        return result

    def _get_node(self, node_id: str) -> DAGNode:
        """Get node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise ValueError(f"Node {node_id} not found")


class TaskBuilder:
    """
    Task Builder: converts natural language to executable CFD DAG.

    Extends task_wizard.py functionality with DAG output.
    """

    def __init__(self):
        self.wizard_path = Path(__file__).parent.parent.parent / "task_wizard.py"

    def parse_intent(self, query: str) -> TaskIntent:
        """
        Parse natural language query into structured intent.

        This extends the existing task_wizard.py parsing.
        """
        # Import and use existing wizard
        import sys
        sys.path.insert(0, str(self.wizard_path.parent))

        try:
            from task_wizard import parse_query
            parsed = parse_query(query)
        except ImportError:
            parsed = {
                "case_type": "generic",
                "geometry": "unknown",
                "physics": "unknown",
            }

        return TaskIntent(
            user_query=query,
            parsed_goals=[parsed.get("case_type", "generic")],
            constraints=[],
            priority="P1"
        )

    def build_dag(self, intent: TaskIntent) -> ExecutableDAG:
        """
        Build executable Directed Acyclic Graph from intent.

        Maps parsed intent to orchestrator components.
        """
        dag = ExecutableDAG()

        # Standard CFD workflow nodes
        dag.add_node(DAGNode(id="n1", name="Parse Geometry", component="ICADParser"))
        dag.add_node(DAGNode(id="n2", name="Plan Physics", component="IPhysicsPlanner"))
        dag.add_node(DAGNode(id="n3", name="Generate Mesh", component="IMeshBuilder"))
        dag.add_node(DAGNode(id="n4", name="Run Solver", component="ISolverRunner"))
        dag.add_node(DAGNode(id="n5", name="Monitor", component="IMonitor"))
        dag.add_node(DAGNode(id="n6", name="Verify", component="IVerifyConsole"))

        # Standard workflow edges
        dag.add_edge("n1", "n2")  # Geometry -> Physics
        dag.add_edge("n2", "n3")  # Physics -> Mesh
        dag.add_edge("n3", "n4")  # Mesh -> Solver
        dag.add_edge("n4", "n5")  # Solver -> Monitor
        dag.add_edge("n5", "n6")  # Monitor -> Verify

        return dag


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for task building."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Build CFD task from natural language")
    parser.add_argument("query", help="Natural language query")
    parser.add_argument("--output", default="dag.json", help="Output DAG JSON")

    args = parser.parse_args()

    builder = TaskBuilder()
    intent = builder.parse_intent(args.query)
    dag = builder.build_dag(intent)

    # Export DAG as JSON
    dag_data = {
        "nodes": [
            {
                "id": n.id,
                "name": n.name,
                "component": n.component,
                "dependencies": n.dependencies,
                "parameters": n.parameters
            }
            for n in dag.nodes
        ],
        "edges": dag.edges,
        "execution_order": [n.id for n in dag.topological_sort()]
    }

    with open(args.output, "w") as f:
        json.dump(dag_data, f, indent=2)

    print(f"DAG created with {len(dag.nodes)} nodes")
    print(f"Execution order: {' → '.join(dag_data['execution_order'])}")
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()
