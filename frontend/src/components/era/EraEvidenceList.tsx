"use client";

import { useMemo, useState } from "react";

import type { EraEvidenceItem } from "@/lib/types";

import { EraEvidenceCard } from "./EraEvidenceCard";

const PAGE_SIZE = 20;

interface EraEvidenceListProps {
  items: EraEvidenceItem[];
  totalCount: number;
  employeeName: string;
}

export function EraEvidenceList({
  items,
  totalCount,
  employeeName,
}: EraEvidenceListProps) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const visible = useMemo(
    () => items.slice(0, visibleCount),
    [items, visibleCount],
  );

  if (items.length === 0) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-6 text-center">
        <h3 className="text-sm font-medium text-zinc-200">Evidence</h3>
        <p className="mt-2 text-sm text-zinc-400">
          Low observable risk for {employeeName} — connect more integrations for
          richer signals.
        </p>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-zinc-200">
          Evidence ({totalCount})
        </h3>
        {totalCount > items.length && (
          <span className="text-xs text-zinc-500">
            Showing {items.length} of {totalCount}
          </span>
        )}
      </div>
      <div className="max-h-[28rem] space-y-3 overflow-y-auto pr-1">
        {visible.map((item) => (
          <EraEvidenceCard key={item.id} item={item} full />
        ))}
      </div>
      {visibleCount < items.length && (
        <button
          type="button"
          onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
          className="mt-3 w-full rounded-lg border border-zinc-700 px-3 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-800/60"
        >
          Load more ({items.length - visibleCount} remaining)
        </button>
      )}
    </section>
  );
}
