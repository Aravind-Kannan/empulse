"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  Bell,
  Building2,
  FileWarning,
  GitBranch,
  Network,
  PanelRightOpen,
  UserRoundSearch,
} from "lucide-react";

import type { EraTeamSummary } from "@/lib/types";

interface EraKpiStripProps {
  summary: EraTeamSummary;
  unmappedCount?: number;
  loading?: boolean;
  onOpenP1Issues?: () => void;
  onOpenNotifications?: () => void;
}

type SignalTone = "neutral" | "warn" | "risk" | "good";

type SignalAction = "panel" | "kra" | "identity";

interface SignalMetric {
  id: string;
  label: string;
  value: string;
  hint: string;
  tone: SignalTone;
  icon: LucideIcon;
  onClick?: () => void;
  href?: string;
  action?: SignalAction;
}

function actionIndicatorLabel(action: SignalAction): string {
  if (action === "panel") return "Opens side panel";
  if (action === "kra") return "Opens KRA";
  return "Opens identity mapping";
}

function ActionIndicator({ action }: { action: SignalAction }) {
  const className = "h-3.5 w-3.5 text-zinc-500 group-hover:text-zinc-400";
  if (action === "panel") {
    return <PanelRightOpen className={className} aria-hidden />;
  }
  if (action === "kra") {
    return <Network className={className} aria-hidden />;
  }
  return <Building2 className={className} aria-hidden />;
}

function toneStyles(tone: SignalTone, active: boolean): {
  cell: string;
  icon: string;
  value: string;
} {
  if (!active) {
    return {
      cell: "hover:bg-zinc-800/35",
      icon: "border-zinc-800/80 bg-zinc-950/50 text-zinc-500",
      value: "text-zinc-200",
    };
  }
  if (tone === "risk") {
    return {
      cell: "bg-red-500/[0.06] hover:bg-red-500/10",
      icon: "border-red-500/30 bg-red-500/10 text-red-300",
      value: "text-red-200",
    };
  }
  if (tone === "warn") {
    return {
      cell: "bg-amber-500/[0.06] hover:bg-amber-500/10",
      icon: "border-amber-500/30 bg-amber-500/10 text-amber-300",
      value: "text-amber-100",
    };
  }
  if (tone === "good") {
    return {
      cell: "bg-emerald-500/[0.05] hover:bg-emerald-500/10",
      icon: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
      value: "text-emerald-100",
    };
  }
  return {
    cell: "hover:bg-zinc-800/35",
    icon: "border-zinc-800/80 bg-zinc-950/50 text-zinc-400",
    value: "text-zinc-100",
  };
}

function SignalSkeleton() {
  return (
    <div className="min-w-[8.5rem] flex-1 animate-pulse px-3 py-3">
      <div className="flex items-start gap-2.5">
        <div className="h-8 w-8 shrink-0 rounded-lg bg-zinc-800" />
        <div className="min-w-0 flex-1">
          <div className="h-2.5 w-14 rounded bg-zinc-800" />
          <div className="mt-2 h-5 w-10 rounded bg-zinc-800" />
          <div className="mt-1.5 h-2 w-16 rounded bg-zinc-800" />
        </div>
      </div>
    </div>
  );
}

function SignalCell({ metric }: { metric: SignalMetric }) {
  const active =
    metric.tone === "risk" ||
    metric.tone === "warn" ||
    (metric.id === "alerts" && metric.value !== "0");
  const styles = toneStyles(metric.tone, active);
  const Icon = metric.icon;

  const content = (
    <>
      {metric.action ? (
        <span
          className="absolute right-2.5 top-2.5"
          title={actionIndicatorLabel(metric.action)}
          aria-label={actionIndicatorLabel(metric.action)}
        >
          <ActionIndicator action={metric.action} />
        </span>
      ) : null}
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${styles.icon}`}
      >
        <Icon className="h-3.5 w-3.5" aria-hidden />
      </span>
      <span className="min-w-0 flex-1 text-left">
        <span className="block text-[9px] font-medium uppercase tracking-wide text-zinc-500">
          {metric.label}
        </span>
        <span className={`mt-0.5 block text-lg font-semibold tabular-nums leading-tight ${styles.value}`}>
          {metric.value}
        </span>
        <span className="mt-0.5 block truncate text-[10px] text-zinc-600">
          {metric.hint}
        </span>
      </span>
    </>
  );

  const className = `group relative flex min-w-[8.5rem] flex-1 items-start gap-2.5 px-3 py-3 pr-7 transition ${styles.cell}`;

  if (metric.href) {
    return (
      <Link href={metric.href} className={className}>
        {content}
      </Link>
    );
  }

  if (metric.onClick) {
    return (
      <button type="button" onClick={metric.onClick} className={className}>
        {content}
      </button>
    );
  }

  return <div className={className}>{content}</div>;
}

function buildMetrics({
  summary,
  unmappedCount,
  onOpenP1Issues,
  onOpenNotifications,
}: {
  summary: EraTeamSummary;
  unmappedCount: number;
  onOpenP1Issues?: () => void;
  onOpenNotifications?: () => void;
}): SignalMetric[] {
  const alertCount = summary.unacknowledged_alert_count ?? 0;
  const orphanCount = summary.orphan_file_count ?? 0;
  const orphanDelta = summary.orphan_delta_90d ?? 0;
  const orphanHint =
    orphanDelta > 0
      ? `${orphanCount} total · +${orphanDelta} in 90d`
      : orphanCount > 0
        ? `${orphanCount} unowned in repo`
        : "No orphan files";

  return [
    {
      id: "p1",
      label: "Open P1",
      value: String(summary.open_p1_count),
      hint: summary.open_p1_count > 0 ? "View issue list" : "No active P1s",
      tone: summary.open_p1_count > 0 ? "warn" : "good",
      icon: AlertTriangle,
      onClick: onOpenP1Issues,
      action: "panel",
    },
    {
      id: "incidents",
      label: "Undocumented",
      value: String(summary.undocumented_incident_count),
      hint:
        summary.undocumented_incident_count > 0
          ? "Solved, not written up"
          : "Incidents documented",
      tone: summary.undocumented_incident_count > 0 ? "warn" : "good",
      icon: FileWarning,
    },
    {
      id: "unmapped",
      label: "Unmapped",
      value: String(unmappedCount),
      hint: unmappedCount > 0 ? "Fix identity links" : "Activity mapped",
      tone: unmappedCount > 0 ? "warn" : "good",
      icon: UserRoundSearch,
      href: "/settings/org-chart?tab=identity",
      action: "identity",
    },
    {
      id: "orphans",
      label: "Orphan files",
      value: String(orphanCount),
      hint: orphanHint,
      tone: orphanCount > 0 || orphanDelta > 0 ? "risk" : "good",
      icon: GitBranch,
      href: "/kra",
      action: "kra",
    },
    {
      id: "alerts",
      label: "Alerts",
      value: String(alertCount),
      hint: alertCount > 0 ? "Needs review" : "All caught up",
      tone: alertCount > 0 ? "warn" : "neutral",
      icon: Bell,
      onClick: onOpenNotifications,
      action: "panel",
    },
  ];
}

export function EraKpiStrip({
  summary,
  unmappedCount = 0,
  loading = false,
  onOpenP1Issues,
  onOpenNotifications,
}: EraKpiStripProps) {
  if (loading) {
    return (
      <section className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
        <div className="border-b border-zinc-800/80 px-4 py-2">
          <div className="h-3 w-28 animate-pulse rounded bg-zinc-800" />
        </div>
        <div className="flex divide-x divide-zinc-800/80 overflow-x-auto">
          {Array.from({ length: 5 }).map((_, index) => (
            <SignalSkeleton key={index} />
          ))}
        </div>
      </section>
    );
  }

  const metrics = buildMetrics({
    summary,
    unmappedCount,
    onOpenP1Issues,
    onOpenNotifications,
  });

  return (
    <section className="overflow-hidden rounded-xl border border-zinc-800 bg-gradient-to-br from-zinc-900/50 via-zinc-900/35 to-zinc-950/40">
      <div className="flex items-center justify-between gap-3 border-b border-zinc-800/80 px-4 py-2">
        <div>
          <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
            Operational signals
          </p>
          <p className="text-[11px] text-zinc-600">
            Action items outside team continuity metrics
          </p>
        </div>
      </div>
      <div className="flex divide-x divide-zinc-800/80 overflow-x-auto">
        {metrics.map((metric) => (
          <SignalCell key={metric.id} metric={metric} />
        ))}
      </div>
    </section>
  );
}
