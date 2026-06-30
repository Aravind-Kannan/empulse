"use client";

import { useMemo, useState } from "react";
import { FileText, MessageSquare, Search } from "lucide-react";

import type { InvestigationReference, SmeRecommendation } from "@/lib/types";

const STATUS_DOT: Record<SmeRecommendation["status"], string> = {
  online: "bg-emerald-400",
  away: "bg-amber-400",
  offline: "bg-zinc-500",
};

const REF_ICON = {
  slack: MessageSquare,
  notion: FileText,
  postmortem: FileText,
};

export function InvestigationContextPanel({
  smes,
  references,
}: {
  smes: SmeRecommendation[];
  references: InvestigationReference[];
}) {
  const [query, setQuery] = useState("");

  const filteredReferences = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return references;
    return references.filter(
      (ref) =>
        ref.title.toLowerCase().includes(q) ||
        ref.snippet.toLowerCase().includes(q) ||
        ref.type.toLowerCase().includes(q),
    );
  }, [references, query]);

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-400">
        Context &amp; experts
      </h3>

      <div className="mb-4">
        <p className="mb-2 text-xs font-medium uppercase text-zinc-500">
          Recommended SMEs
        </p>
        <div className="space-y-2">
          {smes.length === 0 && (
            <p className="text-sm text-zinc-500">No SMEs ranked yet.</p>
          )}
          {smes.map((sme) => (
            <div
              key={sme.employee_id}
              className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`h-2 w-2 rounded-full ${STATUS_DOT[sme.status]}`}
                />
                <div>
                  <p className="text-sm text-zinc-100">{sme.name}</p>
                  <p className="text-xs text-zinc-500">{sme.role}</p>
                </div>
              </div>
              <span className="text-sm font-medium text-sky-300">
                {sme.compatibility_score}%
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        <p className="mb-2 text-xs font-medium uppercase text-zinc-500">
          References
        </p>
        <div className="relative mb-3">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search Slack, Notion, postmortems…"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 pl-9 pr-3 text-sm text-zinc-100 outline-none focus:border-zinc-500"
          />
        </div>
        <div className="space-y-2 overflow-y-auto pr-1">
          {filteredReferences.map((ref) => {
            const Icon = REF_ICON[ref.type];
            return (
              <div
                key={ref.id}
                className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3"
              >
                <div className="mb-1 flex items-center gap-2">
                  <Icon className="h-3.5 w-3.5 text-zinc-500" />
                  <p className="text-sm font-medium text-zinc-200">
                    {ref.title}
                  </p>
                </div>
                <p className="text-xs text-zinc-500">{ref.snippet}</p>
                <p className="mt-1 font-mono text-[10px] text-zinc-600">
                  {ref.url}
                </p>
              </div>
            );
          })}
          {filteredReferences.length === 0 && (
            <p className="text-sm text-zinc-500">No references match.</p>
          )}
        </div>
      </div>
    </div>
  );
}
