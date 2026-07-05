"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";

import type { EraDimensionKey } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import type { TeamEvidenceItem } from "./era-utils";
import { getInitials } from "./era-utils";

const ITEMS_PER_PAGE = 8;

interface EraEvidenceFeedProps {
  items: TeamEvidenceItem[];
  selectedId: string | null;
  onSelectEmployee: (employeeId: string) => void;
}

function isFileRiskEvidence(id: string): boolean {
  return id.includes("-file-risk-");
}

function fileRiskLabel(item: TeamEvidenceItem): {
  name: string;
  folder: string | null;
  fullPath: string;
} {
  const fromTitle = item.title.match(/^Critical file — (.+)$/i)?.[1];
  const fromId = item.id.split("-file-risk-")[1]?.replace(/^\d+-/, "");
  const fullPath = fromTitle ?? fromId ?? item.title;
  const parts = fullPath.split("/").filter(Boolean);
  if (parts.length <= 1) {
    return { name: fullPath, folder: null, fullPath };
  }
  return {
    name: parts[parts.length - 1] ?? fullPath,
    folder: parts.slice(0, -1).join("/"),
    fullPath,
  };
}

function severityBadgeClass(severity: TeamEvidenceItem["severity"]): string {
  if (severity === "high") {
    return "bg-red-500/15 text-red-200 border-red-500/30";
  }
  if (severity === "medium") {
    return "bg-amber-500/15 text-amber-200 border-amber-500/30";
  }
  return "bg-zinc-500/15 text-zinc-300 border-zinc-600/40";
}

function FileRiskEvidenceRow({
  item,
  highlighted,
  onSelectEmployee,
}: {
  item: TeamEvidenceItem;
  highlighted: boolean;
  onSelectEmployee: (employeeId: string) => void;
}) {
  const { name, folder, fullPath } = fileRiskLabel(item);
  const githubUrl = item.sources.find((source) => source.url)?.url ?? null;

  return (
    <li
      className={`flex items-center justify-between gap-2 rounded border px-2.5 py-1.5 ${
        highlighted
          ? "border-violet-500/30 bg-violet-500/5"
          : "border-zinc-800/60 bg-zinc-950/30"
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <p
            className="truncate font-mono text-xs text-zinc-300"
            title={fullPath}
          >
            {name}
          </p>
          <span className="shrink-0 rounded border border-red-500/30 bg-red-500/15 px-1.5 py-0.5 text-[9px] font-medium uppercase text-red-200">
            Critical
          </span>
          <button
            type="button"
            onClick={() => onSelectEmployee(item.employee_id)}
            className="inline-flex shrink-0 items-center gap-1 rounded border border-zinc-700/80 bg-zinc-900/60 px-1.5 py-0.5 text-[9px] text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200"
          >
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-zinc-800 text-[8px] font-medium text-zinc-300">
              {getInitials(item.employee_name)}
            </span>
            <span className="max-w-[5rem] truncate">{item.employee_name}</span>
          </button>
          <span className="shrink-0 text-[10px] tabular-nums text-zinc-500">
            {Math.round(item.impact_points)} pts
          </span>
        </div>
        {folder ? (
          <p className="truncate text-[10px] text-zinc-600">{folder}/</p>
        ) : null}
      </div>
      {githubUrl ? (
        <a
          href={githubUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-zinc-500 hover:text-sky-300"
          aria-label={`View ${name} on GitHub`}
          onClick={(event) => event.stopPropagation()}
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      ) : null}
    </li>
  );
}

function StandardEvidenceRow({
  item,
  highlighted,
  onSelectEmployee,
}: {
  item: TeamEvidenceItem;
  highlighted: boolean;
  onSelectEmployee: (employeeId: string) => void;
}) {
  const sourceUrl = item.sources.find((source) => source.url)?.url ?? null;
  const dimension = ERA_DIMENSION_COLORS[item.dimension];

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelectEmployee(item.employee_id)}
        className={`flex w-full items-start gap-2 rounded border px-2.5 py-2 text-left transition hover:brightness-110 ${
          highlighted
            ? "border-violet-500/30 bg-violet-500/5"
            : "border-zinc-800/60 bg-zinc-950/30"
        }`}
      >
        <span
          className={`mt-0.5 shrink-0 rounded border px-1.5 py-0.5 text-[8px] font-medium uppercase ${severityBadgeClass(item.severity)}`}
        >
          {item.severity}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] leading-snug text-zinc-200">{item.title}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[9px] text-zinc-500">
            <span className="inline-flex items-center gap-1 text-zinc-400">
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-zinc-800 text-[8px] font-medium">
                {getInitials(item.employee_name)}
              </span>
              {item.employee_name}
            </span>
            <span>·</span>
            <span className={dimension.text}>{dimension.label}</span>
            <span>·</span>
            <span>{item.sources[0]?.provider ?? "internal"}</span>
            <span>·</span>
            <span className="tabular-nums">{Math.round(item.impact_points)} pts</span>
          </div>
        </div>
        {sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-0.5 shrink-0 text-zinc-500 hover:text-sky-300"
            aria-label="Open source link"
            onClick={(event) => event.stopPropagation()}
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        ) : null}
      </button>
    </li>
  );
}

export function EraEvidenceFeed({
  items,
  selectedId,
  onSelectEmployee,
}: EraEvidenceFeedProps) {
  const [dimensionFilter, setDimensionFilter] = useState<EraDimensionKey | "all">(
    "all",
  );
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (dimensionFilter === "all") return items;
    return items.filter((item) => item.dimension === dimensionFilter);
  }, [dimensionFilter, items]);

  const fileRiskCount = useMemo(
    () => filtered.filter((item) => isFileRiskEvidence(item.id)).length,
    [filtered],
  );

  useEffect(() => {
    setPage(0);
  }, [dimensionFilter, items]);

  const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE);
  const paginated = filtered.slice(
    page * ITEMS_PER_PAGE,
    (page + 1) * ITEMS_PER_PAGE,
  );
  const rangeStart = filtered.length === 0 ? 0 : page * ITEMS_PER_PAGE + 1;
  const rangeEnd = Math.min((page + 1) * ITEMS_PER_PAGE, filtered.length);

  return (
    <section className="flex h-full min-h-[28rem] flex-col rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
            Critical evidence
          </p>
          <h2 className="mt-0.5 text-base font-semibold text-zinc-100">
            Team feed
            <span className="ml-1.5 text-sm font-normal tabular-nums text-zinc-500">
              ({filtered.length})
            </span>
          </h2>
          {fileRiskCount > 0 && (
            <p className="mt-0.5 text-[10px] text-zinc-600">
              {fileRiskCount} critical file{fileRiskCount === 1 ? "" : "s"} with
              GitHub links
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          <button
            type="button"
            onClick={() => setDimensionFilter("all")}
            className={`rounded-md border px-2 py-0.5 text-[10px] ${
              dimensionFilter === "all"
                ? "border-zinc-600 bg-zinc-800 text-zinc-100"
                : "border-zinc-800 bg-zinc-950/50 text-zinc-500"
            }`}
          >
            All
          </button>
          {DIMENSION_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setDimensionFilter(key)}
              className={`rounded-md border px-2 py-0.5 text-[10px] ${
                dimensionFilter === key
                  ? "border-zinc-600 bg-zinc-800 text-zinc-100"
                  : "border-zinc-800 bg-zinc-950/50 text-zinc-500"
              }`}
            >
              <span className={ERA_DIMENSION_COLORS[key].text}>
                {ERA_DIMENSION_COLORS[key].label[0]}
              </span>
            </button>
          ))}
        </div>
      </div>

      <ul className="mt-3 min-h-0 flex-1 space-y-1.5 overflow-y-auto">
        {filtered.length === 0 ? (
          <li className="flex h-32 items-center justify-center text-[11px] text-zinc-500">
            No evidence for this filter.
          </li>
        ) : (
          paginated.map((item) => {
            const highlighted = item.employee_id === selectedId;
            if (isFileRiskEvidence(item.id)) {
              return (
                <FileRiskEvidenceRow
                  key={`${item.id}:${item.employee_id}`}
                  item={item}
                  highlighted={highlighted}
                  onSelectEmployee={onSelectEmployee}
                />
              );
            }
            return (
              <StandardEvidenceRow
                key={`${item.id}:${item.employee_id}`}
                item={item}
                highlighted={highlighted}
                onSelectEmployee={onSelectEmployee}
              />
            );
          })
        )}
      </ul>

      {totalPages > 1 ? (
        <div className="mt-3 flex items-center justify-between border-t border-zinc-800/80 pt-3">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((current) => current - 1)}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:pointer-events-none disabled:opacity-40"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Previous
          </button>
          <span className="text-[10px] tabular-nums text-zinc-500">
            {rangeStart}–{rangeEnd} of {filtered.length}
          </span>
          <button
            type="button"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((current) => current + 1)}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:pointer-events-none disabled:opacity-40"
          >
            Next
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : null}
    </section>
  );
}
