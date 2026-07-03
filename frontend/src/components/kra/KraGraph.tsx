"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";

import type { KraAnalyticsResponse, KraNode } from "@/lib/types";
import {
  formatKraComponentLabel,
  parseGitHubComponentDisplay,
  truncateComponentLabel,
} from "@/lib/github-component-display";

interface PositionedNode extends KraNode {
  x: number;
  y: number;
}

interface GraphLayout {
  nodes: PositionedNode[];
  width: number;
  height: number;
}

interface KraGraphProps {
  graph: KraAnalyticsResponse;
  selectedComponentId: string | null;
  onSelectComponent: (node: KraNode) => void;
  highlightCriticalSpofIds?: Set<string> | null;
}

const MIN_GRAPH_WIDTH = 720;
const MIN_GRAPH_HEIGHT = 280;
/** Scroll viewport cap — layout keeps full node spacing inside viewBox. */
const SCROLL_VIEWPORT_MAX = 560;
const PADDING_Y = 48;
const COLUMN_INSET = 140;
const ENGINEER_MIN_GAP = 88;
const COMPONENT_MIN_GAP = 84;
const ENGINEER_RADIUS = 22;
const COMPONENT_HALF_W = 52;
const COMPONENT_HALF_H = 26;

function columnPositions(count: number, minGap: number, height: number): number[] {
  if (count === 0) return [];
  if (count === 1) return [height / 2];

  const available = height - PADDING_Y * 2;
  const gap = Math.max(minGap, available / (count - 1));
  const totalSpan = (count - 1) * gap;
  const top = (height - totalSpan) / 2;

  return Array.from({ length: count }, (_, index) => top + index * gap);
}

function layoutGraph(graph: KraAnalyticsResponse, graphWidth: number): GraphLayout {
  const engineers = graph.nodes.filter((node) => node.type === "engineer");
  const components = graph.nodes.filter((node) => node.type === "component");
  const engineerX = COLUMN_INSET;
  const componentX = graphWidth - COLUMN_INSET;

  const engineerSpan =
    engineers.length <= 1 ? 0 : (engineers.length - 1) * ENGINEER_MIN_GAP;
  const componentSpan =
    components.length <= 1 ? 0 : (components.length - 1) * COMPONENT_MIN_GAP;
  const height = Math.max(
    MIN_GRAPH_HEIGHT,
    Math.max(engineerSpan, componentSpan, 96) + PADDING_Y * 2,
  );

  const engineerYs = columnPositions(engineers.length, ENGINEER_MIN_GAP, height);
  const componentYs = columnPositions(
    components.length,
    COMPONENT_MIN_GAP,
    height,
  );

  const nodes: PositionedNode[] = [
    ...engineers.map((node, index) => ({
      ...node,
      x: engineerX,
      y: engineerYs[index] ?? height / 2,
    })),
    ...components.map((node, index) => ({
      ...node,
      x: componentX,
      y: componentYs[index] ?? height / 2,
    })),
  ];

  return { nodes, width: graphWidth, height };
}

function linkPath(
  source: PositionedNode,
  target: PositionedNode,
): string {
  const x1 = source.x + (source.type === "engineer" ? ENGINEER_RADIUS : COMPONENT_HALF_W);
  const x2 = target.x - (target.type === "component" ? COMPONENT_HALF_W : ENGINEER_RADIUS);
  const midX = (x1 + x2) / 2;
  return `M ${x1} ${source.y} C ${midX} ${source.y}, ${midX} ${target.y}, ${x2} ${target.y}`;
}

export function KraGraph({
  graph,
  selectedComponentId,
  onSelectComponent,
  highlightCriticalSpofIds = null,
}: KraGraphProps) {
  const uid = useId().replace(/:/g, "");
  const filterSpofId = `kra-spof-glow-${uid}`;
  const filterCriticalId = `kra-critical-spof-glow-${uid}`;
  const dotPatternId = `kra-dots-${uid}`;
  const viewportRef = useRef<HTMLDivElement>(null);
  const [graphWidth, setGraphWidth] = useState(MIN_GRAPH_WIDTH);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;

    const syncWidth = () => {
      setGraphWidth(Math.max(MIN_GRAPH_WIDTH, element.clientWidth));
    };

    syncWidth();
    const observer = new ResizeObserver(syncWidth);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const filterActive = highlightCriticalSpofIds != null;
  const layout = useMemo(
    () => layoutGraph(graph, graphWidth),
    [graph, graphWidth],
  );
  const positionById = useMemo(
    () => new Map(layout.nodes.map((node) => [node.id, node])),
    [layout.nodes],
  );

  const engineerCount = graph.nodes.filter((node) => node.type === "engineer").length;
  const componentCount = graph.nodes.filter((node) => node.type === "component").length;
  const scrollViewportHeight = Math.min(layout.height, SCROLL_VIEWPORT_MAX);

  return (
    <section className="w-full overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-950/80 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)] ring-1 ring-white/[0.03]">
      <div className="flex items-center justify-between border-b border-zinc-800/70 px-4 py-2.5">
        <div>
          <h2 className="text-[13px] font-medium tracking-tight text-zinc-200">
            Ownership map
          </h2>
          <p className="mt-0.5 text-[10px] text-zinc-500">
            {engineerCount} engineer{engineerCount === 1 ? "" : "s"} · {componentCount}{" "}
            component{componentCount === 1 ? "" : "s"}
          </p>
        </div>
        <p className="hidden text-[10px] text-zinc-600 sm:block">
          Select a component for detail
        </p>
      </div>

      <div
        ref={viewportRef}
        className="overflow-y-auto overflow-x-hidden"
        style={{ maxHeight: scrollViewportHeight }}
      >
        <svg
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          className="block w-full"
          style={{ height: layout.height }}
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            <pattern
              id={dotPatternId}
              width="16"
              height="16"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="1" cy="1" r="0.6" fill="#52525b" fillOpacity="0.35" />
            </pattern>
            <linearGradient id={`kra-bg-${uid}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.04" />
              <stop offset="50%" stopColor="#18181b" stopOpacity="0" />
              <stop offset="100%" stopColor="#f97316" stopOpacity="0.04" />
            </linearGradient>
            <filter
              id={filterSpofId}
              x="-50%"
              y="-50%"
              width="200%"
              height="200%"
            >
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter
              id={filterCriticalId}
              x="-50%"
              y="-50%"
              width="200%"
              height="200%"
            >
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <rect
            x={0}
            y={0}
            width={layout.width}
            height={layout.height}
            fill={`url(#kra-bg-${uid})`}
          />
          <rect
            x={0}
            y={0}
            width={layout.width}
            height={layout.height}
            fill={`url(#${dotPatternId})`}
          />

          <rect
            x={16}
            y={14}
            width={layout.width / 2 - 32}
            height={layout.height - 28}
            rx={10}
            fill="#0ea5e906"
            stroke="#0ea5e912"
            strokeWidth={1}
          />
          <rect
            x={layout.width / 2 + 16}
            y={14}
            width={layout.width / 2 - 32}
            height={layout.height - 28}
            rx={10}
            fill="#f9731606"
            stroke="#f9731612"
            strokeWidth={1}
          />

          <text
            x={COLUMN_INSET}
            y={28}
            textAnchor="middle"
            className="fill-sky-400/60 text-[9px] font-medium uppercase tracking-[0.14em]"
          >
            Engineers
          </text>
          <text
            x={layout.width - COLUMN_INSET}
            y={28}
            textAnchor="middle"
            className="fill-amber-400/60 text-[9px] font-medium uppercase tracking-[0.14em]"
          >
            Components
          </text>

          {graph.links.map((link) => {
            const source = positionById.get(link.source);
            const target = positionById.get(link.target);
            if (!source || !target) return null;

            const targetDimmed =
              filterActive &&
              target.type === "component" &&
              !highlightCriticalSpofIds.has(target.id);

            const share = link.codebase_share_pct;
            const strokeWidth =
              share != null && share >= 50 ? 2 : share != null && share >= 20 ? 1.5 : 1;

            return (
              <path
                key={`${link.source}-${link.target}`}
                d={linkPath(source, target)}
                fill="none"
                stroke={targetDimmed ? "#3f3f46" : "#52525b"}
                strokeWidth={strokeWidth}
                strokeOpacity={targetDimmed ? 0.12 : 0.45}
              />
            );
          })}

          {layout.nodes.map((node) => {
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
                  opacity={filterActive ? 0.4 : 1}
                >
                  <circle
                    r={ENGINEER_RADIUS}
                    fill="#0c1222"
                    stroke="#38bdf8"
                    strokeWidth={1.5}
                    strokeOpacity={0.85}
                  />
                  <text
                    textAnchor="middle"
                    y={3}
                    className="fill-zinc-100 text-[9px] font-medium"
                  >
                    {truncateComponentLabel(node.label.split(" ")[0] ?? node.label, 11)}
                  </text>
                  {node.role && (
                    <text
                      textAnchor="middle"
                      y={ENGINEER_RADIUS + 11}
                      className="fill-zinc-500 text-[8px]"
                    >
                      {truncateComponentLabel(node.role, 18)}
                    </text>
                  )}
                </g>
              );
            }

            const componentLabel = formatKraComponentLabel(node);
            const githubDisplay = parseGitHubComponentDisplay(
              node.description,
              node.label,
            );

            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                className="cursor-pointer"
                opacity={dimmed ? 0.22 : 1}
                onClick={() => onSelectComponent(node)}
              >
                <rect
                  x={-COMPONENT_HALF_W}
                  y={-COMPONENT_HALF_H}
                  width={COMPONENT_HALF_W * 2}
                  height={COMPONENT_HALF_H * 2}
                  rx={7}
                  fill={
                    isCriticalSpof ? "#3f0f0f" : isStructuralSpof ? "#3b1a0a" : "#1c1c1f"
                  }
                  stroke={
                    isCriticalSpof
                      ? "#f87171"
                      : isStructuralSpof
                        ? "#fb923c"
                        : isSelected
                          ? "#a1a1aa"
                          : "#52525b"
                  }
                  strokeWidth={isSpof || isSelected ? 2 : 1}
                  filter={
                    isCriticalSpof
                      ? `url(#${filterCriticalId})`
                      : isStructuralSpof
                        ? `url(#${filterSpofId})`
                        : undefined
                  }
                />
                {isCriticalSpof && (
                  <text
                    x={0}
                    y={-COMPONENT_HALF_H - 7}
                    textAnchor="middle"
                    className="fill-red-400/90 text-[7px] font-semibold uppercase tracking-wide"
                  >
                    Critical
                  </text>
                )}
                {isStructuralSpof && !isCriticalSpof && (
                  <text
                    x={0}
                    y={-COMPONENT_HALF_H - 7}
                    textAnchor="middle"
                    className="fill-orange-400/90 text-[7px] font-semibold uppercase tracking-wide"
                  >
                    {node.github_verified_spof ? "GitHub" : "SPOF"}
                  </text>
                )}
                {githubDisplay ? (
                  <>
                    <text
                      textAnchor="middle"
                      y={-3}
                      className={`text-[7px] ${
                        isCriticalSpof || isStructuralSpof
                          ? "fill-orange-300/75"
                          : "fill-zinc-500"
                      }`}
                    >
                      {truncateComponentLabel(githubDisplay.repo, 14)}
                    </text>
                    <text
                      textAnchor="middle"
                      y={7}
                      className={`text-[8px] font-medium ${
                        isCriticalSpof
                          ? "fill-red-200"
                          : isStructuralSpof
                            ? "fill-orange-200"
                            : "fill-zinc-100"
                      }`}
                    >
                      {truncateComponentLabel(githubDisplay.folder, 16)}
                    </text>
                  </>
                ) : (
                  <text
                    textAnchor="middle"
                    y={2}
                    className={`text-[8px] font-medium ${
                      isCriticalSpof
                        ? "fill-red-200"
                        : isStructuralSpof
                          ? "fill-orange-200"
                          : "fill-zinc-100"
                    }`}
                  >
                    {truncateComponentLabel(componentLabel, 16)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-zinc-800/70 bg-zinc-950/90 px-3 py-2 text-[10px] text-zinc-500">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full border border-sky-400/80" />
          Engineer
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded border border-zinc-500/80" />
          Component
        </span>
        <span className="text-zinc-700">·</span>
        <span className="text-zinc-600">Edge weight = ownership %</span>
        {filterActive ? (
          <span className="inline-flex items-center gap-1 text-red-400/90">
            <AlertTriangle className="h-2.5 w-2.5" />
            Critical SPOF
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-orange-400/90">
            <AlertTriangle className="h-2.5 w-2.5" />
            SPOF
          </span>
        )}
      </div>
    </section>
  );
}
