"use client";

import type { FileRiskItem, FileRiskQuadrant } from "@/lib/types";

const QUADRANT_META: Record<
  FileRiskQuadrant,
  { label: string; description: string; cellClass: string }
> = {
  critical: {
    label: "Critical",
    description: "High churn · few contributors",
    cellClass: "border-red-500/40 bg-red-500/10",
  },
  stable_niche: {
    label: "Stable niche",
    description: "Low churn · few contributors",
    cellClass: "border-amber-500/30 bg-amber-500/5",
  },
  active_shared: {
    label: "Active shared",
    description: "High churn · many contributors",
    cellClass: "border-sky-500/30 bg-sky-500/5",
  },
  healthy: {
    label: "Healthy",
    description: "Low churn · many contributors",
    cellClass: "border-emerald-500/30 bg-emerald-500/5",
  },
};

const QUADRANT_ORDER: FileRiskQuadrant[] = [
  "stable_niche",
  "critical",
  "healthy",
  "active_shared",
];

interface FileRiskMatrixProps {
  files: FileRiskItem[];
  quadrantCounts?: Record<string, number>;
  crossTrainingPriority?: FileRiskItem[];
  compact?: boolean;
  title?: string;
}

function dotSize(churn: number, compact: boolean): number {
  const base = compact ? 8 : 10;
  return Math.min(compact ? 18 : 22, base + churn);
}

export function FileRiskMatrix({
  files,
  quadrantCounts = {},
  crossTrainingPriority = [],
  compact = false,
  title = "File risk matrix",
}: FileRiskMatrixProps) {
  const byQuadrant = QUADRANT_ORDER.reduce(
    (acc, quadrant) => {
      acc[quadrant] = files.filter((file) => file.quadrant === quadrant);
      return acc;
    },
    {} as Record<FileRiskQuadrant, FileRiskItem[]>,
  );

  if (files.length === 0) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
        <p className="mt-2 text-sm text-zinc-500">
          No file-level risk data yet. Sync GitHub to populate the churn ×
          ownership matrix.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
          <p className="text-xs text-zinc-500">
            Dot size = PR churn (90d). Critical quadrant = cross-training priority.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[11px] text-zinc-400">
          {QUADRANT_ORDER.map((quadrant) => (
            <span key={quadrant}>
              {QUADRANT_META[quadrant].label}: {quadrantCounts[quadrant] ?? 0}
            </span>
          ))}
        </div>
      </div>

      <div className="mb-3 grid grid-cols-[auto_1fr_1fr] gap-2 text-[10px] uppercase tracking-wide text-zinc-500">
        <div />
        <div className="text-center">Low churn</div>
        <div className="text-center">High churn</div>
      </div>

      <div className="grid grid-cols-[auto_1fr_1fr] gap-2">
        <div className="flex items-center justify-end pr-2 text-[10px] uppercase tracking-wide text-zinc-500 [writing-mode:vertical-rl] rotate-180">
          Few contributors
        </div>
        <MatrixCell quadrant="stable_niche" files={byQuadrant.stable_niche} compact={compact} />
        <MatrixCell quadrant="critical" files={byQuadrant.critical} compact={compact} />

        <div className="flex items-center justify-end pr-2 text-[10px] uppercase tracking-wide text-zinc-500 [writing-mode:vertical-rl] rotate-180">
          Many contributors
        </div>
        <MatrixCell quadrant="healthy" files={byQuadrant.healthy} compact={compact} />
        <MatrixCell quadrant="active_shared" files={byQuadrant.active_shared} compact={compact} />
      </div>

      {crossTrainingPriority.length > 0 && !compact && (
        <div className="mt-4 border-t border-zinc-800 pt-4">
          <h4 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Cross-training priority
          </h4>
          <ul className="mt-2 space-y-2">
            {crossTrainingPriority.slice(0, 5).map((file) => (
              <li
                key={`${file.component_id}-${file.file_path}`}
                className="flex items-start justify-between gap-3 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm text-zinc-100">{file.file_path}</p>
                  <p className="text-xs text-zinc-500">
                    {file.churn_score} PRs · bus factor {file.bus_factor}
                    {file.primary_owner_name ? ` · ${file.primary_owner_name}` : ""}
                  </p>
                </div>
                {file.github_url ? (
                  <a
                    href={file.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 text-xs text-sky-300 hover:text-sky-200"
                  >
                    GitHub
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function MatrixCell({
  quadrant,
  files,
  compact,
}: {
  quadrant: FileRiskQuadrant;
  files: FileRiskItem[];
  compact: boolean;
}) {
  const meta = QUADRANT_META[quadrant];
  const height = compact ? "min-h-[7rem]" : "min-h-[9rem]";

  return (
    <div className={`relative rounded-lg border p-3 ${meta.cellClass} ${height}`}>
      <p className="text-[11px] font-medium text-zinc-200">{meta.label}</p>
      <p className="text-[10px] text-zinc-500">{meta.description}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {files.map((file) => {
          const size = dotSize(file.churn_score, compact);
          const title = `${file.file_path} · ${file.churn_score} PRs · ${file.contributor_count} contributors`;
          return file.github_url ? (
            <a
              key={`${file.component_id}-${file.file_path}`}
              href={file.github_url}
              target="_blank"
              rel="noopener noreferrer"
              title={title}
              className="rounded-full bg-red-400/80 transition hover:scale-110"
              style={{
                width: size,
                height: size,
                opacity: quadrant === "critical" ? 1 : 0.75,
              }}
            />
          ) : (
            <span
              key={`${file.component_id}-${file.file_path}`}
              title={title}
              className="rounded-full bg-zinc-400/80"
              style={{ width: size, height: size }}
            />
          );
        })}
      </div>
    </div>
  );
}
