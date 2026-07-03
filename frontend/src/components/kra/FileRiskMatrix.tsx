"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, ChevronDown, ExternalLink, Users } from "lucide-react";

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

function QuadrantSection({
  quadrant,
  files,
  defaultOpen,
}: {
  quadrant: FileRiskQuadrant;
  files: FileRiskItem[];
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = QUADRANT_META[quadrant];

  if (files.length === 0) return null;

  return (
    <div className={`rounded-xl border ${meta.borderClass}`}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
      >
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className={`text-sm font-medium ${meta.accentClass}`}>{meta.label}</h4>
            <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[11px] text-zinc-300">
              {files.length} {files.length === 1 ? "file" : "files"}
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-500">{meta.description}</p>
        </div>
        <ChevronDown
          className={`mt-0.5 h-4 w-4 shrink-0 text-zinc-500 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open ? (
        <ul className="space-y-2 border-t border-zinc-800/80 px-3 pb-3 pt-2">
          {files.map((file) => (
            <FileRiskRow
              key={`${file.component_id}-${file.file_path}`}
              file={file}
            />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function FileRiskMatrix({
  files,
  quadrantCounts = {},
  crossTrainingPriority = [],
  compact = false,
  title = "File ownership risk",
}: FileRiskMatrixProps) {
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

  const priorityFiles =
    crossTrainingPriority.length > 0
      ? crossTrainingPriority
      : byQuadrant.critical;

  const atRiskCount =
    quadrantCounts.critical ?? byQuadrant.critical.length;

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
          return (
            <div
              key={quadrant}
              className={`rounded-lg border px-3 py-3 ${meta.borderClass}`}
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
            </div>
          );
        })}
      </div>

      {priorityFiles.length > 0 ? (
        <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/5 p-4">
          <div className="mb-3 flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-300" />
            <div>
              <h4 className="text-sm font-medium text-red-100">
                {atRiskCount === 1 ? "1 file needs attention" : `${atRiskCount} files need attention`}
              </h4>
              <p className="mt-1 text-xs text-red-200/80">
                High change rate with too few editors. Prioritize cross-training on
                these files first.
              </p>
            </div>
          </div>
          <ul className="space-y-2">
            {priorityFiles.slice(0, 8).map((file) => (
              <FileRiskRow
                key={`priority-${file.component_id}-${file.file_path}`}
                file={file}
                emphasize
              />
            ))}
          </ul>
          {priorityFiles.length > 8 ? (
            <p className="mt-2 text-xs text-red-200/70">
              +{priorityFiles.length - 8} more in the sections below
            </p>
          ) : null}
        </div>
      ) : (
        <div className="mb-5 flex items-start gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/5 px-4 py-3">
          <Users className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
          <div>
            <p className="text-sm font-medium text-emerald-100">
              No high-risk files in this component
            </p>
            <p className="mt-1 text-xs text-emerald-200/80">
              Nothing is both fast-changing and owned by only one or two people.
            </p>
          </div>
        </div>
      )}

      <div className="space-y-3">
        <h4 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          All files by category
        </h4>
        {QUADRANT_PRIORITY.map((quadrant) => (
          <QuadrantSection
            key={quadrant}
            quadrant={quadrant}
            files={byQuadrant[quadrant]}
            defaultOpen={quadrant === "critical" && priorityFiles.length === 0}
          />
        ))}
      </div>
    </section>
  );
}
