"use client";

import type { CriticalSpofResult } from "@/lib/types";

interface KraKpiStripProps {
  criticalSpof: CriticalSpofResult | null;
  loading?: boolean;
  filterActive?: boolean;
  onToggleFilter?: () => void;
}

function SkeletonCard() {
  return (
    <div className="min-w-[12rem] flex-1 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="h-3 w-24 rounded bg-zinc-800" />
      <div className="mt-3 h-7 w-10 rounded bg-zinc-800" />
      <div className="mt-2 h-3 w-32 rounded bg-zinc-800" />
    </div>
  );
}

export function KraKpiStrip({
  criticalSpof,
  loading = false,
  filterActive = false,
  onToggleFilter,
}: KraKpiStripProps) {
  if (loading) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-1">
        <SkeletonCard />
      </div>
    );
  }

  if (!criticalSpof) return null;

  const count = criticalSpof.count;
  const isAlert = count > 0;
  const partial = criticalSpof.data_completeness.is_partial;

  return (
    <div className="flex gap-3 overflow-x-auto pb-1">
      <button
        type="button"
        onClick={onToggleFilter}
        title="Tier-1 revenue systems with bus factor ≤1 or ≤1 owner"
        className={`min-w-[12rem] flex-1 rounded-xl border p-4 text-left transition hover:bg-zinc-900/60 ${
          filterActive
            ? "border-red-500/50 bg-red-500/10"
            : isAlert
              ? "border-red-500/30 bg-red-500/5 hover:border-red-500/40"
              : "border-emerald-500/30 bg-emerald-500/5 hover:border-emerald-500/40"
        }`}
      >
        <div className="flex items-center gap-2">
          <p className="text-xs uppercase tracking-wide text-zinc-500">
            Critical SPOFs
          </p>
          {partial && (
            <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-300">
              partial
            </span>
          )}
        </div>
        <p
          className={`mt-1 text-2xl font-semibold ${
            isAlert ? "text-red-300" : "text-emerald-300"
          }`}
        >
          {count}
        </p>
        <p className="mt-1 text-xs text-zinc-500">
          {count === 0
            ? "No revenue-critical systems without backup"
            : `${count} revenue-critical system${count === 1 ? "" : "s"} have no backup`}
          {" · "}
          <span className={filterActive ? "text-red-300" : "text-zinc-400"}>
            {filterActive ? "Showing on graph" : "View components"}
          </span>
        </p>
      </button>
    </div>
  );
}
