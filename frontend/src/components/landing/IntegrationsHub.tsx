"use client";

import { motion } from "framer-motion";

import { IntegrationLogo } from "@/components/integrations/IntegrationLogos";
import { REVEAL_EASE } from "@/components/landing/ScrollReveal";
import { useReducedMotion } from "@/hooks/useReducedMotion";

const INTEGRATIONS = [
  {
    id: "github" as const,
    name: "GitHub",
    synced: true,
    position: "top-[8%] left-[6%]",
    delay: 0,
  },
  {
    id: "jira" as const,
    name: "Jira",
    synced: true,
    position: "top-[8%] right-[6%]",
    delay: 0.15,
  },
  {
    id: "slack" as const,
    name: "Slack",
    synced: false,
    position: "bottom-[10%] left-[8%]",
    delay: 0.3,
  },
  {
    id: "notion" as const,
    name: "Notion",
    synced: false,
    position: "bottom-[10%] right-[8%]",
    delay: 0.45,
  },
] as const;

const EDGES = [
  { x1: "22%", y1: "22%", x2: "50%", y2: "50%" },
  { x1: "78%", y1: "22%", x2: "50%", y2: "50%" },
  { x1: "24%", y1: "78%", x2: "50%", y2: "50%" },
  { x1: "76%", y1: "78%", x2: "50%", y2: "50%" },
] as const;

function IntegrationNode({
  id,
  name,
  synced,
  position,
  delay,
  reducedMotion,
}: {
  id: (typeof INTEGRATIONS)[number]["id"];
  name: string;
  synced: boolean;
  position: string;
  delay: number;
  reducedMotion: boolean;
}) {
  const motionProps = reducedMotion
    ? {}
    : {
        initial: { opacity: 0, scale: 0.8, y: 12 },
        whileInView: { opacity: 1, scale: 1, y: 0 },
        viewport: { once: true, amount: 0.4 },
        transition: { duration: 0.7, ease: REVEAL_EASE, delay },
      };

  return (
    <motion.div
      className={`absolute ${position} z-10 w-[132px]`}
      {...motionProps}
    >
      <div
        className={`relative overflow-hidden rounded-2xl border px-4 py-3.5 backdrop-blur-md transition duration-500 ${
          synced
            ? "border-emerald-500/30 bg-emerald-950/20 shadow-[0_0_24px_rgba(16,185,129,0.08)]"
            : "border-zinc-700/50 bg-zinc-950/60 hover:border-zinc-600/60"
        }`}
      >
        {synced ? (
          <span className="absolute right-3 top-3 h-1.5 w-1.5 rounded-full bg-emerald-400 landing-sync-pulse" />
        ) : null}
        <div
          className={`mb-2 flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-700/60 bg-black/40 ${
            id === "notion" ? "text-zinc-100" : ""
          }`}
        >
          <IntegrationLogo id={id} className="h-4 w-4" />
        </div>
        <p className="text-sm font-medium text-zinc-100">{name}</p>
        <p
          className={`mt-0.5 text-[11px] ${
            synced ? "text-emerald-400/90" : "text-zinc-500"
          }`}
        >
          {synced ? "Live in graph" : "Ready to connect"}
        </p>
      </div>
    </motion.div>
  );
}

export function IntegrationsHub() {
  const reducedMotion = useReducedMotion();

  return (
    <div className="relative mx-auto aspect-[4/3] w-full max-w-xl overflow-hidden rounded-3xl border border-zinc-800/50 bg-gradient-to-b from-zinc-950/80 to-black/90 p-2 ring-1 ring-white/[0.04]">
      <div
        className="pointer-events-none absolute inset-0 opacity-60"
        aria-hidden
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(99,102,241,0.12), transparent 55%)",
        }}
      />

      <svg
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden
      >
        <defs>
          <linearGradient id="hub-edge" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#71717a" stopOpacity="0.05" />
            <stop offset="50%" stopColor="#a1a1aa" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#71717a" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        {EDGES.map((edge, index) => (
          <line
            key={index}
            x1={edge.x1}
            y1={edge.y1}
            x2={edge.x2}
            y2={edge.y2}
            stroke="url(#hub-edge)"
            strokeWidth="1"
            strokeDasharray="5 7"
            className={reducedMotion ? "" : "landing-graph-edge"}
            style={{ animationDelay: `${index * 0.4}s` }}
          />
        ))}
      </svg>

      <div className="absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2">
        {reducedMotion ? (
          <div className="flex h-24 w-24 flex-col items-center justify-center rounded-full border border-violet-500/30 bg-violet-950/30 backdrop-blur-md">
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-violet-300/80">
              Cognee
            </span>
            <span className="mt-0.5 text-xs text-zinc-400">Graph</span>
          </div>
        ) : (
          <motion.div
            className="landing-hub-pulse flex h-24 w-24 flex-col items-center justify-center rounded-full border border-violet-500/40 bg-violet-950/40 shadow-[0_0_40px_rgba(139,92,246,0.15)] backdrop-blur-md"
            initial={{ opacity: 0, scale: 0.6 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.9, ease: REVEAL_EASE }}
          >
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-violet-300">
              Cognee
            </span>
            <span className="mt-0.5 text-xs text-zinc-400">Graph</span>
          </motion.div>
        )}
      </div>

      {INTEGRATIONS.map((item) => (
        <IntegrationNode
          key={item.id}
          id={item.id}
          name={item.name}
          synced={item.synced}
          position={item.position}
          delay={item.delay}
          reducedMotion={reducedMotion}
        />
      ))}

      <div className="absolute bottom-4 left-1/2 z-10 -translate-x-1/2">
        <p className="text-center text-[10px] uppercase tracking-[0.18em] text-zinc-600">
          Edges sync on connect
        </p>
      </div>
    </div>
  );
}
