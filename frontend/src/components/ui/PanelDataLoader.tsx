"use client";

import type { LucideIcon } from "lucide-react";

interface PanelDataLoaderProps {
  label: string;
  sublabel?: string;
  icon: LucideIcon;
  steps?: string[];
}

export function PanelDataLoader({
  label,
  sublabel,
  icon: Icon,
  steps,
}: PanelDataLoaderProps) {
  return (
    <div className="flex min-h-[16rem] flex-col items-center justify-center px-6 py-12">
      <div className="relative mb-6 flex h-16 w-16 items-center justify-center">
        <span className="absolute inset-0 animate-ping rounded-2xl bg-violet-500/10" />
        <span className="absolute inset-1 animate-pulse rounded-2xl border border-violet-500/25 bg-violet-500/5" />
        <div className="relative flex h-12 w-12 items-center justify-center rounded-xl border border-zinc-700/80 bg-zinc-900/90 shadow-lg shadow-violet-950/30">
          <Icon className="h-5 w-5 animate-pulse text-violet-300" />
        </div>
      </div>

      <p className="text-sm font-medium text-zinc-200">{label}</p>
      {sublabel ? (
        <p className="mt-1 max-w-sm text-center text-xs text-zinc-500">{sublabel}</p>
      ) : null}

      {steps && steps.length > 0 ? (
        <ul className="mt-5 w-full max-w-xs space-y-2">
          {steps.map((step, index) => (
            <li key={step} className="flex items-center gap-2.5 text-xs text-zinc-500">
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                  index === 0
                    ? "bg-violet-400/90 animate-pulse"
                    : "bg-zinc-700"
                }`}
              />
              <span className={index === 0 ? "text-zinc-400" : undefined}>{step}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-5 flex gap-1">
          {[0, 1, 2].map((index) => (
            <span
              key={index}
              className="h-1.5 w-1.5 rounded-full bg-violet-400/80 animate-bounce"
              style={{ animationDelay: `${index * 0.15}s` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
