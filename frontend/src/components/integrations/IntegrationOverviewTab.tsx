"use client";

import {
  CheckCircle2,
  Database,
  History,
  Loader2,
  Settings2,
} from "lucide-react";

import { formatLocalDateTime } from "@/lib/datetime";
import { integrationConfigSummary } from "@/lib/integration-summary";
import type { IntegrationDefinition } from "@/lib/integrations";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";
import { useIntegrations } from "@/context/IntegrationsContext";

import { CognifyProgress } from "./CognifyProgress";
import { RepoSyncProgress } from "./RepoSyncProgress";
import { SyncDuration } from "./SyncDuration";

interface IntegrationOverviewTabProps {
  app: IntegrationDefinition;
  connected: boolean;
  syncing: boolean;
  latestJob: IntegrationSyncJobStatusResponse | null;
  sourceJobs: IntegrationSyncJobStatusResponse[];
  onOpenConfiguration: () => void;
}

function StatTile({
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
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4 backdrop-blur-sm">
      <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="mt-2 text-xl font-semibold tabular-nums text-zinc-100">{value}</p>
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}

export function IntegrationOverviewTab({
  app,
  connected,
  syncing,
  latestJob,
  sourceJobs,
  onOpenConfiguration,
}: IntegrationOverviewTabProps) {
  const { config } = useIntegrations();
  const summaryRows = integrationConfigSummary(app.id, config);
  const completedJobs = sourceJobs.filter((job) => job.status === "completed");
  const failedJobs = sourceJobs.filter((job) => job.status === "failed");
  const totalIngested = completedJobs.reduce(
    (sum, job) => sum + (job.result?.graph_nodes_created ?? 0),
    0,
  );
  const isActive =
    syncing || latestJob?.status === "running" || latestJob?.status === "queued";

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile
          icon={History}
          label="Sync runs"
          value={sourceJobs.length || "—"}
          hint={
            failedJobs.length > 0
              ? `${failedJobs.length} failed`
              : sourceJobs.length === 0
                ? "No runs yet"
                : undefined
          }
        />
        <StatTile
          icon={Database}
          label="Records synced"
          value={totalIngested || "—"}
          hint={
            completedJobs.length > 0
              ? `From ${completedJobs.length} completed run(s)`
              : "After first successful sync"
          }
        />
        <StatTile
          icon={CheckCircle2}
          label="Last sync"
          value={
            latestJob?.completed_at
              ? formatLocalDateTime(latestJob.completed_at)
              : isActive
                ? "In progress"
                : "—"
          }
          hint={
            latestJob?.status === "failed"
              ? "Last run failed — check Runs tab"
              : connected
                ? "Up to date"
                : "Connect to start syncing"
          }
        />
      </div>

      {isActive && latestJob && (
        <section className="rounded-2xl border border-sky-500/25 bg-gradient-to-b from-sky-950/30 to-zinc-950/40 p-5">
          <div className="flex items-center gap-2 text-sm font-medium text-sky-300">
            <Loader2 className="h-4 w-4 animate-spin" />
            Sync in progress
            <SyncDuration job={latestJob} className="text-sky-400/80" />
          </div>
          {latestJob.progress_message && (
            <p className="mt-2 text-sm text-zinc-300">{latestJob.progress_message}</p>
          )}
          {latestJob.job_kind === "github_repo" && latestJob.progress_stats && (
            <div className="mt-4 max-w-lg">
              <RepoSyncProgress job={latestJob} />
            </div>
          )}
          {latestJob.phase === "cognifying" && (
            <div className="mt-4 max-w-lg">
              <CognifyProgress job={latestJob} />
            </div>
          )}
        </section>
      )}

      {connected && summaryRows.length > 0 && (
        <section className="rounded-2xl border border-zinc-800/80 bg-zinc-950/30 p-5 backdrop-blur-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-medium text-zinc-200">Current configuration</h3>
            <button
              type="button"
              onClick={onOpenConfiguration}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-sky-400 transition hover:text-sky-300"
            >
              <Settings2 className="h-3.5 w-3.5" />
              Edit configuration
            </button>
          </div>
          <dl className="mt-4 divide-y divide-zinc-800/60">
            {summaryRows.map((row) => (
              <div
                key={row.label}
                className="flex flex-col gap-0.5 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4"
              >
                <dt className="shrink-0 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  {row.label}
                </dt>
                <dd className="text-sm text-zinc-300 sm:text-right">{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {!connected && (
        <section className="rounded-2xl border border-dashed border-zinc-800 bg-zinc-950/20 px-5 py-8 text-center">
          <p className="text-sm text-zinc-400">
            Connect {app.name} to start importing data into your workspace.
          </p>
          <button
            type="button"
            onClick={onOpenConfiguration}
            className="mt-4 inline-flex items-center justify-center rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-white"
          >
            Connect {app.name}
          </button>
        </section>
      )}
    </div>
  );
}
