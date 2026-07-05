import {
  Clock,
  Download,
  Loader2,
  RefreshCw,
  SlidersHorizontal,
  Users,
} from "lucide-react";

import type { EraEmployeeMetrics, EraRecoveryEstimate } from "@/lib/types";

import { EraNotificationsButton } from "./EraNotificationsButton";
import { exportEmployeesCsv, formatSyncFreshness } from "./era-utils";

interface EraCommandHeaderProps {
  recovery: EraRecoveryEstimate;
  syncFreshness: Parameters<typeof formatSyncFreshness>[0];
  warnings: string[];
  unmappedCount: number;
  alertsRefreshKey: number;
  employees: EraEmployeeMetrics[];
  highRiskCount: number;
  refreshing: boolean;
  onRefresh: () => void;
  onOpenNotifications: () => void;
  onOpenAlertsSettings: () => void;
}

export function EraCommandHeader({
  recovery,
  syncFreshness,
  warnings,
  unmappedCount,
  alertsRefreshKey,
  employees,
  highRiskCount,
  refreshing,
  onRefresh,
  onOpenNotifications,
  onOpenAlertsSettings,
}: EraCommandHeaderProps) {
  const sync = formatSyncFreshness(syncFreshness);
  const syncClass =
    sync.tone === "ok"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : sync.tone === "warn"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
        : "border-red-500/30 bg-red-500/10 text-red-300";

  const activeCount = employees.length;
  const severeScenario = highRiskCount >= 3;
  const atRiskLabel =
    highRiskCount > 0
      ? `${highRiskCount} high risk`
      : `${activeCount} active`;

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
          Employee risk assessment
        </p>
        <h1 className="mt-0.5 text-xl font-semibold text-zinc-100">ERA Command Center</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 ${
              severeScenario
                ? "border-amber-500/25 bg-amber-500/5"
                : "border-zinc-800/80 bg-zinc-900/40"
            }`}
          >
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-md border ${
                severeScenario
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                  : "border-violet-500/30 bg-violet-500/10 text-violet-300"
              }`}
            >
              <Clock className="h-3.5 w-3.5" aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block text-[9px] font-medium uppercase tracking-wide text-zinc-500">
                {severeScenario ? "Recovery if top 3 leave" : "Est. recovery"}
              </span>
              <span className="mt-0.5 block text-sm font-semibold tabular-nums text-zinc-100">
                {recovery.min}–{recovery.max} weeks
              </span>
            </span>
          </span>

          <span className="inline-flex items-center gap-2 rounded-lg border border-zinc-800/80 bg-zinc-900/40 px-2.5 py-1.5">
            <span className="flex h-6 w-6 items-center justify-center rounded-md border border-zinc-700/80 bg-zinc-950/50 text-zinc-400">
              <Users className="h-3.5 w-3.5" aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block text-[9px] font-medium uppercase tracking-wide text-zinc-500">
                Team in scope
              </span>
              <span
                className={`mt-0.5 block text-sm font-semibold tabular-nums ${
                  highRiskCount > 0 ? "text-red-300" : "text-zinc-100"
                }`}
              >
                {atRiskLabel}
              </span>
            </span>
          </span>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${syncClass}`}
        >
          {sync.label} {sync.tone === "ok" ? "✓" : ""}
        </span>
        <EraNotificationsButton
          warnings={warnings}
          unmappedCount={unmappedCount}
          refreshKey={alertsRefreshKey}
          onClick={onOpenNotifications}
        />
        <button
          type="button"
          onClick={onOpenAlertsSettings}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          Alerts
        </button>
        <button
          type="button"
          onClick={() => exportEmployeesCsv(employees)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800"
        >
          <Download className="h-3.5 w-3.5" />
          Export
        </button>
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 disabled:opacity-60"
        >
          {refreshing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Refresh
        </button>
      </div>
    </div>
  );
}
