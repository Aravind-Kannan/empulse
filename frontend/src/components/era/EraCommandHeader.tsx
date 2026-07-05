import {
  Download,
  Loader2,
  RefreshCw,
  SlidersHorizontal,
} from "lucide-react";

import type { EraEmployeeMetrics } from "@/lib/types";

import { exportEmployeesCsv, formatSyncFreshness } from "./era-utils";

interface EraCommandHeaderProps {
  syncFreshness: Parameters<typeof formatSyncFreshness>[0];
  employees: EraEmployeeMetrics[];
  refreshing: boolean;
  onRefresh: () => void;
  onOpenAlertsSettings: () => void;
}

export function EraCommandHeader({
  syncFreshness,
  employees,
  refreshing,
  onRefresh,
  onOpenAlertsSettings,
}: EraCommandHeaderProps) {
  const sync = formatSyncFreshness(syncFreshness);
  const syncClass =
    sync.tone === "ok"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : sync.tone === "warn"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
        : "border-red-500/30 bg-red-500/10 text-red-300";

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
          Employee risk assessment
        </p>
        <h1 className="mt-0.5 text-xl font-semibold text-zinc-100">ERA Command Center</h1>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${syncClass}`}
        >
          {sync.label} {sync.tone === "ok" ? "✓" : ""}
        </span>
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
