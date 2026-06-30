"use client";

import { useState } from "react";
import { ArrowRight, BrainCircuit, Shield, Sparkles } from "lucide-react";

import { AuthModal } from "@/components/auth/AuthModal";

export function LandingPage() {
  const [authMode, setAuthMode] = useState<"login" | "signup" | null>(null);

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-800">
            <BrainCircuit className="h-5 w-5 text-zinc-100" />
          </div>
          <div>
            <p className="text-sm font-semibold text-zinc-100">Empulse</p>
            <p className="text-xs text-zinc-500">Engineering Intelligence</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setAuthMode("login")}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900"
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => setAuthMode("signup")}
            className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-white"
          >
            Get Started
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-20 pt-10">
        <section className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/50 px-3 py-1 text-xs text-zinc-400">
              <Sparkles className="h-3.5 w-3.5 text-sky-400" />
              Cognee knowledge graph native
            </div>
            <h1 className="text-4xl font-semibold tracking-tight text-zinc-50 sm:text-5xl">
              Engineering Intelligence Powered by Cognee
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-zinc-400">
              Unify org knowledge, incident response, risk analytics, and
              offboarding into one manager cockpit — built on a live engineering
              graph.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setAuthMode("signup")}
                className="inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-5 py-3 text-sm font-medium text-slate-950 transition hover:bg-white"
              >
                Get Started / Sign Up
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setAuthMode("login")}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-5 py-3 text-sm text-zinc-300 transition hover:bg-zinc-900"
              >
                Login
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-gradient-to-br from-zinc-900/80 to-slate-950 p-6">
            <div className="space-y-4">
              {[
                {
                  icon: Shield,
                  title: "Risk & dependency visibility",
                  copy: "ERA, KRA, and incident workspaces share one operational graph.",
                },
                {
                  icon: BrainCircuit,
                  title: "Cognee-powered traversal",
                  copy: "Mock graph hops connect ownership, incidents, and handover packs.",
                },
                {
                  icon: Sparkles,
                  title: "Manager-first onboarding",
                  copy: "New teams start with org chart ingest; returning managers jump to the cockpit.",
                },
              ].map(({ icon: Icon, title, copy }) => (
                <div
                  key={title}
                  className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4"
                >
                  <div className="mb-2 flex items-center gap-2">
                    <Icon className="h-4 w-4 text-sky-400" />
                    <p className="text-sm font-medium text-zinc-100">{title}</p>
                  </div>
                  <p className="text-sm text-zinc-500">{copy}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      {authMode && (
        <AuthModal
          mode={authMode}
          onClose={() => setAuthMode(null)}
          onSwitchMode={setAuthMode}
        />
      )}
    </div>
  );
}
