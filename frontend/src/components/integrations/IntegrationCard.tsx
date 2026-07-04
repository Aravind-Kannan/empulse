"use client";

import Link from "next/link";
import { ArrowUpRight, CheckCircle2, Loader2 } from "lucide-react";

import { formatLocalDateTime } from "@/lib/datetime";
import { integrationDetailPath } from "@/lib/integration-routes";
import type { IntegrationDefinition, IntegrationStatus } from "@/lib/integrations";
import { syncStatusLabel } from "@/lib/sync-jobs";
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

export function IntegrationCard({
  app,
  status,
  connected,
  syncing,
  latestJob,
  runCount,
  returnTo,
}: IntegrationCardProps) {
  const syncLabel = syncStatusLabel(latestJob, syncing, connected);
  const isActive =
    syncing || latestJob?.status === "running" || latestJob?.status === "queued";
  const href = integrationDetailPath(app.id, {
    tab: connected ? "overview" : "configuration",
    returnTo,
  });

  return (
    <li>
      <Link
        href={href}
        className={`group relative flex h-full flex-col overflow-hidden rounded-2xl border bg-gradient-to-b from-zinc-900/70 to-zinc-950/90 p-5 transition duration-300 hover:border-zinc-600/80 hover:shadow-lg hover:shadow-black/20 ${
          isActive
            ? "border-sky-500/30 ring-1 ring-sky-500/20"
            : connected
              ? "border-emerald-500/20"
              : "border-zinc-800/80"
        }`}
      >
        <div
          className={`pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full opacity-40 blur-3xl transition group-hover:opacity-60 ${app.accentBg}`}
          aria-hidden
        />

        <div className="relative flex items-start justify-between gap-3">
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl shadow-inner ${app.accentBg}`}
          >
            <IntegrationLogo
              id={app.id}
              className={`h-6 w-6 ${app.iconClassName}`}
            />
          </div>
          <IntegrationStatusBadge status={status} size="md" />
        </div>

        <div className="relative mt-4 min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-zinc-100">{app.name}</h3>
            <ArrowUpRight className="h-4 w-4 shrink-0 text-zinc-600 transition group-hover:text-zinc-300" />
          </div>
          <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-zinc-500">
            {app.description}
          </p>
        </div>

        <div className="relative mt-4 space-y-2 border-t border-zinc-800/60 pt-4">
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className={syncLabel.className}>{syncLabel.text}</span>
            {runCount > 0 && (
              <span className="tabular-nums text-zinc-600">
                {runCount} run{runCount === 1 ? "" : "s"}
              </span>
            )}
          </div>

          {connected && !isActive && latestJob?.status === "completed" && latestJob.completed_at && (
            <p className="flex items-center gap-1.5 text-[11px] text-zinc-500">
              <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-500/80" />
              Last sync {formatLocalDateTime(latestJob.completed_at)}
              {latestJob.result && (
                <span className="text-zinc-600">
                  · {latestJob.result.graph_nodes_created} synced
                </span>
              )}
            </p>
          )}

          {isActive && (
            <p className="flex items-center gap-1.5 text-[11px] text-sky-400/90">
              <Loader2 className="h-3 w-3 animate-spin" />
              {latestJob?.progress_message ?? "Sync in progress…"}
            </p>
          )}

          <p className="text-[11px] font-medium text-zinc-500">
            {connected ? "Manage integration →" : "Connect →"}
          </p>
        </div>
      </Link>
    </li>
  );
}
