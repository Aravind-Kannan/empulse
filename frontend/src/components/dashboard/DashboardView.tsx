"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowUpRight,
  Clock,
  Loader2,
  Plug,
  RefreshCw,
  Search,
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
import { DashboardCharts } from "./DashboardCharts";
import { SetupChecklist } from "./SetupChecklist";

const REVEAL_EASE = [0.16, 1, 0.3, 1] as const;

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
          : "border-zinc-700/80 bg-gradient-to-br from-zinc-900/70 via-zinc-900/40 to-zinc-950/60"
      } ${href ? "hover:border-zinc-500/80" : ""}`}
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
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-300">
          {label}
        </p>
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-700/80 bg-zinc-950/60 ${accent}`}
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
        <p className="relative mt-2 text-xs text-zinc-400 group-hover:text-zinc-300">
          {hint}
        </p>
      )}

      {href && (
        <ArrowUpRight className="absolute bottom-4 right-4 h-4 w-4 text-zinc-500 opacity-0 transition group-hover:opacity-100 group-hover:text-zinc-300" />
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
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <div
            key={index}
            className="h-36 animate-pulse rounded-2xl border border-zinc-800/60 bg-zinc-900/40"
          />
        ))}
      </div>
    </div>
  );
}

export function DashboardView() {
  const { metrics, loading, refreshMetrics } = useWorkspace();
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
            Key signals across your workspace — each metric shown once.
          </p>
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
          Refresh
        </button>
      </motion.header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard
          label="Team Members"
          numericValue={resolvedMetrics.employee_count}
          icon={Users}
          accent="text-violet-400"
          glow="bg-violet-500/30"
          hint="People on your org chart"
          delay={0.05}
        />
        <MetricCard
          label="Integrations Live"
          numericValue={connectedCount}
          suffix={` / ${totalIntegrations}`}
          icon={Plug}
          accent="text-emerald-400"
          glow="bg-emerald-500/30"
          href="/settings/integrations"
          hint="Connected data sources"
          delay={0.08}
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
          delay={0.11}
        />
        <MetricCard
          label="Average Attrition"
          numericValue={resolvedMetrics.average_attrition_rate}
          suffix="%"
          icon={TrendingDown}
          accent="text-rose-400"
          glow="bg-rose-500/30"
          hint="Rolling org-wide departure rate"
          delay={0.14}
        />
        <MetricCard
          label="Open Incidents"
          numericValue={resolvedMetrics.open_incident_count}
          icon={Search}
          accent="text-amber-400"
          glow="bg-amber-500/30"
          href="/investigation"
          alert={resolvedMetrics.open_incident_count > 0}
          hint="Active investigation items"
          delay={0.17}
        />
        <MetricCard
          label="Active SPOFs"
          numericValue={resolvedMetrics.active_spof_count}
          icon={AlertTriangle}
          accent="text-orange-400"
          glow="bg-orange-500/30"
          href="/kra?filter=spof"
          alert={resolvedMetrics.active_spof_count > 0}
          hint="Single points of failure in KRA"
          delay={0.2}
        />
      </div>

      <DashboardCharts />

      <SetupChecklist />
    </div>
  );
}
