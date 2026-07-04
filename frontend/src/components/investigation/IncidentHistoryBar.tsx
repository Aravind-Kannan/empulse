"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CloudLightning,
  Database,
  Loader2,
} from "lucide-react";
import type { IncidentStatus, IncidentSummary } from "@/lib/types";

import type { IncidentSyncStatus } from "./investigation-prefetch";

const STATUSES: Array<IncidentStatus | "All"> = [
  "All",
  "Open",
  "Investigating",
  "Waiting for Input",
  "Resolved",
  "Closed",
];

const STATUS_STYLES: Record<IncidentStatus, string> = {
  Open: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  Investigating: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  "Waiting for Input": "border-purple-500/30 bg-purple-500/10 text-purple-300",
  Resolved: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  Closed: "border-zinc-700 bg-zinc-800/40 text-zinc-400",
};

const SOURCE_STYLES = {
  jira: "text-sky-400 bg-sky-500/5 border-sky-500/10",
  slack: "text-purple-400 bg-purple-500/5 border-purple-500/10",
};

function SyncStatusBadge({ status }: { status?: IncidentSyncStatus }) {
  if (status === "loading") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full border border-sky-500/20 bg-sky-500/10 px-1.5 py-0.5 text-[9px] font-medium text-sky-300"
        title="Analysis syncing"
      >
        <Loader2 className="h-2.5 w-2.5 animate-spin" />
        Syncing
      </span>
    );
  }
  if (status === "ready") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-medium text-emerald-300"
        title="Analysis ready"
      >
        <CheckCircle2 className="h-2.5 w-2.5" />
        Ready
      </span>
    );
  }
  if (status === "error") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full border border-red-500/20 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-medium text-red-300"
        title="Analysis sync failed"
      >
        Retry on select
      </span>
    );
  }
  return null;
}

interface IncidentHistoryBarProps {
  incidents: IncidentSummary[];
  activeFilter: IncidentStatus | "All";
  activeIncidentId: string | null;
  syncStatus: Record<string, IncidentSyncStatus>;
  syncingCount: number;
  sourcesConnected: Record<string, boolean>;
  warnings: string[];
  onFilterChange: (filter: IncidentStatus | "All") => void;
  onSelectIncident: (incident: IncidentSummary) => void;
  onIncidentVisible?: (incidentId: string) => void;
}

export function IncidentHistoryBar({
  incidents,
  activeFilter,
  activeIncidentId,
  syncStatus,
  syncingCount,
  sourcesConnected,
  warnings,
  onFilterChange,
  onSelectIncident,
  onIncidentVisible,
}: IncidentHistoryBarProps) {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const visibleReportedRef = useRef<Set<string>>(new Set());
  const [hasOverflow, setHasOverflow] = useState(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const jiraOn = Boolean(sourcesConnected.jira);
  const slackOn = Boolean(sourcesConnected.slack);

  const updateScrollState = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    const overflow = el.scrollWidth > el.clientWidth + 2;
    setHasOverflow(overflow);
    setCanScrollLeft(overflow && el.scrollLeft > 2);
    setCanScrollRight(
      overflow && el.scrollLeft + el.clientWidth < el.scrollWidth - 2,
    );
  }, []);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    updateScrollState();

    const onScroll = () => updateScrollState();
    el.addEventListener("scroll", onScroll, { passive: true });

    const resizeObserver = new ResizeObserver(() => updateScrollState());
    resizeObserver.observe(el);

    return () => {
      el.removeEventListener("scroll", onScroll);
      resizeObserver.disconnect();
    };
  }, [incidents, activeFilter, updateScrollState]);

  useEffect(() => {
    visibleReportedRef.current.clear();
  }, [activeFilter, incidents]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container || !onIncidentVisible) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const incidentId = entry.target.getAttribute("data-incident-id");
          if (!incidentId || visibleReportedRef.current.has(incidentId)) return;
          visibleReportedRef.current.add(incidentId);
          onIncidentVisible(incidentId);
        });
      },
      {
        root: container,
        rootMargin: "0px 48px 0px 48px",
        threshold: 0.35,
      },
    );

    const cards = container.querySelectorAll("[data-incident-id]");
    cards.forEach((card) => observer.observe(card));

    return () => observer.disconnect();
  }, [incidents, onIncidentVisible]);

  const scroll = (direction: "left" | "right") => {
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollBy({
      left: direction === "left" ? -340 : 340,
      behavior: "smooth",
    });
  };

  return (
    <section className="space-y-4 overflow-x-hidden bg-zinc-950/10 border border-zinc-800/60 rounded-xl p-4 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <CloudLightning className="h-4.5 w-4.5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-200">Active Incidents</h2>
            <p className="text-[11px] text-zinc-500">
              {jiraOn || slackOn
                ? `Monitoring ${[jiraOn && "Jira", slackOn && "Slack"].filter(Boolean).join(" & ")} · past 14 days`
                : "Connect Jira and Slack in Integrations"}
            </p>
            {syncingCount > 0 && (
              <p className="mt-0.5 text-[10px] text-sky-400/90">
                Syncing analysis for {syncingCount} incident
                {syncingCount === 1 ? "" : "s"} in background…
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-1 bg-zinc-900/40 border border-zinc-800/50 p-1 rounded-lg">
          {STATUSES.map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => onFilterChange(status)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all duration-150 ${
                activeFilter === status
                  ? "bg-zinc-100 text-slate-950 shadow-sm"
                  : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3.5 py-2.5 text-xs text-amber-200">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
          <span>{warnings[0]}</span>
        </div>
      )}

      <div className="relative group overflow-hidden">
        {hasOverflow && canScrollLeft && (
          <button
            type="button"
            onClick={() => scroll("left")}
            aria-label="Scroll incidents left"
            className="absolute -left-2 top-1/2 z-10 hidden h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-zinc-800 bg-zinc-950/90 text-zinc-400 shadow-lg backdrop-blur-sm transition duration-200 hover:border-zinc-700 hover:text-zinc-200 active:scale-95 md:flex opacity-0 group-hover:opacity-100"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}

        <div
          ref={scrollContainerRef}
          className={`incident-cards-scroll flex gap-3 scroll-smooth ${
            hasOverflow ? "overflow-x-auto" : "overflow-x-hidden"
          }`}
        >
          {incidents.map((incident) => {
            const isActive = activeIncidentId === incident.id;
            const cardSync = syncStatus[incident.id] ?? "idle";
            return (
              <button
                key={incident.id}
                type="button"
                data-incident-id={incident.id}
                onClick={() => onSelectIncident(incident)}
                aria-label={
                  cardSync === "ready"
                    ? `${incident.title}, analysis ready`
                    : incident.title
                }
                className={`w-[280px] shrink-0 rounded-xl border p-4 text-left transition-all duration-200 shadow-sm relative ${
                  isActive
                    ? "border-sky-500/50 bg-sky-500/5 ring-1 ring-sky-500/20"
                    : "border-zinc-800/80 bg-zinc-900/10 hover:border-zinc-700 hover:bg-zinc-900/20"
                }`}
              >
                <div className="mb-2.5 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-bold tracking-wide shrink-0 ${STATUS_STYLES[incident.status]}`}
                    >
                      {incident.status}
                    </span>
                    <span
                      className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border shrink-0 ${SOURCE_STYLES[incident.source]}`}
                    >
                      {incident.source}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <SyncStatusBadge status={cardSync} />
                    {incident.jira_id && (
                      <span className="font-mono text-[9px] font-bold text-zinc-500">
                        {incident.jira_id}
                      </span>
                    )}
                  </div>
                </div>

                <p
                  className={`line-clamp-2 text-xs font-semibold leading-relaxed transition ${isActive ? "text-sky-100" : "text-zinc-200"}`}
                >
                  {incident.title}
                </p>

                <div className="mt-2.5 flex items-center gap-1.5 text-[10px] text-zinc-500 font-medium">
                  <span className="truncate max-w-[140px] font-mono bg-zinc-950/40 px-1.5 py-0.5 rounded border border-zinc-900/60">
                    {incident.source === "slack"
                      ? `#${incident.system_scope}`
                      : incident.system_scope}
                  </span>
                  {incident.priority && (
                    <>
                      <span>·</span>
                      <span className="text-amber-500/80 font-semibold">
                        {incident.priority}
                      </span>
                    </>
                  )}
                </div>
              </button>
            );
          })}

          {incidents.length === 0 && (
            <div className="w-full rounded-xl border border-dashed border-zinc-800/80 bg-zinc-950/20 py-8 px-4 text-center">
              <Database className="h-6 w-6 text-zinc-600 mx-auto mb-2" />
              <p className="text-xs text-zinc-500 max-w-[320px] mx-auto">
                {!jiraOn && !slackOn
                  ? "Connect Jira and Slack to see live incidents here."
                  : "No active incidents found matching this status filter."}
              </p>
            </div>
          )}
        </div>

        {hasOverflow && canScrollRight && (
          <button
            type="button"
            onClick={() => scroll("right")}
            aria-label="Scroll incidents right"
            className="absolute -right-2 top-1/2 z-10 hidden h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-zinc-800 bg-zinc-950/90 text-zinc-400 shadow-lg backdrop-blur-sm transition duration-200 hover:border-zinc-700 hover:text-zinc-200 active:scale-95 md:flex opacity-0 group-hover:opacity-100"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        )}
      </div>
    </section>
  );
}
