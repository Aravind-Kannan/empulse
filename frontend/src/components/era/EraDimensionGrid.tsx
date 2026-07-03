"use client";

import type { EraDimensionKey, EraEmployeeMetrics } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { EraDimensionBar } from "./EraDimensionBar";
import {
  dimensionHeadline,
  dimensionValue,
  isDimensionPartial,
} from "./era-utils";

interface EraDimensionGridProps {
  employee: EraEmployeeMetrics;
  selectedDimensions?: EraDimensionKey[];
  onToggleDimension?: (key: EraDimensionKey) => void;
}

export function EraDimensionGrid({
  employee,
  selectedDimensions = [],
  onToggleDimension,
}: EraDimensionGridProps) {
  const selectable = Boolean(onToggleDimension);

  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-zinc-200">Dimension breakdown</h3>
        {selectable && (
          <p className="text-[11px] text-zinc-500">
            {selectedDimensions.length > 0
              ? `${selectedDimensions.length} selected — click to toggle`
              : "Click dimensions to filter drivers & evidence"}
          </p>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {DIMENSION_KEYS.map((key) => {
          const value = dimensionValue(employee, key);
          const partial = isDimensionPartial(employee, key);
          const selected = selectedDimensions.includes(key);
          const colors = ERA_DIMENSION_COLORS[key];
          const headline = dimensionHeadline(employee, key);
          const topFactor = employee.dimension_summaries?.[key]?.top_factors?.[0];

          const className = `rounded-lg border p-3 text-left transition ${
            selected
              ? "border-violet-500/50 bg-violet-500/10 ring-1 ring-violet-500/30"
              : "border-zinc-800 bg-zinc-950/50 hover:border-zinc-700"
          } ${partial ? "border-dashed" : ""} ${selectable ? "cursor-pointer" : ""}`;

          const body = (
            <>
              <div className="flex items-baseline justify-between gap-1">
                <span className={`text-xs font-medium ${colors.text}`}>
                  {colors.label[0]}
                </span>
                <span className="text-lg font-semibold text-zinc-100">
                  {Math.round(value)}
                </span>
              </div>
              <p className="mt-0.5 truncate text-[11px] text-zinc-500">
                {colors.label}
              </p>
              <div className="mt-2">
                <EraDimensionBar
                  dimension={key}
                  value={value}
                  partial={partial}
                />
              </div>
              <p
                className="mt-2 line-clamp-3 text-[10px] leading-snug text-zinc-400"
                title={headline}
              >
                {headline}
              </p>
              {topFactor && (
                <p className="mt-1 text-[10px] text-zinc-500">
                  Top: {topFactor.label}
                  {topFactor.synthetic ? " (estimated)" : ""}
                </p>
              )}
              {partial && (
                <p className="mt-1 text-[10px] text-amber-400/90">Partial data</p>
              )}
            </>
          );

          if (selectable) {
            return (
              <button
                key={key}
                type="button"
                aria-pressed={selected}
                onClick={() => onToggleDimension?.(key)}
                className={className}
              >
                {body}
              </button>
            );
          }

          return (
            <div key={key} className={className}>
              {body}
            </div>
          );
        })}
      </div>
    </section>
  );
}
