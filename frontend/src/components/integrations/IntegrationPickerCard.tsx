"use client";

import { CheckCircle2, CircleDashed, Pencil, Settings2 } from "lucide-react";

import type { IntegrationDefinition } from "@/lib/integrations";

import { IntegrationLogo } from "./IntegrationLogos";

export type IntegrationPickerStatus = "not_connected" | "draft" | "ready";

interface IntegrationPickerCardProps {
  app: IntegrationDefinition;
  status: IntegrationPickerStatus;
  onConfigure: () => void;
  justSaved?: boolean;
}

const STATUS_CONFIG: Record<
  IntegrationPickerStatus,
  { label: string; className: string; icon?: typeof CheckCircle2 }
> = {
  not_connected: {
    label: "Not connected",
    className: "border-zinc-700/80 bg-zinc-900/50 text-zinc-400",
  },
  draft: {
    label: "Draft",
    className: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  },
  ready: {
    label: "Ready",
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
    icon: CheckCircle2,
  },
};

export function IntegrationPickerCard({
  app,
  status,
  onConfigure,
  justSaved = false,
}: IntegrationPickerCardProps) {
  const statusMeta = justSaved
    ? {
        label: "Connected",
        className: "border-emerald-400/50 bg-emerald-500/20 text-emerald-100",
        icon: CheckCircle2,
      }
    : STATUS_CONFIG[status];
  const StatusIcon = statusMeta.icon ?? CircleDashed;
  const ctaLabel =
    status === "ready" ? "Edit" : status === "draft" ? "Continue setup" : "Configure";

  return (
    <button
      type="button"
      onClick={onConfigure}
      className={`group relative flex w-full flex-col rounded-2xl border bg-gradient-to-b from-zinc-900/70 to-zinc-950/90 p-5 text-left hover:shadow-lg hover:shadow-black/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/50 ${
        justSaved
          ? "integration-saved-flash border-emerald-400/80"
          : `transition duration-300 hover:border-zinc-600/80 ${
              status === "ready"
                ? "border-emerald-500/25"
                : status === "draft"
                  ? "border-amber-500/25"
                  : "border-zinc-800/80"
            }`
      }`}
    >
      {justSaved ? (
        <span className="sr-only">{app.name} connected — credentials saved.</span>
      ) : null}

      <div
        className={`pointer-events-none absolute -right-8 -top-8 h-32 w-32 overflow-hidden rounded-full opacity-40 blur-3xl transition group-hover:opacity-60 ${app.accentBg}`}
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
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${statusMeta.className}`}
        >
          <StatusIcon className="h-3 w-3 shrink-0" />
          {statusMeta.label}
        </span>
      </div>

      <div className="relative mt-4 min-w-0 flex-1">
        <h3 className="text-base font-semibold text-zinc-100">{app.name}</h3>
        <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-zinc-500">
          {app.description}
        </p>
      </div>

      <div className="relative mt-4 flex items-center gap-2 border-t border-zinc-800/60 pt-4 text-xs font-medium text-zinc-400 transition group-hover:text-zinc-200">
        {status === "ready" ? (
          <Pencil className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <Settings2 className="h-3.5 w-3.5 shrink-0" />
        )}
        {ctaLabel}
      </div>
    </button>
  );
}
