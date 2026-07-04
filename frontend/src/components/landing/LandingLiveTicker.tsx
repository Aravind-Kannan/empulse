"use client";

import { useEffect, useState } from "react";

const MODULES = [
  { abbr: "ERA", label: "Employee Risk Assessment", status: "Scanning attrition signals" },
  { abbr: "KRA", label: "Knowledge Risk Assessment", status: "Detecting SPOF ownership" },
  { abbr: "II", label: "Incident Investigation", status: "Traversing graph hops" },
  { abbr: "EKH", label: "Knowledge Handover", status: "Compiling offboarding pack" },
];

export function LandingLiveTicker() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActive((prev) => (prev + 1) % MODULES.length);
    }, 3200);
    return () => window.clearInterval(timer);
  }, []);

  const current = MODULES[active];

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-col items-center justify-between gap-4 rounded-2xl border border-zinc-800/80 bg-slate-900/40 px-5 py-4 backdrop-blur-md sm:flex-row">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
          </span>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
            Live workspace pulse
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2">
          {MODULES.map((module, index) => (
            <button
              key={module.abbr}
              type="button"
              onClick={() => setActive(index)}
              className={`rounded-full border px-3 py-1 text-[11px] font-semibold transition ${
                index === active
                  ? "border-violet-500/40 bg-violet-500/10 text-violet-200"
                  : "border-zinc-800 bg-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {module.abbr}
            </button>
          ))}
        </div>

        <p className="text-center text-xs text-zinc-400 sm:text-right">
          <span className="font-medium text-zinc-200">{current.label}</span>
          <span className="text-zinc-600"> · </span>
          {current.status}
        </p>
      </div>
    </div>
  );
}
