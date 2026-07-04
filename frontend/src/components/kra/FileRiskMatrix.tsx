"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";

import type { FileRiskItem, FileRiskQuadrant } from "@/lib/types";

type FileRiskBucket = "needs_attention" | "healthy";

const RISK_QUADRANTS: FileRiskQuadrant[] = ["critical", "stable_niche"];
const HEALTHY_QUADRANTS: FileRiskQuadrant[] = ["active_shared", "healthy"];

const QUADRANT_META: Record<
  FileRiskQuadrant,
  {
    shortLabel: string;
    tooltip: string;
    badgeClass: string;
  }
> = {
  critical: {
    shortLabel: "Critical",
    tooltip: "One owner, active file",
    badgeClass: "bg-red-500/15 text-red-200 border-red-500/30",
  },
  stable_niche: {
    shortLabel: "Concentrated",
    tooltip: "Knowledge sits with few people",
    badgeClass: "bg-orange-500/15 text-orange-200 border-orange-500/30",
  },
  active_shared: {
    shortLabel: "Active",
    tooltip: "Team shares it, changes often",
    badgeClass: "bg-sky-500/10 text-sky-200 border-sky-500/25",
  },
  healthy: {
    shortLabel: "Healthy",
    tooltip: "Team shares it, quiet file",
    badgeClass: "bg-emerald-500/10 text-emerald-200 border-emerald-500/25",
  },
};

const BUCKET_META: Record<
  FileRiskBucket,
  {
    shortLabel: string;
    accentClass: string;
    borderClass: string;
  }
> = {
  needs_attention: {
    shortLabel: "At risk",
    accentClass: "text-red-300",
    borderClass: "border-red-500/30 bg-red-500/5",
  },
  healthy: {
    shortLabel: "Healthy",
    accentClass: "text-emerald-300",
    borderClass: "border-emerald-500/25 bg-emerald-500/5",
  },
};

const BUCKET_PRIORITY: FileRiskBucket[] = ["needs_attention", "healthy"];

const RISK_QUADRANT_ORDER: Record<FileRiskQuadrant, number> = {
  critical: 0,
  stable_niche: 1,
  active_shared: 2,
  healthy: 3,
};

/** FileRiskRow height incl. space-y-2 gap — keeps list area stable across buckets */
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
  collapsible?: boolean;
  defaultExpanded?: boolean;
  emptyMessage?: string;
}

function fileRiskBucket(quadrant: FileRiskQuadrant): FileRiskBucket {
  return RISK_QUADRANTS.includes(quadrant) ? "needs_attention" : "healthy";
}

function ownershipSignal(file: FileRiskItem): string | null {
  if (!file.primary_owner_name) {
    return null;
  }
  if (file.primary_owner_doa_pct != null) {
    return `${file.primary_owner_name} owns ${file.primary_owner_doa_pct.toFixed(0)}%`;
  }
  return `${file.primary_owner_name} is primary owner`;
}

function fileRiskSummary(file: FileRiskItem): string | null {
  if (file.quadrant === "healthy" || file.quadrant === "active_shared") {
    return null;
  }
  return ownershipSignal(file);
}

function bucketCount(
  bucket: FileRiskBucket,
  quadrantCounts: Record<string, number>,
  byBucket: Record<FileRiskBucket, FileRiskItem[]>,
): number {
  if (Object.keys(quadrantCounts).length > 0) {
    const quadrants = bucket === "needs_attention" ? RISK_QUADRANTS : HEALTHY_QUADRANTS;
    return quadrants.reduce((sum, quadrant) => sum + (quadrantCounts[quadrant] ?? 0), 0);
  }
  return byBucket[bucket].length;
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

function FileRiskRow({
  file,
  emphasize = false,
}: {
  file: FileRiskItem;
  emphasize?: boolean;
}) {
  const { name, folder } = formatFileLabel(file.file_path);
  const bucket = fileRiskBucket(file.quadrant);
  const bucketMeta = BUCKET_META[bucket];
  const quadrantMeta = QUADRANT_META[file.quadrant];
  const summary = fileRiskSummary(file);

  return (
    <li
      className={`flex items-start justify-between gap-3 rounded-lg border px-3 py-2.5 ${
        emphasize ? bucketMeta.borderClass : "border-zinc-800 bg-zinc-950/40"
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-mono text-sm text-zinc-100">{name}</p>
          <span
            title={quadrantMeta.tooltip}
            className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${quadrantMeta.badgeClass}`}
          >
            {quadrantMeta.shortLabel}
          </span>
        </div>
        {folder ? (
          <p className="mt-0.5 truncate text-xs text-zinc-500">{folder}/</p>
        ) : null}
        {summary ? (
          <p className="mt-1 text-xs text-zinc-400">{summary}</p>
        ) : null}
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

function FileListPagination({
  page,
  totalItems,
  onPageChange,
}: {
  page: number;
  totalItems: number;
  onPageChange: (updater: (current: number) => number) => void;
}) {
  const totalPages = Math.ceil(totalItems / FILES_PER_PAGE);
  if (totalPages <= 1) {
    return null;
  }

  const rangeStart = totalItems === 0 ? 0 : page * FILES_PER_PAGE + 1;
  const rangeEnd = Math.min((page + 1) * FILES_PER_PAGE, totalItems);

  return (
    <div className="mt-3 flex items-center justify-between border-t border-zinc-800/80 pt-3">
      <button
        type="button"
        disabled={page === 0}
        onClick={() => onPageChange((current) => current - 1)}
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:pointer-events-none disabled:opacity-40"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
        Previous
      </button>
      <span className="text-xs tabular-nums text-zinc-500">
        {rangeStart}–{rangeEnd} of {totalItems}
      </span>
      <button
        type="button"
        disabled={page >= totalPages - 1}
        onClick={() => onPageChange((current) => current + 1)}
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:pointer-events-none disabled:opacity-40"
      >
        Next
        <ChevronRight className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function FileRiskMatrix({
  files,
  quadrantCounts = {},
  crossTrainingPriority = [],
  compact = false,
  title = "File ownership risk",
  collapsible = false,
  defaultExpanded = false,
  emptyMessage,
}: FileRiskMatrixProps) {
  const [selectedBucket, setSelectedBucket] = useState<FileRiskBucket>("needs_attention");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState(defaultExpanded);

  useEffect(() => {
    setExpanded(defaultExpanded);
  }, [defaultExpanded, files]);

  useEffect(() => {
    setSelectedBucket("needs_attention");
    setPage(0);
  }, [files]);

  useEffect(() => {
    setPage(0);
  }, [selectedBucket]);

  const byBucket = useMemo(() => {
    const needsAttention = files
      .filter((file) => fileRiskBucket(file.quadrant) === "needs_attention")
      .sort((a, b) => {
        const order =
          RISK_QUADRANT_ORDER[a.quadrant] - RISK_QUADRANT_ORDER[b.quadrant];
        if (order !== 0) {
          return order;
        }
        return b.churn_score - a.churn_score;
      });
    const healthy = files
      .filter((file) => fileRiskBucket(file.quadrant) === "healthy")
      .sort((a, b) => b.churn_score - a.churn_score);

    return {
      needs_attention: needsAttention,
      healthy,
    } satisfies Record<FileRiskBucket, FileRiskItem[]>;
  }, [files]);

  const listBodyMinHeightPx = useMemo(() => {
    const tallestBucketCount = Math.max(
      ...BUCKET_PRIORITY.map((bucket) => byBucket[bucket].length),
    );
    const rowCount = Math.max(Math.min(tallestBucketCount, FILES_PER_PAGE), 1);
    const needsPagination = tallestBucketCount > FILES_PER_PAGE;
    return (
      rowCount * FILE_ROW_HEIGHT_PX +
      LIST_BODY_PADDING_PX +
      (needsPagination ? PAGINATION_HEIGHT_PX : 0)
    );
  }, [byBucket]);

  const selectedFiles = byBucket[selectedBucket];
  const paginatedFiles = selectedFiles.slice(
    page * FILES_PER_PAGE,
    (page + 1) * FILES_PER_PAGE,
  );

  const priorityFiles =
    crossTrainingPriority.length > 0
      ? crossTrainingPriority
      : byBucket.needs_attention;

  if (files.length === 0) {
    if (compact && collapsible) {
      return (
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="flex w-full items-start gap-2 text-left"
            aria-expanded={expanded}
          >
            {expanded ? (
              <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
            ) : (
              <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
            )}
            <h3 className="min-w-0 flex-1 text-sm font-medium text-zinc-200">
              {title}
              <span className="ml-2 font-normal tabular-nums text-zinc-500">
                (0 files)
              </span>
            </h3>
          </button>
          {expanded ? (
            <p className="mt-3 border-t border-zinc-800 pt-3 text-sm text-zinc-500">
              {emptyMessage ??
                "No file ownership data yet. Connect and sync GitHub to see which files depend on too few people."}
            </p>
          ) : null}
        </section>
      );
    }

    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
        <p className="mt-2 text-sm text-zinc-500">
          {emptyMessage ??
            "No file ownership data yet. Connect and sync GitHub to see which files depend on too few people."}
        </p>
      </section>
    );
  }

  if (compact) {
    const fileCount = priorityFiles.length;
    const paginatedPriorityFiles = priorityFiles.slice(
      page * FILES_PER_PAGE,
      (page + 1) * FILES_PER_PAGE,
    );
    const heading = (
      <div className="min-w-0 flex-1 text-left">
        <h3 className="text-sm font-medium text-zinc-200">
          {title}
          <span className="ml-2 font-normal tabular-nums text-zinc-500">
            ({fileCount} {fileCount === 1 ? "file" : "files"})
          </span>
        </h3>
        <p className="mt-1 text-xs text-zinc-500">
          Files where this person is the main owner.
        </p>
      </div>
    );

    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
        {collapsible ? (
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="flex w-full items-start gap-2 text-left"
            aria-expanded={expanded}
          >
            {expanded ? (
              <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
            ) : (
              <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
            )}
            {heading}
          </button>
        ) : (
          <div className="mb-3">{heading}</div>
        )}
        {(!collapsible || expanded) && (
          <div className={collapsible ? "mt-3 border-t border-zinc-800 pt-3" : undefined}>
            <ul className="space-y-2">
              {paginatedPriorityFiles.map((file) => (
                <FileRiskRow
                  key={`${file.component_id}-${file.file_path}`}
                  file={file}
                  emphasize
                />
              ))}
            </ul>
            <FileListPagination
              page={page}
              totalItems={fileCount}
              onPageChange={setPage}
            />
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4 sm:p-5">
      <div className="mb-4">
        <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        {BUCKET_PRIORITY.map((bucket) => {
          const meta = BUCKET_META[bucket];
          const count = bucketCount(bucket, quadrantCounts, byBucket);
          const isSelected = selectedBucket === bucket;
          return (
            <button
              key={bucket}
              type="button"
              onClick={() => setSelectedBucket(bucket)}
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
            </button>
          );
        })}
      </div>

      <div className={`rounded-xl border ${BUCKET_META[selectedBucket].borderClass}`}>
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
              <FileListPagination
                page={page}
                totalItems={selectedFiles.length}
                onPageChange={setPage}
              />
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
