"use client";

import { useEffect, useState } from "react";
import { Bot, MessageSquare, Search, ShieldAlert, Users } from "lucide-react";

const GRAPH_HOPS = [
  { from: "PROJ-442", edge: "MENTIONS", to: "Payment API" },
  { from: "Payment API", edge: "OWNED_BY", to: "Alice Chen" },
  { from: "PROJ-442", edge: "THREAD_IN", to: "#incident-checkout" },
];

const CHAT_LINES = [
  "What caused the checkout timeout spike?",
  "Tracing multi-hop graph across Jira + Slack…",
  "Root cause: Redis connection pool exhaustion on Payment API.",
];

export function BentoInvestigationWorkspace() {
  const [activeHop, setActiveHop] = useState(0);
  const [chatLine, setChatLine] = useState(0);

  useEffect(() => {
    const hopTimer = window.setInterval(() => {
      setActiveHop((prev) => (prev + 1) % GRAPH_HOPS.length);
    }, 2200);
    return () => window.clearInterval(hopTimer);
  }, []);

  useEffect(() => {
    const chatTimer = window.setInterval(() => {
      setChatLine((prev) => (prev + 1) % CHAT_LINES.length);
    }, 2800);
    return () => window.clearInterval(chatTimer);
  }, []);

  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-800/80 bg-slate-950/90">
      <div className="flex items-center justify-between border-b border-zinc-800/80 bg-slate-900/60 px-4 py-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-500">
          Incident Investigation — 3-Panel Workspace
        </p>
        <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-300">
          Live graph triage
        </span>
      </div>

      <div className="grid h-[280px] grid-cols-3 divide-x divide-zinc-800/80">
        {/* Chat panel */}
        <div className="flex flex-col bg-slate-900/20 p-3">
          <div className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-zinc-500">
            <MessageSquare className="h-3 w-3" />
            Assistant
          </div>
          <div className="flex-1 space-y-2">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/80 px-2.5 py-2">
              <p className="text-[10px] text-zinc-400">{CHAT_LINES[0]}</p>
            </div>
            <div className="rounded-lg border border-sky-500/20 bg-sky-500/5 px-2.5 py-2">
              <div className="mb-1 flex items-center gap-1 text-[9px] text-sky-400">
                <Bot className="h-2.5 w-2.5" />
                Cognee
              </div>
              <p className="text-[10px] leading-relaxed text-sky-100/90 transition-opacity duration-500">
                {CHAT_LINES[chatLine]}
              </p>
            </div>
          </div>
        </div>

        {/* Diagnostics + graph hops */}
        <div className="flex flex-col bg-slate-900/30 p-3">
          <div className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-zinc-500">
            <ShieldAlert className="h-3 w-3 text-amber-400" />
            Diagnostics
          </div>
          <div className="mb-3 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2">
            <p className="text-[9px] uppercase tracking-wider text-zinc-600">
              Probable root cause
            </p>
            <p className="mt-1 text-[10px] leading-relaxed text-zinc-300">
              Connection pool saturation on Payment API after deploy PROJ-441.
            </p>
          </div>
          <div className="flex-1 space-y-1.5">
            <p className="text-[9px] uppercase tracking-wider text-zinc-600">
              Graph hops
            </p>
            {GRAPH_HOPS.map((hop, index) => (
              <div
                key={`${hop.from}-${hop.edge}-${hop.to}`}
                className={`flex items-center gap-1 rounded-md border px-2 py-1.5 font-mono text-[9px] transition-all duration-500 ${
                  index === activeHop
                    ? "border-violet-500/40 bg-violet-500/10 text-violet-200"
                    : "border-zinc-800/80 bg-transparent text-zinc-500"
                }`}
              >
                <span className="truncate text-sky-300/90">[{hop.from}]</span>
                <span className="shrink-0 text-zinc-600">→</span>
                <span className="shrink-0 text-amber-400/80">{hop.edge}</span>
                <span className="shrink-0 text-zinc-600">→</span>
                <span className="truncate text-emerald-300/90">[{hop.to}]</span>
              </div>
            ))}
          </div>
        </div>

        {/* Context panel */}
        <div className="flex flex-col bg-slate-900/20 p-3">
          <div className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-zinc-500">
            <Search className="h-3 w-3" />
            Context
          </div>
          <p className="mb-2 text-[9px] uppercase tracking-wider text-zinc-600">
            Recommended SMEs
          </p>
          <div className="space-y-1.5">
            {[
              { name: "Alice Chen", score: 94, role: "Payment API owner" },
              { name: "Ben Rivera", score: 78, role: "Redis on-call" },
            ].map((sme, index) => (
              <div
                key={sme.name}
                className={`flex items-center gap-2 rounded-lg border px-2 py-1.5 transition-colors duration-500 ${
                  index === activeHop % 2
                    ? "border-emerald-500/30 bg-emerald-500/5"
                    : "border-zinc-800/80 bg-zinc-950/40"
                }`}
              >
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-zinc-700 bg-zinc-900">
                  <Users className="h-3 w-3 text-zinc-500" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[10px] font-medium text-zinc-200">
                    {sme.name}
                  </p>
                  <p className="truncate text-[9px] text-zinc-500">{sme.role}</p>
                </div>
                <span className="shrink-0 text-[10px] font-semibold text-sky-400">
                  {sme.score}%
                </span>
              </div>
            ))}
          </div>
          <div className="mt-auto rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-2 py-1.5">
            <p className="text-[9px] text-zinc-500">
              Slack <span className="text-zinc-400">#incident-checkout</span> · Jira{" "}
              <span className="text-zinc-400">PROJ-442</span> · Notion runbook linked
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
