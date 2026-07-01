"use client";

import Link from "next/link";
import { Check, Copy, FileDown, Minus } from "lucide-react";

import type {
  EraAnalyticsResponse,
  EraEmployeeMetrics,
  IntegrationId,
  IdentityCoverageLevel,
} from "@/lib/types";

import {
  formatPerProviderSyncFreshness,
  formatProviderSyncAge,
} from "./era-utils";

interface EraDetailFooterProps {
  employee: EraEmployeeMetrics;
  syncFreshness: EraAnalyticsResponse["sync_freshness"];
  onExportPdf: () => void;
  onCopyLink: () => void;
  linkCopied: boolean;
}

const PROVIDERS: IntegrationId[] = ["github", "jira", "slack", "notion"];

const PROVIDER_LABELS: Record<IntegrationId, string> = {
  github: "GitHub",
  jira: "Jira",
  slack: "Slack",
  notion: "Notion",
};

function coverageIcon(level: IdentityCoverageLevel | undefined) {
  if (level === "confirmed" || level === "high") {
    return <Check className="h-3 w-3 text-emerald-400" />;
  }
  return <Minus className="h-3 w-3 text-zinc-500" />;
}

export function EraDetailFooter({
  employee,
  syncFreshness,
  onExportPdf,
  onCopyLink,
  linkCopied,
}: EraDetailFooterProps) {
  const coverage = employee.identity_coverage ?? {};
  const completeness = employee.data_completeness_pct ?? 0;

  return (
    <footer className="era-detail-footer border-t border-zinc-800 bg-zinc-950/80 px-5 py-4">
      <div className="space-y-3 text-xs text-zinc-400">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-medium text-zinc-500">Identity:</span>
          {PROVIDERS.map((provider) => (
            <span key={provider} className="inline-flex items-center gap-1">
              {coverageIcon(coverage[provider])}
              {PROVIDER_LABELS[provider]}
            </span>
          ))}
          <Link
            href="/settings/identity-mapping"
            className="text-violet-300 hover:text-violet-200"
          >
            Fix mapping
          </Link>
        </div>

        <p>
          <span className="font-medium text-zinc-500">Last sync: </span>
          {formatPerProviderSyncFreshness(syncFreshness)}
        </p>

        <p>
          <span className="font-medium text-zinc-500">Data completeness: </span>
          {completeness}%
        </p>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 print:hidden">
        <button
          type="button"
          onClick={onExportPdf}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800"
        >
          <FileDown className="h-3.5 w-3.5" />
          Export PDF
        </button>
        <button
          type="button"
          onClick={onCopyLink}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800"
        >
          <Copy className="h-3.5 w-3.5" />
          {linkCopied ? "Link copied" : "Copy link"}
        </button>
      </div>

      <p className="mt-2 hidden text-[10px] text-zinc-600 print:block">
        Sync snapshot:{" "}
        {PROVIDERS.map(
          (provider) =>
            `${PROVIDER_LABELS[provider]} ${formatProviderSyncAge(syncFreshness[provider])}`,
        ).join(" · ")}
      </p>
    </footer>
  );
}
