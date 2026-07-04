"use client";

import Link from "next/link";
import { BrainCircuit } from "lucide-react";

interface LandingNavProps {
  /** Offset below a fixed top banner (px). */
  topOffset?: number;
}

export function LandingNav({ topOffset = 0 }: LandingNavProps) {
  return (
    <header
      className="fixed inset-x-0 z-50 border-b border-zinc-800/80 bg-slate-950/60 backdrop-blur-md transition-[top] duration-200"
      style={{ top: topOffset }}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800/80 bg-slate-900/40">
            <BrainCircuit className="h-4 w-4 text-violet-300" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-zinc-100">
            Empulse
          </span>
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          <a
            href="#pillars"
            className="text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            Core pillars
          </a>
          <a
            href="#platform"
            className="text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            Platform
          </a>
          <a
            href="#architecture"
            className="text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            Architecture
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className="rounded-full border border-zinc-700/80 bg-slate-900/40 px-4 py-1.5 text-sm text-zinc-200 backdrop-blur-sm transition hover:border-zinc-600 hover:bg-slate-900/70"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}
