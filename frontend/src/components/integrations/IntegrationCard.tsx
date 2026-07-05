"use client";

import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Loader2,
} from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { formatRelativeTime } from "@/lib/datetime";
import { integrationDetailPath } from "@/lib/integration-routes";
import { integrationListCardChips } from "@/lib/integration-summary";
import type { IntegrationDefinition, IntegrationStatus } from "@/lib/integrations";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

import { IntegrationLogo } from "./IntegrationLogos";
import { IntegrationStatusBadge } from "./IntegrationStatusBadge";

interface IntegrationCardProps {
  app: IntegrationDefinition;
  status: IntegrationStatus;
  connected: boolean;
  syncing: boolean;
  latestJob: IntegrationSyncJobStatusResponse | null;
  runCount: number;
  returnTo?: string;
}

function syncProgressPercent(
  job: IntegrationSyncJobStatusResponse | null,
): number | null {
  const stats = job?.progress_stats;
  if (!stats) return null;
  if (stats.files_total && stats.files_total > 0) {
    return Math.round(
      ((stats.files_completed ?? 0) / stats.files_total) * 100,
    );
  }
  if (stats.branches_total && stats.branches_total > 0) {
    return Math.round(
      ((stats.branches_completed ?? 0) / stats.branches_total) * 100,
    );
  }
  return null;
}

export function IntegrationCard({
  app,
  status,
  connected,
  syncing,
  latestJob,
  runCount,
  returnTo,
}: IntegrationCardProps) {
  const { config } = useIntegrations();
  const chips = integrationListCardChips(app.id, config, connected);
  const isActive =
    syncing || latestJob?.status === "running" || latestJob?.status === "queued";
  const isFailed = latestJob?.status === "failed";
  const progressPercent = syncProgressPercent(latestJob);
  const href = integrationDetailPath(app.id, {
    tab: connected ? "overview" : "configuration",
    returnTo,
  });

  const orgRosterIndex = chips.indexOf("Org roster");
  const scopeChipCount =
    connected && orgRosterIndex > 0 ? orgRosterIndex : 0;

  const borderClass = isActive
    ? "border-sky-500/35 shadow-[0_0_0_1px_rgba(14,165,233,0.12)]"
    : isFailed
      ? "border-red-500/25"
      : connected
        ? "border-emerald-500/20"
        : "border-zinc-800/80";

  return (
    <li>
      <Link
        href={href}
        className={`group relative flex h-full flex-col overflow-hidden rounded-2xl border bg-zinc-950/70 p-5 pl-[1.375rem] backdrop-blur-sm transition duration-300 hover:-translate-y-0.5 hover:border-zinc-600/70 hover:bg-zinc-950/90 hover:shadow-xl hover:shadow-black/25 ${borderClass}`}
      >
        <div
          className={`absolute inset-y-3 left-0 w-[3px] rounded-r-full transition-opacity group-hover:opacity-100 ${
            connected ? app.accentBg : "bg-zinc-700/80"
          } ${isActive ? "opacity-100" : "opacity-80"}`}
          aria-hidden
        />

        <div className="flex items-start gap-4">
          <div
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1 ring-white/10 ${app.accentBg}`}
          >
            <IntegrationLogo
              id={app.id}
              className={`h-5 w-5 ${app.iconClassName}`}
            />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-base font-semibold tracking-tight text-zinc-100">
                {app.name}
              </h3>
              <IntegrationStatusBadge status={status} size="md" />
            </div>
            <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-zinc-500">
              {app.description}
            </p>
          </div>
        </div>

        {chips.length > 0 && (
          <ul className="mt-4 flex flex-wrap gap-1.5">
            {chips.map((chip, index) => {
              const isScopeChip = connected && index < scopeChipCount;
              return (
                <li
                  key={chip}
                  className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${
                    isScopeChip
                      ? "border-sky-500/20 bg-sky-500/5 text-sky-200/90"
                      : "border-zinc-700/70 bg-zinc-900/50 text-zinc-400"
                  }`}
                >
                  {chip}
                </li>
              );
            })}
          </ul>
        )}

        <div className="mt-4 flex flex-1 flex-col justify-end">
          {(isActive || isFailed || (connected && latestJob?.completed_at)) && (
            <div
              className={`rounded-xl border px-3 py-2.5 ${
                isFailed
                  ? "border-red-500/20 bg-red-500/5"
                  : isActive
                    ? "border-sky-500/20 bg-sky-500/5"
                    : "border-zinc-800/80 bg-zinc-900/40"
              }`}
            >
              {isActive && (
                <div className="space-y-2">
                  <p className="flex items-center gap-2 text-xs text-sky-300">
                    <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
                    <span className="truncate">
                      {latestJob?.progress_message ?? "Import in progress…"}
                    </span>
                  </p>
                  {progressPercent !== null && (
                    <div className="h-1 overflow-hidden rounded-full bg-sky-950/80">
                      <div
                        className="h-full rounded-full bg-sky-400 transition-all duration-500"
                        style={{ width: `${Math.max(progressPercent, 4)}%` }}
                      />
                    </div>
                  )}
                </div>
              )}

              {isFailed && (
                <p className="flex items-start gap-2 text-xs text-red-300">
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span className="line-clamp-2">
                    {latestJob?.error ?? "Last import failed — open details to retry."}
                  </span>
                </p>
              )}

              {!isActive && !isFailed && connected && latestJob?.completed_at && (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <span className="inline-flex items-center gap-1.5 text-emerald-300/90">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    Imported {formatRelativeTime(latestJob.completed_at)}
                  </span>
                  {latestJob.result && (
                    <span className="text-zinc-500">
                      {latestJob.result.graph_nodes_created.toLocaleString()} records
                    </span>
                  )}
                  {runCount > 0 && (
                    <span className="inline-flex items-center gap-1 text-zinc-600">
                      <Clock3 className="h-3 w-3 shrink-0" />
                      {runCount} sync{runCount === 1 ? "" : "s"}
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="mt-4 flex items-center justify-between gap-3 border-t border-zinc-800/60 pt-4">
            <p className="text-xs text-zinc-500">
              {connected
                ? isActive
                  ? "View live progress"
                  : isFailed
                    ? "Review error & retry"
                    : runCount === 0
                      ? "Ready for first import"
                      : "Manage sync & history"
                : "Connect to import workspace data"}
            </p>
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700/80 bg-zinc-900/60 px-3 py-1.5 text-xs font-medium text-zinc-200 transition group-hover:border-zinc-600 group-hover:bg-zinc-800/80 group-hover:text-white">
              {connected ? "Open" : "Set up"}
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
            </span>
          </div>
        </div>
      </Link>
    </li>
  );
}
