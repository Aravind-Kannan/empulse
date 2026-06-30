"use client";

import { useMemo } from "react";

export interface DebugGraphNode {
  id: string;
  label: string;
  type: string;
}

export interface DebugGraphEdge {
  source: string;
  target: string;
  relationship: string;
}

const NODE_COLORS: Record<string, { fill: string; stroke: string }> = {
  person: { fill: "#0c4a6e", stroke: "#38bdf8" },
  document: { fill: "#3b0764", stroke: "#c084fc" },
  system: { fill: "#431407", stroke: "#fb923c" },
};

interface SimulationGraphMapProps {
  nodes: DebugGraphNode[];
  edges: DebugGraphEdge[];
}

function layoutNodes(nodes: DebugGraphNode[]) {
  const columns: Record<string, DebugGraphNode[]> = {
    person: [],
    document: [],
    system: [],
  };
  for (const node of nodes) {
    (columns[node.type] ?? columns.document).push(node);
  }

  const positioned: Array<DebugGraphNode & { x: number; y: number }> = [];
  const xByType = { person: 120, document: 420, system: 720 };
  for (const [type, group] of Object.entries(columns)) {
    group.forEach((node, index) => {
      positioned.push({
        ...node,
        x: xByType[type as keyof typeof xByType] ?? 420,
        y: 80 + index * 90,
      });
    });
  }
  return positioned;
}

export function SimulationGraphMap({ nodes, edges }: SimulationGraphMapProps) {
  const positioned = useMemo(() => layoutNodes(nodes), [nodes]);
  const positionById = useMemo(
    () => new Map(positioned.map((node) => [node.id, node])),
    [positioned],
  );

  if (nodes.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-zinc-800 text-sm text-zinc-500">
        Run the simulation to visualize extracted graph entities.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950/60">
      <svg viewBox="0 0 900 520" className="h-[520px] w-full">
        {edges.map((edge, index) => {
          const source = positionById.get(edge.source);
          const target = positionById.get(edge.target);
          if (!source || !target) return null;
          const midX = (source.x + target.x) / 2;
          const midY = (source.y + target.y) / 2;
          return (
            <g key={`${edge.source}-${edge.target}-${index}`}>
              <line
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke="#52525b"
                strokeWidth={1.5}
                markerEnd="url(#arrow)"
              />
              <text
                x={midX}
                y={midY - 6}
                textAnchor="middle"
                className="fill-zinc-500 text-[9px]"
              >
                {edge.relationship}
              </text>
            </g>
          );
        })}

        <defs>
          <marker
            id="arrow"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L6,3 L0,6 Z" fill="#71717a" />
          </marker>
        </defs>

        {positioned.map((node) => {
          const colors = NODE_COLORS[node.type] ?? NODE_COLORS.document;
          return (
            <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
              <circle
                r={26}
                fill={colors.fill}
                stroke={colors.stroke}
                strokeWidth={2}
              />
              <text
                textAnchor="middle"
                y={4}
                className="fill-zinc-100 text-[9px] font-medium"
              >
                {node.label.length > 16
                  ? `${node.label.slice(0, 14)}…`
                  : node.label}
              </text>
              <text
                textAnchor="middle"
                y={42}
                className="fill-zinc-500 text-[8px] uppercase"
              >
                {node.type}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
