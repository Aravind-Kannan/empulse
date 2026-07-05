"use client";

import Link from "next/link";
import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, Info } from "lucide-react";

import type { EraEvidenceItem } from "@/lib/types";

import { ERA_DIMENSION_COLORS } from "./era-colors";

interface EraEvidenceCardProps {
  item: EraEvidenceItem;
  compact?: boolean;
  minimal?: boolean;
  full?: boolean;
}

function severityIcon(severity: EraEvidenceItem["severity"]) {
  if (severity === "high") {
    return <AlertTriangle className="h-3.5 w-3.5 text-red-400" />;
  }
  return <Info className="h-3.5 w-3.5 text-amber-400" />;
}

function severityLabel(severity: EraEvidenceItem["severity"]) {
  return severity.toUpperCase();
}

export function EraEvidenceCard({
  item,
  compact = false,
  minimal = false,
  full = false,
}: EraEvidenceCardProps) {
  const [expanded, setExpanded] = useState(false);
  const dimension = ERA_DIMENSION_COLORS[item.dimension];
  const longDescription = item.description.length > 140;
  const description =
    full && !expanded && longDescription
      ? `${item.description.slice(0, 140)}…`
      : item.description;

  if (minimal) {
    return (
      <div className="rounded border border-zinc-800/70 bg-zinc-950/40 px-2 py-1">
        <div className="flex min-w-0 items-center gap-1.5">
          {severityIcon(item.severity)}
          <p className="min-w-0 flex-1 truncate text-[10px] leading-tight text-zinc-300">
            {item.title}
          </p>
          <span className="shrink-0 text-[9px] tabular-nums text-zinc-500">
            {Math.round(item.impact_points)}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border border-zinc-800 bg-zinc-950/60 ${
        compact ? "p-3" : "p-4"
      }`}
    >
      <div className="flex items-start gap-2">
        {severityIcon(item.severity)}
        <div className="min-w-0 flex-1">
          {full ? (
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <span
                className={`font-semibold ${
                  item.severity === "high"
                    ? "text-red-300"
                    : item.severity === "medium"
                      ? "text-amber-300"
                      : "text-zinc-400"
                }`}
              >
                {severityLabel(item.severity)}
              </span>
              <span className="text-zinc-600">·</span>
              <span className={dimension.text}>{dimension.label}</span>
              <span className="ml-auto font-medium text-zinc-300">
                {Math.round(item.impact_points)} pts
              </span>
            </div>
          ) : null}

          <p className={`font-medium text-zinc-100 ${full ? "mt-1 text-sm" : "text-sm"}`}>
            {item.title}
          </p>
          {!compact && (
            <p className="mt-1 text-xs leading-relaxed text-zinc-400">{description}</p>
          )}
          {full && longDescription && (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="mt-1 inline-flex items-center gap-0.5 text-[11px] font-medium text-violet-300 hover:text-violet-200"
            >
              {expanded ? (
                <>
                  Show less <ChevronUp className="h-3 w-3" />
                </>
              ) : (
                <>
                  Show more <ChevronDown className="h-3 w-3" />
                </>
              )}
            </button>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
            {!full && (
              <>
                <span className={dimension.text}>{dimension.label}</span>
                <span className="text-zinc-500">·</span>
                <span className="text-zinc-400">
                  {item.sources[0]?.provider ?? "internal"}
                </span>
              </>
            )}
            {item.synthetic && (
              <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-amber-300">
                Estimated
              </span>
            )}
            {item.mitigation_status && item.mitigation_status !== "open" && (
              <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-400">
                {item.mitigation_status.replace("_", " ")}
              </span>
            )}
          </div>

          {full && item.sources.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {item.sources.map((source, index) =>
                source.url ? (
                  <a
                    key={`${source.label}-${index}`}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-[11px] text-sky-300 hover:border-zinc-600 hover:text-sky-200"
                  >
                    {source.label}
                  </a>
                ) : (
                  <span
                    key={`${source.label}-${index}`}
                    className="rounded-md border border-zinc-800 bg-zinc-900/50 px-2 py-1 text-[11px] text-zinc-400"
                  >
                    {source.label}
                  </span>
                ),
              )}
            </div>
          )}

          {full && (
            <div className="mt-3 flex flex-wrap gap-2 print:hidden">
              <Link
                href="/kra"
                className="text-[11px] font-medium text-violet-300 hover:text-violet-200"
              >
                View in KRA
              </Link>
              <span className="text-zinc-700">·</span>
              <span
                className="text-[11px] text-zinc-500"
                title="Mitigation tracking ships in Step 12"
              >
                Mark mitigated (Step 12)
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
