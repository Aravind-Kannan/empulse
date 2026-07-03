"use client";

import type { EraDimensionKey, EraEmployeeMetrics } from "@/lib/types";

import { ERA_DIMENSION_COLORS } from "./era-colors";
import { EraDimensionBar } from "./EraDimensionBar";
import {
  dimensionHeadline,
  dimensionValue,
  getDimensionSummary,
  isDimensionPartial,
  topEvidenceForDimension,
} from "./era-utils";

interface EraDimensionCellProps {
  employee: EraEmployeeMetrics;
  dimension: EraDimensionKey;
  showHeadline?: boolean;
  onDimensionClick?: (dimension: EraDimensionKey) => void;
}

export function EraDimensionCell({
  employee,
  dimension,
  showHeadline = true,
  onDimensionClick,
}: EraDimensionCellProps) {
  const value = dimensionValue(employee, dimension);
  const partial = isDimensionPartial(employee, dimension);
  const headline = dimensionHeadline(employee, dimension);
  const summary = getDimensionSummary(employee, dimension);
  const evidence = topEvidenceForDimension(employee, dimension);
  const colors = ERA_DIMENSION_COLORS[dimension];
  const tooltip = [
    `${colors.label}: ${Math.round(value)}%`,
    headline,
    ...evidence.map((item) => item.title),
  ]
    .filter(Boolean)
    .join("\n");

  const content = (
    <div className="min-w-[4.5rem]">
      <EraDimensionBar
        dimension={dimension}
        value={value}
        partial={partial}
        showValue
      />
      {showHeadline && (
        <p
          className="mt-1 line-clamp-2 text-[10px] leading-snug text-zinc-500"
          title={headline}
        >
          {headline}
        </p>
      )}
      {summary?.top_factors?.[0]?.synthetic && (
        <span className="mt-0.5 inline-block text-[9px] text-amber-400/90">
          Estimated
        </span>
      )}
    </div>
  );

  if (!onDimensionClick) {
    return (
      <div title={tooltip} className="group">
        {content}
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      title={tooltip}
      onClick={(event) => {
        event.stopPropagation();
        onDimensionClick(dimension);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          event.stopPropagation();
          onDimensionClick(dimension);
        }
      }}
      className="group cursor-pointer rounded-md p-0.5 text-left transition hover:bg-zinc-800/60"
    >
      {content}
    </div>
  );
}
