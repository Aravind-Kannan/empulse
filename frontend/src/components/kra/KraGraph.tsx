"use client";

import { useMemo } from "react";
import { AlertTriangle } from "lucide-react";

import type { KraAnalyticsResponse, KraNode } from "@/lib/types";

interface PositionedNode extends KraNode {
  x: number;
  y: number;
}

interface KraGraphProps {
  graph: KraAnalyticsResponse;
  selectedComponentId: string | null;
  onSelectComponent: (node: KraNode) => void;
  /** When set, only these component IDs get critical-SPOF highlight (filter mode). */
  highlightCriticalSpofIds?: Set<string> | null;
}

function layoutNodes(graph: KraAnalyticsResponse): PositionedNode[] {
  const engineers = graph.nodes.filter((n) => n.type === "engineer");
  const components = graph.nodes.filter((n) => n.type === "component");
  const width = 900;
  const height = 520;
  const padding = 70;

  const positioned: PositionedNode[] = [];

  engineers.forEach((node, index) => {
    const y =
      padding +
      (index * (height - padding * 2)) / Math.max(engineers.length - 1, 1);
    positioned.push({ ...node, x: 160, y });
  });

  components.forEach((node, index) => {
    const y =
      padding +
      (index * (height - padding * 2)) / Math.max(components.length - 1, 1);
    positioned.push({ ...node, x: width - 160, y });
  });

  return positioned;
}

export function KraGraph({
  graph,
  selectedComponentId,
  onSelectComponent,
  highlightCriticalSpofIds = null,
}: KraGraphProps) {
  const filterActive = highlightCriticalSpofIds != null;
  const positioned = useMemo(() => layoutNodes(graph), [graph]);
  const positionById = useMemo(
    () => new Map(positioned.map((node) => [node.id, node])),
    [positioned],
  );

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/30">
      <svg viewBox="0 0 900 520" className="h-[520px] w-full">
        <defs>
          <filter id="spof-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="critical-spof-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {graph.links.map((link) => {
          const source = positionById.get(link.source);
          const target = positionById.get(link.target);
          if (!source || !target) return null;

          const targetDimmed =
            filterActive &&
            target.type === "component" &&
            !highlightCriticalSpofIds.has(target.id);

          return (
            <line
              key={`${link.source}-${link.target}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke="#52525b"
              strokeWidth={2}
              strokeOpacity={targetDimmed ? 0.2 : 0.8}
            />
          );
        })}

        {positioned.map((node) => {
          const isSelected =
            node.type === "component" && node.id === selectedComponentId;
          const isCriticalSpof =
            node.type === "component" &&
            filterActive &&
            highlightCriticalSpofIds.has(node.id);
          const isStructuralSpof =
            node.type === "component" && node.is_spof && !filterActive;
          const isSpof = isCriticalSpof || isStructuralSpof;
          const dimmed =
            filterActive &&
            node.type === "component" &&
            !highlightCriticalSpofIds.has(node.id);

          if (node.type === "engineer") {
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                opacity={filterActive ? 0.35 : 1}
              >
                <circle
                  r={28}
                  fill="#1e293b"
                  stroke="#38bdf8"
                  strokeWidth={2}
                />
                <text
                  textAnchor="middle"
                  y={5}
                  className="fill-zinc-100 text-[11px] font-medium"
                >
                  {node.label.split(" ")[0]}
                </text>
                <text
                  textAnchor="middle"
                  y={48}
                  className="fill-zinc-500 text-[10px]"
                >
                  {node.role}
                </text>
              </g>
            );
          }

          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              className="cursor-pointer"
              opacity={dimmed ? 0.25 : 1}
              onClick={() => onSelectComponent(node)}
            >
              <rect
                x={-42}
                y={-32}
                width={84}
                height={64}
                rx={8}
                fill={
                  isCriticalSpof ? "#450a0a" : isStructuralSpof ? "#431407" : "#27272a"
                }
                stroke={
                  isCriticalSpof
                    ? "#f87171"
                    : isStructuralSpof
                      ? "#fb923c"
                      : isSelected
                        ? "#a1a1aa"
                        : "#71717a"
                }
                strokeWidth={isSpof || isSelected ? 3 : 2}
                filter={
                  isCriticalSpof
                    ? "url(#critical-spof-glow)"
                    : isStructuralSpof
                      ? "url(#spof-glow)"
                      : undefined
                }
              />
              {isCriticalSpof && (
                <text
                  x={0}
                  y={-42}
                  textAnchor="middle"
                  className="fill-red-400 text-[10px] font-semibold"
                >
                  Critical SPOF
                </text>
              )}
              {isStructuralSpof && !isCriticalSpof && (
                <text
                  x={0}
                  y={-42}
                  textAnchor="middle"
                  className="fill-orange-400 text-[10px] font-semibold"
                >
                  {node.github_verified_spof ? "GitHub SPOF" : "SPOF"}
                </text>
              )}
              <text
                textAnchor="middle"
                y={4}
                className={`text-[10px] font-medium ${
                  isCriticalSpof
                    ? "fill-red-200"
                    : isStructuralSpof
                      ? "fill-orange-200"
                      : "fill-zinc-100"
                }`}
              >
                {node.label.length > 14
                  ? `${node.label.slice(0, 12)}…`
                  : node.label}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="flex flex-wrap items-center gap-4 border-t border-zinc-800 px-4 py-3 text-xs text-zinc-500">
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-3 rounded-full border-2 border-sky-400" />
          Engineer
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-3 rounded border-2 border-zinc-500" />
          Component
        </span>
        {filterActive ? (
          <span className="inline-flex items-center gap-1 text-red-400">
            <AlertTriangle className="h-3 w-3" />
            Critical SPOF (tier-1, no backup)
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-orange-400">
            <AlertTriangle className="h-3 w-3" />
            Single Point of Failure
          </span>
        )}
      </div>
    </div>
  );
}
