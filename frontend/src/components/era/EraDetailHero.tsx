"use client";

import { AlertTriangle } from "lucide-react";

import type { EraEmployeeMetrics } from "@/lib/types";

import { getInitials } from "./era-utils";

interface EraDetailHeroProps {
  employee: EraEmployeeMetrics;
  blastRadiusNarrative?: string | null;
}

function riskRingStroke(level: EraEmployeeMetrics["risk_level"]): string {
  if (level === "high") return "#f87171";
  if (level === "medium") return "#fbbf24";
  return "#34d399";
}

export function EraDetailHero({
  employee,
  blastRadiusNarrative,
}: EraDetailHeroProps) {
  const score = Math.round(employee.risk_factor_score);
  const ringRadius = 40;
  const circumference = 2 * Math.PI * ringRadius;
  const dash = (score / 100) * circumference;
  const recovery = employee.recovery_estimate_weeks;
  const componentNames = (employee.affected_components ?? [])
    .slice(0, 2)
    .map((component) => component.name);

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-lg font-semibold text-violet-200">
            {getInitials(employee.name)}
          </div>
          <div className="min-w-0">
            <h2 className="text-xl font-semibold text-zinc-100">{employee.name}</h2>
            <p className="text-sm text-zinc-400">{employee.role}</p>
            <p className="mt-0.5 text-xs text-zinc-500">
              {employee.employee_id} · {employee.email}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase ${
                  employee.risk_level === "high"
                    ? "border-red-500/30 bg-red-500/10 text-red-300"
                    : employee.risk_level === "medium"
                      ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                      : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                }`}
              >
                {employee.risk_level === "high" && (
                  <AlertTriangle className="h-3 w-3" />
                )}
                {employee.risk_level}
              </span>
              {employee.departure_watchlist && (
                <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-300">
                  Departure watchlist
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="relative mx-auto h-28 w-28 shrink-0 sm:mx-0">
          <svg className="h-28 w-28 -rotate-90" viewBox="0 0 112 112">
            <circle
              cx="56"
              cy="56"
              r={ringRadius}
              fill="none"
              stroke="#27272a"
              strokeWidth="10"
            />
            <circle
              cx="56"
              cy="56"
              r={ringRadius}
              fill="none"
              stroke={riskRingStroke(employee.risk_level)}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={`${dash} ${circumference}`}
              className="motion-safe:transition-all motion-safe:duration-700 motion-reduce:transition-none"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold text-zinc-100">{score}%</span>
            <span className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
              Risk
            </span>
          </div>
        </div>
      </div>

      {(blastRadiusNarrative || (recovery && componentNames.length > 0)) && (
        <p className="mt-4 text-sm leading-relaxed text-zinc-400">
          {blastRadiusNarrative ??
            `If ${employee.name.split(" ")[0]} leaves, ${componentNames.join(" + ")} recovery estimated ${recovery?.min}–${recovery?.max} weeks.`}
        </p>
      )}
    </section>
  );
}
