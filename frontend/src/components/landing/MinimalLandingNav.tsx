"use client";

import Link from "next/link";

interface MinimalLandingNavProps {
  topOffset?: number;
}

export function MinimalLandingNav({ topOffset = 0 }: MinimalLandingNavProps) {
  return (
    <header
      className="fixed inset-x-0 z-50 border-b border-zinc-800/40 bg-black/30 backdrop-blur-md transition-[top] duration-200"
      style={{ top: topOffset }}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <Link href="/" className="group flex items-baseline gap-0.5">
          <span className="text-[15px] font-semibold tracking-[-0.02em] text-zinc-50">
            Empulse
          </span>
          <span className="text-[15px] font-light tracking-[-0.02em] text-zinc-500 transition group-hover:text-zinc-400">
            .
          </span>
        </Link>

        <nav className="hidden items-center gap-7 md:flex">
          <a
            href="#features"
            className="text-[13px] text-zinc-400 transition hover:text-zinc-100"
          >
            Features
          </a>
          <a
            href="#integrations"
            className="text-[13px] text-zinc-400 transition hover:text-zinc-100"
          >
            Integrations
          </a>
        </nav>

        <div className="flex items-center gap-4">
          <Link
            href="/login"
            className="text-[13px] text-zinc-400 transition hover:text-zinc-100"
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className="rounded-full bg-zinc-100 px-4 py-1.5 text-[13px] font-medium text-zinc-950 transition hover:bg-white"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}
