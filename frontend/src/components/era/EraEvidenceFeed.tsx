"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, Info } from "lucide-react";

import type { EraDimensionKey } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import type { TeamEvidenceItem } from "./era-utils";

interface EraEvidenceFeedProps {
  items: TeamEvidenceItem[];
  selectedId: string | null;
  onSelectEmployee: (employeeId: string) => void;
}

function severityGlyph(severity: TeamEvidenceItem["severity"]) {
  if (severity === "high") {
    return <AlertTriangle className="h-4 w-4 text-red-400" />;
  }
  return <Info className="h-4 w-4 text-amber-400" />;
}

export function EraEvidenceFeed({
  items,
  selectedId,
  onSelectEmployee,
}: EraEvidenceFeedProps) {
  const [dimensionFilter, setDimensionFilter] = useState<EraDimensionKey | "all">(
    "all",
  );

  const filtered = useMemo(() => {
    if (dimensionFilter === "all") return items;
    return items.filter((item) => item.dimension === dimensionFilter);
  }, [dimensionFilter, items]);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/30">
      <div className="flex flex-col gap-3 border-b border-zinc-800 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-sm font-medium text-zinc-200">Critical evidence feed</h2>
        <div className="flex flex-wrap gap-1">
          <button
            type="button"
            onClick={() => setDimensionFilter("all")}
            className={`rounded-full px-2.5 py-1 text-[11px] ${
              dimensionFilter === "all"
                ? "bg-zinc-100 text-slate-950"
                : "bg-zinc-800 text-zinc-400"
            }`}
          >
            All
          </button>
          {DIMENSION_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setDimensionFilter(key)}
              className={`rounded-full px-2.5 py-1 text-[11px] ${
                dimensionFilter === key
                  ? "bg-zinc-100 text-slate-950"
                  : "bg-zinc-800 text-zinc-400"
              }`}
            >
              {ERA_DIMENSION_COLORS[key].label[0]}
            </button>
          ))}
        </div>
      </div>

      <div className="divide-y divide-zinc-800">
        {filtered.length === 0 ? (
          <p className="p-6 text-center text-sm text-zinc-500">
            No evidence items for this filter.
          </p>
        ) : (
          filtered.map((item) => {
            const highlighted = item.employee_id === selectedId;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectEmployee(item.employee_id)}
                className={`flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-zinc-800/40 ${
                  highlighted ? "bg-zinc-800/50" : ""
                }`}
              >
                {severityGlyph(item.severity)}
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-zinc-100">
                    <span className="font-medium">{item.employee_name}</span>
                    {" — "}
                    {item.title}
                  </p>
                  <p className="mt-0.5 text-xs text-zinc-500">
                    {item.sources[0]?.provider ?? "internal"} ·{" "}
                    {ERA_DIMENSION_COLORS[item.dimension].label}
                  </p>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
