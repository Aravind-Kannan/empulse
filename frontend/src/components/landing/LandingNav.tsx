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
      className="fixed inset-x-0 z-50 border-b border-white/5 bg-black/40 backdrop-blur-md transition-[top] duration-200"
      style={{ top: topOffset }}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/5 ring-1 ring-white/10">
            <BrainCircuit className="h-4 w-4 text-zinc-200" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-zinc-100">
            Empulse
          </span>
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          <a
            href="#platform"
            className="text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            Platform
          </a>
          <a
            href="#how-it-works"
            className="text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            How it works
          </a>
          <a
            href="#capabilities"
            className="text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            Capabilities
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            Login
          </Link>
          <Link
            href="/signup"
            className="rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm text-zinc-200 transition hover:bg-white/10"
          >
            Get Started
          </Link>
        </div>
      </div>
    </header>
  );
}
