"use client";

import { X } from "lucide-react";

import { OrgBulkCsvPanel } from "@/components/org-workspace/OrgBulkCsvPanel";
import type { OrgChartPayload } from "@/lib/types";

interface OrgBulkCsvDialogProps {
  orgChart: OrgChartPayload;
  applyLocally?: boolean;
  onApplied: (orgChart: OrgChartPayload) => void;
  onClose: () => void;
}

export function OrgBulkCsvDialog({
  orgChart,
  applyLocally = false,
  onApplied,
  onClose,
}: OrgBulkCsvDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-zinc-700 bg-slate-950 shadow-xl">
        <div className="flex shrink-0 items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <h3 className="text-lg font-medium text-zinc-100">
              Bulk CSV Import / Export
            </h3>
            <p className="mt-0.5 text-xs text-zinc-500">
              Export, edit offline, then re-upload for validation and sync.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-4">
          <OrgBulkCsvPanel
            orgChart={orgChart}
            applyLocally={applyLocally}
            onApplied={(next) => {
              onApplied(next);
              onClose();
            }}
            variant="dialog"
          />
        </div>
      </div>
    </div>
  );
}
