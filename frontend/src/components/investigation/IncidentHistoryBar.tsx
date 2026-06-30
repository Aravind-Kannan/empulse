"use client";

import type { IncidentStatus, IncidentSummary } from "@/lib/types";

const STATUSES: Array<IncidentStatus | "All"> = [
  "All",
  "Open",
  "Investigating",
  "Waiting for Input",
  "Resolved",
  "Closed",
];

const STATUS_STYLES: Record<IncidentStatus, string> = {
  Open: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  Investigating: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  "Waiting for Input": "border-violet-500/40 bg-violet-500/10 text-violet-300",
  Resolved: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  Closed: "border-zinc-600 bg-zinc-800/50 text-zinc-400",
};

interface IncidentHistoryBarProps {
  incidents: IncidentSummary[];
  activeFilter: IncidentStatus | "All";
  activeIncidentId: string | null;
  onFilterChange: (filter: IncidentStatus | "All") => void;
  onSelectIncident: (incident: IncidentSummary) => void;
}

export function IncidentHistoryBar({
  incidents,
  activeFilter,
  activeIncidentId,
  onFilterChange,
  onSelectIncident,
}: IncidentHistoryBarProps) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-300">Incident history</h2>
        <div className="flex flex-wrap gap-1">
          {STATUSES.map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => onFilterChange(status)}
              className={`rounded-md px-2.5 py-1 text-xs transition ${
                activeFilter === status
                  ? "bg-zinc-100 text-slate-950"
                  : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-1">
        {incidents.map((incident) => (
          <button
            key={incident.id}
            type="button"
            onClick={() => onSelectIncident(incident)}
            className={`min-w-[240px] shrink-0 rounded-xl border p-4 text-left transition ${
              activeIncidentId === incident.id
                ? "border-zinc-500 bg-zinc-800/80"
                : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-700"
            }`}
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <span
                className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${STATUS_STYLES[incident.status]}`}
              >
                {incident.status}
              </span>
              <span className="font-mono text-[10px] text-zinc-500">
                {incident.jira_id}
              </span>
            </div>
            <p className="text-sm font-medium text-zinc-100">{incident.title}</p>
            <p className="mt-1 text-xs text-zinc-500">{incident.system_scope}</p>
          </button>
        ))}
        {incidents.length === 0 && (
          <p className="text-sm text-zinc-500">No incidents for this filter.</p>
        )}
      </div>
    </section>
  );
}
