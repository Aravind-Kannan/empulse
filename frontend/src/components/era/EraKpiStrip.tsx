import Link from "next/link";

import type { EraRiskHistoryPoint, EraTeamSummary } from "@/lib/types";

import { ERA_DIMENSION_COLORS } from "./era-colors";
import { EraRiskSparkline, EraTrendChip } from "./EraRiskSparkline";

interface EraKpiStripProps {
  summary: EraTeamSummary;
  integrationCount: number;
  teamHistory?: EraRiskHistoryPoint[];
  loading?: boolean;
}

function SkeletonCard() {
  return (
    <div className="min-w-[9.5rem] flex-1 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="h-3 w-20 rounded bg-zinc-800" />
      <div className="mt-3 h-7 w-12 rounded bg-zinc-800" />
      <div className="mt-2 h-3 w-24 rounded bg-zinc-800" />
    </div>
  );
}

export function EraKpiStrip({
  summary,
  integrationCount,
  teamHistory = [],
  loading = false,
}: EraKpiStripProps) {
  if (loading) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-1">
        {Array.from({ length: 6 }).map((_, index) => (
          <SkeletonCard key={index} />
        ))}
      </div>
    );
  }

  const driver = ERA_DIMENSION_COLORS[summary.top_risk_driver];

  return (
    <div className="flex gap-3 overflow-x-auto pb-1">
      <div className="min-w-[9.5rem] flex-1 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        <p className="text-xs uppercase tracking-wide text-zinc-500">Team risk</p>
        <div className="mt-1 flex items-center gap-2">
          <p className="text-2xl font-semibold text-zinc-100">
            {summary.avg_risk_score}%
          </p>
          <EraTrendChip trend={summary.avg_risk_trend_7d} />
        </div>
        <div className="mt-2 flex items-center justify-between gap-2">
          <p className={`text-xs ${driver.text}`}>
            Top driver: {driver.label}
          </p>
          <EraRiskSparkline history={teamHistory} width={72} height={24} />
        </div>
      </div>

      <div
        className={`min-w-[9.5rem] flex-1 rounded-xl border p-4 ${
          summary.high_risk_count > 0
            ? "border-red-500/30 bg-red-500/5"
            : "border-zinc-800 bg-zinc-900/40"
        }`}
      >
        <p className="text-xs uppercase tracking-wide text-zinc-500">High risk</p>
        <p
          className={`mt-1 text-2xl font-semibold ${
            summary.high_risk_count > 0 ? "text-red-300" : "text-zinc-100"
          }`}
        >
          {summary.high_risk_count}
        </p>
        <p className="mt-1 text-xs text-zinc-500">people</p>
      </div>

      <Link
        href="/kra?filter=spof"
        className="min-w-[9.5rem] flex-1 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 transition hover:border-fuchsia-500/40 hover:bg-zinc-900/60"
      >
        <p className="text-xs uppercase tracking-wide text-zinc-500">SPOF</p>
        <p className="mt-1 text-2xl font-semibold text-fuchsia-300">
          {summary.spof_component_count}
        </p>
        <p className="mt-1 text-xs text-fuchsia-400/80">components → KRA</p>
      </Link>

      <div className="min-w-[9.5rem] flex-1 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        <p className="text-xs uppercase tracking-wide text-zinc-500">Open P1</p>
        <p className="mt-1 text-2xl font-semibold text-zinc-100">
          {summary.open_p1_count}
        </p>
        <p className="mt-1 text-xs text-zinc-500">issues</p>
      </div>

      <div className="min-w-[9.5rem] flex-1 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        <p className="text-xs uppercase tracking-wide text-zinc-500">
          Undocumented
        </p>
        <p className="mt-1 text-2xl font-semibold text-zinc-100">
          {summary.undocumented_incident_count}
        </p>
        <p className="mt-1 text-xs text-zinc-500">incidents</p>
      </div>

      <div className="min-w-[11rem] flex-[1.2] rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        <p className="text-xs uppercase tracking-wide text-zinc-500">
          Data health
        </p>
        <p className="mt-1 text-2xl font-semibold text-zinc-100">
          {summary.data_health_pct}%
        </p>
        <div className="mt-2 h-2 rounded-full bg-zinc-800">
          <div
            className="h-full rounded-full bg-emerald-500"
            style={{ width: `${summary.data_health_pct}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-zinc-500">
          {integrationCount}/4 integrations synced
        </p>
      </div>
    </div>
  );
}
