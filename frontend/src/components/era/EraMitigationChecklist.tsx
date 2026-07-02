"use client";

import { useState } from "react";
import { CheckCircle2, ExternalLink, Loader2 } from "lucide-react";

import { patchEraEvidenceMitigation } from "@/lib/api";
import type { EraMitigationItem } from "@/lib/types";

interface EraMitigationChecklistProps {
  employeeId: string;
  items: EraMitigationItem[];
  onUpdated?: () => void;
}

function priorityClass(priority: string) {
  if (priority === "critical") {
    return "border-red-500/30 bg-red-500/10 text-red-300";
  }
  if (priority === "high") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  }
  return "border-zinc-700 bg-zinc-900/40 text-zinc-400";
}

export function EraMitigationChecklist({
  employeeId,
  items,
  onUpdated,
}: EraMitigationChecklistProps) {
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const visible = items.filter((item) => item.mitigation_status !== "dismissed");

  if (visible.length === 0) {
    return (
      <section className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/20 p-5">
        <h3 className="text-sm font-medium text-zinc-200">Recommended actions</h3>
        <p className="mt-2 text-sm text-zinc-500">
          No open mitigations — evidence signals are within normal thresholds.
        </p>
      </section>
    );
  }

  async function updateStatus(
    evidenceId: string,
    mitigation_status: EraMitigationItem["mitigation_status"],
  ) {
    setPendingId(evidenceId);
    setError(null);
    try {
      await patchEraEvidenceMitigation(evidenceId, {
        employee_id: employeeId,
        mitigation_status,
      });
      onUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update mitigation.");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
      <h3 className="text-sm font-medium text-zinc-200">Recommended actions</h3>
      <p className="mt-1 text-xs text-zinc-500">
        Track remediation from ERA evidence and rule engine suggestions.
      </p>
      {error ? <p className="mt-2 text-xs text-red-300">{error}</p> : null}
      <ul className="mt-4 space-y-3">
        {visible.map((item) => {
          const done = item.mitigation_status === "done";
          const inProgress = item.mitigation_status === "in_progress";
          return (
            <li
              key={item.evidence_id}
              className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    {done ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                    ) : (
                      <span className="inline-block h-4 w-4 shrink-0 rounded border border-zinc-600" />
                    )}
                    <p
                      className={`text-sm ${done ? "text-zinc-500 line-through" : "text-zinc-100"}`}
                    >
                      {item.title}
                    </p>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${priorityClass(item.priority)}`}
                    >
                      {item.priority}
                    </span>
                    {inProgress ? (
                      <span className="text-[10px] uppercase text-sky-300">in progress</span>
                    ) : null}
                    {item.link ? (
                      <a
                        href={item.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] text-violet-300 hover:text-violet-200"
                      >
                        Open <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : null}
                  </div>
                </div>
                {!done ? (
                  <div className="flex shrink-0 gap-2">
                    {!inProgress ? (
                      <button
                        type="button"
                        disabled={pendingId === item.evidence_id}
                        onClick={() => void updateStatus(item.evidence_id, "in_progress")}
                        className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
                      >
                        Assign
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={pendingId === item.evidence_id}
                      onClick={() => void updateStatus(item.evidence_id, "done")}
                      className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-50"
                    >
                      {pendingId === item.evidence_id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        "Done"
                      )}
                    </button>
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
