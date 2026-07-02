"use client";

import type { EraRiskHistoryPoint } from "@/lib/types";

interface EraRiskSparklineProps {
  history: EraRiskHistoryPoint[];
  width?: number;
  height?: number;
  strokeClassName?: string;
  className?: string;
}

function buildPath(
  history: EraRiskHistoryPoint[],
  width: number,
  height: number,
): string {
  if (history.length === 0) {
    return "";
  }
  const scores = history.map((point) => point.risk_factor_score);
  const min = Math.min(...scores, 0);
  const max = Math.max(...scores, 100);
  const range = max - min || 1;
  const step = history.length > 1 ? width / (history.length - 1) : 0;

  return history
    .map((point, index) => {
      const x = index * step;
      const y = height - ((point.risk_factor_score - min) / range) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function EraRiskSparkline({
  history,
  width = 96,
  height = 28,
  strokeClassName = "stroke-violet-400",
  className = "",
}: EraRiskSparklineProps) {
  if (history.length < 2) {
    return (
      <div
        className={`flex items-center text-[10px] text-zinc-600 ${className}`}
        style={{ width, height }}
      >
        No trend yet
      </div>
    );
  }

  const path = buildPath(history, width, height);
  const latest = history[history.length - 1]?.risk_factor_score ?? 0;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      aria-hidden
    >
      <path
        d={path}
        fill="none"
        className={strokeClassName}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={width}
        cy={
          height -
          ((latest - Math.min(...history.map((p) => p.risk_factor_score), 0)) /
            (Math.max(...history.map((p) => p.risk_factor_score), 100) -
              Math.min(...history.map((p) => p.risk_factor_score), 0) || 1)) *
            height
        }
        r="2"
        className={strokeClassName.replace("stroke-", "fill-")}
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
