"use client";

import Link from "next/link";
import { Check, Copy, FileDown, LogOut } from "lucide-react";

import type { EraAnalyticsResponse, EraEmployeeMetrics } from "@/lib/types";

import { formatPerProviderSyncFreshness } from "./era-utils";

interface EraDetailFooterProps {
  employee: EraEmployeeMetrics;
  syncFreshness: EraAnalyticsResponse["sync_freshness"];
  onExportPdf: () => void;
  onCopyLink: () => void;
  linkCopied: boolean;
}

export function EraDetailFooter({
  employee,
  syncFreshness,
  onExportPdf,
  onCopyLink,
  linkCopied,
}: EraDetailFooterProps) {
  return (
    <footer className="era-detail-footer border-t border-zinc-800 bg-zinc-950/80 px-5 py-4">
      <p className="text-xs text-zinc-400">
        <span className="font-medium text-zinc-500">Last sync: </span>
        {formatPerProviderSyncFreshness(syncFreshness)}
      </p>

      <div className="mt-4 flex flex-wrap gap-2 print:hidden">
        {!employee.excluded ? (
          <Link
            href={`/exit?employee=${encodeURIComponent(employee.employee_id)}&prefill=era`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-2 text-xs font-medium text-violet-200 hover:bg-violet-500/20"
          >
            <LogOut className="h-3.5 w-3.5" />
            Open knowledge handover
          </Link>
        ) : null}
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
    </footer>
  );
}
