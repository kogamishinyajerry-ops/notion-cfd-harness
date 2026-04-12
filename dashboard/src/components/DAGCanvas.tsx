import { useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import PipelineStepNode from './PipelineStepNode';
import NodeDetailDrawer from './NodeDetailDrawer';
import type { PipelineStep, PipelineConfig } from '../services/types';

const nodeTypes = { pipelineStepNode: PipelineStepNode };

const STEP_TYPE_DURATION_MS: Record<string, number> = {
  generate: 60000,
  run: 300000,
  monitor: 600000,
  visualize: 120000,
  report: 60000,
};

interface DAGCanvasProps {
  steps: PipelineStep[];
  config: PipelineConfig;
  selectedStepId: string | null;
  onNodeClick: (step: PipelineStep) => void;
  onCloseDrawer: () => void;
}

function buildDagreLayout(steps: PipelineStep[]): { nodes: Node[]; edges: Edge[] } {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: 'TB', nodesep: 80, ranksep: 120 });

  steps.forEach((step) => {
    dagreGraph.setNode(step.id, { width: 200, height: 80 });
  });

  const dag: Record<string, string[]> = {};
  steps.forEach((step) => {
    if (!dag[step.id]) dag[step.id] = [];
    step.depends_on.forEach((dep) => {
      dagreGraph.setEdge(dep, step.id);
      dag[step.id].push(dep);
    });
  });

  dagre.layout(dagreGraph);

  const nodes: Node[] = steps.map((step) => {
    const nodeInfo = dagreGraph.node(step.id);
    return {
      id: step.id,
      type: 'pipelineStepNode',
      position: { x: nodeInfo.x - 100, y: nodeInfo.y - 40 },
      data: {
        step,
        isStale: isStepStale(step),
      },
    };
  });

  const edges: Edge[] = [];
  steps.forEach((step) => {
    step.depends_on.forEach((dep) => {
      edges.push({
        id: `${dep}-${step.id}`,
        source: dep,
        target: step.id,
        type: 'smoothstep',
        animated: step.status === 'RUNNING',
        style: { stroke: 'var(--border-color)' },
      });
    });
  });

  return { nodes, edges };
}

function isStepStale(step: PipelineStep): boolean {
  if (step.status !== 'RUNNING' || !step.started_at) return false;
  const threshold = STEP_TYPE_DURATION_MS[step.step_type] ?? 300000;
  return Date.now() - new Date(step.started_at).getTime() > threshold;
}

export default function DAGCanvas({
  steps,
  config,
  selectedStepId,
  onNodeClick,
  onCloseDrawer,
}: DAGCanvasProps) {
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () => buildDagreLayout(steps),
    [steps]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);

  // Sync layout nodes with step data (status, result) on each render
  const updatedNodes = useMemo(() => {
    return nodes.map((n) => {
      const step = steps.find((s) => s.id === n.id);
      if (!step) return n;
      return {
        ...n,
        data: { step, isStale: isStepStale(step) },
      };
    });
  }, [nodes, steps]);

  const selectedStep = steps.find((s) => s.id === selectedStepId) ?? null;

  if (steps.length === 0) {
    return (
      <div className="dag-empty">
        <p className="dag-empty-heading">No steps defined</p>
        <p>This pipeline has no steps. Add steps from the pipeline creation page.</p>
      </div>
    );
  }

  return (
    <>
      <div className="dag-canvas-wrapper">
        <ReactFlow
          nodes={updatedNodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.2}
          maxZoom={2}
          onNodeClick={(_evt, node) => {
            const step = steps.find((s) => s.id === node.id);
            if (step) onNodeClick(step);
          }}
        >
          <Background />
          <Controls />
          <MiniMap
            nodeColor={(n) => {
              const step = steps.find((s) => s.id === n.id);
              if (!step) return 'var(--color-pending)';
              return `var(--color-${step.status.toLowerCase()})`;
            }}
          />
        </ReactFlow>
      </div>
      <NodeDetailDrawer step={selectedStep} onClose={onCloseDrawer} />
    </>
  );
}
