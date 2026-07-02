"use client";

import { useEffect, useState } from "react";
import { GitPullRequest, Loader2, Users } from "lucide-react";

import { fetchEraReviewNetwork } from "@/lib/api";
import type { EraReviewNetworkResponse } from "@/lib/types";

interface EraReviewNetworkProps {
  employeeId: string;
  employeeName: string;
}

export function EraReviewNetwork({
  employeeId,
  employeeName,
}: EraReviewNetworkProps) {
  const [data, setData] = useState<EraReviewNetworkResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchEraReviewNetwork(employeeId)
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load review network",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [employeeId]);

  if (loading) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading review network…
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
        <p className="text-sm text-red-300">{error}</p>
      </section>
    );
  }

  const metrics = data?.metrics;
  const reviewers = data?.incoming_reviewers ?? [];

  if (!metrics && reviewers.length === 0) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
        <h3 className="text-sm font-medium text-zinc-200">Review network</h3>
        <p className="mt-2 text-sm text-zinc-500">
          No GitHub review data in the last {data?.window_days ?? 90} days.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-zinc-200">Review network</h3>
        <span className="text-xs text-zinc-500">{data?.window_days ?? 90}d window</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        Who reviews {employeeName}&apos;s PRs — system health, not performance ranking.
      </p>

      {metrics && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <MetricChip
            label="Concentration"
            value={`${metrics.review_concentration_pct.toFixed(0)}%`}
            hint="top reviewer share"
          />
          <MetricChip
            label="Backup score"
            value={`${metrics.backup_review_score.toFixed(0)}`}
            hint="review diversity"
          />
          <MetricChip
            label="Sole reviewer"
            value={String(metrics.sole_reviewer_count)}
            hint="PRs at risk"
          />
          <MetricChip
            label="Reviews given"
            value={String(metrics.reviews_given_count)}
            hint="backup signal"
          />
        </div>
      )}

      {reviewers.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-zinc-500">
            <Users className="h-3.5 w-3.5" />
            Incoming reviewers
          </p>
          <ul className="space-y-2">
            {reviewers.slice(0, 5).map((edge) => (
              <li
                key={`${edge.reviewer_employee_id}-${edge.author_employee_id}`}
                className="flex items-center justify-between rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-3 py-2 text-sm"
              >
                <span className="text-zinc-200">
                  {edge.reviewer_login || edge.reviewer_employee_id}
                </span>
                <span className="flex items-center gap-1 text-xs text-zinc-500">
                  <GitPullRequest className="h-3.5 w-3.5" />
                  {edge.review_count} reviews
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function MetricChip({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="text-lg font-semibold text-zinc-100">{value}</p>
      <p className="text-[10px] text-zinc-600">{hint}</p>
    </div>
  );
}
