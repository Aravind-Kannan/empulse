"use client";

import { useMemo, useState } from "react";
import {
  Check,
  Copy,
  ExternalLink,
  FileText,
  MessageSquare,
  Search,
  Ticket,
  Users,
} from "lucide-react";

import type {
  InvestigationAssignmentRecord,
  InvestigationBaseMetadata,
  InvestigationReference,
  SmeRecommendation,
} from "@/lib/types";

const STATUS_DOT: Record<SmeRecommendation["status"], string> = {
  online: "bg-emerald-500 ring-emerald-500/20",
  away: "bg-amber-500 ring-amber-500/20",
  offline: "bg-zinc-500 ring-zinc-500/20",
};

function isOpenableReferenceUrl(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

type ReferenceSection = {
  key: string;
  label: string;
  icon: typeof MessageSquare;
  colorClass: string;
  bgClass: string;
  borderClass: string;
  items: InvestigationReference[];
};

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function getAvatarColor(name: string): string {
  const colors = [
    "bg-red-500/10 text-red-400 border-red-500/20",
    "bg-orange-500/10 text-orange-400 border-orange-500/20",
    "bg-amber-500/10 text-amber-400 border-amber-500/20",
    "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    "bg-teal-500/10 text-teal-400 border-teal-500/20",
    "bg-sky-500/10 text-sky-400 border-sky-500/20",
    "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
    "bg-purple-500/10 text-purple-400 border-purple-500/20",
    "bg-pink-500/10 text-pink-400 border-pink-500/20",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function InvestigationContextPanel({
  smes,
  slackThreads,
  jiraTickets,
  notionPages,
  baseMetadata,
  analyzing,
  graphAnalyzing = false,
  analysisMessage,
}: {
  smes: SmeRecommendation[];
  slackThreads: InvestigationReference[];
  jiraTickets: InvestigationReference[];
  notionPages: InvestigationReference[];
  baseMetadata?: InvestigationBaseMetadata | null;
  analyzing: boolean;
  graphAnalyzing?: boolean;
  analysisMessage: string | null;
}) {
  const [query, setQuery] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (e: React.MouseEvent, id: string, url: string) => {
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.writeText(url);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const sections: ReferenceSection[] = useMemo(
    () => [
      {
        key: "slack",
        label: "Slack Threads",
        icon: MessageSquare,
        colorClass: "text-purple-400",
        bgClass: "bg-purple-500/5",
        borderClass: "border-purple-500/10 hover:border-purple-500/30",
        items: slackThreads,
      },
      {
        key: "jira",
        label: "Related Jira Tickets",
        icon: Ticket,
        colorClass: "text-sky-400",
        bgClass: "bg-sky-500/5",
        borderClass: "border-sky-500/10 hover:border-sky-500/30",
        items: jiraTickets,
      },
      {
        key: "notion",
        label: "Notion & Postmortems",
        icon: FileText,
        colorClass: "text-emerald-400",
        bgClass: "bg-emerald-500/5",
        borderClass: "border-emerald-500/10 hover:border-emerald-500/30",
        items: notionPages,
      },
    ],
    [slackThreads, jiraTickets, notionPages],
  );

  const filteredSections = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sections;
    return sections
      .map((section) => ({
        ...section,
        items: section.items.filter(
          (ref) =>
            ref.title.toLowerCase().includes(q) ||
            ref.snippet.toLowerCase().includes(q) ||
            ref.type.toLowerCase().includes(q),
        ),
      }))
      .filter((section) => section.items.length > 0);
  }, [sections, query]);

  const hasReferences = sections.some((section) => section.items.length > 0);
  const visibleSmes = smes.length > 0 ? smes : (baseMetadata?.scope_owners ?? []);
  const assignments = baseMetadata?.assignments ?? [];
  const showSmeSkeleton = graphAnalyzing && visibleSmes.length === 0;
  const showReferenceSkeleton = graphAnalyzing && !hasReferences;

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-800 bg-zinc-950/20 backdrop-blur-sm shadow-xl">
      {/* Header */}
      <div className="flex items-center gap-2.5 border-b border-zinc-800/80 px-4 py-3.5 bg-zinc-900/10">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
          <Users className="h-4 w-4" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">
            Context &amp; Experts
          </h3>
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">
            SMEs &amp; Historical Context
          </p>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 scrollbar-thin scrollbar-thumb-zinc-800">
        {baseMetadata?.incident && (
          <div className="rounded-xl border border-zinc-800/70 bg-zinc-900/20 px-3 py-2.5">
            <p className="text-xs font-medium text-zinc-200 truncate">
              {baseMetadata.incident.title}
            </p>
            <p className="mt-0.5 text-[10px] text-zinc-500">
              Scope: {baseMetadata.incident.system_scope}
              {baseMetadata.incident.jira_id
                ? ` · ${baseMetadata.incident.jira_id}`
                : ""}
              {" · "}
              {baseMetadata.incident.status}
            </p>
          </div>
        )}

        {assignments.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              Component assignments
            </p>
            <div className="space-y-1.5">
              {assignments.slice(0, 6).map((row: InvestigationAssignmentRecord) => (
                <div
                  key={`${row.employee_id}-${row.component_id}`}
                  className="flex items-center justify-between rounded-lg border border-zinc-800/60 bg-zinc-950/40 px-2.5 py-2 text-[11px]"
                >
                  <span className="truncate text-zinc-300">
                    {row.employee_name}
                  </span>
                  <span className="shrink-0 text-zinc-500">
                    {row.component_name} · {Math.round(row.codebase_share_pct)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recommended SMEs */}
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            Recommended SMEs
          </p>
          <div className="space-y-2">
            {showSmeSkeleton ? (
              <>
                <p className="text-xs text-sky-400 animate-pulse">
                  {analysisMessage ?? "Finding experts…"}
                </p>
                {[1, 2].map((item) => (
                  <div
                    key={item}
                    className="flex items-center justify-between rounded-xl border border-zinc-900 bg-zinc-950/40 px-3 py-2.5"
                  >
                    <div className="flex items-center gap-2.5">
                      <div className="h-8 w-8 animate-pulse rounded-full bg-zinc-800/60" />
                      <div className="space-y-1.5">
                        <div className="h-3 w-24 animate-pulse rounded bg-zinc-800/60" />
                        <div className="h-2 w-16 animate-pulse rounded bg-zinc-800/60" />
                      </div>
                    </div>
                    <div className="h-3.5 w-8 animate-pulse rounded bg-zinc-800/60" />
                  </div>
                ))}
              </>
            ) : visibleSmes.length === 0 ? (
              <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-3.5 text-center">
                <p className="text-xs text-zinc-500">
                  No subject matter experts identified in system memory for this component. Ensure team assignments and identity mappings are configured.
                </p>
              </div>
            ) : (
              visibleSmes.map((sme) => {
                const avatarColor = getAvatarColor(sme.name);
                return (
                  <div
                    key={sme.employee_id}
                    className="flex items-center justify-between rounded-xl border border-zinc-800/60 bg-zinc-900/10 px-3.5 py-2.5 transition hover:border-zinc-700 hover:bg-zinc-900/20"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {/* Avatar with Status Dot */}
                      <div className="relative shrink-0">
                        <div
                          className={`flex h-8 w-8 items-center justify-center rounded-full border text-xs font-bold ${avatarColor}`}
                        >
                          {getInitials(sme.name)}
                        </div>
                        <span
                          className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border border-zinc-950 ring-1 ${STATUS_DOT[sme.status]}`}
                        />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-zinc-200 truncate">
                          {sme.name}
                        </p>
                        <p className="text-xs text-zinc-500 truncate">
                          {sme.role}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0 ml-2">
                      <span className="text-xs font-bold text-sky-400 bg-sky-500/5 border border-sky-500/10 px-2 py-0.5 rounded-full">
                        {sme.compatibility_score}%
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Historical References */}
        <div className="space-y-2 flex flex-col min-h-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            Historical references
          </p>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-600" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search Slack, Jira, Notion…"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 py-2 pl-9 pr-3 text-sm text-zinc-100 outline-none transition-all duration-150 placeholder:text-zinc-600 focus:border-zinc-700 focus:ring-1 focus:ring-zinc-700"
            />
          </div>

          <div className="space-y-4 pt-1">
            {showReferenceSkeleton ? (
              <div className="space-y-3">
                <p className="text-xs text-sky-400 animate-pulse">
                  {analysisMessage ?? "Pulling related references…"}
                </p>
                {[1, 2].map((item) => (
                  <div
                    key={item}
                    className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-4 space-y-2.5"
                  >
                    <div className="mb-2 h-3.5 w-2/3 animate-pulse rounded bg-zinc-800/60" />
                    <div className="h-3 w-full animate-pulse rounded bg-zinc-800/60" />
                  </div>
                ))}
              </div>
            ) : !hasReferences ? (
              <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-4 text-center">
                <p className="text-xs text-zinc-500">
                  No connected references found in system memory. Ask a question in chat or sync integrations to populate.
                </p>
              </div>
            ) : null}

            {!analyzing && hasReferences &&
              sections.map((section) => {
                const itemsToRender = query.trim()
                  ? section.items.filter(
                      (ref) =>
                        ref.title.toLowerCase().includes(query.toLowerCase()) ||
                        ref.snippet.toLowerCase().includes(query.toLowerCase())
                    )
                  : section.items;

                // If we are searching and this section has no matches, don't render it at all to keep it clean
                if (query.trim() && itemsToRender.length === 0) return null;

                return (
                  <div key={section.key} className="space-y-2">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-600 pl-1">
                      {section.label}
                    </p>
                    <div className="space-y-2">
                      {itemsToRender.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-zinc-800/50 bg-zinc-950/10 p-2.5 text-center">
                          <p className="text-[11px] text-zinc-500">
                            No linked {section.label.toLowerCase()} found for this incident.
                          </p>
                        </div>
                      ) : (
                        itemsToRender.map((ref) => {
                          const Icon = section.icon;
                          const isCopied = copiedId === ref.id;
                          const canOpen = isOpenableReferenceUrl(ref.url);
                          return (
                            <div
                              key={ref.id}
                              className={`group relative rounded-lg border ${section.borderClass} ${section.bgClass} p-2.5 transition-all duration-200 shadow-sm`}
                            >
                              {/* Top row: Icon, Title, Actions */}
                              <div className="mb-1 flex items-start justify-between gap-2">
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <Icon className={`h-3.5 w-3.5 shrink-0 ${section.colorClass}`} />
                                  <p className="text-xs font-semibold text-zinc-200 truncate">
                                    {ref.title}
                                  </p>
                                </div>
                                <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                                  {canOpen && (
                                    <>
                                      <button
                                        type="button"
                                        onClick={(e) => handleCopy(e, ref.id, ref.url)}
                                        className="p-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition"
                                        title="Copy Link"
                                      >
                                        {isCopied ? (
                                          <Check className="h-2.5 w-2.5 text-emerald-400" />
                                        ) : (
                                          <Copy className="h-2.5 w-2.5" />
                                        )}
                                      </button>
                                      <a
                                        href={ref.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="p-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition"
                                        title="Open Link"
                                      >
                                        <ExternalLink className="h-2.5 w-2.5" />
                                      </a>
                                    </>
                                  )}
                                </div>
                              </div>

                              {/* Snippet */}
                              {ref.snippet && (
                                <p className="text-[11px] text-zinc-400 leading-normal line-clamp-2 mb-1.5 bg-zinc-950/20 p-1.5 rounded border border-zinc-900/40 shadow-inner">
                                  {ref.snippet}
                                </p>
                              )}

                              {/* Link Badge */}
                              {canOpen ? (
                                <a
                                  href={ref.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 font-mono text-[9px] text-zinc-500 hover:text-zinc-300 transition-colors bg-zinc-950/40 border border-zinc-900/60 px-1.5 py-0.5 rounded"
                                >
                                  <ExternalLink className="h-2 w-2 text-zinc-600" />
                                  <span className="truncate max-w-[150px]">
                                    {ref.url.replace(/^https?:\/\/(www\.)?/, "")}
                                  </span>
                                </a>
                              ) : null}
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                );
              })}

            {!analyzing && hasReferences && filteredSections.length === 0 && (
              <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-4 text-center">
                <p className="text-xs text-zinc-500">No references match search query.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
