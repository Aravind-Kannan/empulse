"use client";

import { useMemo } from "react";
import { Database, Plug, SkipForward, Sparkles } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import {
  INTEGRATION_CATALOG,
  getConnectedIntegrationIds,
} from "@/lib/integrations";
import { jobsForIntegration } from "@/lib/sync-jobs";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

function aggregateSyncStats(jobs: IntegrationSyncJobStatusResponse[]) {
  const completed = jobs.filter((job) => job.status === "completed" && job.result);
  let ingested = 0;
  let skipped = 0;

  for (const job of completed) {
    const result = job.result!;
    ingested += result.graph_nodes_created ?? 0;
    skipped += result.items_skipped ?? 0;
  }

  return { ingested, skipped, completedCount: completed.length };
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: typeof Database;
}) {
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-4 py-3 backdrop-blur-sm">
      <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-zinc-500">{hint}</p>}
    </div>
  );
}

export function IntegrationsStatsRow() {
  const { config, syncJobs } = useIntegrations();
  const connectedCount = getConnectedIntegrationIds(config).length;
  const stats = useMemo(() => aggregateSyncStats(syncJobs), [syncJobs]);
  const totalRuns = useMemo(
    () =>
      INTEGRATION_CATALOG.reduce(
        (sum, app) => sum + jobsForIntegration(syncJobs, app.id).length,
        0,
      ),
    [syncJobs],
  );

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        icon={Plug}
        label="Connected"
        value={connectedCount}
        hint={`of ${INTEGRATION_CATALOG.length} available sources`}
      />
      <StatCard
        icon={Sparkles}
        label="Synced"
        value={stats.ingested || "—"}
        hint={
          stats.completedCount
            ? `${stats.completedCount} completed sync(s)`
            : "Run sync to import data"
        }
      />
      <StatCard
        icon={SkipForward}
        label="Skipped"
        value={stats.skipped || "—"}
        hint="Unchanged since last sync"
      />
      <StatCard
        icon={Database}
        label="Total runs"
        value={totalRuns || "—"}
        hint="Across all integrations"
      />
    </div>
  );
}
