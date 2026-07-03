"use client";

import type { EraDimensionKey, EraEmployeeMetrics } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { getDimensionSummary } from "./era-utils";

interface EraDimensionFactorWaterfallProps {
  employee: EraEmployeeMetrics;
  dimension?: EraDimensionKey;
  dimensions?: EraDimensionKey[];
  compact?: boolean;
}

export function EraDimensionFactorWaterfall({
  employee,
  dimension,
  dimensions,
  compact = false,
}: EraDimensionFactorWaterfallProps) {
  const keys =
    dimensions && dimensions.length > 0
      ? DIMENSION_KEYS.filter((key) => dimensions.includes(key))
      : DIMENSION_KEYS;

  return (
    <div className="space-y-4">
      {keys.map((key) => {
        const summary = getDimensionSummary(employee, key);
        const colors = ERA_DIMENSION_COLORS[key];
        const factors = summary?.top_factors ?? [];
        const maxImpact = Math.max(...factors.map((f) => f.impact_points), 1);

        return (
          <div key={key}>
            <div className="mb-2 flex items-baseline justify-between gap-2">
              <span className={`text-xs font-medium ${colors.text}`}>
                {colors.label}
              </span>
              <span className="text-xs text-zinc-500">
                {Math.round(summary?.score ?? employee.dimensions?.[key] ?? 0)}%
              </span>
            </div>
            {factors.length === 0 ? (
              <p className="text-[11px] text-zinc-500">
                {summary?.headline ?? "No contributing factors"}
              </p>
            ) : (
              <div className="space-y-1.5">
                {factors.map((factor) => (
                  <div key={factor.key} className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 rounded-full bg-zinc-800">
                      <div
                        className={`h-full rounded-full ${colors.bar}`}
                        style={{
                          width: `${Math.max(
                            4,
                            (factor.impact_points / maxImpact) * 100,
                          )}%`,
                        }}
                      />
                    </div>
                    <span
                      className="max-w-[12rem] truncate text-[10px] text-zinc-400"
                      title={`${factor.label} — ${factor.impact_points} pts`}
                    >
                      {factor.label}
                      {factor.synthetic ? " (est.)" : ""}
                    </span>
                    <span className="w-8 text-right text-[10px] tabular-nums text-zinc-500">
                      {Math.round(factor.impact_points)}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {summary?.headline && !compact && (
              <p className="mt-1.5 text-[11px] text-zinc-500">{summary.headline}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
