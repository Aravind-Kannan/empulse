"use client";

import { BrainCircuit } from "lucide-react";

interface GlobalPageLoaderProps {
  label?: string;
}

export function GlobalPageLoader({
  label = "Loading workspace",
}: GlobalPageLoaderProps) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 text-zinc-300">
      <div
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 50% 40%, rgba(99,102,241,0.12), transparent 65%), radial-gradient(ellipse 50% 40% at 80% 80%, rgba(56,189,248,0.08), transparent 55%)",
        }}
      />

      <div className="relative flex flex-col items-center gap-6">
        <div className="relative flex h-20 w-20 items-center justify-center">
          <span className="absolute inset-0 animate-ping rounded-2xl bg-violet-500/10" />
          <span className="absolute inset-1 animate-pulse rounded-2xl border border-violet-500/30 bg-violet-500/5" />
          <div className="relative flex h-14 w-14 items-center justify-center rounded-xl border border-zinc-700/80 bg-zinc-900/80 shadow-xl shadow-violet-950/40 backdrop-blur-sm">
            <BrainCircuit className="h-7 w-7 animate-pulse text-violet-300" />
          </div>
        </div>

        <div className="text-center">
          <p className="text-sm font-medium tracking-wide text-zinc-200">Empulse</p>
          <p className="mt-1 text-xs text-zinc-500">{label}</p>
        </div>

        <div className="flex gap-1">
          {[0, 1, 2].map((index) => (
            <span
              key={index}
              className="h-1.5 w-1.5 rounded-full bg-violet-400/80 animate-bounce"
              style={{ animationDelay: `${index * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
