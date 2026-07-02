"use client";

import { Check, Loader2 } from "lucide-react";

import type { InvestigationAnalysisPhase } from "@/lib/types";

const STEPS: { phase: InvestigationAnalysisPhase; label: string }[] = [
  { phase: "searching", label: "Analyze historical incidents" },
  { phase: "matching", label: "Match components and owners" },
  { phase: "summarizing", label: "Summarize findings" },
];

const PHASE_ORDER: Record<InvestigationAnalysisPhase, number> = {
  searching: 0,
  matching: 1,
  summarizing: 2,
};

export function InvestigationAnalysisProgress({
  phase,
  message,
}: {
  phase: InvestigationAnalysisPhase;
  message: string;
}) {
  const activeIndex = PHASE_ORDER[phase];

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-300">{message}</p>
      <ul className="space-y-2">
        {STEPS.map((step, index) => {
          const done = index < activeIndex;
          const active = index === activeIndex;
          return (
            <li
              key={step.phase}
              className={`flex items-center gap-2 text-xs ${
                active
                  ? "text-sky-300"
                  : done
                    ? "text-emerald-400/90"
                    : "text-zinc-600"
              }`}
            >
              {done ? (
                <Check className="h-3.5 w-3.5 shrink-0" />
              ) : active ? (
                <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
              ) : (
                <span className="h-3.5 w-3.5 shrink-0 rounded-full border border-zinc-700" />
              )}
              {step.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
