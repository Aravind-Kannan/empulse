"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";

import type { FileRiskItem, FileRiskQuadrant } from "@/lib/types";

const QUADRANT_META: Record<
  FileRiskQuadrant,
  {
    label: string;
    shortLabel: string;
    description: string;
    accentClass: string;
    borderClass: string;
    badgeClass: string;
  }
> = {
  critical: {
    label: "Needs cross-training",
    shortLabel: "At risk",
    description: "Changes often, but only one or two people edit this file.",
    accentClass: "text-red-300",
    borderClass: "border-red-500/30 bg-red-500/5",
    badgeClass: "bg-red-500/15 text-red-200 border-red-500/30",
  },
  stable_niche: {
    label: "Narrow ownership",
    shortLabel: "Narrow",
    description: "Rarely changes, but few people know it well.",
    accentClass: "text-amber-300",
    borderClass: "border-amber-500/25 bg-amber-500/5",
    badgeClass: "bg-amber-500/10 text-amber-200 border-amber-500/25",
  },
  active_shared: {
    label: "Active & shared",
    shortLabel: "Shared",
    description: "Many people edit this file — healthy distribution.",
    accentClass: "text-sky-300",
    borderClass: "border-sky-500/25 bg-sky-500/5",
    badgeClass: "bg-sky-500/10 text-sky-200 border-sky-500/25",
  },
  healthy: {
    label: "Healthy",
    shortLabel: "Healthy",
    description: "Low change rate with enough people who know the code.",
    accentClass: "text-emerald-300",
    borderClass: "border-emerald-500/25 bg-emerald-500/5",
    badgeClass: "bg-emerald-500/10 text-emerald-200 border-emerald-500/25",
  },
};

const QUADRANT_PRIORITY: FileRiskQuadrant[] = [
  "critical",
  "stable_niche",
  "active_shared",
  "healthy",
];

/** FileRiskRow height incl. space-y-2 gap — keeps list area stable across quadrants */
const FILE_ROW_HEIGHT_PX = 76;
const LIST_BODY_PADDING_PX = 24;
const PAGINATION_HEIGHT_PX = 44;
const FILES_PER_PAGE = 5;

interface FileRiskMatrixProps {
  files: FileRiskItem[];
  quadrantCounts?: Record<string, number>;
  crossTrainingPriority?: FileRiskItem[];
  compact?: boolean;
  title?: string;
}

function formatFileLabel(path: string): { name: string; folder: string | null } {
  const parts = path.split("/").filter(Boolean);
  if (parts.length <= 1) {
    return { name: path, folder: null };
  }
  return {
    name: parts[parts.length - 1] ?? path,
    folder: parts.slice(0, -1).join("/"),
  };
}

function contributorLabel(count: number): string {
  if (count <= 1) return "1 person edits this";
  if (count === 2) return "2 people edit this";
  return `${count} people edit this`;
}

function changeLabel(churn: number): string {
  if (churn === 0) return "No recent changes";
  if (churn === 1) return "1 change in 90 days";
  return `${churn} changes in 90 days`;
}

function FileRiskRow({ file, emphasize = false }: { file: FileRiskItem; emphasize?: boolean }) {
  const { name, folder } = formatFileLabel(file.file_path);
  const meta = QUADRANT_META[file.quadrant];

  return (
    <li
      className={`flex items-start justify-between gap-3 rounded-lg border px-3 py-2.5 ${
        emphasize ? meta.borderClass : "border-zinc-800 bg-zinc-950/40"
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-mono text-sm text-zinc-100">{name}</p>
          {!emphasize && (
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${meta.badgeClass}`}
            >
              {meta.shortLabel}
            </span>
          )}
        </div>
        {folder ? (
          <p className="mt-0.5 truncate text-xs text-zinc-500">{folder}/</p>
        ) : null}
        <p className="mt-1.5 text-xs text-zinc-400">
          {changeLabel(file.churn_score)}
          <span className="text-zinc-600"> · </span>
          {contributorLabel(file.contributor_count)}
          {file.primary_owner_name ? (
            <>
              <span className="text-zinc-600"> · </span>
              Main owner: {file.primary_owner_name}
            </>
          ) : null}
        </p>
      </div>
      {file.github_url ? (
        <a
          href={file.github_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-0.5 inline-flex shrink-0 items-center gap-1 text-xs text-sky-300 hover:text-sky-200"
        >
          View
          <ExternalLink className="h-3 w-3" />
        </a>
      ) : null}
    </li>
  );
}

export function FileRiskMatrix({
  files,
  quadrantCounts = {},
  crossTrainingPriority = [],
  compact = false,
  title = "File ownership risk",
}: FileRiskMatrixProps) {
  const [selectedQuadrant, setSelectedQuadrant] =
    useState<FileRiskQuadrant>("critical");
  const [page, setPage] = useState(0);

  useEffect(() => {
    setSelectedQuadrant("critical");
    setPage(0);
  }, [files]);

  useEffect(() => {
    setPage(0);
  }, [selectedQuadrant]);

  const byQuadrant = useMemo(
    () =>
      QUADRANT_PRIORITY.reduce(
        (acc, quadrant) => {
          acc[quadrant] = files.filter((file) => file.quadrant === quadrant);
          return acc;
        },
        {} as Record<FileRiskQuadrant, FileRiskItem[]>,
      ),
    [files],
  );

  const listBodyMinHeightPx = useMemo(() => {
    const tallestQuadrantCount = Math.max(
      ...QUADRANT_PRIORITY.map((quadrant) => byQuadrant[quadrant].length),
    );
    const rowCount = Math.max(
      Math.min(tallestQuadrantCount, FILES_PER_PAGE),
      1,
    );
    const needsPagination = tallestQuadrantCount > FILES_PER_PAGE;
    return (
      rowCount * FILE_ROW_HEIGHT_PX +
      LIST_BODY_PADDING_PX +
      (needsPagination ? PAGINATION_HEIGHT_PX : 0)
    );
  }, [byQuadrant]);

  const selectedFiles = byQuadrant[selectedQuadrant];
  const totalPages = Math.ceil(selectedFiles.length / FILES_PER_PAGE);
  const paginatedFiles = selectedFiles.slice(
    page * FILES_PER_PAGE,
    (page + 1) * FILES_PER_PAGE,
  );
  const rangeStart =
    selectedFiles.length === 0 ? 0 : page * FILES_PER_PAGE + 1;
  const rangeEnd = Math.min((page + 1) * FILES_PER_PAGE, selectedFiles.length);

  const priorityFiles =
    crossTrainingPriority.length > 0
      ? crossTrainingPriority
      : byQuadrant.critical;

  if (files.length === 0) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
        <p className="mt-2 text-sm text-zinc-500">
          No file ownership data yet. Connect and sync GitHub to see which files
          depend on too few people.
        </p>
      </section>
    );
  }

  if (compact) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
        <div className="mb-3">
          <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
          <p className="mt-1 text-xs text-zinc-500">
            Files where this person is the main owner and the team would struggle
            if they were unavailable.
          </p>
        </div>
        <ul className="space-y-2">
          {priorityFiles.map((file) => (
            <FileRiskRow
              key={`${file.component_id}-${file.file_path}`}
              file={file}
              emphasize
            />
          ))}
        </ul>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4 sm:p-5">
      <div className="mb-5">
        <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-zinc-500">
          Shows which files change often but are owned by only one or two people.
          Those are the best candidates for pairing and knowledge sharing.
        </p>
      </div>

      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {QUADRANT_PRIORITY.map((quadrant) => {
          const meta = QUADRANT_META[quadrant];
          const count = quadrantCounts[quadrant] ?? byQuadrant[quadrant].length;
          const isSelected = selectedQuadrant === quadrant;
          return (
            <button
              key={quadrant}
              type="button"
              onClick={() => setSelectedQuadrant(quadrant)}
              className={`rounded-lg border px-3 py-3 text-left transition-colors hover:brightness-110 ${
                meta.borderClass
              } ${isSelected ? "ring-2 ring-zinc-400/50" : ""}`}
            >
              <p className={`text-[11px] font-medium uppercase tracking-wide ${meta.accentClass}`}>
                {meta.shortLabel}
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100">
                {count}
              </p>
              <p className="mt-1 text-[11px] leading-snug text-zinc-500">
                {meta.label}
              </p>
            </button>
          );
        })}
      </div>

      <div
        className={`rounded-xl border ${QUADRANT_META[selectedQuadrant].borderClass}`}
      >
        <div className="border-b border-zinc-800/80 px-4 py-3">
          <h4
            className={`text-sm font-medium ${QUADRANT_META[selectedQuadrant].accentClass}`}
          >
            {QUADRANT_META[selectedQuadrant].label}
          </h4>
          <p className="mt-1 text-xs text-zinc-500">
            {QUADRANT_META[selectedQuadrant].description}
          </p>
        </div>
        <div
          className="flex flex-col px-3 py-3"
          style={{ minHeight: listBodyMinHeightPx }}
        >
          {selectedFiles.length > 0 ? (
            <>
              <ul className="space-y-2">
                {paginatedFiles.map((file) => (
                  <FileRiskRow
                    key={`${file.component_id}-${file.file_path}`}
                    file={file}
                  />
                ))}
              </ul>
              {totalPages > 1 ? (
                <div className="mt-3 flex items-center justify-between border-t border-zinc-800/80 pt-3">
                  <button
                    type="button"
                    disabled={page === 0}
                    onClick={() => setPage((current) => current - 1)}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:pointer-events-none disabled:opacity-40"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    Previous
                  </button>
                  <span className="text-xs tabular-nums text-zinc-500">
                    {rangeStart}–{rangeEnd} of {selectedFiles.length}
                  </span>
                  <button
                    type="button"
                    disabled={page >= totalPages - 1}
                    onClick={() => setPage((current) => current + 1)}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:pointer-events-none disabled:opacity-40"
                  >
                    Next
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : null}
            </>
          ) : (
            <p className="flex flex-1 items-center justify-center text-sm text-zinc-500">
              No files in this category.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
