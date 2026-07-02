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

const SOURCE_STYLES = {
  jira: "text-sky-400",
  slack: "text-violet-400",
};

interface IncidentHistoryBarProps {
  incidents: IncidentSummary[];
  activeFilter: IncidentStatus | "All";
  activeIncidentId: string | null;
  sourcesConnected: Record<string, boolean>;
  warnings: string[];
  onFilterChange: (filter: IncidentStatus | "All") => void;
  onSelectIncident: (incident: IncidentSummary) => void;
}

export function IncidentHistoryBar({
  incidents,
  activeFilter,
  activeIncidentId,
  sourcesConnected,
  warnings,
  onFilterChange,
  onSelectIncident,
}: IncidentHistoryBarProps) {
  const jiraOn = Boolean(sourcesConnected.jira);
  const slackOn = Boolean(sourcesConnected.slack);

  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-medium text-zinc-300">Active incidents</h2>
          <p className="mt-0.5 text-xs text-zinc-500">
            {jiraOn || slackOn
              ? `From ${[jiraOn && "Jira", slackOn && "Slack"].filter(Boolean).join(" & ")} · last 14 days`
              : "Connect Jira and Slack in Settings → Integrations"}
          </p>
        </div>
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

      {warnings.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          {warnings[0]}
        </div>
      )}

      <div className="flex gap-3 overflow-x-auto pb-1">
        {incidents.map((incident) => (
          <button
            key={incident.id}
            type="button"
            onClick={() => onSelectIncident(incident)}
            className={`min-w-[260px] shrink-0 rounded-xl border p-4 text-left transition ${
              activeIncidentId === incident.id
                ? "border-zinc-500 bg-zinc-800/80"
                : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-700"
            }`}
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${STATUS_STYLES[incident.status]}`}
                >
                  {incident.status}
                </span>
                <span
                  className={`text-[10px] font-medium uppercase ${SOURCE_STYLES[incident.source]}`}
                >
                  {incident.source}
                </span>
              </div>
              {incident.jira_id ? (
                <span className="font-mono text-[10px] text-zinc-500">
                  {incident.jira_id}
                </span>
              ) : null}
            </div>
            <p className="line-clamp-2 text-sm font-medium text-zinc-100">
              {incident.title}
            </p>
            <p className="mt-1 text-xs text-zinc-500">
              {incident.source === "slack"
                ? `#${incident.system_scope}`
                : incident.system_scope}
              {incident.priority ? ` · ${incident.priority}` : ""}
            </p>
          </button>
        ))}
        {incidents.length === 0 && (
          <div className="rounded-xl border border-dashed border-zinc-800 px-6 py-8 text-sm text-zinc-500">
            {!jiraOn && !slackOn
              ? "Connect Jira and Slack to see live incidents here."
              : "No open bugs or incidents in the last 14 days. Check Jira issue types or Slack incident channels."}
          </div>
        )}
      </div>
    </section>
  );
}
