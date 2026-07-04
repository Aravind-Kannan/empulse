import { Download, Loader2, RefreshCw, SlidersHorizontal } from "lucide-react";

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

  const subtitle =
    highRiskCount >= 3
      ? `If top ${Math.min(3, highRiskCount)} at-risk employees left today → est. recovery ${recovery.min}–${recovery.max} weeks`
      : `Team continuity posture — est. recovery ${recovery.min}–${recovery.max} weeks if key people leave`;

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">ERA Command Center</h1>
        <p className="mt-1 max-w-3xl text-sm text-zinc-400">{subtitle}</p>
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
