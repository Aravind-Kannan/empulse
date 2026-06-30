"use client";

import { useEffect, useState } from "react";

const METRICS = [
  { name: "Alice Chen", risk: 72, trend: "up" },
  { name: "Ben Rivera", risk: 41, trend: "down" },
  { name: "Cara Patel", risk: 58, trend: "up" },
];

export function BentoEraMetrics() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(
      () => setActive((p) => (p + 1) % METRICS.length),
      2400,
    );
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="flex h-[148px] flex-col justify-between">
      {METRICS.map((metric, index) => (
        <div
          key={metric.name}
          className={`flex items-center gap-3 rounded-lg border px-3 py-2 transition-opacity duration-500 ${
            index === active
              ? "border-violet-500/30 bg-violet-500/5 opacity-100"
              : "border-zinc-800 bg-transparent opacity-50"
          }`}
        >
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs text-zinc-300">{metric.name}</p>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full rounded-full bg-gradient-to-r from-violet-500 to-rose-500 transition-all duration-700"
                style={{ width: `${metric.risk}%` }}
              />
            </div>
          </div>
          <span className="w-10 shrink-0 text-right text-sm font-semibold tabular-nums text-zinc-200">
            {metric.risk}
          </span>
        </div>
      ))}
    </div>
  );
}
