"use client";

import { Info } from "lucide-react";
import type { LucideIcon } from "lucide-react";

function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="group/info relative inline-flex shrink-0">
      <span
        role="img"
        aria-label="More detail"
        className="rounded p-0.5 text-zinc-500 hover:text-zinc-300"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
      >
        <Info className="h-3 w-3" aria-hidden />
      </span>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-0 z-10 mb-1 hidden w-56 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-[10px] font-normal normal-case leading-snug tracking-normal text-zinc-300 shadow-lg group-hover/info:block"
      >
        {text}
      </span>
    </span>
  );
}

export function IntegrationStatCard({
  label,
  value,
  hint,
  info,
  icon: Icon,
  compactValue = false,
  className = "",
}: {
  label: string;
  value: string | number;
  hint?: string;
  info?: string;
  icon: LucideIcon;
  compactValue?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-4 py-3 backdrop-blur-sm ${className}`}
    >
      <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{label}</span>
        {info && <InfoTooltip text={info} />}
      </div>
      <p
        className={
          compactValue
            ? "mt-1.5 text-sm font-medium leading-snug text-zinc-100"
            : "mt-1 text-2xl font-semibold tabular-nums text-zinc-100"
        }
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-[11px] text-zinc-500">{hint}</p>}
    </div>
  );
}
