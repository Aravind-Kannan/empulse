import { Loader2 } from "lucide-react";

import type { IntegrationStatus } from "@/lib/integrations";

const STATUS_STYLES: Record<
  IntegrationStatus,
  { label: string; className: string }
> = {
  connected: {
    label: "Connected",
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  },
  available: {
    label: "Not connected",
    className: "border-zinc-700/80 bg-zinc-900/40 text-zinc-500",
  },
  disconnected: {
    label: "Disconnected",
    className: "border-zinc-600/50 bg-zinc-800/40 text-zinc-400",
  },
  syncing: {
    label: "Syncing",
    className: "border-sky-500/30 bg-sky-500/10 text-sky-400",
  },
  pending: {
    label: "Pending verification",
    className: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  },
};

interface IntegrationStatusBadgeProps {
  status: IntegrationStatus;
  size?: "sm" | "md";
}

export function IntegrationStatusBadge({
  status,
  size = "sm",
}: IntegrationStatusBadgeProps) {
  const badge = STATUS_STYLES[status];
  const sizeClass =
    size === "md"
      ? "px-2.5 py-1 text-xs"
      : "px-2 py-0.5 text-[10px]";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-medium ${badge.className} ${sizeClass}`}
    >
      {status === "syncing" && (
        <Loader2 className={size === "md" ? "h-3 w-3 animate-spin" : "h-2.5 w-2.5 animate-spin"} />
      )}
      {badge.label}
    </span>
  );
}
