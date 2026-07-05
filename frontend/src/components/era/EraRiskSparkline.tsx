"use client";

import type { EraRiskHistoryPoint } from "@/lib/types";

interface EraRiskSparklineProps {
  history: EraRiskHistoryPoint[];
  width?: number;
  height?: number;
  fluid?: boolean;
  strokeClassName?: string;
  strokeColor?: string;
  className?: string;
  emptyLabel?: string;
}

const FLUID_VIEW_WIDTH = 240;
const FLUID_VIEW_HEIGHT = 32;
const FLUID_MULTI_VIEW_HEIGHT = 40;

function scoreRange(histories: EraRiskHistoryPoint[][]): {
  min: number;
  max: number;
  range: number;
} {
  const scores = histories.flatMap((history) =>
    history.map((point) => point.risk_factor_score),
  );
  if (scores.length === 0) {
    return { min: 0, max: 100, range: 100 };
  }
  const min = Math.min(...scores, 0);
  const max = Math.max(...scores, 100);
  const range = max - min || 1;
  return { min, max, range };
}

function buildPath(
  history: EraRiskHistoryPoint[],
  width: number,
  height: number,
  scale?: { min: number; range: number },
): string {
  if (history.length === 0) {
    return "";
  }
  const scores = history.map((point) => point.risk_factor_score);
  const min = scale?.min ?? Math.min(...scores, 0);
  const range = scale?.range ?? ((Math.max(...scores, 100) - min) || 1);
  const step = history.length > 1 ? width / (history.length - 1) : 0;

  return history
    .map((point, index) => {
      const x = index * step;
      const y = height - ((point.risk_factor_score - min) / range) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export interface SparklineSeries {
  id: string;
  history: EraRiskHistoryPoint[];
  strokeColor: string;
}

interface EraMultiRiskSparklineProps {
  series: SparklineSeries[];
  fluid?: boolean;
  className?: string;
  emptyLabel?: string;
}

export function EraMultiRiskSparkline({
  series,
  fluid = false,
  className = "",
  emptyLabel = "No trend yet",
}: EraMultiRiskSparklineProps) {
  const chartWidth = FLUID_VIEW_WIDTH;
  const chartHeight = FLUID_MULTI_VIEW_HEIGHT;
  const histories = series.map((item) => item.history);
  const hasEnoughData = histories.some((history) => history.length >= 2);

  if (!hasEnoughData) {
    return (
      <div
        className={`flex items-center text-[10px] text-zinc-600 ${
          fluid ? "h-10 w-full" : ""
        } ${className}`}
      >
        {emptyLabel}
      </div>
    );
  }

  const scale = scoreRange(histories);

  return (
    <svg
      width={fluid ? "100%" : chartWidth}
      height={chartHeight}
      viewBox={`0 0 ${chartWidth} ${chartHeight}`}
      preserveAspectRatio={fluid ? "none" : undefined}
      className={`${fluid ? "h-10 w-full" : ""} ${className}`}
      aria-hidden
    >
      {series.map((item) => {
        if (item.history.length < 2) {
          return null;
        }
        const path = buildPath(item.history, chartWidth, chartHeight, scale);
        const latest = item.history[item.history.length - 1]?.risk_factor_score ?? 0;
        const latestY =
          chartHeight - ((latest - scale.min) / scale.range) * chartHeight;
        return (
          <g key={item.id}>
            <path
              d={path}
              fill="none"
              stroke={item.strokeColor}
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx={chartWidth} cy={latestY} r="2" fill={item.strokeColor} />
          </g>
        );
      })}
    </svg>
  );
}

export function EraRiskSparkline({
  history,
  width = 96,
  height = 28,
  fluid = false,
  strokeClassName = "stroke-violet-400",
  strokeColor,
  className = "",
  emptyLabel = "No trend yet",
}: EraRiskSparklineProps) {
  const chartWidth = fluid ? FLUID_VIEW_WIDTH : width;
  const chartHeight = fluid ? FLUID_VIEW_HEIGHT : height;

  if (history.length < 2) {
    return (
      <div
        className={`flex items-center text-[10px] text-zinc-600 ${
          fluid ? "h-8 w-full" : ""
        } ${className}`}
        style={fluid ? undefined : { width, height }}
      >
        {emptyLabel}
      </div>
    );
  }

  const path = buildPath(history, chartWidth, chartHeight);
  const latest = history[history.length - 1]?.risk_factor_score ?? 0;
  const scores = history.map((point) => point.risk_factor_score);
  const min = Math.min(...scores, 0);
  const max = Math.max(...scores, 100);
  const range = max - min || 1;
  const latestY =
    chartHeight - ((latest - min) / range) * chartHeight;
  const pathStrokeProps = strokeColor
    ? { stroke: strokeColor }
    : { className: strokeClassName };

  return (
    <svg
      width={fluid ? "100%" : width}
      height={chartHeight}
      viewBox={`0 0 ${chartWidth} ${chartHeight}`}
      preserveAspectRatio={fluid ? "none" : undefined}
      className={`${fluid ? "h-8 w-full" : ""} ${className}`}
      aria-hidden
    >
      <path
        d={path}
        fill="none"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        {...pathStrokeProps}
      />
      <circle
        cx={chartWidth}
        cy={latestY}
        r="2"
        fill={strokeColor ?? undefined}
        className={strokeColor ? undefined : strokeClassName.replace("stroke-", "fill-")}
      />
    </svg>
  );
}

export function EraTrendChip({ trend }: { trend: number | null | undefined }) {
  if (trend == null) {
    return null;
  }
  const up = trend > 0;
  const flat = trend === 0;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${
        flat
          ? "border-zinc-700 bg-zinc-800/80 text-zinc-400"
          : up
            ? "border-red-500/30 bg-red-500/10 text-red-300"
            : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      }`}
    >
      {flat ? "—" : up ? "▲" : "▼"} {Math.abs(trend).toFixed(1)}
    </span>
  );
}
