"use client";

import Link from "next/link";

import type { EraEmployeeMetrics, IntegrationId } from "@/lib/types";

import { identityCoverageSummary } from "./era-utils";

const PROVIDER_LABELS: Record<IntegrationId, string> = {
  github: "GitHub",
  jira: "Jira",
  slack: "Slack",
  notion: "Notion",
};

interface EraDataQualityStripProps {
  employee: EraEmployeeMetrics;
}

export function EraDataQualityStrip({ employee }: EraDataQualityStripProps) {
  const { connected, total, missing } = identityCoverageSummary(employee);
  const completeness = Math.round(employee.data_completeness_pct ?? 0);
  const partialDimensions = Object.entries(employee.dimensions?.partial ?? {})
    .filter(([, value]) => value)
    .map(([key]) => key);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium text-zinc-300">Data coverage</p>
        <span className="text-xs text-zinc-500">
          {connected}/{total} identity providers · {completeness}% complete
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {(["github", "jira", "slack", "notion"] as IntegrationId[]).map(
          (provider) => {
            const level = employee.identity_coverage?.[provider] ?? "missing";
            const tone =
              level === "confirmed" || level === "high"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : level === "medium"
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                  : "border-zinc-700 bg-zinc-900 text-zinc-500";
            return (
              <span
                key={provider}
                className={`rounded border px-1.5 py-0.5 text-[10px] ${tone}`}
                title={`${PROVIDER_LABELS[provider]}: ${level}`}
              >
                {PROVIDER_LABELS[provider]}
              </span>
            );
          },
        )}
      </div>
      {(missing.length > 0 || partialDimensions.length > 0) && (
        <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">
          {missing.length > 0 && (
            <>
              Map {missing.map((p) => PROVIDER_LABELS[p]).join(", ")} in{" "}
              <Link
                href="/settings/identity-mapping"
                className="text-violet-300 hover:text-violet-200"
              >
                identity settings
              </Link>
              .
            </>
          )}
          {partialDimensions.length > 0 && (
            <>
              {missing.length > 0 ? " " : ""}
              Partial dimension scores: {partialDimensions.join(", ")}.
            </>
          )}
        </p>
      )}
    </div>
  );
}
