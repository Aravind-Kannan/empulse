"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type {
  EraAffectedComponent,
  EraDimensionKey,
  EraRiskHistoryPoint,
} from "@/lib/types";

import { ERA_DIMENSION_COLORS } from "./era-colors";
import { historyForDimension } from "./era-utils";
import {
  EraMultiRiskSparkline,
  EraRiskSparkline,
  EraTrendChip,
} from "./EraRiskSparkline";

interface EraDetailCompactInsightsProps {
  history: EraRiskHistoryPoint[];
  trendDimensions: EraDimensionKey[];
  components: EraAffectedComponent[];
}

const VISIBLE_COMPONENTS = 6;

function historyTrend(history: EraRiskHistoryPoint[]): number | null {
  if (history.length < 2) {
    return null;
  }
  return (
    history[history.length - 1].risk_factor_score -
    history[0].risk_factor_score
  );
}

function criticalityDot(
  criticality: EraAffectedComponent["criticality"],
): string {
  if (criticality === "tier1_revenue") return "bg-red-400";
  if (criticality === "tier2_core") return "bg-amber-400";
  return "bg-zinc-500";
}

function CompactTrendDelta({ trend }: { trend: number | null }) {
  if (trend == null) {
    return null;
  }
  const up = trend > 0;
  const flat = trend === 0;
  return (
    <span
      className={`tabular-nums ${
        flat ? "text-zinc-500" : up ? "text-red-400" : "text-emerald-400"
      }`}
    >
      {flat ? "—" : up ? "▲" : "▼"}
      {Math.abs(trend).toFixed(1)}
    </span>
  );
}

export function EraDetailCompactInsights({
  history,
  trendDimensions,
  components,
}: EraDetailCompactInsightsProps) {
  const [showAllComponents, setShowAllComponents] = useState(false);
  const multiTrend = trendDimensions.length > 1;

  const dimensionSeries = useMemo(
    () =>
      trendDimensions.map((dimension) => ({
        dimension,
        history: historyForDimension(history, dimension),
        colors: ERA_DIMENSION_COLORS[dimension],
      })),
    [history, trendDimensions],
  );

  const visibleComponents = showAllComponents
    ? components
    : components.slice(0, VISIBLE_COMPONENTS);
  const hiddenCount = components.length - VISIBLE_COMPONENTS;
  const hasComponents = components.length > 0;

  const singleSeries = dimensionSeries[0];

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 px-3 py-2.5">
      <div
        className={`grid gap-3 ${hasComponents ? "grid-cols-[minmax(0,1fr)_11rem]" : "grid-cols-1"}`}
      >
        <div className="min-w-0">
          <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
            30-day trend
            {!multiTrend && singleSeries && (
              <span className={`ml-1.5 normal-case ${singleSeries.colors.text}`}>
                · {singleSeries.colors.label}
              </span>
            )}
          </p>
          <div className="mt-1.5 flex items-end gap-2">
            <div className="min-w-0 flex-1">
              {multiTrend ? (
                <EraMultiRiskSparkline
                  fluid
                  series={dimensionSeries.map((item) => ({
                    id: item.dimension,
                    history: item.history,
                    strokeColor: item.colors.stroke,
                  }))}
                />
              ) : singleSeries ? (
                <EraRiskSparkline
                  history={singleSeries.history}
                  fluid
                  strokeColor={singleSeries.colors.stroke}
                />
              ) : null}
            </div>
            {!multiTrend && singleSeries && (
              <div className="shrink-0 text-right">
                <EraTrendChip trend={historyTrend(singleSeries.history)} />
                {singleSeries.history.length >= 2 && (
                  <p className="mt-0.5 text-[9px] tabular-nums text-zinc-500">
                    {Math.round(singleSeries.history[0].risk_factor_score)}% →{" "}
                    {Math.round(
                      singleSeries.history[singleSeries.history.length - 1]
                        .risk_factor_score,
                    )}
                    %
                  </p>
                )}
              </div>
            )}
          </div>
          {multiTrend && (
            <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
              {dimensionSeries.map((item) => (
                <span
                  key={item.dimension}
                  className="inline-flex items-center gap-1.5 text-[9px]"
                >
                  <span
                    className="h-0.5 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: item.colors.stroke }}
                  />
                  <span className={item.colors.text}>{item.colors.label}</span>
                  <CompactTrendDelta trend={historyTrend(item.history)} />
                </span>
              ))}
            </div>
          )}
        </div>

        {hasComponents && (
          <div className="min-w-0 border-l border-zinc-800/80 pl-3">
            <div className="flex items-baseline justify-between gap-1">
              <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
                Components
              </p>
              <span className="text-[9px] tabular-nums text-zinc-600">
                {components.length}
              </span>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {visibleComponents.map((component) => (
                <Link
                  key={component.id}
                  href={`/kra?highlight=${encodeURIComponent(component.id)}`}
                  className="inline-flex max-w-full items-center gap-1 rounded border border-zinc-700/80 bg-zinc-950/50 px-1.5 py-0.5 text-[9px] text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-900"
                >
                  <span
                    className={`h-1 w-1 shrink-0 rounded-full ${criticalityDot(component.criticality)}`}
                    aria-hidden
                  />
                  <span className="truncate">{component.name}</span>
                  {component.spof && (
                    <span className="shrink-0 text-[8px] font-medium uppercase text-orange-400">
                      SPOF
                    </span>
                  )}
                </Link>
              ))}
              {!showAllComponents && hiddenCount > 0 && (
                <button
                  type="button"
                  onClick={() => setShowAllComponents(true)}
                  className="rounded border border-dashed border-zinc-700 px-1.5 py-0.5 text-[9px] text-zinc-500 hover:border-zinc-600 hover:text-zinc-400"
                >
                  +{hiddenCount}
                </button>
              )}
              {showAllComponents && components.length > VISIBLE_COMPONENTS && (
                <button
                  type="button"
                  onClick={() => setShowAllComponents(false)}
                  className="rounded px-1.5 py-0.5 text-[9px] text-zinc-500 hover:text-zinc-400"
                >
                  Less
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
