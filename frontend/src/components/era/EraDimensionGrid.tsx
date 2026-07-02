"use client";

import type { EraEmployeeMetrics } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { EraDimensionBar } from "./EraDimensionBar";
import {
  dimensionValue,
  isDimensionPartial,
  primaryDimensionKey,
} from "./era-utils";

interface EraDimensionGridProps {
  employee: EraEmployeeMetrics;
}

const DRIVER_HINTS: Partial<Record<string, string>> = {
  knowledge: "Primary driver",
  operational: "Load signal",
  documentation: "Docs gap",
  structural: "Org shape",
  burnout: "Watch",
};

export function EraDimensionGrid({ employee }: EraDimensionGridProps) {
  const primary = primaryDimensionKey(employee);

  return (
    <section>
      <h3 className="mb-3 text-sm font-medium text-zinc-200">Dimension breakdown</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {DIMENSION_KEYS.map((key) => {
          const value = dimensionValue(employee, key);
          const partial = isDimensionPartial(employee, key);
          const highlighted = key === primary;
          const colors = ERA_DIMENSION_COLORS[key];

          return (
            <div
              key={key}
              className={`rounded-lg border p-3 ${
                highlighted
                  ? "border-violet-500/40 bg-violet-500/5"
                  : "border-zinc-800 bg-zinc-950/50"
              } ${partial ? "border-dashed" : ""}`}
              title={partial ? "Partial data — connect more integrations" : undefined}
            >
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
              {partial && (
                <p className="mt-1.5 text-[10px] text-amber-400/90">Partial data</p>
              )}
              {highlighted && DRIVER_HINTS[key] && (
                <p className="mt-1.5 text-[10px] font-medium text-violet-300">
                  {DRIVER_HINTS[key]}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
