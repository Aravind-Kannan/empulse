"use client";

import { motion } from "framer-motion";

import { useReducedMotion } from "@/hooks/useReducedMotion";

const NODES = [
  { x: "12%", y: "22%", size: 6, delay: 0 },
  { x: "78%", y: "18%", size: 8, delay: 0.4 },
  { x: "88%", y: "62%", size: 5, delay: 0.8 },
  { x: "18%", y: "72%", size: 7, delay: 1.2 },
  { x: "52%", y: "12%", size: 4, delay: 0.6 },
  { x: "42%", y: "84%", size: 5, delay: 1.0 },
];

const EDGES = [
  [0, 4],
  [4, 1],
  [1, 2],
  [0, 3],
  [3, 5],
  [5, 2],
] as const;

export function LandingHeroBackdrop() {
  const reducedMotion = useReducedMotion();

  if (reducedMotion) {
    return (
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        aria-hidden
        style={{
          background:
            "radial-gradient(ellipse 50% 40% at 50% 30%, rgba(99,102,241,0.12), transparent 70%)",
        }}
      />
    );
  }

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <div
        className="absolute inset-0 opacity-50"
        style={{
          background:
            "radial-gradient(ellipse 55% 45% at 50% 35%, rgba(99,102,241,0.14), transparent 65%), radial-gradient(ellipse 40% 30% at 80% 70%, rgba(56,189,248,0.08), transparent 60%)",
        }}
      />

      <svg className="absolute inset-0 h-full w-full">
        {EDGES.map(([from, to], index) => {
          const a = NODES[from];
          const b = NODES[to];
          return (
            <line
              key={`${from}-${to}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="url(#hero-edge)"
              strokeWidth="1"
              strokeDasharray="4 6"
              className="landing-graph-edge"
              style={{ animationDelay: `${index * 0.3}s` }}
            />
          );
        })}
        <defs>
          <linearGradient id="hero-edge" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.1" />
            <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#a78bfa" stopOpacity="0.1" />
          </linearGradient>
        </defs>
      </svg>

      {NODES.map((node, index) => (
        <motion.span
          key={index}
          className="absolute rounded-full bg-violet-400/30 ring-1 ring-violet-400/40"
          style={{
            left: node.x,
            top: node.y,
            width: node.size * 4,
            height: node.size * 4,
            marginLeft: -(node.size * 2),
            marginTop: -(node.size * 2),
          }}
          animate={{
            y: [0, -10, 0],
            opacity: [0.35, 0.75, 0.35],
          }}
          transition={{
            duration: 4 + index * 0.4,
            repeat: Infinity,
            ease: "easeInOut",
            delay: node.delay,
          }}
        />
      ))}
    </div>
  );
}
