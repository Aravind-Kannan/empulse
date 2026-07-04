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
  detailOpen?: boolean;
  splitView?: boolean;
}

const MIN_GRAPH_WIDTH = 720;
const MIN_GRAPH_HEIGHT = 280;
/** Scroll viewport cap — layout keeps full node spacing inside viewBox. */
const SCROLL_VIEWPORT_MAX = 560;
const GRAPH_PADDING_TOP = 40;
const GRAPH_PADDING_BOTTOM = 36;
const COLUMN_INSET = 140;
const COMPACT_COLUMN_INSET = 72;
const ENGINEER_MIN_GAP = 92;
const COMPONENT_MIN_GAP = 84;
const ENGINEER_RADIUS = 22;
const ENGINEER_NAME_OFFSET = 12;
const COMPONENT_HALF_W = 52;
const COMPONENT_HALF_H = 26;
const ENGINEER_ABOVE = ENGINEER_RADIUS;
const ENGINEER_BELOW = ENGINEER_RADIUS + ENGINEER_NAME_OFFSET;
const COMPONENT_ABOVE = COMPONENT_HALF_H + 14;
const COMPONENT_BELOW = COMPONENT_HALF_H;

function columnPositions(
  count: number,
  minGap: number,
  height: number,
  extentAbove: number,
  extentBelow: number,
): number[] {
  if (count === 0) return [];

  const minY = GRAPH_PADDING_TOP + extentAbove;
  const maxY = height - GRAPH_PADDING_BOTTOM - extentBelow;
  if (count === 1) return [(minY + maxY) / 2];

  const span = maxY - minY;
  const gap = Math.max(minGap, span / (count - 1));
  const totalSpan = (count - 1) * gap;
  const start = minY + (span - totalSpan) / 2;

  return Array.from({ length: count }, (_, index) => start + index * gap);
}

function layoutGraph(
  graph: KraAnalyticsResponse,
  graphWidth: number,
  compact: boolean,
): GraphLayout {
  const engineers = graph.nodes.filter((node) => node.type === "engineer");
  const components = graph.nodes.filter((node) => node.type === "component");
  const inset = compact ? COMPACT_COLUMN_INSET : COLUMN_INSET;
  const engineerX = inset;
  const componentX = graphWidth - inset;

  const engineerSpan =
    engineers.length <= 1 ? 0 : (engineers.length - 1) * ENGINEER_MIN_GAP;
  const componentSpan =
    components.length <= 1 ? 0 : (components.length - 1) * COMPONENT_MIN_GAP;
  const height = Math.max(
    MIN_GRAPH_HEIGHT,
    Math.max(engineerSpan, componentSpan, 96) +
      GRAPH_PADDING_TOP +
      GRAPH_PADDING_BOTTOM +
      ENGINEER_ABOVE +
      ENGINEER_BELOW,
  );

  const engineerYs = columnPositions(
    engineers.length,
    ENGINEER_MIN_GAP,
    height,
    ENGINEER_ABOVE,
    ENGINEER_BELOW,
  );
  const componentYs = columnPositions(
    components.length,
    COMPONENT_MIN_GAP,
    height,
    COMPONENT_ABOVE,
    COMPONENT_BELOW,
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

function linkEndpoints(
  source: PositionedNode,
  target: PositionedNode,
): { x1: number; y1: number; x2: number; y2: number; midX: number } {
  const x1 = source.x + (source.type === "engineer" ? ENGINEER_RADIUS : COMPONENT_HALF_W);
  const x2 = target.x - (target.type === "component" ? COMPONENT_HALF_W : ENGINEER_RADIUS);
  const midX = (x1 + x2) / 2;
  return { x1, y1: source.y, x2, y2: target.y, midX };
}

function linkPath(
  source: PositionedNode,
  target: PositionedNode,
): string {
  const { x1, y1, x2, y2, midX } = linkEndpoints(source, target);
  return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
}

function getEngineerInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function cubicBezierMidpoint(
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  x3: number,
  y3: number,
): { x: number; y: number } {
  const t = 0.5;
  const mt = 1 - t;
  return {
    x:
      mt ** 3 * x0 +
      3 * mt ** 2 * t * x1 +
      3 * mt * t ** 2 * x2 +
      t ** 3 * x3,
    y:
      mt ** 3 * y0 +
      3 * mt ** 2 * t * y1 +
      3 * mt * t ** 2 * y2 +
      t ** 3 * y3,
  };
}

const NODE_TRANSITION = "transform 300ms ease-out";

export function KraGraph({
  graph,
  selectedComponentId,
  onSelectComponent,
  highlightCriticalSpofIds = null,
  detailOpen = false,
  splitView = false,
}: KraGraphProps) {
  const uid = useId().replace(/:/g, "");
  const filterSpofId = `kra-spof-glow-${uid}`;
  const filterCriticalId = `kra-critical-spof-glow-${uid}`;
  const dotPatternId = `kra-dots-${uid}`;
  const viewportRef = useRef<HTMLDivElement>(null);
  const [graphWidth, setGraphWidth] = useState(MIN_GRAPH_WIDTH);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

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
    () => layoutGraph(graph, graphWidth, detailOpen),
    [graph, graphWidth, detailOpen],
  );
  const positionById = useMemo(
    () => new Map(layout.nodes.map((node) => [node.id, node])),
    [layout.nodes],
  );

  const hoveredLinkKeys = useMemo(() => {
    if (!hoveredNodeId) return null;
    const keys = new Set<string>();
    for (const link of graph.links) {
      if (link.source === hoveredNodeId || link.target === hoveredNodeId) {
        keys.add(`${link.source}-${link.target}`);
      }
    }
    return keys;
  }, [graph.links, hoveredNodeId]);

  const engineerCount = graph.nodes.filter((node) => node.type === "engineer").length;
  const componentCount = graph.nodes.filter((node) => node.type === "component").length;
  const scrollViewportHeight = Math.min(layout.height, SCROLL_VIEWPORT_MAX);

  const columnDividerX = useMemo(() => {
    const engineerXs = layout.nodes
      .filter((node) => node.type === "engineer")
      .map((node) => node.x);
    const componentXs = layout.nodes
      .filter((node) => node.type === "component")
      .map((node) => node.x);
    if (engineerXs.length > 0 && componentXs.length > 0) {
      return (Math.max(...engineerXs) + Math.min(...componentXs)) / 2;
    }
    return layout.width / 2;
  }, [layout.nodes, layout.width]);

  const zoneInset = detailOpen ? COMPACT_COLUMN_INSET : COLUMN_INSET;
  const engineerZoneLeft = zoneInset - ENGINEER_RADIUS - 12;
  const engineerZoneWidth = Math.max(columnDividerX - engineerZoneLeft - 8, 48);
  const componentZoneX = columnDividerX + 8;
  const componentZoneWidth = Math.max(graphWidth - componentZoneX - 16, 48);

  return (
    <section
      className={`flex h-full min-h-0 w-full flex-col overflow-hidden bg-zinc-950/80 ${
        splitView
          ? "shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)]"
          : "rounded-xl border border-zinc-800/80 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)] ring-1 ring-white/[0.03]"
      }`}
    >
      <div className="flex items-center justify-between border-b border-zinc-800/70 px-4 py-2.5">
        <div>
          <h2 className="text-[13px] font-medium tracking-tight text-zinc-200">
            Ownership map
          </h2>
          <p className="mt-0.5 text-[10px] text-zinc-500">
            Who owns which codebase areas
          </p>
        </div>
        <p className="hidden text-[10px] text-zinc-500 sm:block">
          Hover a node · click a component for detail
        </p>
      </div>

      <div className="grid grid-cols-2 border-b border-zinc-800/60 bg-zinc-950/50">
        <div className="border-r border-zinc-800/40 px-3 py-2 text-center">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-sky-400/90">
            Engineers
          </p>
          <p className="mt-0.5 text-[10px] tabular-nums text-zinc-500">
            {engineerCount} linked
          </p>
        </div>
        <div className="px-3 py-2 text-center">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-amber-400/90">
            Components
          </p>
          <p className="mt-0.5 text-[10px] tabular-nums text-zinc-500">
            {componentCount} in scope
          </p>
        </div>
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
            x={engineerZoneLeft}
            y={8}
            width={engineerZoneWidth}
            height={layout.height - 16}
            rx={10}
            fill="#0ea5e906"
            stroke="#0ea5e912"
            strokeWidth={1}
            style={{ transition: "width 300ms ease-out" }}
          />
          <rect
            x={componentZoneX}
            y={8}
            width={componentZoneWidth}
            height={layout.height - 16}
            rx={10}
            fill="#f9731606"
            stroke="#f9731612"
            strokeWidth={1}
            style={{ transition: "x 300ms ease-out, width 300ms ease-out" }}
          />

          <line
            x1={columnDividerX}
            y1={8}
            x2={columnDividerX}
            y2={layout.height - 8}
            stroke="#3f3f46"
            strokeOpacity={0.35}
            strokeDasharray="4 4"
            style={{ transition: "x1 300ms ease-out, x2 300ms ease-out" }}
          />

          {graph.links.map((link) => {
            const source = positionById.get(link.source);
            const target = positionById.get(link.target);
            if (!source || !target) return null;

            const linkKey = `${link.source}-${link.target}`;
            const isHoveredLink = hoveredLinkKeys?.has(linkKey) ?? false;
            const hoverActive = hoveredLinkKeys != null;

            const targetDimmed =
              filterActive &&
              target.type === "component" &&
              !highlightCriticalSpofIds.has(target.id);

            const share = link.codebase_share_pct;
            const strokeWidth =
              share != null && share >= 50 ? 2 : share != null && share >= 20 ? 1.5 : 1;

            return (
              <path
                key={linkKey}
                d={linkPath(source, target)}
                fill="none"
                stroke={
                  isHoveredLink ? "#38bdf8" : targetDimmed ? "#3f3f46" : "#52525b"
                }
                strokeWidth={isHoveredLink ? Math.max(strokeWidth, 2) : strokeWidth}
                strokeOpacity={
                  isHoveredLink
                    ? 0.9
                    : hoverActive
                      ? 0.1
                      : targetDimmed
                        ? 0.12
                        : 0.45
                }
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
              const isHovered = hoveredNodeId === node.id;
              return (
                <g
                  key={node.id}
                  style={{
                    transform: `translate(${node.x}px, ${node.y}px)`,
                    transition: NODE_TRANSITION,
                  }}
                  opacity={filterActive && !isHovered ? 0.4 : 1}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  className="cursor-default"
                >
                  <circle
                    r={ENGINEER_RADIUS}
                    fill="#0c1222"
                    stroke="#38bdf8"
                    strokeWidth={1.5}
                    strokeOpacity={0.85}
                  />
                  <title>{node.label}</title>
                  <text
                    textAnchor="middle"
                    y={4}
                    className="fill-zinc-100 text-[10px] font-semibold"
                  >
                    {getEngineerInitials(node.label)}
                  </text>
                  <text
                    textAnchor="middle"
                    y={ENGINEER_RADIUS + ENGINEER_NAME_OFFSET}
                    className="fill-zinc-300 text-[8px] font-medium"
                  >
                    {truncateComponentLabel(node.label.split(" ")[0] ?? node.label, 14)}
                  </text>
                </g>
              );
            }

            const componentLabel = formatKraComponentLabel(node);
            const githubDisplay = parseGitHubComponentDisplay(
              node.description,
              node.label,
            );

            const isHovered = hoveredNodeId === node.id;

            return (
              <g
                key={node.id}
                style={{
                  transform: `translate(${node.x}px, ${node.y}px)`,
                  transition: NODE_TRANSITION,
                }}
                className="cursor-pointer"
                opacity={dimmed && !isHovered ? 0.22 : 1}
                onClick={() => onSelectComponent(node)}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
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

          {hoveredLinkKeys &&
            graph.links.map((link) => {
              if (!hoveredLinkKeys.has(`${link.source}-${link.target}`)) return null;
              if (link.codebase_share_pct == null) return null;

              const source = positionById.get(link.source);
              const target = positionById.get(link.target);
              if (!source || !target) return null;

              const { x1, y1, x2, y2, midX } = linkEndpoints(source, target);
              const labelPos = cubicBezierMidpoint(x1, y1, midX, y1, midX, y2, x2, y2);
              const label = `${link.codebase_share_pct.toFixed(1)}%`;
              const labelWidth = label.length * 5.2 + 8;

              return (
                <g key={`label-${link.source}-${link.target}`} pointerEvents="none">
                  <rect
                    x={labelPos.x - labelWidth / 2}
                    y={labelPos.y - 8}
                    width={labelWidth}
                    height={16}
                    rx={4}
                    fill="#09090b"
                    fillOpacity={0.92}
                    stroke="#38bdf8"
                    strokeOpacity={0.35}
                    strokeWidth={1}
                  />
                  <text
                    x={labelPos.x}
                    y={labelPos.y + 3}
                    textAnchor="middle"
                    className="fill-sky-300 text-[9px] font-medium"
                  >
                    {label}
                  </text>
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
