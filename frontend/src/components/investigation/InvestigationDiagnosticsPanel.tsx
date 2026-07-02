"use client";

import { Loader2, RefreshCw } from "lucide-react";

function ConfidenceGauge({ score }: { score: number }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score >= 75 ? "#34d399" : score >= 50 ? "#fbbf24" : "#f87171";

  return (
    <div className="relative mx-auto h-36 w-36">
      <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90">
        <circle
          cx="64"
          cy="64"
          r={radius}
          fill="none"
          stroke="#3f3f46"
          strokeWidth="10"
        />
        <circle
          cx="64"
          cy="64"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold text-zinc-100">{score}%</span>
        <span className="text-[10px] uppercase tracking-wide text-zinc-500">
          Confidence
        </span>
      </div>
    </div>
  );
}

export function InvestigationDiagnosticsPanel({
  rootCause,
  confidence,
  workaround,
  status,
  graphHops,
  statusUpdating,
  analyzing,
  analysisMessage,
  onStatusChange,
  onRefresh,
  refreshing = false,
}: {
  rootCause: string | null;
  confidence: number | null;
  workaround: string | null;
  status: string;
  graphHops: string[];
  statusUpdating: boolean;
  analyzing: boolean;
  analysisMessage: string | null;
  onStatusChange: (status: string) => void;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  const statuses = [
    "Open",
    "Investigating",
    "Waiting for Input",
    "Resolved",
    "Closed",
  ];

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Core diagnostics
        </h3>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={analyzing || refreshing}
            className="inline-flex items-center gap-1 rounded-md border border-zinc-700 px-2 py-1 text-[10px] uppercase tracking-wide text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-200 disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        )}
      </div>

      {analyzing ? (
        <div className="flex h-36 flex-col items-center justify-center gap-2 text-center">
          <Loader2 className="h-6 w-6 animate-spin text-sky-400" />
          <p className="text-sm text-zinc-400">
            {analysisMessage ?? "Analyzing incident…"}
          </p>
        </div>
      ) : confidence !== null ? (
        <ConfidenceGauge score={confidence} />
      ) : (
        <div className="flex h-36 items-center justify-center text-sm text-zinc-500">
          Run a question in chat to see analysis
        </div>
      )}

      <div className="mt-4 space-y-4">
        <div>
          <p className="mb-1 text-xs font-medium uppercase text-zinc-500">
            Probable root cause
          </p>
          {analyzing ? (
            <div className="space-y-2">
              <div className="h-3 animate-pulse rounded bg-zinc-800" />
              <div className="h-3 w-4/5 animate-pulse rounded bg-zinc-800" />
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-zinc-200">
              {rootCause ?? "—"}
            </p>
          )}
        </div>

        <div>
          <p className="mb-1 text-xs font-medium uppercase text-zinc-500">
            Immediate emergency workaround
          </p>
          {analyzing ? (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
              <div className="h-3 animate-pulse rounded bg-zinc-800" />
            </div>
          ) : (
            <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
              {workaround ?? "—"}
            </p>
          )}
        </div>

        {graphHops.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium uppercase text-zinc-500">
              Related connections
            </p>
            <ul className="space-y-1 text-xs text-zinc-400">
              {graphHops.map((hop) => (
                <li key={hop} className="font-mono">
                  {hop}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <label className="mb-1 block text-xs font-medium uppercase text-zinc-500">
            Incident status
          </label>
          <div className="relative">
            <select
              value={status}
              disabled={statusUpdating}
              onChange={(e) => onStatusChange(e.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500 disabled:opacity-60"
            >
              {statuses.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            {statusUpdating && (
              <div className="mt-2 flex items-center gap-2 text-xs text-sky-400">
                <Loader2 className="h-3 w-3 animate-spin" />
                Saving status…
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
