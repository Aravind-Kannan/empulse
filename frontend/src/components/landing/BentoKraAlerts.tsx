"use client";

import { useEffect, useState } from "react";

const ALERTS = [
  { component: "Payment API", owner: "Alice Chen" },
  { component: "Auth Service", owner: "Ben Rivera" },
  { component: "Checkout", owner: "Cara Patel" },
];

const SEVERITY_STYLES = {
  low: {
    card: "border-emerald-500/30 bg-emerald-500/5",
    badge: "bg-emerald-500/20 text-emerald-300",
    label: "Stable",
  },
  medium: {
    card: "border-amber-500/30 bg-amber-500/5",
    badge: "bg-amber-500/20 text-amber-300",
    label: "SPOF",
  },
  high: {
    card: "border-rose-500/30 bg-rose-500/5",
    badge: "bg-rose-500/20 text-rose-300",
    label: "Critical",
  },
};

export function BentoKraAlerts() {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setPhase((prev) => (prev + 1) % 3);
    }, 2800);
    return () => window.clearInterval(timer);
  }, []);

  const severities = ALERTS.map((_, index) => {
    const level = (index + phase) % 3;
    return level === 0 ? "low" : level === 1 ? "medium" : "high";
  }) as Array<keyof typeof SEVERITY_STYLES>;

  return (
    <div className="flex h-[240px] flex-col gap-3">
      {ALERTS.map((alert, index) => {
        const style = SEVERITY_STYLES[severities[index]];
        return (
          <div
            key={alert.component}
            className={`flex h-[68px] items-center justify-between rounded-xl border px-3 transition-colors duration-700 ${style.card}`}
          >
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-zinc-200">
                {alert.component}
              </p>
              <p className="truncate text-[10px] text-zinc-500">{alert.owner}</p>
            </div>
            <span
              className={`w-16 shrink-0 rounded-md px-2 py-1 text-center text-[10px] font-semibold uppercase tracking-wide transition-colors duration-700 ${style.badge}`}
            >
              {style.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
