"use client";

import type { EraDimensionKey, EraEmployeeMetrics, EraEvidenceItem } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { EraDimensionFactorWaterfall } from "./EraDimensionFactorWaterfall";
import { dimensionValue, isDimensionPartial } from "./era-utils";

interface EraContinuityRiskVisualProps {
  employee: EraEmployeeMetrics;
  evidence?: EraEvidenceItem[];
  evidenceTotalCount?: number;
  filterDimensions?: EraDimensionKey[];
  expandedFactorId?: string | null;
  onGaugeClick?: (key: EraDimensionKey) => void;
  onFactorClick?: (rowId: string) => void;
}

const GAUGE_ARC_LENGTH = 100.53;
const RAINBOW_ORDER: EraDimensionKey[] = [...DIMENSION_KEYS];
const RAINBOW_RADII = [82, 66, 50, 34, 18] as const;
const PANEL_HEIGHT = "h-[20rem]";

function arcPath(cx: number, cy: number, radius: number): string {
  return `M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`;
}

interface RainbowArcProps {
  dimension: EraDimensionKey;
  score: number;
  radius: number;
  cx: number;
  cy: number;
  active: boolean;
  dimmed: boolean;
  partial: boolean;
  onClick?: () => void;
}

function RainbowArc({
  dimension,
  score,
  radius,
  cx,
  cy,
  active,
  dimmed,
  partial,
  onClick,
}: RainbowArcProps) {
  const colors = ERA_DIMENSION_COLORS[dimension];
  const pct = Math.min(100, Math.max(0, score)) / 100;
  const dash = pct * GAUGE_ARC_LENGTH;
  const path = arcPath(cx, cy, radius);
  const strokeWidth = 11;
  const opacity = dimmed ? 0.35 : 1;

  return (
    <g
      role="button"
      tabIndex={0}
      aria-pressed={active}
      aria-label={`${colors.label} dimension score ${Math.round(score)}`}
      className="cursor-pointer outline-none"
      style={{ opacity }}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick?.();
        }
      }}
    >
      <path
        d={path}
        fill="none"
        stroke="transparent"
        strokeWidth={strokeWidth + 10}
        strokeLinecap="round"
        pointerEvents="stroke"
      />
      <path
        d={path}
        fill="none"
        stroke="#27272a"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={partial ? "4 4" : undefined}
      />
      {pct > 0 && (
        <path
          d={path}
          fill="none"
          stroke={colors.stroke}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${GAUGE_ARC_LENGTH}`}
          className="motion-safe:transition-all motion-safe:duration-500 motion-reduce:transition-none"
        />
      )}
      {active && (
        <path
          d={path}
          fill="none"
          stroke="#a78bfa"
          strokeWidth={strokeWidth + 3}
          strokeLinecap="round"
          strokeOpacity={0.5}
        />
      )}
    </g>
  );
}

export function EraContinuityRiskVisual({
  employee,
  evidence = [],
  evidenceTotalCount,
  filterDimensions = [],
  expandedFactorId = null,
  onGaugeClick,
  onFactorClick,
}: EraContinuityRiskVisualProps) {
  const filterActive = filterDimensions.length > 0;
  const visibleDimensions = filterActive ? filterDimensions : [...DIMENSION_KEYS];
  const cx = 100;
  const cy = 92;
  const totalEvidence = evidenceTotalCount ?? evidence.length;

  return (
    <section
      className={`flex ${PANEL_HEIGHT} overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/30`}
    >
      <div className="flex w-[42%] shrink-0 flex-col border-r border-zinc-800/80 p-3">
        <h3 className="mb-2 shrink-0 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Dimension breakdown
        </h3>
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center">
          <div className="w-full max-w-[11rem]">
            <svg viewBox="0 0 200 100" className="h-auto w-full" aria-hidden>
              {RAINBOW_ORDER.map((key, index) => {
                const value = dimensionValue(employee, key);
                const active = filterDimensions.includes(key);
                const dimmed = filterActive && !active;
                return (
                  <RainbowArc
                    key={key}
                    dimension={key}
                    score={value}
                    radius={RAINBOW_RADII[index]}
                    cx={cx}
                    cy={cy}
                    active={active}
                    dimmed={dimmed}
                    partial={isDimensionPartial(employee, key)}
                    onClick={() => onGaugeClick?.(key)}
                  />
                );
              })}
            </svg>
          </div>
          <div className="mt-2 grid w-full grid-cols-5 gap-0.5 text-center">
            {RAINBOW_ORDER.map((key) => {
              const value = Math.round(dimensionValue(employee, key));
              const colors = ERA_DIMENSION_COLORS[key];
              const active = filterDimensions.includes(key);
              return (
                <button
                  key={key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onGaugeClick?.(key)}
                  className={`min-w-0 rounded px-0.5 py-0.5 transition ${
                    active
                      ? "bg-violet-500/15 ring-1 ring-violet-500/40"
                      : "hover:bg-zinc-800/60"
                  }`}
                >
                  <span className={`block text-[8px] font-medium ${colors.text}`}>
                    {colors.label[0]}
                  </span>
                  <span className="block text-[10px] tabular-nums text-zinc-400">{value}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-center text-[10px] text-zinc-600">
            {filterActive
              ? `${filterDimensions.length} selected — click arcs to toggle`
              : "Click an arc to filter drivers & evidence"}
          </p>
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col p-3">
        <div className="mb-2 flex shrink-0 items-baseline justify-between gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Drivers & evidence
            {filterActive && (
              <span className="ml-1 normal-case text-zinc-600">
                · {filterDimensions.length} selected
              </span>
            )}
          </h3>
          {totalEvidence > evidence.length && !filterActive && (
            <span className="text-[10px] text-zinc-600">
              {evidence.length} of {totalEvidence}
            </span>
          )}
        </div>
        <p className="mb-2 shrink-0 text-[10px] text-zinc-600">
          Click a bar to view evidence for that signal
        </p>
        <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
          {evidence.length === 0 &&
          visibleDimensions.every((key) => {
            const score = dimensionValue(employee, key);
            const factors = employee.dimension_summaries?.[key]?.top_factors ?? [];
            return score <= 0 && factors.length === 0;
          }) ? (
            <p className="py-4 text-center text-xs text-zinc-500">
              Low observable risk — connect integrations for richer signals.
            </p>
          ) : (
            <EraDimensionFactorWaterfall
              employee={employee}
              dimensions={visibleDimensions}
              evidence={evidence}
              drillDown
              expandedFactorId={expandedFactorId}
              onFactorClick={onFactorClick}
              compact
            />
          )}
        </div>
      </div>
    </section>
  );
}
