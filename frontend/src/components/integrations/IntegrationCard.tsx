"use client";

import { Loader2 } from "lucide-react";

import type { IntegrationDefinition, IntegrationStatus } from "@/lib/integrations";

import { IntegrationLogo } from "./IntegrationLogos";

const STATUS_STYLES: Record<
  IntegrationStatus,
  { label: string; className: string }
> = {
  connected: {
    label: "Connected",
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  },
  disconnected: {
    label: "Disconnected",
    className: "border-zinc-700 bg-zinc-800/50 text-zinc-400",
  },
  syncing: {
    label: "Syncing",
    className: "border-sky-500/30 bg-sky-500/10 text-sky-400",
  },
};

interface IntegrationCardProps {
  app: IntegrationDefinition;
  status: IntegrationStatus;
  onAction: () => void;
}

export function IntegrationCard({ app, status, onAction }: IntegrationCardProps) {
  const badge = STATUS_STYLES[status];
  const isConnected = status === "connected" || status === "syncing";

  return (
    <article className="group flex flex-col rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-900/80 to-zinc-950 p-5 shadow-sm transition hover:border-zinc-700 hover:shadow-lg hover:shadow-black/20">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div
          className={`flex h-12 w-12 items-center justify-center rounded-xl ${app.accentBg}`}
        >
          <IntegrationLogo
            id={app.id}
            className={`h-7 w-7 ${app.iconClassName}`}
          />
        </div>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${badge.className}`}
        >
          {status === "syncing" && (
            <Loader2 className="h-3 w-3 animate-spin" />
          )}
          {badge.label}
        </span>
      </div>

      <h3 className="text-base font-semibold text-zinc-100">{app.name}</h3>
      <p className="mt-1 text-sm text-zinc-400">{app.description}</p>

      <div className="mt-4 flex-1 rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-3 py-2.5">
        <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
          Syncs to Cognee
        </p>
        <p className="mt-1 text-xs leading-relaxed text-zinc-400">
          {app.syncsToCognee}
        </p>
      </div>

      <button
        type="button"
        onClick={onAction}
        className="mt-4 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm font-medium text-zinc-100 transition group-hover:border-zinc-600 hover:bg-zinc-800"
      >
        {isConnected ? "Configure" : "Connect"}
      </button>
    </article>
  );
}
