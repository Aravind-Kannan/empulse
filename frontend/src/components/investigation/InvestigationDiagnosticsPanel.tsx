"use client";

import { useState, useEffect, useRef } from "react";
import { Activity, AlertCircle, Loader2, RefreshCw, ShieldAlert, Zap, ChevronDown, Check } from "lucide-react";

function ConfidenceSection({ score }: { score: number }) {
  const ringRadius = 28;
  const ringCircumference = 2 * Math.PI * ringRadius;
  const color =
    score >= 75 ? "#10b981" : score >= 50 ? "#f59e0b" : "#ef4444";

  let level = "Low";
  let desc = "Limited historical context found. Based primarily on current incident details.";
  let textColor = "text-red-400";
  
  if (score >= 75) {
    level = "High";
    desc = "Strongly backed by multiple matching historical cases, team assignments, and communication history.";
    textColor = "text-emerald-400";
  } else if (score >= 50) {
    level = "Medium";
    desc = "Supported by moderate historical context and related discussions.";
    textColor = "text-amber-400";
  }

  return (
    <div className="flex items-center gap-4 p-3.5 bg-zinc-900/10 rounded-xl border border-zinc-900/40">
      {/* Confidence ring */}
      <div className="relative flex h-[72px] w-[72px] shrink-0 items-center justify-center">
        <svg
          viewBox="0 0 72 72"
          className="absolute inset-0 h-full w-full -rotate-90"
          aria-hidden
        >
          <circle
            cx="36"
            cy="36"
            r="28"
            fill="none"
            stroke="#27272a"
            strokeWidth="4"
          />
          <circle
            cx="36"
            cy="36"
            r="28"
            fill="none"
            stroke={color}
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={ringCircumference}
            strokeDashoffset={ringCircumference * (1 - score / 100)}
            className="transition-all duration-500 ease-out"
          />
        </svg>
        <div className="relative z-10 flex flex-col items-center justify-center leading-none">
          <span className="text-sm font-bold tabular-nums text-zinc-100">
            {score}
          </span>
          <span className="mt-0.5 text-[9px] font-semibold uppercase tracking-wide text-zinc-500">
            %
          </span>
        </div>
      </div>

      {/* Explanation */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className={`text-xs font-bold uppercase tracking-wider ${textColor}`}>
            {level} Confidence
          </span>
        </div>
        <p className="text-[11px] text-zinc-400 leading-normal">
          {desc}
        </p>
      </div>
    </div>
  );
}

export function InvestigationDiagnosticsPanel({
  rootCause,
  confidence,
  workaround,
  workaroundAvailable = false,
  status,
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
  workaroundAvailable?: boolean;
  status: string;
  statusUpdating: boolean;
  analyzing: boolean;
  analysisMessage: string | null;
  onStatusChange: (status: string) => void;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  const statuses = [
    "Open",
    "Investigating",
    "Waiting for Input",
    "Resolved",
    "Closed",
  ];

  const statusColors: Record<string, string> = {
    Open: "bg-sky-500/10 text-sky-400 border-sky-500/20 hover:bg-sky-500/20",
    Investigating: "bg-amber-500/10 text-amber-400 border-amber-500/20 hover:bg-amber-500/20",
    "Waiting for Input": "bg-purple-500/10 text-purple-400 border-purple-500/20 hover:bg-purple-500/20",
    Resolved: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20",
    Closed: "bg-zinc-800 text-zinc-400 border-zinc-700 hover:bg-zinc-700",
  };

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-800 bg-zinc-950/20 backdrop-blur-sm shadow-xl relative">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800/80 px-4 py-3 bg-zinc-900/10 shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">
              Core Diagnostics
            </h3>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">
              AI Analysis &amp; Status
            </p>
          </div>
        </div>

        {/* Custom Status Dropdown & Refresh Button */}
        <div className="flex items-center gap-2">
          {/* Custom Dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              disabled={statusUpdating}
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold transition-all duration-150 active:scale-95 disabled:opacity-40 disabled:active:scale-100 ${statusColors[status] || "bg-zinc-900 text-zinc-300 border-zinc-800"}`}
            >
              <span>{status}</span>
              <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`} />
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 mt-1.5 w-44 origin-top-right rounded-xl border border-zinc-800 bg-zinc-950 p-1.5 shadow-xl z-50 animate-in fade-in slide-in-from-top-1 duration-100">
                <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-500 border-b border-zinc-900 mb-1">
                  Change Status
                </div>
                <div className="space-y-0.5">
                  {statuses.map((item) => {
                    const isSelected = item === status;
                    return (
                      <button
                        key={item}
                        type="button"
                        onClick={() => {
                          onStatusChange(item);
                          setDropdownOpen(false);
                        }}
                        className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${
                          isSelected
                            ? "bg-zinc-900 text-zinc-100"
                            : "text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200"
                        }`}
                      >
                        <span>{item}</span>
                        {isSelected && <Check className="h-3.5 w-3.5 text-emerald-400" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={analyzing || refreshing}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900/30 text-zinc-400 transition hover:border-zinc-700 hover:text-zinc-200 disabled:opacity-40"
              title="Refresh Diagnostics"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
              />
            </button>
          )}
        </div>
      </div>

      {/* Scrollable Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 scrollbar-thin scrollbar-thumb-zinc-800">
        {/* Status Updating Loader overlay/banner if saving */}
        {statusUpdating && (
          <div className="flex items-center gap-2 rounded-xl border border-sky-500/20 bg-sky-500/5 px-3 py-2.5 text-xs text-sky-300 animate-pulse">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Updating status and syncing system memory…</span>
          </div>
        )}

        {/* Confidence Gauge Section */}
        <div className="bg-zinc-900/10 rounded-xl border border-zinc-900/40 overflow-hidden shrink-0">
          {analyzing && confidence === null ? (
            <div className="flex h-24 flex-col items-center justify-center gap-2 text-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-sky-400" />
              <p className="text-xs text-zinc-400 max-w-[200px] animate-pulse">
                {analysisMessage ?? "Analyzing incident history for diagnostics…"}
              </p>
            </div>
          ) : analyzing && refreshing ? (
            <div className="flex h-24 flex-col items-center justify-center gap-2 text-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-sky-400" />
              <p className="text-xs text-zinc-400 max-w-[220px] animate-pulse">
                {analysisMessage ?? "Refreshing from knowledge graph…"}
              </p>
            </div>
          ) : confidence !== null ? (
            <div className="p-1">
              <ConfidenceSection score={confidence} />
            </div>
          ) : (
            <div className="flex h-24 flex-col items-center justify-center text-center p-4">
              <AlertCircle className="h-5 w-5 text-zinc-600 mb-1" />
              <p className="text-xs text-zinc-500 max-w-[200px]">
                Select an incident card to load diagnostics
              </p>
            </div>
          )}
        </div>

        {/* Probable Root Cause Section */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            <ShieldAlert className="h-3.5 w-3.5 text-amber-500/80" />
            <span>Probable root cause</span>
          </div>
          {analyzing && !rootCause ? (
            <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-4 space-y-2.5">
              <div className="h-3 animate-pulse rounded bg-zinc-800/60" />
              <div className="h-3 w-4/5 animate-pulse rounded bg-zinc-800/60" />
            </div>
          ) : analyzing && refreshing ? (
            <div className="rounded-xl border border-sky-500/20 bg-sky-500/5 p-4 space-y-2.5">
              <div className="flex items-center gap-2 text-xs text-sky-300">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>{analysisMessage ?? "Re-querying knowledge graph…"}</span>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/20 p-4 shadow-inner">
              <p className="text-xs leading-relaxed text-zinc-200 whitespace-pre-wrap">
                {rootCause?.trim() || "No root cause evidence found in system memory. Try syncing integrations or asking the assistant in chat."}
              </p>
            </div>
          )}
        </div>

        {/* Suggested Workarounds & Solutions Section */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            <Zap className="h-3.5 w-3.5 text-emerald-500/80" />
            <span>Suggested workarounds &amp; solutions</span>
          </div>
          {analyzing && !workaround ? (
            <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-4">
              <div className="h-3.5 animate-pulse rounded bg-zinc-800/60" />
            </div>
          ) : workaroundAvailable ? (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 shadow-sm">
              <p className="text-xs leading-relaxed text-emerald-100/90 whitespace-pre-wrap">
                {workaround?.trim()}
              </p>
            </div>
          ) : (
            <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/20 p-4 shadow-inner">
              <p className="text-xs leading-relaxed text-zinc-400 whitespace-pre-wrap">
                {workaround?.trim() ||
                  "No suggested workarounds or solutions found in system memory. Try syncing integrations or asking the assistant in chat."}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
