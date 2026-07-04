"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowUpRight,
  Clock,
  Loader2,
  Network,
  RefreshCw,
  Search,
  Sparkles,
  TrendingDown,
  Users,
} from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import {
  getConnectedIntegrationIds,
  INTEGRATION_CATALOG,
} from "@/lib/integrations";
import type { DashboardMetrics } from "@/lib/types";

import { AnimatedMetricValue } from "./AnimatedMetricValue";
import { SetupChecklist } from "./SetupChecklist";

const REVEAL_EASE = [0.16, 1, 0.3, 1] as const;

const CRON_OPTIONS = [
  { value: "0 9 * * 1", label: "Monday 9:00 AM" },
  { value: "0 8 * * 1", label: "Monday 8:00 AM" },
  { value: "0 17 * * 5", label: "Friday 5:00 PM" },
  { value: "0 6 1 * *", label: "1st of month 6:00 AM" },
];

const SHORTCUTS = [
  {
    href: "/era",
    label: "Employee Risk Assessment",
    description: "Continuity posture & attrition signals",
    icon: Users,
    accent: "from-violet-500/20 to-indigo-500/5",
    iconColor: "text-violet-400",
  },
  {
    href: "/kra",
    label: "Knowledge Risk Graph",
    description: "SPOF detection & doc coverage",
    icon: Network,
    accent: "from-fuchsia-500/20 to-pink-500/5",
    iconColor: "text-fuchsia-400",
  },
  {
    href: "/investigation",
    label: "Incident Investigation",
    description: "Open incidents & root-cause trails",
    icon: Search,
    accent: "from-amber-500/20 to-orange-500/5",
    iconColor: "text-amber-400",
  },
  {
    href: "/exit",
    label: "Knowledge Handover",
    description: "Exit workflows & transfer plans",
    icon: Users,
    accent: "from-sky-500/20 to-cyan-500/5",
    iconColor: "text-sky-400",
  },
] as const;

interface MetricCardProps {
  label: string;
  numericValue: number;
  decimals?: number;
  suffix?: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
  glow?: string;
  href?: string;
  alert?: boolean;
  hint?: string;
  delay?: number;
}

function MetricCard({
  label,
  numericValue,
  decimals = 0,
  suffix = "",
  icon: Icon,
  accent,
  glow,
  href,
  alert = false,
  hint,
  delay = 0,
}: MetricCardProps) {
  const reducedMotion = useReducedMotion();

  const card = (
    <motion.div
      initial={reducedMotion ? false : { opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.65, ease: REVEAL_EASE, delay }}
      whileHover={href ? { y: -3, transition: { duration: 0.2 } } : undefined}
      className={`group relative overflow-hidden rounded-2xl border p-5 backdrop-blur-sm transition-colors ${
        alert
          ? "border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-zinc-900/60 to-zinc-950/80"
          : "border-zinc-800/80 bg-gradient-to-br from-zinc-900/70 via-zinc-900/40 to-zinc-950/60"
      } ${href ? "hover:border-zinc-600/80" : ""}`}
    >
      {glow && !reducedMotion && (
        <motion.div
          className={`pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full blur-2xl ${glow}`}
          animate={{ opacity: [0.35, 0.65, 0.35], scale: [1, 1.15, 1] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        />
      )}

      {alert && !reducedMotion && (
        <span className="absolute right-4 top-4 flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-400" />
        </span>
      )}

      <div className="relative mb-4 flex items-start justify-between gap-3">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-500">
          {label}
        </p>
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800/80 bg-zinc-950/60 ${accent}`}
        >
          <Icon className="h-4 w-4" />
        </div>
      </div>

      <p className="relative text-3xl font-semibold tabular-nums tracking-tight text-zinc-50">
        <AnimatedMetricValue
          value={numericValue}
          decimals={decimals}
          suffix={suffix}
        />
      </p>

      {hint && (
        <p className="relative mt-2 text-xs text-zinc-500 group-hover:text-zinc-400">
          {hint}
        </p>
      )}

      {href && (
        <ArrowUpRight className="absolute bottom-4 right-4 h-4 w-4 text-zinc-600 opacity-0 transition group-hover:opacity-100 group-hover:text-zinc-400" />
      )}
    </motion.div>
  );

  if (href) {
    return <Link href={href}>{card}</Link>;
  }
  return card;
}

function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <div className="h-16 animate-pulse rounded-xl border border-zinc-800/60 bg-zinc-900/40" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="h-36 animate-pulse rounded-2xl border border-zinc-800/60 bg-zinc-900/40"
          />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="h-64 animate-pulse rounded-2xl border border-zinc-800/60 bg-zinc-900/40 lg:col-span-2" />
        <div className="h-64 animate-pulse rounded-2xl border border-zinc-800/60 bg-zinc-900/40" />
      </div>
    </div>
  );
}

export function DashboardView() {
  const { metrics, loading, digest, setDigest, refreshMetrics } = useWorkspace();
  const { config } = useIntegrations();
  const [refreshing, setRefreshing] = useState(false);
  const reducedMotion = useReducedMotion();

  const connectedCount = getConnectedIntegrationIds(config).length;
  const totalIntegrations = INTEGRATION_CATALOG.length;

  const resolvedMetrics: DashboardMetrics = useMemo(
    () => ({
      average_attrition_rate: metrics?.average_attrition_rate ?? 12,
      average_tenure_years: metrics?.average_tenure_years ?? 2.4,
      open_incident_count: metrics?.open_incident_count ?? 0,
      active_spof_count: metrics?.active_spof_count ?? 0,
      employee_count: metrics?.employee_count ?? 0,
    }),
    [metrics],
  );

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshMetrics();
    } finally {
      setRefreshing(false);
    }
  }, [refreshMetrics]);

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="relative space-y-8 pb-10">
      {!reducedMotion && (
        <>
          <div className="pointer-events-none absolute -left-24 top-0 h-72 w-72 rounded-full bg-violet-600/10 blur-3xl" />
          <div className="pointer-events-none absolute -right-16 top-32 h-64 w-64 rounded-full bg-fuchsia-600/8 blur-3xl" />
        </>
      )}

      <motion.header
        initial={reducedMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: REVEAL_EASE }}
        className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"
      >
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Live aggregates across all workspaces.
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
            <span className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-1.5">
              {resolvedMetrics.employee_count} team members
            </span>
            <span className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-1.5">
              {connectedCount}/{totalIntegrations} integrations
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => void handleRefresh()}
          disabled={refreshing}
          className="inline-flex shrink-0 items-center gap-2 self-start rounded-xl border border-zinc-700/80 bg-zinc-900/80 px-4 py-2 text-xs font-medium text-zinc-200 transition hover:border-zinc-600 hover:bg-zinc-800 disabled:opacity-60"
        >
          {refreshing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Refresh metrics
        </button>
      </motion.header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Average Attrition"
          numericValue={resolvedMetrics.average_attrition_rate}
          suffix="%"
          icon={TrendingDown}
          accent="text-rose-400"
          glow="bg-rose-500/30"
          hint="Rolling org-wide departure rate"
          delay={0.05}
        />
        <MetricCard
          label="Average Tenure"
          numericValue={resolvedMetrics.average_tenure_years}
          decimals={1}
          suffix=" yrs"
          icon={Clock}
          accent="text-sky-400"
          glow="bg-sky-500/30"
          hint="Mean years with the organization"
          delay={0.1}
        />
        <MetricCard
          label="Open Incidents"
          numericValue={resolvedMetrics.open_incident_count}
          icon={Search}
          accent="text-amber-400"
          glow="bg-amber-500/30"
          href="/investigation"
          alert={resolvedMetrics.open_incident_count > 0}
          hint="Active investigation workspace items"
          delay={0.15}
        />
        <MetricCard
          label="Active SPOFs"
          numericValue={resolvedMetrics.active_spof_count}
          icon={AlertTriangle}
          accent="text-orange-400"
          glow="bg-orange-500/30"
          href="/kra?filter=spof"
          alert={resolvedMetrics.active_spof_count > 0}
          hint="Single points of failure in KRA graph"
          delay={0.2}
        />
      </div>

      <SetupChecklist />

      <div className="grid gap-4 lg:grid-cols-3">
        <motion.section
          initial={reducedMotion ? false : { opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, ease: REVEAL_EASE, delay: 0.25 }}
          className="relative overflow-hidden rounded-2xl border border-zinc-800/80 bg-gradient-to-br from-zinc-900/60 to-zinc-950/80 p-6 lg:col-span-2"
        >
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-zinc-400">
                Workspace shortcuts
              </h2>
              <p className="mt-1 text-xs text-zinc-500">
                Jump into specialized risk surfaces
              </p>
            </div>
            <Sparkles className="h-4 w-4 text-violet-400/70" />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {SHORTCUTS.map(({ href, label, description, icon: Icon, accent, iconColor }, index) => (
              <motion.div
                key={href}
                initial={reducedMotion ? false : { opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{
                  duration: 0.5,
                  ease: REVEAL_EASE,
                  delay: 0.3 + index * 0.06,
                }}
              >
                <Link
                  href={href}
                  className={`group flex items-start gap-3 rounded-xl border border-zinc-800/80 bg-gradient-to-br ${accent} px-4 py-4 transition hover:border-zinc-600/80 hover:bg-zinc-900/50`}
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-zinc-800/80 bg-zinc-950/70">
                    <Icon className={`h-4 w-4 ${iconColor}`} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-zinc-100">{label}</p>
                    <p className="mt-0.5 text-xs text-zinc-500">{description}</p>
                  </div>
                  <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-zinc-600 transition group-hover:text-zinc-300" />
                </Link>
              </motion.div>
            ))}
          </div>
        </motion.section>

        <motion.section
          initial={reducedMotion ? false : { opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, ease: REVEAL_EASE, delay: 0.3 }}
          className="relative overflow-hidden rounded-2xl border border-zinc-800/80 bg-gradient-to-br from-zinc-900/60 via-zinc-950/80 to-black p-6"
        >
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_rgba(56,189,248,0.08),_transparent_60%)]" />

          <div className="relative">
            <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-zinc-400">
              Executive digest
            </h2>
            <p className="mt-1 text-xs text-zinc-500">
              Scheduled summary for leadership inboxes
            </p>

            <div className="mt-5 space-y-5">
              <label className="flex items-center justify-between gap-3 rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-4 py-3">
                <span className="text-sm text-zinc-200">Weekly digest</span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={digest.enabled}
                  onClick={() => setDigest({ enabled: !digest.enabled })}
                  className={`relative h-6 w-11 rounded-full transition-colors ${
                    digest.enabled ? "bg-emerald-600" : "bg-zinc-700"
                  }`}
                >
                  <motion.span
                    layout
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    className="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm"
                    style={{ left: digest.enabled ? "1.25rem" : "0.125rem" }}
                  />
                </button>
              </label>

              <div>
                <label className="mb-1.5 block text-[11px] uppercase tracking-wide text-zinc-500">
                  Schedule
                </label>
                <select
                  value={digest.cron}
                  onChange={(e) => setDigest({ cron: e.target.value })}
                  disabled={!digest.enabled}
                  className="w-full rounded-xl border border-zinc-700/80 bg-zinc-950/80 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-500 disabled:opacity-50"
                >
                  {CRON_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <p className="text-xs leading-relaxed text-zinc-600">
                Covers {resolvedMetrics.employee_count} employees across connected
                workspaces. Settings persist locally for this session.
              </p>
            </div>
          </div>
        </motion.section>
      </div>
    </div>
  );
}
