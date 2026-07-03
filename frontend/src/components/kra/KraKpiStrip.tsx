"use client";

import Link from "next/link";

import type {
  CriticalSpofResult,
  DocumentationCoverageResult,
  DocumentationGapComponent,
} from "@/lib/types";

interface KraKpiStripProps {
  criticalSpof: CriticalSpofResult | null;
  documentationCoverage: DocumentationCoverageResult | null;
  loading?: boolean;
  filterActive?: boolean;
  onToggleFilter?: () => void;
  gapPanelOpen?: boolean;
  onToggleGapPanel?: () => void;
  onSelectGapComponent?: (gap: DocumentationGapComponent) => void;
}

function SkeletonCard() {
  return (
    <div className="min-w-[12rem] flex-1 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="h-3 w-24 rounded bg-zinc-800" />
      <div className="mt-3 h-7 w-10 rounded bg-zinc-800" />
      <div className="mt-2 h-3 w-32 rounded bg-zinc-800" />
    </div>
  );
}

function coverageRingColor(pct: number): string {
  if (pct >= 80) return "#34d399";
  if (pct >= 50) return "#fbbf24";
  return "#f87171";
}

function DocCoverageRing({ pct }: { pct: number }) {
  const ringRadius = 18;
  const circumference = 2 * Math.PI * ringRadius;
  const dash = (pct / 100) * circumference;

  return (
    <svg className="h-11 w-11 -rotate-90 shrink-0" viewBox="0 0 44 44">
      <circle
        cx="22"
        cy="22"
        r={ringRadius}
        fill="none"
        stroke="#27272a"
        strokeWidth="4"
      />
      <circle
        cx="22"
        cy="22"
        r={ringRadius}
        fill="none"
        stroke={coverageRingColor(pct)}
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${circumference}`}
      />
    </svg>
  );
}

export function KraKpiStrip({
  criticalSpof,
  documentationCoverage,
  loading = false,
  filterActive = false,
  onToggleFilter,
  gapPanelOpen = false,
  onToggleGapPanel,
}: KraKpiStripProps) {
  if (loading) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-1">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  return (
    <div className="flex gap-3 overflow-x-auto pb-1">
      {criticalSpof && (
        <button
          type="button"
          onClick={onToggleFilter}
          title="Tier-1 revenue systems with bus factor ≤1 or ≤1 owner"
          className={`min-w-[12rem] flex-1 rounded-xl border p-4 text-left transition hover:bg-zinc-900/60 ${
            filterActive
              ? "border-red-500/50 bg-red-500/10"
              : criticalSpof.count > 0
                ? "border-red-500/30 bg-red-500/5 hover:border-red-500/40"
                : "border-emerald-500/30 bg-emerald-500/5 hover:border-emerald-500/40"
          }`}
        >
          <div className="flex items-center gap-2">
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              Critical SPOFs
            </p>
            {criticalSpof.data_completeness.is_partial && (
              <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-300">
                partial
              </span>
            )}
          </div>
          <p
            className={`mt-1 text-2xl font-semibold ${
              criticalSpof.count > 0 ? "text-red-300" : "text-emerald-300"
            }`}
          >
            {criticalSpof.count}
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            {criticalSpof.count === 0
              ? "No revenue-critical systems without backup"
              : `${criticalSpof.count} revenue-critical system${criticalSpof.count === 1 ? "" : "s"} have no backup`}
            {" · "}
            <span className={filterActive ? "text-red-300" : "text-zinc-400"}>
              {filterActive ? "Showing on graph" : "View components"}
            </span>
          </p>
        </button>
      )}

      {documentationCoverage && (
        <DocCoverageCard
          coverage={documentationCoverage}
          gapPanelOpen={gapPanelOpen}
          onToggleGapPanel={onToggleGapPanel}
        />
      )}
    </div>
  );
}

function DocCoverageCard({
  coverage,
  gapPanelOpen,
  onToggleGapPanel,
}: {
  coverage: DocumentationCoverageResult;
  gapPanelOpen: boolean;
  onToggleGapPanel?: () => void;
}) {
  const notionMissing = coverage.data_completeness.notion === "missing";
  const notionPartial = coverage.data_completeness.notion === "partial";
  const partial = coverage.data_completeness.is_partial;
  const pct = coverage.coverage_pct;
  const gapCount = coverage.gap_components.length;
  const canShowGaps = !notionMissing && !notionPartial && pct !== null && gapCount > 0;

  if (notionMissing) {
    return (
      <div className="min-w-[14rem] flex-1 rounded-xl border border-dashed border-zinc-700 bg-zinc-900/30 p-4">
        <p className="text-xs uppercase tracking-wide text-zinc-500">
          Doc coverage
        </p>
        <p className="mt-2 text-sm text-zinc-400">
          Connect Notion to score runbook coverage for active systems.
        </p>
        <Link
          href="/settings/integrations"
          className="mt-3 inline-block text-xs font-medium text-sky-400 hover:text-sky-300"
        >
          Connect Notion →
        </Link>
      </div>
    );
  }

  if (notionPartial) {
    return (
      <div className="min-w-[14rem] flex-1 rounded-xl border border-dashed border-amber-500/30 bg-amber-500/5 p-4">
        <p className="text-xs uppercase tracking-wide text-zinc-500">
          Doc coverage
        </p>
        <p className="mt-2 text-sm text-zinc-400">
          Notion is connected — run a sync to index runbook pages.
        </p>
        <Link
          href="/settings/integrations"
          className="mt-3 inline-block text-xs font-medium text-amber-300 hover:text-amber-200"
        >
          Sync Notion →
        </Link>
      </div>
    );
  }

  const headline =
    pct === null
      ? "No active systems to score"
      : `${pct}% of active systems have current runbooks`;

  const toneClass =
    pct === null
      ? "border-zinc-700 bg-zinc-900/30"
      : pct >= 80
        ? "border-emerald-500/30 bg-emerald-500/5 hover:border-emerald-500/40"
        : pct >= 50
          ? "border-amber-500/30 bg-amber-500/5 hover:border-amber-500/40"
          : "border-red-500/30 bg-red-500/5 hover:border-red-500/40";

  const Wrapper = canShowGaps ? "button" : "div";

  return (
    <Wrapper
      {...(canShowGaps
        ? {
            type: "button" as const,
            onClick: onToggleGapPanel,
          }
        : {})}
      className={`min-w-[14rem] flex-1 rounded-xl border p-4 text-left transition ${
        canShowGaps ? "hover:bg-zinc-900/60" : ""
      } ${gapPanelOpen && canShowGaps ? "border-sky-500/40 bg-sky-500/5" : toneClass}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              Doc coverage
            </p>
            {partial && (
              <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-300">
                partial
              </span>
            )}
          </div>
          <p
            className={`mt-1 text-2xl font-semibold ${
              pct === null
                ? "text-zinc-400"
                : pct >= 80
                  ? "text-emerald-300"
                  : pct >= 50
                    ? "text-amber-300"
                    : "text-red-300"
            }`}
          >
            {pct === null ? "—" : `${pct}%`}
          </p>
        </div>
        {pct !== null && <DocCoverageRing pct={pct} />}
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {headline}
        {canShowGaps && (
          <>
            {" · "}
            <span className={gapPanelOpen ? "text-sky-300" : "text-zinc-400"}>
              {gapPanelOpen ? "Hide gaps" : "View gaps"}
            </span>
          </>
        )}
      </p>
    </Wrapper>
  );
}

interface KraDocGapPanelProps {
  gaps: DocumentationGapComponent[];
  open: boolean;
  onClose: () => void;
  onSelectComponent: (gap: DocumentationGapComponent) => void;
}

export function KraDocGapPanel({
  gaps,
  open,
  onClose,
  onSelectComponent,
}: KraDocGapPanelProps) {
  if (!open) return null;

  return (
    <>
      <button
        type="button"
        aria-label="Close gap panel"
        className="fixed inset-0 z-30 bg-black/40"
        onClick={onClose}
      />
      <aside className="fixed right-0 top-0 z-40 flex h-full w-full max-w-lg flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              Documentation gaps
            </p>
            <h2 className="text-lg font-semibold text-zinc-100">
              Uncovered active systems
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1 text-sm text-zinc-400 hover:bg-zinc-800"
          >
            Close
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {gaps.length === 0 ? (
            <p className="text-sm text-zinc-500">All active systems are covered.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
                  <th className="pb-2 pr-3 font-medium">Component</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {gaps.map((gap) => (
                  <tr
                    key={gap.component_id}
                    className="border-b border-zinc-800/60 hover:bg-zinc-900/40"
                  >
                    <td className="py-3 pr-3">
                      <button
                        type="button"
                        onClick={() => onSelectComponent(gap)}
                        className="font-medium text-zinc-200 hover:text-sky-300"
                      >
                        {gap.component_name}
                      </button>
                    </td>
                    <td className="py-3 pr-3 text-zinc-400">
                      {gap.gap_reason === "missing" ? (
                        "Missing runbook"
                      ) : (
                        <>
                          Stale
                          {gap.last_doc_edit
                            ? ` (${Math.max(
                                0,
                                Math.floor(
                                  (Date.now() -
                                    new Date(gap.last_doc_edit).getTime()) /
                                    86400000,
                                ),
                              )}d)`
                            : ""}
                        </>
                      )}
                    </td>
                    <td className="py-3">
                      {gap.gap_reason === "stale" && gap.notion_page_urls[0] ? (
                        <a
                          href={gap.notion_page_urls[0]}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sky-400 hover:text-sky-300"
                        >
                          Open Notion
                        </a>
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </aside>
    </>
  );
}
