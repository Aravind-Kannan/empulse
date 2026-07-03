"use client";

import Link from "next/link";
import {
  AlertTriangle,
  Clock,
  Loader2,
  Network,
  Search,
  TrendingDown,
  Users,
} from "lucide-react";

import { useWorkspace } from "@/context/WorkspaceContext";

import { SetupChecklist } from "./SetupChecklist";

const CRON_OPTIONS = [
  { value: "0 9 * * 1", label: "Monday 9:00 AM" },
  { value: "0 8 * * 1", label: "Monday 8:00 AM" },
  { value: "0 17 * * 5", label: "Friday 5:00 PM" },
  { value: "0 6 1 * *", label: "1st of month 6:00 AM" },
];

function MetricCard({
  label,
  value,
  icon: Icon,
  accent,
  href,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
  href?: string;
}) {
  const content = (
    <div
      className={`rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 transition ${
        href ? "hover:border-zinc-600 hover:bg-zinc-900/60" : ""
      }`}
    >
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          {label}
        </p>
        <Icon className={`h-4 w-4 ${accent}`} />
      </div>
      <p className="text-2xl font-semibold text-zinc-100">{value}</p>
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}

export function DashboardView() {
  const { metrics, loading, digest, setDigest, refreshMetrics } = useWorkspace();

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading cockpit metrics…
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Dashboard</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Manager cockpit — live aggregates across all workspaces.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refreshMetrics()}
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-900"
        >
          Refresh
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Average Attrition Rate"
          value={`${metrics?.average_attrition_rate ?? 12}%`}
          icon={TrendingDown}
          accent="text-rose-400"
        />
        <MetricCard
          label="Average Tenure"
          value={`${metrics?.average_tenure_years ?? 2.4} yrs`}
          icon={Clock}
          accent="text-sky-400"
        />
        <MetricCard
          label="Open Incidents"
          value={String(metrics?.open_incident_count ?? 0)}
          icon={Search}
          accent="text-amber-400"
          href="/investigation"
        />
        <MetricCard
          label="Active SPOFs"
          value={String(metrics?.active_spof_count ?? 0)}
          icon={AlertTriangle}
          accent="text-orange-400"
          href="/kra"
        />
      </div>

      <SetupChecklist />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5 lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Workspace shortcuts
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              { href: "/era", label: "Employee Risk Assessment", icon: Users },
              { href: "/kra", label: "Knowledge Risk Graph", icon: Network },
              { href: "/investigation", label: "Incident Investigation", icon: Search },
              { href: "/exit", label: "Employee Knowledge Handover", icon: Users },
            ].map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-950/50 px-4 py-3 text-sm text-zinc-300 transition hover:border-zinc-600 hover:text-zinc-100"
              >
                <Icon className="h-4 w-4 text-zinc-500" />
                {label}
              </Link>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Executive email digest
          </h2>
          <div className="space-y-4">
            <label className="flex items-center justify-between gap-3">
              <span className="text-sm text-zinc-300">
                Weekly executive digest
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={digest.enabled}
                onClick={() => setDigest({ enabled: !digest.enabled })}
                className={`relative h-6 w-11 rounded-full transition ${
                  digest.enabled ? "bg-emerald-600" : "bg-zinc-700"
                }`}
              >
                <span
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition ${
                    digest.enabled ? "left-5" : "left-0.5"
                  }`}
                />
              </button>
            </label>
            <div>
              <label className="mb-1 block text-xs text-zinc-500">
                Cron schedule
              </label>
              <select
                value={digest.cron}
                onChange={(e) => setDigest({ cron: e.target.value })}
                disabled={!digest.enabled}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500 disabled:opacity-50"
              >
                {CRON_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <p className="text-xs text-zinc-600">
              Team size: {metrics?.employee_count ?? "—"} · Settings persist
              locally for this session.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
