"use client";

import { Info } from "lucide-react";

import type {
  EraDimensionFactorSummary,
  EraDimensionKey,
  EraEmployeeMetrics,
  EraEvidenceItem,
} from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { EraEvidenceCard } from "./EraEvidenceCard";
import { groupEvidenceByFactor } from "./evidence-factor-mapping";
import { dimensionValue, getDimensionSummary } from "./era-utils";

export function factorRowId(dimension: EraDimensionKey, factorKey: string): string {
  return `${dimension}:${factorKey}`;
}

interface EraDimensionFactorWaterfallProps {
  employee: EraEmployeeMetrics;
  dimension?: EraDimensionKey;
  dimensions?: EraDimensionKey[];
  evidence?: EraEvidenceItem[];
  compact?: boolean;
  drillDown?: boolean;
  expandedFactorId?: string | null;
  onFactorClick?: (rowId: string) => void;
}

function factorBarWidth(
  factor: EraDimensionFactorSummary,
  dimensionScore: number,
  maxImpact: number,
): number {
  if (factor.impact_points <= 0) return 0;
  if (dimensionScore > 0) {
    return Math.min(100, (factor.impact_points / dimensionScore) * 100);
  }
  return (factor.impact_points / maxImpact) * 100;
}

function factorInfoText(factor: EraDimensionFactorSummary): string {
  const est = factor.synthetic ? " (estimated)" : "";
  return `${factor.label} contributed ${factor.impact_points.toFixed(1)} impact points (signal value: ${factor.value})${est}.`;
}

function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="group/info relative inline-flex shrink-0">
      <button
        type="button"
        className="rounded p-0.5 text-zinc-500 hover:text-zinc-300 focus:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
        aria-label="More detail"
        onClick={(event) => event.stopPropagation()}
      >
        <Info className="h-3 w-3" />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full right-0 z-10 mb-1 hidden w-52 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-[10px] leading-snug text-zinc-300 shadow-lg group-hover/info:block group-focus-within/info:block"
      >
        {text}
      </span>
    </span>
  );
}

export function EraDimensionFactorWaterfall({
  employee,
  dimension,
  dimensions,
  evidence = [],
  compact = false,
  drillDown = false,
  expandedFactorId = null,
  onFactorClick,
}: EraDimensionFactorWaterfallProps) {
  const keys =
    dimensions && dimensions.length > 0
      ? DIMENSION_KEYS.filter((key) => dimensions.includes(key))
      : dimension
        ? [dimension]
        : DIMENSION_KEYS;

  return (
    <div className="space-y-3">
      {keys.map((key) => {
        const summary = getDimensionSummary(employee, key);
        const colors = ERA_DIMENSION_COLORS[key];
        const factors = summary?.top_factors ?? [];
        const dimensionScore = summary?.score ?? dimensionValue(employee, key);
        const maxImpact = Math.max(...factors.map((f) => f.impact_points), 1);
        const headline = summary?.headline;
        const showHeadline =
          headline &&
          headline !== "No significant signal detected" &&
          dimensionScore > 0;
        const isFiltered = Boolean(dimensions && dimensions.length > 0);
        const evidenceByFactor = groupEvidenceByFactor(
          key,
          factors.map((factor) => factor.key),
          evidence,
        );

        if (!isFiltered && dimensionScore <= 0 && factors.length === 0) {
          return null;
        }

        const renderBarRow = (
          rowId: string,
          label: string,
          impactPoints: number,
          synthetic: boolean,
          linkedEvidence: EraEvidenceItem[],
          factor?: EraDimensionFactorSummary,
        ) => {
          const isSelected = expandedFactorId === rowId;
          const width = factor
            ? factorBarWidth(factor, dimensionScore, maxImpact)
            : Math.min(
                100,
                dimensionScore > 0
                  ? (impactPoints / dimensionScore) * 100
                  : (impactPoints / maxImpact) * 100,
              );

          return (
            <div key={rowId} className="space-y-1">
              <button
                type="button"
                aria-expanded={isSelected}
                onClick={() => onFactorClick?.(rowId)}
                className={`grid w-full grid-cols-[minmax(0,1fr)_5rem_1.25rem_1.5rem] items-center gap-x-1.5 rounded-md px-1 py-1 text-left transition ${
                  isSelected
                    ? "bg-violet-500/10 ring-1 ring-violet-500/30"
                    : "hover:bg-zinc-800/40"
                }`}
              >
                <span className="truncate text-[10px] text-zinc-400">
                  {label}
                  {synthetic ? " (est.)" : ""}
                </span>
                <div className="h-1.5 w-full rounded-full bg-zinc-800">
                  <div
                    className={`h-full rounded-full ${colors.bar}`}
                    style={{
                      width: `${width > 0 && width < 4 ? 4 : width}%`,
                    }}
                  />
                </div>
                {factor ? (
                  <InfoTooltip text={factorInfoText(factor)} />
                ) : (
                  <span />
                )}
                <span className="text-right text-[10px] tabular-nums text-zinc-500">
                  {Math.round(impactPoints)}
                </span>
              </button>
              {isSelected && (
                <div className="ml-1 space-y-1 border-l border-zinc-800 pl-2">
                  {linkedEvidence.length > 0 ? (
                    linkedEvidence.map((item) => (
                      <EraEvidenceCard key={item.id} item={item} minimal />
                    ))
                  ) : factor ? (
                    <p className="text-[10px] leading-snug text-zinc-500">
                      {factorInfoText(factor)}
                    </p>
                  ) : null}
                </div>
              )}
            </div>
          );
        };

        return (
          <div key={key}>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-1.5">
                <span className={`text-xs font-medium ${colors.text}`}>
                  {colors.label}
                </span>
                {showHeadline && !compact && <InfoTooltip text={headline} />}
              </div>
              <span className="shrink-0 text-xs tabular-nums text-zinc-500">
                {Math.round(dimensionScore)}%
              </span>
            </div>

            {drillDown ? (
              <div className="space-y-0.5">
                {factors.map((factor) =>
                  renderBarRow(
                    factorRowId(key, factor.key),
                    factor.label,
                    factor.impact_points,
                    factor.synthetic,
                    evidenceByFactor.get(factor.key) ?? [],
                    factor,
                  ),
                )}
                {factors.length === 0 &&
                  dimensionScore > 0 &&
                  headline &&
                  headline !== "No significant signal detected" && (
                    <p className="text-[11px] text-zinc-500">{headline}</p>
                  )}
              </div>
            ) : (
              <div className="space-y-1.5">
                {factors.map((factor) => {
                  const width = factorBarWidth(factor, dimensionScore, maxImpact);
                  return (
                    <div
                      key={factor.key}
                      className="grid grid-cols-[minmax(0,1fr)_5rem_1.25rem_1.5rem] items-center gap-x-1.5"
                    >
                      <span className="truncate text-[10px] text-zinc-400">
                        {factor.label}
                      </span>
                      <div className="h-1.5 w-full rounded-full bg-zinc-800">
                        <div
                          className={`h-full rounded-full ${colors.bar}`}
                          style={{
                            width: `${width > 0 && width < 4 ? 4 : width}%`,
                          }}
                        />
                      </div>
                      <InfoTooltip text={factorInfoText(factor)} />
                      <span className="text-right text-[10px] tabular-nums text-zinc-500">
                        {Math.round(factor.impact_points)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
