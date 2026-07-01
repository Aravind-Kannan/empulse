import { AlertTriangle, Info } from "lucide-react";

import type { EraEvidenceItem } from "@/lib/types";

import { ERA_DIMENSION_COLORS } from "./era-colors";

interface EraEvidenceCardProps {
  item: EraEvidenceItem;
  compact?: boolean;
}

function severityIcon(severity: EraEvidenceItem["severity"]) {
  if (severity === "high") {
    return <AlertTriangle className="h-3.5 w-3.5 text-red-400" />;
  }
  return <Info className="h-3.5 w-3.5 text-amber-400" />;
}

export function EraEvidenceCard({ item, compact = false }: EraEvidenceCardProps) {
  const dimension = ERA_DIMENSION_COLORS[item.dimension];
  return (
    <div
      className={`rounded-lg border border-zinc-800 bg-zinc-950/60 ${
        compact ? "p-3" : "p-4"
      }`}
    >
      <div className="flex items-start gap-2">
        {severityIcon(item.severity)}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-zinc-100">{item.title}</p>
          {!compact && (
            <p className="mt-1 text-xs text-zinc-400">{item.description}</p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
            <span className={`${dimension.text}`}>{dimension.label}</span>
            <span className="text-zinc-500">·</span>
            <span className="text-zinc-400">
              {item.sources[0]?.provider ?? "internal"}
            </span>
            {item.synthetic && (
              <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-500">
                synthetic
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
