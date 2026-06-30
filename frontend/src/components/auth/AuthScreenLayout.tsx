"use client";

import Link from "next/link";
import { BrainCircuit } from "lucide-react";

interface AuthScreenLayoutProps {
  mode: "login" | "signup";
  children: React.ReactNode;
}

const MARKETING = {
  login: {
    headline: "Engineering intelligence, decoded.",
    subline: "Welcome back.",
  },
  signup: {
    headline: "Engineering intelligence, decoded.",
    subline: "Create your workspace in minutes.",
  },
};

export function AuthScreenLayout({ mode, children }: AuthScreenLayoutProps) {
  const copy = MARKETING[mode];

  return (
    <div className="relative flex min-h-screen bg-black text-zinc-100">
      {/* Ambient background */}
      <div className="auth-ambient pointer-events-none absolute inset-0" />

      {/* Left marketing pane — hidden on small screens */}
      <div className="relative hidden w-1/2 flex-col justify-between border-r border-white/5 p-12 lg:flex">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/5 ring-1 ring-white/10">
            <BrainCircuit className="h-4 w-4 text-zinc-200" />
          </div>
          <span className="text-sm font-semibold tracking-tight">Empulse</span>
        </Link>

        <div className="max-w-md">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-zinc-500">
            Engineering Intelligence
          </p>
          <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-tight text-zinc-50">
            {copy.headline}
          </h1>
          <p className="landing-metallic-text mt-3 text-2xl font-medium">
            {copy.subline}
          </p>
          <p className="mt-6 text-sm leading-relaxed text-zinc-500">
            Unify org knowledge, incident response, risk analytics, and
            offboarding in one Cognee-powered manager cockpit.
          </p>
        </div>

        <p className="text-xs text-zinc-600">
          © {new Date().getFullYear()} Empulse · Powered by Cognee
        </p>
      </div>

      {/* Right form pane */}
      <div className="relative flex w-full flex-col items-center justify-center px-6 py-12 lg:w-1/2">
        <Link
          href="/"
          className="absolute left-6 top-6 flex items-center gap-2 lg:hidden"
        >
          <BrainCircuit className="h-5 w-5 text-zinc-400" />
          <span className="text-sm font-medium text-zinc-300">Empulse</span>
        </Link>

        <div className="w-full max-w-md">
          <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-8 shadow-2xl ring-1 ring-white/10 backdrop-blur-xl">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
