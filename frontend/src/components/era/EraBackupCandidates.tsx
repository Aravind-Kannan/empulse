"use client";

import type { EraBackupCandidate } from "@/lib/types";

interface EraBackupCandidatesProps {
  candidates: EraBackupCandidate[];
}

function groupByComponent(candidates: EraBackupCandidate[]) {
  const groups = new Map<string, EraBackupCandidate[]>();
  for (const candidate of candidates) {
    const key = candidate.component_id;
    const existing = groups.get(key) ?? [];
    existing.push(candidate);
    groups.set(key, existing);
  }
  return groups;
}

export function EraBackupCandidates({ candidates }: EraBackupCandidatesProps) {
  if (candidates.length === 0) {
    return (
      <section className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/20 p-5">
        <h3 className="text-sm font-medium text-zinc-200">Backup candidates</h3>
        <p className="mt-2 text-sm text-zinc-500">
          No backup candidates identified yet — schedule pairing or connect GitHub
          review data.
        </p>
      </section>
    );
  }

  const grouped = groupByComponent(candidates);

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
      <h3 className="text-sm font-medium text-zinc-200">Backup candidates</h3>
      <p className="mt-1 text-xs text-zinc-500">
        Ranked by DOA ownership, review participation, and recent commits.
      </p>
      <div className="mt-4 space-y-4">
        {[...grouped.entries()].map(([componentId, rows]) => (
          <div key={componentId}>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
              {rows[0]?.component_name ?? componentId}
            </p>
            <ol className="mt-2 space-y-2">
              {rows.map((candidate, index) => (
                <li
                  key={`${candidate.employee_id}-${candidate.component_id}`}
                  className="flex items-start justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm"
                >
                  <div>
                    <p className="font-medium text-zinc-100">
                      {index + 1}. {candidate.name}
                    </p>
                    <p className="mt-0.5 text-xs text-zinc-500">
                      {candidate.ownership_pct}% ownership · {candidate.review_count}{" "}
                      reviews · {candidate.recent_commits} recent commits
                    </p>
                  </div>
                  {candidate.label === "ramping" ? (
                    <span className="shrink-0 rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-300">
                      ramping
                    </span>
                  ) : null}
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>
    </section>
  );
}
