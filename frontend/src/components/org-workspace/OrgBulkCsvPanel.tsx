"use client";

import { useRef, useState } from "react";
import { Download, Loader2, Upload, FileSpreadsheet } from "lucide-react";

import { applyBulkOrgUpload, validateBulkOrgUpload } from "@/lib/api";
import { exportOrgChartCsv, parseOrgChartCsv } from "@/lib/org-csv";
import type { BulkCsvRow, BulkUploadResponse, OrgChartPayload } from "@/lib/types";

interface OrgBulkCsvPanelProps {
  orgChart: OrgChartPayload;
  applyLocally?: boolean;
  onApplied: (orgChart: OrgChartPayload) => void;
  variant?: "inline" | "dialog";
}

export function OrgBulkCsvPanel({
  orgChart,
  applyLocally = false,
  onApplied,
  variant = "inline",
}: OrgBulkCsvPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<BulkCsvRow[] | null>(null);
  const [preview, setPreview] = useState<BulkUploadResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleFile(file: File) {
    setError(null);
    setSuccess(null);
    setPreview(null);

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Only .csv files are supported.");
      return;
    }

    try {
      const parsed = await parseOrgChartCsv(file);
      setRows(parsed);
      setIsValidating(true);
      const result = await validateBulkOrgUpload({
        company: orgChart.company,
        rows: parsed,
        current_org: orgChart,
      });
      setPreview(result);
      if (!result.valid) {
        setError(result.errors.join(" "));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to parse CSV");
      setRows(null);
    } finally {
      setIsValidating(false);
    }
  }

  async function handleApply() {
    if (!rows || !preview?.valid || !preview.merged_org) return;

    setIsApplying(true);
    setError(null);
    setSuccess(null);

    try {
      if (applyLocally) {
        onApplied(preview.merged_org);
        setSuccess("Bulk changes applied to workspace.");
      } else {
        const result = await applyBulkOrgUpload({
          company: orgChart.company,
          rows,
          current_org: orgChart,
        });
        if (result.merged_org) {
          onApplied(result.merged_org);
        }
        const nodes = result.sync_result?.graph_nodes_created ?? 0;
        setSuccess(
          `Bulk changes synced (${nodes} graph nodes re-indexed).`,
        );
      }
      setPreview(null);
      setRows(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk apply failed");
    } finally {
      setIsApplying(false);
    }
  }

  const added = preview?.diff.filter((entry) => entry.kind === "added") ?? [];
  const modified = preview?.diff.filter((entry) => entry.kind === "modified") ?? [];
  const removed = preview?.diff.filter((entry) => entry.kind === "removed") ?? [];

  const containerClass =
    variant === "dialog"
      ? "space-y-4"
      : "space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5";

  return (
    <section className={containerClass}>
      {variant === "inline" && (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="h-4 w-4 text-zinc-400" />
              <h2 className="text-sm font-semibold text-zinc-100">
                Bulk CSV Import / Export
              </h2>
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              Export the directory, edit offline, re-upload for validation and mass
              sync.
            </p>
          </div>
          <button
            type="button"
            onClick={() => exportOrgChartCsv(orgChart)}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900"
          >
            <Download className="h-4 w-4" />
            Export Configuration as CSV
          </button>
        </div>
      )}

      {variant === "dialog" && (
        <button
          type="button"
          onClick={() => exportOrgChartCsv(orgChart)}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900"
        >
          <Download className="h-4 w-4" />
          Export Configuration as CSV
        </button>
      )}

      <div
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const file = event.dataTransfer.files[0];
          if (file) void handleFile(file);
        }}
        className="rounded-lg border border-dashed border-zinc-700 bg-zinc-950/60 px-4 py-8 text-center"
      >
        <Upload className="mx-auto mb-3 h-6 w-6 text-zinc-500" />
        <p className="text-sm text-zinc-300">Drop a .csv file here</p>
        <p className="mt-1 text-xs text-zinc-500">
          Columns: id, name, email, dynamic_role, team_name,
          reports_to_email_or_id
        </p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-4 rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-white"
        >
          Choose CSV file
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void handleFile(file);
            event.target.value = "";
          }}
        />
      </div>

      {isValidating && (
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Validating CSV and computing diff…
        </div>
      )}

      {preview && preview.valid && (
        <div className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-950/50 p-4">
          <h3 className="text-sm font-medium text-zinc-100">Changes Summary</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            <SummaryCard label="New entries" count={added.length} tone="emerald" />
            <SummaryCard label="Modified" count={modified.length} tone="sky" />
            <SummaryCard label="Removed" count={removed.length} tone="amber" />
          </div>
          <div className="max-h-48 space-y-2 overflow-y-auto text-sm">
            {preview.diff.length === 0 && (
              <p className="text-zinc-500">No changes detected vs current org chart.</p>
            )}
            {preview.diff.map((entry) => (
              <div
                key={`${entry.kind}-${entry.employee_id}`}
                className="rounded-md border border-zinc-800 px-3 py-2"
              >
                <p className="font-medium text-zinc-200">
                  {entry.kind.toUpperCase()}: {entry.name}
                </p>
                {entry.changes.map((change) => (
                  <p key={change} className="text-xs text-zinc-500">
                    {change}
                  </p>
                ))}
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => void handleApply()}
            disabled={isApplying || preview.diff.length === 0}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isApplying ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Applying bulk changes…
              </>
            ) : (
              "Apply Bulk Changes"
            )}
          </button>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {success && (
        <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {success}
        </div>
      )}
    </section>
  );
}

function SummaryCard({
  label,
  count,
  tone,
}: {
  label: string;
  count: number;
  tone: "emerald" | "sky" | "amber";
}) {
  const toneClasses = {
    emerald: "border-emerald-500/30 text-emerald-200",
    sky: "border-sky-500/30 text-sky-200",
    amber: "border-amber-500/30 text-amber-200",
  }[tone];

  return (
    <div className={`rounded-lg border px-3 py-2 ${toneClasses}`}>
      <p className="text-xs uppercase tracking-wide opacity-80">{label}</p>
      <p className="text-2xl font-semibold">{count}</p>
    </div>
  );
}
