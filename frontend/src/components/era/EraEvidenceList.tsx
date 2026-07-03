"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { EraDimensionKey, EraEvidenceItem } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { EraEvidenceCard } from "./EraEvidenceCard";

const PAGE_SIZE = 20;

interface EraEvidenceListProps {
  items: EraEvidenceItem[];
  totalCount: number;
  employeeName: string;
  filterDimension?: EraDimensionKey | null;
  filterDimensions?: EraDimensionKey[];
  groupByDimension?: boolean;
  defaultCollapsed?: boolean;
}

function filterLabel(dimensions: EraDimensionKey[]): string {
  if (dimensions.length === 0) return "";
  if (dimensions.length === 1) {
    return ERA_DIMENSION_COLORS[dimensions[0]].label;
  }
  return dimensions.map((key) => ERA_DIMENSION_COLORS[key].label).join(", ");
}

export function EraEvidenceList({
  items,
  totalCount,
  employeeName,
  filterDimension = null,
  filterDimensions,
  groupByDimension = true,
  defaultCollapsed = false,
}: EraEvidenceListProps) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [expanded, setExpanded] = useState<Partial<Record<EraDimensionKey, boolean>>>(
    {},
  );

  const activeFilters = useMemo(() => {
    if (filterDimensions && filterDimensions.length > 0) {
      return filterDimensions;
    }
    if (filterDimension) {
      return [filterDimension];
    }
    return [];
  }, [filterDimension, filterDimensions]);

  const filtered = useMemo(() => {
    if (activeFilters.length === 0) return items;
    return items.filter((item) => activeFilters.includes(item.dimension));
  }, [activeFilters, items]);

  const grouped = useMemo(() => {
    if (!groupByDimension) {
      return null;
    }
    const keys =
      activeFilters.length > 0
        ? DIMENSION_KEYS.filter((key) => activeFilters.includes(key))
        : DIMENSION_KEYS;
    return keys
      .map((key) => ({
        key,
        items: filtered.filter((item) => item.dimension === key),
      }))
      .filter((group) => group.items.length > 0);
  }, [activeFilters, filtered, groupByDimension]);

  const flatVisible = useMemo(
    () => filtered.slice(0, visibleCount),
    [filtered, visibleCount],
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

  if (activeFilters.length > 0 && filtered.length === 0) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-6 text-center">
        <h3 className="text-sm font-medium text-zinc-200">Evidence</h3>
        <p className="mt-2 text-sm text-zinc-400">
          No evidence items for {filterLabel(activeFilters)}.
        </p>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-zinc-200">
          Evidence ({activeFilters.length > 0 ? filtered.length : totalCount})
          {activeFilters.length > 0 && (
            <span className="ml-2 text-violet-300">· {filterLabel(activeFilters)}</span>
          )}
        </h3>
        {totalCount > items.length && activeFilters.length === 0 && (
          <span className="text-xs text-zinc-500">
            Showing {items.length} of {totalCount}
          </span>
        )}
      </div>

      {grouped ? (
        <div className="space-y-3">
          {grouped.map((group) => {
            const isExpanded = defaultCollapsed
              ? expanded[group.key] === true
              : expanded[group.key] !== false;
            const colors = ERA_DIMENSION_COLORS[group.key];
            return (
              <div
                key={group.key}
                className="rounded-lg border border-zinc-800 bg-zinc-950/40"
              >
                <button
                  type="button"
                  onClick={() =>
                    setExpanded((current) => ({
                      ...current,
                      [group.key]: defaultCollapsed
                        ? current[group.key] !== true
                        : current[group.key] === false,
                    }))
                  }
                  className="flex w-full items-center gap-2 px-3 py-2 text-left"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-zinc-500" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-zinc-500" />
                  )}
                  <span className={`text-xs font-medium ${colors.text}`}>
                    {colors.label}
                  </span>
                  <span className="text-xs text-zinc-500">({group.items.length})</span>
                </button>
                {isExpanded && (
                  <div className="space-y-2 border-t border-zinc-800 px-3 py-3">
                    {group.items.map((item) => (
                      <EraEvidenceCard key={item.id} item={item} full />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="max-h-[28rem] space-y-3 overflow-y-auto pr-1">
          {flatVisible.map((item) => (
            <EraEvidenceCard key={item.id} item={item} full />
          ))}
        </div>
      )}

      {!groupByDimension && visibleCount < filtered.length && (
        <button
          type="button"
          onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
          className="mt-3 w-full rounded-lg border border-zinc-700 px-3 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-800/60"
        >
          Load more ({filtered.length - visibleCount} remaining)
        </button>
      )}
    </section>
  );
}
